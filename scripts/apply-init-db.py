"""在 Windows 上没有 mariadb 客户端时，用 PyMySQL 执行 init-db.sql。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe scripts\\apply-init-db.py

密码可用环境变量 MYSQL_ROOT_PASSWORD 提供，默认 jwpei（与本地开发一致）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pymysql

SQL_FILE = Path(__file__).resolve().parent / "init-db.sql"


def statements(sql: str) -> list[str]:
    """按分号切分并去掉整行注释；本文件不含分号出现在字符串里的情况。"""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    body = "\n".join(lines)
    return [chunk.strip() for chunk in body.split(";") if chunk.strip()]


def main() -> int:
    if not SQL_FILE.exists():
        print(f"找不到 {SQL_FILE}", file=sys.stderr)
        return 2

    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("MYSQL_ROOT_USER", "root"),
        password=os.environ.get("MYSQL_ROOT_PASSWORD", "jwpei"),
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            for stmt in statements(SQL_FILE.read_text(encoding="utf-8")):
                cursor.execute(stmt)
                print(f"OK  {stmt.splitlines()[0][:70]}")
    finally:
        conn.close()
    print("init-db.sql 执行完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
