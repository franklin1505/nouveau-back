from rest_framework import serializers
from ..models import Administrator
    
class AdministratorUpdateSerializer(serializers.ModelSerializer):
    # Champ write-only pour le mot de passe (non affiché dans la réponse)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Administrator
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def update(self, instance, validated_data):
        # Extraire et traiter le mot de passe s'il est présent dans les données
        password = validated_data.pop('password', None)
        # Mise à jour des autres champs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance