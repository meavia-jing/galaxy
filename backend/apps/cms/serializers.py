from rest_framework import serializers

from common.sanitizer import sanitize_html

from .models import Banner, ContentPage


class BannerSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ["id", "title", "image_path", "target_url", "sort_order"]

    def get_id(self, obj) -> str:
        return str(obj.pk)


class ContentPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentPage
        fields = ["slug", "title", "body", "published_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 读侧再净一次：净化上线前入库的历史数据可能仍是原始 HTML。
        data["body"] = sanitize_html(data.get("body", ""))
        return data
