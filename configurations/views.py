from rest_framework import generics, status
from rest_framework.views import APIView
from configurations.helpers import create_response
from configurations.models import Notification
from configurations.serializers import NotificationSerializer

# Create your views here.
      
class ArchivedNotificationsView(generics.ListAPIView):
    """
    Vue pour lister les notifications archivées avec pagination.
    """
    queryset = Notification.objects.filter(status="archived").order_by('-created_at')
    serializer_class = NotificationSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return self.get_paginated_response(serializer.data)
    
    
class NotificationArchiveView(APIView):
    """
    Vue pour archiver une ou plusieurs notifications.
    """

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


class UnreadNotificationsView(generics.ListAPIView):
    """
    Vue pour lister les notifications non lues.
    """
    queryset = Notification.objects.filter(status="unread").order_by('-created_at')
    serializer_class = NotificationSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return create_response(
            status_type="success",
            message="Liste des notifications non lues récupérée avec succès",
            data=serializer.data
        )
  