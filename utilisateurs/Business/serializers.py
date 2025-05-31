from rest_framework import serializers
from ..models import Business, Contact, Administrator, Partner
from django.db import transaction
import json

class ContactSerializer(serializers.ModelSerializer):
    """
    Serializer pour le modèle Contact.
    """
    class Meta:
        model = Contact
        fields = '__all__'  

class AdministratorSerializer(serializers.ModelSerializer):
    """
    Serializer pour le modèle Administrator.
    """
    class Meta:
        model = Administrator
        exclude = ('password', 'otp_code', 'otp_expires_at',)
        
class PartnerSerializer(serializers.ModelSerializer):
    """
    Serializer pour le modèle Partner.
    """
    class Meta:
        model = Partner
        exclude = ('password', 'otp_code', 'otp_expires_at',)
        

class JSONContactsField(serializers.Field):
    def to_internal_value(self, data):
        # Si data est une chaîne, la convertir en liste d'objets
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    self.fail("Expected a list of contacts.")
                return parsed
            except json.JSONDecodeError:
                self.fail("Invalid JSON format for contacts.")
        # Si data est déjà une liste, la retourner directement
        elif isinstance(data, list):
            return data
        else:
            self.fail("Invalid type for contacts; expected list or JSON string.")

    def to_representation(self, value):
        # value est une relation many-to-many
        serializer = ContactSerializer(value, many=True)
        return serializer.data
    
    
class BusinessSerializer(serializers.ModelSerializer):
    # Utilisation du champ personnalisé pour gérer le JSON
    contacts = JSONContactsField(required=False)
    main_user = AdministratorSerializer(read_only=True)
    partner = PartnerSerializer(read_only=True)

    class Meta:
        model = Business
        fields = '__all__'

    def update(self, instance, validated_data):
        with transaction.atomic():
            # Extraire les données pour contacts (maintenant converties en liste)
            contacts_data = validated_data.pop('contacts', None)
            
            # Mise à jour des autres champs
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Mise à jour des contacts si des données sont envoyées
            if contacts_data is not None:
                contact_ids = []
                for contact_data in contacts_data:
                    # Si un id est présent, on met à jour ou crée
                    if 'id' in contact_data:
                        obj, created = Contact.objects.update_or_create(
                            id=contact_data['id'],
                            defaults=contact_data
                        )
                    else:
                        obj = Contact.objects.create(**contact_data)
                    contact_ids.append(obj.id)
                # Réaffecter la liste complète des contacts à l'instance
                instance.contacts.set(contact_ids)
            return instance