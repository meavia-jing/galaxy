<#
.SYNOPSIS
  备份 MariaDB 数据库，产出 .sql / .sha256 / .json 三件套，可选自校验恢复。

.DESCRIPTION
  凭据从 backend/.env（或仓库根 .env）读取，不写在命令行上，避免出现在进程列表。
  备份默认带 --single-transaction，不锁表；--routines --triggers 保证存储过程与触发器不丢。

  -Verify 会把备份恢复到临时库（默认 shop_restorecheck_<时间戳>）后比较表清单，
  通过后立即 DROP 临时库。这是「空库备份可恢复」的可重复证据，而不是一次性手工结论。

.EXAMPLE
  pwsh -File scripts\db-backup.ps1 -Verify

.EXAMPLE
  pwsh -File scripts\db-backup.ps1 -Verify -AdminUser root -AdminPassword ***
#>
[CmdletBinding()]
param(
    [string]$Database = "shop",
    [string]$OutDir = "backups",
    [int]$Keep = 7,
    [switch]$Verify,
    [string]$MariaBin = "",
    [string]$AdminUser = "",
    [string]$AdminPassword = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Step([string]$Message) { Write-Host "[BACKUP] $Message" }

function Resolve-MariaBin {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:MARIA_BIN) { $candidates += $env:MARIA_BIN }
    if ($env:MARIA_HOME) { $candidates += (Join-Path $env:MARIA_HOME "bin") }
    $candidates += "D:\mariadb\bin"
    $candidates += "C:\Program Files\MariaDB 11.4\bin"

    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path (Join-Path $dir "mariadb-dump.exe"))) { return $dir }
    }
    $cmd = Get-Command mariadb-dump -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path -Parent $cmd.Source) }
    throw "找不到 mariadb-dump。请用 -MariaBin 指定，或设置 MARIA_BIN 环境变量。"
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

function Get-TableNames([string]$Bin, [string]$DefaultsFile, [string]$Db) {
    $sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='$Db' ORDER BY table_name;"
    $raw = & (Join-Path $Bin "mariadb.exe") "--defaults-file=$DefaultsFile" "--skip-column-names" "--batch" -e $sql
    if ($LASTEXITCODE -ne 0) { throw "读取 $Db 表清单失败（退出码 $LASTEXITCODE）" }
    return @($raw | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
}

$envFile = if (Test-Path (Join-Path $repoRoot "backend\.env")) {
    Join-Path $repoRoot "backend\.env"
} else {
    Join-Path $repoRoot ".env"
}
$envMap = Read-DotEnv $envFile
foreach ($key in @("DB_USER", "DB_PASSWORD")) {
    if (-not $envMap.ContainsKey($key) -or -not $envMap[$key]) {
        throw "未在 $envFile 中找到 $key，无法备份。"
    }
}
if (-not $envMap.ContainsKey("DB_HOST")) { $envMap["DB_HOST"] = "127.0.0.1" }
if (-not $envMap.ContainsKey("DB_PORT")) { $envMap["DB_PORT"] = "3306" }

$bin = Resolve-MariaBin -Explicit $MariaBin
$outRoot = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $repoRoot $OutDir }
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$sqlPath = Join-Path $outRoot "$Database-$stamp.sql"
$defaultsFile = New-ClientDefaultsFile $envMap

# -Verify 要 CREATE/DROP 临时库并跨库读取，shop 账号通常没有该权限。
# 显式传 -AdminUser 时才做自校验，避免用低权限账号跑出自欺欺人的失败。
$adminDefaultsFile = $null
if ($AdminUser) {
    $adminMap = @{
        DB_USER     = $AdminUser
        DB_PASSWORD = $AdminPassword
        DB_HOST     = $envMap["DB_HOST"]
        DB_PORT     = $envMap["DB_PORT"]
    }
    $adminDefaultsFile = New-ClientDefaultsFile $adminMap
} elseif ($Verify) {
    throw "-Verify 需要建库/删库权限，请同时传 -AdminUser/-AdminPassword（本地可用 root）。"
}

$started = Get-Date

try {
    Write-Step "备份 $Database -> $sqlPath"
    & (Join-Path $bin "mariadb-dump.exe") "--defaults-file=$defaultsFile" `
        "--single-transaction" "--quick" "--routines" "--triggers" `
        "--default-character-set=utf8mb4" "--result-file=$sqlPath" $Database
    if ($LASTEXITCODE -ne 0) { throw "mariadb-dump 失败，退出码 $LASTEXITCODE" }

    $info = Get-Item $sqlPath
    if ($info.Length -lt 1024) { throw "备份文件过小（$($info.Length) 字节），疑似空库或参数错误。" }

    $hash = (Get-FileHash -Path $sqlPath -Algorithm SHA256).Hash.ToLower()
    "$hash  $($info.Name)" | Set-Content -Path "$sqlPath.sha256" -Encoding ascii

    $tables = Get-TableNames -Bin $bin -DefaultsFile $defaultsFile -Db $Database
    $record = [ordered]@{
        database   = $Database
        file       = $info.Name
        bytes      = $info.Length
        sha256     = $hash
        tables     = $tables.Count
        started_at = $started.ToString("o")
        seconds    = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
        mariadb    = (& (Join-Path $bin "mariadb-dump.exe") --version)
        verify     = $null
    }

    Write-Step ("完成：{0:N0} 字节，{1} 张表，SHA256 {2}..." -f $info.Length, $tables.Count, $hash.Substring(0, 16))

    if ($Verify) {
        $tempDb = "shop_restorecheck_{0}" -f (Get-Date -Format "HHmmss")
        Write-Step "自校验：恢复到临时库 $tempDb"
        try {
            & (Join-Path $bin "mariadb.exe") "--defaults-file=$adminDefaultsFile" -e "CREATE DATABASE ``$tempDb`` CHARACTER SET utf8mb4" | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "创建临时库 $tempDb 失败" }

            $client = Start-Process -FilePath (Join-Path $bin "mariadb.exe") `
                -ArgumentList @("--defaults-file=$adminDefaultsFile", $tempDb) `
                -RedirectStandardInput $sqlPath -NoNewWindow -Wait -PassThru
            if ($client.ExitCode -ne 0) { throw "恢复失败，退出码 $($client.ExitCode)" }

            $restored = Get-TableNames -Bin $bin -DefaultsFile $adminDefaultsFile -Db $tempDb
            $missing = @($tables | Where-Object { $restored -notcontains $_ })
            $extra = @($restored | Where-Object { $tables -notcontains $_ })
            if ($missing.Count -gt 0 -or $extra.Count -gt 0) {
                throw "表清单不一致：缺 $($missing -join ',') 多 $($extra -join ',')"
            }

            $record.verify = [ordered]@{
                ok          = $true
                temp_db     = $tempDb
                tables      = $restored.Count
                checked_at  = (Get-Date).ToString("o")
            }
            Write-Step "自校验通过：$($restored.Count) 张表与源库一致"
        } finally {
            & (Join-Path $bin "mariadb.exe") "--defaults-file=$adminDefaultsFile" -e "DROP DATABASE IF EXISTS ``$tempDb``" | Out-Null
        }
    }

    $jsonPath = Join-Path $outRoot "$Database-$stamp.json"
    $record | ConvertTo-Json -Depth 4 | Set-Content -Path $jsonPath -Encoding utf8
    Write-Step "元数据：$jsonPath"

    $old = Get-ChildItem -Path $outRoot -Filter "$Database-*" -File |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip ($Keep * 3)
    if ($old) {
        $old | Remove-Item -Force
        Write-Step "清理超出保留份数的旧备份：$($old.Count) 个文件"
    }
} finally {
    Remove-Item -Path $defaultsFile -Force -ErrorAction SilentlyContinue
    if ($adminDefaultsFile) { Remove-Item -Path $adminDefaultsFile -Force -ErrorAction SilentlyContinue }
}
