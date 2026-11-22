"""Cart endpoints — every row is scoped to the caller.

没有用完整 ModelViewSet：POST 要「同 SKU 合并」、PATCH 要库存校验，两者都走服务层，
DRF 的默认 create/update 会绕过这些规则。
"""
from decimal import Decimal
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.mixins import DestroyModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from .models import CartItem
from .serializers import (
    CartItemPatchSerializer,
    CartItemSerializer,
    CartItemWriteSerializer,
    CartSummarySerializer,
)
from .services import patch_item, put_item, remove_item


class CartItemViewSet(ListModelMixin, DestroyModelMixin, GenericViewSet):
    """GET/POST /cart-items/ 、PATCH/DELETE /cart-items/{id}/"""

    permission_classes = [IsAuthenticated]
    serializer_class = CartItemSerializer
    pagination_class = None
    # 仅用于 OpenAPI 推断模型；真实查询由 get_queryset 按当前用户过滤。
    queryset = CartItem.objects.none()

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).select_related("sku", "sku__product")

    @extend_schema(request=CartItemWriteSerializer, responses=CartItemSerializer,
                   summary="加入购物车：同 SKU 合并为一行，数量为设定值")
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = CartItemWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        item = put_item(
            request.user,
            data["sku_id"],
            data["quantity"],
            data.get("selected", True),
        )
        body = CartItemSerializer(item, context=self.get_serializer_context()).data
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(request=CartItemPatchSerializer, responses=CartItemSerializer,
                   summary="修改数量或勾选（不校验商品状态，只校验库存与数量范围）")
    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = CartItemPatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = patch_item(
            request.user,
            self.get_object(),
            quantity=payload.validated_data.get("quantity"),
            selected=payload.validated_data.get("selected"),
        )
        body = CartItemSerializer(item, context=self.get_serializer_context()).data
        return Response(body)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        remove_item(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartSummaryView(APIView):
    """GET /cart/ — 结算前汇总：可结算项小计 + 是否存在不可用项。"""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CartSummarySerializer, summary="购物车汇总：服务端计算小计")
    def get(self, request: Request) -> Response:
        items = CartItemSerializer(
            CartItem.objects.filter(user=request.user).select_related("sku", "sku__product"),
            many=True,
        ).data
        selectable = [item for item in items if item["selected"] and item["available"]]
        subtotal = sum(
            (Decimal(item["line_amount"]) for item in selectable), start=Decimal("0.00")
        )
        return Response(
            {
                "items": items,
                "selected_count": len(selectable),
                "subtotal": str(subtotal),
                "has_unavailable": any(not item["available"] for item in items),
            }
        )
