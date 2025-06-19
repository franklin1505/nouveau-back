from rest_framework import serializers

from configurations.models import Vehicle
from courses.models import EstimationTariff, Passenger
from utilisateurs.Auth.serializers import ClientSerializer
from utilisateurs.models import CustomUser
from django.core.exceptions import ValidationError

class EstimationLogIdSerializer(serializers.Serializer):
    estimation_log = serializers.IntegerField()
     
class UpdateTariffSerializer(serializers.Serializer):
    estimation_tariff_id = serializers.IntegerField()
    standard_cost = serializers.FloatField(min_value=0)

class PaymentSerializer(serializers.Serializer):
    estimate_id = serializers.IntegerField()
    payment_method = serializers.IntegerField()
    payment_timing = serializers.ChoiceField(
        choices=[('now', 'Now'), ('later', 'Later')],
        default='later',  # ✅ NOUVEAU - Défaut 'later' pour V1
        help_text="Indique si le paiement sera effectué maintenant ou plus tard"
    )
    code_promo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    compensation = serializers.FloatField(required=False, default=0)
    commission = serializers.FloatField(required=False, default=0)

    def validate(self, data):
        """
        Validation pour s'assurer que compensation et commission ne sont pas tous les deux fournis
        """
        compensation = data.get('compensation', 0)
        commission = data.get('commission', 0)
        
        if compensation and compensation > 0 and commission and commission > 0:
            raise serializers.ValidationError(
                "Vous ne pouvez pas définir à la fois compensation et commission."
            )
        
        return data

class UserChoiceSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    estimation_tariff_id = serializers.IntegerField(required=False, allow_null=True)  # Nouveau champ
    selected_tariff = serializers.IntegerField(allow_null=True, required=False)
    is_standard_cost = serializers.BooleanField(default=False)
    standard_cost = serializers.FloatField(required=False, allow_null=True)
    admin_booking = serializers.BooleanField(default=False)

    def validate(self, data):
        vehicle = Vehicle.objects.get(id=data['vehicle_id'])
        
        try:
            user = self.context['request'].user
            user_type = getattr(user, 'user_type', 'client')
            is_admin = (user_type == 'administrator')
        except (KeyError, AttributeError):
            is_admin = False

        admin_booking = data.get('admin_booking', False)
        
        if admin_booking and not is_admin:
            raise ValidationError("Seuls les administrateurs peuvent utiliser admin_booking.")

        # Valider estimation_tariff_id si fourni
        if data.get('estimation_tariff_id'):
            try:
                tariff = EstimationTariff.objects.get(id=data['estimation_tariff_id'], vehicle_id=data['vehicle_id'])
                if tariff.estimation_log_id != self.context.get('estimation_log_id'):
                    raise ValidationError("L'estimation_tariff_id ne correspond pas à estimation_log_id.")
            except EstimationTariff.DoesNotExist:
                raise ValidationError(f"Le tarif avec l'ID {data['estimation_tariff_id']} n'existe pas pour ce véhicule.")

        if admin_booking and is_admin:
            if vehicle.availability_type == 'on_demand':
                if data.get('standard_cost') is None or data['standard_cost'] <= 0:
                    raise ValidationError("Le tarif de base est obligatoire et doit être supérieur à 0 pour les véhicules on_demand en mode admin.")
                data['is_standard_cost'] = True
            else:
                if data.get('standard_cost') is not None and data['standard_cost'] <= 0:
                    raise ValidationError("Le tarif de base doit être supérieur à 0.")
                if data.get('standard_cost') is not None:
                    data['is_standard_cost'] = True
            return data

        if vehicle.availability_type == 'on_demand':
            if is_admin:
                if data.get('standard_cost') is None or data['standard_cost'] <= 0:
                    raise ValidationError("Le tarif de base est obligatoire et doit être supérieur à 0 pour les véhicules on_demand.")
                data['is_standard_cost'] = True
            else:
                if data.get('standard_cost') is not None and data['standard_cost'] > 0:
                    raise ValidationError("Les clients ne peuvent pas définir un tarif pour les véhicules on_demand.")
                data['standard_cost'] = None
                data['is_standard_cost'] = False
        else:
            if is_admin and data.get('standard_cost') is not None:
                if data['standard_cost'] <= 0:
                    raise ValidationError("Le tarif de base doit être supérieur à 0.")
                data['is_standard_cost'] = True
            elif not is_admin and data.get('standard_cost') is not None:
                raise ValidationError("Les clients ne peuvent pas modifier le tarif des véhicules normaux.")

        return data
  
class PassengerSerializer(serializers.Serializer):
    existing = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=[]
    )
    new = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=[]
    )

    def validate(self, data):
        existing_ids = data.get('existing', [])
        new_passengers = data.get('new', [])

        # Validation des passagers existants
        for passenger_id in existing_ids:
            try:
                Passenger.objects.get(id=passenger_id)
            except Passenger.DoesNotExist:
                raise serializers.ValidationError(f"Le passager avec l'ID {passenger_id} n'existe pas.")

        # Validation des nouveaux passagers
        for passenger in new_passengers:
            if not passenger.get('name') or not passenger.get('phone_number'):
                raise serializers.ValidationError("Le nom et le numéro de téléphone sont requis pour un nouveau passager.")
            
            # ✅ Validation de l'email si fourni
            email = passenger.get('email')
            if email and email.strip():
                # Validation simple de l'email
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, email.strip()):
                    raise serializers.ValidationError(f"L'email '{email}' n'est pas valide pour le passager {passenger.get('name', 'inconnu')}.")

        return data 
   
class EstimateAttributeSerializer(serializers.Serializer):
    attribute = serializers.IntegerField() 
    quantity = serializers.IntegerField()
    
class NewUserSerializer(serializers.Serializer):
    user_type = serializers.CharField(default='client')
    email = serializers.EmailField(allow_blank=True, allow_null=True, required=False)
    first_name = serializers.CharField()
    last_name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    phone_number = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    client_type = serializers.CharField()
    joint_key = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    is_partial = serializers.BooleanField()
    address = serializers.CharField(allow_blank=True,allow_null=True, required=False)

class ClientInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=False)
    new_user = NewUserSerializer(required=False)

    def validate(self, data):
        # Cas 1 : ID fourni
        if 'id' in data:
            try:
                user = CustomUser.objects.get(id=data['id'])
                data['existing_user'] = {
                    "id": user.id,  
                    **ClientSerializer(user).data  
                }
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("L'utilisateur avec cet ID n'existe pas.")
        
        # Cas 2 : Username et password fournis
        elif 'username' in data and 'password' in data:
            # On ne fait pas de validation supplémentaire ici, car la connexion sera gérée dans validate_client_info
            pass
        
        # Cas 3 : Nouvel utilisateur
        elif 'new_user' in data:
            new_user_serializer = NewUserSerializer(data=data['new_user'])
            if not new_user_serializer.is_valid():
                raise serializers.ValidationError(new_user_serializer.errors)
            data['new_user'] = new_user_serializer.validated_data
        
        # Aucun cas valide
        else:
            raise serializers.ValidationError("Informations client invalides. Fournissez un ID, un username/password, ou des données pour un nouvel utilisateur.")

        return data
    
class ClientDisplayDataSerializer(serializers.Serializer):
    user_type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    def get_user_type(self, obj):
        """
        Formate le user_type en utilisant get_client_type_display.
        """
        client_type_display = obj.get("client_type_display", "client")
        return f"client ({client_type_display})"

    def get_name(self, obj):
        return f"{obj.get('first_name', '')} {obj.get('last_name', '')}".strip()

    def get_email(self, obj):
        return obj.get("email", "Non renseigné")

    def get_phone_number(self, obj):
        return obj.get("phone_number", "Non renseigné")

    def get_address(self, obj):
        return obj.get("address", "Non renseigné")

class ClientRequestDataSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False)

class ClientResponseSerializer(serializers.Serializer):
    display_data = ClientDisplayDataSerializer()
    request_data = ClientRequestDataSerializer()

    def to_representation(self, instance):
        """
        Formate les données en fonction du cas (existing_user, logged_user, new_user).
        """
        if 'existing_user' in instance:
            user = instance['existing_user']
            return {
                "display_data": ClientDisplayDataSerializer(user).data,
                "request_data": {"id": user.get("id")}
            }
        elif 'logged_user' in instance:
            user_info = instance['logged_user'].get("data", {}).get("user_info", {})
            return {
                "display_data": ClientDisplayDataSerializer(user_info).data,
                "request_data": {"id": user_info.get("user_id")}
            }
        elif 'new_user' in instance:
            user_data = instance['new_user'].get("data", {})
            return {
                "display_data": ClientDisplayDataSerializer(user_data).data,
                "request_data": {
                    "id": user_data.get("id"),  # Inclure l'ID récupéré
                    "username": user_data.get("username")
                }
            }
        else:
            return {}
        
class PassengerDisplayDataSerializer(serializers.Serializer):
    name = serializers.CharField()
    phone_number = serializers.CharField()

class PassengerResponseSerializer(serializers.Serializer):
    display_data = PassengerDisplayDataSerializer(many=True)
    request_data = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()))

    def to_representation(self, instance):
        return {
            "display_data": [{"name": passenger['name'], "phone_number": passenger['phone_number']} for passenger in instance['display_data']],
            "request_data": {"ids": instance['request_data']}
        }
       
class EstimateAttributeDisplayDataSerializer(serializers.Serializer):
    attribute_name = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2)

class EstimateAttributeResponseSerializer(serializers.Serializer):
    display_data = EstimateAttributeDisplayDataSerializer(many=True)
    request_data = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()))

    def to_representation(self, instance):
        total_attributes_cost = instance.get('total_attributes_cost', 0)
        display_data = [
            {
                "attribute_name": attr['attribute_name'],
                "unit_price": attr['unit_price'],
                "quantity": attr['quantity'],
                "total": attr['total']
            }
            for attr in instance['display_data']
        ]
        # Ajouter le total_attributes_cost à la fin de display_data
        display_data.append({
            "total_attributes_cost": total_attributes_cost
        })

        return {
            "display_data": display_data,
            "request_data": {
                "ids": instance['request_data'].get('ids', []),
                "total_attributes_cost": total_attributes_cost
            }
        }
   

class PassengerListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.CharField(allow_null=True, default="Non renseigné")
    is_main_client = serializers.BooleanField()
    created_at = serializers.DateTimeField()

    def to_representation(self, instance):
        """
        Formate les données du passager pour la réponse.
        """
        representation = super().to_representation(instance)
        representation['created_at'] = instance['created_at'].isoformat()
        return representation