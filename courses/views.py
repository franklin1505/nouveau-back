from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from configurations.helpers import create_response
from .utils import send_test_notifications, send_anonymous_notification, send_anonymous_reservation_notification

# Create your views here.
""" from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PromoCode, TariffRule, Notification

@receiver(post_save, sender=PromoCode)
def check_usage_limit(sender, instance, **kwargs):
    if instance.usage_limit is not None and instance.usage_count >= instance.usage_limit:
        # Vérifier si une notification existe déjà
        if not Notification.objects.filter(related_rule__promo_code=instance, type="usage_limit", status="unread").exists():
            related_rule = TariffRule.objects.filter(promo_code=instance).first()
            if related_rule:
                Notification.objects.create(
                    title="Limite d'utilisation atteinte",
                    message=f"La règle '{related_rule.name}' a atteint sa limite d'utilisation fixée à {instance.usage_limit}.",
                    type="usage_limit",
                    related_rule=related_rule
                )
 """

class TestAnonymousNotificationsView(APIView):
    """
    Vue pour tester l'envoi de notifications aux utilisateurs anonymes via WebSocket.
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """
        Envoie des notifications test aux utilisateurs anonymes via les deux canaux WebSocket.
        """
        try:
            # Envoyer une notification standard aux utilisateurs anonymes
            send_anonymous_notification(
                title="Notification Anonyme Test",
                message="Ceci est une notification test envoyée aux utilisateurs anonymes via le canal standard.",
                data={'test_id': 'anonymous-123'}
            )
            
            # Envoyer une notification de réservation aux utilisateurs anonymes
            send_anonymous_reservation_notification(
                title="Réservation Anonyme Test",
                message="Ceci est une notification test envoyée aux utilisateurs anonymes via le canal de réservation.",
                data={'reservation_id': 'anonymous-456', 'status': 'test'}
            )
            
            return create_response(
                status_type="success",
                message="Notifications test anonymes envoyées avec succès",
                data={
                    'standard_notification': {
                        'title': "Notification Anonyme Test",
                        'message': "Ceci est une notification test envoyée aux utilisateurs anonymes via le canal standard."
                    },
                    'reservation_notification': {
                        'title': "Réservation Anonyme Test",
                        'message': "Ceci est une notification test envoyée aux utilisateurs anonymes via le canal de réservation."
                    }
                }
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message="Erreur lors de l'envoi des notifications test anonymes",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=str(e)
            )

class TestNotificationsView(APIView):
    """
    Vue pour tester l'envoi de notifications via WebSocket.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """
        Envoie des notifications test via les deux canaux WebSocket.
        """
        try:
            result = send_test_notifications(request.user)
            return create_response(
                status_type="success",
                message="Notifications test envoyées avec succès",
                data=result
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message="Erreur lors de l'envoi des notifications test",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=str(e)
            )
