from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from courses.Reservations.helpers import apply_commission_or_compensation, create_response, format_booking_data
from courses.models import Booking, BookingSegment, Estimate, EstimateAttribute, EstimationLog, Passenger
from parametrages.models import APIKey
from courses.Estimations.helpers import calculate_distances_and_durations

class ValidationService:
    @staticmethod
    def validate_params_for_statistics(request):
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
        if compensation > 0 and commission > 0:
            return False, create_response(
                status_type="error",
                message="Vous ne pouvez pas définir à la fois compensation et commission",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        return True, None

    @staticmethod
    def validate_booking_for_return_trip(booking_id):
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
    @staticmethod
    def success_response(message, data=None, http_status=status.HTTP_200_OK):
        return create_response(
            status_type="success",
            message=message,
            data=data,
            http_status=http_status
        )
    
    @staticmethod
    def error_response(message, data=None, http_status=status.HTTP_400_BAD_REQUEST):
        return create_response(
            status_type="error",
            message=message,
            data=data,
            http_status=http_status
        )
    
    @staticmethod
    def not_found_response(resource="Ressource"):
        return create_response(
            status_type="error",
            message=f"{resource} non trouvée",
            http_status=status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def validation_error_response(errors):
        return create_response(
            status_type="error",
            message="Données invalides",
            data=errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class FilterContextBuilder:
    @staticmethod
    def build_context(params):
        scope = params.get('scope', 'total')
        search_key = params.get('search_key', '')
        
        context = {
            'current_scope': scope,
            'current_search_key': search_key,
            'filter_level': FilterContextBuilder._determine_filter_level(scope, search_key, params),
            'filter_type': FilterContextBuilder._determine_filter_type(scope, search_key),
            'breadcrumb': FilterContextBuilder._build_breadcrumb(scope, search_key, params),
            'navigation_hints': FilterContextBuilder._build_navigation_hints(scope, search_key)
        }
        
        return context
    
    @staticmethod
    def _determine_filter_level(scope, search_key, params):
        # Niveau 3 : filtres finaux appliqués
        level_3_filters = ['billing_status', 'cancellation_status', 'payment_timing']
        if any(params.get(filter_name) for filter_name in level_3_filters):
            return 3
        
        # Niveau 2 : filtres intermédiaires
        level_2_prefixes = ['status_', 'booking_type_', 'recurring_type_', 'recurring_monthly_', 'recurring_custom_']
        if search_key and any(search_key.startswith(prefix) for prefix in level_2_prefixes):
            return 2
        
        # Niveau 1 : scope uniquement
        return 1
    
    @staticmethod
    def _determine_filter_type(scope, search_key):
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
    def _build_breadcrumb(scope, search_key, params):
        breadcrumb = []
        
        # Niveau 1 : Scope
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
        
        # Niveau 2 : Search key
        if search_key and search_key != 'total':
            breadcrumb.extend(FilterContextBuilder._build_search_key_breadcrumb(search_key, scope))
        
        # Niveau 3 : Filtres finaux
        level_3_filters = {
            'billing_status': 'Facturation',
            'cancellation_status': 'Annulation', 
            'payment_timing': 'Paiement'
        }
        
        for filter_name, filter_label in level_3_filters.items():
            filter_value = params.get(filter_name)
            if filter_value:
                breadcrumb.append({
                    'label': f"{filter_label}: {filter_value}",
                    'scope': scope,
                    'search_key': search_key,
                    'filter': {filter_name: filter_value}
                })
        
        return breadcrumb
    
    @staticmethod
    def _build_search_key_breadcrumb(search_key, scope):
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
    @staticmethod
    def handle_round_trip_communications(booking_id, validated_data, user):
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
    @staticmethod
    def build_transformation_response_data(booking_id, result, validated_data, user, comm_success, comm_details):
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

class DataSerializer:
    """Classe unifiée pour la sérialisation de tous les objets"""
    
    @staticmethod
    def serialize_passenger(passenger):
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

def get_query_params(request):
    if hasattr(request, 'query_params'):
        return request.query_params
    elif hasattr(request, 'GET'):
        return request.GET
    return {}

def extract_booking_filters(request):
    query_params = get_query_params(request)
    return {
        key: query_params.get(key) 
        for key in ['billing_status', 'cancellation_status', 'payment_timing'] 
        if query_params.get(key)
    }

def extract_scope_and_search_key(request):
    query_params = get_query_params(request)
    return {
        'scope': query_params.get('scope'),
        'search_key': query_params.get('search_key')
    }

def validate_search_key(search_key):
    return (True, None) if search_key else (False, "Clé de recherche manquante")

def validate_detail_request(request):
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
    from configurations.models import Attribute
    return sum(
        Attribute.objects.get(id=attr['attribute']).unit_price * attr['quantity']
        for attr in attributes_data
        if Attribute.objects.filter(id=attr['attribute']).exists()
    )

def calculate_base_cost(original_estimate):
    return max((original_estimate.total_booking_cost or 0) - 
               (original_estimate.total_attributes_cost or 0), 0)

def should_create_separate_estimate(original_estimate, return_data):
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

def build_empty_stats_response(model_class):
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in model_class.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in model_class.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in model_class.PAYMENT_TIMING_CHOICES}
    }

def build_empty_pagination_response():
    return {
        'page': 1, 'page_size': 12, 'total_pages': 0, 'total_count': 0,
        'has_next': False, 'has_previous': False, 'next': None, 'previous': None
    }

def build_global_stats_response(main_stats, serialized_data):
    return create_response(
        status_type="success",
        message="Statistiques des réservations récupérées avec succès",
        data=serialized_data
    )

def build_detail_response(serialized_data):
    return create_response(
        status_type="success",
        message="Détails de la réservation récupérés avec succès",
        data=serialized_data
    )

def build_update_response(serialized_data):
    return create_response(
        status_type="success",
        message="Réservation mise à jour avec succès",
        data=serialized_data
    )

def build_empty_detail_response(model_class):
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
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in Booking.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in Booking.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in Booking.PAYMENT_TIMING_CHOICES}
    }

def _get_empty_pagination():
    return {
        'page': 1, 'page_size': 12, 'total_pages': 0, 'total_count': 0,
        'has_next': False, 'has_previous': False, 'next': None, 'previous': None
    }

def validate_booking_detail_request(booking_id):
    return ValidationService.validate_booking_exists(booking_id)

def generate_return_preview(booking_id):
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
    
    from courses.Reservations.Reservations_details.helpers import DataSerializer
    
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
                
                from courses.models import BookingLog
                BookingLog.objects.create(
                    booking=booking,
                    user=user,
                    action=base_message
                )
                logs_created = True
                
            except Exception:
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

def create_return_estimation_log(return_data, original_booking):
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

def extract_booking_template_data(source_booking):
    from courses.Reservations.Reservations_details.helpers import BookingTemplateExtractor
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
    source_booking, error = ValidationService.validate_booking_for_duplication(booking_id)
    if error:
        raise ValueError(error)
    
    return {
        'eligible': True,
        'duplicate_template': extract_booking_template_data(source_booking),
        'reference_data': {
            'previous_driver': serialize_driver(source_booking.assigned_driver),
            'previous_partner': serialize_partner(source_booking.assigned_partner)
        },
        'modification_options': {
            'all_fields_modifiable': True,
            'requires_client_selection': False,
            'attributes_empty_by_default': True,
            'pricing_recalculated_automatically': True
        }
    }

def duplicate_booking_unified(source_booking_id, modifications, user):
    from courses.Reservations.Reservations_details.helpers import BookingDuplicator
    
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
    if not booking.is_round_trip:
        return format_booking_data(booking=booking, include_request_data=include_request_data)
    
    from courses.Reservations.Reservations_details.helpers import DataSerializer
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
    if booking.booking_type == 'round_trip':
        return format_round_trip_booking_data(booking, include_request_data)
    
    display_data = {
        'id': booking.id,
        'booking_number': booking.booking_number,
        'booking_type': booking.booking_type,
        'status': booking.status,
        'created_at': booking.created_at.isoformat() if booking.created_at else None,
        'compensation': booking.compensation or 0,
        'commission': booking.commission or 0,
        'driver_sale_price': booking.driver_sale_price or 0,
        'partner_sale_price': booking.partner_sale_price or 0,
    }

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

    result = {"display_data": display_data}
    if include_request_data:
        request_data = {
            "booking_id": booking.id,
            "client_id": booking.client.id if booking.client else None
        }
        result["request_data"] = request_data
    
    return result

def shorten_address(address):
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
    
    except Exception:
        return str(date_input)[:10] if date_input else "Date non définie"

def serialize_driver(driver):
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

def serialize_partner(partner):
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

def create_transformation_log_safe(booking, user, return_data):
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
        
    except Exception:
        return False

def get_communication_functions():
    try:
        from courses.Reservations.communication_service import (
            send_duplication_communications, 
            send_round_trip_communications
        )
        return send_duplication_communications, send_round_trip_communications
    except ImportError:
        return None, None

def format_booking_text(booking_data, user_type, booking):
    booking_type_display = {
        'one_way': 'Aller simple',
        'round_trip': 'Aller-retour'
    }.get(booking_data['booking_type'], booking_data['booking_type'])
    
    client_name = (f"{booking_data['client']['first_name']} {booking_data['client']['last_name']}"
                   if booking_data['client'] else "Non défini")
    
    text = [
        f"Réservation #{booking_data['booking_number']}",
        f"Type: {booking_type_display}",
        f"Statut: {booking_data.get('status_display', booking_data['status'])}",
        f"Client: {client_name}",
        "---",
        "Trajet(s) :"
    ]
    
    segments = booking_data.get('segments', [])
    outbound_segment = next((s for s in segments if s['segment_type'] == 'outbound'), None)
    return_segment = next((s for s in segments if s['segment_type'] == 'return'), None)
    
    def format_segment(segment, segment_label):
        if not segment:
            return []
        estimate = segment.get('estimate', {})
        estimation_log = estimate.get('estimation_log', {})
        vehicle = estimate.get('vehicle', {})
        passengers = estimate.get('passengers', [])
        attributes = estimate.get('estimate_attribute', [])
        
        passenger_names = ", ".join(p['name'] for p in passengers) or "Aucun"
        attribute_list = ", ".join(
            f"{a['name']} (x{a['quantity']})" for a in attributes
        ) or "Aucun"
        
        return [
            f"{segment_label} :",
            f"  Départ: {shorten_address(estimation_log.get('departure', 'N/A'))}",
            f"  Destination: {shorten_address(estimation_log.get('destination', 'N/A'))}",
            f"  Date: {format_date_business(segment.get('pickup_date', 'N/A'))}",
            f"  Points de passage: {', '.join(estimation_log.get('waypoints', []) or ['N/A'])}",
            f"  Type d'estimation: {estimation_log.get('estimate_type', 'N/A')}",
            f"  Distance: {segment.get('distance_travelled', 0)} km",
            f"  Durée: {segment.get('duration_travelled', 'N/A')}",
            f"  Passagers: {len(passengers)} ({passenger_names})",
            f"  Véhicule: {vehicle.get('brand', 'N/A')} {vehicle.get('model', 'N/A')} "
            f"({vehicle.get('vehicle_type', 'N/A')})",
            f"  Numéro de vol: {segment.get('flight_number', 'N/A')}",
            f"  Message: {segment.get('message', 'Aucun')}",
            f"  Attributs: {attribute_list}"
        ]
    
    if booking_data['booking_type'] == 'round_trip' and outbound_segment and return_segment:
        text.extend(format_segment(outbound_segment, "Aller"))
        text.append("")
        text.extend(format_segment(return_segment, "Retour"))
    elif outbound_segment:
        text.extend(format_segment(outbound_segment, "Trajet"))
    
    estimate = booking_data.get('estimate', {})
    payment_method = estimate.get('payment_method', {})
    text.extend([
        "---",
        f"Coût total: {estimate.get('total_booking_cost', 0)}€",
        f"Coût des attributs: {estimate.get('total_attributes_cost', 0)}€",
        f"Nombre de bagages: {estimate.get('number_of_luggages', 'N/A')}",
        f"Nombre de passagers: {estimate.get('number_of_passengers', 0)}",
        f"Numéro de dossier: {estimate.get('case_number', 'N/A')}",
        f"Méthode de paiement: {payment_method.get('name', 'Non défini')}",
        f"Statut de facturation: {booking_data.get('billing_status_display', booking_data.get('billing_status', 'N/A'))}",
        f"Statut d'annulation: {booking_data.get('cancellation_status_display', booking_data.get('cancellation_status', 'N/A'))}",
        f"Paiement: {booking_data.get('payment_timing_display', booking_data.get('payment_timing', 'N/A'))}"
    ])
    
    if booking_data.get('assigned_driver'):
        text.append(
            f"Chauffeur assigné: {booking_data['assigned_driver']['first_name']} "
            f"{booking_data['assigned_driver']['last_name']} "
            f"({booking_data['assigned_driver'].get('email', 'N/A')}, {booking_data['assigned_driver']['phone_number']})"
        )
    
    if booking_data.get('assigned_partner'):
        text.append(
            f"Partenaire assigné: {booking_data['assigned_partner']['company_name']} "
            f"({booking_data['assigned_partner']['contact_email']}, {booking_data['assigned_partner']['contact_phone']})"
        )
    
    if user_type == 'administrator':
        text.extend([
            f"Commission: {booking_data.get('effective_commission', booking_data.get('commission', 0))}%",
            f"Compensation: {booking_data.get('effective_compensation', booking_data.get('compensation', 0))}€",
            f"Prix chauffeur: {booking_data.get('driver_sale_price', 0)}€",
            f"Prix partenaire: {booking_data.get('partner_sale_price', 0)}€"
        ])
    elif user_type == 'partner':
        text.extend([
            f"Commission: {booking_data.get('effective_commission', booking_data.get('commission', 0))}%",
            f"Prix partenaire: {booking_data.get('partner_sale_price', 0)}€"
        ])
    elif user_type == 'driver' and 'driver_sale_price' in booking_data:
        text.append(f"Prix chauffeur: {booking_data['driver_sale_price']}€")
    
    if booking_data.get('recurring_info') and user_type in ['administrator', 'client']:
        rec_info = booking_data['recurring_info']
        rec_type = rec_info.get('recurrence_type_display', 'N/A')
        rec_details = ""
        if rec_info.get('monthly_type'):
            rec_details = rec_info.get('monthly_type_display', '')
        elif rec_info.get('custom_pattern'):
            rec_details = rec_info.get('custom_pattern_display', '')
        text.append(f"Récurrence: {rec_type} ({rec_details})")
    
    text.extend([
        f"Créé le: {format_date_business(booking_data['created_at'])}",
        f"Archivé: {'Oui' if booking_data['is_archived'] else 'Non'}"
    ])
    
    return "\n".join(text)