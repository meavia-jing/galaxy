"""Seed demo data (no real personal information).

Idempotent: safe to run repeatedly. Creates a superuser, an operator, a normal
demo user, categories, products with SKUs, banners and a help page, and
generates local placeholder images so no network access is required.
"""
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.catalog.models import Category, Product, ProductImage, SKU
from apps.cms.models import Banner, ContentPage, PublishStatus

User = get_user_model()

PRODUCTS = [
    {
        "slug": "anc-headphones-pro",
        "title": "无线降噪耳机 Pro",
        "subtitle": "40 小时续航 | 混合主动降噪",
        "category": "digital",
        "featured": True,
        "colors": ((32, 44, 74), (86, 130, 204)),
        "skus": [
            ("ANC-PRO-BK", {"颜色": "曜石黑"}, "1299.00", 86),
            ("ANC-PRO-WH", {"颜色": "云母白"}, "1349.00", 42),
        ],
        "description": "双馈混合主动降噪，40 小时超长续航，支持 LDAC 与多点连接。",
    },
    {
        "slug": "mech-keyboard-k87",
        "title": "机械键盘 K87",
        "subtitle": "87 键 | 热插拔 | 三模连接",
        "category": "digital",
        "featured": True,
        "colors": ((48, 38, 30), (170, 120, 78)),
        "skus": [
            ("KB-K87-RED", {"轴体": "红轴"}, "599.00", 120),
            ("KB-K87-BROWN", {"轴体": "茶轴"}, "629.00", 75),
        ],
        "description": "Gasket 结构、全键热插拔、蓝牙/2.4G/有线三模，PBT 键帽。",
    },
    {
        "slug": "portable-monitor-156",
        "title": "便携显示器 15.6 英寸",
        "subtitle": "1080P IPS | Type-C 一线直连",
        "category": "digital",
        "featured": False,
        "colors": ((24, 46, 46), (70, 160, 150)),
        "skus": [
            ("MON-156-STD", {"版本": "标准版"}, "1599.00", 33),
        ],
        "description": "100% sRGB 色域，仅 780g，支持一线连接与手机镜像。",
    },
    {
        "slug": "nordic-bedside-lamp",
        "title": "北欧原木床头灯",
        "subtitle": "实木灯座 | 无极调光",
        "category": "home",
        "featured": True,
        "colors": ((74, 60, 40), (200, 170, 120)),
        "skus": [
            ("LAMP-OK-S", {"尺寸": "小号"}, "299.00", 60),
            ("LAMP-OK-L", {"尺寸": "大号"}, "399.00", 25),
        ],
        "description": "白蜡木灯座搭配亚麻灯罩，暖光无极调光，营造柔和氛围。",
    },
    {
        "slug": "linen-cushion-set",
        "title": "棉麻沙发抱枕组合",
        "subtitle": "一对装 | 可拆洗",
        "category": "home",
        "featured": False,
        "colors": ((70, 62, 58), (188, 176, 164)),
        "skus": [
            ("CUSHION-GY", {"颜色": "雾灰"}, "129.00", 200),
            ("CUSHION-BE", {"颜色": "米杏"}, "139.00", 150),
        ],
        "description": "精梳棉麻面料，隐形拉链可拆洗，支持机洗。",
    },
    {
        "slug": "pour-over-coffee-set",
        "title": "陶瓷手冲咖啡套装",
        "subtitle": "滤杯 + 分享壶 + 滤纸",
        "category": "home",
        "featured": True,
        "colors": ((36, 52, 44), (120, 170, 140)),
        "skus": [
            ("COFFEE-SET-01", {"组合": "标准套装"}, "399.00", 48),
        ],
        "description": "高温烧制陶瓷滤杯，配耐热玻璃分享壶，附赠 100 张滤纸。",
    },
    {
        "slug": "trek-backpack-35l",
        "title": "轻量登山背包 35L",
        "subtitle": "背负系统 | 防泼水",
        "category": "outdoor",
        "featured": True,
        "colors": ((30, 44, 34), (96, 150, 96)),
        "skus": [
            ("BP-35-BK", {"颜色": "深林绿"}, "499.00", 70),
            ("BP-35-GR", {"颜色": "岩灰"}, "499.00", 54),
        ],
        "description": "35L 容量，透气背负系统，防泼水面料，附雨罩。",
    },
    {
        "slug": "folding-camp-chair",
        "title": "折叠露营椅",
        "subtitle": "铝合金支架 | 承重 120kg",
        "category": "outdoor",
        "featured": False,
        "colors": ((56, 40, 34), (180, 120, 90)),
        "skus": [
            ("CHAIR-CAMP-01", {"颜色": "沙棕"}, "239.00", 95),
        ],
        "description": "一秒展开，收纳仅 38cm，铝合金骨架轻便耐用。",
    },
]

CATEGORIES = [
    ("数码影音", "digital", 10),
    ("家居生活", "home", 20),
    ("户外运动", "outdoor", 30),
]

BANNERS = [
    ("新季数码好物 · 限时特惠", "banner-digital", "/products?category=digital", 10),
    ("把自然带回家 · 家居生活节", "banner-home", "/products?category=home", 20),
    ("出发去野 · 户外装备清单", "banner-outdoor", "/products?category=outdoor", 30),
]


def _gradient_image(path: Path, size, top, bottom, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    image = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    font_size = max(int(height * 0.22), 18)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    text = label[:2]
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) / 2
    y = (height - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    image.save(path, "PNG", optimize=True)


class Command(BaseCommand):
    help = "Create demo users, catalog, CMS content and placeholder images."

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        self._users()
        categories = self._categories()
        self._products(categories, media_root)
        self._cms(media_root)
        self.stdout.write(self.style.SUCCESS("演示数据已就绪"))

    def _users(self):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin", password="ShopAdmin2026", nickname="系统管理员"
            )
            self.stdout.write("创建管理员 admin / ShopAdmin2026")
        operator, created = User.objects.get_or_create(
            username="operator",
            defaults={"nickname": "运营小张", "role": User.Role.OPERATOR, "is_staff": True},
        )
        if created:
            operator.set_password("ShopOperator2026")
            operator.save()
            self.stdout.write("创建运营 operator / ShopOperator2026")
        if not User.objects.filter(username="demo").exists():
            User.objects.create_user(
                username="demo", password="ShopDemo2026", nickname="演示用户"
            )
            self.stdout.write("创建普通用户 demo / ShopDemo2026")

    def _categories(self):
        result = {}
        for name, slug, order in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "sort_order": order, "is_active": True},
            )
            result[slug] = category
        return result

    def _products(self, categories, media_root: Path):
        for index, item in enumerate(PRODUCTS, start=1):
            product, _ = Product.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "category": categories[item["category"]],
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "description": item["description"],
                    "status": Product.Status.ACTIVE,
                    "is_featured": item["featured"],
                },
            )
            image_name = f"demo/product-{index}.png"
            _gradient_image(
                media_root / image_name,
                (900, 600),
                item["colors"][0],
                item["colors"][1],
                item["title"],
            )
            ProductImage.objects.update_or_create(
                product=product,
                path=f"/media/{image_name}",
                defaults={"alt_text": item["title"], "sort_order": 0},
            )
            for code, attrs, price, stock in item["skus"]:
                SKU.objects.update_or_create(
                    sku_code=code,
                    defaults={
                        "product": product,
                        "attributes": attrs,
                        "price": Decimal(price),
                        "stock_total": stock,
                        "is_active": True,
                    },
                )
        self.stdout.write(f"商品 {len(PRODUCTS)} 个已就绪")

    def _cms(self, media_root: Path):
        for index, (title, name, target, order) in enumerate(BANNERS, start=1):
            image_name = f"demo/{name}.png"
            _gradient_image(
                media_root / image_name,
                (1600, 520),
                (18, 24, 40),
                (60, 96, 160),
                title,
            )
            Banner.objects.update_or_create(
                title=title,
                defaults={
                    "image_path": f"/media/{image_name}",
                    "target_url": target,
                    "sort_order": order,
                    "is_active": True,
                },
            )
        ContentPage.objects.update_or_create(
            slug="help",
            defaults={
                "title": "帮助中心",
                "body": "本商城为演示站点，支付能力为模拟支付，不发生任何真实资金交易。",
                "status": PublishStatus.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        ContentPage.objects.update_or_create(
            slug="about",
            defaults={
                "title": "关于我们",
                "body": "在线商城演示项目，基于 Vue 3 与 Django 5.2 构建。",
                "status": PublishStatus.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        self.stdout.write("CMS 内容已就绪")
