# serializers.py
from rest_framework import serializers
from utilisateurs.models import Business, CustomUser

class BusinessInfoSerializer(serializers.ModelSerializer):
    vehicles_count = serializers.SerializerMethodField()
    drivers_count = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = (
            'id', 'name', 'address', 'email', 'phone_number', 'website',
            'createdAt', 'description', 'logo', 'operation_location',
            'business_type', 'validation', 'vehicles_count', 'drivers_count'
        )

    def get_vehicles_count(self, obj):
        return obj.vehicles.count()

    def get_drivers_count(self, obj):
        return obj.driver_set.count()



class UserDynamicSerializer(serializers.ModelSerializer):
    businesses = serializers.SerializerMethodField()
    partner_business_count = serializers.SerializerMethodField()
    business = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    parent_info = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        exclude = ('password', 'otp_code', 'otp_expires_at',)
    # Retourne tous les champs du modèle CustomUser

    def get_businesses(self, obj):
        if obj.user_type == 'administrator':
            qs = obj.businesses.all()  # Relation définie sur Administrator (ex: via main_user)
            return BusinessInfoSerializer(qs, many=True, context=self.context).data
        elif obj.user_type == 'partner':
            qs = obj.partner_businesses.all()  # Relation définie sur Partner (ex: via partner)
            return BusinessInfoSerializer(qs, many=True, context=self.context).data
        return []

    def get_partner_business_count(self, obj):
        if obj.user_type == 'administrator':
            # Attention : adapter cette requête selon vos besoins réels
            return Business.objects.filter(partner__isnull=False).count()
        return None

    def get_business(self, obj):
        if obj.user_type == 'driver' and not obj.is_independent:
            if hasattr(obj, 'business') and obj.business:
                return BusinessInfoSerializer(obj.business, context=self.context).data
        return None

    def get_children_count(self, obj):
        if obj.user_type == 'client' and hasattr(obj, 'client_type') and obj.client_type in ['agency', 'company']:
            return obj.children.count()
        return None

    def get_parent_info(self, obj):
        if (
            obj.user_type == 'client' and 
            hasattr(obj, 'client_type') and 
            obj.client_type in ['agency_agent', 'company_collaborator']
        ):
            if obj.parent:
                return {
                    'id': obj.parent.id,
                    'first_name': obj.parent.first_name,
                    'last_name': obj.parent.last_name,
                    'client_type': obj.parent.client_type,
                }
        return None
