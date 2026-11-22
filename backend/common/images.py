"""图片上传统一校验：类型白名单、5 MB 上限、内容嗅探、尺寸与像素上限。

为什么不能只看扩展名：把 ``shell.php`` 改名成 ``a.png`` 后，扩展名与
``Content-Type`` 都可以被伪造，只有把文件真正解码一遍才能确认它是图片。
这里用 Pillow 解码（Pillow 已是项目依赖，seed_demo 生成占位图也用它），
解码失败的、扩展名与真实格式不符的、超尺寸的一律拒绝。

``ProductImage.path`` 只允许站内绝对路径或 http(s) 外链，
防止后台填进 ``javascript:`` 之类协议后，前台 ``<img :src>`` 变成注入点。
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_EDGE_PIXELS = 6000
MAX_TOTAL_PIXELS = 24_000_000

# 扩展名 → 允许的真实格式（jpg / jpeg 都对应 Pillow 的 JPEG）
FORMATS_BY_SUFFIX: dict[str, frozenset[str]] = {
    ".jpg": frozenset({"JPEG"}),
    ".jpeg": frozenset({"JPEG"}),
    ".png": frozenset({"PNG"}),
    ".webp": frozenset({"WEBP"}),
    ".gif": frozenset({"GIF"}),
}

ALLOWED_SUFFIX_LABEL = "JPG / JPEG / PNG / WebP / GIF"


def _suffix(name: str) -> str:
    lowered = (name or "").lower()
    return lowered[lowered.rfind("."):] if "." in lowered else ""


def _decode(file) -> Image.Image:
    """把文件完整解码一遍；任何异常都视为「不是有效图片」。"""
    file.seek(0)
    image = Image.open(file)
    # verify() 只校验结构（截断、伪造尾部），之后这个对象不可再用。
    image.verify()
    file.seek(0)
    return Image.open(file)


def validate_image_file(file) -> None:
    """Django 字段校验器：不通过时抛 ``ValidationError``（DRF 会转成字段错误）。"""
    size = getattr(file, "size", None)
    if size is None:
        return
    if size <= 0:
        raise ValidationError("图片不能是空文件")
    if size > MAX_IMAGE_BYTES:
        raise ValidationError("图片不能超过 5 MB")

    suffix = _suffix(getattr(file, "name", ""))
    if suffix not in FORMATS_BY_SUFFIX:
        raise ValidationError(f"只支持 {ALLOWED_SUFFIX_LABEL} 格式的图片")

    try:
        image = _decode(file)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        # 伪造扩展名的脚本/HTML、截断文件、解码炸弹都走这条分支。
        raise ValidationError("文件内容不是有效图片，已拒绝") from None
    finally:
        # 无论成败都把指针还给调用方，否则后续写盘会拿到空内容。
        try:
            file.seek(0)
        except (AttributeError, ValueError):  # pragma: no cover - 非常规文件对象
            pass

    if image.format not in FORMATS_BY_SUFFIX[suffix]:
        raise ValidationError("文件扩展名与实际图片格式不一致")

    width, height = image.size
    if width > MAX_EDGE_PIXELS or height > MAX_EDGE_PIXELS:
        raise ValidationError(f"图片单边不能超过 {MAX_EDGE_PIXELS} 像素")
    if width * height > MAX_TOTAL_PIXELS:
        raise ValidationError("图片总像素过大，疑似解压炸弹")


def validate_image_path(value: str) -> None:
    """图片地址只能是站内绝对路径或 http(s) 外链。"""
    if not value:
        return
    cleaned = value.strip()
    if cleaned.startswith("//"):
        raise ValidationError("图片地址不能是协议相对地址")
    if cleaned.startswith("/") or cleaned.startswith(("http://", "https://")):
        return
    raise ValidationError("图片地址需以 / 或 http(s):// 开头")
