<#
.SYNOPSIS
  为发布制品生成 SHA256 清单（SHA256SUMS 格式），并输出清单自身的校验值。

.DESCRIPTION
  默认对 frontend/dist 全量文件逐个计算 SHA256，按相对路径排序输出，格式与
  `sha256sum -c` 兼容（GNU 工具可直接在发布机复核）。
  清单落到 docs/releases/，与代码同提交；清单自身的 SHA256 打印到控制台，
  供人抄进交接文档或发布记录。

.EXAMPLE
  pwsh -File scripts\release-manifest.ps1 -Label frontend
#>
[CmdletBinding()]
param(
    [string]$Path = "frontend\dist",
    [string]$Label = "frontend",
    [string]$OutDir = "docs\releases"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$target = if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $repoRoot $Path }

if (-not (Test-Path $target)) {
    throw "制品目录不存在：$target。前端先执行 npm run build。"
}

$files = Get-ChildItem -Path $target -Recurse -File | Sort-Object FullName
if ($files.Count -eq 0) { throw "制品目录为空：$target" }

$outRoot = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $repoRoot $OutDir }
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$manifestPath = Join-Path $outRoot "$Label-$stamp-SHA256SUMS.txt"
$lines = New-Object System.Collections.Generic.List[string]
$totalBytes = 0

foreach ($file in $files) {
    $hash = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash.ToLower()
    $relative = [System.IO.Path]::GetRelativePath($target, $file.FullName).Replace("\", "/")
    $lines.Add("$hash  $relative")
    $totalBytes += $file.Length
}

$lines | Set-Content -Path $manifestPath -Encoding ascii
$manifestHash = (Get-FileHash -Path $manifestPath -Algorithm SHA256).Hash.ToLower()

Write-Host "[MANIFEST] 制品：$target"
Write-Host ("[MANIFEST] 文件 {0} 个，合计 {1:N0} 字节" -f $files.Count, $totalBytes)
Write-Host "[MANIFEST] 清单：$manifestPath"
Write-Host "[MANIFEST] 清单 SHA256：$manifestHash"
Write-Host "[MANIFEST] 复核命令：cd $target; sha256sum -c $manifestPath"
