"""[INT-IMG-01~05][I03-T01] 商品图片与数据库的集成用例。

验证「后台上传一张图 → 地址自动写入 → 前台拿到可用的 cover_image」，
以及非法文件在写库前就被拦下（不会留下半条脏记录）。
"""
from __future__ import annotations

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import Category, Product, ProductImage

pytestmark = pytest.mark.django_db


def png_bytes(size: tuple[int, int] = (24, 24)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 80, 30)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def product() -> Product:
    category = Category.objects.create(name="测试分类", slug="test-cat")
    return Product.objects.create(
        category=category, title="测试商品", slug="test-product", status=Product.Status.ACTIVE
    )


@pytest.fixture
def storage_tmp(tmp_path, monkeypatch):
    """把图片落盘指到临时目录，避免测试在仓库里留下 media/。"""
    storage = FileSystemStorage(location=str(tmp_path))
    field = ProductImage._meta.get_field("image")
    monkeypatch.setattr(field, "storage", storage)
    return tmp_path


def test_upload_fills_path_and_writes_file(product, storage_tmp):
    """[INT-IMG-01] 只上传文件、不填地址时，save() 自动写入 /media/products/... 地址。"""
    image = ProductImage(
        product=product,
        image=SimpleUploadedFile("hero.png", png_bytes(), content_type="image/png"),
    )

    image.save()

    image.refresh_from_db()
    assert image.path.startswith("/media/products/hero")
    assert image.path.endswith(".png")
    stored = storage_tmp / image.image.name
    assert stored.exists() and stored.stat().st_size > 0


def test_cover_image_is_used_by_product(product, storage_tmp):
    """[INT-IMG-02] 首图即 cover_image，商品详情列表能拿到可用的 src。"""
    ProductImage.objects.create(
        product=product,
        image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"),
    )
    ProductImage.objects.create(
        product=product, path="/media/demo/second.png", sort_order=5
    )

    assert product.cover_image.path.startswith("/media/products/cover")
    assert product.images.count() == 2


def test_script_file_is_rejected_before_insert(product):
    """[INT-IMG-03] 伪装成 png 的脚本在 save() 抛错，库里不多出一条记录。"""
    with pytest.raises(ValidationError):
        ProductImage.objects.create(
            product=product,
            image=SimpleUploadedFile("evil.png", b"<?php echo 1; ?>", content_type="image/png"),
        )

    assert ProductImage.objects.count() == 0


def test_full_clean_rejects_row_without_path_or_image(product):
    """[INT-IMG-04] 既没有文件也没有地址时 full_clean 报错（后台表单会看到该提示）。"""
    row = ProductImage(product=product)

    with pytest.raises(ValidationError) as exc:
        row.full_clean()

    assert "path" in exc.value.message_dict


def test_path_only_row_still_works(product):
    """[INT-IMG-05] 沿用旧做法（只填地址）不受影响，兼容 seed_demo 的数据。"""
    image = ProductImage(product=product, path="/media/demo/product-1.png")
    image.save()

    image.refresh_from_db()
    assert image.path == "/media/demo/product-1.png"
    assert not image.image


def test_dangerous_path_is_rejected(product):
    """[INT-IMG-06] 地址填 javascript: 时 save() 拒绝，避免前台 img src 变注入点。"""
    with pytest.raises(ValidationError):
        ProductImage.objects.create(product=product, path="javascript:alert(1)")

    assert ProductImage.objects.count() == 0
