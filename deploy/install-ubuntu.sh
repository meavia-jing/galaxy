#!/usr/bin/env bash
# I01-T04 幂等安装脚本：在干净 Ubuntu 24.04 上完成「源码 → HTTPS 可访问」。
#
#   用法（root）：
#     SRC_DIR=/mnt/d/myProject DOMAIN=shop.local bash deploy/install-ubuntu.sh
#
# 设计取舍：
#   * 前端默认复制已有的 frontend/dist（「从发布制品安装」），加 BUILD_FRONTEND=1 可在服务器上重建。
#   * 证书用自签，仅用于本机验证；生产按 §7 换 Let's Encrypt。
#   * 重复执行不会重置数据库密码，只在 .env 不存在时生成。
set -euo pipefail

APP=shop
SRC_DIR=${SRC_DIR:?需要 SRC_DIR 指向仓库根}
DOMAIN=${DOMAIN:-shop.local}
ROOT_DIR=/srv/$APP
RELEASE_ID=${RELEASE_ID:-$(date +%Y%m%d%H%M%S)}
RELEASE_DIR=$ROOT_DIR/releases/$RELEASE_ID
CERT_DIR=/etc/ssl/$APP
BUILD_FRONTEND=${BUILD_FRONTEND:-0}

DB_NAME=$APP
DB_USER=$APP
REDIS_DB=1

log() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 执行（wsl -u root）"
[ -f "$SRC_DIR/backend/requirements.txt" ] || die "SRC_DIR 不像仓库根：$SRC_DIR"

log "1/9 系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3.12 python3.12-venv python3-dev \
  mariadb-server redis-server nginx git rsync curl openssl >/dev/null
echo "已安装：$(nginx -v 2>&1)、$(python3 --version)、mariadb $(mariadb --version | awk '{print $5}')"

log "2/9 运行用户与目录"
id -u $APP >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin $APP
mkdir -p "$ROOT_DIR/releases" "$ROOT_DIR/shared/media" "$ROOT_DIR/shared/backups" "$ROOT_DIR/logs" "$CERT_DIR"
chown -R $APP:$APP "$ROOT_DIR"

log "3/9 数据库与 Redis"
systemctl enable --now mariadb >/dev/null 2>&1
systemctl enable --now redis-server >/dev/null 2>&1

ENV_FILE=$ROOT_DIR/shared/.env
if [ -f "$ENV_FILE" ]; then
  DB_PASSWORD=$(grep -m1 '^DB_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
  echo "复用已有 .env 中的数据库密码"
else
  DB_PASSWORD=$(openssl rand -hex 16)
fi
DJANGO_SECRET=$(openssl rand -base64 48 | tr -d '\n')

mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
SQL
echo "数据库 $DB_NAME 与用户 $DB_USER 就绪"

log "4/9 发布目录：$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
rsync -a --delete \
  --exclude '.git' --exclude 'node_modules' --exclude '.venv' \
  --exclude '__pycache__' --exclude 'test-results' --exclude '.pytest_cache' \
  "$SRC_DIR"/ "$RELEASE_DIR"/
[ -f "$RELEASE_DIR/frontend/dist/index.html" ] || die "缺少 frontend/dist，请先构建或设 BUILD_FRONTEND=1"

log "5/9 Python 虚拟环境"
python3.12 -m venv "$RELEASE_DIR/.venv"
"$RELEASE_DIR/.venv/bin/pip" install -q --upgrade pip
"$RELEASE_DIR/.venv/bin/pip" install -q -r "$RELEASE_DIR/backend/requirements.txt"
"$RELEASE_DIR/.venv/bin/python" -c "import django, gunicorn; print('django', django.get_version())"

if [ "$BUILD_FRONTEND" = "1" ]; then
  log "5b 前端在服务器上重建"
  ( cd "$RELEASE_DIR/frontend" && npm ci --silent && npm run build --silent )
fi

log "6/9 环境文件"
cat > "$ENV_FILE" <<ENV
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=$DJANGO_SECRET
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=$DOMAIN,127.0.0.1,localhost
DJANGO_LOG_LEVEL=INFO

DB_ENGINE=mysql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306

CACHE_URL=redis://127.0.0.1:6379/$REDIS_DB

CORS_ALLOWED_ORIGINS=https://$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
SECURE_SSL_REDIRECT=true
ENV
chmod 600 "$ENV_FILE"
chown $APP:$APP "$ENV_FILE"

log "7/9 迁移、静态文件、部署检查"
set -a; . "$ENV_FILE"; set +a
cd "$RELEASE_DIR/backend"
"$RELEASE_DIR/.venv/bin/python" manage.py migrate --noinput | tail -3
"$RELEASE_DIR/.venv/bin/python" manage.py collectstatic --noinput | tail -2
"$RELEASE_DIR/.venv/bin/python" manage.py check --deploy || die "check --deploy 未通过"
cd - >/dev/null

ln -sfn "$RELEASE_DIR" "$ROOT_DIR/current"
chown -R $APP:$APP "$RELEASE_DIR"

log "8/9 systemd 与 Nginx"
sed -e "s|^User=.*|User=$APP|" -e "s|^Group=.*|Group=$APP|" \
  "$RELEASE_DIR/deploy/shop.service" > /etc/systemd/system/$APP.service
systemctl daemon-reload
systemctl enable $APP >/dev/null 2>&1
systemctl restart $APP
sleep 3
systemctl is-active --quiet $APP || { journalctl -u $APP -n 30 --no-pager; die "gunicorn 未启动"; }

if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$DOMAIN" >/dev/null 2>&1
fi
sed -e "s|shop\.example\.com|$DOMAIN|g" \
    -e "s|/etc/letsencrypt/live/$DOMAIN|$CERT_DIR|g" \
    "$RELEASE_DIR/deploy/nginx-shop.conf" > /etc/nginx/sites-available/$APP
ln -sfn /etc/nginx/sites-available/$APP /etc/nginx/sites-enabled/$APP
rm -f /etc/nginx/sites-enabled/default
nginx -t 2>&1 | tail -1
systemctl reload nginx

log "9/9 健康检查"
CURL="curl -sk --resolve $DOMAIN:443:127.0.0.1"
# nginx reload 是异步的：刚发完 reload 立刻请求可能仍打到旧配置（曾因此误报 301）。
for i in $(seq 1 15); do
  code=$($CURL -o /dev/null -w '%{http_code}' "https://$DOMAIN/health/live/")
  [ "$code" = "200" ] && break
  sleep 1
done
$CURL "https://$DOMAIN/health/live/" -o /tmp/live.json -w 'live  HTTP %{http_code}\n' || true
cat /tmp/live.json; echo
$CURL "https://$DOMAIN/health/ready/" -o /tmp/ready.json -w 'ready HTTP %{http_code}\n' || true
cat /tmp/ready.json; echo
[ "$code" = "200" ] || die "健康检查未通过（live 返回 $code）"

printf '\n\033[1;32m部署完成\033[0m\n'
echo "  release   : $RELEASE_ID"
echo "  current   : $(readlink -f $ROOT_DIR/current)"
echo "  HTTPS     : https://$DOMAIN/   （自签证书，curl 用 -k）"
echo "  验证脚本  : SRC_DIR 无关，直接 bash deploy/verify-deploy.sh $DOMAIN"
