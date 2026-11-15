#Requires -Version 7.0
<#
.SYNOPSIS
    冒烟层门禁：13 项固定检查，3 分钟内跑完，任一失败退出码为 1。

.DESCRIPTION
    对应 docs/testing/用例矩阵.md 中的 SMK-01 ~ SMK-13。
    检查四端口存活、健康探针、Swagger、演示账号登录、三个公开列表接口、
    一次地址写操作（写后即清理）、前端首页。

    用法（项目根目录）：
        pwsh -File scripts/smoke.ps1
        pwsh -File scripts/smoke.ps1 -ApiBase http://127.0.0.1:8000 -NoWeb

    退出码：0 全绿；1 存在失败项；2 脚本自身参数/环境错误。
#>
[CmdletBinding()]
param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$WebBase = "http://127.0.0.1:5173",
    [string]$Username = "demo",
    [string]$Password = "ShopDemo2026",
    [string]$ReportDir = "",
    [switch]$NoWeb
)

$ErrorActionPreference = "Stop"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    # 某些非交互终端不允许改编码，忽略即可
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $ReportDir) { $ReportDir = Join-Path $repoRoot "docs/testing/reports" }
$null = New-Item -ItemType Directory -Force -Path $ReportDir

$script:http = [System.Net.Http.HttpClient]::new()
$script:http.Timeout = [TimeSpan]::FromSeconds(10)

function Send-Request {
    param(
        [string]$Method = "GET",
        [string]$Url,
        [hashtable]$Headers = @{},
        $Body = $null
    )

    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::new($Method), $Url)
    foreach ($key in $Headers.Keys) {
        # 不用 TryAddWithoutValidation 之外的方式，避免 Host/自定义头被拒
        $null = $request.Headers.TryAddWithoutValidation($key, [string]$Headers[$key])
    }
    if ($null -ne $Body) {
        $json = if ($Body -is [string]) { $Body } else { $Body | ConvertTo-Json -Compress -Depth 8 }
        $request.Content = [System.Net.Http.StringContent]::new(
            $json, [System.Text.Encoding]::UTF8, "application/json")
    }

    try {
        $response = $script:http.SendAsync($request).GetAwaiter().GetResult()
        $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $parsed = $null
        if ($text) {
            try { $parsed = $text | ConvertFrom-Json } catch { $parsed = $null }
        }
        return [pscustomobject]@{
            Status = [int]$response.StatusCode
            Json   = $parsed
            Text   = $text
        }
    } catch {
        return [pscustomobject]@{ Status = 0; Json = $null; Text = $_.Exception.Message }
    } finally {
        $request.Dispose()
    }
}

function Test-Port {
    param([int]$Port, [int]$TimeoutMs = 1500)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return ($task.Wait($TimeoutMs) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

$script:results = [System.Collections.Generic.List[object]]::new()

function Add-Result {
    param(
        [string]$Id,
        [string]$Name,
        [bool]$Ok,
        [string]$Detail,
        [long]$ElapsedMs
    )
    $script:results.Add([pscustomobject]@{
        id         = $Id
        name       = $Name
        ok         = $Ok
        detail     = $Detail
        elapsed_ms = $ElapsedMs
    })
}

function Invoke-Check {
    param(
        [string]$Id,
        [string]$Name,
        [scriptblock]$Body
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $ok = $false
    $detail = ""
    try {
        $outcome = & $Body
        if ($outcome -is [hashtable] -or $outcome -is [pscustomobject]) {
            $ok = [bool]$outcome.ok
            $detail = [string]$outcome.detail
        } else {
            $ok = [bool]$outcome
            $detail = if ($ok) { "ok" } else { "断言未通过" }
        }
    } catch {
        $ok = $false
        $detail = "异常: $($_.Exception.Message)"
    }
    $sw.Stop()
    Add-Result -Id $Id -Name $Name -Ok $ok -Detail $detail -ElapsedMs $sw.ElapsedMilliseconds
    $mark = if ($ok) { "PASS" } else { "FAIL" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("[{0}] {1} {2} ({3} ms) {4}" -f $mark, $Id, $Name, $sw.ElapsedMilliseconds, $detail) -ForegroundColor $color
}

$startedAt = Get-Date
Write-Host "== 冒烟检查 ==" -ForegroundColor Cyan
Write-Host "API: $ApiBase   Web: $WebBase" -ForegroundColor DarkGray

# --- SMK-01 ~ SMK-04 端口 ---------------------------------------------------
Invoke-Check "SMK-01" "前端 5173 可访问" {
    $port = Test-Port 5173
    if (-not $port) { return @{ ok = $false; detail = "端口未监听" } }
    if ($NoWeb) { return @{ ok = $true; detail = "端口已监听（-NoWeb 跳过 HTTP）" } }
    $r = Send-Request -Url "$WebBase/"
    @{ ok = ($r.Status -eq 200); detail = "HTTP $($r.Status)" }
}

Invoke-Check "SMK-02" "后端 8000 端口监听" {
    $ok = Test-Port 8000
    @{ ok = $ok; detail = $(if ($ok) { "已监听" } else { "端口未监听" }) }
}

Invoke-Check "SMK-03" "MariaDB 3306 端口监听" {
    $ok = Test-Port 3306
    @{ ok = $ok; detail = $(if ($ok) { "已监听" } else { "端口未监听" }) }
}

Invoke-Check "SMK-04" "Redis 6379 端口监听" {
    $ok = Test-Port 6379
    @{ ok = $ok; detail = $(if ($ok) { "已监听" } else { "端口未监听" }) }
}

# --- SMK-05 ~ SMK-07 健康与文档 ---------------------------------------------
Invoke-Check "SMK-05" "GET /health/live/" {
    $r = Send-Request -Url "$ApiBase/health/live/"
    $status = $r.Json.data.status
    @{ ok = ($r.Status -eq 200 -and $status -eq "ok"); detail = "HTTP $($r.Status) status=$status" }
}

Invoke-Check "SMK-06" "GET /health/ready/ 数据库与缓存" {
    $r = Send-Request -Url "$ApiBase/health/ready/"
    $checks = $r.Json.data.checks
    $db = if ($checks) { $checks.database } else { "-" }
    $cache = if ($checks) { $checks.cache } else { "-" }
    $err = if ($r.Status -ne 200 -and $r.Json.error) { " error=$($r.Json.error.code)" } else { "" }
    @{
        ok     = ($r.Status -eq 200 -and $db -eq "ok" -and $cache -eq "ok")
        detail = "HTTP $($r.Status) database=$db cache=$cache$err"
    }
}

Invoke-Check "SMK-07" "GET /api/docs/ Swagger" {
    $r = Send-Request -Url "$ApiBase/api/docs/"
    @{ ok = ($r.Status -eq 200); detail = "HTTP $($r.Status)" }
}

# --- SMK-08 登录 ------------------------------------------------------------
$accessToken = $null
Invoke-Check "SMK-08" "演示账号登录并取得 access" {
    $r = Send-Request -Method POST -Url "$ApiBase/api/v1/auth/login/" -Body @{
        username = $Username
        password = $Password
    }
    $script:accessToken = $r.Json.data.access
    $ok = ($r.Status -eq 200 -and -not [string]::IsNullOrWhiteSpace($script:accessToken))
    @{ ok = $ok; detail = "HTTP $($r.Status) access=$(if($ok){'已获取'}else{'缺失'})" }
}

# --- SMK-09 ~ SMK-11 公开列表 ----------------------------------------------
Invoke-Check "SMK-09" "GET /api/v1/products/ 有商品" {
    $r = Send-Request -Url "$ApiBase/api/v1/products/"
    $total = if ($r.Json.data) { [int]$r.Json.data.total } else { 0 }
    $err = if ($r.Status -ne 200 -and $r.Json.error) { " error=$($r.Json.error.code)" } else { "" }
    @{ ok = ($r.Status -eq 200 -and $total -gt 0); detail = "HTTP $($r.Status) total=$total$err" }
}

Invoke-Check "SMK-10" "GET /api/v1/categories/ 非空" {
    $r = Send-Request -Url "$ApiBase/api/v1/categories/"
    $count = if ($null -ne $r.Json.data) { @($r.Json.data).Count } else { 0 }
    $err = if ($r.Status -ne 200 -and $r.Json.error) { " error=$($r.Json.error.code)" } else { "" }
    @{ ok = ($r.Status -eq 200 -and $count -gt 0); detail = "HTTP $($r.Status) 分类 $count 个$err" }
}

Invoke-Check "SMK-11" "GET /api/v1/banners/ 非空" {
    $r = Send-Request -Url "$ApiBase/api/v1/banners/"
    $count = if ($null -ne $r.Json.data) { @($r.Json.data).Count } else { 0 }
    $err = if ($r.Status -ne 200 -and $r.Json.error) { " error=$($r.Json.error.code)" } else { "" }
    @{ ok = ($r.Status -eq 200 -and $count -gt 0); detail = "HTTP $($r.Status) 横幅 $count 个$err" }
}

# --- SMK-12 地址写操作（写后清理，不残留数据） ------------------------------
Invoke-Check "SMK-12" "地址 新增→查询→删除" {
    if (-not $script:accessToken) {
        return @{ ok = $false; detail = "缺少 access，登录步骤未通过" }
    }
    $headers = @{ Authorization = "Bearer $($script:accessToken)" }
    $payload = @{
        recipient = "冒烟检查"
        phone     = "13800138000"
        province  = "北京市"
        city      = "北京市"
        district  = "朝阳区"
        detail    = "自动化冒烟临时地址"
    }

    $created = Send-Request -Method POST -Url "$ApiBase/api/v1/addresses/" -Headers $headers -Body $payload
    $newId = $created.Json.data.id
    if ($created.Status -ne 201 -or -not $newId) {
        $snippet = if ($created.Text.Length -gt 160) { $created.Text.Substring(0, 160) } else { $created.Text }
        return @{ ok = $false; detail = "新增失败 HTTP $($created.Status) $snippet" }
    }

    try {
        $listed = Send-Request -Url "$ApiBase/api/v1/addresses/" -Headers $headers
        $found = @($listed.Json.data | Where-Object { $_.id -eq $newId }).Count -gt 0
        if (-not $found) {
            return @{ ok = $false; detail = "新增后列表中找不到 id=$newId" }
        }
    } finally {
        $deleted = Send-Request -Method DELETE -Url "$ApiBase/api/v1/addresses/$newId/" -Headers $headers
    }

    @{ ok = ($deleted.Status -eq 204); detail = "创建 201 / 查询命中 / 删除 $($deleted.Status)" }
}

# --- SMK-13 前端首页 --------------------------------------------------------
if (-not $NoWeb) {
    Invoke-Check "SMK-13" "前端首页渲染标记文案" {
        $r = Send-Request -Url "$WebBase/"
        $hit = $r.Text -match "云集商城"
        @{ ok = ($r.Status -eq 200 -and $hit); detail = "HTTP $($r.Status) 文案匹配=$hit" }
    }
}

# --- 汇总与报告 -------------------------------------------------------------
$script:http.Dispose()
$finishedAt = Get-Date
$total = $script:results.Count
$passed = @($script:results | Where-Object { $_.ok }).Count
$failed = $total - $passed
$suffix = if ($NoWeb) { "api-only" } else { "full" }
$reportPath = Join-Path $ReportDir ("smoke-{0}-{1}.json" -f $finishedAt.ToString("yyyyMMdd-HHmmss"), $suffix)

$report = [pscustomobject]@{
    generated_at = $finishedAt.ToString("o")
    duration_ms  = [long]($finishedAt - $startedAt).TotalMilliseconds
    api_base     = $ApiBase
    web_base     = $WebBase
    summary      = [pscustomobject]@{ total = $total; passed = $passed; failed = $failed; ok = ($failed -eq 0) }
    checks       = $script:results
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding utf8

Write-Host ""
$verdict = if ($failed -eq 0) { "全绿" } else { "存在失败" }
$color = if ($failed -eq 0) { "Green" } else { "Red" }
Write-Host ("冒烟 {0}/{1} 通过（{2}），用时 {3:N1}s" -f $passed, $total, $verdict, ($finishedAt - $startedAt).TotalSeconds) -ForegroundColor $color
Write-Host "报告：$reportPath" -ForegroundColor DarkGray

if ($failed -gt 0) {
    Write-Host "失败项：" -ForegroundColor Red
    $script:results | Where-Object { -not $_.ok } | ForEach-Object {
        Write-Host ("  - {0} {1}: {2}" -f $_.id, $_.name, $_.detail) -ForegroundColor Red
    }
    exit 1
}
exit 0
