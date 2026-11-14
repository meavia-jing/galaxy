# 启动本地开发环境（Windows 11）
# 用法：pwsh -File scripts/start-dev.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    Write-Host '未找到 .venv，请先执行：python -m venv .venv'
    exit 1
}

# Redis（cygwin 版必须以其目录为工作目录，否则路径解析失败）
if (-not (Get-Process redis-server -ErrorAction SilentlyContinue)) {
    Write-Host '启动 Redis ...'
    Start-Process -FilePath 'D:\redis\redis-server.exe' -ArgumentList 'redis.conf' `
        -WorkingDirectory 'D:\redis' -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

if (-not (Get-Service MariaDB -ErrorAction SilentlyContinue | Where-Object Status -eq 'Running')) {
    Write-Host '启动 MariaDB 服务 ...'
    Start-Service MariaDB
}

Write-Host '启动 Django (127.0.0.1:8000) ...'
Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList 'manage.py', 'runserver', '127.0.0.1:8000' `
    -WorkingDirectory "$root\backend"

Write-Host '启动 Vite (127.0.0.1:5173) ...'
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' -WorkingDirectory "$root\frontend"

Write-Host ''
Write-Host '前台：http://127.0.0.1:5173'
Write-Host '后台：http://127.0.0.1:8000/admin/'
Write-Host 'API 文档：http://127.0.0.1:8000/api/docs/'
