import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ReservationConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = None

    async def connect(self):
        from django.contrib.auth.models import AnonymousUser
        
        self.user = self.scope['user']

        # Pour le test, accepter les connexions même si l'utilisateur n'est pas authentifié
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            # Utiliser un groupe générique pour les utilisateurs non authentifiés
            self.group_name = 'reservations_anonymous'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            return

        self.group_name = f'reservations_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Handle incoming WebSocket messages if necessary
        pass

    async def send_reservation_notification(self, event):
        notification_data = event['data']
        await self.send(text_data=json.dumps({
            'type': 'reservation_notification',
            'data': notification_data,
        }))
