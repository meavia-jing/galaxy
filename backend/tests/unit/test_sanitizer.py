"""[UNIT-SEC-01~08][I03-T04] 富文本白名单净化的单元用例（不碰数据库）。

口径见 ``common/sanitizer.py`` 模块文档：白名单外的标签去标签留文本，
危险标签连内容丢弃，属性与 URL 协议同样白名单。
"""
from __future__ import annotations

import pytest

from common.sanitizer import MAX_BODY_LENGTH, sanitize_html


def test_plain_text_is_escaped():
    """[UNIT-SEC-01] 纯文本里的裸尖括号必须转义，不能当成标签透传。"""
    assert sanitize_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_script_is_dropped_with_its_content():
    """[UNIT-SEC-02] <script> 连内容一起丢弃，不能把脚本源码当正文显示。"""
    raw = "<p>公告</p><script>alert('xss')</script>"
    assert sanitize_html(raw) == "<p>公告</p>"


def test_style_and_iframe_are_dropped():
    """[UNIT-SEC-03] style / iframe 同样整体丢弃。"""
    raw = "<style>p{color:red}</style><p>正文</p><iframe src='https://evil'></iframe>"
    assert sanitize_html(raw) == "<p>正文</p>"


def test_inline_event_handlers_are_removed():
    """[UNIT-SEC-04] onerror 等事件属性不在白名单内，必须消失。"""
    clean = sanitize_html('<img src="https://cdn/a.png" onerror="alert(1)">')
    assert "onerror" not in clean
    assert clean == '<img src="https://cdn/a.png">'


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "java\nscript:alert(1)",
        "jav&#x61;script:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "//evil.example.com/x",
        "vbscript:msgbox(1)",
    ],
)
def test_dangerous_href_is_dropped(href):
    """[UNIT-SEC-05] 非 http/https/mailto 的协议一律丢弃，链接保留为纯文本。"""
    clean = sanitize_html(f'<a href="{href}">点这里</a>')
    assert "href" not in clean
    assert clean == '<a rel="noopener noreferrer">点这里</a>'


def test_safe_links_keep_href_and_gain_rel():
    """[UNIT-SEC-06] 合法链接保留 href，并强制加 rel。"""
    clean = sanitize_html('<a href="https://example.com/a?b=1" title="说明">外链</a>')
    assert clean == (
        '<a href="https://example.com/a?b=1" title="说明" rel="noopener noreferrer">外链</a>'
    )
    relative = sanitize_html('<a href="/pages/about/">站内</a>')
    assert 'href="/pages/about/"' in relative


def test_unknown_tags_are_unwrapped_but_text_survives():
    """[UNIT-SEC-07] 白名单外（如 <font>、<marquee>）去标签留文本。"""
    assert sanitize_html("<marquee><font color=red>促销</font></marquee>") == "促销"


def test_output_is_always_balanced():
    """[UNIT-SEC-08] 未闭合的标签由净化器补齐，输出结构合法。"""
    assert sanitize_html("<p><strong>粗体") == "<p><strong>粗体</strong></p>"
    # 交叉嵌套按最近的同名标签闭合，不会产出 <b><i></b></i> 这种非法结构。
    assert sanitize_html("<b><i>x</b>") == "<b><i>x</i></b>"


def test_long_body_is_truncated():
    """[UNIT-SEC-09] 超长正文按上限截断，防止解析开销失控。"""
    raw = "字" * (MAX_BODY_LENGTH + 100)
    assert len(sanitize_html(raw)) <= MAX_BODY_LENGTH + 10


def test_empty_input():
    """[UNIT-SEC-10] None 与空串返回空串，调用方无需判空。"""
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""


def test_empty_attribute_value_is_dropped():
    """[UNIT-SEC-11] href 为空时直接丢弃该属性，不留 href="" 空壳。"""
    assert sanitize_html('<a href="">空链接</a>') == '<a rel="noopener noreferrer">空链接</a>'


def test_nested_dangerous_tag_keeps_dropping():
    """[UNIT-SEC-12] script 内再套 script 时按深度计数，防止提前结束丢弃状态。"""
    raw = "<script><script>alert(1)</script></script><p>保留</p>"
    assert sanitize_html(raw) == "<p>保留</p>"


def test_comments_declarations_and_pi_are_removed():
    """[UNIT-SEC-13] 注释、DOCTYPE、处理指令整体丢弃，不进输出。"""
    raw = "<!DOCTYPE html><!-- 隐藏说明 --><p>正文</p><?php echo 1; ?>"
    assert sanitize_html(raw) == "<p>正文</p>"
