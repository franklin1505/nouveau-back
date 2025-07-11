from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from configurations.notification_service import NotificationService
from courses.Reservations.helpers import apply_commission_or_compensation, create_response, format_booking_data
from courses.models import Booking, BookingSegment, Estimate, EstimateAttribute, EstimationLog, Passenger
from utilisateurs.helpers import get_business_info, send_email
from django.template.loader import render_to_string

from utilisateurs.models import Administrator, Business

# ============== UTILITAIRES DE BASE ==============

def get_query_params(request):
    """Get query parameters compatible with Django and DRF"""
    if hasattr(request, 'query_params'):
        return request.query_params
    elif hasattr(request, 'GET'):
        return request.GET
    return {}

def extract_booking_filters(request):
    """Extract booking filters from query parameters"""
    query_params = get_query_params(request)
    return {
        key: query_params.get(key) 
        for key in ['billing_status', 'cancellation_status', 'payment_timing'] 
        if query_params.get(key)
    }

def extract_scope_and_search_key(request):
    """Extract scope and search_key from request"""
    query_params = get_query_params(request)
    return {
        'scope': query_params.get('scope'),
        'search_key': query_params.get('search_key')
    }

# ============== VALIDATIONS ==============

def validate_search_key(search_key):
    """Validate search_key parameter"""
    return (True, None) if search_key else (False, "Clé de recherche manquante")

def validate_booking_id(booking_id):
    """Validate booking ID parameter"""
    if not booking_id:
        return False, "ID de réservation manquant"
    try:
        int(booking_id)
        return True, None
    except (ValueError, TypeError):
        return False, "ID de réservation invalide"

def validate_booking_for_return_trip(booking_id):
    """Valide qu'un booking peut être transformé en aller-retour"""
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

def validate_detail_request(request):
    """Validate request parameters for detail view"""
    params = extract_scope_and_search_key(request)
    is_valid, error_message = validate_search_key(params['search_key'])
    
    if not is_valid:
        return False, create_response(
            status_type="error",
            message=error_message,
            http_status=status.HTTP_400_BAD_REQUEST
        ), None
    
    return True, None, params

def validate_booking_detail_request(booking_id):
    """Validate request parameters for booking detail by ID"""
    is_valid, error_message = validate_booking_id(booking_id)
    
    if not is_valid:
        return False, create_response(
            status_type="error",
            message=error_message,
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    return True, None

# ============== CONSTRUCTEURS DE RÉPONSES ==============

def build_empty_stats_response(model_class):
    """Build empty sub-stats when no data found"""
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in model_class.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in model_class.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in model_class.PAYMENT_TIMING_CHOICES}
    }

def build_empty_pagination_response():
    """Build empty pagination when no data found"""
    return {
        'page': 1, 'page_size': 20, 'total_pages': 0, 'total_count': 0,
        'has_next': False, 'has_previous': False, 'next': None, 'previous': None
    }

def build_global_stats_response(main_stats, serialized_data):
    """Build response for global statistics"""
    return create_response(
        status_type="success",
        message="Statistiques des réservations récupérées avec succès",
        data=serialized_data
    )

def build_detail_response(serialized_data):
    """Build response for booking detail"""
    return create_response(
        status_type="success",
        message="Détails de la réservation récupérés avec succès",
        data=serialized_data
    )

def build_update_response(serialized_data):
    """Build response for booking update"""
    return create_response(
        status_type="success",
        message="Réservation mise à jour avec succès",
        data=serialized_data
    )

def build_empty_detail_response(model_class):
    """Build empty response for detail statistics"""
    return create_response(
        status_type="success",
        message="Aucune réservation trouvée pour les critères spécifiés",
        data={
            'bookings': [],
            'sub_stats': build_empty_stats_response(model_class),
            'pagination': build_empty_pagination_response()
        }
    )

# ============== SÉRIALISEURS UNIFIÉS ==============

class DataSerializer:
    """Classe unifiée pour la sérialisation de tous les objets"""
    
    @staticmethod
    def serialize_passenger(passenger):
        """Sérialise un passager"""
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
        """Sérialise un attribut d'estimation"""
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
        """Sérialise les données du véhicule"""
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
        """Sérialise la méthode de paiement"""
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
        """Sérialise le lieu de rendez-vous"""
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
        """Sérialise un log d'estimation"""
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
        """Sérialise une estimation complète"""
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
        """Sérialise les données du client"""
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
        """Sérialise les données du chauffeur"""
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
        """Sérialise les données du partenaire"""
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
        """Sérialise un booking complet"""
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

# ============== LOGIQUE MÉTIER ==============

def should_create_separate_estimate(original_estimate, return_data):
    """Détermine s'il faut créer un nouvel estimate ou réutiliser l'existant"""
    original_log = original_estimate.estimation_log
    
    # Vérifications simples
    checks = [
        # Trajet inversé
        (return_data.get('departure') != original_log.destination or 
         return_data.get('destination') != original_log.departure),
        
        # Waypoints différents
        (original_log.waypoints or []) != return_data.get('waypoints', []),
        
        # Nouveau véhicule
        'vehicle_id' in return_data and return_data['vehicle_id'] != original_estimate.user_choice.vehicle_id,
        
        # Nouvelle méthode de paiement
        'payment_method_id' in return_data and return_data['payment_method_id'] != (
            original_estimate.payment_method.id if original_estimate.payment_method else None
        ),
        
        # Nouveaux passagers
        'passengers' in return_data and return_data['passengers'].get('new'),
        
        # Nouveaux attributs
        'estimate_attributes' in return_data and return_data['estimate_attributes']
    ]
    
    # Vérification des champs simples
    simple_fields = ['flight_number', 'message', 'number_of_luggages', 'number_of_passengers']
    for field in simple_fields:
        original_value = str(getattr(original_estimate, field, '') or '')
        new_value = str(return_data.get(field, '') or '')
        if original_value != new_value:
            checks.append(True)
    
    return any(checks)

def calculate_base_cost(original_estimate):
    """Calcule le coût de base pour le retour"""
    return max((original_estimate.total_booking_cost or 0) - 
               (original_estimate.total_attributes_cost or 0), 0)

def create_return_estimation_log(return_data, original_booking):
    """Crée un nouvel EstimationLog pour le retour"""
    original_log = original_booking.estimate.estimation_log
    
    return EstimationLog.objects.create(
        departure=return_data['departure'],
        destination=return_data['destination'],
        pickup_date=return_data['pickup_date'],
        waypoints=return_data.get('waypoints', []),
        estimate_type=original_log.estimate_type,
        user=original_log.user,
        is_booked=True,
        distance_travelled=return_data.get('distance_travelled', 0),
        duration_travelled=return_data.get('duration_travelled', '0h0min')
    )

def create_return_estimate(return_data, original_booking):
    """Crée un nouvel Estimate pour le retour"""
    from courses.Reservations.helpers import create_and_associate_passengers, process_estimate_attributes
    from configurations.models import Vehicle, PaymentMethod
    from courses.models import UserChoice
    
    return_estimation_log = create_return_estimation_log(return_data, original_booking)
    
    # Gestion du véhicule
    user_choice = original_booking.estimate.user_choice
    if 'vehicle_id' in return_data and return_data['vehicle_id']:
        try:
            Vehicle.objects.get(id=return_data['vehicle_id'])
            user_choice = UserChoice.objects.create(
                vehicle_id=return_data['vehicle_id'],
                is_standard_cost=True
            )
        except Vehicle.DoesNotExist:
            pass  # Garder l'original
    
    # Gestion de la méthode de paiement
    payment_method = original_booking.estimate.payment_method
    if 'payment_method_id' in return_data and return_data['payment_method_id']:
        try:
            payment_method = PaymentMethod.objects.get(id=return_data['payment_method_id'])
        except PaymentMethod.DoesNotExist:
            pass  # Garder l'original
    
    # Créer l'estimate
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
    
    # Gestion des passagers
    if 'passengers' in return_data and return_data['passengers']:
        original_user = original_booking.estimate.estimation_log.user
        passengers_response = create_and_associate_passengers(original_user.id, return_data['passengers'])
        return_estimate.passengers.set(passengers_response['request_data'])
    else:
        return_estimate.passengers.set(original_booking.estimate.passengers.all())
    
    # Gestion des attributs
    if 'estimate_attributes' in return_data and return_data['estimate_attributes']:
        attributes_result = process_estimate_attributes(return_data['estimate_attributes'])
        return_estimate.estimate_attribute.set(attributes_result['request_data']['ids'])
        
        calculated_cost = attributes_result['total_attributes_cost']
        if calculated_cost != return_data.get('total_attributes_cost', 0):
            return_estimate.total_attributes_cost = calculated_cost
            return_estimate.save()
    
    return return_estimate

# ============== FONCTION PRINCIPALE ==============

def generate_return_preview(booking_id):
    """Génère un aperçu complet du trajet retour - VERSION SANS DUPLICATION"""
    booking, error = validate_booking_for_return_trip(booking_id)
    if error:
        raise ValueError(error)
    
    original_estimate = booking.estimate
    original_log = original_estimate.estimation_log
    base_cost = calculate_base_cost(original_estimate)
    
    # Données du booking original (aller) - version légère
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
    
    # Données du trajet retour (uniquement les différences)
    return_trip_data = {
        'departure': original_log.destination,  # Inversé
        'destination': original_log.departure,  # Inversé
        'pickup_date': timezone.now().isoformat(),  # Date par défaut
        'estimated_cost': base_cost,
        'flight_number': original_estimate.flight_number or '',  # Editable
        'message': '',  # Vide par défaut pour le retour
        'number_of_passengers': original_estimate.number_of_passengers,  # Copié
        'number_of_luggages': original_estimate.number_of_luggages,  # Copié
        'waypoints': [],  # Vide par défaut
        'distance_travelled': original_log.distance_travelled,  # Même distance estimée
        'duration_travelled': original_log.duration_travelled,  # Même durée estimée
        'compensation': 0,  # Par défaut
        'commission': 0,  # Par défaut
        'status': 'pending'  # Statut par défaut du retour
    }
    
    # Données partagées (client, véhicule, etc.) - une seule fois
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
    
    # Calculs et options
    cost_breakdown = {
        'original_total_cost': original_estimate.total_booking_cost or 0,
        'original_attributes_cost': original_estimate.total_attributes_cost or 0,
        'calculated_base_cost': base_cost,
        'return_estimated_cost': base_cost
    }
    
    return {
        'eligible': True,
        'outbound_trip': original_booking_summary,  # Résumé du trajet aller
        'return_trip': return_trip_data,  # Données du trajet retour
        'shared_data': shared_data,  # Données communes (client, véhicule, etc.)
        'cost_breakdown': cost_breakdown,  # Détail des coûts
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

# ============== CONVERSION ALLER-RETOUR ==============

def convert_booking_to_round_trip(booking_id, return_data, user=None):
    """Transforme un booking simple en aller-retour"""
    with transaction.atomic():
        booking, error = validate_booking_for_return_trip(booking_id)
        if error:
            raise ValueError(error)
        
        original_estimate = booking.estimate
        if not original_estimate:
            raise ValueError("Aucune estimation associée au booking")
        
        # 🔥 MARQUER LE BOOKING POUR ÉVITER LE TRACKING AUTOMATIQUE DÈS LE DÉBUT
        booking._skip_change_tracking = True
        
        # ✅ CRÉER LE LOG BUSINESS AVANT TOUTE TRANSFORMATION
        logs_created = False
        if user:
            try:
                user_display = f"{user.first_name} {user.last_name}".strip() or user.username
                departure_short = shorten_address(return_data.get('departure', ''))
                destination_short = shorten_address(return_data.get('destination', ''))
                
                # 🔥 CORRECTION: Gérer le pickup_date correctement
                pickup_date = return_data.get('pickup_date')
                if pickup_date:
                    date_short = format_date_business(pickup_date)
                else:
                    date_short = "Date non définie"
                
                base_message = (
                    f"Réservation {booking.booking_number} transformée en aller-retour par {user_display}. "
                    f"Retour: {departure_short} → {destination_short} le {date_short} ({return_data.get('total_cost', 0)}€)"
                )
                
                # Ajouts conditionnels
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
                
                # ✅ LOG BUSINESS PERSONNALISÉ DIRECTEMENT EN BASE
                from courses.Logs.services import BookingLogService
                from courses.models import BookingLog
                
                # CRÉATION DIRECTE POUR ÉVITER TOUT CONFLIT
                BookingLog.objects.create(
                    booking=booking,
                    user=user,
                    action=final_message
                )
                logs_created = True
                print(f"✅ Log créé avec succès: {final_message}")
                
            except Exception as log_error:
                print(f"❌ Erreur lors du logging de transformation: {log_error}")
                import traceback
                traceback.print_exc()
                logs_created = False
        
        # Marquer l'EstimationLog original comme réservé
        original_estimate.estimation_log.is_booked = True
        original_estimate.estimation_log.save()
        
        # Créer les segments
        outbound_segment = BookingSegment.objects.create(
            booking=booking, segment_type='outbound', estimate=original_estimate,
            status=booking.status, segment_cost=original_estimate.total_booking_cost or 0,
            compensation=booking.compensation or 0, commission=booking.commission or 0, order=1
        )
        
        # Décision sur l'estimate
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
        
        # ✅ TRANSFORMATION DU BOOKING (avec flag déjà défini)
        booking.booking_type = 'round_trip'
        booking.estimate = None
        booking.driver_sale_price = booking.effective_driver_sale_price
        booking.partner_sale_price = booking.effective_partner_sale_price
        booking.save(update_fields=['booking_type', 'estimate', 'driver_sale_price', 'partner_sale_price'])
        
        print(f"✅ Transformation terminée - logs_created: {logs_created}")
        
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
                'old_driver_price': 0,  # Prix original avant transformation
                'new_driver_price': booking.driver_sale_price,
                'old_partner_price': 0,  # Prix original avant transformation  
                'new_partner_price': booking.partner_sale_price,
                'total_cost_calculated': booking.total_cost_calculated
            }
        }

# ============== FORMATAGE ALLER-RETOUR ==============

def format_round_trip_booking_data(booking, include_request_data=True):
    """Formate les données d'un booking aller-retour"""
    if not booking.is_round_trip:
        return format_booking_data(booking=booking, include_request_data=include_request_data)
    
    # Utiliser le sérialiseur unifié
    display_data = DataSerializer.serialize_booking(booking)
    
    # Données spécifiques aller-retour
    display_data.update({
        'status': booking.effective_status,
        'total_compensation': booking.effective_compensation,
        'total_commission': booking.effective_commission,
        'total_cost': booking.total_cost_calculated
    })
    
    # Segments avec données référentielles
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
        # Request data simplifiée
        request_data = {k: v for k, v in display_data.items() 
                       if k in ['booking_number', 'billing_status', 'cancellation_status', 'payment_timing']}
        if booking.client:
            request_data["client_id"] = booking.client.id
        result["request_data"] = request_data
    
    return result

# ============== UTILITAIRES TEXTE ==============

def shorten_address(address):
    """Raccourcit une adresse pour l'affichage"""
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
    """Formate une date en format business français court"""
    try:
        from datetime import datetime
        
        # Si c'est déjà un objet datetime, l'utiliser directement
        if isinstance(date_input, datetime):
            dt = date_input
        elif isinstance(date_input, str):
            # Si c'est une string, la parser
            if 'T' in date_input:
                dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(date_input)
        else:
            # Si c'est un autre type (date), essayer de le convertir
            dt = datetime.combine(date_input, datetime.min.time()) if hasattr(date_input, 'year') else datetime.now()
        
        # Format business court : "11 juil. 2025 à 09h15"
        months_short = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
                       'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
        
        month_short = months_short[dt.month - 1]
        
        return f"{dt.day} {month_short} {dt.year} à {dt.hour:02d}h{dt.minute:02d}"
    
    except Exception as e:
        print(f"Erreur format_date_business: {e}")
        return str(date_input)[:10] if date_input else "Date non définie"


    
def get_round_trip_unified_context(booking_id):
    """Prépare le contexte unifié pour aller-retour"""
    booking = Booking.objects.get(id=booking_id)
    business_info = get_business_info()
    
    # Données formatées du booking aller-retour
    booking_data = format_round_trip_booking_data(booking, include_request_data=False)
    round_trip_details = booking_data["display_data"]
    
    # Informations sur qui a créé la transformation
    booking_creator = get_booking_creator_info(booking)
    
    # URL du PDF (sera mise à jour pour aller-retour si nécessaire)
    pdf_url = f"{business_info['operator_url']}/api/reservations/booking/{booking_id}/pdf/"
    
    # Calculs financiers détaillés
    financial_summary = {
        'outbound_cost': 0,
        'return_cost': 0,
        'total_cost': round_trip_details.get('total_cost', 0),
        'total_compensation': round_trip_details.get('total_compensation', 0),
        'total_commission': round_trip_details.get('total_commission', 0),
        'old_total': 0,
        'price_increase': 0
    }
    
    # Calcul des coûts par segment
    segments = round_trip_details.get('segments', [])
    for segment in segments:
        if segment['type'] == 'outbound':
            financial_summary['outbound_cost'] = segment.get('cost', 0)
            financial_summary['old_total'] = segment.get('cost', 0)
        elif segment['type'] == 'return':
            financial_summary['return_cost'] = segment.get('cost', 0)
    
    financial_summary['price_increase'] = (
        financial_summary['total_cost'] - financial_summary['old_total']
    )
    
    # Context unifié pour tous les templates
    unified_context = {
        "round_trip_details": round_trip_details,
        "business_info": business_info,
        "booking_creator": booking_creator,
        "pdf_url": pdf_url,
        "financial_summary": financial_summary,
        "transformation_type": "simple_to_round_trip",
    }
    
    return unified_context, booking

def send_round_trip_client_email(context, booking):
    """Envoie l'email au client pour transformation aller-retour"""
    if not booking.client or not booking.client.email:
        return
    
    try:
        client_email = booking.client.email
        client_name = booking.client.get_full_name()
        
        # Context spécifique client
        client_context = {
            **context,
            "recipient_name": client_name,
            "recipient_role": "client",
        }
        
        subject = f"Votre réservation {context['round_trip_details']['booking_number']} transformée en aller-retour"
        
        html_content = render_to_string("fichiers_mails/email_round_trip_transformation.html", client_context)
        send_email(client_email, subject, html_content)
        
    except Exception as e:
        print(f"Erreur envoi email client aller-retour: {str(e)}")

def send_round_trip_passenger_emails(context, booking):
    """Envoie les emails aux passagers pour transformation aller-retour"""
    segments = context['round_trip_details'].get("segments", [])
    emails_sent = 0
    
    # Récupérer tous les passagers uniques des deux segments
    all_passengers = {}
    for segment in segments:
        if 'estimate' in segment and 'passengers' in segment['estimate']:
            for passenger in segment['estimate']['passengers']:
                all_passengers[passenger['id']] = passenger
    
    for passenger in all_passengers.values():
        passenger_email = passenger.get("email")
        if not passenger_email or passenger_email == "Non renseigné":
            continue
            
        try:
            # Context spécifique passager
            passenger_context = {
                **context,
                "recipient_name": passenger["name"],
                "recipient_role": "passenger",
                "recipient_is_main": passenger.get("is_main_client", False),
            }
            
            if passenger.get("is_main_client"):
                subject = f"Votre réservation {context['round_trip_details']['booking_number']} transformée en aller-retour"
            else:
                subject = f"Mise à jour - Réservation {context['round_trip_details']['booking_number']} transformée en aller-retour"
            
            html_content = render_to_string("fichiers_mails/email_round_trip_transformation.html", passenger_context)
            send_email(passenger_email, subject, html_content)
            emails_sent += 1
            
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email à {passenger_email}: {str(e)}")
    
    if emails_sent == 0:
        print("Transformation aller-retour : Aucun passager avec email")

def send_round_trip_manager_email(context):
    """Envoie l'email au manager pour transformation aller-retour"""
    try:
        business = Business.objects.filter(business_type="my_business").first()
        manager_email = None
        
        if business:
            if business.main_user:
                if business.main_user.role == "manager" and business.main_user.email:
                    manager_email = business.main_user.email
                elif business.main_user.email:
                    manager_email = business.main_user.email
            
            if not manager_email and business.email:
                manager_email = business.email
        
        if not manager_email:
            manager_admin = Administrator.objects.filter(
                role="manager", 
                email__isnull=False
            ).exclude(email='').first()
            
            if manager_admin:
                manager_email = manager_admin.email
        
        if not manager_email:
            any_admin = Administrator.objects.filter(
                email__isnull=False
            ).exclude(email='').first()
            
            if any_admin:
                manager_email = any_admin.email
        
        if not manager_email:
            return
        
        subject = f"Transformation aller-retour - {context['round_trip_details']['booking_number']}"
        html_content = render_to_string("fichiers_mails/email_round_trip_transformation_admin.html", context)
        send_email(manager_email, subject, html_content)
            
    except Exception as e:
        print(f"Erreur envoi email manager aller-retour: {str(e)}")

def send_round_trip_unified_emails(booking_id):
    """Envoi unifié des emails pour transformation aller-retour"""
    try:
        unified_context, booking = get_round_trip_unified_context(booking_id)
        
        # Email manager (toujours envoyé)
        try:
            send_round_trip_manager_email(unified_context)
        except Exception as manager_error:
            pass  # Ne pas faire échouer tout le processus
        
        # Emails selon le type de réservation
        if booking.client is None:
            # Réservation admin - emails aux passagers
            try:
                send_round_trip_passenger_emails(unified_context, booking)
            except Exception as passenger_error:
                pass
        else:
            # Réservation client - email au client
            try:
                send_round_trip_client_email(unified_context, booking)
            except Exception as client_error:
                pass
        
    except Exception as e:
        print(f"Erreur globale envoi emails aller-retour: {str(e)}")

def send_round_trip_notifications(booking_id):
    """Envoie les notifications pour transformation aller-retour"""
    try:        
        booking = Booking.objects.get(id=booking_id)
        NotificationService.create_round_trip_notification(booking)
        
    except Exception as e:
        print(f"Erreur notifications aller-retour: {e}")

def send_round_trip_emails_with_notifications(booking_id):
    """Point d'entrée principal pour emails + notifications aller-retour"""
    try:
        # 1. Envoi des emails
        send_round_trip_unified_emails(booking_id)
        
        # 2. Envoi des notifications
        send_round_trip_notifications(booking_id)
        
        return True, "Emails et notifications envoyés avec succès"
        
    except Exception as e:
        error_msg = f"Erreur envoi emails/notifications aller-retour: {e}"
        print(error_msg)
        return False, error_msg

def get_booking_creator_info(booking):
    """Retourne les infos sur qui a créé la réservation"""
    if booking.client is None:
        # Réservation admin
        admin_user = booking.estimate.estimation_log.user if booking.estimate and booking.estimate.estimation_log else None
        return {
            "type": "admin",
            "user": admin_user,
            "name": admin_user.get_full_name() if admin_user else "Admin inconnu"
        }
    else:
        # Réservation client
        return {
            "type": "client", 
            "user": booking.client,
            "name": booking.client.get_full_name()
        }
        
def create_transformation_log_safe(booking, user, return_data):
    """Version sécurisée pour créer le log de transformation"""
    try:
        from courses.models import BookingLog
        
        if not user:
            return False
            
        user_display = f"{user.first_name} {user.last_name}".strip() or user.username
        
        # Formatage sécurisé des données
        departure = str(return_data.get('departure', 'Non défini'))[:50]
        destination = str(return_data.get('destination', 'Non défini'))[:50]
        total_cost = return_data.get('total_cost', 0)
        
        # Date formatée de manière sécurisée
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
        
        # Message simple et robuste
        message = (
            f"Réservation {booking.booking_number} transformée en aller-retour par {user_display}. "
            f"Retour: {departure} → {destination} le {date_str} ({total_cost}€)."
        )
        
        # Création directe du log
        BookingLog.objects.create(
            booking=booking,
            user=user,
            action=message
        )
        
        print(f"✅ Log de transformation créé: {message}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur création log transformation: {e}")
        return False



# ============== FONCTIONS UTILITAIRES DE BASE ==============

def validate_booking_for_duplication(booking_id):
    """Valide qu'un booking peut être dupliqué"""
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

def calculate_attributes_cost(attributes_data):
    """Calcule le coût total des attributs"""
    from configurations.models import Attribute
    return sum(
        Attribute.objects.get(id=attr['attribute']).unit_price * attr['quantity']
        for attr in attributes_data
        if Attribute.objects.filter(id=attr['attribute']).exists()
    )

# ============== EXTRACTEURS DE TEMPLATE ==============

class BookingTemplateExtractor:
    """Extracteur unifié pour les templates de duplication"""
    
    @staticmethod
    def extract_estimate_base_data(estimate, suggested_date):
        """Extrait les données de base d'un estimate"""
        estimation_log = estimate.estimation_log
        return {
            'pickup_date': suggested_date.isoformat(),
            'departure': estimation_log.departure,
            'destination': estimation_log.destination,
            'waypoints': estimation_log.waypoints or [],
            'distance_travelled': estimation_log.distance_travelled,
            'duration_travelled': estimation_log.duration_travelled,
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
        """Extrait les données de base d'un booking"""
        return {
            'compensation': booking.compensation or 0,
            'commission': booking.commission or 0,
            'assigned_driver_id': None,
            'assigned_partner_id': None,
            'passengers': [],
            'estimate_attributes': [],
            'message': ''
        }
    
    @staticmethod
    def get_suggested_date(pickup_date, days_offset=1):
        """Calcule une date suggérée"""
        from datetime import timedelta
        return pickup_date + timedelta(days=days_offset)

def extract_booking_template_data(source_booking):
    """Point d'entrée unifié pour extraction de template"""
    extractor = BookingTemplateExtractor()
    
    base_data = {
        'booking_type': source_booking.booking_type,
        'client_id': None,  # Force à choisir
        **extractor.extract_booking_base_data(source_booking)
    }
    
    if source_booking.booking_type == 'one_way':
        estimate_data = extractor.extract_estimate_base_data(
            source_booking.estimate,
            extractor.get_suggested_date(source_booking.estimate.estimation_log.pickup_date)
        )
        return {**base_data, **estimate_data, 'total_booking_cost': estimate_data['base_cost'], 'total_attributes_cost': 0}
    
    else:  # round_trip
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
    """Génère l'aperçu de duplication"""
    source_booking, error = validate_booking_for_duplication(booking_id)
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
            'requires_client_selection': True,
            'attributes_empty_by_default': True,
            'pricing_recalculated_automatically': True
        }
    }

def duplicate_booking_unified(source_booking_id, modifications, user):
    """Point d'entrée unifié optimisé pour la duplication"""
    source_booking, error = validate_booking_for_duplication(source_booking_id)
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
        

# ============== CRÉATEURS D'OBJETS UNIFIÉS ==============

class EstimateCreator:
    """Créateur unifié pour les estimates de duplication"""
    
    @staticmethod
    def create_estimation_log(template_data, modifications, source_user):
        """Crée un EstimationLog"""
        return EstimationLog.objects.create(
            departure=modifications.get('departure', template_data['departure']),
            destination=modifications.get('destination', template_data['destination']),
            pickup_date=modifications.get('pickup_date', template_data['pickup_date']),
            waypoints=modifications.get('waypoints', template_data.get('waypoints', [])),
            estimate_type=template_data.get('estimate_type', 'simple_transfer'),
            user=source_user,
            is_booked=True,
            distance_travelled=modifications.get('distance_travelled', template_data.get('distance_travelled', 0)),
            duration_travelled=modifications.get('duration_travelled', template_data.get('duration_travelled', '0h0min'))
        )
    
    @staticmethod
    def create_user_choice(modifications, template_data, source_estimate):
        """Crée un UserChoice avec validation du véhicule"""
        from configurations.models import Vehicle
        from courses.models import UserChoice
        
        vehicle_id = modifications.get('vehicle_id', template_data.get('vehicle_id'))
        if vehicle_id and not Vehicle.objects.filter(id=vehicle_id).exists():
            vehicle_id = source_estimate.user_choice.vehicle_id if source_estimate.user_choice else None
        
        return UserChoice.objects.create(vehicle_id=vehicle_id, is_standard_cost=True)
    
    @staticmethod
    def get_payment_method(modifications, template_data, source_estimate):
        """Récupère la méthode de paiement"""
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
        """Récupère le lieu de rendez-vous"""
        from configurations.models import MeetingPlace
        
        if template_data.get('meeting_place_id'):
            try:
                return MeetingPlace.objects.get(id=template_data['meeting_place_id'])
            except MeetingPlace.DoesNotExist:
                pass
        return source_estimate.meeting_place
    
    @staticmethod
    def create_estimate_with_relations(template_data, modifications, source_estimate):
        """Crée un estimate complet avec toutes ses relations"""
        creator = EstimateCreator()
        
        # 1. Objets de base
        estimation_log = creator.create_estimation_log(template_data, modifications, source_estimate.estimation_log.user)
        user_choice = creator.create_user_choice(modifications, template_data, source_estimate)
        payment_method = creator.get_payment_method(modifications, template_data, source_estimate)
        meeting_place = creator.get_meeting_place(template_data, source_estimate)
        
        # 2. Calcul des coûts
        base_cost = modifications.get('total_booking_cost', template_data.get('total_booking_cost', 0))
        attributes_cost = calculate_attributes_cost(modifications.get('estimate_attributes', []))
        total_cost = base_cost + attributes_cost
        
        # 3. Créer l'estimate
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
        
        # 4. Relations
        creator.create_passengers(estimate, modifications.get('passengers', []), modifications.get('client_id'))
        creator.create_attributes(estimate, modifications.get('estimate_attributes', []))
        
        return estimate
    
    @staticmethod
    def create_passengers(estimate, passengers_data, client_id):
        """Crée et associe les passagers"""
        for passenger_data in passengers_data:
            passenger = Passenger.objects.create(
                name=passenger_data['name'],
                phone_number=passenger_data['phone_number'],
                email=passenger_data.get('email', ''),
                is_main_client=passenger_data.get('is_main_client', False),
                client_id=client_id
            )
            estimate.passengers.add(passenger)
    
    @staticmethod
    def create_attributes(estimate, attributes_data):
        """Crée et associe les attributs"""
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

# ============== DUPLICATEURS SPÉCIALISÉS ==============

class BookingDuplicator:
    """Duplicateur unifié pour tous types de booking"""
    
    @staticmethod
    def create_booking_base(booking_type, client_id, source_booking):
        """Crée les données de base d'un booking"""
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
        """Applique le pricing de façon unifiée - réutilise la fonction existante"""
        return apply_commission_or_compensation(total_cost, compensation, commission)
    
    @staticmethod
    def duplicate_one_way(source_booking, modifications, user):
        """Duplique un booking one_way"""
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
        """Duplique un booking round_trip"""
        # Préparation des modifications par segment
        shared_mods = modifications.get('shared_modifications', {})
        outbound_mods = {**shared_mods, **modifications.get('outbound_modifications', {}), 'client_id': modifications['client_id']}
        return_mods = {**shared_mods, **modifications.get('return_modifications', {}), 'client_id': modifications['client_id']}
        
        # Création des estimates
        template = extract_booking_template_data(source_booking)
        outbound_estimate = EstimateCreator.create_estimate_with_relations(
            template['outbound_segment'], outbound_mods, source_booking.outbound_segment.estimate
        )
        
        # Décision estimate retour
        if should_create_separate_estimate(outbound_estimate, return_mods):
            return_estimate = EstimateCreator.create_estimate_with_relations(
                template['return_segment'], return_mods, source_booking.return_segment.estimate
            )
            estimates_created = 2
        else:
            return_estimate = outbound_estimate
            estimates_created = 1
        
        # Création du booking
        booking_data = BookingDuplicator.create_booking_base('round_trip', modifications['client_id'], source_booking)
        booking_data.update({
            'estimate': None,
            'assigned_driver_id': shared_mods.get('assigned_driver_id'),
            'assigned_partner_id': shared_mods.get('assigned_partner_id')
        })
        
        new_booking = Booking.objects.create(**booking_data)
        
        # Création des segments
        BookingDuplicator.create_segment(new_booking, 'outbound', outbound_estimate, outbound_mods, 1)
        BookingDuplicator.create_segment(new_booking, 'return', return_estimate, return_mods, 2)
        
        # Mise à jour des prix globaux
        new_booking.driver_sale_price = new_booking.effective_driver_sale_price
        new_booking.partner_sale_price = new_booking.effective_partner_sale_price
        new_booking.save(update_fields=['driver_sale_price', 'partner_sale_price'])
        
        BookingDuplicator.create_log(new_booking, source_booking, user, modifications)
        
        return new_booking, estimates_created
    
    @staticmethod
    def create_segment(booking, segment_type, estimate, modifications, order):
        """Crée un segment de booking"""
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
        """Crée le log de duplication de façon unifiée"""
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
