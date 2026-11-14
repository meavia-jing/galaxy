"""Public catalog endpoints: categories, product list, product detail."""
from django.core.cache import cache
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import BusinessError

from . import selectors
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer

CATEGORY_CACHE_KEY = "shop:dev:v1:catalog:categories"
CATEGORY_CACHE_TTL = 60


def invalidate_catalog_cache() -> None:
    """Called after any product/category write; short TTL is the safety net."""
    cache.delete(CATEGORY_CACHE_KEY)


class CategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = cache.get(CATEGORY_CACHE_KEY)
        if data is None:
            data = CategorySerializer(selectors.active_categories(), many=True).data
            cache.set(CATEGORY_CACHE_KEY, data, CATEGORY_CACHE_TTL)
        return Response(data)


class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        params = self.request.query_params
        sort = params.get("sort", "newest")
        if sort not in selectors.SORT_WHITELIST:
            raise BusinessError(
                "INVALID_SORT", "排序参数不在允许范围内", status.HTTP_400_BAD_REQUEST
            )
        return selectors.product_list(
            category_slug=params.get("category", "").strip(),
            keyword=params.get("keyword", "").strip(),
            sort=sort,
        )


class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk: int):
        product = selectors.product_detail(pk)
        if product is None:
            raise BusinessError("NOT_FOUND", "商品不存在或已下架", status.HTTP_404_NOT_FOUND)
        return Response(ProductDetailSerializer(product).data)
