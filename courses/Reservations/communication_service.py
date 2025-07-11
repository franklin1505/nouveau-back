# courses/Reservations/communication_service.py

from django.template.loader import render_to_string
from configurations.notification_service import NotificationService
from courses.Reservations.Reservations_details.helpers import format_duplication_booking_data, shorten_address
from courses.models import BookingLog, Booking
from utilisateurs.helpers import send_email, get_business_info
from utilisateurs.models import Administrator, Business


class BookingCommunicationService:
    """Service centralisé pour communications booking (duplication et aller-retour)"""
    
    @staticmethod
    def handle_booking_event(booking_id, event_type, user=None, additional_data=None):
        """Point d'entrée unique pour tous les événements booking"""
        try:
            booking = Booking.objects.get(id=booking_id)
            
            # Préparer le contexte
            if event_type == 'duplicated':
                context = BookingCommunicationService._prepare_duplication_context(booking, additional_data, user)
            elif event_type == 'transformed_round_trip':
                context = BookingCommunicationService._prepare_round_trip_context(booking, additional_data, user)
            else:
                raise ValueError(f"Type d'événement non supporté: {event_type}")
            
            # Exécution fail-safe
            BookingCommunicationService._execute_communications(booking, event_type, context, user)
            
            return True, "Communications envoyées avec succès"
            
        except Exception as e:
            error_msg = f"Erreur communication {event_type}: {str(e)}"
            print(error_msg)
            return False, error_msg

    @staticmethod
    def _prepare_duplication_context(booking, additional_data, user):
        """Prépare le contexte pour duplication avec gestion robuste"""
        try:
            business_info = get_business_info()
            
            # Déterminer le bon formateur selon le type
            booking_data = format_duplication_booking_data(booking, include_request_data=False)

            # ✅ CORRECTION : Informations sur qui a créé la duplication avec fallback robuste
            booking_creator = {
                "type": "admin" if booking.client is None else "client",
                "name": f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu"
            }
            
            # ✅ CORRECTION : Gestion robuste de l'utilisateur créateur
            if booking.client:
                booking_creator["user"] = booking.client
            elif booking.estimate and booking.estimate.estimation_log and booking.estimate.estimation_log.user:
                booking_creator["user"] = booking.estimate.estimation_log.user
            else:
                # ✅ Fallback si pas d'utilisateur trouvé
                booking_creator["user"] = user if user else None
            
            pdf_url = f"{business_info['operator_url']}/api/reservations/booking/{booking.id}/pdf/"
            
            return {
                "event_type": "duplication",
                "reservation_details": booking_data["display_data"],
                "business_info": business_info,
                "booking_creator": booking_creator,
                "pdf_url": pdf_url,
                "duplicated_by": f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu"
            }
        except Exception as e:
            print(f"❌ Erreur préparation contexte duplication: {e}")
            # ✅ CORRECTION : Contexte minimal robuste en cas d'erreur
            return {
                "event_type": "duplication",
                "reservation_details": {
                    "booking_number": getattr(booking, 'booking_number', 'N/A'),
                    "total_booking_cost": 0,
                    "user": {
                        "name": f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu"
                    },
                    "passengers": [],
                    "segments": [] if booking.booking_type == 'round_trip' else None
                },
                "business_info": get_business_info(),
                "booking_creator": {
                    "type": "client" if booking.client else "admin",
                    "name": f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu",
                    "user": user if user else None
                },
                "pdf_url": f"{get_business_info()['operator_url']}/api/reservations/booking/{booking.id}/pdf/",
                "duplicated_by": f"{user.first_name} {user.last_name}".strip() if user else "Utilisateur inconnu"
            }
        
    
    @staticmethod
    def _prepare_round_trip_context(booking, additional_data, user):
        """Réutilise la logique aller-retour existante"""
        from courses.Reservations.Reservations_details.helpers import get_round_trip_unified_context
        unified_context, _ = get_round_trip_unified_context(booking.id)
        return unified_context

    @staticmethod
    def _execute_communications(booking, event_type, context, user):
        """Exécute les 3 types de communications en mode fail-safe"""
        
        # 1. LOGS (priorité max)
        try:
            BookingCommunicationService._create_logs(booking, event_type, context, user)
        except Exception as log_error:
            print(f"❌ Erreur logs {event_type}: {log_error}")
        
        # 2. EMAILS
        try:
            BookingCommunicationService._send_emails(booking, event_type, context)
        except Exception as email_error:
            print(f"❌ Erreur emails {event_type}: {email_error}")
        
        # 3. NOTIFICATIONS
        try:
            BookingCommunicationService._send_notifications(booking, event_type, context)
        except Exception as notif_error:
            print(f"❌ Erreur notifications {event_type}: {notif_error}")

    @staticmethod
    def _create_logs(booking, event_type, context, user):
        """Crée les logs selon le même style que l'existant"""
        if not user:
            return
        
        try:
            if event_type == 'duplicated':
                message = BookingCommunicationService._generate_duplication_log_message(booking, context, user)
            elif event_type == 'transformed_round_trip':
                # Utiliser la logique existante de l'aller-retour
                return  # Car déjà géré dans convert_booking_to_round_trip
            else:
                message = f"Événement {event_type} par {user.get_full_name()}"
            
            BookingLog.objects.create(booking=booking, user=user, action=message)
            
        except Exception as e:
            print(f"❌ Erreur création log: {e}")
    
    @staticmethod
    def _generate_duplication_log_message(booking, context, user):
        """Génère le message de log pour duplication (style existant) - VERSION CORRIGÉE"""
        user_display = f"{user.first_name} {user.last_name}".strip() or user.username
        
        reservation_details = context.get('reservation_details', {})
        
        # ✅ CORRECTION : Récupérer trajet et coût depuis les bonnes données
        if booking.booking_type == 'one_way':
            # Pour one_way, récupérer depuis estimation_log
            estimation_log = reservation_details.get('estimation_log', {})
            departure = estimation_log.get('departure', 'N/A')
            destination = estimation_log.get('destination', 'N/A')
            total_cost = reservation_details.get('total_booking_cost', 0)
        else:
            # Pour round_trip, récupérer depuis segments
            segments = reservation_details.get('segments', [])
            outbound = next((s for s in segments if s['type'] == 'outbound'), {})
            departure = outbound.get('departure', 'N/A')
            destination = outbound.get('destination', 'N/A') 
            total_cost = reservation_details.get('total_cost', 0)
        
        # Client info
        client_name = "Client inconnu"
        user_info = reservation_details.get('user')
        if user_info:
            client_name = user_info.get('name', 'Client inconnu')
        
        return (
            f"Booking {booking.booking_number} créé par duplication par {user_display}. "
            f"Client: {client_name}. Trajet: {shorten_address(departure)} → "
            f"{shorten_address(destination)} ({total_cost}€)"
        )    
        
    @staticmethod
    def _send_emails(booking, event_type, context):
        """Envoie les emails selon la logique validée"""
        
        # Manager toujours notifié
        BookingCommunicationService._send_manager_email(event_type, context)
        
        # Client OU passagers (jamais les deux)
        if booking.client is None:
            # Réservation admin → emails passagers
            BookingCommunicationService._send_passenger_emails(event_type, context, booking)
        else:
            # Réservation client → email client
            BookingCommunicationService._send_client_email(event_type, context, booking)
    
    @staticmethod
    def _send_manager_email(event_type, context):
        """Envoie l'email au manager"""
        try:
            manager_email = BookingCommunicationService._get_manager_email()
            if not manager_email:
                return
            
            # Template et sujet selon l'événement
            if event_type == 'duplicated':
                template = "fichiers_mails/email_booking_duplicated_admin.html"
                booking_number = context.get('reservation_details', {}).get('booking_number', 'N/A')
                subject = f"Nouvelle réservation - {booking_number}"
            elif event_type == 'transformed_round_trip':
                template = "fichiers_mails/email_round_trip_transformation_admin.html"
                booking_number = context.get('round_trip_details', {}).get('booking_number', 'N/A')
                subject = f"Transformation aller-retour - {booking_number}"
            else:
                return
            
            html_content = render_to_string(template, context)
            send_email(manager_email, subject, html_content)
            
        except Exception as e:
            print(f"❌ Erreur email manager: {e}")
    
    @staticmethod
    def _send_client_email(event_type, context, booking):
        """Envoie l'email au client"""
        try:
            if not booking.client or not booking.client.email:
                return
            
            client_email = booking.client.email
            client_name = booking.client.get_full_name()
            
            # Context spécifique client
            client_context = {
                **context,
                "recipient_name": client_name,
                "recipient_role": "client"
            }
            
            # Template et sujet selon l'événement
            if event_type == 'duplicated':
                template = "fichiers_mails/email_booking_duplicated_client.html"
                booking_number = context.get('reservation_details', {}).get('booking_number', 'N/A')
                subject = f"Votre nouvelle réservation - {booking_number}"
            elif event_type == 'transformed_round_trip':
                template = "fichiers_mails/email_round_trip_transformation.html"
                booking_number = context.get('round_trip_details', {}).get('booking_number', 'N/A')
                subject = f"Votre réservation transformée en aller-retour - {booking_number}"
            else:
                return
            
            html_content = render_to_string(template, client_context)
            send_email(client_email, subject, html_content)
            
        except Exception as e:
            print(f"❌ Erreur email client: {e}")
    
    @staticmethod
    def _send_passenger_emails(event_type, context, booking):
        """Envoie les emails aux passagers (réservations admin)"""
        try:
            # Récupération des passagers selon le type de booking
            if booking.booking_type == 'round_trip':
                passengers = BookingCommunicationService._get_round_trip_passengers(context)
            else:
                passengers = context.get('reservation_details', {}).get('passengers', [])
            
            for passenger in passengers:
                passenger_email = passenger.get('email')
                if not passenger_email or passenger_email == "Non renseigné":
                    continue
                
                # Context spécifique passager
                passenger_context = {
                    **context,
                    "recipient_name": passenger['name'],
                    "recipient_role": "passenger",
                    "recipient_is_main": passenger.get('is_main_client', False)
                }
                
                # Template et sujet selon l'événement
                if event_type == 'duplicated':
                    template = "fichiers_mails/email_booking_duplicated_client.html"
                    booking_number = context.get('reservation_details', {}).get('booking_number', 'N/A')
                    if passenger.get('is_main_client'):
                        subject = f"Votre nouvelle réservation - {booking_number}"
                    else:
                        subject = f"Nouvelle réservation - Vous êtes passager - {booking_number}"
                elif event_type == 'transformed_round_trip':
                    template = "fichiers_mails/email_round_trip_transformation.html"
                    booking_number = context.get('round_trip_details', {}).get('booking_number', 'N/A')
                    subject = f"Réservation transformée en aller-retour - {booking_number}"
                else:
                    continue
                
                html_content = render_to_string(template, passenger_context)
                send_email(passenger_email, subject, html_content)
                
        except Exception as e:
            print(f"❌ Erreur emails passagers: {e}")
    
    @staticmethod
    def _get_round_trip_passengers(context):
        """Récupère les passagers uniques pour aller-retour"""
        segments = context.get('round_trip_details', {}).get('segments', [])
        all_passengers = {}
        
        for segment in segments:
            if 'estimate' in segment and 'passengers' in segment['estimate']:
                for passenger in segment['estimate']['passengers']:
                    all_passengers[passenger['id']] = passenger
        
        return list(all_passengers.values())

    @staticmethod
    def _send_notifications(booking, event_type, context):
        """Envoie les notifications temps réel"""
        try:
            if event_type == 'duplicated':
                # Réutiliser la logique existante
                NotificationService.create_booking_notification(booking, is_update=False)
            elif event_type == 'transformed_round_trip':
                # Utiliser la logique spécialisée aller-retour
                NotificationService.create_round_trip_notification(booking)
                
        except Exception as e:
            print(f"❌ Erreur notifications: {e}")

    @staticmethod
    def _get_manager_email():
        """Récupère l'email du manager (logique existante)"""
        try:
            business = Business.objects.filter(business_type="my_business").first()
            
            if business and business.main_user and business.main_user.email:
                return business.main_user.email
            
            if business and business.email:
                return business.email
            
            manager_admin = Administrator.objects.filter(
                role="manager", email__isnull=False
            ).exclude(email='').first()
            
            if manager_admin:
                return manager_admin.email
            
            any_admin = Administrator.objects.filter(
                email__isnull=False
            ).exclude(email='').first()
            
            return any_admin.email if any_admin else None
            
        except Exception:
            return None

# ============== FONCTIONS PUBLIQUES ==============

def send_duplication_communications(new_booking_id, source_booking_id=None, user=None):
    """Point d'entrée pour communications de duplication"""
    additional_data = {}
    if source_booking_id:
        try:
            source_booking = Booking.objects.get(id=source_booking_id)
            additional_data['source_booking'] = source_booking
        except:
            pass
    
    return BookingCommunicationService.handle_booking_event(
        booking_id=new_booking_id,
        event_type='duplicated',
        user=user,
        additional_data=additional_data
    )

def send_round_trip_communications(booking_id, return_data=None, user=None):
    """Point d'entrée pour communications aller-retour"""
    return BookingCommunicationService.handle_booking_event(
        booking_id=booking_id,
        event_type='transformed_round_trip',
        user=user,
        additional_data=return_data
    )