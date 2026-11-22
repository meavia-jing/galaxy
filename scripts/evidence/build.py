"""生成作业证据 HTML：全部内容取自仓库真实文件与真实命令输出，不做改写。

用法：
    python scripts/evidence/build.py           # 生成 .evidence-html/*.html
    node scripts/evidence/shoot.mjs            # 截图到 docs/homework/

依赖：markdown（未随项目安装，用 pip install --target .evidence-deps markdown 装到临时目录即可）。
"""

from __future__ import annotations

import html
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 向上找到含 迭代计划文档.md 的仓库根，避免脚本移动后路径失效。
ROOT = Path(__file__).resolve().parent
while not (ROOT / "迭代计划文档.md").exists():
    if ROOT.parent == ROOT:
        raise SystemExit("未找到仓库根（迭代计划文档.md）")
    ROOT = ROOT.parent

# 依赖与中间 HTML 都放在仓库外：SMK-14 会扫描提交目录下的 .py，第三方库会误判超限。
DEPS = Path(os.environ.get("EVIDENCE_DEPS") or Path(tempfile.gettempdir()) / "galaxy-evidence-deps")
OUT = Path(os.environ.get("EVIDENCE_HTML") or Path(tempfile.gettempdir()) / "galaxy-evidence-html")
sys.path.insert(0, str(DEPS))

try:
    import markdown  # noqa: E402
except ImportError:
    raise SystemExit(
        "缺少 markdown 渲染库，请先执行（装到仓库外，避免被 SMK-14 扫描）：\n"
        "  python -m pip install --target "
        f'"{DEPS}" markdown'
    )

OUT.mkdir(parents=True, exist_ok=True)

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 26px 30px 40px; background: #f6f7f9;
  font-family: "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  color: #1f2328; font-size: 14px; line-height: 1.62;
}
.meta {
  background: #fff; border: 1px solid #d8dee4; border-left: 4px solid #2f6feb;
  border-radius: 6px; padding: 12px 16px; margin-bottom: 18px;
}
.meta .src { font-family: Consolas, "Cascadia Mono", monospace; font-size: 12.5px; color: #57606a; }
.meta .note { color: #57606a; font-size: 12.5px; margin-top: 4px; }
.doc {
  background: #fff; border: 1px solid #d8dee4; border-radius: 6px;
  padding: 20px 24px; margin-bottom: 18px;
}
.doc h1 { font-size: 19px; border-bottom: 2px solid #eaeef2; padding-bottom: 8px; }
.doc h2 { font-size: 16px; margin: 22px 0 8px; border-bottom: 1px solid #eaeef2; padding-bottom: 5px; }
.doc h3 { font-size: 14.5px; margin: 16px 0 6px; }
.doc table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 12.8px; }
.doc th, .doc td { border: 1px solid #d8dee4; padding: 5px 8px; text-align: left; vertical-align: top; }
.doc th { background: #f0f3f6; font-weight: 600; }
.doc tr:nth-child(even) td { background: #fafbfc; }
.doc blockquote { margin: 10px 0; padding: 8px 14px; background: #fff8e6;
  border-left: 3px solid #d4a72c; color: #4d3800; font-size: 13px; }
.doc code { background: #eff1f3; padding: 1px 5px; border-radius: 3px;
  font-family: Consolas, monospace; font-size: 12.5px; }
.doc pre { background: #eff1f3; padding: 10px 12px; border-radius: 5px; overflow-x: auto; }
.doc pre code { background: none; padding: 0; }
.doc ul, .doc ol { padding-left: 22px; }
.term { background: #0d1117; border-radius: 8px; margin: 0 0 18px;
  border: 1px solid #30363d; overflow: hidden; }
.term__bar { background: #161b22; padding: 8px 14px; color: #8b949e;
  font-size: 12px; font-family: Consolas, monospace; border-bottom: 1px solid #30363d; }
.term__body { padding: 14px 16px; color: #c9d1d9; font-family: Consolas, monospace;
  font-size: 12.7px; white-space: pre-wrap; line-height: 1.55; }
.term__body .cmd { color: #7ee787; }
.alert { background: #fff; border: 1px solid #d1242f55; border-left: 4px solid #d1242f;
  border-radius: 6px; padding: 16px 20px; margin-bottom: 18px; }
.alert h1 { margin: 0 0 6px; font-size: 20px; color: #b42318; }
.alert .sub { font-size: 13.5px; color: #57606a; }
"""


def md(text: str) -> str:
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def styled(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"
    )


def meta(src: str, note: str) -> str:
    return (
        f"<div class='meta'><div class='src'>来源文件：{html.escape(src)}</div>"
        f"<div class='note'>{html.escape(note)}</div></div>"
    )


def term(title: str, text: str) -> str:
    lines = []
    for ln in text.splitlines():
        if ln.startswith("PS> "):
            lines.append(f"<span class='cmd'>{html.escape(ln)}</span>")
        else:
            lines.append(html.escape(ln))
    return (
        f"<div class='term'><div class='term__bar'>{html.escape(title)}</div>"
        f"<div class='term__body'>{'<br>'.join(lines)}</div></div>"
    )


def section(path: str, title: str, start: int, end: int) -> str:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    chunk = "\n".join(lines[start - 1:end])
    return f"<div class='doc'><h1>{html.escape(title)}</h1>{md(chunk)}</div>"


def run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return (out.stdout or "").strip()


def git_snapshot() -> str:
    blocks = [
        (
            'PS> git tag -l "baseline-*" --format="%(refname:short)  %(objectname:short)  '
            '%(taggername)  %(taggerdate:iso)"',
            run([
                "git", "tag", "-l", "baseline-*", "--format="
                "%(refname:short)  %(objectname:short)  %(taggername)  %(taggerdate:iso)",
            ]),
        ),
        ("PS> git describe --tags", run(["git", "describe", "--tags"])),
        ("PS> git tag -l -n99 baseline-003", run(["git", "tag", "-l", "-n99", "baseline-003"])),
        (
            "PS> git ls-remote --tags origin | Select-String baseline",
            "\n".join(
                ln for ln in run(["git", "ls-remote", "--tags", "origin"]).splitlines()
                if "baseline" in ln
            ),
        ),
    ]
    parts = []
    for cmd, out in blocks:
        parts.append(cmd)
        parts.append(out)
        parts.append("")
    return "\n".join(parts)


def iter_table() -> str:
    """从迭代计划文档 §15 的台账实时统计各迭代任务状态，不写死数字。"""
    text = (ROOT / "迭代计划文档.md").read_text(encoding="utf-8")
    counts: dict[str, dict[str, int]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[1].startswith("I"):
            continue
        mark, task = cells[0], cells[1]
        it = task.split("-")[0]
        if it not in {"I01", "I02", "I03", "I04"}:
            continue
        slot = counts.setdefault(it, {"✅": 0, "🚧": 0, "⬜": 0})
        if mark in slot:
            slot[mark] += 1

    names = {
        "I01": "I01 基础框架与直接部署",
        "I02": "I02 注册登录与用户中心",
        "I03": "I03 商品展示与 CMS",
        "I04": "I04 购物车与订单创建",
    }
    rows = ["| 迭代 | 任务数 | 已交付 | 部分交付 | 未开始 | 是否闭合 |", "| --- | --- | --- | --- | --- | --- |"]
    total = {"✅": 0, "🚧": 0, "⬜": 0}
    for it, name in names.items():
        c = counts.get(it, {"✅": 0, "🚧": 0, "⬜": 0})
        for k in total:
            total[k] += c[k]
        closed = "**否**" if c["🚧"] or c["⬜"] else "是"
        rows.append(
            f"| {name} | 5 | {c['✅']} | {c['🚧']} | {c['⬜']} | {closed} |"
        )
    rows.append(
        f"| **合计** | **20** | **{total['✅']}** | **{total['🚧']}** | **{total['⬜']}** | **闭合 0 个** |"
    )
    return "\n".join(rows)


def main() -> None:
    # 1 迭代计划
    plan_lines = (ROOT / "迭代计划文档.md").read_text(encoding="utf-8").splitlines()
    body = meta("迭代计划文档.md", f"渲染自仓库真实文件（共 {len(plan_lines)} 行），未改写任何内容")
    body += section("迭代计划文档.md", "迭代计划文档.md　头部与基线声明", 1, 10)
    body += section("迭代计划文档.md", "§15 任务进度总表", 236, len(plan_lines))
    (OUT / "01-迭代计划.html").write_text(styled("迭代计划", body), encoding="utf-8")

    # 2 交接文档
    body = meta("docs/交接文档.md", "渲染自仓库真实文件（§1 概况 + §2 完成情况 + §3 进度汇总）")
    body += section("docs/交接文档.md", "docs/交接文档.md　§1 项目概况", 1, 21)
    body += section("docs/交接文档.md", "§2 完成情况总表", 22, 76)
    body += section("docs/交接文档.md", "§3 进度汇总", 77, 92)
    (OUT / "02-交接文档.html").write_text(styled("交接文档", body), encoding="utf-8")

    # 3 基线标签
    body = meta("git 命令实况", "以下命令在本仓库实际执行，输出为原始结果")
    body += term("PowerShell — 仓库根", git_snapshot())
    body += section("docs/基线管理.md", "docs/基线管理.md　§1 基线的定义与 §3 基线清单", 14, 40)
    (OUT / "03-基线标签.html").write_text(styled("基线标签", body), encoding="utf-8")

    # 4 完成度自评
    body = (
        "<div class='alert'><h1>作业完成度自评</h1>"
        "<div class='sub'>数据取自已提交文档与 git 实况，非估算</div></div>"
    )
    body += "<div class='doc'><h1>一、迭代闭合状态（决定作业成败的指标）</h1>"
    body += md(iter_table())
    body += md(
        "\n> 作业要求「两个以上完整迭代」= 至少 I01 与 I02 各自走完"
        "「任务全交付 → 门禁全绿 → 文档同步 → 打标签 → 人工验收」。\n"
        "> 只要「部分交付」或「未开始」不为 0，该迭代就不能闭合。\n"
    )
    body += "</div>"
    body += "<div class='doc'><h1>二、现有标签的性质</h1>"
    body += md(
        "| 标签 | 覆盖范围 | 性质 |\n"
        "| --- | --- | --- |\n"
        "| `baseline-001` | I01-T01/T02、I02-T02/T04、I03-T02/T03 等混合 | 跨迭代补丁基线 |\n"
        "| `baseline-002` | I01-T03/T04、I02-T01/T04、I03-T05 等混合 | 跨迭代补丁基线 |\n"
        "| `baseline-003` | 测试补齐 + 价格排序修复 + 备份校验 | 跨迭代补丁基线 |\n\n"
        "> 三者都横跨 I01–I03，无法回答「I01 在第几个标签闭合」。"
        "作业要求的形态是一迭代一标签。\n"
    )
    body += "</div>"
    (OUT / "04-完成度.html").write_text(styled("作业完成度自评", body), encoding="utf-8")

    print("built:", sorted(p.name for p in OUT.glob("*.html")))


if __name__ == "__main__":
    main()
