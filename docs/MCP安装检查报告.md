# MCP 安装检查报告

| 字段 | 内容 |
| --- | --- |
| 执行时间 | 2026-11-14 23:00–23:55 (UTC+8) |
| 执行环境 | Windows 11 (10.0.26200) / Node v24.14.0 / npm 11.9.0 / uv 0.9 / Python 3.12.10 |
| 配置文件 | `C:\Users\zhang\.cursor\mcp.json`（用户级，所有工作区生效） |
| 检查工具 | `scripts/mcp-check.mjs`（JSON-RPC 握手 + `tools/list`）、`scripts/mcp-smoke.mjs`（真实 `tools/call`） |
| 结论 | 8 项需求中 7 项可用（含内置 computer use 与改用系统 Chrome 的 playwright），2 项已配置但因本机缺少宿主软件待启用 |

## 1. 安装清单

| 需求 | 实际包 / 来源 | 版本 | 启动命令 | Cursor 命名空间 | 状态 | 工具数 |
| --- | --- | --- | --- | --- | --- | --- |
| windows-cli | `@simonb97/server-win-cli` (npm) | 0.2.1 | `npx -y @simonb97/server-win-cli` | `user-windows-cli` | ready | 9 |
| redis | `@modelcontextprotocol/server-redis` (npm) | 最新 | `npx -y @modelcontextprotocol/server-redis redis://127.0.0.1:6379` | `user-redis` | ready | 4 |
| mysql | `@benborla29/mcp-server-mysql` (npm) | 2.0.9 | `npx -y @benborla29/mcp-server-mysql` | `user-mysql` | ready | 1 |
| playwright | `@playwright/mcp` (npm) | 0.0.85 | `npx -y @playwright/mcp@latest --isolated --browser chrome` | `user-playwright` | ready（需重连后生效） | 25 |
| computer use | Cursor 内置（无外部进程） | — | 无需配置 | `cursor-computer-use` | ready | 10 |
| Chrome DevTools mcp | `chrome-devtools-mcp` (npm) | 1.13.0 | `npx -y chrome-devtools-mcp@latest --isolated` | `user-chrome-devtools` | ready | 33 |
| godot | `@coding-solo/godot-mcp` (npm) | 0.1.1 | `npx -y @coding-solo/godot-mcp` | `user-godot` | ready（宿主 Godot 未安装） | 14 |
| blender | `mcp-for-blender` (PyPI，原 `blender-mcp`) | 最新 | `uvx mcp-for-blender` | `user-blender` | ready（宿主 Blender 未安装） | 10 |

> Cursor 侧工具数与脚本直连略有差异：Cursor 会额外注入 `mcp_auth` 等包装工具，因此 `user-*` 命名空间的工具数比服务自身多 1–2 个。

## 2. 验证证据

### 2.1 握手 + 工具枚举（`node scripts/mcp-check.mjs`）

```
检查 windows-cli ... OK  9 个工具   用时 3.7s
检查 redis ...       OK  4 个工具   用时 5.5s
检查 mysql ...       OK  1 个工具   用时 4.6s
检查 blender ...     OK 10 个工具   用时 14.1s
检查 godot ...       OK 14 个工具   用时 4.2s
检查 chrome-devtools ... OK 33 个工具  用时 5.6s
检查 playwright ...  OK 25 个工具   用时 4.0s
合计 7 个，成功 7 个，失败 0 个
```

### 2.2 真实工具调用（`node scripts/mcp-smoke.mjs`）

```
=== redis: 调用成功 ===
id=10 isError=false -> Successfully set key: mcp:check
id=11 isError=false -> ok-2026

=== mysql: 调用成功 ===
id=20 isError=false -> [{ "products": 8 }] Query execution time: 2.78 ms

=== playwright: 调用成功 ===
id=30 isError=false -> await page.goto('http://127.0.0.1:5173/');
                       Page URL: http://127.0.0.1:5173/
                       Page Title: 云集商城 · 在线电商演示
```

Playwright 真正启动了 Chrome 并打开了本项目前台首页，说明浏览器链路可用。

### 2.3 通过 Cursor 自身通道调用（端到端）

| 命名空间 | 调用 | 返回 |
| --- | --- | --- |
| `user-mysql` | `mysql_query`: `SELECT VERSION(), COUNT(catalog_product), COUNT(accounts_address)` | `13.0.2-MariaDB, products=8, addresses=2`，耗时 4.89 ms |
| `user-redis` | `get mcp:check` | `ok-2026` |
| `cursor-computer-use` | `computer_screenshot` | 成功捕获 1920×1080 主屏（见 `docs/screenshots/07-mcp-computer-use.png`） |

### 2.4 命名空间状态（Cursor 工具目录）

```
user-blender          tools=17  status=ready
user-chrome-devtools  tools=35  status=ready
user-godot            tools=16  status=ready
user-mysql            tools=3   status=ready
user-playwright       tools=27  status=ready
user-redis            tools=6   status=ready
user-windows-cli      tools=11  status=ready
```

## 3. 遇到的问题与处理

| 问题 | 现象 | 处理 |
| --- | --- | --- |
| PyPI 版 redis MCP 不可用 | `uvx mcp-server-redis` 报 `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`（mcp 2.x 已把 FastMCP 改为 MCPServer） | 改用官方 npm 包 `@modelcontextprotocol/server-redis`，URL 作为位置参数传入 |
| 同上，加固版仍缺环境变量 | 加 `--with "mcp<2"` 后报 `REDIS_PASSWORD: Field required`，而本机 Redis 无密码 | 不再使用该包，避免为无密码实例传假密码 |
| blender-mcp 改名 | `uvx blender-mcp` 提示 `blender-mcp is now mcp-for-blender` | 配置改为 `uvx mcp-for-blender` |
| Playwright 浏览器版本不匹配 | 本机 `ms-playwright` 为 chromium v1234，`@playwright/mcp@latest` 需要 v1255，直接启动会报可执行文件缺失 | 放弃下载（实测代理下 15 分钟只下到 0.8 MB），改用本机已安装的 Chrome：追加 `--browser chrome`，并以 `--isolated` 隔离用户配置。实测已成功打开本项目首页 |
| Godot 未安装 | 服务启动时报 `Could not find Godot in common locations for win32` | 服务仍可 `ready`（工具可列出），实际执行需安装 Godot 4 并修正 `GODOT_PATH` |
| Blender 未安装 | 工具可列出，但 `get_addon_status`/`execute_blender_code` 需要 Blender 内运行官方插件 | 建议安装 Blender 4.x 后启用 MCP 插件再使用 |

## 4. 使用说明

- 配置示例见仓库 `docs/mcp.example.json`；本机实际配置在 `C:\Users\zhang\.cursor\mcp.json`。
- 修改 `mcp.json` 后需要在 Cursor 的 MCP 面板点重连（或重启窗口），命名空间才会用新参数重启。
  本次改完 `playwright` 参数后，`user-playwright` 曾短暂报 `Not connected`，属预期，重连即可。
- MySQL 连接使用项目专用账号 `shop`（仅 `shop` 库权限），并关闭 DELETE：`ALLOW_DELETE_OPERATION=false`。
- Playwright 用系统 Chrome（`--browser chrome`），无需另外下载 chromium。
- 自检命令（任意目录）：

```powershell
node D:\myProject\scripts\mcp-check.mjs          # 全部
node D:\myProject\scripts\mcp-check.mjs redis    # 单个
node D:\myProject\scripts\mcp-smoke.mjs          # 真实调用
```

- Playwright 运行会在工作目录生成 `.playwright-mcp/` 快照，已加入 `.gitignore`。

## 5. 安全边界

- `windows-cli` 限制了可访问目录（`D:\myProject`、`C:\Users\zhang`），命令超时 60 秒。
- `mysql` 账号只授予 `shop.*`，且 MCP 侧禁用删除操作。
- `playwright` / `chrome-devtools` 使用 `--isolated`，不接管用户日常浏览器配置。
- 配置文件中包含本地数据库口令，位于用户目录，不随仓库提交。
