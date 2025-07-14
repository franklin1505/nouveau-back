# courses/Reservations/Reservations_details/helpers.py

from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from courses.Reservations.helpers import apply_commission_or_compensation, create_response, format_booking_data
from courses.models import Booking, BookingSegment, Estimate, EstimateAttribute, EstimationLog, Passenger
from parametrages.models import APIKey
from courses.Estimations.helpers import calculate_distances_and_durations

# ============== SERVICES CENTRALISÉS ==============

class ValidationService:
    """Service centralisé pour toutes les validations"""
    
    @staticmethod
    def validate_params_for_statistics(request):
        # Validation centralisée pour toutes les vues statistiques
        from .serializers import RecurringSearchParamsSerializer
        
        params_serializer = RecurringSearchParamsSerializer(data=request.query_params)
        if not params_serializer.is_valid():
            return False, create_response(
                status_type="error",
                message="Paramètres invalides",
                data=params_serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST
            ), None
        
        return True, None, params_serializer.validated_data
    
    @staticmethod
    def validate_booking_exists(booking_id):
        # Validation centralisée d'existence booking
        if not booking_id:
            return False, create_response(
                status_type="error",
                message="ID de réservation manquant",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            int(booking_id)
            return True, None
        except (ValueError, TypeError):
            return False, create_response(
                status_type="error",
                message="ID de réservation invalide",
                http_status=status.HTTP_400_BAD_REQUEST
            )
    
    @staticmethod
    def validate_segment_update_data(request_data, allowed_fields):
        # Validation centralisée pour mise à jour segments
        update_data = {
            field: value for field, value in request_data.items() 
            if field in allowed_fields
        }
        
        if not update_data:
            return False, create_response(
                status_type="error",
                message="Aucune donnée valide à mettre à jour",
                http_status=status.HTTP_400_BAD_REQUEST
            ), None
        
        return True, None, update_data
    
    @staticmethod
    def validate_compensation_commission(compensation, commission):
        # Validation métier compensation/commission
        if compensation > 0 and commission > 0:
            return False, create_response(
                status_type="error",
                message="Vous ne pouvez pas définir à la fois compensation et commission",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        return True, None

    @staticmethod
    def validate_booking_for_return_trip(booking_id):
        # Valide qu'un booking peut être transformé en aller-retour
        try:
            booking = Booking.objects.get(id=booking_id)
            
            if booking.booking_type == 'round_trip':
                raise ValueError("Ce booking est déjà un aller-retour")
            if not booking.estimate:
                raise ValueError("Booking sans estimation associée")
            if not booking.estimate.estimation_log:
                raise ValueError("Estimation sans log associé")
            
            return booking, None
            
        except Booking.DoesNotExist:
            return None, f"Booking avec l'ID {booking_id} non trouvé"
        except Exception as e:
            return None, str(e)

    @staticmethod
    def validate_booking_for_duplication(booking_id):
        # Valide qu'un booking peut être dupliqué
        try:
            return Booking.objects.select_related(
                'estimate__estimation_log', 'client', 'assigned_driver', 'assigned_partner'
            ).prefetch_related(
                'estimate__passengers', 'estimate__estimate_attribute__attribute',
                'segments__estimate__estimation_log', 'segments__estimate__passengers',
                'segments__estimate__estimate_attribute__attribute'
            ).get(id=booking_id), None
        except Booking.DoesNotExist:
            return None, f"Booking avec l'ID {booking_id} non trouvé"
        except Exception as e:
            return None, str(e)

class ResponseBuilder:
    """Constructeur centralisé pour toutes les réponses"""
    
    @staticmethod
    def success_response(message, data=None, http_status=status.HTTP_200_OK):
        # Réponse de succès standardisée
        return create_response(
            status_type="success",
            message=message,
            data=data,
            http_status=http_status
        )
    
    @staticmethod
    def error_response(message, data=None, http_status=status.HTTP_400_BAD_REQUEST):
        # Réponse d'erreur standardisée
        return create_response(
            status_type="error",
            message=message,
            data=data,
            http_status=http_status
        )
    
    @staticmethod
    def not_found_response(resource="Ressource"):
        # Réponse 404 standardisée
        return create_response(
            status_type="error",
            message=f"{resource} non trouvée",
            http_status=status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def validation_error_response(errors):
        # Réponse d'erreur de validation standardisée
        return create_response(
            status_type="error",
            message="Données invalides",
            data=errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class FilterContextBuilder:
    """Constructeur centralisé pour le contexte de filtrage"""
    
    @staticmethod
    def build_context(params):
        # Construction complète du contexte de filtrage
        scope = params.get('scope', 'total')
        search_key = params.get('search_key', '')
        
        context = {
            'current_scope': scope,
            'current_search_key': search_key,
            'filter_level': FilterContextBuilder._determine_filter_level(scope, search_key),
            'filter_type': FilterContextBuilder._determine_filter_type(scope, search_key),
            'breadcrumb': FilterContextBuilder._build_breadcrumb(scope, search_key),
            'navigation_hints': FilterContextBuilder._build_navigation_hints(scope, search_key)
        }
        
        return context
    
    @staticmethod
    def _determine_filter_level(scope, search_key):
        # Détermine le niveau de profondeur du filtrage
        if not search_key or search_key == 'total':
            return 1
        
        if search_key.startswith(('recurring_monthly_', 'recurring_custom_')):
            return 3
        elif search_key.startswith('recurring_type_'):
            return 2
        elif search_key.startswith(('recurring_', 'booking_type_', 'status_')):
            return 2
        
        return 1
    
    @staticmethod
    def _determine_filter_type(scope, search_key):
        # Détermine le type de filtrage actif
        if scope == 'recurring' or search_key.startswith('recurring_'):
            return 'recurring'
        elif search_key.startswith('booking_type_'):
            return 'booking_type'
        elif search_key.startswith('status_'):
            return 'status'
        elif scope in ['today', 'past', 'future']:
            return 'temporal'
        elif scope in ['cancelled', 'archived']:
            return 'special'
        
        return 'standard'
    
    @staticmethod
    def _build_breadcrumb(scope, search_key):
        # Construction du breadcrumb de navigation
        breadcrumb = []
        
        if scope and scope != 'total':
            scope_labels = {
                'today': 'Aujourd\'hui',
                'past': 'Passées', 
                'future': 'Futures',
                'cancelled': 'Annulées',
                'recurring': 'Récurrences',
                'archived': 'Archivées'
            }
            breadcrumb.append({
                'label': scope_labels.get(scope, scope.title()),
                'scope': scope,
                'search_key': None
            })
        
        if search_key and search_key != 'total':
            breadcrumb.extend(FilterContextBuilder._build_search_key_breadcrumb(search_key))
        
        return breadcrumb
    
    @staticmethod
    def _build_search_key_breadcrumb(search_key):
        # Construction du breadcrumb pour search_key
        breadcrumb = []
        
        if search_key.startswith('recurring_'):
            if search_key == 'recurring_bookings':
                breadcrumb.append({'label': 'Récurrences', 'search_key': search_key})
            
            elif search_key.startswith('recurring_type_'):
                type_labels = {
                    'daily': 'Quotidienne', 'weekly': 'Hebdomadaire',
                    'monthly': 'Mensuelle', 'yearly': 'Annuelle', 'custom': 'Personnalisée'
                }
                rec_type = search_key.replace('recurring_type_', '')
                breadcrumb.extend([
                    {'label': 'Récurrences', 'search_key': 'recurring_bookings'},
                    {'label': type_labels.get(rec_type, rec_type), 'search_key': search_key}
                ])
            
            elif search_key.startswith('recurring_monthly_'):
                monthly_labels = {'same_date': 'Même date', 'same_position': 'Même position'}
                monthly_type = search_key.replace('recurring_monthly_', '')
                breadcrumb.extend([
                    {'label': 'Récurrences', 'search_key': 'recurring_bookings'},
                    {'label': 'Mensuelle', 'search_key': 'recurring_type_monthly'},
                    {'label': monthly_labels.get(monthly_type, monthly_type), 'search_key': search_key}
                ])
            
            elif search_key.startswith('recurring_custom_'):
                pattern_labels = {
                    'days_of_week': 'Jours semaine', 'interval_based': 'Intervalle fixe',
                    'specific_dates': 'Dates spécifiques'
                }
                pattern_type = search_key.replace('recurring_custom_', '')
                breadcrumb.extend([
                    {'label': 'Récurrences', 'search_key': 'recurring_bookings'},
                    {'label': 'Personnalisée', 'search_key': 'recurring_type_custom'},
                    {'label': pattern_labels.get(pattern_type, pattern_type), 'search_key': search_key}
                ])
        
        elif search_key.startswith('booking_type_'):
            booking_type = search_key.replace('booking_type_', '')
            type_label = "Aller simple" if booking_type == "one_way" else "Aller-retour"
            breadcrumb.append({'label': type_label, 'search_key': search_key})
        
        elif search_key.startswith('status_'):
            status_code = search_key.replace('status_', '')
            status_labels = dict(Booking.STATUS_CHOICES)
            breadcrumb.append({
                'label': status_labels.get(status_code, status_code), 
                'search_key': search_key
            })
        
        return breadcrumb
    
    @staticmethod
    def _build_navigation_hints(scope, search_key):
        # Construction des hints de navigation pour le frontend
        hints = {
            'can_drill_down': False,
            'available_filters': ['billing_status', 'cancellation_status', 'payment_timing'],
            'next_level_available': False
        }
        
        if search_key == 'recurring_type_monthly':
            hints['can_drill_down'] = True
            hints['drill_down_options'] = ['same_date', 'same_position']
        elif search_key == 'recurring_type_custom':
            hints['can_drill_down'] = True
            hints['drill_down_options'] = ['days_of_week', 'interval_based', 'specific_dates']
        
        return hints

class CommunicationHandler:
    """Gestionnaire centralisé pour les communications"""
    
    @staticmethod
    def handle_round_trip_communications(booking_id, validated_data, user):
        # Gestion centralisée des communications aller-retour
        try:
            send_duplication_communications, send_round_trip_communications = get_communication_functions()
            if not send_round_trip_communications:
                return False, ["Service de communication non disponible"]
                
            comm_success, comm_message = send_round_trip_communications(
                booking_id=booking_id,
                return_data=validated_data,
                user=user
            )
            
            details = CommunicationHandler._build_communication_details(
                comm_success, comm_message, booking_id
            )
            
            return comm_success, details
            
        except Exception as e:
            return False, [f"Erreur communication: {str(e)}"]
    
    @staticmethod
    def handle_duplication_communications(new_booking_id, source_booking_id, user):
        # Gestion centralisée des communications duplication
        try:
            send_duplication_communications, send_round_trip_communications = get_communication_functions()
            if not send_duplication_communications:
                return False, ["Service de communication non disponible"]
                
            comm_success, comm_message = send_duplication_communications(
                new_booking_id=new_booking_id,
                source_booking_id=source_booking_id,
                user=user
            )
            
            details = CommunicationHandler._build_communication_details(
                comm_success, comm_message, new_booking_id
            )
            
            return comm_success, details
            
        except Exception as e:
            return False, [f"Erreur communication: {str(e)}"]
    
    @staticmethod
    def _build_communication_details(comm_success, comm_message, booking_id):
        # Construction des détails de communication
        if comm_success:
            try:
                booking = Booking.objects.get(id=booking_id)
                details = ["Email envoyé", "Notification créée"]
                
                if not booking.client:
                    passenger_count = CommunicationHandler._count_passenger_emails(booking)
                    if passenger_count > 0:
                        details.append(f"Passagers notifiés ({passenger_count})")
                    else:
                        details.append("Aucun passager avec email")
                
                return details
                
            except Exception:
                return ["Communications envoyées"]
        else:
            return [f"Erreur: {comm_message}"]
    
    @staticmethod
    def _count_passenger_emails(booking):
        # Compte les passagers avec email selon le type de booking
        if booking.booking_type == 'one_way':
            if booking.estimate:
                return booking.estimate.passengers.exclude(
                    Q(email__isnull=True) | Q(email__exact='')
                ).count()
        else:
            total = 0
            for segment in booking.segments.all():
                if segment.estimate:
                    total += segment.estimate.passengers.exclude(
                        Q(email__isnull=True) | Q(email__exact='')
                    ).count()
            return total
        
        return 0

class ResponseDataBuilder:
    """Constructeur centralisé pour les données de réponse complexes"""
    
    @staticmethod
    def build_transformation_response_data(booking_id, result, validated_data, user, comm_success, comm_details):
        # Construction des données de réponse pour transformation aller-retour
        booking = Booking.objects.get(id=booking_id)
        display_data = format_round_trip_booking_data(booking, include_request_data=False)
        
        return {
            **result,
            "booking_details": display_data["display_data"],
            "transformation_summary": {
                "user": f"{user.first_name} {user.last_name}".strip() or user.username,
                "transformation_type": "simple_to_round_trip",
                "return_departure": validated_data.get('departure'),
                "return_destination": validated_data.get('destination'),
                "return_date": validated_data.get('pickup_date').isoformat() if validated_data.get('pickup_date') else None,
                "return_cost": validated_data.get('total_cost'),
                "logs_created": result.get('logs_created', False),
                "communications_sent": comm_success
            },
            "communication_status": {
                "success": comm_success,
                "details": comm_details
            }
        }
    
    @staticmethod
    def build_duplication_response_data(result, comm_success, comm_details, user):
        # Construction des données de réponse pour duplication
        new_booking = Booking.objects.get(id=result['new_booking_id'])
        display_data = format_duplication_booking_data(new_booking, include_request_data=False)
        
        return {
            **result,
            "new_booking_details": display_data["display_data"],
            "duplication_summary": {
                "user": f"{user.first_name} {user.last_name}".strip() or user.username,
                "source_booking": result['source_booking_number'],
                "new_booking": result['new_booking_number'],
                "booking_type": result['booking_type'],
                "total_cost": result['total_cost'],
                "estimates_created": result['estimates_created']
            },
            "communication_status": {
                "success": comm_success,
                "details": comm_details
            }
        }

# ============== UTILITAIRES DE BASE ==============

def get_query_params(request):
    # Get query parameters compatible with Django and DRF
    if hasattr(request, 'query_params'):
        return request.query_params
    elif hasattr(request, 'GET'):
        return request.GET
    return {}

def extract_booking_filters(request):
    # Extract booking filters from query parameters
    query_params = get_query_params(request)
    return {
        key: query_params.get(key) 
        for key in ['billing_status', 'cancellation_status', 'payment_timing'] 
        if query_params.get(key)
    }

def extract_scope_and_search_key(request):
    # Extract scope and search_key from request
    query_params = get_query_params(request)
    return {
        'scope': query_params.get('scope'),
        'search_key': query_params.get('search_key')
    }

def validate_search_key(search_key):
    # Validate search_key parameter
    return (True, None) if search_key else (False, "Clé de recherche manquante")

def validate_detail_request(request):
    # Validate request parameters for detail view
    params = extract_scope_and_search_key(request)
    is_valid, error_message = validate_search_key(params['search_key'])
    
    if not is_valid:
        return False, create_response(
            status_type="error",
            message=error_message,
            http_status=status.HTTP_400_BAD_REQUEST
        ), None
    
    return True, None, params

def calculate_trip_metrics(departure, destination, waypoints=None, api_key=None):
    # Calcule automatiquement distance et durée pour un trajet
    try:
        if not api_key:
            api_key_obj = APIKey.objects.first()
            if not api_key_obj:
                return {"distance_travelled": 0, "duration_travelled": "0h0min"}
            api_key = api_key_obj.key_value
        
        result = calculate_distances_and_durations(
            api_key, departure, destination, origin=None, waypoints=waypoints
        )
        
        duration_minutes = result["dur_parcourt_minutes"]
        hours = int(duration_minutes // 60)
        minutes = int(duration_minutes % 60)
        duration_formatted = f"{hours}h{minutes:02d}min"
        
        return {
            "distance_travelled": round(result["dist_parcourt_km"], 2),
            "duration_travelled": duration_formatted
        }
        
    except Exception as e:
        print(f"Erreur calcul métriques pour {departure} → {destination}: {e}")
        return {"distance_travelled": 0, "duration_travelled": "0h0min"}

def calculate_attributes_cost(attributes_data):
    # Calcule le coût total des attributs
    from configurations.models import Attribute
    return sum(
        Attribute.objects.get(id=attr['attribute']).unit_price * attr['quantity']
        for attr in attributes_data
        if Attribute.objects.filter(id=attr['attribute']).exists()
    )

def calculate_base_cost(original_estimate):
    # Calcule le coût de base pour le retour
    return max((original_estimate.total_booking_cost or 0) - 
               (original_estimate.total_attributes_cost or 0), 0)

def should_create_separate_estimate(original_estimate, return_data):
    # Détermine s'il faut créer un nouvel estimate ou réutiliser l'existant
    original_log = original_estimate.estimation_log
    
    checks = [
        (return_data.get('departure') != original_log.destination or 
         return_data.get('destination') != original_log.departure),
        (original_log.waypoints or []) != return_data.get('waypoints', []),
        'vehicle_id' in return_data and return_data['vehicle_id'] != original_estimate.user_choice.vehicle_id,
        'payment_method_id' in return_data and return_data['payment_method_id'] != (
            original_estimate.payment_method.id if original_estimate.payment_method else None
        ),
        'passengers' in return_data and return_data['passengers'].get('new'),
        'estimate_attributes' in return_data and return_data['estimate_attributes']
    ]
    
    simple_fields = ['flight_number', 'message', 'number_of_luggages', 'number_of_passengers']
    for field in simple_fields:
        original_value = str(getattr(original_estimate, field, '') or '')
        new_value = str(return_data.get(field, '') or '')
        if original_value != new_value:
            checks.append(True)
    
    return any(checks)

# ============== CONSTRUCTEURS DE RÉPONSES ==============

def build_empty_stats_response(model_class):
    # Build empty sub-stats when no data found
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in model_class.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in model_class.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in model_class.PAYMENT_TIMING_CHOICES}
    }

def build_empty_pagination_response():
    # Build empty pagination when no data found
    return {
        'page': 1, 'page_size': 20, 'total_pages': 0, 'total_count': 0,
        'has_next': False, 'has_previous': False, 'next': None, 'previous': None
    }

def build_global_stats_response(main_stats, serialized_data):
    # Build response for global statistics
    return create_response(
        status_type="success",
        message="Statistiques des réservations récupérées avec succès",
        data=serialized_data
    )

def build_detail_response(serialized_data):
    # Build response for booking detail
    return create_response(
        status_type="success",
        message="Détails de la réservation récupérés avec succès",
        data=serialized_data
    )

def build_update_response(serialized_data):
    # Build response for booking update
    return create_response(
        status_type="success",
        message="Réservation mise à jour avec succès",
        data=serialized_data
    )

def build_empty_detail_response(model_class):
    # Build empty response for detail statistics
    return create_response(
        status_type="success",
        message="Aucune réservation trouvée pour les critères spécifiés",
        data={
            'bookings': [],
            'sub_stats': build_empty_stats_response(model_class),
            'pagination': build_empty_pagination_response()
        }
    )

def build_extended_empty_detail_response(params):
    # Réponse vide étendue optimisée
    scope = params.get('scope', 'total')
    search_key = params.get('search_key', '')
    
    message = "Aucune réservation trouvée"
    if scope == 'recurring':
        message = "Aucune réservation récurrente trouvée"
    elif search_key.startswith('recurring_'):
        message = "Aucune réservation trouvée pour ce type de récurrence"
    
    return ResponseBuilder.success_response(
        message=message,
        data={
            'bookings': [],
            'sub_stats': _get_empty_sub_stats(),
            'pagination': _get_empty_pagination(),
            'filter_context': FilterContextBuilder.build_context(params)
        }
    )

def _get_empty_sub_stats():
    # Sous-stats vides standardisées
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in Booking.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in Booking.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in Booking.PAYMENT_TIMING_CHOICES}
    }

def _get_empty_pagination():
    # Pagination vide standardisée
    return {
        'page': 1, 'page_size': 20, 'total_pages': 0, 'total_count': 0,
        'has_next': False, 'has_previous': False, 'next': None, 'previous': None
    }

# ============== WRAPPERS COMPATIBILITÉ ==============

def validate_booking_detail_request(booking_id):
    # Wrapper pour compatibilité - utilise le service centralisé
    return ValidationService.validate_booking_exists(booking_id)

# ============== SÉRIALISEURS UNIFIÉS ==============

class DataSerializer:
    """Classe unifiée pour la sérialisation de tous les objets"""
    
    @staticmethod
    def serialize_passenger(passenger):
        # Sérialise un passager
        return {
            'id': passenger.id,
            'name': passenger.name,
            'phone_number': passenger.phone_number,
            'email': passenger.email,
            'is_main_client': passenger.is_main_client,
            'created_at': passenger.created_at.isoformat() if passenger.created_at else None
        }

    @staticmethod
    def serialize_estimate_attribute(attr):
        # Sérialise un attribut d'estimation
        return {
            'id': attr.id,
            'attribute_id': attr.attribute.id,
            'attribute_name': getattr(attr.attribute, 'attribute_name', 
                                    getattr(attr.attribute, 'name', 'N/A')),
            'quantity': attr.quantity,
            'unit_price': attr.unit_price,
            'total': attr.total
        }

    @staticmethod
    def serialize_vehicle(user_choice):
        # Sérialise les données du véhicule
        if not user_choice or not user_choice.vehicle_id:
            return None
        
        try:
            from configurations.models import Vehicle
            vehicle = Vehicle.objects.get(id=user_choice.vehicle_id)
            
            vehicle_type_data = None
            if vehicle.vehicle_type:
                vehicle_type_data = {
                    'id': vehicle.vehicle_type.id,
                    'name': vehicle.vehicle_type.name,
                    'description': getattr(vehicle.vehicle_type, 'description', '')
                }
            
            return {
                'id': vehicle.id,
                'brand': vehicle.brand,
                'model': vehicle.model,
                'vehicle_type': vehicle_type_data,
                'passenger_capacity': getattr(vehicle, 'passenger_capacity', None),
                'luggage_capacity': getattr(vehicle, 'luggage_capacity', None),
                'fuel_type': getattr(vehicle, 'fuel_type', None),
                'is_standard_cost': user_choice.is_standard_cost
            }
        except Exception as e:
            return {'id': user_choice.vehicle_id, 'error': str(e)}

    @staticmethod
    def serialize_payment_method(payment_method):
        # Sérialise la méthode de paiement
        if not payment_method:
            return None
        
        return {
            'id': payment_method.id,
            'name': payment_method.name,
            'description': getattr(payment_method, 'description', ''),
            'is_active': getattr(payment_method, 'is_active', True)
        }

    @staticmethod
    def serialize_meeting_place(meeting_place):
        # Sérialise le lieu de rendez-vous
        if not meeting_place:
            return None
        
        return {
            'id': meeting_place.id,
            'name': getattr(meeting_place, 'name', 
                          getattr(meeting_place, 'address', 'N/A')),
            'address': getattr(meeting_place, 'address', '')
        }

    @staticmethod
    def serialize_estimation_log(estimation_log):
        # Sérialise un log d'estimation
        return {
            'id': estimation_log.id,
            'departure': estimation_log.departure,
            'destination': estimation_log.destination,
            'pickup_date': estimation_log.pickup_date.isoformat() if estimation_log.pickup_date else None,
            'waypoints': estimation_log.waypoints or [],
            'estimate_type': estimation_log.estimate_type,
            'estimate_type_display': (estimation_log.get_estimate_type_display() 
                                    if hasattr(estimation_log, 'get_estimate_type_display') 
                                    else estimation_log.estimate_type),
            'created_at': estimation_log.created_at.isoformat() if estimation_log.created_at else None,
            'is_booked': estimation_log.is_booked,
            'distance_travelled': estimation_log.distance_travelled,
            'duration_travelled': estimation_log.duration_travelled,
            'user_id': estimation_log.user.id if estimation_log.user else None,
            'user_name': (f"{estimation_log.user.first_name} {estimation_log.user.last_name}".strip() 
                         if estimation_log.user else None)
        }

    @staticmethod
    def serialize_estimate(estimate):
        # Sérialise une estimation complète
        return {
            'id': estimate.id,
            'flight_number': estimate.flight_number,
            'message': estimate.message,
            'total_booking_cost': estimate.total_booking_cost,
            'total_attributes_cost': estimate.total_attributes_cost,
            'number_of_luggages': estimate.number_of_luggages,
            'number_of_passengers': estimate.number_of_passengers,
            'case_number': estimate.case_number,
            'is_payment_pending': estimate.is_payment_pending,
            'created_at': estimate.created_at.isoformat() if estimate.created_at else None,
            'passengers': [DataSerializer.serialize_passenger(p) for p in estimate.passengers.all()],
            'estimate_attribute': [DataSerializer.serialize_estimate_attribute(a) for a in estimate.estimate_attribute.all()],
            'vehicle': DataSerializer.serialize_vehicle(estimate.user_choice),
            'payment_method': DataSerializer.serialize_payment_method(estimate.payment_method),
            'meeting_place': DataSerializer.serialize_meeting_place(estimate.meeting_place),
            'estimation_log': DataSerializer.serialize_estimation_log(estimate.estimation_log)
        }

    @staticmethod
    def serialize_client(client):
        # Sérialise les données du client
        if not client:
            return None
        
        return {
            'id': client.id,
            'first_name': client.first_name,
            'last_name': client.last_name,
            'full_name': client.get_full_name(),
            'email': client.email,
            'phone_number': client.phone_number,
            'client_type': getattr(client, 'client_type', None),
            'client_type_display': (client.get_client_type_display() 
                                  if hasattr(client, 'get_client_type_display') else None),
            'created_at': (client.date_joined.isoformat() 
                          if hasattr(client, 'date_joined') and client.date_joined else None)
        }

    @staticmethod
    def serialize_driver(driver):
        # Sérialise les données du chauffeur
        if not driver:
            return None
        
        return {
            'id': driver.id,
            'first_name': driver.first_name,
            'last_name': driver.last_name,
            'full_name': f"{driver.first_name} {driver.last_name}".strip(),
            'phone_number': driver.phone_number,
            'email': getattr(driver, 'email', None),
            'license_number': getattr(driver, 'license_number', None),
            'is_active': getattr(driver, 'is_active', None)
        }

    @staticmethod
    def serialize_partner(partner):
        # Sérialise les données du partenaire
        if not partner:
            return None
        
        return {
            'id': partner.id,
            'company_name': partner.company_name,
            'contact_email': partner.contact_email,
            'contact_phone': partner.contact_phone,
            'address': getattr(partner, 'address', None),
            'is_active': getattr(partner, 'is_active', None)
        }

    @staticmethod
    def serialize_booking(booking):
        # Sérialise un booking complet
        return {
            'id': booking.id,
            'booking_number': booking.booking_number,
            'booking_type': booking.booking_type,
            'status': booking.status,
            'status_display': booking.get_status_display(),
            'billing_status': booking.billing_status,
            'billing_status_display': booking.get_billing_status_display(),
            'cancellation_status': booking.cancellation_status,
            'cancellation_status_display': booking.get_cancellation_status_display(),
            'payment_timing': booking.payment_timing,
            'payment_timing_display': booking.get_payment_timing_display(),
            'is_archived': booking.is_archived,
            'is_driver_paid': booking.is_driver_paid,
            'is_partner_paid': booking.is_partner_paid,
            'driver_sale_price': booking.driver_sale_price,
            'partner_sale_price': booking.partner_sale_price,
            'compensation': booking.compensation,
            'commission': booking.commission,
            'created_at': booking.created_at.isoformat() if booking.created_at else None,
            'estimate': DataSerializer.serialize_estimate(booking.estimate) if booking.estimate else None,
            'client': DataSerializer.serialize_client(booking.client),
            'assigned_driver': DataSerializer.serialize_driver(booking.assigned_driver),
            'assigned_partner': DataSerializer.serialize_partner(booking.assigned_partner)
        }

# ============== CRÉATEURS D'OBJETS OPTIMISÉS ==============

def create_return_estimation_log(return_data, original_booking):
    # Crée un nouvel EstimationLog pour le retour avec calculs automatiques
    original_log = original_booking.estimate.estimation_log
    
    metrics = calculate_trip_metrics(
        return_data['departure'],
        return_data['destination'], 
        return_data.get('waypoints', [])
    )
    
    return EstimationLog.objects.create(
        departure=return_data['departure'],
        destination=return_data['destination'],
        pickup_date=return_data['pickup_date'],
        waypoints=return_data.get('waypoints', []),
        estimate_type=original_log.estimate_type,
        user=original_log.user,
        is_booked=True,
        distance_travelled=metrics["distance_travelled"],
        duration_travelled=metrics["duration_travelled"]
    )

def create_return_estimate(return_data, original_booking):
    # Crée un nouvel Estimate pour le retour
    from courses.Reservations.helpers import create_and_associate_passengers, process_estimate_attributes
    from configurations.models import Vehicle, PaymentMethod
    from courses.models import UserChoice
    
    return_estimation_log = create_return_estimation_log(return_data, original_booking)
    
    user_choice = original_booking.estimate.user_choice
    if 'vehicle_id' in return_data and return_data['vehicle_id']:
        try:
            Vehicle.objects.get(id=return_data['vehicle_id'])
            user_choice = UserChoice.objects.create(
                vehicle_id=return_data['vehicle_id'],
                is_standard_cost=True
            )
        except Vehicle.DoesNotExist:
            pass
    
    payment_method = original_booking.estimate.payment_method
    if 'payment_method_id' in return_data and return_data['payment_method_id']:
        try:
            payment_method = PaymentMethod.objects.get(id=return_data['payment_method_id'])
        except PaymentMethod.DoesNotExist:
            pass
    
    return_estimate = Estimate.objects.create(
        estimation_log=return_estimation_log,
        user_choice=user_choice,
        meeting_place=original_booking.estimate.meeting_place,
        payment_method=payment_method,
        flight_number=return_data.get('flight_number'),
        message=return_data.get('message', ''),
        total_booking_cost=return_data.get('total_cost', 0),
        total_attributes_cost=return_data.get('total_attributes_cost', 0),
        number_of_luggages=return_data.get('number_of_luggages'),
        number_of_passengers=return_data.get('number_of_passengers'),
        case_number=original_booking.estimate.case_number,
        is_payment_pending=True
    )
    
    if 'passengers' in return_data and return_data['passengers']:
        original_user = original_booking.estimate.estimation_log.user
        passengers_response = create_and_associate_passengers(original_user.id, return_data['passengers'])
        return_estimate.passengers.set(passengers_response['request_data'])
    else:
        return_estimate.passengers.set(original_booking.estimate.passengers.all())
    
    if 'estimate_attributes' in return_data and return_data['estimate_attributes']:
        attributes_result = process_estimate_attributes(return_data['estimate_attributes'])
        return_estimate.estimate_attribute.set(attributes_result['request_data']['ids'])
        
        calculated_cost = attributes_result['total_attributes_cost']
        if calculated_cost != return_data.get('total_attributes_cost', 0):
            return_estimate.total_attributes_cost = calculated_cost
            return_estimate.save()
    
    return return_estimate

class EstimateCreator:
    """Créateur unifié pour les estimates de duplication avec calculs automatiques"""
    
    @staticmethod
    def create_estimation_log(template_data, modifications, source_user):
        # Crée juste un EstimationLog, pas de tariff
        departure = modifications.get('departure', template_data['departure'])
        destination = modifications.get('destination', template_data['destination'])
        waypoints = modifications.get('waypoints', template_data.get('waypoints', []))
        
        metrics = calculate_trip_metrics(departure, destination, waypoints)
        
        return EstimationLog.objects.create(
            departure=departure,
            destination=destination,
            pickup_date=modifications.get('pickup_date', template_data['pickup_date']),
            waypoints=waypoints,
            estimate_type=template_data.get('estimate_type', 'simple_transfer'),
            user=source_user,
            is_booked=True,
            distance_travelled=metrics["distance_travelled"],
            duration_travelled=metrics["duration_travelled"]
        )
    
    @staticmethod
    def create_user_choice(modifications, template_data, source_estimate):
        # Crée un UserChoice avec validation du véhicule
        from configurations.models import Vehicle
        from courses.models import UserChoice
        
        vehicle_id = modifications.get('vehicle_id', template_data.get('vehicle_id'))
        if vehicle_id and not Vehicle.objects.filter(id=vehicle_id).exists():
            vehicle_id = source_estimate.user_choice.vehicle_id if source_estimate.user_choice else None
        
        return UserChoice.objects.create(vehicle_id=vehicle_id, is_standard_cost=True)
    
    @staticmethod
    def get_payment_method(modifications, template_data, source_estimate):
        # Récupère la méthode de paiement
        from configurations.models import PaymentMethod
        
        payment_method_id = modifications.get('payment_method_id', template_data.get('payment_method_id'))
        if payment_method_id:
            try:
                return PaymentMethod.objects.get(id=payment_method_id)
            except PaymentMethod.DoesNotExist:
                pass
        return source_estimate.payment_method
    
    @staticmethod
    def get_meeting_place(template_data, source_estimate):
        # Récupère le lieu de rendez-vous
        from configurations.models import MeetingPlace
        
        if template_data.get('meeting_place_id'):
            try:
                return MeetingPlace.objects.get(id=template_data['meeting_place_id'])
            except MeetingPlace.DoesNotExist:
                pass
        return source_estimate.meeting_place
    
    @staticmethod
    def create_estimate_with_relations(template_data, modifications, source_estimate):
        # Crée un estimate sans EstimationTariff
        creator = EstimateCreator()
        
        estimation_log = creator.create_estimation_log(template_data, modifications, source_estimate.estimation_log.user)
        user_choice = creator.create_user_choice(modifications, template_data, source_estimate)
        payment_method = creator.get_payment_method(modifications, template_data, source_estimate)
        meeting_place = creator.get_meeting_place(template_data, source_estimate)
        
        base_cost = float(modifications.get('total_booking_cost', template_data.get('total_booking_cost', 0)))
        attributes_cost = float(calculate_attributes_cost(modifications.get('estimate_attributes', [])))
        total_cost = base_cost + attributes_cost
        
        estimate = Estimate.objects.create(
            estimation_log=estimation_log,
            user_choice=user_choice,
            meeting_place=meeting_place,
            payment_method=payment_method,
            flight_number=modifications.get('flight_number', template_data.get('flight_number', '')),
            message=modifications.get('message', template_data.get('message', '')),
            total_booking_cost=total_cost,
            total_attributes_cost=attributes_cost,
            number_of_luggages=modifications.get('number_of_luggages', template_data.get('number_of_luggages')),
            number_of_passengers=modifications.get('number_of_passengers', template_data.get('number_of_passengers')),
            case_number=modifications.get('case_number', template_data.get('case_number')),
            is_payment_pending=True
        )
        
        creator.create_passengers(estimate, modifications.get('passengers', {}), modifications.get('client_id'))
        creator.create_attributes(estimate, modifications.get('estimate_attributes', []))
        
        return estimate
    
    @staticmethod
    def create_passengers(estimate, passengers_data, client_id):
        # Crée et associe les passagers selon la structure existing/new
        if not passengers_data:
            return
        
        existing_ids = passengers_data.get('existing', [])
        for passenger_id in existing_ids:
            try:
                passenger = Passenger.objects.get(id=passenger_id)
                estimate.passengers.add(passenger)
            except Passenger.DoesNotExist:
                continue
        
        new_passengers = passengers_data.get('new', [])
        for passenger_data in new_passengers:
            try:
                email = passenger_data.get('email', '').strip()
                if not email:
                    email = None
                
                passenger = Passenger.objects.create(
                    name=passenger_data['name'],
                    phone_number=passenger_data['phone_number'],
                    email=email,
                    is_main_client=passenger_data.get('is_main_client', False),
                    client_id=client_id
                )
                estimate.passengers.add(passenger)
                
            except Exception:
                continue
    
    @staticmethod
    def create_attributes(estimate, attributes_data):
        # Crée et associe les attributs
        from configurations.models import Attribute
        
        for attr_data in attributes_data:
            try:
                attribute = Attribute.objects.get(id=attr_data['attribute'])
                estimate_attr = EstimateAttribute.objects.create(
                    attribute=attribute,
                    quantity=attr_data['quantity']
                )
                estimate.estimate_attribute.add(estimate_attr)
            except Attribute.DoesNotExist:
                continue

class BookingTemplateExtractor:
    """Extracteur unifié pour les templates de duplication"""
    
    @staticmethod
    def extract_estimate_base_data(estimate, suggested_date):
        # Extrait les données de base d'un estimate avec calculs automatiques
        estimation_log = estimate.estimation_log
        
        metrics = calculate_trip_metrics(
            estimation_log.departure,
            estimation_log.destination,
            estimation_log.waypoints or []
        )
        
        return {
            'pickup_date': suggested_date.isoformat(),
            'departure': estimation_log.departure,
            'destination': estimation_log.destination,
            'waypoints': estimation_log.waypoints or [],
            'distance_travelled': metrics["distance_travelled"],
            'duration_travelled': metrics["duration_travelled"],
            'estimate_type': estimation_log.estimate_type,
            'vehicle_id': estimate.user_choice.vehicle_id if estimate.user_choice else None,
            'payment_method_id': estimate.payment_method.id if estimate.payment_method else None,
            'meeting_place_id': estimate.meeting_place.id if estimate.meeting_place else None,
            'base_cost': calculate_base_cost(estimate),
            'flight_number': estimate.flight_number or '',
            'number_of_passengers': estimate.number_of_passengers,
            'number_of_luggages': estimate.number_of_luggages,
            'case_number': estimate.case_number
        }
    
    @staticmethod
    def extract_booking_base_data(booking):
        # Extrait les données de base d'un booking avec structure passagers
        return {
            'compensation': booking.compensation or 0,
            'commission': booking.commission or 0,
            'assigned_driver_id': None,
            'assigned_partner_id': None,
            'passengers': {'existing': [], 'new': []},
            'estimate_attributes': [],
            'message': ''
        }
    
    @staticmethod
    def get_suggested_date(pickup_date, days_offset=1):
        # Calcule une date suggérée
        from datetime import timedelta
        return pickup_date + timedelta(days=days_offset)

class BookingDuplicator:
    """Duplicateur unifié pour tous types de booking"""
    
    @staticmethod
    def create_booking_base(booking_type, client_id, source_booking):
        # Crée les données de base d'un booking
        return {
            'booking_type': booking_type,
            'client_id': client_id,
            'status': 'pending',
            'billing_status': 'not_invoiced',
            'cancellation_status': 'not_cancelled',
            'payment_timing': source_booking.payment_timing
        }
    
    @staticmethod
    def apply_pricing(total_cost, compensation=0, commission=0):
        # Applique le pricing de façon unifiée
        return apply_commission_or_compensation(total_cost, compensation, commission)
    
    @staticmethod
    def duplicate_one_way(source_booking, modifications, user):
        # Duplique un booking one_way avec calculs automatiques
        template_data = extract_booking_template_data(source_booking)
        new_estimate = EstimateCreator.create_estimate_with_relations(template_data, modifications, source_booking.estimate)
        
        pricing = BookingDuplicator.apply_pricing(
            new_estimate.total_booking_cost,
            modifications.get('compensation', 0),
            modifications.get('commission', 0)
        )
        
        booking_data = BookingDuplicator.create_booking_base('one_way', modifications['client_id'], source_booking)
        booking_data.update({
            'estimate': new_estimate,
            'assigned_driver_id': modifications.get('assigned_driver_id'),
            'assigned_partner_id': modifications.get('assigned_partner_id'),
            **pricing
        })
        
        new_booking = Booking.objects.create(**booking_data)
        BookingDuplicator.create_log(new_booking, source_booking, user, modifications)
        
        return new_booking, 1
    
    @staticmethod
    def duplicate_round_trip(source_booking, modifications, user):
        # Duplique un booking round_trip avec calculs automatiques
        shared_mods = modifications.get('shared_modifications', {})
        outbound_mods = {**shared_mods, **modifications.get('outbound_modifications', {}), 'client_id': modifications['client_id']}
        return_mods = {**shared_mods, **modifications.get('return_modifications', {}), 'client_id': modifications['client_id']}
        
        template = extract_booking_template_data(source_booking)
        outbound_estimate = EstimateCreator.create_estimate_with_relations(
            template['outbound_segment'], outbound_mods, source_booking.outbound_segment.estimate
        )
        
        if should_create_separate_estimate(outbound_estimate, return_mods):
            return_estimate = EstimateCreator.create_estimate_with_relations(
                template['return_segment'], return_mods, source_booking.return_segment.estimate
            )
            estimates_created = 2
        else:
            return_estimate = outbound_estimate
            estimates_created = 1
        
        booking_data = BookingDuplicator.create_booking_base('round_trip', modifications['client_id'], source_booking)
        booking_data.update({
            'estimate': None,
            'assigned_driver_id': shared_mods.get('assigned_driver_id'),
            'assigned_partner_id': shared_mods.get('assigned_partner_id')
        })
        
        new_booking = Booking.objects.create(**booking_data)
        
        BookingDuplicator.create_segment(new_booking, 'outbound', outbound_estimate, outbound_mods, 1)
        BookingDuplicator.create_segment(new_booking, 'return', return_estimate, return_mods, 2)
        
        new_booking.driver_sale_price = new_booking.effective_driver_sale_price
        new_booking.partner_sale_price = new_booking.effective_partner_sale_price
        new_booking.save(update_fields=['driver_sale_price', 'partner_sale_price'])
        
        BookingDuplicator.create_log(new_booking, source_booking, user, modifications)
        
        return new_booking, estimates_created
    
    @staticmethod
    def create_segment(booking, segment_type, estimate, modifications, order):
        # Crée un segment de booking
        pricing = BookingDuplicator.apply_pricing(
            estimate.total_booking_cost,
            modifications.get('compensation', 0),
            modifications.get('commission', 0)
        )
        
        BookingSegment.objects.create(
            booking=booking,
            segment_type=segment_type,
            estimate=estimate,
            status='pending',
            segment_cost=estimate.total_booking_cost,
            compensation=pricing['compensation'],
            commission=pricing['commission'],
            order=order
        )
    
    @staticmethod
    def create_log(new_booking, source_booking, user, modifications):
        # Crée le log de duplication de façon unifiée
        if not user:
            return
        
        try:
            from courses.models import BookingLog
            from utilisateurs.models import Client
            
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            client_name = Client.objects.get(id=modifications['client_id']).get_full_name()
            
            if new_booking.booking_type == 'one_way':
                departure = new_booking.estimate.estimation_log.departure
                destination = new_booking.estimate.estimation_log.destination
                total_cost = new_booking.estimate.total_booking_cost
            else:
                outbound = new_booking.outbound_segment
                departure = outbound.departure if outbound else "N/A"
                destination = outbound.destination if outbound else "N/A"
                total_cost = new_booking.total_cost_calculated
            
            message = (
                f"Booking {new_booking.booking_number} créé par duplication de "
                f"{source_booking.booking_number} par {user_display}. "
                f"Client: {client_name}. Trajet: {shorten_address(departure)} → "
                f"{shorten_address(destination)} ({total_cost}€)"
            )
            
            BookingLog.objects.create(booking=new_booking, user=user, action=message)
            
        except Exception as e:
            print(f"❌ Erreur log duplication: {e}")

# ============== FONCTIONS PRINCIPALES ==============

def generate_return_preview(booking_id):
    # Génère un aperçu complet du trajet retour
    booking, error = ValidationService.validate_booking_for_return_trip(booking_id)
    if error:
        raise ValueError(error)
    
    original_estimate = booking.estimate
    original_log = original_estimate.estimation_log
    base_cost = calculate_base_cost(original_estimate)
    
    original_booking_summary = {
        'id': booking.id,
        'booking_number': booking.booking_number,
        'booking_type': booking.booking_type,
        'status': booking.status,
        'created_at': booking.created_at.isoformat() if booking.created_at else None,
        'departure': original_log.departure,
        'destination': original_log.destination,
        'pickup_date': original_log.pickup_date.isoformat() if original_log.pickup_date else None,
        'total_cost': original_estimate.total_booking_cost or 0,
        'flight_number': original_estimate.flight_number,
        'number_of_passengers': original_estimate.number_of_passengers,
        'number_of_luggages': original_estimate.number_of_luggages
    }
    
    return_trip_data = {
        'departure': original_log.destination,
        'destination': original_log.departure,
        'pickup_date': timezone.now().isoformat(),
        'estimated_cost': base_cost,
        'flight_number': original_estimate.flight_number or '',
        'message': '',
        'number_of_passengers': original_estimate.number_of_passengers,
        'number_of_luggages': original_estimate.number_of_luggages,
        'waypoints': [],
        'compensation': 0,
        'commission': 0,
        'status': 'pending'
    }
    
    shared_data = {
        'client': DataSerializer.serialize_client(booking.client),
        'vehicle': DataSerializer.serialize_vehicle(original_estimate.user_choice),
        'payment_method': DataSerializer.serialize_payment_method(original_estimate.payment_method),
        'meeting_place': DataSerializer.serialize_meeting_place(original_estimate.meeting_place),
        'passengers': [DataSerializer.serialize_passenger(p) for p in original_estimate.passengers.all()],
        'estimate_attributes': [DataSerializer.serialize_estimate_attribute(a) for a in original_estimate.estimate_attribute.all()],
        'assigned_driver': DataSerializer.serialize_driver(booking.assigned_driver),
        'assigned_partner': DataSerializer.serialize_partner(booking.assigned_partner)
    }
    
    cost_breakdown = {
        'original_total_cost': original_estimate.total_booking_cost or 0,
        'original_attributes_cost': original_estimate.total_attributes_cost or 0,
        'calculated_base_cost': base_cost,
        'return_estimated_cost': base_cost
    }
    
    return {
        'eligible': True,
        'outbound_trip': original_booking_summary,
        'return_trip': return_trip_data,
        'shared_data': shared_data,
        'cost_breakdown': cost_breakdown,
        'transformation_options': {
            'can_modify_vehicle': True,
            'can_modify_payment_method': True,
            'can_modify_passengers': True,
            'can_modify_attributes': True,
            'can_add_waypoints': True,
            'can_modify_pricing': True,
            'can_modify_schedule': True
        }
    }

def convert_booking_to_round_trip(booking_id, return_data, user=None):
    # Transforme un booking simple en aller-retour
    with transaction.atomic():
        booking, error = ValidationService.validate_booking_for_return_trip(booking_id)
        if error:
            raise ValueError(error)
        
        original_estimate = booking.estimate
        if not original_estimate:
            raise ValueError("Aucune estimation associée au booking")
        
        booking._skip_change_tracking = True
        
        logs_created = False
        if user:
            try:
                user_display = f"{user.first_name} {user.last_name}".strip() or user.username
                departure_short = shorten_address(return_data.get('departure', ''))
                destination_short = shorten_address(return_data.get('destination', ''))
                
                pickup_date = return_data.get('pickup_date')
                if pickup_date:
                    date_short = format_date_business(pickup_date)
                else:
                    date_short = "Date non définie"
                
                base_message = (
                    f"Réservation {booking.booking_number} transformée en aller-retour par {user_display}. "
                    f"Retour: {departure_short} → {destination_short} le {date_short} ({return_data.get('total_cost', 0)}€)"
                )
                
                additions = []
                
                if 'passengers' in return_data and return_data['passengers'].get('new'):
                    new_count = len(return_data['passengers']['new'])
                    additions.append(f"+{new_count} nouveaux passagers")
                
                if 'vehicle_id' in return_data:
                    try:
                        from configurations.models import Vehicle
                        vehicle = Vehicle.objects.get(id=return_data['vehicle_id'])
                        additions.append(f"véhicule {vehicle.brand} {vehicle.model}")
                    except:
                        additions.append("véhicule modifié")
                
                if return_data.get('commission', 0) > 0:
                    additions.append(f"commission {return_data['commission']}%")
                elif return_data.get('compensation', 0) > 0:
                    additions.append(f"compensation {return_data['compensation']}€")
                
                final_message = f"{base_message}. {', '.join(additions)}." if additions else f"{base_message}."
                
                from courses.models import BookingLog
                
                BookingLog.objects.create(
                    booking=booking,
                    user=user,
                    action=final_message
                )
                logs_created = True
                
            except Exception as log_error:
                logs_created = False
        
        original_estimate.estimation_log.is_booked = True
        original_estimate.estimation_log.save()
        
        outbound_segment = BookingSegment.objects.create(
            booking=booking, segment_type='outbound', estimate=original_estimate,
            status=booking.status, segment_cost=original_estimate.total_booking_cost or 0,
            compensation=booking.compensation or 0, commission=booking.commission or 0, order=1
        )
        
        if should_create_separate_estimate(original_estimate, return_data):
            return_estimate = create_return_estimate(return_data, booking)
            estimates_created = 1
        else:
            return_estimate = original_estimate
            estimates_created = 0
        
        return_segment = BookingSegment.objects.create(
            booking=booking, segment_type='return', estimate=return_estimate,
            status='pending', segment_cost=return_data.get('total_cost', 0),
            compensation=return_data.get('compensation', 0), 
            commission=return_data.get('commission', 0), order=2
        )
        
        booking.booking_type = 'round_trip'
        booking.estimate = None
        booking.driver_sale_price = booking.effective_driver_sale_price
        booking.partner_sale_price = booking.effective_partner_sale_price
        booking.save(update_fields=['booking_type', 'estimate', 'driver_sale_price', 'partner_sale_price'])
        
        return {
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'segments_created': 2,
            'estimates_created': estimates_created,
            'outbound_segment_id': outbound_segment.id,
            'return_segment_id': return_segment.id,
            'return_estimate_id': return_estimate.id,
            'logs_created': logs_created,
            'price_calculation': {
                'old_driver_price': 0,
                'new_driver_price': booking.driver_sale_price,
                'old_partner_price': 0,
                'new_partner_price': booking.partner_sale_price,
                'total_cost_calculated': booking.total_cost_calculated
            }
        }

def extract_booking_template_data(source_booking):
    # Point d'entrée unifié pour extraction de template avec client original
    extractor = BookingTemplateExtractor()
    
    base_data = {
        'booking_type': source_booking.booking_type,
        'client_id': source_booking.client.id if source_booking.client else None,
        **extractor.extract_booking_base_data(source_booking)
    }
    
    if source_booking.booking_type == 'one_way':
        estimate_data = extractor.extract_estimate_base_data(
            source_booking.estimate,
            extractor.get_suggested_date(source_booking.estimate.estimation_log.pickup_date)
        )
        return {**base_data, **estimate_data, 'total_booking_cost': estimate_data['base_cost'], 'total_attributes_cost': 0}
    
    else:
        outbound = source_booking.outbound_segment
        return_seg = source_booking.return_segment
        
        if not outbound or not return_seg:
            raise ValueError("Booking aller-retour incomplet")
        
        outbound_data = extractor.extract_estimate_base_data(
            outbound.estimate,
            extractor.get_suggested_date(outbound.pickup_date)
        )
        return_data = extractor.extract_estimate_base_data(
            return_seg.estimate,
            extractor.get_suggested_date(return_seg.pickup_date)
        )
        
        return {
            **base_data,
            'outbound_segment': {**outbound_data, 'total_cost': outbound_data['base_cost'], 'total_attributes_cost': 0, **base_data},
            'return_segment': {**return_data, 'total_cost': return_data['base_cost'], 'total_attributes_cost': 0, **base_data},
            'shared_data': {
                'vehicle_id': outbound_data['vehicle_id'],
                'payment_method_id': outbound_data['payment_method_id'],
                'meeting_place_id': outbound_data['meeting_place_id'],
                'passengers': [],
                'assigned_driver_id': None,
                'assigned_partner_id': None
            }
        }

def generate_duplicate_preview(booking_id):
    # Génère l'aperçu de duplication
    source_booking, error = ValidationService.validate_booking_for_duplication(booking_id)
    if error:
        raise ValueError(error)
    
    return {
        'eligible': True,
        'duplicate_template': extract_booking_template_data(source_booking),
        'reference_data': {
            'previous_driver': DataSerializer.serialize_driver(source_booking.assigned_driver),
            'previous_partner': DataSerializer.serialize_partner(source_booking.assigned_partner)
        },
        'modification_options': {
            'all_fields_modifiable': True,
            'requires_client_selection': False,
            'attributes_empty_by_default': True,
            'pricing_recalculated_automatically': True
        }
    }

def duplicate_booking_unified(source_booking_id, modifications, user):
    # Point d'entrée unifié optimisé pour la duplication
    source_booking, error = ValidationService.validate_booking_for_duplication(source_booking_id)
    if error:
        raise ValueError(error)
    
    if not modifications.get('client_id'):
        raise ValueError("Client obligatoire pour la duplication")
    
    with transaction.atomic():
        if source_booking.booking_type == 'one_way':
            new_booking, estimates_created = BookingDuplicator.duplicate_one_way(source_booking, modifications, user)
        else:
            new_booking, estimates_created = BookingDuplicator.duplicate_round_trip(source_booking, modifications, user)
        
        return {
            'source_booking_id': source_booking.id,
            'source_booking_number': source_booking.booking_number,
            'new_booking_id': new_booking.id,
            'new_booking_number': new_booking.booking_number,
            'booking_type': new_booking.booking_type,
            'total_cost': getattr(new_booking, 'total_cost_calculated', new_booking.estimate.total_booking_cost),
            'client_id': new_booking.client.id,
            'estimates_created': estimates_created,
            'duplication_successful': True
        }

def format_round_trip_booking_data(booking, include_request_data=True):
    # Formate les données d'un booking aller-retour
    if not booking.is_round_trip:
        return format_booking_data(booking=booking, include_request_data=include_request_data)
    
    display_data = DataSerializer.serialize_booking(booking)
    
    display_data.update({
        'status': booking.effective_status,
        'total_compensation': booking.effective_compensation,
        'total_commission': booking.effective_commission,
        'total_cost': booking.total_cost_calculated
    })
    
    segments_data = []
    for segment in booking.segments.all():
        if segment.estimate:
            segments_data.append({
                'id': segment.id,
                'type': segment.segment_type,
                'departure': segment.departure,
                'destination': segment.destination,
                'pickup_date': segment.pickup_date.isoformat(),
                'status': segment.status,
                'cost': segment.segment_cost,
                'compensation': segment.compensation,
                'commission': segment.commission,
                'estimate': DataSerializer.serialize_estimate(segment.estimate)
            })
    
    display_data['segments'] = segments_data
    
    result = {"display_data": display_data}
    if include_request_data:
        request_data = {k: v for k, v in display_data.items() 
                       if k in ['booking_number', 'billing_status', 'cancellation_status', 'payment_timing']}
        if booking.client:
            request_data["client_id"] = booking.client.id
        result["request_data"] = request_data
    
    return result

def format_duplication_booking_data(booking, include_request_data=True):
    # Formate les données de booking pour la duplication
    if booking.booking_type == 'round_trip':
        return format_round_trip_booking_data(booking, include_request_data)
    
    display_data = {}
    
    display_data.update({
        'id': booking.id,
        'booking_number': booking.booking_number,
        'booking_type': booking.booking_type,
        'status': booking.status,
        'status_display': booking.get_status_display(),
        'created_at': booking.created_at.isoformat() if booking.created_at else None,
        'compensation': booking.compensation or 0,
        'commission': booking.commission or 0,
        'driver_sale_price': booking.driver_sale_price or 0,
        'partner_sale_price': booking.partner_sale_price or 0,
    })

    if booking.client:
        display_data["user"] = {
            "name": booking.client.get_full_name(),
            "email": booking.client.email,
            "first_name": booking.client.first_name,
            "last_name": booking.client.last_name,
            "phone_number": booking.client.phone_number,
            "client_type": booking.client.get_client_type_display() if hasattr(booking.client, 'get_client_type_display') else "Client",
            "user_type": "Client"
        }
    else:
        admin_user = None
        if booking.estimate and booking.estimate.estimation_log:
            admin_user = booking.estimate.estimation_log.user
        
        display_data["user"] = {
            "name": admin_user.get_full_name() if admin_user else "Admin inconnu",
            "email": admin_user.email if admin_user else "",
            "first_name": admin_user.first_name if admin_user else "",
            "last_name": admin_user.last_name if admin_user else "",
            "phone_number": admin_user.phone_number if admin_user else "",
            "client_type": "Réservation Administrateur",
            "user_type": "Administrateur"
        }
    
    if booking.estimate:
        estimate = booking.estimate
        display_data.update({
            'total_booking_cost': estimate.total_booking_cost or 0,
            'total_attributes_cost': estimate.total_attributes_cost or 0,
            'flight_number': estimate.flight_number or '',
            'message': estimate.message or '',
            'number_of_luggages': estimate.number_of_luggages,
            'number_of_passengers': estimate.number_of_passengers,
            'case_number': estimate.case_number,
            'is_payment_pending': estimate.is_payment_pending
        })
        
        total_trajet = (estimate.total_booking_cost or 0) - (estimate.total_attributes_cost or 0)
        display_data['total_trajet'] = max(total_trajet, 0)
        
        if estimate.estimation_log:
            estimation_log = estimate.estimation_log
            display_data["estimation_log"] = {
                "id": estimation_log.id,
                "departure": estimation_log.departure,
                "destination": estimation_log.destination,
                "pickup_date": estimation_log.pickup_date.isoformat() if estimation_log.pickup_date else None,
                "waypoints": estimation_log.waypoints or [],
                "estimate_type": estimation_log.estimate_type,
                "estimate_type_display": estimation_log.get_estimate_type_display() if hasattr(estimation_log, 'get_estimate_type_display') else estimation_log.estimate_type,
                "distance_travelled": estimation_log.distance_travelled,
                "duration_travelled": estimation_log.duration_travelled,
                "is_booked": estimation_log.is_booked,
                "created_at": estimation_log.created_at.isoformat() if estimation_log.created_at else None
            }

        if estimate.passengers.exists():
            display_data["passengers"] = [
                {
                    "id": p.id,
                    "name": p.name,
                    "phone_number": p.phone_number,
                    "email": p.email or "Non renseigné",
                    "is_main_client": p.is_main_client,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in estimate.passengers.all()
            ]
        else:
            display_data["passengers"] = []

        if estimate.estimate_attribute.exists():
            display_data["estimate_attribute"] = [
                {
                    "id": a.id,
                    "attribute_name": a.attribute.attribute_name,
                    "unit_price": float(a.attribute.unit_price),
                    "quantity": a.quantity,
                    "total": float(a.total)
                }
                for a in estimate.estimate_attribute.all()
            ]
        else:
            display_data["estimate_attribute"] = []

        if estimate.user_choice and estimate.user_choice.vehicle_id:
            try:
                from configurations.models import Vehicle
                vehicle = Vehicle.objects.get(id=estimate.user_choice.vehicle_id)
                display_data["vehicle"] = {
                    "id": vehicle.id,
                    "brand": vehicle.brand,
                    "model": vehicle.model,
                    "vehicle_type": vehicle.vehicle_type.name if vehicle.vehicle_type else "Non défini"
                }
            except Vehicle.DoesNotExist:
                display_data["vehicle"] = {
                    "brand": "Véhicule",
                    "model": "non trouvé",
                    "vehicle_type": "Inconnu"
                }
        else:
            display_data["vehicle"] = {
                "brand": "Non",
                "model": "défini",
                "vehicle_type": "Inconnu"
            }

        if estimate.meeting_place:
            try:
                display_data["meeting_place"] = {
                    "name": estimate.meeting_place.name if hasattr(estimate.meeting_place, 'name') else str(estimate.meeting_place),
                    "address": getattr(estimate.meeting_place, 'address', '')
                }
            except:
                display_data["meeting_place"] = "Lieu de rendez-vous défini"
        else:
            display_data["meeting_place"] = "Aucun lieu de rendez-vous spécifié"

        if estimate.payment_method:
            display_data["payment_method"] = {
                "id": estimate.payment_method.id,
                "name": estimate.payment_method.name,
                "description": getattr(estimate.payment_method, 'description', '')
            }
        else:
            display_data["payment_method"] = None

    else:
        display_data.update({
            'total_booking_cost': 0,
            'total_attributes_cost': 0,
            'total_trajet': 0,
            'passengers': [],
            'estimate_attribute': [],
            'estimation_log': {},
            'vehicle': {"brand": "Non", "model": "défini", "vehicle_type": "Inconnu"},
            'meeting_place': "Aucun lieu de rendez-vous spécifié",
            'payment_method': None
        })

    result = {"display_data": display_data}
    if include_request_data:
        request_data = {
            "booking_id": booking.id,
            "client_id": booking.client.id if booking.client else None
        }
        result["request_data"] = request_data
    
    return result

# ============== UTILITAIRES TEXTE ==============

def shorten_address(address):
    # Raccourcit une adresse pour l'affichage
    if not address:
        return "Adresse non définie"
    
    if "," in address:
        parts = address.split(",")
        if len(parts) >= 2:
            main_location = parts[0].strip()
            city = parts[-1].strip().split()[-1] if parts[-1].strip() else ""
            
            if len(main_location) > 35:
                main_location = main_location[:32] + "..."
                
            return f"{main_location}, {city}" if city else main_location
    
    return address[:45] + "..." if len(address) > 45 else address

def format_date_business(date_input):
    # Formate une date en format business français court
    try:
        from datetime import datetime
        
        if isinstance(date_input, datetime):
            dt = date_input
        elif isinstance(date_input, str):
            if 'T' in date_input:
                dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(date_input)
        else:
            dt = datetime.combine(date_input, datetime.min.time()) if hasattr(date_input, 'year') else datetime.now()
        
        months_short = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
                       'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
        
        month_short = months_short[dt.month - 1]
        
        return f"{dt.day} {month_short} {dt.year} à {dt.hour:02d}h{dt.minute:02d}"
    
    except Exception as e:
        return str(date_input)[:10] if date_input else "Date non définie"

def get_booking_creator_info(booking):
    # Retourne les infos sur qui a créé la réservation
    if booking.client is None:
        admin_user = booking.estimate.estimation_log.user if booking.estimate and booking.estimate.estimation_log else None
        return {
            "type": "admin",
            "user": admin_user,
            "name": admin_user.get_full_name() if admin_user else "Admin inconnu"
        }
    else:
        return {
            "type": "client", 
            "user": booking.client,
            "name": booking.client.get_full_name()
        }
        
def create_transformation_log_safe(booking, user, return_data):
    # Version sécurisée pour créer le log de transformation
    try:
        from courses.models import BookingLog
        
        if not user:
            return False
            
        user_display = f"{user.first_name} {user.last_name}".strip() or user.username
        
        departure = str(return_data.get('departure', 'Non défini'))[:50]
        destination = str(return_data.get('destination', 'Non défini'))[:50]
        total_cost = return_data.get('total_cost', 0)
        
        pickup_date = return_data.get('pickup_date')
        if pickup_date:
            try:
                if hasattr(pickup_date, 'strftime'):
                    date_str = pickup_date.strftime("%d/%m/%Y à %H:%M")
                else:
                    date_str = str(pickup_date)[:16]
            except:
                date_str = "Date non définie"
        else:
            date_str = "Date non définie"
        
        message = (
            f"Réservation {booking.booking_number} transformée en aller-retour par {user_display}. "
            f"Retour: {departure} → {destination} le {date_str} ({total_cost}€)."
        )
        
        BookingLog.objects.create(
            booking=booking,
            user=user,
            action=message
        )
        
        return True
        
    except Exception as e:
        return False

# ============== IMPORTS DÉFINIS EN LAZY POUR ÉVITER LES IMPORTS CIRCULAIRES ==============

def get_communication_functions():
    # Import lazy pour éviter l'import circulaire
    try:
        from courses.Reservations.communication_service import (
            send_duplication_communications, 
            send_round_trip_communications
        )
        return send_duplication_communications, send_round_trip_communications
    except ImportError:
        # Fallback si le service n'est pas disponible
        return None, None