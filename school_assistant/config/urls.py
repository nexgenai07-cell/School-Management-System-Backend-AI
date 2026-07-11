"""
Project-level URL configuration.

This file should only need one new line per app, ever -- the actual,
frequent route additions happen inside each app's own
urls/admin.py / teacher.py / student.py / parent.py.
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# (Optional Stripe webhook import)
# from finance.views.admin import StripeWebhookView

schema_view = get_schema_view(
    openapi.Info(
        title="School ERP API",
        default_version="v1",
        description="REST API for the Smart School ERP (Admin / Teacher / Student / Parent)",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin site (renamed to avoid clash with /api/admin/)
    path("admin-site/", admin.site.urls),

    # ── Swagger / ReDoc ──────────────────────────────────────
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # ✅ FIX: Add the raw OpenAPI schema endpoint (required for Swagger UI to load)
    path("swagger/?format=openapi", schema_view.without_ui(cache_timeout=0), name="schema-json"),

    # ── API Routes ────────────────────────────────────────────
    path("api/", include("accounts.urls")),
    path("api/", include("academics.urls")),
    path("api/", include("attendance.urls")),
    path("api/", include("finance.urls")),
    path("api/", include("communication.urls")),
    path("api/", include("administration.urls")),
    path("api/", include("chat.urls")),
]