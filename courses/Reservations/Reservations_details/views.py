from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import Http404

from courses.Reservations.helpers import handle_api_exceptions
from courses.models import Booking, BookingSegment

from .services import BookingStatsService
from .serializers import (
    ExtendedGlobalBookingStatisticsSerializer, ExtendedBookingCompleteSerializer, 
    BookingUpdateSerializer, ReturnTripDataSerializer, RoundTripDuplicateModificationSerializer,
    BookingSegmentSerializer, DuplicateModificationSerializer
)
from .pagination import BookingPagination
from .helpers import (
    CommunicationHandler,
    FilterContextBuilder,
    ResponseDataBuilder,
    validate_booking_detail_request,
    build_extended_empty_detail_response, build_detail_response,
    convert_booking_to_round_trip, duplicate_booking_unified,
    generate_duplicate_preview, generate_return_preview,
    create_transformation_log_safe, ValidationService, ResponseBuilder,
)

class BaseBookingView(APIView):
    """Classe de base avec méthodes communes"""
    permission_classes = [IsAuthenticated]
    
    def validate_and_extract_params(self, request):
        """Validation et extraction des paramètres - méthode réutilisable"""
        return ValidationService.validate_params_for_statistics(request)
    
    def get_filter_context(self, params):
        """Construction du contexte de filtrage - méthode réutilisable"""
        return FilterContextBuilder.build_context(params)

class ExtendedGlobalBookingStatisticsView(BaseBookingView):
    """✅ CORRIGÉ : Vue globale optimisée avec filtres utilisateur"""
    
    @handle_api_exceptions
    def get(self, request):
        is_valid, error_response, params = self.validate_and_extract_params(request)
        if not is_valid:
            return error_response
        
        # ✅ CORRECTION : Utiliser les stats filtrées par utilisateur
        response_data = BookingStatsService.get_user_filtered_stats(
            user=request.user,
            scope=params.get('scope'),
            search_key=params.get('search_key')
        )
        
        serializer = ExtendedGlobalBookingStatisticsSerializer(response_data)
        return ResponseBuilder.success_response(
            message="Statistiques globales récupérées avec succès",
            data=serializer.data
        )

class ExtendedBookingStatisticsDetailView(BaseBookingView):
    """✅ CORRIGÉ : Vue détaillée optimisée avec filtres utilisateur et pagination corrigée"""
    pagination_class = BookingPagination
    
    @handle_api_exceptions
    def get(self, request):
        is_valid, error_response, params = self.validate_and_extract_params(request)
        if not is_valid:
            return error_response
        
        # ✅ CORRECTION : Utiliser les bookings filtrés par utilisateur
        queryset = BookingStatsService.get_user_filtered_bookings(request.user, params)
        
        if not queryset.exists():
            return build_extended_empty_detail_response(params)
        
        paginator = self.pagination_class()
        
        # ✅ CORRECTION : Utiliser page_size de la requête
        if 'page_size' in request.query_params:
            try:
                paginator.page_size = min(int(request.query_params['page_size']), 100)
            except (ValueError, TypeError):
                pass
        
        page = paginator.paginate_queryset(queryset, request)
        
        sub_stats = BookingStatsService.get_extended_sub_stats(queryset, params)
        filter_context = self.get_filter_context(params)
        
        serializer = ExtendedBookingCompleteSerializer(page, many=True)
        return paginator.get_paginated_response(
            data=serializer.data,
            sub_stats=sub_stats,
            filter_context=filter_context
        )

class BookingDetailView(BaseBookingView):
    """Vue détail individual simplifiée"""
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        is_valid, error_response = validate_booking_detail_request(booking_id)
        if not is_valid:
            return error_response
        
        try:
            booking = BookingStatsService.get_booking_by_id(booking_id)
            
            # ✅ NOUVEAU : Vérifier les permissions utilisateur
            from .user_permissions import BookingUserPermissionService
            try:
                # Créer un queryset avec juste ce booking pour vérifier les permissions
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation d'accéder à cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = ExtendedBookingCompleteSerializer(booking)
            return build_detail_response(serializer.data)
        except Http404:
            return ResponseBuilder.not_found_response("Réservation")

class BookingUpdateView(BaseBookingView):
    """Vue de mise à jour simplifiée avec vérification permissions"""
    
    @handle_api_exceptions
    def put(self, request, booking_id):
        return self._update_booking(request, booking_id, partial=False)
    
    @handle_api_exceptions
    def patch(self, request, booking_id):
        return self._update_booking(request, booking_id, partial=True)
    
    def _update_booking(self, request, booking_id, partial=True):
        is_valid, error_response = validate_booking_detail_request(booking_id)
        if not is_valid:
            return error_response
        
        try:
            booking = BookingStatsService.get_booking_by_id(booking_id)
            
            # ✅ NOUVEAU : Vérifier les permissions utilisateur
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation de modifier cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = BookingUpdateSerializer(
                booking, data=request.data, partial=partial, context={'request': request}
            )
            
            if serializer.is_valid():
                updated_booking = serializer.save()
                response_serializer = ExtendedBookingCompleteSerializer(updated_booking)
                
                update_type = "partielle" if partial else "complète"
                return ResponseBuilder.success_response(
                    message=f"Mise à jour {update_type} effectuée avec succès",
                    data=response_serializer.data
                )
            
            return ResponseBuilder.validation_error_response(serializer.errors)
            
        except Http404:
            return ResponseBuilder.not_found_response("Réservation")

class BookingReturnPreviewView(BaseBookingView):
    """Vue aperçu retour allégée"""
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        try:
            # ✅ NOUVEAU : Vérifier les permissions avant de générer l'aperçu
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation d'accéder à cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            preview_data = generate_return_preview(booking_id)
            return ResponseBuilder.success_response(
                message="Aperçu du trajet retour généré avec succès",
                data=preview_data
            )
        except ValueError as e:
            return ResponseBuilder.error_response(str(e))

class BookingReturnCreateView(BaseBookingView):
    """Vue création retour allégée avec délégation communication"""
    
    @handle_api_exceptions
    def post(self, request, booking_id):
        try:
            # ✅ NOUVEAU : Vérifier les permissions
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation de modifier cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = ReturnTripDataSerializer(data=request.data)
            if not serializer.is_valid():
                return ResponseBuilder.validation_error_response(serializer.errors)
            
            result = convert_booking_to_round_trip(
                booking_id, serializer.validated_data, user=request.user
            )
            
            if not result.get('logs_created', False):
                booking = Booking.objects.get(id=booking_id)
                alternative_success = create_transformation_log_safe(
                    booking, request.user, serializer.validated_data
                )
                if alternative_success:
                    result['logs_created'] = True
            
            comm_success, comm_details = CommunicationHandler.handle_round_trip_communications(
                booking_id, serializer.validated_data, request.user
            )
            
            response_data = ResponseDataBuilder.build_transformation_response_data(
                booking_id, result, serializer.validated_data, 
                request.user, comm_success, comm_details
            )
            
            message = "Réservation transformée en aller-retour avec succès"
            if not comm_success:
                message += ". Attention: problème envoi communications"
            
            return ResponseBuilder.success_response(
                message=message,
                data=response_data,
                http_status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return ResponseBuilder.error_response(str(e))

class BookingDuplicatePreviewView(BaseBookingView):
    """Vue aperçu duplication allégée"""
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        try:
            # ✅ NOUVEAU : Vérifier les permissions
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation d'accéder à cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            preview_data = generate_duplicate_preview(booking_id)
            return ResponseBuilder.success_response(
                message="Aperçu de duplication généré avec succès",
                data=preview_data
            )
        except ValueError as e:
            return ResponseBuilder.error_response(str(e))

class BookingDuplicateCreateView(BaseBookingView):
    """Vue création duplication allégée"""
    
    @handle_api_exceptions
    def post(self, request, booking_id):
        try:
            # ✅ NOUVEAU : Vérifier les permissions
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation d'accéder à cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            source_booking, error = ValidationService.validate_booking_for_duplication(booking_id)
            if error:
                return ResponseBuilder.not_found_response("Booking source")
            
            serializer_class = (RoundTripDuplicateModificationSerializer 
                              if source_booking.booking_type == 'round_trip' 
                              else DuplicateModificationSerializer)
            
            serializer = serializer_class(data=request.data)
            if not serializer.is_valid():
                return ResponseBuilder.validation_error_response(serializer.errors)
            
            result = duplicate_booking_unified(booking_id, serializer.validated_data, request.user)
            
            comm_success, comm_details = CommunicationHandler.handle_duplication_communications(
                result['new_booking_id'], booking_id, request.user
            )
            
            response_data = ResponseDataBuilder.build_duplication_response_data(
                result, comm_success, comm_details, request.user
            )
            
            message = "Booking dupliqué avec succès"
            if not comm_success:
                message += ". Attention: problème envoi communications"
            
            return ResponseBuilder.success_response(
                message=message,
                data=response_data,
                http_status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return ResponseBuilder.error_response(str(e))

class BookingSegmentUpdateView(BaseBookingView):
    """Vue mise à jour segment allégée"""
    
    ALLOWED_FIELDS = ['status', 'compensation', 'commission']
    
    @handle_api_exceptions
    def patch(self, request, booking_id, segment_type):
        if segment_type not in ['outbound', 'return']:
            return ResponseBuilder.error_response(
                "Type de segment invalide. Utilisez 'outbound' ou 'return'"
            )
        
        try:
            # ✅ NOUVEAU : Vérifier les permissions
            from .user_permissions import BookingUserPermissionService
            try:
                single_booking_qs = Booking.objects.filter(id=booking_id)
                filtered_qs = BookingUserPermissionService.apply_user_booking_filter(single_booking_qs, request.user)
                
                if not filtered_qs.exists():
                    return ResponseBuilder.error_response(
                        "Vous n'avez pas l'autorisation de modifier cette réservation",
                        http_status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return ResponseBuilder.error_response(
                    "Erreur de vérification des permissions",
                    http_status=status.HTTP_403_FORBIDDEN
                )
            
            booking = Booking.objects.get(id=booking_id, booking_type='round_trip')
            segment = booking.segments.get(segment_type=segment_type)
            
            is_valid, error_response, update_data = ValidationService.validate_segment_update_data(
                request.data, self.ALLOWED_FIELDS
            )
            if not is_valid:
                return error_response
            
            compensation = update_data.get('compensation', segment.compensation or 0)
            commission = update_data.get('commission', segment.commission or 0)
            
            is_valid, error_response = ValidationService.validate_compensation_commission(
                compensation, commission
            )
            if not is_valid:
                return error_response
            
            for field, value in update_data.items():
                setattr(segment, field, value)
            segment.save()
            
            segment_serializer = BookingSegmentSerializer(segment)
            return ResponseBuilder.success_response(
                message=f"Segment {segment_type} mis à jour avec succès",
                data={
                    "segment": segment_serializer.data,
                    "updated_fields": list(update_data.keys())
                }
            )
            
        except (Booking.DoesNotExist, BookingSegment.DoesNotExist):
            return ResponseBuilder.not_found_response("Booking ou segment")

# Alias pour compatibilité descendante
GlobalBookingStatisticsView = ExtendedGlobalBookingStatisticsView
BookingStatisticsDetailView = ExtendedBookingStatisticsDetailView