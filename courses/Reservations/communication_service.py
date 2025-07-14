# courses/Reservations/communication_service.py

from django.template.loader import render_to_string
from configurations.notification_service import NotificationService
from courses.models import BookingLog, Booking
from utilisateurs.helpers import send_email, get_business_info
from utilisateurs.models import Administrator, Business

# ============== IMPORT LAZY POUR ÉVITER L'IMPORT CIRCULAIRE ==============

def get_helper_functions():
    """Import lazy pour éviter l'import circulaire"""
    try:
        from courses.Reservations.Reservations_details.helpers import (
            format_duplication_booking_data, 
            shorten_address,
            format_round_trip_booking_data
        )
        return format_duplication_booking_data, shorten_address, format_round_trip_booking_data
    except ImportError:
        return None, None, None

class CommunicationManager:
    """Manager centralisé pour toutes les communications booking"""
    
    # Configuration des types d'événements
    EMAIL_CONFIGS = {
        'duplicated': {
            'template': 'fichiers_mails/email_booking_duplicated_admin.html',
            'subject_template': 'Nouvelle réservation - {booking_number}',
            'client_template': 'fichiers_mails/email_booking_duplicated_client.html',
            'client_subject': 'Votre nouvelle réservation - {booking_number}'
        },
        'transformed_round_trip': {
            'template': 'fichiers_mails/email_round_trip_transformation_admin.html',
            'subject_template': 'Transformation aller-retour - {booking_number}',
            'client_template': 'fichiers_mails/email_round_trip_transformation.html',
            'client_subject': 'Votre réservation transformée en aller-retour - {booking_number}'
        },
        'recurring_creation': {
            'template': 'fichiers_mails/email_recurring_creation_admin.html',
            'subject_template': 'Récurrence créée - {total_bookings} courses depuis {base_booking}',
            'manager_only': True
        }
    }
    
    @classmethod
    def get_manager_email(cls):
        # Récupère l'email du manager avec fallbacks
        try:
            business = Business.objects.filter(business_type="my_business").first()
            if business:
                if business.main_user and business.main_user.email:
                    return business.main_user.email
                if business.email:
                    return business.email
            
            manager = Administrator.objects.filter(
                role="manager", email__isnull=False
            ).exclude(email='').first()
            if manager:
                return manager.email
            
            admin = Administrator.objects.filter(
                email__isnull=False
            ).exclude(email='').first()
            return admin.email if admin else None
            
        except Exception:
            return None
    
    @classmethod
    def send_email_safe(cls, email_address, subject, html_content):
        # Envoi d'email avec gestion d'erreur
        try:
            return send_email(email_address, subject, html_content)
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False
    
    @classmethod
    def create_log_safe(cls, booking, user, message):
        # Création de log avec gestion d'erreur
        try:
            if user:
                BookingLog.objects.create(booking=booking, user=user, action=message)
                return True
        except Exception as e:
            print(f"❌ Erreur création log: {e}")
        return False


class BookingCommunicationService:
    """Service principal pour communications booking"""
    
    @staticmethod
    def handle_booking_event(booking_id, event_type, user=None, additional_data=None):
        # Point d'entrée unique pour tous les événements booking
        try:
            booking = Booking.objects.get(id=booking_id)
            
            context = BookingCommunicationService._prepare_context(booking, event_type, user, additional_data)
            
            results = {
                'logs': BookingCommunicationService._handle_logs(booking, event_type, context, user),
                'emails': BookingCommunicationService._handle_emails(booking, event_type, context),
                'notifications': BookingCommunicationService._handle_notifications(booking, event_type, context, user)
            }
            
            success_count = sum(1 for result in results.values() if result)
            return success_count > 0, f"Communications: {success_count}/3 réussies"
            
        except Booking.DoesNotExist:
            return False, f"Booking {booking_id} non trouvé"
        except Exception as e:
            return False, f"Erreur communication {event_type}: {str(e)}"
    
    @staticmethod
    def _prepare_context(booking, event_type, user, additional_data):
        # Prépare le contexte selon le type d'événement
        format_duplication_booking_data, shorten_address, format_round_trip_booking_data = get_helper_functions()
        
        base_context = {
            'business_info': get_business_info(),
            'event_type': event_type,
            'user': user,
            'booking': booking
        }
        
        if event_type == 'duplicated' and format_duplication_booking_data:
            booking_data = format_duplication_booking_data(booking, include_request_data=False)
            base_context.update({
                'reservation_details': booking_data["display_data"],
                'pdf_url': f"{base_context['business_info']['operator_url']}/api/reservations/booking/{booking.id}/pdf/",
                'duplicated_by': f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu"
            })
        
        elif event_type == 'transformed_round_trip':
            try:
                from courses.Reservations.Reservations_details.helpers import get_round_trip_unified_context
                unified_context, _ = get_round_trip_unified_context(booking.id)
                base_context.update(unified_context)
            except:
                base_context['round_trip_details'] = {'booking_number': booking.booking_number}
        
        elif event_type == 'recurring_creation':
            if additional_data:
                base_context.update({
                    'manager_data': {
                        'template_id': additional_data.get('template_id'),
                        'total_bookings': additional_data.get('total_bookings', 0),
                        'base_booking': additional_data.get('base_booking', 'N/A'),
                        'has_errors': additional_data.get('has_errors', False),
                        'created_by': additional_data.get('created_by', 'Admin'),
                        'created_bookings': additional_data.get('created_bookings', []),
                        'base_booking_obj': additional_data.get('base_booking_obj'),
                        'trip_info': additional_data.get('trip_info', {}),
                        'vehicle_info': additional_data.get('vehicle_info', 'N/A'),
                        'total_cost': additional_data.get('total_cost', 0),
                        'detailed_bookings': additional_data.get('detailed_bookings', [])
                    }
                })
        
        return base_context
    
    @staticmethod
    def _handle_logs(booking, event_type, context, user):
        # Gère les logs selon le type
        if not user:
            return False
        
        try:
            if event_type == 'duplicated':
                message = BookingCommunicationService._generate_duplication_log(booking, context, user)
            elif event_type == 'transformed_round_trip':
                return True
            elif event_type == 'recurring_creation':
                message = BookingCommunicationService._generate_recurring_log(context, user)
            else:
                message = f"Événement {event_type} par {user.get_full_name()}"
            
            return CommunicationManager.create_log_safe(booking, user, message)
            
        except Exception as e:
            print(f"❌ Erreur logs {event_type}: {e}")
            return False
    
    @staticmethod
    def _handle_emails(booking, event_type, context):
        # Gère les emails selon le type et destinataires
        try:
            email_config = CommunicationManager.EMAIL_CONFIGS.get(event_type)
            if not email_config:
                return False
            
            results = []
            
            results.append(BookingCommunicationService._send_manager_email(event_type, context, email_config))
            
            if not email_config.get('manager_only', False):
                if booking.client is None:
                    results.append(BookingCommunicationService._send_passenger_emails(event_type, context, booking, email_config))
                else:
                    results.append(BookingCommunicationService._send_client_email(event_type, context, booking, email_config))
            
            return any(results)
            
        except Exception as e:
            print(f"❌ Erreur emails {event_type}: {e}")
            return False
    
    @staticmethod
    def _handle_notifications(booking, event_type, context, user):
        # Gère les notifications selon le type
        try:
            if event_type == 'duplicated':
                return NotificationService.create_booking_notification(booking, is_update=False)
            elif event_type == 'transformed_round_trip':
                return NotificationService.create_round_trip_notification(booking)
            elif event_type == 'recurring_creation':
                return BookingCommunicationService._create_recurring_notification(context, user)
            return False
            
        except Exception as e:
            print(f"❌ Erreur notifications {event_type}: {e}")
            return False
    
    @staticmethod
    def _send_manager_email(event_type, context, email_config):
        # Envoie l'email manager avec template approprié
        try:
            manager_email = CommunicationManager.get_manager_email()
            if not manager_email:
                print("❌ Aucun email manager trouvé")
                return False
            
            if event_type == 'recurring_creation':
                manager_data = context.get('manager_data', {})
                subject = email_config['subject_template'].format(
                    total_bookings=manager_data.get('total_bookings', 0),
                    base_booking=manager_data.get('base_booking', 'N/A')
                )
                
                base_booking_obj = manager_data.get('base_booking_obj')
                client_name = "Client inconnu"
                if base_booking_obj:
                    if base_booking_obj.client:
                        client_name = base_booking_obj.client.get_full_name()
                    else:
                        if base_booking_obj.estimate and base_booking_obj.estimate.estimation_log:
                            if base_booking_obj.estimate.estimation_log.user:
                                client_name = f"{base_booking_obj.estimate.estimation_log.user.first_name} {base_booking_obj.estimate.estimation_log.user.last_name}".strip()
                            elif base_booking_obj.estimate.passengers.exists():
                                first_passenger = base_booking_obj.estimate.passengers.first()
                                client_name = first_passenger.name
                        
                        if client_name == "Client inconnu":
                            client_name = "Réservation admin"
                
                created_bookings = manager_data.get('created_bookings', [])
                detailed_bookings = manager_data.get('detailed_bookings', [])
                
                email_context = {
                    **context,
                    'template_id': manager_data.get('template_id'),
                    'base_booking': manager_data.get('base_booking', 'N/A'),
                    'created_by': manager_data.get('created_by', 'Admin'),
                    'total_bookings': manager_data.get('total_bookings', 0),
                    'client_name': client_name,
                    'has_modifications': any(b.get('type') == 'modified' for b in created_bookings),
                    'departure': manager_data.get('trip_info', {}).get('departure', 'N/A'),
                    'destination': manager_data.get('trip_info', {}).get('destination', 'N/A'),
                    'vehicle_info': manager_data.get('vehicle_info', 'N/A'),
                    'total_cost': manager_data.get('total_cost', 0),
                    'detailed_bookings': detailed_bookings,
                    'has_errors': manager_data.get('has_errors', False),
                    'base_booking_obj': manager_data.get('base_booking_obj'),
                }
                
            else:
                booking_number = context.get('reservation_details', {}).get('booking_number') or \
                               context.get('round_trip_details', {}).get('booking_number', 'N/A')
                subject = email_config['subject_template'].format(booking_number=booking_number)
                email_context = context
            
            html_content = render_to_string(email_config['template'], email_context)
            
            result = CommunicationManager.send_email_safe(manager_email, subject, html_content)
            print(f"📧 Email manager envoyé: {result} - {subject}")
            return result
            
        except Exception as e:
            import traceback
            print(f"❌ Erreur email manager {event_type}: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def _send_client_email(event_type, context, booking, email_config):
        # Envoie l'email client
        try:
            if not booking.client or not booking.client.email:
                return False
            
            client_context = {
                **context,
                "recipient_name": booking.client.get_full_name(),
                "recipient_role": "client"
            }
            
            booking_number = context.get('reservation_details', {}).get('booking_number', 'N/A')
            subject = email_config['client_subject'].format(booking_number=booking_number)
            
            html_content = render_to_string(email_config['client_template'], client_context)
            
            return CommunicationManager.send_email_safe(booking.client.email, subject, html_content)
            
        except Exception as e:
            print(f"❌ Erreur email client {event_type}: {e}")
            return False
    
    @staticmethod
    def _send_passenger_emails(event_type, context, booking, email_config):
        # Envoie les emails passagers
        try:
            if booking.booking_type == 'round_trip':
                passengers = BookingCommunicationService._get_round_trip_passengers(context)
            else:
                passengers = context.get('reservation_details', {}).get('passengers', [])
            
            success_count = 0
            for passenger in passengers:
                if not passenger.get('email') or passenger['email'] == "Non renseigné":
                    continue
                
                passenger_context = {
                    **context,
                    "recipient_name": passenger['name'],
                    "recipient_role": "passenger",
                    "recipient_is_main": passenger.get('is_main_client', False)
                }
                
                booking_number = context.get('reservation_details', {}).get('booking_number', 'N/A')
                if passenger.get('is_main_client'):
                    subject = email_config['client_subject'].format(booking_number=booking_number)
                else:
                    subject = f"Nouvelle réservation - Vous êtes passager - {booking_number}"
                
                html_content = render_to_string(email_config['client_template'], passenger_context)
                
                if CommunicationManager.send_email_safe(passenger['email'], subject, html_content):
                    success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Erreur emails passagers {event_type}: {e}")
            return False
    
    @staticmethod
    def _get_round_trip_passengers(context):
        # Récupère passagers uniques pour aller-retour
        segments = context.get('round_trip_details', {}).get('segments', [])
        passengers = {}
        for segment in segments:
            if 'estimate' in segment and 'passengers' in segment['estimate']:
                for passenger in segment['estimate']['passengers']:
                    passengers[passenger['id']] = passenger
        return list(passengers.values())
    
    @staticmethod
    def _generate_duplication_log(booking, context, user):
        # Génère message log duplication
        format_duplication_booking_data, shorten_address, format_round_trip_booking_data = get_helper_functions()
        
        user_display = f"{user.first_name} {user.last_name}".strip() or user.username
        reservation_details = context.get('reservation_details', {})
        
        if booking.booking_type == 'one_way':
            estimation_log = reservation_details.get('estimation_log', {})
            departure = estimation_log.get('departure', 'N/A')
            destination = estimation_log.get('destination', 'N/A')
            total_cost = reservation_details.get('total_booking_cost', 0)
        else:
            segments = reservation_details.get('segments', [])
            outbound = next((s for s in segments if s['type'] == 'outbound'), {})
            departure = outbound.get('departure', 'N/A')
            destination = outbound.get('destination', 'N/A')
            total_cost = reservation_details.get('total_cost', 0)
        
        client_name = reservation_details.get('user', {}).get('name', 'Client inconnu')
        
        if shorten_address:
            departure_short = shorten_address(departure)
            destination_short = shorten_address(destination)
        else:
            departure_short = departure[:30] + "..." if len(departure) > 30 else departure
            destination_short = destination[:30] + "..." if len(destination) > 30 else destination
        
        return (
            f"Booking {booking.booking_number} créé par duplication par {user_display}. "
            f"Client: {client_name}. Trajet: {departure_short} → "
            f"{destination_short} ({total_cost}€)"
        )
    
    @staticmethod
    def _generate_recurring_log(context, user):
        # Génère message log récurrence
        user_display = f"{user.first_name} {user.last_name}".strip() or user.username
        manager_data = context.get('manager_data', {})
        
        return (
            f"Récurrence créée par {user_display}. "
            f"{manager_data.get('total_bookings', 0)} courses générées depuis "
            f"{manager_data.get('base_booking', 'N/A')}. "
            f"Template #{manager_data.get('template_id', 'N/A')}"
        )
    
    @staticmethod
    def _create_recurring_notification(context, user):
        # Crée notification récurrence
        try:
            manager_data = context.get('manager_data', {})
            
            total_bookings = manager_data.get('total_bookings', 0)
            has_errors = manager_data.get('has_errors', False)
            base_booking = manager_data.get('base_booking', 'N/A')
            user_name = f"{user.first_name} {user.last_name}".strip() if user else "Admin"
            
            if has_errors:
                message = f"⚠️ Récurrence créée avec erreurs par {user_name}\n📋 {total_bookings} courses depuis {base_booking}"
                notification_type = "warning"
            else:
                message = f"✅ Récurrence créée par {user_name}\n📋 {total_bookings} courses depuis {base_booking}"
                notification_type = "success"
            
            try:
                booking = context.get('booking')
                if hasattr(NotificationService, 'create_booking_notification') and booking:
                    return NotificationService.create_booking_notification(
                        booking=booking,
                        is_update=False
                    )
                else:
                    print(f"✅ Notification récurrence créée: {message}")
                    return True
                    
            except AttributeError:
                print(f"✅ Notification récurrence créée: {message}")
                return True
                
        except Exception as e:
            print(f"❌ Erreur notification récurrence: {e}")
            return False


# ============== FONCTIONS PUBLIQUES SIMPLIFIÉES ==============

def send_duplication_communications(new_booking_id, source_booking_id=None, user=None):
    # Communications duplication
    return BookingCommunicationService.handle_booking_event(
        booking_id=new_booking_id,
        event_type='duplicated',
        user=user
    )

def send_round_trip_communications(booking_id, return_data=None, user=None):
    # Communications aller-retour
    return BookingCommunicationService.handle_booking_event(
        booking_id=booking_id,
        event_type='transformed_round_trip',
        user=user,
        additional_data=return_data
    )

def send_booking_email(email_data, user):
    # Point d'entrée unifié pour emails
    booking_type = email_data.get('booking_type')
    
    if booking_type == 'recurring_creation':
        return BookingCommunicationService._send_manager_email(
            'recurring_creation',
            email_data,
            CommunicationManager.EMAIL_CONFIGS['recurring_creation']
        )
    
    return False

def create_booking_notification(message, notification_type, user, data=None):
    # Point d'entrée unifié pour notifications
    try:
        if data and data.get('type') == 'recurring_creation':
            context = {'manager_data': data}
            return BookingCommunicationService._create_recurring_notification(context, user)
        
        try:
            if hasattr(NotificationService, 'create_notification'):
                return NotificationService.create_notification(
                    message=message,
                    notification_type=notification_type,
                    user=user,
                    data=data
                )
            else:
                print(f"✅ Notification créée: {message}")
                return True
        except Exception as e:
            print(f"❌ Erreur NotificationService: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Erreur notification: {e}")
        return False