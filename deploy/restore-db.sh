#!/usr/bin/env bash
# I01-T05 数据库恢复（Ubuntu）：先校验 SHA256，再按需安全备份现有库。
#
#   用法：
#     bash deploy/restore-db.sh <备份文件.sql>            # 恢复到 .env 中的 DB_NAME
#     bash deploy/restore-db.sh <备份文件.sql> --into shop_drill   # 恢复到指定库（演练用）
#     bash deploy/restore-db.sh <备份文件.sql> --force    # 目标库非空时也直接覆盖
#
# 设计：默认拒绝覆盖非空库，除非加 --force 且已自动做过一次安全备份。
set -euo pipefail

SQL_FILE=${1:?用法: restore-db.sh <备份文件.sql> [--into DB] [--force]}
shift
ENV_FILE=${ENV_FILE:-/srv/shop/shared/.env}
TARGET_DB=""
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --into) TARGET_DB=${2:?}; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

log() { printf '[RESTORE] %s\n' "$*"; }
die() { printf '\033[1;31m[RESTORE] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$SQL_FILE" ] || die "备份文件不存在：$SQL_FILE"
[ -f "$ENV_FILE" ] || die "找不到环境文件 $ENV_FILE"
set -a; . "$ENV_FILE"; set +a
TARGET_DB=${TARGET_DB:-$DB_NAME}

# 校验值不符直接拒绝——恢复一个损坏的备份比不恢复更糟。
if [ -f "$SQL_FILE.sha256" ]; then
  EXPECTED=$(awk '{print $1}' "$SQL_FILE.sha256")
  ACTUAL=$(sha256sum "$SQL_FILE" | awk '{print $1}')
  [ "$EXPECTED" = "$ACTUAL" ] || die "SHA256 不匹配，拒绝恢复（期望 $EXPECTED，实际 $ACTUAL）"
  log "SHA256 校验通过"
else
  log "警告：没有 .sha256 文件，跳过完整性校验"
fi

EXISTING=$(mariadb --skip-column-names --batch \
  -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TARGET_DB';" 2>/dev/null || echo 0)
if [ "$EXISTING" != "0" ] && [ "$FORCE" = "1" ]; then
  SAFETY=/srv/shop/shared/backups/pre-restore-$(date +%Y%m%d-%H%M%S).sql
  mkdir -p "$(dirname "$SAFETY")"
  log "目标库非空（$EXISTING 张表），先做安全备份：$SAFETY"
  mariadb-dump --single-transaction --quick --routines --triggers \
    --result-file="$SAFETY" "$TARGET_DB"
  log "安全备份完成：$(stat -c%s "$SAFETY") 字节"
elif [ "$EXISTING" != "0" ] && [ "$FORCE" = "0" ]; then
  die "目标库 $TARGET_DB 已有 $EXISTING 张表；加 --force 覆盖，或用 --into 恢复到新库"
fi

mariadb -e "CREATE DATABASE IF NOT EXISTS \`$TARGET_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
log "恢复 $SQL_FILE -> $TARGET_DB"
mariadb "$TARGET_DB" < "$SQL_FILE"

COUNT=$(mariadb --skip-column-names --batch \
  -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TARGET_DB';")
log "恢复完成：$TARGET_DB 现有 $COUNT 张表"
