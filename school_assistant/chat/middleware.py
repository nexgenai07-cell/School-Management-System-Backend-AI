"""
JWT Authentication middleware for Django Channels WebSocket connections.

The HTTP API authenticates every request with a JWT access token sent in
an `Authorization: Bearer <token>` header (see REST_FRAMEWORK settings).
Browsers can't attach custom headers when opening a WebSocket, so the
frontend instead passes the SAME access token as a query string param:

    wss://<host>/ws/chat/<session_id>/?token=<access_token>

This middleware reads that token, validates it exactly the way
rest_framework_simplejwt validates HTTP requests, and attaches the
resulting User to `scope["user"]` -- mirroring what Channels' built-in
session-based AuthMiddlewareStack does, but for JWT instead of cookies.
If the token is missing/invalid/expired/the account isn't Active,
scope["user"] is AnonymousUser and ChatConsumer.connect() rejects it.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user_from_token(token: str):
    from accounts.models import User

    try:
        validated_token = AccessToken(token)
        user_id = validated_token["user_id"]
    except (TokenError, KeyError):
        return AnonymousUser()

    try:
        user = User.objects.select_related("role").get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

    if not user.is_active or user.status != "Active":
        return AnonymousUser()

    return user


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticates WebSocket connections using a `?token=<JWT access token>` query param."""

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]

        scope["user"] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)