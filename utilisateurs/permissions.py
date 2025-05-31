from rest_framework.permissions import BasePermission

class IsAdministratorOrPartner(BasePermission):
    message = "Seuls les administrateurs ou partenaires peuvent modifier des véhicules."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return user.user_type in ['administrator', 'partner']
