from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from configurations.helpers import create_response
from configurations.models import Notification
from configurations.serializers import NotificationSerializer

class ArchivedNotificationsView(APIView):
    """
    Vue simple pour lister les notifications archivées sans pagination.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Récupérer toutes les notifications archivées
        notifications = Notification.objects.filter(status="archived").order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        
        return create_response(
            status_type="success",
            message="Liste des notifications archivées récupérée avec succès",
            data={
                "count": notifications.count(),
                "results": serializer.data
            }
        )

class UnreadNotificationsView(APIView):
    """
    Vue pour lister les notifications non lues.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        notifications = Notification.objects.filter(status="unread").order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        
        return create_response(
            status_type="success",
            message="Liste des notifications non lues récupérée avec succès",
            data={
                "count": notifications.count(),
                "results": serializer.data
            }
        )
class NotificationArchiveView(APIView):
    """
    Vue pour archiver une ou plusieurs notifications.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        notification_ids = request.data.get("notification_ids", [])
        if not isinstance(notification_ids, list) or not notification_ids:
            return create_response(
                status_type="error",
                message="Une liste d'IDs de notifications est requise",
                http_status=status.HTTP_400_BAD_REQUEST
            )

        # Filtrer les notifications valides à archiver
        notifications = Notification.objects.filter(id__in=notification_ids, status="unread")
        if not notifications.exists():
            return create_response(
                status_type="error",
                message="Aucune notification valide trouvée pour archivage",
                http_status=status.HTTP_404_NOT_FOUND
            )

        # Archiver les notifications
        notifications.update(status="archived")

        return create_response(
            status_type="success",
            message=f"{notifications.count()} notification(s) archivée(s) avec succès",
            data={"archived_ids": notification_ids}
        )