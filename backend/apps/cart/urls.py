from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CartItemViewSet, CartSummaryView

router = SimpleRouter()
router.register("cart-items", CartItemViewSet, basename="cart-item")

urlpatterns = [
    path("cart/", CartSummaryView.as_view(), name="cart-summary"),
    *router.urls,
]
