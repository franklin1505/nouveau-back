# courses/Reservations/Reservations_details/user_permissions.py

from django.core.exceptions import PermissionDenied
from utilisateurs.models import Administrator, Client, Driver, Partner

class BookingUserPermissionService:
    """Service centralisé pour la gestion des permissions utilisateur sur les bookings"""
    
    @staticmethod
    def apply_user_booking_filter(queryset, user):
        """Applique le filtre de bookings selon le type d'utilisateur"""
        try:
            # Manager voit tout
            Administrator.objects.get(user=user, role='manager')
            return queryset
        except Administrator.DoesNotExist:
            pass
        
        try:
            # Client voit seulement ses bookings
            client = Client.objects.get(user=user)
            return queryset.filter(client=client)
        except Client.DoesNotExist:
            pass
        
        try:
            # Chauffeur voit les bookings assignés
            driver = Driver.objects.get(user=user)
            return queryset.filter(assigned_driver=driver)
        except Driver.DoesNotExist:
            pass
        
        try:
            # Partenaire voit les bookings assignés
            partner = Partner.objects.get(user=user)
            return queryset.filter(assigned_partner=partner)
        except Partner.DoesNotExist:
            pass
        
        # Aucun type reconnu
        raise PermissionDenied("Type d'utilisateur non reconnu")
    
    @staticmethod
    def get_user_type(user):
        """Retourne le type d'utilisateur pour logging/debug"""
        try:
            Administrator.objects.get(user=user, role='manager')
            return 'manager'
        except Administrator.DoesNotExist:
            pass
        
        try:
            Client.objects.get(user=user)
            return 'client'
        except Client.DoesNotExist:
            pass
        
        try:
            Driver.objects.get(user=user)
            return 'driver'
        except Driver.DoesNotExist:
            pass
        
        try:
            Partner.objects.get(user=user)
            return 'partner'
        except Partner.DoesNotExist:
            pass
        
        return 'unknown'