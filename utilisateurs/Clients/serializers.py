from rest_framework import serializers
from utilisateurs.models import Client
from django.db.models import Count

class ClientSerializer(serializers.ModelSerializer):
    """
    Serializer for Client model with basic information.
    """
    client_type_display = serializers.CharField(source='get_client_type_display', read_only=True)
    parent_info = serializers.SerializerMethodField(read_only=True)
    children_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'phone_number',
            'address', 'client_type', 'client_type_display', 'is_partial',
            'parent', 'parent_info', 'joint_key', 'children_count', 'is_active',
            'date_added'
        ]
        read_only_fields = ['username', 'joint_key', 'date_added']

    def get_parent_info(self, obj):
        if obj.parent:
            return {
                'id': obj.parent.id,
                'first_name': obj.parent.first_name,
                'last_name': obj.parent.last_name,
                'client_type': obj.parent.client_type,
                'is_active': obj.parent.is_active,
                'client_type_display': obj.parent.get_client_type_display()
            }
        return None

    def get_children_count(self, obj):
        return obj.children.count()

class ClientDetailSerializer(ClientSerializer):
    """
    Extended serializer for Client model with additional information.
    """
    children = serializers.SerializerMethodField(read_only=True)

    class Meta(ClientSerializer.Meta):
        fields = ClientSerializer.Meta.fields + ['children']

    def get_children(self, obj):
        if obj.client_type in ['agency', 'company']:
            children = obj.children.all()
            return ClientSerializer(children, many=True).data
        return []

class ClientUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating Client information.
    """
    class Meta:
        model = Client
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',
            'address', 'is_partial', 'is_active', 'client_type'
        ]
        
    def validate(self, data):
        """
        Validation spécifique pour la mise à jour du client_type.
        """
        client_type = data.get('client_type')
        instance = self.instance
        
        # Si on change le type de client
        if client_type and instance and instance.client_type != client_type:
            # Vérifier si le client a des enfants et qu'on essaie de changer son type
            if instance.client_type in ['agency', 'company'] and instance.children.exists():
                raise serializers.ValidationError(
                    "Impossible de changer le type de ce client car il a des agents/collaborateurs associés."
                )
                
            # Vérifier si le client est un agent/collaborateur et qu'on essaie de le changer en un type incompatible
            if instance.client_type in ['agency_agent', 'company_collaborator'] and instance.parent:
                if client_type != 'agency_agent' and client_type != 'company_collaborator':
                    raise serializers.ValidationError(
                        "Impossible de changer ce type de client car il est associé à une agence/société. "
                        "Veuillez d'abord le dissocier."
                    )
                
                # Vérifier la compatibilité entre le type de client et le type de parent
                if client_type == 'agency_agent' and instance.parent.client_type != 'agency':
                    raise serializers.ValidationError(
                        "Un agent doit être associé à une agence."
                    )
                if client_type == 'company_collaborator' and instance.parent.client_type != 'company':
                    raise serializers.ValidationError(
                        "Un collaborateur doit être associé à une société."
                    )
        
        return data

class ClientTypeStatisticsSerializer(serializers.Serializer):
    """
    Serializer for client statistics by client type.
    """
    client_type = serializers.CharField()
    client_type_display = serializers.CharField()
    count = serializers.IntegerField()
    partial_count = serializers.IntegerField()
    non_partial_count = serializers.IntegerField()
    search_key = serializers.CharField()

class ClientAssociationSerializer(serializers.Serializer):
    """
    Serializer for associating/dissociating a client with an agency/company.
    
    Association:
    - Valide que le parent existe et est de type 'agency' ou 'company'
    - Vérifie la compatibilité entre le type du client et celui du parent
    - Pour les clients simples, détermine le nouveau type ('agency_agent' ou 'company_collaborator')
    
    Dissociation:
    - Vérifie que le client est de type 'agency_agent' ou 'company_collaborator'
    - La réinitialisation du client (type, joint_key) est gérée dans la vue
    """
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, data):
        parent_id = data.get('parent_id')
        instance = self.context.get('client')
        
        if not instance:
            raise serializers.ValidationError("Client non spécifié.")
            
        # Si on veut dissocier le client (parent_id = null)
        if parent_id is None:
            if instance.client_type not in ['agency_agent', 'company_collaborator']:
                raise serializers.ValidationError(
                    "Seuls les agents et collaborateurs peuvent être dissociés."
                )
            # Pas besoin de validation supplémentaire pour la dissociation
            # Le client sera remis en type 'simple' et sa joint_key sera effacée dans la vue
            return data
            
        # Si on veut associer le client à un parent
        try:
            parent = Client.objects.get(id=parent_id)
        except Client.DoesNotExist:
            raise serializers.ValidationError(f"Le client parent avec l'ID {parent_id} n'existe pas.")
            
        # Vérifier si le parent est une agence ou une société
        if parent.client_type not in ['agency', 'company']:
            raise serializers.ValidationError(
                "Le client parent doit être une agence ou une société."
            )
        
        # Vérifier la compatibilité des types pour les clients déjà agents ou collaborateurs
        if instance.client_type == 'agency_agent' and parent.client_type != 'agency':
            raise serializers.ValidationError("Un agent doit être associé à une agence.")
            
        if instance.client_type == 'company_collaborator' and parent.client_type != 'company':
            raise serializers.ValidationError("Un collaborateur doit être associé à une société.")
        
        # Pour les clients simples, on va changer leur type automatiquement
        # Pour les autres types, on vérifie s'ils peuvent être associés
        if instance.client_type not in ['simple', 'agency_agent', 'company_collaborator']:
            raise serializers.ValidationError(
                "Seuls les clients simples, agents ou collaborateurs peuvent être associés à une agence/société."
            )
            
        data['parent'] = parent
        # Déterminer le nouveau type de client si c'est un client simple
        if instance.client_type == 'simple':
            data['new_client_type'] = 'agency_agent' if parent.client_type == 'agency' else 'company_collaborator'
            # Note: La joint_key du parent sera assignée au client dans la vue
        
        return data
        
    # Note: La méthode update a été supprimée car la logique d'association/dissociation
    # est maintenant entièrement gérée dans la vue ClientAssociationView

class GlobalClientStatisticsSerializer(serializers.Serializer):
    """
    Serializer for global client statistics.
    """
    total_clients = serializers.IntegerField()
    active_clients = serializers.IntegerField()
    inactive_clients = serializers.IntegerField()
    partial_clients_count = serializers.IntegerField()
    client_types = ClientTypeStatisticsSerializer(many=True)
