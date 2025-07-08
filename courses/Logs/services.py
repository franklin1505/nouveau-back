from django.utils import timezone
from django.contrib.auth import get_user_model
from courses.models import Booking, BookingLog
import threading

User = get_user_model()
_thread_local = threading.local()

class BookingLogService:
    @staticmethod
    def set_current_user(user):
        _thread_local.user = user
    
    @staticmethod
    def get_current_user():
        return getattr(_thread_local, 'user', None)
    
    @staticmethod
    def clear_current_user():
        if hasattr(_thread_local, 'user'):
            delattr(_thread_local, 'user')
    
    @staticmethod
    def log_action(booking, action, user=None):
        user = user or BookingLogService.get_current_user()
        BookingLog.objects.create(booking=booking, user=user, action=action)
    
    @staticmethod
    def log_detailed_creation(booking, user=None):
        user = user or BookingLogService.get_current_user()
        creator_info = BookingLogService._get_user_display(user)
        client_info = BookingLogService._get_booking_client_info(booking, user)
        action = f"Réservation créée par {creator_info}{client_info}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_comprehensive_modification(booking, old_values, user=None):
        user = user or BookingLogService.get_current_user()
        user_display = BookingLogService._get_user_display(user)
        changes = []
        
        current_values = {
            'status': booking.status,
            'billing_status': booking.billing_status,
            'cancellation_status': booking.cancellation_status,
            'payment_timing': booking.payment_timing,
            'driver_sale_price': booking.driver_sale_price,
            'partner_sale_price': booking.partner_sale_price,
            'compensation': booking.compensation,
            'commission': booking.commission,
            'assigned_driver': booking.assigned_driver,
            'assigned_partner': booking.assigned_partner,
            'is_archived': booking.is_archived,
            'is_driver_paid': booking.is_driver_paid,
            'is_partner_paid': booking.is_partner_paid,
        }
        
        for field, current_value in current_values.items():
            old_value = old_values.get(field)
            if old_value != current_value:
                change_desc = BookingLogService._format_field_change(field, old_value, current_value)
                if change_desc:
                    changes.append(change_desc)
        
        if booking.estimate:
            changes.extend(BookingLogService._detect_estimate_changes(booking, old_values))
        
        if booking.estimate and booking.estimate.estimation_log:
            changes.extend(BookingLogService._detect_estimation_log_changes(booking, old_values))
        
        if changes:
            action = f"Réservation modifiée par {user_display} : {changes[0]}" if len(changes) == 1 else f"Réservation modifiée par {user_display} : {' • '.join(changes)}"
            BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def _detect_estimate_changes(booking, old_values):
        changes = []
        estimate = booking.estimate
        old_estimate = old_values.get('estimate_snapshot', {})
        estimate_fields = {
            'total_booking_cost': 'coût total',
            'total_attributes_cost': 'coût attributs',
            'flight_number': 'numéro de vol',
            'number_of_luggages': 'nombre de bagages',
            'number_of_passengers': 'nombre de passagers',
            'message': 'message',
            'case_number': 'numéro de dossier',
            'is_payment_pending': 'paiement en attente'
        }
        
        for field, label in estimate_fields.items():
            old_val = old_estimate.get(field)
            new_val = getattr(estimate, field, None)
            if old_val != new_val:
                if field in ['total_booking_cost', 'total_attributes_cost']:
                    changes.append(f"{label} {old_val or 0}€ → {new_val or 0}€")
                elif field == 'is_payment_pending':
                    changes.append("paiement marqué en attente" if new_val else "paiement plus en attente")
                else:
                    changes.append(f"{label} modifié")
        return changes
    
    @staticmethod
    def _detect_estimation_log_changes(booking, old_values):
        changes = []
        estimation_log = booking.estimate.estimation_log
        old_log = old_values.get('estimation_log_snapshot', {})
        log_fields = {
            'departure': 'lieu de départ',
            'destination': 'destination',
            'pickup_date': 'date de prise en charge',
            'distance_travelled': 'distance',
            'duration_travelled': 'durée',
            'estimate_type': 'type d\'estimation'
        }
        
        for field, label in log_fields.items():
            old_val = old_log.get(field)
            new_val = getattr(estimation_log, field, None)
            if old_val != new_val:
                if field == 'pickup_date':
                    old_date = old_val.strftime("%d/%m/%Y %H:%M") if old_val else 'non définie'
                    new_date = new_val.strftime("%d/%m/%Y %H:%M") if new_val else 'non définie'
                    changes.append(f"{label} {old_date} → {new_date}")
                elif field == 'distance_travelled':
                    changes.append(f"{label} {old_val or 0}km → {new_val or 0}km")
                else:
                    changes.append(f"{label} modifié")
        return changes
    
    @staticmethod
    def log_deletion(booking, user=None):
        user = user or BookingLogService.get_current_user()
        user_display = BookingLogService._get_user_display(user)
        action = f"Réservation supprimée par {user_display}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def _format_field_change(field, old_value, new_value):
        if field == 'status':
            status_map = dict(Booking.STATUS_CHOICES)
            old_display = status_map.get(old_value, old_value)
            new_display = status_map.get(new_value, new_value)
            return f"statut '{old_display}' → '{new_display}'"
        elif field == 'billing_status':
            billing_map = dict(Booking.BILLING_STATUS_CHOICES)
            old_display = billing_map.get(old_value, old_value)
            new_display = billing_map.get(new_value, new_value)
            return f"facturation '{old_display}' → '{new_display}'"
        elif field == 'cancellation_status':
            cancel_map = dict(Booking.CANCELLATION_STATUS_CHOICES)
            old_display = cancel_map.get(old_value, old_value)
            new_display = cancel_map.get(new_value, new_value)
            return f"annulation '{old_display}' → '{new_display}'"
        elif field == 'payment_timing':
            timing_map = dict(Booking.PAYMENT_TIMING_CHOICES)
            old_display = timing_map.get(old_value, old_value)
            new_display = timing_map.get(new_value, new_value)
            return f"timing paiement '{old_display}' → '{new_display}'"
        elif field in ['driver_sale_price', 'partner_sale_price', 'compensation', 'commission']:
            field_names = {
                'driver_sale_price': 'prix chauffeur',
                'partner_sale_price': 'prix partenaire',
                'compensation': 'compensation',
                'commission': 'commission'
            }
            return f"{field_names[field]} {old_value or 0}€ → {new_value or 0}€"
        elif field == 'assigned_driver':
            return f"chauffeur assigné : {new_value.first_name} {new_value.last_name}" if new_value else "chauffeur désassigné"
        elif field == 'assigned_partner':
            return f"partenaire assigné : {new_value.company_name}" if new_value else "partenaire désassigné"
        elif field == 'is_driver_paid' and new_value:
            return "paiement chauffeur marqué comme effectué"
        elif field == 'is_partner_paid' and new_value:
            return "paiement partenaire marqué comme effectué"
        elif field == 'is_archived' and new_value:
            return "réservation archivée"
        return None
    
    @staticmethod
    def _get_booking_client_info(booking, creator_user=None):
        if booking.client:
            client_name = f"{booking.client.first_name} {booking.client.last_name}"
            if creator_user and hasattr(creator_user, 'client') and creator_user.client == booking.client:
                return ""
            return f" pour {client_name}"
        if booking.estimate and booking.estimate.passengers.exists():
            main_passenger = booking.estimate.passengers.filter(is_main_client=True).first()
            return f" pour {main_passenger.name}" if main_passenger else f" pour {booking.estimate.passengers.first().name}"
        return " (réservation administrative)"
    
    @staticmethod
    def _get_user_display(user):
        if not user:
            return "Système"
        user_name = user.get_full_name() or user.username
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return f"{user_name} (Admin)"
        elif hasattr(user, 'user_type'):
            user_type_map = {
                'client': 'Client',
                'driver': 'Chauffeur', 
                'admin': 'Admin',
                'administrator': 'Admin',
                'partner': 'Partenaire'
            }
            return f"{user_name} ({user_type_map.get(user.user_type, 'Utilisateur')})"
        return user_name
    
    @staticmethod
    def get_booking_timeline(booking):
        return BookingLog.objects.filter(booking=booking).order_by('timestamp')
    
    @staticmethod
    def get_user_actions(user, limit=50):
        return BookingLog.objects.filter(user=user).order_by('-timestamp')[:limit]

class BookingChangeTracker:
    @staticmethod
    def capture_booking_state(booking):
        try:
            booking = Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute__attribute'
            ).get(pk=booking.pk)
            state = {
                'booking': {
                    'status': booking.status,
                    'billing_status': booking.billing_status,
                    'cancellation_status': booking.cancellation_status,
                    'payment_timing': booking.payment_timing,
                    'driver_sale_price': booking.driver_sale_price,
                    'partner_sale_price': booking.partner_sale_price,
                    'compensation': booking.compensation,
                    'commission': booking.commission,
                    'assigned_driver_id': booking.assigned_driver.id if booking.assigned_driver else None,
                    'assigned_partner_id': booking.assigned_partner.id if booking.assigned_partner else None,
                    'is_archived': booking.is_archived,
                    'is_driver_paid': booking.is_driver_paid,
                    'is_partner_paid': booking.is_partner_paid,
                }
            }
            if booking.estimate:
                state['estimate'] = {
                    'total_booking_cost': booking.estimate.total_booking_cost,
                    'total_attributes_cost': booking.estimate.total_attributes_cost,
                    'flight_number': booking.estimate.flight_number,
                    'number_of_luggages': booking.estimate.number_of_luggages,
                    'number_of_passengers': booking.estimate.number_of_passengers,
                    'message': booking.estimate.message,
                    'case_number': booking.estimate.case_number,
                    'is_payment_pending': booking.estimate.is_payment_pending,
                }
                if booking.estimate.estimation_log:
                    state['estimation_log'] = {
                        'departure': booking.estimate.estimation_log.departure,
                        'destination': booking.estimate.estimation_log.destination,
                        'pickup_date': booking.estimate.estimation_log.pickup_date,
                        'distance_travelled': booking.estimate.estimation_log.distance_travelled,
                        'duration_travelled': booking.estimate.estimation_log.duration_travelled,
                        'estimate_type': booking.estimate.estimation_log.estimate_type,
                    }
                state['passengers'] = [
                    {
                        'id': p.id,
                        'name': p.name,
                        'phone_number': p.phone_number,
                        'email': p.email,
                        'is_main_client': p.is_main_client
                    } for p in booking.estimate.passengers.all()
                ] if booking.estimate.passengers.exists() else []
                state['attributes'] = [
                    {
                        'id': attr.id,
                        'attribute_id': attr.attribute.id,
                        'attribute_name': attr.attribute.attribute_name,
                        'quantity': attr.quantity,
                        'unit_price': attr.unit_price,
                        'total': attr.total
                    } for attr in booking.estimate.estimate_attribute.all()
                ] if booking.estimate.estimate_attribute.exists() else []
            return state
        except:
            return {}

    @staticmethod
    def detect_and_log_changes(booking, old_state, user):
        new_state = BookingChangeTracker.capture_booking_state(booking)
        changes = []
        if 'booking' in old_state and 'booking' in new_state:
            changes.extend(BookingChangeTracker._compare_sections(old_state['booking'], new_state['booking'], 'booking'))
        if 'estimate' in old_state and 'estimate' in new_state:
            changes.extend(BookingChangeTracker._compare_sections(old_state['estimate'], new_state['estimate'], 'estimate'))
        if 'estimation_log' in old_state and 'estimation_log' in new_state:
            changes.extend(BookingChangeTracker._compare_sections(old_state['estimation_log'], new_state['estimation_log'], 'estimation_log'))
        if 'passengers' in old_state and 'passengers' in new_state:
            changes.extend(BookingChangeTracker._compare_passengers(old_state['passengers'], new_state['passengers']))
        if 'attributes' in old_state and 'attributes' in new_state:
            changes.extend(BookingChangeTracker._compare_attributes(old_state['attributes'], new_state['attributes']))
        if changes:
            user_display = BookingLogService._get_user_display(user)
            action = f"Réservation modifiée par {user_display} : {changes[0]}" if len(changes) == 1 else f"Réservation modifiée par {user_display} : {' • '.join(changes)}"
            BookingLogService.log_action(booking, action, user)

    @staticmethod
    def _compare_sections(old_dict, new_dict, context):
        changes = []
        for key, new_value in new_dict.items():
            old_value = old_dict.get(key)
            if old_value != new_value:
                change = BookingChangeTracker._format_change(context, key, old_value, new_value)
                if change:
                    changes.append(change)
        return changes
    
    @staticmethod
    def _format_change(context, field, old_value, new_value):
        field_map = {
            'status': ('statut', lambda x: dict(Booking.STATUS_CHOICES).get(x, x)),
            'billing_status': ('facturation', lambda x: dict(Booking.BILLING_STATUS_CHOICES).get(x, x)),
            'cancellation_status': ('annulation', lambda x: dict(Booking.CANCELLATION_STATUS_CHOICES).get(x, x)),
            'payment_timing': ('timing paiement', lambda x: dict(Booking.PAYMENT_TIMING_CHOICES).get(x, x)),
            'driver_sale_price': ('prix chauffeur', lambda x: f"{x or 0}€"),
            'partner_sale_price': ('prix partenaire', lambda x: f"{x or 0}€"),
            'compensation': ('compensation', lambda x: f"{x or 0}€"),
            'commission': ('commission', lambda x: f"{x or 0}€"),
            'is_driver_paid': ('paiement chauffeur', lambda x: 'effectué' if x else 'en attente'),
            'is_partner_paid': ('paiement partenaire', lambda x: 'effectué' if x else 'en attente'),
            'is_archived': ('archivage', lambda x: 'archivé' if x else 'actif'),
            'total_booking_cost': ('coût total', lambda x: f"{x or 0}€"),
            'total_attributes_cost': ('coût attributs', lambda x: f"{x or 0}€"),
            'flight_number': ('numéro de vol', lambda x: x or 'aucun'),
            'number_of_luggages': ('nombre de bagages', lambda x: x or '0'),
            'number_of_passengers': ('nombre de passagers', lambda x: x or 0),
            'message': ('message', lambda x: 'modifié'),
            'case_number': ('numéro de dossier', lambda x: x or 'aucun'),
            'is_payment_pending': ('paiement en attente', lambda x: 'oui' if x else 'non'),
            'departure': ('lieu de départ', lambda x: x or 'non défini'),
            'destination': ('destination', lambda x: x or 'non définie'),
            'pickup_date': ('date de prise en charge', lambda x: x.strftime("%d/%m/%Y %H:%M") if x else 'non définie'),
            'distance_travelled': ('distance', lambda x: f"{x or 0}km"),
            'duration_travelled': ('durée', lambda x: x or 'non définie'),
            'estimate_type': ('type estimation', lambda x: x or 'non défini'),
        }
        if field in field_map:
            label, formatter = field_map[field]
            if field in ['is_driver_paid', 'is_partner_paid', 'is_archived'] and new_value and not old_value:
                return f"{label} marqué comme {formatter(new_value)}"
            if field in ['message', 'flight_number', 'case_number', 'number_of_luggages', 'departure', 'destination', 'duration_travelled']:
                if old_value != new_value:
                    return f"{label} modifié"
            old_formatted = formatter(old_value)
            new_formatted = formatter(new_value)
            return f"{label} {old_formatted} → {new_formatted}"
        return None
    
    @staticmethod
    def _compare_passengers(old_passengers, new_passengers):
        changes = []
        old_count = len(old_passengers)
        new_count = len(new_passengers)
        if old_count != new_count:
            changes.append(f"nombre de passagers {old_count} → {new_count}")
        old_by_id = {p['id']: p for p in old_passengers}
        new_by_id = {p['id']: p for p in new_passengers if 'id' in p}
        for passenger_id, new_p in new_by_id.items():
            if passenger_id in old_by_id:
                old_p = old_by_id[passenger_id]
                if old_p.get('name') != new_p.get('name'):
                    changes.append(f"nom passager modifié")
                if old_p.get('phone_number') != new_p.get('phone_number'):
                    changes.append(f"téléphone passager modifié")
                if old_p.get('email') != new_p.get('email'):
                    changes.append(f"email passager modifié")
        new_passengers_count = len([p for p in new_passengers if 'id' not in p or p['id'] not in old_by_id])
        if new_passengers_count > 0:
            changes.append(f"{new_passengers_count} nouveau(x) passager(s) ajouté(s)")
        removed_passengers_count = len([p for p in old_passengers if p['id'] not in new_by_id])
        if removed_passengers_count > 0:
            changes.append(f"{removed_passengers_count} passager(s) supprimé(s)")
        return changes
    
    @staticmethod
    def _compare_attributes(old_attributes, new_attributes):
        changes = []
        old_count = len(old_attributes)
        new_count = len(new_attributes)
        if old_count != new_count:
            changes.append(f"nombre d'attributs {old_count} → {new_count}")
        old_by_id = {attr['id']: attr for attr in old_attributes}
        new_by_id = {attr['id']: attr for attr in new_attributes if 'id' in attr}
        for attr_id, new_attr in new_by_id.items():
            if attr_id in old_by_id:
                old_attr = old_by_id[attr_id]
                if old_attr.get('quantity') != new_attr.get('quantity'):
                    attr_name = new_attr.get('attribute_name', f'attribut {attr_id}')
                    changes.append(f"quantité {attr_name} {old_attr.get('quantity')} → {new_attr.get('quantity')}")
                if old_attr.get('attribute_id') != new_attr.get('attribute_id'):
                    changes.append(f"type d'attribut modifié")
        new_attributes_count = len([attr for attr in new_attributes if 'id' not in attr or attr['id'] not in old_by_id])
        if new_attributes_count > 0:
            changes.append(f"{new_attributes_count} nouvel(s) attribut(s) ajouté(s)")
        removed_attributes_count = len([attr for attr in old_attributes if attr['id'] not in new_by_id])
        if removed_attributes_count > 0:
            changes.append(f"{removed_attributes_count} attribut(s) supprimé(s)")
        return changes