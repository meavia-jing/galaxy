# I03-T04：把上线前已入库的正文按白名单净化一遍
#
# 模型 save() 只拦截之后的写入，历史行仍是原始 HTML，公开接口虽有读侧净化，
# 但库里留着 <script> 本身就不该长期存在，因此单独做一次数据迁移。
from django.db import migrations


def sanitize_existing_bodies(apps, schema_editor):
    from common.sanitizer import sanitize_html

    ContentPage = apps.get_model("cms", "ContentPage")
    for page in ContentPage.objects.exclude(body="").only("id", "body").iterator():
        cleaned = sanitize_html(page.body)
        if cleaned != page.body:
            # 用 update() 绕过模型 save()，避免与迁移时的历史模型定义纠缠。
            ContentPage.objects.filter(pk=page.pk).update(body=cleaned)


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sanitize_existing_bodies, migrations.RunPython.noop),
    ]
