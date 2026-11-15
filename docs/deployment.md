# 部署说明（Ubuntu 24.04 直接部署，不使用容器）

> 本文件为 I01-T04 的部署说明。仓库提供 `deploy/shop.service`（systemd）与
> `deploy/nginx-shop.conf`（Nginx）两个模板，占位符见 §11；健康检查见 §8。
> 模板未在干净 Ubuntu 24.04 上执行过，I01-T04 因此只登记「AI 已交付」；
> 真机执行后按实测结果填写 `docs/acceptance/I01/I01-T04.md`。

## 1 目录结构

```
/srv/shop/
  releases/<release_id>/    每次发布的完整代码与 venv
  current -> releases/<release_id>
  shared/.env               环境变量（权限 600，属主 shop）
  shared/media/             上传媒体
  shared/backups/           数据库与媒体备份
  logs/                     Gunicorn 与业务日志
```

## 2 系统依赖

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-dev \
  default-libmysqlclient-dev build-essential pkg-config \
  mariadb-server redis-server nginx git
```

## 3 数据库与 Redis

```sql
CREATE DATABASE shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'shop'@'localhost' IDENTIFIED BY '<strong-password>';
GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'localhost';
FLUSH PRIVILEGES;
```

Redis 仅监听 127.0.0.1，使用独立 DB 索引（默认 `/1`），不保存订单事实数据。

## 4 应用安装

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin shop
sudo mkdir -p /srv/shop/releases /srv/shop/shared/media /srv/shop/shared/backups
```

```bash
cd /srv/shop/releases
git clone <repo> <release_id>
cd <release_id>
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env          # 填入生产配置，随后移动为 /srv/shop/shared/.env
cd frontend && npm ci && npm run build    # 产物 frontend/dist
```

## 5 迁移与静态文件

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
.venv/bin/python backend/manage.py migrate --noinput
.venv/bin/python backend/manage.py collectstatic --noinput
.venv/bin/python backend/manage.py check --deploy
```

## 6 systemd

仓库模板 `deploy/shop.service`（与下文一致，按 §11 替换路径与用户）：

```ini
[Unit]
Description=Shop Gunicorn
After=network.target mariadb.service redis-server.service

[Service]
User=shop
Group=shop
WorkingDirectory=/srv/shop/current/backend
EnvironmentFile=/srv/shop/shared/.env
ExecStart=/srv/shop/current/.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8001 --workers 3 --timeout 60 \
  --access-logfile /srv/shop/logs/access.log \
  --error-logfile /srv/shop/logs/error.log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp deploy/shop.service /etc/systemd/system/shop.service
sudo systemctl daemon-reload
sudo systemctl enable --now shop
```

## 7 Nginx

仓库模板 `deploy/nginx-shop.conf`（与下文一致，按 §11 替换域名与证书路径）：

```nginx
server {
    listen 80;
    server_name shop.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name shop.example.com;

    ssl_certificate     /etc/letsencrypt/live/shop.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shop.example.com/privkey.pem;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy same-origin always;
    client_max_body_size 6m;

    root /srv/shop/current/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8001;
    }

    location /media/ {
        alias /srv/shop/shared/media/;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
sudo cp deploy/nginx-shop.conf /etc/nginx/sites-available/shop.conf
sudo ln -sf /etc/nginx/sites-available/shop.conf /etc/nginx/sites-enabled/shop.conf
sudo nginx -t && sudo systemctl reload nginx
```

## 8 健康检查

- `GET /health/live/` 只反映进程存活。
- `GET /health/ready/` 检查数据库与缓存，任一不可用返回 503。

```bash
curl -fsS https://shop.example.com/health/live/
curl -fsS https://shop.example.com/health/ready/
```

## 9 发布与回滚

发布：备份数据库 → 新目录安装 → `migrate --check` → migrate → collectstatic →
`check --deploy` → `scripts/release-manifest.ps1` 生成制品校验值 → 切换 `current` 软链 →
`systemctl restart shop` → 健康检查与冒烟。发布记录里必须同时登记校验清单文件名与其自身 SHA256。

回滚：数据库结构与旧版本兼容时，把 `current` 指回上一 release 并重启。
不兼容时必须停写并恢复已验证备份（`scripts/db-restore.ps1` 或 §10 的 Linux 等价命令），同时明确丢失的时间区间。

## 10 备份与恢复

仓库提供两组脚本，凭据从 `backend/.env`（或仓库根 `.env`）读取，不写在命令行上。

| 用途 | 脚本 | 产物 |
| --- | --- | --- |
| 备份 + 可选自校验恢复 | `scripts/db-backup.ps1` | `backups/<库>-<时间戳>.sql`、`.sql.sha256`、`.json`（字节数/表数/耗时/工具版本） |
| 恢复 | `scripts/db-restore.ps1` | 先校验 `.sha256`，目标库非空时自动做 `pre-restore-*.sql` 安全备份 |
| 发布制品校验值 | `scripts/release-manifest.ps1` | `docs/releases/<标签>-<时间戳>-SHA256SUMS.txt`（`sha256sum -c` 兼容） |

```powershell
# 备份并自校验：恢复到临时库比对表清单，通过后 DROP（需要建库权限，用 root）
pwsh -File scripts\db-backup.ps1 -Verify -AdminUser root -AdminPassword ***

# 恢复：校验值不符直接拒绝；目标库非空会先做安全备份
pwsh -File scripts\db-restore.ps1 -DumpFile backups\shop-20261115-175534.sql -Database shop -AdminUser root

# 发布制品校验值（前端 dist 13 个文件）
pwsh -File scripts\release-manifest.ps1 -Label frontend
```

Linux 生产机等价命令（脚本逻辑一致，模板未在真机执行）：

```bash
mariadb-dump --single-transaction --quick --routines --triggers \
  --default-character-set=utf8mb4 shop > /srv/shop/shared/backups/shop-$(date +%F-%H%M).sql
sha256sum /srv/shop/shared/backups/shop-$(date +%F-%H%M).sql > /srv/shop/shared/backups/shop-$(date +%F-%H%M).sql.sha256
tar czf /srv/shop/shared/backups/media-$(date +%F).tar.gz -C /srv/shop/shared media
```

恢复演练（季度）：取最新备份 → 恢复到 `shop_restore_check` → 比对 `information_schema.tables` →
`manage.py migrate --check` → 抽样查询 → 记录 RTO → DROP 临时库。目标 RPO ≤ 15 分钟、RTO ≤ 2 小时。

每天执行备份，保留 14 天并异地存储。备份文件含真实数据，`backups/` 已在 `.gitignore` 中排除；校验清单（`docs/releases/`）随代码入库。

## 11 模板占位符与自检

两个模板是示例配置，直接复制不会工作，必须替换下表内容。仓库根目录执行命令时按实际路径调整。

| 占位符 | 出现位置 | 替换为 |
| --- | --- | --- |
| `/srv/shop` | 两个模板 | 实际发布根目录 |
| `shop`（`User` / `Group`） | `deploy/shop.service` | 应用系统账号 |
| `shop.example.com` | `deploy/nginx-shop.conf` | 真实域名 |
| `/etc/letsencrypt/live/shop.example.com/` | `deploy/nginx-shop.conf` | 证书实际目录 |
| `127.0.0.1:8001` | 两个模板 | Gunicorn 监听地址与端口 |

自检顺序（任一步失败不要继续）：

```bash
sudo /srv/shop/current/.venv/bin/gunicorn --check-config config.wsgi:application
sudo systemctl daemon-reload && sudo systemctl restart shop
sudo systemctl status shop --no-pager
curl -fsS http://127.0.0.1:8001/health/live/
curl -fsS http://127.0.0.1:8001/health/ready/
sudo nginx -t
sudo journalctl -u shop -n 50 --no-pager
```

`/health/ready/` 返回 503 时先看 `checks`：`database=unavailable` 查 MariaDB 与凭据，`cache=unavailable` 查 Redis 与 `CACHE_URL`。认证与公开列表在 Redis 故障时会回源，不会整体 500（见 `docs/交接文档.md` §5.1）。
