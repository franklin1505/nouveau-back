from rest_framework import serializers

from courses.models import Passenger
from utilisateurs.Auth.serializers import ClientSerializer
from utilisateurs.models import CustomUser

class EstimationLogIdSerializer(serializers.Serializer):
    estimation_log = serializers.IntegerField()

class UserChoiceSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    selected_tariff = serializers.IntegerField(allow_null=True, required=False)
    is_standard_cost = serializers.BooleanField()

class PassengerSerializer(serializers.Serializer):
    existing = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=[]
    )
    new = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        required=False,
        default=[]
    )

    def validate(self, data):
        existing_ids = data.get('existing', [])
        new_passengers = data.get('new', [])

        # Validation des passagers existants
        for passenger_id in existing_ids:
            try:
                Passenger.objects.get(id=passenger_id)  # On utilise le modèle Passenger
            except Passenger.DoesNotExist:
                raise serializers.ValidationError(f"Le passager avec l'ID {passenger_id} n'existe pas.")

        # Validation des nouveaux passagers
        for passenger in new_passengers:
            if not passenger.get('name') or not passenger.get('phone_number'):
                raise serializers.ValidationError("Le nom et le numéro de téléphone sont requis pour un nouveau passager.")

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