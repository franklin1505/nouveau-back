# courses/Reservations/Reservations_details/recurring_views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.core.exceptions import ValidationError

from courses.Reservations.Reservations_details.pagination import BookingPagination
from courses.Reservations.Reservations_details.recurring.helpers import BookingExtractor, ResponseHelper
from courses.Reservations.Reservations_details.recurring.serializers import RecurringConfigSerializer, RecurringCreationSerializer
from courses.Reservations.Reservations_details.recurring.services import RecurringConfigService, RecurringCreationService, RecurringPreviewService
from courses.Reservations.helpers import handle_api_exceptions, create_response


class RecurringTypesView(APIView):
    """GET /{id}/recurring/types/ - Types avec config intelligente"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        try:
            # Validation booking
            base_booking, error = RecurringPreviewService.validate_booking_for_recurring(booking_id)
            if error:
                return create_response("error", error, http_status=status.HTTP_400_BAD_REQUEST)
            
            # Config intelligente
            available_types = RecurringConfigService.get_intelligent_configs(base_booking)
            
            # Info booking + trajet
            booking_info = BookingExtractor.get_base_booking_info(base_booking)
            booking_info.update(BookingExtractor.get_trip_data(base_booking))
            
            return create_response(
                "success",
                "Types de récurrence disponibles",
                data={
                    'booking': booking_info,
                    'types': available_types
                }
            )
            
        except Exception as e:
            return create_response("error", str(e), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecurringPreviewView(APIView):
    """POST/GET /{id}/recurring/preview/ - Preview bookings complets"""
    permission_classes = [IsAuthenticated]
    pagination_class = BookingPagination  # ✅ RÉUTILISATION
    
    @handle_api_exceptions
    def post(self, request, booking_id):
        """Génère preview"""
        try:
            # Validation config
            serializer = RecurringConfigSerializer(data=request.data)
            if not serializer.is_valid():
                return create_response(
                    "error", 
                    "Données invalides", 
                    data=serializer.errors, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # Création template + preview
            template, occurrences = RecurringPreviewService.create_template_and_preview(
                booking_id, serializer.validated_data, request.user
            )
            
            # ✅ PAGINATION UNIFIÉE
            queryset = template.occurrences.all().order_by('occurrence_number')
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            
            # ✅ FORMATAGE AVEC HELPERS EXISTANTS
            preview_data = RecurringPreviewService.format_occurrences_preview(page, template.base_booking)
            
            # ✅ RÉPONSE AVEC PAGINATION STANDARD
            return paginator.get_paginated_response(preview_data, {
                'template_id': template.id,
                'total_occurrences': len(occurrences),
                'recurrence_type': template.recurrence_type
            })
            
        except ValidationError as e:
            return create_response("error", str(e), http_status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return create_response("error", str(e), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        """Récupère page preview existant"""
        try:
            # Template actif
            from courses.models import RecurringBookingTemplate
            try:
                template = RecurringBookingTemplate.objects.get(base_booking_id=booking_id, is_active=True)
            except RecurringBookingTemplate.DoesNotExist:
                return create_response("error", "Aucun preview actif", http_status=status.HTTP_404_NOT_FOUND)
            
            # ✅ PAGINATION UNIFIÉE
            queryset = template.occurrences.all().order_by('occurrence_number')
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            
            # ✅ FORMATAGE AVEC HELPERS EXISTANTS
            preview_data = RecurringPreviewService.format_occurrences_preview(page, template.base_booking)
            
            # ✅ RÉPONSE AVEC PAGINATION STANDARD
            return paginator.get_paginated_response(preview_data, {
                'template_id': template.id,
                'recurrence_type': template.recurrence_type
            })
            
        except Exception as e:
            return create_response("error", str(e), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecurringCreateView(APIView):
    """POST /{template_id}/recurring/create/ - Création finale"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def post(self, request, template_id):
        try:
            # Validation structure optimisée
            serializer = RecurringCreationSerializer(data=request.data)
            if not serializer.is_valid():
                return create_response(
                    "error", 
                    "Données invalides", 
                    data=serializer.errors, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            validated_data = serializer.validated_data
            
            # Vérification cohérence
            if validated_data['template_id'] != template_id:
                return create_response("error", "Template ID incohérent", http_status=status.HTTP_400_BAD_REQUEST)
            
            # Création bookings
            result = RecurringCreationService.create_final_bookings(
                template_id,
                validated_data['valid_occurrences'],
                validated_data.get('modified_occurrences', []),
                request.user
            )
            
            # Message selon résultat
            if result['summary']['total_errors'] == 0:
                message = f"{result['summary']['total_created']} bookings créés avec succès"
            else:
                message = f"{result['summary']['total_created']} bookings créés, {result['summary']['total_errors']} erreurs"
            
            return create_response("success", message, data=result, http_status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return create_response("error", str(e), http_status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return create_response("error", str(e), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)