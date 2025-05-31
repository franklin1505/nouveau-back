import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from configurations.models import Notification
from django.utils import timezone

def send_anonymous_notification(title, message, data=None):
    """
    Envoie une notification à tous les utilisateurs anonymes connectés.
    
    Args:
        title: Le titre de la notification
        message: Le contenu de la notification
        data: Données supplémentaires à inclure dans la notification (optionnel)
    """
    if data is None:
        data = {}
    
    notification_data = {
        'title': title,
        'message': message,
        'timestamp': timezone.now().isoformat(),
        **data
    }
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'notifications_anonymous',
        {
            'type': 'send_notification',
            'data': notification_data
        }
    )

def send_anonymous_reservation_notification(title, message, data=None):
    """
    Envoie une notification de réservation à tous les utilisateurs anonymes connectés.
    
    Args:
        title: Le titre de la notification
        message: Le contenu de la notification
        data: Données supplémentaires à inclure dans la notification (optionnel)
    """
    if data is None:
        data = {}
    
    notification_data = {
        'title': title,
        'message': message,
        'timestamp': timezone.now().isoformat(),
        **data
    }
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'reservations_anonymous',
        {
            'type': 'send_reservation_notification',
            'data': notification_data
        }
    )

def create_and_send_notification(user, title, message, notification_type="expiration"):
    """
    Crée une notification dans la base de données et l'envoie via WebSocket.
    
    Args:
        user: L'utilisateur destinataire de la notification
        title: Le titre de la notification
        message: Le contenu de la notification
        notification_type: Le type de notification (par défaut: "expiration")
    
    Returns:
        La notification créée
    """
    # Créer la notification dans la base de données
    notification = Notification.objects.create(
        title=title,
        message=message,
        type=notification_type,
        status="unread",
        user=user
    )
    
    # Envoyer la notification via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user.id}',
        {
            'type': 'send_notification',
            'data': {
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.type,
                'status': notification.status,
                'created_at': notification.created_at.isoformat()
            }
        }
    )
    
    return notification

def send_reservation_notification(user, title, message, data=None):
    """
    Envoie une notification de réservation via WebSocket.
    
    Args:
        user: L'utilisateur destinataire de la notification
        title: Le titre de la notification
        message: Le contenu de la notification
        data: Données supplémentaires à inclure dans la notification (optionnel)
    """
    if data is None:
        data = {}
    
    notification_data = {
        'title': title,
        'message': message,
        'timestamp': timezone.now().isoformat(),
        **data
    }
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'reservations_{user.id}',
        {
            'type': 'send_reservation_notification',
            'data': notification_data
        }
    )

def send_test_notifications(user):
    """
    Envoie des notifications test via les deux canaux WebSocket.
    
    Args:
        user: L'utilisateur destinataire des notifications test
    
    Returns:
        Un dictionnaire contenant les notifications envoyées
    """
    # Notification standard
    notification = create_and_send_notification(
        user=user,
        title="Notification Test",
        message="Ceci est une notification test envoyée via le canal standard.",
        notification_type="expiration"
    )
    
    # Notification de réservation
    send_reservation_notification(
        user=user,
        title="Réservation Test",
        message="Ceci est une notification test envoyée via le canal de réservation.",
        data={
            'reservation_id': 'test-123',
            'status': 'test'
        }
    )
    
    return {
        'standard_notification': {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message
        },
        'reservation_notification': {
            'title': "Réservation Test",
            'message': "Ceci est une notification test envoyée via le canal de réservation."
        }
    }
