from django.core.exceptions import PermissionDenied
from utilisateurs.models import Administrator, Client, Driver, Partner

class BookingUserPermissionService:
    @staticmethod
    def apply_user_booking_filter(queryset, user):
        """
        Applique un filtre basé sur le type d'utilisateur.
        Les modèles Administrator, Client, Driver, Partner héritent de CustomUser
        donc on filtre directement sur l'ID de l'utilisateur.
        """
        try:
            # Vérifier si l'utilisateur est un administrateur
            Administrator.objects.get(id=user.id, role__in=['super_admin', 'manager', 'admin_simple'])
            return queryset
        except Administrator.DoesNotExist:
            pass
        
        try:
            # Vérifier si l'utilisateur est un client
            client = Client.objects.get(id=user.id)
            return queryset.filter(client=client)
        except Client.DoesNotExist:
            pass
        
        try:
            # Vérifier si l'utilisateur est un chauffeur
            driver = Driver.objects.get(id=user.id)
            return queryset.filter(assigned_driver=driver)
        except Driver.DoesNotExist:
            pass
        
        try:
            # Vérifier si l'utilisateur est un partenaire
            partner = Partner.objects.get(id=user.id)
            return queryset.filter(assigned_partner=partner)
        except Partner.DoesNotExist:
            pass
        
        raise PermissionDenied("Type d'utilisateur non reconnu")
    
    @staticmethod
    def get_user_type(user):
        """
        Détermine le type d'utilisateur en vérifiant l'ID directement
        """
        try:
            Administrator.objects.get(id=user.id, role__in=['super_admin', 'manager', 'admin_simple'])
            return 'administrator'
        except Administrator.DoesNotExist:
            pass
        
        try:
            Client.objects.get(id=user.id)
            return 'client'
        except Client.DoesNotExist:
            pass
        
        try:
            Driver.objects.get(id=user.id)
            return 'driver'
        except Driver.DoesNotExist:
            pass
        
        try:
            Partner.objects.get(id=user.id)
            return 'partner'
        except Partner.DoesNotExist:
            pass
        
        return 'unknown'
    
    @staticmethod
    def restrict_booking_fields(user, booking_data, booking):
        """
        Restreint les champs sensibles selon le type d'utilisateur
        """
        user_type = BookingUserPermissionService.get_user_type(user)
        restricted_data = booking_data.copy()
        
        sensitive_fields = ['compensation', 'effective_compensation', 'commission', 'effective_commission', 
                           'driver_sale_price', 'partner_sale_price']
        
        is_driver_linked_to_partner = False
        if user_type == 'partner' and booking.assigned_driver:
            try:
                partner = Partner.objects.get(id=user.id)
                driver = booking.assigned_driver
                is_driver_linked_to_partner = driver.business and driver.business.partner == partner
            except Partner.DoesNotExist:
                pass
        
        if user_type == 'client':
            for field in sensitive_fields:
                restricted_data.pop(field, None)
            for segment in restricted_data.get('segments', []):
                for field in ['compensation', 'commission']:
                    segment.pop(field, None)
        
        elif user_type == 'driver':
            # Le chauffeur ne peut voir que son propre prix de vente s'il est assigné
            allowed_fields = []
            if booking.assigned_driver and booking.assigned_driver.id == user.id:
                allowed_fields = ['driver_sale_price']
            
            for field in sensitive_fields:
                if field not in allowed_fields:
                    restricted_data.pop(field, None)
            for segment in restricted_data.get('segments', []):
                for field in ['compensation', 'commission']:
                    segment.pop(field, None)
        
        elif user_type == 'partner':
            allowed_fields = ['partner_sale_price', 'commission', 'effective_commission']
            if is_driver_linked_to_partner:
                allowed_fields.append('driver_sale_price')
            for field in sensitive_fields:
                if field not in allowed_fields:
                    restricted_data.pop(field, None)
            for segment in restricted_data.get('segments', []):
                segment.pop('compensation', None)
        
        return restricted_data