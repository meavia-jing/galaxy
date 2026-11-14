from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import BusinessError

from .models import Banner, ContentPage, PublishStatus
from .serializers import BannerSerializer, ContentPageSerializer

BANNER_CACHE_KEY = "shop:dev:v1:cms:banners"
CACHE_TTL = 60


def invalidate_cms_cache() -> None:
    cache.delete(BANNER_CACHE_KEY)


class BannerListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = cache.get(BANNER_CACHE_KEY)
        if data is None:
            queryset = Banner.objects.filter(is_active=True)
            data = BannerSerializer(queryset, many=True).data
            cache.set(BANNER_CACHE_KEY, data, CACHE_TTL)
        return Response(data)


class ContentPageDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        page = ContentPage.objects.filter(
            slug=slug, status=PublishStatus.PUBLISHED
        ).first()
        if page is None:
            raise BusinessError("NOT_FOUND", "页面不存在", status.HTTP_404_NOT_FOUND)
        return Response(ContentPageSerializer(page).data)
