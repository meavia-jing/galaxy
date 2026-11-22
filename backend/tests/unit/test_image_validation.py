"""[UNIT-IMG-01~12][I03-T01] 图片上传校验的单元用例（不碰数据库）。

口径见 ``common/images.py``：扩展名白名单 + Pillow 真实解码 + 尺寸/像素上限，
扩展名与真实格式不一致、内容不是图片、超 5 MB 一律拒绝。
"""
from __future__ import annotations

import io
import os

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from common.images import (
    MAX_IMAGE_BYTES,
    MAX_EDGE_PIXELS,
    validate_image_file,
    validate_image_path,
)


def make_image(suffix: str = ".png", size: tuple[int, int] = (16, 16), fmt: str = "PNG"):
    """在内存里生成一张真图片，返回 SimpleUploadedFile。"""
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buffer, fmt)
    return SimpleUploadedFile(f"pic{suffix}", buffer.getvalue(), content_type="image/png")


def test_valid_png_passes():
    """[UNIT-IMG-01] 合法 PNG 通过，且校验后指针回到开头（后续写盘能拿到完整内容）。"""
    upload = make_image()
    validate_image_file(upload)
    assert upload.tell() == 0
    assert len(upload.read()) == upload.size


def test_valid_jpeg_passes():
    """[UNIT-IMG-02] 合法 JPEG 通过。"""
    validate_image_file(make_image(".jpg", fmt="JPEG"))


def test_oversized_file_is_rejected():
    """[UNIT-IMG-03] 超过 5 MB 直接拒绝（不等到解码阶段）。"""
    too_big = SimpleUploadedFile("big.png", os.urandom(MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValidationError) as exc:
        validate_image_file(too_big)
    assert "5 MB" in str(exc.value)


def test_empty_file_is_rejected():
    """[UNIT-IMG-04] 空文件拒绝。"""
    with pytest.raises(ValidationError):
        validate_image_file(SimpleUploadedFile("empty.png", b""))


def test_disallowed_suffix_is_rejected():
    """[UNIT-IMG-05] .php / .svg 等不在白名单内的扩展名拒绝。"""
    for name in ("shell.php", "logo.svg", "noext"):
        upload = SimpleUploadedFile(name, b"<html>not an image</html>")
        with pytest.raises(ValidationError) as exc:
            validate_image_file(upload)
        assert "格式" in str(exc.value)


def test_text_file_renamed_to_png_is_rejected():
    """[UNIT-IMG-06] 恶意文件改扩展名（PHP 马/HTML）在解码阶段被识破。"""
    upload = SimpleUploadedFile("evil.png", b"<?php system($_GET['c']); ?>")
    with pytest.raises(ValidationError) as exc:
        validate_image_file(upload)
    assert "不是有效图片" in str(exc.value)


def test_truncated_image_is_rejected():
    """[UNIT-IMG-07] 截断的图片（只留文件头）拒绝。"""
    valid = make_image()
    truncated = SimpleUploadedFile("cut.png", valid.read()[:40])
    with pytest.raises(ValidationError):
        validate_image_file(truncated)


def test_format_not_matching_suffix_is_rejected():
    """[UNIT-IMG-08] 真实 JPEG 改名成 .png 拒绝，防止双扩展名绕过。"""
    upload = make_image(".png", fmt="JPEG")
    with pytest.raises(ValidationError) as exc:
        validate_image_file(upload)
    assert "不一致" in str(exc.value)


def test_too_wide_image_is_rejected():
    """[UNIT-IMG-09] 单边超过 6000 像素拒绝。"""
    upload = make_image(size=(MAX_EDGE_PIXELS + 1, 8))
    with pytest.raises(ValidationError) as exc:
        validate_image_file(upload)
    assert "像素" in str(exc.value)


def test_huge_pixel_count_is_rejected():
    """[UNIT-IMG-10] 总像素超上限（解压炸弹口径）拒绝。"""
    upload = make_image(size=(5000, 5000))  # 2500 万 > 2400 万，单边仍合法
    with pytest.raises(ValidationError) as exc:
        validate_image_file(upload)
    assert "像素" in str(exc.value)


def test_image_path_rejects_dangerous_scheme():
    """[UNIT-IMG-11] 图片地址不允许 javascript: / data: / 协议相对地址。"""
    for value in ("javascript:alert(1)", "data:image/png;base64,AAAA", "//evil.example.com/a.png"):
        with pytest.raises(ValidationError):
            validate_image_path(value)


def test_image_path_accepts_site_and_http():
    """[UNIT-IMG-12] 站内绝对路径、http(s) 外链与空值放行。"""
    for value in ("/media/demo/a.png", "https://cdn.example.com/a.png", "http://a/b.png", ""):
        validate_image_path(value)
