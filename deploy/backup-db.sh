#!/usr/bin/env bash
# I01-T05 数据库备份（Ubuntu）：产出 .sql + .sha256 + .json 三件套，可选自校验恢复。
#
#   用法：
#     bash deploy/backup-db.sh                  # 仅备份
#     bash deploy/backup-db.sh --verify         # 备份 + 恢复到临时库比表清单
#
# 凭据从 EnvironmentFile（默认 /srv/shop/shared/.env）读取，不出现在进程列表。
# --verify 需要建库/删库权限，用 root 执行；日常备份用 shop 账号即可。
set -euo pipefail

ENV_FILE=${ENV_FILE:-/srv/shop/shared/.env}
OUT_DIR=${OUT_DIR:-/srv/shop/shared/backups}
KEEP=${KEEP:-7}
VERIFY=0
[ "${1:-}" = "--verify" ] && VERIFY=1

log() { printf '[BACKUP] %s\n' "$*"; }
die() { printf '\033[1;31m[BACKUP] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "找不到环境文件 $ENV_FILE"
set -a; . "$ENV_FILE"; set +a
: "${DB_NAME:?缺少 DB_NAME}"
: "${DB_USER:?缺少 DB_USER}"
: "${DB_PASSWORD:?缺少 DB_PASSWORD}"
DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-3306}

mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
SQL_PATH=$OUT_DIR/$DB_NAME-$STAMP.sql
CNF=$(mktemp); trap 'rm -f "$CNF"' EXIT
printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\ndefault-character-set=utf8mb4\n' \
  "$DB_USER" "$DB_PASSWORD" "$DB_HOST" "$DB_PORT" > "$CNF"
chmod 600 "$CNF"

log "备份 $DB_NAME -> $SQL_PATH"
START=$(date +%s)
# --single-transaction 不锁表；--routines --triggers 保证存储过程与触发器不丢。
mariadb-dump --defaults-file="$CNF" --single-transaction --quick \
  --routines --triggers --default-character-set=utf8mb4 \
  --result-file="$SQL_PATH" "$DB_NAME"

BYTES=$(stat -c%s "$SQL_PATH")
[ "$BYTES" -ge 1024 ] || die "备份文件过小（$BYTES 字节），疑似空库或参数错误"

HASH=$(sha256sum "$SQL_PATH" | awk '{print $1}')
printf '%s  %s\n' "$HASH" "$(basename "$SQL_PATH")" > "$SQL_PATH.sha256"

TABLES=$(mariadb --defaults-file="$CNF" --skip-column-names --batch \
  -e "SELECT table_name FROM information_schema.tables WHERE table_schema='$DB_NAME' ORDER BY table_name;")
TABLE_COUNT=$(printf '%s\n' "$TABLES" | grep -c . || true)

log "完成：$BYTES 字节，$TABLE_COUNT 张表，SHA256 ${HASH:0:16}..."

VERIFY_JSON=null
if [ "$VERIFY" = "1" ]; then
  TEMP_DB="shop_restorecheck_$(date +%H%M%S)"
  log "自校验：恢复到临时库 $TEMP_DB"
  mariadb -e "CREATE DATABASE \`$TEMP_DB\` CHARACTER SET utf8mb4"
  trap 'mariadb -e "DROP DATABASE IF EXISTS \`'"$TEMP_DB"'\`" 2>/dev/null; rm -f "$CNF"' EXIT
  mariadb "$TEMP_DB" < "$SQL_PATH"
  RESTORED=$(mariadb --skip-column-names --batch \
    -e "SELECT table_name FROM information_schema.tables WHERE table_schema='$TEMP_DB' ORDER BY table_name;")
  RESTORED_COUNT=$(printf '%s\n' "$RESTORED" | grep -c . || true)
  [ "$TABLE_COUNT" = "$RESTORED_COUNT" ] \
    || die "表数量不一致：源 $TABLE_COUNT，恢复 $RESTORED_COUNT"
  MISSING=$(comm -23 <(printf '%s\n' "$TABLES" | sort) <(printf '%s\n' "$RESTORED" | sort))
  [ -z "$MISSING" ] || die "恢复后缺少表：$MISSING"
  mariadb -e "DROP DATABASE \`$TEMP_DB\`"
  trap 'rm -f "$CNF"' EXIT
  VERIFY_JSON="{\"ok\": true, \"temp_db\": \"$TEMP_DB\", \"tables\": $RESTORED_COUNT}"
  log "自校验通过：$RESTORED_COUNT 张表与源库一致"
fi

SECONDS_ELAPSED=$(( $(date +%s) - START ))
JSON_PATH=$OUT_DIR/$DB_NAME-$STAMP.json
cat > "$JSON_PATH" <<JSON
{
  "database": "$DB_NAME",
  "file": "$(basename "$SQL_PATH")",
  "bytes": $BYTES,
  "sha256": "$HASH",
  "tables": $TABLE_COUNT,
  "seconds": $SECONDS_ELAPSED,
  "mariadb": "$(mariadb-dump --version | head -1)",
  "verify": $VERIFY_JSON
}
JSON
log "元数据：$JSON_PATH"

# 每份备份 3 个文件；按份数保留。
EXCESS=$(( KEEP * 3 ))
ls -1t "$OUT_DIR"/"$DB_NAME"-* 2>/dev/null | tail -n +$(( EXCESS + 1 )) | while read -r f; do
  rm -f "$f"
done
log "保留最近 $KEEP 份"
