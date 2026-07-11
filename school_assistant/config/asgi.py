"""
ASGI config.

Required because the AI chatbot uses WebSockets (via Django Channels) for
real-time message delivery, in addition to normal HTTP request/response.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# This must be created BEFORE importing anything that touches models, so
# Django's app registry is ready first.
django_asgi_app = get_asgi_application()

# ✅ PERMANENT FIX: Wake up Neon DB at server startup
# This ensures the database connection is alive BEFORE any WebSocket
# handshake, preventing the 5-second cold-start timeout.
from django.db import connection
try:
    connection.ensure_connection()
    print("✅ Database connection established at startup")
except Exception as e:
    print(f"⚠️ Could not connect to DB at startup: {e}")

from channels.routing import ProtocolTypeRouter, URLRouter

from chat.middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # JWTAuthMiddleware (not Channels' default session-based
    # AuthMiddlewareStack) because this project authenticates entirely
    # via JWT -- there's no Django session cookie to read here.
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})