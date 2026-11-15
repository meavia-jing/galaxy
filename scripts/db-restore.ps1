<#
.SYNOPSIS
  从 mariadb-dump 备份恢复数据库，恢复前做校验与安全备份。

.DESCRIPTION
  顺序：校验 .sha256 -> 目标库非空时先做安全备份 -> 确认 -> 恢复 -> 报告表数。
  安全备份落在 backups/pre-restore-<库>-<时间戳>.sql，恢复失败时可按提示回灌。

.EXAMPLE
  pwsh -File scripts\db-restore.ps1 -DumpFile backups\shop-20261115-180000.sql -Database shop_restore_check -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DumpFile,
    [string]$Database = "shop",
    [switch]$Force,
    [switch]$SkipSafetyBackup,
    [string]$MariaBin = "",
    [string]$AdminUser = "",
    [string]$AdminPassword = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Step([string]$Message) { Write-Host "[RESTORE] $Message" }

function Resolve-MariaBin {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:MARIA_BIN) { $candidates += $env:MARIA_BIN }
    if ($env:MARIA_HOME) { $candidates += (Join-Path $env:MARIA_HOME "bin") }
    $candidates += "D:\mariadb\bin"
    $candidates += "C:\Program Files\MariaDB 11.4\bin"
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path (Join-Path $dir "mariadb.exe"))) { return $dir }
    }
    $cmd = Get-Command mariadb -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path -Parent $cmd.Source) }
    throw "找不到 mariadb 客户端。请用 -MariaBin 指定，或设置 MARIA_BIN 环境变量。"
}

function Read-DotEnv([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) { continue }
        $map[$trimmed.Substring(0, $idx).Trim()] = $trimmed.Substring($idx + 1).Trim()
    }
    return $map
}

function New-ClientDefaultsFile([hashtable]$EnvMap) {
    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("shop-my-{0}.cnf" -f ([guid]::NewGuid().ToString("N")))
    $content = @(
        "[client]",
        "user=$($EnvMap['DB_USER'])",
        "password=$($EnvMap['DB_PASSWORD'])",
        "host=$($EnvMap['DB_HOST'])",
        "port=$($EnvMap['DB_PORT'])",
        "default-character-set=utf8mb4"
    ) -join "`n"
    Set-Content -Path $path -Value $content -Encoding ascii -NoNewline
    return $path
}

function Invoke-Client([string]$Bin, [string]$DefaultsFile, [string[]]$Arguments) {
    & (Join-Path $Bin "mariadb.exe") "--defaults-file=$DefaultsFile" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "mariadb 执行失败，退出码 $LASTEXITCODE" }
}

$dumpPath = if ([System.IO.Path]::IsPathRooted($DumpFile)) { $DumpFile } else { Join-Path $repoRoot $DumpFile }
if (-not (Test-Path $dumpPath)) { throw "备份文件不存在：$dumpPath" }

$sidecar = "$dumpPath.sha256"
if (Test-Path $sidecar) {
    $expected = ((Get-Content $sidecar -Raw).Trim() -split "\s+")[0].ToLower()
    $actual = (Get-FileHash -Path $dumpPath -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "校验值不匹配：期望 $expected，实得 $actual。文件可能损坏，拒绝恢复。" }
    Write-Step "SHA256 校验通过"
} else {
    Write-Warning "未找到 $sidecar，跳过校验值比对。"
}

$envFile = if (Test-Path (Join-Path $repoRoot "backend\.env")) {
    Join-Path $repoRoot "backend\.env"
} else {
    Join-Path $repoRoot ".env"
}
$envMap = Read-DotEnv $envFile
foreach ($key in @("DB_USER", "DB_PASSWORD")) {
    if (-not $envMap.ContainsKey($key) -or -not $envMap[$key]) { throw "未在 $envFile 中找到 $key。" }
}
if (-not $envMap.ContainsKey("DB_HOST")) { $envMap["DB_HOST"] = "127.0.0.1" }
if (-not $envMap.ContainsKey("DB_PORT")) { $envMap["DB_PORT"] = "3306" }

$bin = Resolve-MariaBin -Explicit $MariaBin
$defaultsFile = New-ClientDefaultsFile $envMap

# 恢复到非当前库（如恢复演练的临时库）需要建库权限：shop 账号没有，
# 必须显式给 -AdminUser，否则直接拒绝，避免跑到一半失败留下半套数据。
$applyDefaults = $defaultsFile
$adminDefaultsFile = $null
if ($Database -ne $envMap["DB_NAME"]) {
    if (-not $AdminUser) {
        throw "目标库 $Database 与 DB_NAME 不同，需要 -AdminUser/-AdminPassword 才能建库并写入。"
    }
    $adminDefaultsFile = New-ClientDefaultsFile @{
        DB_USER     = $AdminUser
        DB_PASSWORD = $AdminPassword
        DB_HOST     = $envMap["DB_HOST"]
        DB_PORT     = $envMap["DB_PORT"]
    }
    $applyDefaults = $adminDefaultsFile
}

try {
    $existing = Invoke-Client $bin $applyDefaults @(
        "--skip-column-names", "--batch", "-e",
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$Database';"
    )
    $tableCount = [int](@($existing)[0].Trim())

    if (-not $Force) {
        Write-Host ""
        Write-Host "即将把 $dumpPath" -ForegroundColor Yellow
        Write-Host "恢复到库 $Database（当前 $tableCount 张表，已有数据会被覆盖）" -ForegroundColor Yellow
        $answer = Read-Host "输入库名确认，其他任意输入取消"
        if ($answer -ne $Database) { Write-Step "已取消"; exit 1 }
    }

    if ($tableCount -gt 0 -and -not $SkipSafetyBackup) {
        $safetyDir = Join-Path $repoRoot "backups"
        New-Item -ItemType Directory -Force -Path $safetyDir | Out-Null
        $safety = Join-Path $safetyDir ("pre-restore-{0}-{1}.sql" -f $Database, (Get-Date -Format "yyyyMMdd-HHmmss"))
        Write-Step "恢复前安全备份 -> $safety"
        & (Join-Path $bin "mariadb-dump.exe") "--defaults-file=$applyDefaults" `
            "--single-transaction" "--quick" "--routines" "--triggers" `
            "--default-character-set=utf8mb4" "--result-file=$safety" $Database
        if ($LASTEXITCODE -ne 0) { throw "安全备份失败，已中止恢复。" }
    }

    Invoke-Client $bin $applyDefaults @("-e", "CREATE DATABASE IF NOT EXISTS ``$Database`` CHARACTER SET utf8mb4")
    Write-Step "恢复 $([System.IO.Path]::GetFileName($dumpPath)) -> $Database"
    $client = Start-Process -FilePath (Join-Path $bin "mariadb.exe") `
        -ArgumentList @("--defaults-file=$applyDefaults", $Database) `
        -RedirectStandardInput $dumpPath -NoNewWindow -Wait -PassThru
    if ($client.ExitCode -ne 0) { throw "恢复失败，退出码 $($client.ExitCode)" }

    $after = Invoke-Client $bin $applyDefaults @(
        "--skip-column-names", "--batch", "-e",
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$Database';"
    )
    Write-Step "恢复完成：$Database 现有 $([int](@($after)[0].Trim())) 张表"
} finally {
    Remove-Item -Path $defaultsFile -Force -ErrorAction SilentlyContinue
    if ($adminDefaultsFile) { Remove-Item -Path $adminDefaultsFile -Force -ErrorAction SilentlyContinue }
}
