import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from configurations.routing import websocket_urlpatterns as config_websocket_urlpatterns
from courses.routing import websocket_urlpatterns as courses_websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Combiner les routes WebSocket des différentes applications
combined_websocket_urlpatterns = config_websocket_urlpatterns + courses_websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(combined_websocket_urlpatterns)
    ),
})
