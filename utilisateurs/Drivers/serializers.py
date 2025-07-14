from rest_framework import serializers
from utilisateurs.models import Driver, Business
from django.db.models import Count

class DriverSerializer(serializers.ModelSerializer):
    """
    Serializer for Driver model with basic information.
    """
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    business_info = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Driver
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'phone_number',
            'address', 'user_type', 'user_type_display', 'is_independent', 
            'years_experience', 'spoken_languages', 'business','is_validated',
            'business_info', 'status_display', 'is_active', 'date_added'
        ]
        read_only_fields = ['username', 'date_added', 'user_type']

    def get_business_info(self, obj):
        if obj.business:
            return {
                'id': obj.business.id,
                'name': obj.business.name,
                'business_type': obj.business.business_type,
                'email': obj.business.email,
                'phone_number': obj.business.phone_number,
                'validation': obj.business.validation
            }
        return None

    def get_status_display(self, obj):
        status = []
        if obj.is_independent:
            status.append('Indépendant')
        else:
            status.append('Lié à une entreprise')
        
        return ' - '.join(status)

class DriverDetailSerializer(DriverSerializer):
    """
    Extended serializer for Driver model with additional information.
    """
    business_details = serializers.SerializerMethodField(read_only=True)

    class Meta(DriverSerializer.Meta):
        fields = DriverSerializer.Meta.fields + ['business_details']

    def get_business_details(self, obj):
        if obj.business:
            return {
                'id': obj.business.id,
                'name': obj.business.name,
                'business_type': obj.business.business_type,
                'email': obj.business.email,
                'phone_number': obj.business.phone_number,
                'address': obj.business.address,
                'website': obj.business.website,
                'description': obj.business.description,
                'operation_location': obj.business.operation_location,
                'validation': obj.business.validation,
                'createdAt': obj.business.createdAt
            }
        return None

class DriverUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating Driver information.
    """
    class Meta:
        model = Driver
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'address',
            'years_experience', 'spoken_languages', 'is_active'
        ]
        
    def validate_years_experience(self, value):
        """
        Validation pour les années d'expérience.
        """
        if value < 0:
            raise serializers.ValidationError("Les années d'expérience ne peuvent pas être négatives.")
        if value > 50:
            raise serializers.ValidationError("Les années d'expérience semblent trop élevées.")
        return value



class DriverBusinessAssociationSerializer(serializers.Serializer):
    """
    Serializer for associating/dissociating a driver with a business.
    """
    business_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, data):
        business_id = data.get('business_id')
        driver = self.context.get('driver')
        
        if not driver:
            raise serializers.ValidationError("Chauffeur non spécifié.")
            
        # Si on veut dissocier le chauffeur (business_id = null)
        if business_id is None:
            if driver.is_independent:
                raise serializers.ValidationError(
                    "Ce chauffeur est déjà indépendant."
                )
            return data
            
        # Si on veut associer le chauffeur à un business
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise serializers.ValidationError(f"Le business avec l'ID {business_id} n'existe pas.")
            
        # Vérifier si le business est validé
        if not business.validation:
            raise serializers.ValidationError(
                "Le business doit être validé avant d'y associer un chauffeur."
            )
        
        # Vérifier si le chauffeur n'est pas déjà associé à ce business
        if driver.business and driver.business.id == business_id:
            raise serializers.ValidationError(
                "Ce chauffeur est déjà associé à ce business."
            )
            
        data['business'] = business
        return data

class DriverStatisticsSerializer(serializers.Serializer):
    """
    Serializer for driver statistics.
    """
    status_type = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()

class GlobalDriverStatisticsSerializer(serializers.Serializer):
    """
    Serializer for global driver statistics.
    """
    total_drivers = serializers.IntegerField()
    active_drivers = serializers.IntegerField()
    inactive_drivers = serializers.IntegerField()
    independent_drivers = serializers.IntegerField()
    business_drivers = serializers.IntegerField()
    validated_drivers = serializers.IntegerField()
    non_validated_drivers = serializers.IntegerField()
    driver_statistics = DriverStatisticsSerializer(many=True)