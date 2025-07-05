import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Accepter toutes les connexions
        await self.accept()

    async def disconnect(self, close_code):
        # Nettoyer les groupes si nécessaire
        pass

    async def receive(self, text_data):
        # Gérer les messages entrants si nécessaire
        data = json.loads(text_data)
        
        # Si le client s'identifie avec son user_id
        if data.get('type') == 'join' and data.get('user_id'):
            user_id = data['user_id']
            group_name = f'notifications_{user_id}'
            await self.channel_layer.group_add(group_name, self.channel_name)
            
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'message': f'Connecté aux notifications pour user {user_id}'
            }))

    async def send_notification(self, event):
        """Méthode appelée pour envoyer une notification"""
        await self.send(text_data=json.dumps(event['data']))

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Si le client s'identifie avec son user_id
        if data.get('type') == 'join' and data.get('user_id'):
            user_id = data['user_id']
            group_name = f'notifications_{user_id}'
            await self.channel_layer.group_add(group_name, self.channel_name)
            
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'message': f'Connecté aux notifications pour user {user_id}'
            }))

    async def send_notification(self, event):
        """Méthode appelée pour envoyer une notification"""
        await self.send(text_data=json.dumps(event['data']))