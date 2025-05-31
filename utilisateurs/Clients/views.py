from django.db.models import Count
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utilisateurs.helpers import create_response
from utilisateurs.models import Client
from utilisateurs.Clients.serializers import (
    ClientAssociationSerializer,
    ClientSerializer,
    ClientDetailSerializer,
    ClientUpdateSerializer,
    ClientTypeStatisticsSerializer,
    GlobalClientStatisticsSerializer
)

class ClientListView(generics.ListAPIView):
    """
    View to retrieve a list of all clients.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Client.objects.all().order_by('client_type', 'first_name')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Count clients by type
        client_type_counts = {}
        for client_type, client_type_display in Client.CLIENT_TYPES:
            count = queryset.filter(client_type=client_type).count()
            client_type_counts[client_type] = {
                'count': count,
                'display': client_type_display
            }
        
        serializer = self.get_serializer(queryset, many=True)
        
        response_data = {
            'clients': serializer.data,
            'client_type_counts': client_type_counts,
            'total_count': queryset.count()
        }
        
        return create_response(
            status_type="success",
            message="Liste des clients récupérée avec succès",
            data=response_data
        )

class ClientDetailView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update detailed information about a specific client.
    """
    permission_classes = [IsAuthenticated]
    queryset = Client.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ClientUpdateSerializer
        return ClientDetailSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return create_response(
            status_type="success",
            message="Détails du client récupérés avec succès",
            data=serializer.data
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            # Return the full client details after update
            detail_serializer = ClientDetailSerializer(instance)
            return create_response(
                status_type="success",
                message="Client mis à jour avec succès",
                data=detail_serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de la mise à jour du client",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class ClientUpdateView(generics.UpdateAPIView):
    """
    View to update client information.
    """
    serializer_class = ClientUpdateSerializer
    permission_classes = [IsAuthenticated]
    queryset = Client.objects.all()
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            # Return the full client details after update
            detail_serializer = ClientDetailSerializer(instance)
            return create_response(
                status_type="success",
                message="Client mis à jour avec succès",
                data=detail_serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de la mise à jour du client",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class ClientActivationView(APIView):
    """
    View to activate or deactivate a client account.
    
    Pour les clients de type 'agency' ou 'company':
    - Lors de la désactivation: désactive également tous les agents/collaborateurs associés
    - Lors de l'activation: peut activer uniquement le client ou le client avec tous ses agents/collaborateurs
      selon le paramètre 'with_children' (true/false)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            client = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return create_response(
                status_type="error",
                message="Client non trouvé",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        # Récupérer l'action à effectuer (activer ou désactiver)
        action = request.data.get('action')
        
        if action not in ['activate', 'deactivate']:
            return create_response(
                status_type="error",
                message="Action non valide. Utilisez 'activate' ou 'deactivate'.",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si c'est une activation ou désactivation
        is_activation = (action == 'activate')
        
        # Mettre à jour le statut du client
        client.is_active = is_activation
        client.save()
        
        # Statistiques pour le rapport
        affected_children_count = 0
        
        # Traitement spécial pour les agences et sociétés
        if client.client_type in ['agency', 'company']:
            # Pour la désactivation: toujours désactiver tous les agents/collaborateurs
            if not is_activation:
                children = client.children.all()
                for child in children:
                    child.is_active = False
                    child.save()
                    affected_children_count += 1
            
            # Pour l'activation: vérifier si on doit activer les agents/collaborateurs
            elif is_activation and request.data.get('with_children') == 'true':
                children = client.children.all()
                for child in children:
                    child.is_active = True
                    child.save()
                    affected_children_count += 1
        
        # Préparer le message de réponse
        action_text = "activé" if is_activation else "désactivé"
        
        # Ajouter des informations sur les agents/collaborateurs affectés si nécessaire
        children_message = ""
        if affected_children_count > 0:
            children_text = "agents" if client.client_type == 'agency' else "collaborateurs"
            children_message = f" ({affected_children_count} {children_text} également {action_text}s)"
        
        serializer = ClientSerializer(client)
        return create_response(
            status_type="success",
            message=f"Client {action_text} avec succès{children_message}",
            data=serializer.data
        )


class ClientAssociationView(APIView):
    """
    View to associate or dissociate a client with an agency/company.
    
    Association:
    - Si le client est de type 'simple', son type est changé en 'agency_agent' ou 'company_collaborator'
    - Le client est lié au parent (agence ou société)
    - La joint_key du parent est assignée au client
    
    Dissociation:
    - Le client est détaché de son parent
    - Son type est remis à 'simple'
    - Sa joint_key est effacée
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            client = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return create_response(
                status_type="error",
                message="Client non trouvé",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ClientAssociationSerializer(data=request.data, context={'client': client})
        
        if serializer.is_valid():
            parent_id = serializer.validated_data.get('parent_id')
            
            # Dissocier le client
            if parent_id is None:
                old_parent = client.parent
                # Réinitialiser le client
                client.parent = None
                client.joint_key = None
                client.client_type = 'simple'  # Remettre en client simple
                client.save()
                
                return create_response(
                    status_type="success",
                    message=f"Client dissocié avec succès de {old_parent.first_name} {old_parent.last_name} et remis en client simple",
                    data=ClientSerializer(client).data
                )
            
            # Associer le client
            parent = serializer.validated_data.get('parent')
            new_client_type = serializer.validated_data.get('new_client_type')
            
            # Si c'est un client simple, on change son type
            if new_client_type:
                old_type = client.get_client_type_display()
                client.client_type = new_client_type
                new_type = client.get_client_type_display()
                type_change_message = f" (changé de '{old_type}' à '{new_type}')"
            else:
                type_change_message = ""
                
            client.parent = parent
            # Ajouter la joint_key du parent
            client.joint_key = parent.joint_key
            client.save()
            
            return create_response(
                status_type="success",
                message=f"Client associé avec succès à {parent.first_name} {parent.last_name}{type_change_message}",
                data=ClientSerializer(client).data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de l'association/dissociation du client",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class GlobalClientStatisticsView(APIView):
    """
    View to get global statistics about clients.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get all clients
        clients = Client.objects.all()
        
        # Count total, active, and inactive clients
        total_clients = clients.count()
        active_clients = clients.filter(is_active=True).count()
        inactive_clients = clients.filter(is_active=False).count()
        
        # Count total partial clients
        partial_clients_count = clients.filter(is_partial=True).count()
        
        # Count clients by type
        client_types_data = []
        for client_type, client_type_display in Client.CLIENT_TYPES:
            # Compter tous les clients de ce type
            count = clients.filter(client_type=client_type).count()
            
            # Compter les clients partiels de ce type
            partial_count = clients.filter(client_type=client_type, is_partial=True).count()
            
            # Compter les clients non partiels de ce type
            non_partial_count = clients.filter(client_type=client_type, is_partial=False).count()
            
            client_types_data.append({
                'client_type': client_type,
                'client_type_display': client_type_display,
                'count': count,
                'partial_count': partial_count,
                'non_partial_count': non_partial_count,
                'search_key': f'client_type_{client_type}'
            })
        
        # Prepare statistics data
        statistics_data = {
            'total_clients': total_clients,
            'active_clients': active_clients,
            'inactive_clients': inactive_clients,
            'partial_clients_count': partial_clients_count,
            'client_types': client_types_data
        }
        
        serializer = GlobalClientStatisticsSerializer(statistics_data)
        return create_response(
            status_type="success",
            message="Statistiques des clients récupérées avec succès",
            data=serializer.data
        )
        
class ClientStatisticsDetailView(APIView):
    """
    View to get detailed statistics about clients based on a search key.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        search_key = request.query_params.get('search_key')
        
        if not search_key:
            return create_response(
                status_type="error",
                message="Clé de recherche manquante",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse the search key to get the client type
        if search_key.startswith('client_type_'):
            client_type = search_key.replace('client_type_', '')
            
            # Vérifier si on demande spécifiquement les clients partiels ou non partiels
            is_partial = request.query_params.get('is_partial')
            
            # Filtrer les clients selon le type et éventuellement selon is_partial
            if is_partial is not None:
                is_partial_bool = is_partial.lower() == 'true'
                clients = Client.objects.filter(client_type=client_type, is_partial=is_partial_bool)
                partial_status = "partiels" if is_partial_bool else "non partiels"
            else:
                clients = Client.objects.filter(client_type=client_type)
                partial_status = ""
            
            if not clients.exists():
                # Au lieu de retourner une erreur 404, on renvoie une réponse de succès avec une liste vide.
                return create_response(
                    status_type="success",
                    message=f"Aucun client {partial_status} trouvé pour le type {client_type}",
                    data=[],  # ou data=None selon vos préférences
                    http_status=status.HTTP_200_OK
                )
            
            serializer = ClientSerializer(clients, many=True)
            return create_response(
                status_type="success",
                message=f"Liste des clients {partial_status} de type {client_type} récupérée avec succès",
                data=serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Clé de recherche invalide",
            http_status=status.HTTP_400_BAD_REQUEST
        )
