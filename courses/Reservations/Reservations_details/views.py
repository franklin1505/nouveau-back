from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import Http404

from courses.Reservations.helpers import create_response, format_booking_data, handle_api_exceptions, send_unified_emails_with_notifications
from courses.models import Booking, BookingLog, BookingSegment
from .services import BookingStatsService
from .serializers import BookingSegmentSerializer, DuplicateModificationSerializer, GlobalBookingStatisticsSerializer, BookingCompleteSerializer, BookingUpdateSerializer, ReturnTripDataSerializer, RoundTripBookingSerializer, RoundTripDuplicateModificationSerializer
from .pagination import BookingPagination
from .helpers import convert_booking_to_round_trip, create_transformation_log_safe, duplicate_booking_unified, extract_booking_filters, extract_scope_and_search_key, build_empty_detail_response, build_global_stats_response, build_detail_response, format_round_trip_booking_data, generate_duplicate_preview, generate_return_preview, send_round_trip_emails_with_notifications, validate_booking_for_duplication, validate_detail_request, validate_booking_detail_request

class GlobalBookingStatisticsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request):
        params = extract_scope_and_search_key(request)
        main_stats = BookingStatsService.get_main_stats()
        status_workflow = BookingStatsService.get_status_workflow_stats(params['scope'])
        serializer = GlobalBookingStatisticsSerializer({'main_stats': main_stats, 'status_workflow': status_workflow})
        return build_global_stats_response(main_stats, serializer.data)

class BookingStatisticsDetailView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = BookingPagination
    
    @handle_api_exceptions
    def get(self, request):
        is_valid, error_response, params = validate_detail_request(request)
        if not is_valid:
            return error_response
        
        queryset = BookingStatsService.filter_bookings(
            scope=params['scope'],
            search_key=params['search_key'],
            **extract_booking_filters(request)
        )
        
        if not queryset.exists():
            return build_empty_detail_response(Booking)
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        sub_stats = BookingStatsService.get_sub_stats(queryset)
        serializer = BookingCompleteSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data, sub_stats)

class BookingDetailView(APIView):
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
    permission_classes = [IsAuthenticated]
    
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
            serializer = BookingUpdateSerializer(booking, data=request.data, partial=partial, context={'request': request})
            
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

class BookingReturnPreviewView(APIView):
    """Vue pour générer un aperçu du trajet retour."""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        """Génère l'aperçu par défaut du trajet retour."""
        try:
            preview_data = generate_return_preview(booking_id)
            return create_response(
                status_type="success",
                message="Aperçu du trajet retour généré avec succès",
                data=preview_data,
                http_status=status.HTTP_200_OK
            )
        except ValueError as e:
            return create_response(
                status_type="error",
                message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la création du trajet retour: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class BookingSegmentUpdateView(APIView):
    """
    Vue pour mettre à jour un segment spécifique d'un booking aller-retour
    """
    permission_classes = [IsAuthenticated]
    
    ALLOWED_FIELDS = ['status', 'compensation', 'commission']
    
    @handle_api_exceptions
    def patch(self, request, booking_id, segment_type):
        """Met à jour un segment spécifique (aller ou retour)"""
        
        if segment_type not in ['outbound', 'return']:
            return create_response(
                status_type="error",
                message="Type de segment invalide. Utilisez 'outbound' ou 'return'",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 1. Récupération du booking et du segment
            booking = Booking.objects.get(id=booking_id, booking_type='round_trip')
            segment = booking.segments.get(segment_type=segment_type)
            
            # 2. Validation des champs autorisés
            update_data = {}
            for field, value in request.data.items():
                if field in self.ALLOWED_FIELDS:
                    update_data[field] = value
                else:
                    return create_response(
                        status_type="error",
                        message=f"Champ '{field}' non autorisé pour la mise à jour",
                        http_status=status.HTTP_400_BAD_REQUEST
                    )
            
            if not update_data:
                return create_response(
                    status_type="error",
                    message="Aucune donnée valide à mettre à jour",
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # 3. Validation compensation/commission
            compensation = update_data.get('compensation', segment.compensation or 0)
            commission = update_data.get('commission', segment.commission or 0)
            
            if compensation > 0 and commission > 0:
                return create_response(
                    status_type="error",
                    message="Vous ne pouvez pas définir à la fois compensation et commission",
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # 4. Mise à jour du segment
            for field, value in update_data.items():
                setattr(segment, field, value)
            segment.save()
            
            # # 5. Log de l'action
            # try:
            #     user_id = request.user.id if request.user.is_authenticated else None
            #     BookingLog.objects.create(
            #         booking=booking,
            #         user_id=user_id,
            #         action=f"Segment {segment_type} mis à jour: {', '.join(update_data.keys())}"
            #     )
            # except:
            #     pass  # Ne pas faire échouer pour un log
            
            # 6. Réponse avec données mises à jour
            segment_serializer = BookingSegmentSerializer(segment)
            
            return create_response(
                status_type="success",
                message=f"Segment {segment_type} mis à jour avec succès",
                data={
                    "segment": segment_serializer.data,
                    "updated_fields": list(update_data.keys())
                },
                http_status=status.HTTP_200_OK
            )
            
        except Booking.DoesNotExist:
            return create_response(
                status_type="error",
                message="Booking aller-retour non trouvé",
                http_status=status.HTTP_404_NOT_FOUND
            )
        except BookingSegment.DoesNotExist:
            return create_response(
                status_type="error",
                message=f"Segment {segment_type} non trouvé pour ce booking",
                http_status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la mise à jour: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la génération de l'aperçu: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BookingReturnCreateView(APIView):
    """
    Vue pour créer le trajet retour et transformer en aller-retour
    Avec envoi d'emails et notifications en temps réel
    """
    permission_classes = [IsAuthenticated]
    
    def validate_return_data(self, request_data):
        """Valide les données du trajet retour"""
        serializer = ReturnTripDataSerializer(data=request_data)
        if not serializer.is_valid():
            raise ValueError(f"Erreurs de validation: {serializer.errors}")
        return serializer.validated_data
    
    @handle_api_exceptions
    def post(self, request, booking_id):
        """Crée le trajet retour et transforme en aller-retour avec emails et notifications"""
        
        try:
            # 1. Validation des données
            validated_data = self.validate_return_data(request.data)
            
            # 2. Conversion en aller-retour avec utilisateur pour le logging
            result = convert_booking_to_round_trip(
                booking_id, 
                validated_data, 
                user=request.user
            )
            
            # 3. Si le log principal a échoué, essayer la version sécurisée
            if not result.get('logs_created', False):
                try:
                    booking = Booking.objects.get(id=booking_id)
                    alternative_success = create_transformation_log_safe(booking, request.user, validated_data)
                    if alternative_success:
                        result['logs_created'] = True
                        print("✅ Log créé avec la méthode alternative")
                except Exception as alt_error:
                    print(f"❌ Échec log alternatif: {alt_error}")
            
            # 4. Récupération du booking transformé pour affichage
            booking = Booking.objects.get(id=booking_id)
            display_data = format_round_trip_booking_data(booking, include_request_data=False)
            
            # 5. 🔥 ENVOI DES EMAILS ET NOTIFICATIONS EN TEMPS RÉEL
            try:
                email_success, email_status = send_round_trip_emails_with_notifications(booking_id)
            except Exception as email_error:
                print(f"Erreur envoi emails/notifications aller-retour: {email_error}")
                email_success = False
                email_status = f"Erreur envoi: {str(email_error)}"
            
            # 6. Détails sur les communications envoyées
            communication_details = []
            if email_success:
                if booking.client:
                    communication_details.append("Email client envoyé")
                else:
                    # Compter les passagers avec email pour réservations admin
                    segments = display_data["display_data"].get("segments", [])
                    passenger_emails = 0
                    for segment in segments:
                        if 'estimate' in segment and 'passengers' in segment['estimate']:
                            for passenger in segment['estimate']['passengers']:
                                if passenger.get("email") and passenger["email"] != "Non renseigné":
                                    passenger_emails += 1
                    if passenger_emails > 0:
                        communication_details.append(f"Emails passagers envoyés ({passenger_emails})")
                    else:
                        communication_details.append("Aucun passager avec email")
                
                communication_details.append("Email manager envoyé")
                communication_details.append("Notification créée")
            
            # 7. Réponse de succès avec informations complètes
            response_data = {
                **result,
                "booking_details": display_data["display_data"],
                "transformation_summary": {
                    "user": f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    "transformation_type": "simple_to_round_trip",
                    "return_departure": validated_data.get('departure'),
                    "return_destination": validated_data.get('destination'),
                    "return_date": validated_data.get('pickup_date'),
                    "return_cost": validated_data.get('total_cost'),
                    "logs_created": result.get('logs_created', False),
                    "emails_sent": email_success,
                    "email_status": email_status
                },
                "communication_status": {
                    "emails_sent": email_success,
                    "notifications_sent": email_success,
                    "details": communication_details,
                    "status_message": email_status
                }
            }
            
            # 8. Message de succès adaptatif
            if email_success:
                success_message = "Réservation transformée en aller-retour avec succès. Emails et notifications envoyés."
            else:
                success_message = "Réservation transformée en aller-retour avec succès. Attention: problème envoi communications."
            
            return create_response(
                status_type="success",
                message=success_message,
                data=response_data,
                http_status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return create_response(
                status_type="error",
                message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la transformation: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BookingDuplicatePreviewView(APIView):
    """Vue pour générer un aperçu de duplication"""
    permission_classes = [IsAuthenticated]
    
    @handle_api_exceptions
    def get(self, request, booking_id):
        try:
            preview_data = generate_duplicate_preview(booking_id)
            return create_response(
                status_type="success",
                message="Aperçu de duplication généré avec succès",
                data=preview_data,
                http_status=status.HTTP_200_OK
            )
        except ValueError as e:
            return create_response(
                status_type="error",
                message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la génération de l'aperçu: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BookingDuplicateCreateView(APIView):
    """Vue pour créer une duplication de booking"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self, booking_type):
        """Retourne le bon serializer selon le type"""
        return RoundTripDuplicateModificationSerializer if booking_type == 'round_trip' else DuplicateModificationSerializer
    
    @handle_api_exceptions
    def post(self, request, booking_id):
        try:
            # Validation du booking source
            source_booking, error = validate_booking_for_duplication(booking_id)
            if error:
                return create_response(status_type="error", message=error, http_status=status.HTTP_404_NOT_FOUND)
            
            # Validation des données
            serializer_class = self.get_serializer_class(source_booking.booking_type)
            serializer = serializer_class(data=request.data)
            if not serializer.is_valid():
                return create_response(
                    status_type="error", 
                    message="Données invalides", 
                    data=serializer.errors, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # Duplication
            result = duplicate_booking_unified(booking_id, serializer.validated_data, request.user)
            
            # Récupération et formatage du nouveau booking
            new_booking = Booking.objects.get(id=result['new_booking_id'])
            display_data = (format_round_trip_booking_data(new_booking, include_request_data=False) 
                          if new_booking.booking_type == 'round_trip' 
                          else format_booking_data(booking=new_booking, include_request_data=False))
            
            # Réponse
            response_data = {
                **result,
                "new_booking_details": display_data["display_data"],
                "duplication_summary": {
                    "user": f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    "source_booking": result['source_booking_number'],
                    "new_booking": result['new_booking_number'],
                    "booking_type": result['booking_type'],
                    "total_cost": result['total_cost'],
                    "estimates_created": result['estimates_created']
                }
            }
            
            return create_response(
                status_type="success",
                message="Booking dupliqué avec succès",
                data=response_data,
                http_status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return create_response(status_type="error", message=str(e), http_status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return create_response(
                status_type="error", 
                message=f"Erreur lors de la duplication: {str(e)}", 
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )