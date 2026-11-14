from rest_framework import serializers

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
