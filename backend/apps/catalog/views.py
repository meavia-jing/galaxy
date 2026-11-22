"""Public catalog endpoints: categories, product list, product detail."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.cache import cache_delete, cached
from common.exceptions import BusinessError

from . import selectors
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer

CATEGORY_CACHE_KEY = "shop:dev:v1:catalog:categories"
CATEGORY_CACHE_TTL = 60


def invalidate_catalog_cache() -> None:
    """Called after any product/category write; short TTL is the safety net."""
    cache_delete(CATEGORY_CACHE_KEY)


class CategoryListView(APIView):
    permission_classes = [AllowAny]
    # 公开端点显式清空认证类，否则 OpenAPI 会标成需要 Bearer（误导调用方）。
    authentication_classes: list = []

    @extend_schema(responses=CategorySerializer(many=True), summary="启用中的分类")
    def get(self, request):
        data = cached(
            CATEGORY_CACHE_KEY,
            CATEGORY_CACHE_TTL,
            lambda: CategorySerializer(selectors.active_categories(), many=True).data,
        )
        return Response(data)


class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = ProductListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("category", str, description="分类 slug"),
            OpenApiParameter("keyword", str, description="标题/副标题关键词"),
            OpenApiParameter(
                "sort",
                str,
                enum=sorted(selectors.SORT_WHITELIST),
                description="排序白名单，非白名单值返回 400 INVALID_SORT",
            ),
        ],
        summary="商品列表（分页上限 100）",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

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
    authentication_classes: list = []

    @extend_schema(responses=ProductDetailSerializer, summary="商品详情")
    def get(self, request, pk: int):
        product = selectors.product_detail(pk)
        if product is None:
            raise BusinessError("NOT_FOUND", "商品不存在或已下架", status.HTTP_404_NOT_FOUND)
        return Response(ProductDetailSerializer(product).data)
