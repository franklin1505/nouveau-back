from celery import shared_task
from django.contrib.auth import get_user_model
from .utils import create_and_send_notification, send_reservation_notification

User = get_user_model()

@shared_task
def send_scheduled_notification(user_id, title, message, notification_type="expiration"):
    """
    Tâche Celery pour envoyer une notification programmée.
    
    Args:
        user_id: ID de l'utilisateur destinataire
        title: Titre de la notification
        message: Contenu de la notification
        notification_type: Type de notification (par défaut: "expiration")
    
    Returns:
        ID de la notification créée
    """
    try:
        user = User.objects.get(id=user_id)
        notification = create_and_send_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )
        return notification.id
    except User.DoesNotExist:
        return None
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification programmée: {str(e)}")
        return None

@shared_task
def send_scheduled_reservation_notification(user_id, title, message, data=None):
    """
    Tâche Celery pour envoyer une notification de réservation programmée.
    
    Args:
        user_id: ID de l'utilisateur destinataire
        title: Titre de la notification
        message: Contenu de la notification
        data: Données supplémentaires à inclure dans la notification (optionnel)
    
    Returns:
        True si la notification a été envoyée avec succès, False sinon
    """
    try:
        user = User.objects.get(id=user_id)
        send_reservation_notification(
            user=user,
            title=title,
            message=message,
            data=data
        )
        return True
    except User.DoesNotExist:
        return False
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification de réservation programmée: {str(e)}")
        return False
