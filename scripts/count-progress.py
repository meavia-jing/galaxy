r"""从《迭代计划文档》§15 逐任务行统计进度，禁止手写估算。

用法（项目根目录）：
    ..\.venv\Scripts\python.exe scripts\count-progress.py
    ..\.venv\Scripts\python.exe scripts\count-progress.py --check

输出形如：
    [✅ 13] [🚧 5] [⬜ 27] — 完成度 28.9%（13/45），含部分交付 40.0%（18/45）

``--check`` 模式与文档中「进度：」行的数字比对，不一致时退出码 1，
用于提交前卡住手工计数漂移。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "迭代计划文档.md"

MARKS = ("✅", "🚧", "⬜")
TASK_ROW = re.compile(r"^\|\s*(✅|🚧|⬜)\s*\|\s*(I\d{2}-T\d{2})\s*\|")
ITER_NAMES = {
    "I01": "基础框架与直接部署",
    "I02": "注册登录与用户中心基础",
    "I03": "商品展示与 CMS",
    "I04": "购物车与订单创建",
    "I05": "模拟支付与订单履约",
    "I06": "优惠券",
    "I07": "站内通知",
    "I08": "用户评价",
    "I09": "客服对话",
    "I10": "全量验证与交付审核",
}


def collect() -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    text = PLAN.read_text(encoding="utf-8")
    per_iter: dict[str, dict[str, int]] = {}
    total = {mark: 0 for mark in MARKS}
    seen: set[str] = set()

    for line in text.splitlines():
        match = TASK_ROW.match(line)
        if not match:
            continue
        mark, task = match.groups()
        if task in seen:  # §14.3 台账与 §15 都出现任务号时只算一次
            continue
        seen.add(task)
        group = task.split("-")[0]
        slot = per_iter.setdefault(group, {m: 0 for m in MARKS})
        slot[mark] += 1
        total[mark] += 1

    return per_iter, total


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "0.0%"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="与文档进度行比对，不一致则退出码 1")
    args = parser.parse_args()

    per_iter, total = collect()
    count = sum(total.values())
    delivered = total["✅"]
    partial = total["🚧"]
    pending = total["⬜"]
    summary = (
        f"[✅ {delivered}] [🚧 {partial}] [⬜ {pending}] — "
        f"完成度 **{pct(delivered, count)}**（{delivered}/{count}），"
        f"含部分交付 {pct(delivered + partial, count)}（{delivered + partial}/{count}）"
    )

    print("迭代   ✅  🚧  ⬜  合计")
    for name in sorted(per_iter):
        c = per_iter[name]
        print(f"{name}   {c['✅']:2}  {c['🚧']:2}  {c['⬜']:2}  {sum(c.values()):3}")
    print(summary)

    if args.check:
        text = PLAN.read_text(encoding="utf-8")
        found = re.search(r"进度：`\[✅ (\d+)\] \[🚧 (\d+)\] \[⬜ (\d+)\]`", text)
        if not found:
            print("未在《迭代计划文档》找到「进度：`[✅ n] [🚧 n] [⬜ n]`」行", file=sys.stderr)
            return 1
        expected = (delivered, partial, pending)
        actual = tuple(int(v) for v in found.groups())
        if expected != actual:
            print(f"进度行与实际统计不一致：文档 {actual}，实际 {expected}", file=sys.stderr)
            return 1
        print("进度行与逐任务统计一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
