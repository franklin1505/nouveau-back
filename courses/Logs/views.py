from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from courses.Logs.serializers import BookingLogSerializer
from courses.Logs.services import BookingLogService
from courses.Reservations.helpers import handle_api_exceptions, create_response
from courses.models import Booking

class BookingTimelineView(APIView):
    """Vue pour récupérer la timeline complète d'un booking"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        logs = BookingLogService.get_booking_timeline(booking)
        serializer = BookingLogSerializer(logs, many=True)
        
        return create_response(
            status_type="success",
            message="Timeline de la réservation récupérée avec succès",
            data={
                'booking_id': booking_id,
                'booking_number': booking.booking_number,
                'total_actions': logs.count(),
                'timeline': serializer.data
            }
        )

class UserActionsView(APIView):
    """Vue pour récupérer les actions d'un utilisateur"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request):
        limit = int(request.query_params.get('limit', 50))
        logs = BookingLogService.get_user_actions(request.user, limit)
        serializer = BookingLogSerializer(logs, many=True)
        
        return create_response(
            status_type="success",
            message="Actions utilisateur récupérées avec succès",
            data={
                'user_id': request.user.id,
                'user_name': request.user.get_full_name() or request.user.username,
                'total_actions': logs.count(),
                'actions': serializer.data
            }
        )