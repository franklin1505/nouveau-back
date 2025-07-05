from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from configurations.models import Notification
from utilisateurs.models import Business, Administrator
from configurations.serializers import NotificationSerializer

class NotificationService:
    @staticmethod
    def create_booking_notification(booking, is_update=False):
        """
        Logique simple :
        - Manager : TOUJOURS notifié
        - Client : SEULEMENT si booking.client existe
        """
        notifications_created = []
        
        # 1. MANAGER : Toujours notifié
        manager_notification = NotificationService._create_manager_notification(booking, is_update)
        if manager_notification:
            notifications_created.append(manager_notification)
            NotificationService._send_realtime_notification(manager_notification)
        
        # 2. CLIENT : Seulement si réservation client normale
        if booking.client:  # Réservation client (pas admin/ponctuelle)
            client_notification = NotificationService._create_client_notification(booking, is_update)
            if client_notification:
                notifications_created.append(client_notification)
                NotificationService._send_realtime_notification(client_notification)
        
        return notifications_created
    
    @staticmethod
    def _create_manager_notification(booking, is_update):
        """Crée une notification pour le manager"""
        try:
            # Trouver le manager
            manager = NotificationService._get_manager()
            if not manager:
                print("Aucun manager trouvé pour les notifications")
                return None
            
            # Générer le contenu
            booking_info = NotificationService._get_booking_info(booking)
            action = "mise à jour" if is_update else "création"
            
            notification = Notification.objects.create(
                title=f"{'Mise à jour' if is_update else 'Nouvelle'} réservation",
                message=f"Réservation {booking.booking_number} - {action} confirmée\n"
                       f"Client: {booking_info['client_name']}\n"
                       f"Trajet: {booking_info['departure']} → {booking_info['destination']}\n"
                       f"Date: {booking_info['pickup_date']}\n"
                       f"Montant: {booking_info['total_cost']}€",
                type="booking_update" if is_update else "booking_confirmation",
                user=manager
            )
            return notification
            
        except Exception as e:
            print(f"Erreur création notification manager: {e}")
            return None
    
    @staticmethod
    def _create_client_notification(booking, is_update):
        """Crée une notification pour le client (seulement si booking.client existe)"""
        try:
            if not booking.client:
                return None
                
            booking_info = NotificationService._get_booking_info(booking)
            action = "mise à jour" if is_update else "confirmation"
            
            notification = Notification.objects.create(
                title=f"{'Mise à jour de votre' if is_update else 'Confirmation de'} réservation",
                message=f"Votre réservation {booking.booking_number} - {action}\n"
                       f"Trajet: {booking_info['departure']} → {booking_info['destination']}\n"
                       f"Date: {booking_info['pickup_date']}\n"
                       f"Véhicule: {booking_info['vehicle']}\n"
                       f"Montant: {booking_info['total_cost']}€",
                type="booking_update" if is_update else "booking_confirmation",
                user=booking.client
            )
            return notification
            
        except Exception as e:
            print(f"Erreur création notification client: {e}")
            return None
    
    @staticmethod
    def _get_manager():
        """Trouve le manager à notifier"""
        try:
            # 1. Chercher via Business my_business
            business = Business.objects.filter(business_type="my_business").first()
            if business and business.main_user:
                return business.main_user
            
            # 2. Fallback : chercher un manager
            manager = Administrator.objects.filter(role="manager").first()
            if manager:
                return manager
            
            # 3. Fallback final : n'importe quel admin
            return Administrator.objects.first()
            
        except Exception as e:
            print(f"Erreur recherche manager: {e}")
            return None
    
    @staticmethod
    def _get_booking_info(booking):
        """Extrait les informations du booking"""
        estimation_log = booking.estimate.estimation_log
        
        # Nom du client
        if booking.client:
            client_name = booking.client.get_full_name()
        else:
            # Réservation admin/ponctuelle
            admin_user = estimation_log.user
            client_name = f"{admin_user.get_full_name()} (Admin)" if admin_user else "Réservation Admin"
        
        # Véhicule
        vehicle_info = "Véhicule non spécifié"
        if booking.estimate.user_choice:
            from configurations.models import Vehicle
            try:
                vehicle = Vehicle.objects.get(id=booking.estimate.user_choice.vehicle_id)
                vehicle_info = f"{vehicle.brand} {vehicle.model}"
            except Vehicle.DoesNotExist:
                pass
        
        return {
            "client_name": client_name,
            "departure": estimation_log.departure,
            "destination": estimation_log.destination,
            "pickup_date": estimation_log.pickup_date.strftime("%d/%m/%Y à %H:%M"),
            "vehicle": vehicle_info,
            "total_cost": booking.estimate.total_booking_cost or 0
        }
    
    @staticmethod
    def _send_realtime_notification(notification):
        """Envoie une notification en temps réel"""
        if not notification.user:
            return
            
        try:
            channel_layer = get_channel_layer()
            
            # Sérialiser la notification
            serializer = NotificationSerializer(notification)
            notification_data = {
                **serializer.data,
                "booking_id": NotificationService._extract_booking_id(notification.message)
            }
            
            # Envoyer via WebSocket
            group_name = f'notifications_{notification.user.id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'send_notification',
                    'data': {
                        'type': 'booking_notification',
                        'notification': notification_data
                    }
                }
            )
            
        except Exception as e:
            print(f"Erreur envoi temps réel: {e}")
    
    @staticmethod
    def _extract_booking_id(message):
        """Extrait le booking_id du message"""
        import re
        match = re.search(r'BK-\d{2}-\d{6}', message)
        return match.group(0) if match else None