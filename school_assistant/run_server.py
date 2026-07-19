"""Run the ASGI app with WebSocket pings fully disabled -- more reliable
than passing --ws-ping-timeout 0 on the CLI, which doesn't actually
disable the timeout (known uvicorn quirk)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "config.asgi:application",
        host="0.0.0.0",
        port=8000,
        ws="wsproto",
        ws_ping_interval=None,  # native pings poori tarah off
        ws_ping_timeout=None,
    )
# if __name__ == "__main__":
#     uvicorn.run(
#         "config.asgi:application",
#         host="0.0.0.0",
#         port=8000,
#         ws="wsproto",
#         ws_ping_interval=3600,
#         ws_ping_timeout=3600,
#     )