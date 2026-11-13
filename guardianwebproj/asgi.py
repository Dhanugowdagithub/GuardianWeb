"""
ASGI config for guardianwebproj project.
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'guardianwebproj.settings')

import django
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from guardianwebapp.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})