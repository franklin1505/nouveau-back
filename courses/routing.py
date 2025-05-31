from django.urls import path
from .consumers import ReservationConsumer

websocket_urlpatterns = [
    path('ws/reservations/', ReservationConsumer.as_asgi()),
]
