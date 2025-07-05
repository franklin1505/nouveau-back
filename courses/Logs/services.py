from django.utils import timezone
from django.contrib.auth import get_user_model
from courses.models import Booking, BookingLog
import threading

User = get_user_model()

_thread_local = threading.local()

class BookingLogService:
    
    @staticmethod
    def set_current_user(user):
        """Définir l'utilisateur courant pour le thread"""
        _thread_local.user = user
    
    @staticmethod
    def get_current_user():
        """Récupérer l'utilisateur courant du thread"""
        return getattr(_thread_local, 'user', None)
    
    @staticmethod
    def clear_current_user():
        """Nettoyer l'utilisateur courant"""
        if hasattr(_thread_local, 'user'):
            delattr(_thread_local, 'user')
    
    @staticmethod
    def log_action(booking, action, user=None, details=None):
        """
        Enregistrer une action sur un booking
        
        Args:
            booking: Instance de Booking
            action: Type d'action (str)
            user: Utilisateur qui effectue l'action (optionnel)
            details: Détails supplémentaires (optionnel)
        """
        if user is None:
            user = BookingLogService.get_current_user()
        
        action_message = BookingLogService._build_action_message(action, details, user)
        
        BookingLog.objects.create(
            booking=booking,
            user=user,
            action=action_message
        )
    
    @staticmethod
    def log_creation(booking, user=None):
        """Log de création de booking"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Réservation créée par {user_type}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_modification(booking, changed_fields=None, user=None):
        """Log de modification de booking"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        
        if changed_fields:
            fields_str = ", ".join(changed_fields)
            action = f"Modification effectuée par {user_type} - Champs: {fields_str}"
        else:
            action = f"Modification effectuée par {user_type}"
        
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_status_change(booking, old_status, new_status, user=None):
        """Log de changement de statut"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Statut modifié par {user_type}: {old_status} → {new_status}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_duplication(original_booking, new_booking, user=None):
        """Log de duplication de booking"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Réservation dupliquée par {user_type} depuis #{original_booking.id}"
        BookingLogService.log_action(new_booking, action, user)
    
    @staticmethod
    def log_deletion(booking, user=None):
        """Log de suppression de booking"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Réservation supprimée par {user_type}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_financial_change(booking, field_name, old_value, new_value, user=None):
        """Log de modification financière"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Modification financière par {user_type} - {field_name}: {old_value}€ → {new_value}€"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_assignment(booking, assignment_type, assignee_name, user=None):
        """Log d'assignation (chauffeur/partenaire)"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Assignation {assignment_type} par {user_type}: {assignee_name}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def log_export(booking, export_type, user=None):
        """Log d'export de booking"""
        user = user or BookingLogService.get_current_user()
        user_type = BookingLogService._get_user_type(user)
        action = f"Export {export_type} généré par {user_type}"
        BookingLogService.log_action(booking, action, user)
    
    @staticmethod
    def _build_action_message(action, details, user):
        """Construire le message d'action avec timestamp"""
        timestamp = timezone.now().strftime("%d/%m/%Y à %H:%M")
        base_message = f"{timestamp} - {action}"
        
        if details:
            return f"{base_message} - {details}"
        return base_message
    
    @staticmethod
    def _get_user_type(user):
        """Déterminer le type d'utilisateur"""
        if not user:
            return "Système"
        
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return f"Admin ({user.get_full_name() or user.username})"
        elif hasattr(user, 'user_type'):
            user_type_map = {
                'client': 'Client',
                'driver': 'Chauffeur', 
                'admin': 'Admin',
                'partner': 'Partenaire'
            }
            type_name = user_type_map.get(user.user_type, 'Utilisateur')
            return f"{type_name} ({user.get_full_name() or user.username})"
        
        return f"Utilisateur ({user.get_full_name() or user.username})"
    
    @staticmethod
    def get_booking_timeline(booking):
        """Récupérer la timeline complète d'un booking"""
        return BookingLog.objects.filter(booking=booking).order_by('timestamp')
    
    @staticmethod
    def get_user_actions(user, limit=50):
        """Récupérer les actions d'un utilisateur"""
        return BookingLog.objects.filter(user=user).order_by('-timestamp')[:limit]