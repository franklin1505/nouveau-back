from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import Http404

from courses.Reservations.helpers import handle_api_exceptions, create_response
from courses.models import Booking
from .services import BookingStatsService
from .serializers import (
    GlobalBookingStatisticsSerializer, 
    BookingCompleteSerializer,
    BookingBasicSerializer,
    BookingUpdateSerializer
)
from .pagination import BookingPagination
from .helpers import (
    extract_booking_filters,
    extract_scope_and_search_key,
    build_empty_detail_response,
    build_global_stats_response,
    build_detail_response,
    build_update_response,
    validate_detail_request,
    validate_booking_detail_request
)

class GlobalBookingStatisticsView(APIView):
    """View to get global booking statistics with status workflow"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request):
        params = extract_scope_and_search_key(request)
        scope = params['scope']
        
        main_stats = BookingStatsService.get_main_stats()
        status_workflow = BookingStatsService.get_status_workflow_stats(scope)
        
        statistics_data = {
            'main_stats': main_stats,
            'status_workflow': status_workflow
        }
        
        serializer = GlobalBookingStatisticsSerializer(statistics_data)
        return build_global_stats_response(main_stats, serializer.data)

class BookingStatisticsDetailView(APIView):
    """View to get detailed booking statistics with filtering and pagination"""
    permission_classes = [IsAuthenticated]
    pagination_class = BookingPagination
    
    @handle_api_exceptions
    def get(self, request):
        is_valid, error_response, params = validate_detail_request(request)
        if not is_valid:
            return error_response
        
        scope = params['scope']
        search_key = params['search_key']
        filters = extract_booking_filters(request)
        
        queryset = BookingStatsService.filter_bookings(
            scope=scope,
            search_key=search_key,
            **filters
        )
        
        if not queryset.exists():
            return build_empty_detail_response(Booking)
        
        return self._build_paginated_response(request, queryset)
    
    def _build_paginated_response(self, request, queryset):
        """Build paginated response with sub-stats"""
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        sub_stats = BookingStatsService.get_sub_stats(queryset)
        serializer = BookingCompleteSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data, sub_stats)

class BookingDetailView(APIView):
    """View to get single booking detail by ID"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        is_valid, error_response = validate_booking_detail_request(booking_id)
        if not is_valid:
            return error_response
        
        try:
            booking = BookingStatsService.get_booking_by_id(booking_id)
            serializer = BookingCompleteSerializer(booking)
            return build_detail_response(serializer.data)
        except Http404:
            return create_response(
                status_type="error",
                message="Réservation non trouvée",
                http_status=status.HTTP_404_NOT_FOUND
            )

class BookingUpdateView(APIView):
    """View to update booking and related models"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def put(self, request, booking_id):
        """Full update of booking"""
        return self._update_booking(request, booking_id, partial=False)
    
    @handle_api_exceptions
    def patch(self, request, booking_id):
        """Partial update of booking"""
        return self._update_booking(request, booking_id, partial=True)
    
    def _update_booking(self, request, booking_id, partial=True):
        """Common update logic for PUT and PATCH"""
        is_valid, error_response = validate_booking_detail_request(booking_id)
        if not is_valid:
            return error_response
        
        try:
            booking = BookingStatsService.get_booking_by_id(booking_id)
            serializer = BookingUpdateSerializer(
                booking, 
                data=request.data, 
                partial=partial
            )
            
            if serializer.is_valid():
                updated_booking = serializer.save()
                response_serializer = BookingCompleteSerializer(updated_booking)
                update_type = "partielle" if partial else "complète"
                return create_response(
                    status_type="success",
                    message=f"Mise à jour {update_type} effectuée avec succès",
                    data=response_serializer.data
                )
            
            return create_response(
                status_type="error",
                message="Données invalides",
                data=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except Http404:
            return create_response(
                status_type="error",
                message="Réservation non trouvée",
                http_status=status.HTTP_404_NOT_FOUND
            )