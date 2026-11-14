"""Authentication and profile endpoints."""
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.exceptions import BusinessError

from .models import Address
from .serializers import (
    AddressSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import create_address, delete_address, update_address
from .tokens import ShopTokenObtainPairSerializer, tokens_for_user

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth/"


def _cookie_kwargs():
    return {
        "httponly": True,
        "secure": getattr(settings, "REFRESH_COOKIE_SECURE", True),
        "samesite": "Lax",
        "path": REFRESH_COOKIE_PATH,
    }


def _set_refresh_cookie(response, raw_refresh: str) -> None:
    response.set_cookie(REFRESH_COOKIE, raw_refresh, max_age=7 * 24 * 3600, **_cookie_kwargs())


def _clear_refresh_cookie(response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def _require_csrf(request) -> None:
    """Cookie-authenticated endpoints must echo the csrftoken cookie in a header."""
    header = request.META.get("HTTP_X_CSRFTOKEN", "")
    cookie = request.COOKIES.get("csrftoken", "")
    if not header or not cookie or header != cookie:
        raise BusinessError(
            "CSRF_FAILED", "CSRF 校验失败，请刷新页面后重试", status.HTTP_403_FORBIDDEN
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "register_ip"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh, access = tokens_for_user(user)
        response = Response(
            {
                "access": str(access),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_ip"
    serializer_class = ShopTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh = response.data.pop("refresh", None)
            if refresh:
                _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        _require_csrf(request)
        raw = request.COOKIES.get(REFRESH_COOKIE, "")
        if not raw:
            raise BusinessError("UNAUTHORIZED", "登录状态已失效", status.HTTP_401_UNAUTHORIZED)
        try:
            old = RefreshToken(raw)
            user_id = old.payload.get("user_id")
            auth_version = old.payload.get("auth_version")
        except TokenError:
            raise BusinessError("UNAUTHORIZED", "登录状态已失效", status.HTTP_401_UNAUTHORIZED)

        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        if user is None or not user.is_active or auth_version != user.auth_version:
            raise BusinessError("UNAUTHORIZED", "登录状态已失效", status.HTTP_401_UNAUTHORIZED)

        old.blacklist()
        refresh, access = tokens_for_user(user)
        response = Response({"access": str(access), "user": UserSerializer(user).data})
        _set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        _require_csrf(request)
        raw = request.COOKIES.get(REFRESH_COOKIE, "")
        user_id = None
        if raw:
            try:
                token = RefreshToken(raw)
                user_id = token.payload.get("user_id")
                token.blacklist()
            except TokenError:
                user_id = None

        if user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.filter(pk=user_id).first()
            if user is not None:
                user.bump_auth_version()

        response = Response({"logged_out": True})
        _clear_refresh_cookie(response)
        return response


class CsrfTokenView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.auth_version += 1
        user.save(update_fields=["password", "must_change_password", "auth_version", "updated_at"])

        from .models import User

        refresh, access = tokens_for_user(user)
        response = Response({"access": str(access), "user": UserSerializer(user).data})
        _set_refresh_cookie(response, str(refresh))
        return response


class AddressViewSet(ModelViewSet):
    """CRUD for the caller's own addresses; other users' rows are invisible."""

    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = create_address(request.user, dict(serializer.validated_data))
        return Response(self.get_serializer(address).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        address = self.get_object()
        serializer = self.get_serializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        address = update_address(request.user, address, dict(serializer.validated_data))
        return Response(self.get_serializer(address).data)

    def destroy(self, request, *args, **kwargs):
        address = self.get_object()
        delete_address(request.user, address)
        return Response(status=status.HTTP_204_NO_CONTENT)
