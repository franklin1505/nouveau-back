from rest_framework import serializers

class VehicleCostSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="id")
    availability_type = serializers.CharField(source="availability_type")
    availability_time = serializers.IntegerField(source="availability_time", allow_null=True)
    availability_message = serializers.SerializerMethodField()
    luggage_capacity = serializers.CharField(source="luggage_capacity")
    passenger_capacity = serializers.CharField(source="passenger_capacity")
    image = serializers.CharField(source="image", allow_null=True)
    vehicle_type = serializers.CharField(source="vehicle_type")
    vehicle_name = serializers.CharField(source="vehicle_name")
    pricing = serializers.DictField()

    def get_availability_message(self, obj):
        availability_messages = {
            "immediate": "Le véhicule est disponible immédiatement pour votre prise en charge.",
            "delayed": "Le véhicule sera disponible dans {availability_time} heure(s). Nous vous recommandons d'ajuster l'horaire de votre prise en charge si nécessaire.",
            "on_demand": "Ce véhicule est disponible uniquement sur demande préalable. Veuillez nous contacter pour établir un devis personnalisé et organiser votre prise en charge.",
            "unknown": "Les informations sur la disponibilité de ce véhicule ne sont pas actuellement disponibles. Veuillez nous contacter pour en savoir plus."
        }
        message = availability_messages.get(obj["availability_type"], "Disponibilité non spécifiée.")
        if obj["availability_type"] == "delayed" and obj.get("availability_time") is not None:
            return message.format(availability_time=obj["availability_time"])
        return message

class EstimateSerializer(serializers.Serializer):
    departure_location = serializers.CharField(required=True)
    destination_location = serializers.CharField(required=True)
    pickup_date = serializers.CharField(required=True)
    destinationInputs = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    estimate_type = serializers.CharField(default="simple_transfer")