# 部署说明（Ubuntu 24.04 直接部署，不使用容器）

> 本文件为 I01-T04 的部署说明。当前仓库已提供 Nginx / Gunicorn / systemd 模板与
> 健康检查，验收证据需在干净 Ubuntu 24.04 上按本文执行后填写
> `docs/acceptance/I01/I01-T04.md`。

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

`deploy/shop.service`：

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
sudo systemctl daemon-reload
sudo systemctl enable --now shop
```

## 7 Nginx

`deploy/nginx-shop.conf`：

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

## 8 健康检查

- `GET /health/live/` 只反映进程存活。
- `GET /health/ready/` 检查数据库与缓存，任一不可用返回 503。

```bash
curl -fsS https://shop.example.com/health/live/
curl -fsS https://shop.example.com/health/ready/
```

## 9 发布与回滚

发布：备份数据库 → 新目录安装 → `migrate --check` → migrate → collectstatic →
`check --deploy` → 切换 `current` 软链 → `systemctl restart shop` → 健康检查与冒烟。

回滚：数据库结构与旧版本兼容时，把 `current` 指回上一 release 并重启。
不兼容时必须停写并恢复已验证备份，同时明确丢失的时间区间。

## 10 备份

```bash
mariadb-dump --single-transaction shop | gzip > /srv/shop/shared/backups/shop-$(date +%F-%H%M).sql.gz
tar czf /srv/shop/shared/backups/media-$(date +%F).tar.gz -C /srv/shop/shared media
```

每天执行，保留 14 天，异地存储；目标 RPO ≤ 15 分钟、RTO ≤ 2 小时，须通过恢复演练验证。
