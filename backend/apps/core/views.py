"""Liveness and readiness probes.

Liveness only reports the process; readiness checks DB and cache so a failing
dependency is visible without exposing configuration.
"""
import logging

from django.db import connection
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class LivenessSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()


class ReadinessSerializer(serializers.Serializer):
    status = serializers.CharField()
    checks = serializers.DictField(child=serializers.CharField())


class LiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses=LivenessSerializer, summary="存活探针：只代表进程在跑")
    def get(self, request):
        return Response({"status": "ok", "service": "shop-api"})


class ReadyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        responses={200: ReadinessSerializer, 503: ReadinessSerializer},
        summary="就绪探针：数据库或缓存不可用时返回 503 degraded",
    )
    def get(self, request):
        checks = {}
        ok = True

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            logger.exception("readiness: database check failed")
            checks["database"] = "unavailable"
            ok = False

        try:
            cache.set("shop:health:ping", "1", 10)
            checks["cache"] = "ok" if cache.get("shop:health:ping") == "1" else "unavailable"
            if checks["cache"] != "ok":
                ok = False
        except Exception:  # noqa: BLE001
            logger.exception("readiness: cache check failed")
            checks["cache"] = "unavailable"
            ok = False

        return Response(
            {"status": "ok" if ok else "degraded", "checks": checks},
            status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
