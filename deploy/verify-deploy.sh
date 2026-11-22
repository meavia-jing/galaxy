#!/usr/bin/env bash
# I01-T04 验收验证：逐条核对「HTTPS 可用、重启恢复、依赖故障就绪失败但存活正常」。
#
#   用法（root 或能操作 systemd 的用户）：
#     bash deploy/verify-deploy.sh [DOMAIN]
#
# 会短暂停掉 mariadb / redis 各一次，验证完自动拉起；请在验证机上执行。
set -uo pipefail

DOMAIN=${1:-shop.local}
BASE="https://$DOMAIN"
CURL=(curl -sk --resolve "$DOMAIN:443:127.0.0.1" -o /dev/null -w '%{http_code}')
PASS=0
FAIL=0

ok()   { printf '  \033[1;32mPASS\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  \033[1;31mFAIL\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
head2() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }

expect_code() { # expect_code <label> <expected> <path>
  local code
  code=$("${CURL[@]}" "$BASE$3")
  if [ "$code" = "$2" ]; then ok "$1 → $code"; else bad "$1 → 期望 $2，实际 $code"; fi
}

head2 "1 HTTPS 页面与 API"
expect_code "首页"                200 /
expect_code "存活探针 /health/live/"  200 /health/live/
expect_code "就绪探针 /health/ready/" 200 /health/ready/
expect_code "商品列表 API"         200 /api/v1/products/
expect_code "后台登录页"           200 /admin/login/

ADMIN_CSS=$(curl -sk --resolve "$DOMAIN:443:127.0.0.1" "$BASE/admin/login/" \
  | grep -o '/static/admin/css/[a-z]*\.css' | head -1)
if [ -n "$ADMIN_CSS" ]; then
  expect_code "后台静态资源 $ADMIN_CSS" 200 "$ADMIN_CSS"
else
  bad "后台页面未引用 static（collectstatic 或 /static/ 配置有问题）"
fi

head2 "2 systemd 托管"
if systemctl is-enabled --quiet shop; then ok "shop.service 已 enable（开机会自启）"; else bad "shop.service 未 enable"; fi
if systemctl is-active --quiet shop; then ok "shop.service 运行中"; else bad "shop.service 未运行"; fi
if systemctl is-active --quiet nginx; then ok "nginx 运行中"; else bad "nginx 未运行"; fi

head2 "3 重启恢复（模拟重启：restart shop + reload nginx）"
systemctl restart shop; systemctl reload nginx; sleep 4
expect_code "重启后首页"         200 /
expect_code "重启后就绪探针"     200 /health/ready/

head2 "4 数据库故障：就绪失败、存活正常、恢复后自愈"
systemctl stop mariadb; sleep 2
expect_code "DB 停 /health/live/"  200 /health/live/
expect_code "DB 停 /health/ready/" 503 /health/ready/
systemctl start mariadb
for _ in $(seq 1 20); do
  sleep 1
  [ "$("${CURL[@]}" "$BASE/health/ready/")" = "200" ] && break
done
expect_code "DB 恢复 /health/ready/" 200 /health/ready/

head2 "5 缓存故障：就绪失败、存活正常、恢复后自愈"
systemctl stop redis-server; sleep 2
expect_code "Redis 停 /health/live/"  200 /health/live/
expect_code "Redis 停 /health/ready/" 503 /health/ready/
systemctl start redis-server
for _ in $(seq 1 20); do
  sleep 1
  [ "$("${CURL[@]}" "$BASE/health/ready/")" = "200" ] && break
done
expect_code "Redis 恢复 /health/ready/" 200 /health/ready/

head2 "6 明文 HTTP 强制跳转 HTTPS"
REDIRECT=$(curl -s -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:80:127.0.0.1" "http://$DOMAIN/")
if [ "$REDIRECT" = "301" ]; then ok "http → https 301"; else bad "http 未跳转，实际 $REDIRECT"; fi

printf '\n结果：\033[1;32m%d 通过\033[0m，\033[1;31m%d 失败\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
