"""富文本白名单净化：只保留允许的标签与属性，其余丢弃或去标签保留文本。

为什么不引入第三方库：``bleach`` 已停止维护，``nh3`` 需要额外二进制包，
而本项目的富文本只有 CMS 内容页正文一处，标准库 ``html.parser`` 足够，
也避免在离线部署机上多一个安装风险。

净化口径（写进 I03-T04 验收记录）：

* 白名单标签之外的标签：**去标签、保留文本**（排版降级但不丢内容）；
* ``script``/``style``/``iframe`` 等危险标签：**连内容一起丢弃**，否则脚本正文
  会以纯文本形式留在页面上；
* 属性同样白名单，``onerror`` 之类事件属性一律不保留；
* ``href``/``src`` 只放行 http/https/mailto（图片不含 mailto），
  并剔除 URL 内的空白与控制字符，防止 ``java\\nscript:`` 这类绕过；
* 协议相对地址（```//evil``）与 ``data:`` 一并拒绝。
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# 正文字数上限：超出部分截断，避免超长载荷拖慢解析。
MAX_BODY_LENGTH = 50_000

# 允许保留的排版标签，均为无语义风险的结构标签。
ALLOWED_TAGS = frozenset(
    {
        "p", "br", "hr", "span", "div",
        "strong", "b", "em", "i", "u", "s", "small", "sub", "sup",
        "ul", "ol", "li", "blockquote", "code", "pre",
        "h2", "h3", "h4", "h5", "h6",
        "a", "img",
        "table", "thead", "tbody", "tr", "th", "td",
    }
)

# 这些标签连内容一起丢弃。只去标签会把 <script> 里的代码当正文渲染出来。
DROP_WITH_CONTENT = frozenset(
    {
        "script", "style", "iframe", "frame", "frameset", "object", "embed",
        "applet", "noscript", "template", "svg", "math", "form", "input",
        "select", "option", "textarea", "button", "title", "head", "base", "link", "meta",
    }
)

ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "width", "height"}),
    "td": frozenset({"colspan", "rowspan"}),
    "th": frozenset({"colspan", "rowspan"}),
}

VOID_TAGS = frozenset({"br", "hr", "img"})

SAFE_SCHEMES: dict[str, frozenset[str]] = {
    "a": frozenset({"http", "https", "mailto"}),
    "img": frozenset({"http", "https"}),
}

URL_WHITESPACE = re.compile(r"[\x00-\x20\x7f]+")
SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")


def _safe_url(value: str, tag: str) -> str | None:
    """返回可安全输出的 URL；不安全时返回 None，调用方据此丢掉该属性。"""
    cleaned = URL_WHITESPACE.sub("", value.strip())
    if not cleaned:
        return None
    match = SCHEME.match(cleaned)
    if match is None:
        # 无协议：只接受站内绝对路径、锚点与查询串。
        if cleaned.startswith(("/", "#", "?")) and not cleaned.startswith("//"):
            return cleaned
        # 裸相对路径（如 images/a.png）也放行，但必须以字母数字开头。
        return cleaned if cleaned[0].isalnum() else None
    return cleaned if match.group(1).lower() in SAFE_SCHEMES[tag] else None


class _Sanitizer(HTMLParser):
    """单次遍历即可，输出始终是标签闭合的 HTML 片段。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._open: list[str] = []
        self._drop_tag = ""
        self._drop_depth = 0

    # ---- 标签 ----

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag == self._drop_tag:
                self._drop_depth += 1
            return
        if tag in DROP_WITH_CONTENT:
            self._drop_tag = tag
            self._drop_depth = 1
            return
        if tag not in ALLOWED_TAGS:
            return  # 白名单之外：去标签，文本由 handle_data 保留
        self._out.append(self._render_start(tag, attrs))
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag == self._drop_tag:
                self._drop_depth -= 1
                if self._drop_depth == 0:
                    self._drop_tag = ""
            return
        if tag in VOID_TAGS or tag not in ALLOWED_TAGS or tag not in self._open:
            return
        # 关到最近的同名标签，途中的未闭合子标签一并补齐，保持输出结构合法。
        while self._open:
            open_tag = self._open.pop()
            self._out.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    # ---- 文本与其他节点 ----

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        self._out.append(html.escape(data, quote=False))

    def handle_comment(self, data: str) -> None:  # noqa: D401 - 注释整体丢弃
        return

    def handle_decl(self, decl: str) -> None:
        return

    def handle_pi(self, data: str) -> None:
        return

    # ---- 输出 ----

    def _render_start(self, tag: str, attrs) -> str:
        allowed = ALLOWED_ATTRS.get(tag, frozenset())
        parts = [f"<{tag}"]
        seen: set[str] = set()
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or name in seen or value is None:
                continue
            if name in ("href", "src"):
                value = _safe_url(value, tag)
                if value is None:
                    continue
            seen.add(name)
            parts.append(f' {name}="{html.escape(value, quote=True)}"')
        if tag == "a":
            # 外链一律加 rel，避免 reverse tabnabbing。
            parts.append(' rel="noopener noreferrer"')
        return "".join(parts) + ">"

    def result(self) -> str:
        tail = "".join(f"</{tag}>" for tag in reversed(self._open))
        self._open.clear()
        return "".join(self._out) + tail


def sanitize_html(raw: str | None, *, max_length: int = MAX_BODY_LENGTH) -> str:
    """把任意 HTML 片段净化为白名单子集；``None`` / 空串返回空串。"""
    if not raw:
        return ""
    parser = _Sanitizer()
    parser.feed(raw[:max_length])
    parser.close()
    return parser.result()
