from django.db.models import Count
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utilisateurs.helpers import create_response
from utilisateurs.models import Driver, Business
from utilisateurs.Drivers.serializers import (
    DriverSerializer,
    DriverDetailSerializer,
    DriverUpdateSerializer,
    DriverBusinessAssociationSerializer,
    DriverStatisticsSerializer,
    GlobalDriverStatisticsSerializer
)

class DriverListView(generics.ListAPIView):
    """
    View to retrieve a list of all drivers.
    """
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Driver.objects.all().order_by('is_independent', 'first_name')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Count drivers by status
        driver_status_counts = {
            'independent': queryset.filter(is_independent=True).count(),
            'business_linked': queryset.filter(is_independent=False).count(),
            'active': queryset.filter(is_active=True).count(),
            'inactive': queryset.filter(is_active=False).count()
        }
        
        serializer = self.get_serializer(queryset, many=True)
        
        response_data = {
            'drivers': serializer.data,
            'driver_status_counts': driver_status_counts,
            'total_count': queryset.count()
        }
        
        return create_response(
            status_type="success",
            message="Liste des chauffeurs récupérée avec succès",
            data=response_data
        )

class DriverDetailView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update detailed information about a specific driver.
    """
    permission_classes = [IsAuthenticated]
    queryset = Driver.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DriverUpdateSerializer
        return DriverDetailSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return create_response(
            status_type="success",
            message="Détails du chauffeur récupérés avec succès",
            data=serializer.data
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            # Return the full driver details after update
            detail_serializer = DriverDetailSerializer(instance)
            return create_response(
                status_type="success",
                message="Chauffeur mis à jour avec succès",
                data=detail_serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de la mise à jour du chauffeur",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class DriverUpdateView(generics.UpdateAPIView):
    """
    View to update driver information.
    """
    serializer_class = DriverUpdateSerializer
    permission_classes = [IsAuthenticated]
    queryset = Driver.objects.all()
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            # Return the full driver details after update
            detail_serializer = DriverDetailSerializer(instance)
            return create_response(
                status_type="success",
                message="Chauffeur mis à jour avec succès",
                data=detail_serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de la mise à jour du chauffeur",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class DriverActivationView(APIView):
    """
    View to activate/deactivate or validate/invalidate a driver account.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            driver = Driver.objects.get(pk=pk)
        except Driver.DoesNotExist:
            return create_response(
                status_type="error",
                message="Chauffeur non trouvé",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        # Récupérer l'action à effectuer
        action = request.data.get('action')
        
        if action not in ['activate', 'deactivate', 'validate', 'invalidate']:
            return create_response(
                status_type="error",
                message="Action non valide. Utilisez 'activate', 'deactivate', 'validate' ou 'invalidate'.",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mettre à jour le statut du chauffeur
        if action in ['activate', 'deactivate']:
            is_activation = (action == 'activate')
            driver.is_active = is_activation
            action_text = "activé" if is_activation else "désactivé"
        else:
            is_validation = (action == 'validate')
            driver.is_validated = is_validation
            action_text = "validé" if is_validation else "invalidé"
        
        driver.save()
        
        serializer = DriverSerializer(driver)
        return create_response(
            status_type="success",
            message=f"Chauffeur {action_text} avec succès",
            data=serializer.data
        )

class DriverBusinessAssociationView(APIView):
    """
    View to associate or dissociate a driver with a business.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            driver = Driver.objects.get(pk=pk)
        except Driver.DoesNotExist:
            return create_response(
                status_type="error",
                message="Chauffeur non trouvé",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DriverBusinessAssociationSerializer(data=request.data, context={'driver': driver})
        
        if serializer.is_valid():
            business_id = serializer.validated_data.get('business_id')
            
            # Dissocier le chauffeur
            if business_id is None:
                old_business = driver.business
                old_business_name = old_business.name if old_business else "aucun business"
                
                # Réinitialiser le chauffeur
                driver.business = None
                driver.is_independent = True
                driver.save()
                
                return create_response(
                    status_type="success",
                    message=f"Chauffeur dissocié avec succès de {old_business_name} et remis en indépendant",
                    data=DriverSerializer(driver).data
                )
            
            # Associer le chauffeur
            business = serializer.validated_data.get('business')
            
            # Sauvegarder l'ancien statut pour le message
            was_independent = driver.is_independent
            old_business = driver.business
            
            driver.business = business
            driver.is_independent = False
            driver.save()
            
            # Préparer le message de réponse
            if was_independent:
                status_change = " (changé d'indépendant à lié à une entreprise)"
            elif old_business:
                status_change = f" (transféré de {old_business.name})"
            else:
                status_change = ""
                
            return create_response(
                status_type="success",
                message=f"Chauffeur associé avec succès à {business.name}{status_change}",
                data=DriverSerializer(driver).data
            )
        
        return create_response(
            status_type="error",
            message="Erreur lors de l'association/dissociation du chauffeur",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class GlobalDriverStatisticsView(APIView):
    """
    View to get global statistics about drivers.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get all drivers
        drivers = Driver.objects.all()
        
        # Count total, active, and inactive drivers
        total_drivers = drivers.count()
        active_drivers = drivers.filter(is_active=True).count()
        inactive_drivers = drivers.filter(is_active=False).count()
        
        # Count independent vs business-linked drivers
        independent_drivers = drivers.filter(is_independent=True).count()
        business_drivers = drivers.filter(is_independent=False).count()
        
        # Count validated vs non-validated drivers
        validated_drivers = drivers.filter(is_validated=True).count()
        non_validated_drivers = drivers.filter(is_validated=False).count()
        
        # Count drivers by status type
        driver_status_data = []
        status_types = [
            ('active', 'Chauffeurs Actifs', active_drivers),
            ('inactive', 'Chauffeurs Inactifs', inactive_drivers),
            ('independent', 'Chauffeurs Indépendants', independent_drivers),
            ('business_linked', 'Chauffeurs liés à une entreprise', business_drivers),
            ('validated', 'Chauffeurs Validés', validated_drivers),
            ('non_validated', 'Chauffeurs Non Validés', non_validated_drivers),
        ]
        
        for status_type, status_display, count in status_types:
            driver_status_data.append({
                'status_type': status_type,
                'status_display': status_display,
                'count': count,
                'search_key': f'driver_status_{status_type}'
            })
        
        # Prepare statistics data
        statistics_data = {
            'total_drivers': total_drivers,
            'active_drivers': active_drivers,
            'inactive_drivers': inactive_drivers,
            'independent_drivers': independent_drivers,
            'business_drivers': business_drivers,
            'validated_drivers': validated_drivers,
            'non_validated_drivers': non_validated_drivers,
            'driver_statistics': driver_status_data
        }
        
        serializer = GlobalDriverStatisticsSerializer(statistics_data)
        return create_response(
            status_type="success",
            message="Statistiques des chauffeurs récupérées avec succès",
            data=serializer.data
        )

class DriverStatisticsDetailView(APIView):
    """
    View to get detailed statistics about drivers based on a search key.
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
        
        # Parse the search key to get the driver status
        if search_key.startswith('driver_status_'):
            status_type = search_key.replace('driver_status_', '')
            
            # Filter drivers based on status type
            drivers = Driver.objects.all()
            
            if status_type == 'active':
                filtered_drivers = drivers.filter(is_active=True)
                status_name = "actifs"
            elif status_type == 'inactive':
                filtered_drivers = drivers.filter(is_active=False)
                status_name = "inactifs"
            elif status_type == 'independent':
                filtered_drivers = drivers.filter(is_independent=True)
                status_name = "indépendants"
            elif status_type == 'business_linked':
                filtered_drivers = drivers.filter(is_independent=False)
                status_name = "liés à une entreprise"
            elif status_type == 'validated':
                filtered_drivers = drivers.filter(is_validated=True)
                status_name = "validés"
            elif status_type == 'non_validated':
                filtered_drivers = drivers.filter(is_validated=False)
                status_name = "non validés"
            else:
                return create_response(
                    status_type="error",
                    message="Type de statut invalide",
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            if not filtered_drivers.exists():
                # Au lieu de retourner une erreur 404, on renvoie une réponse de succès avec une liste vide.
                return create_response(
                    status_type="success",
                    message=f"Aucun chauffeur {status_name} trouvé",
                    data=[],  # ou data=None selon vos préférences
                    http_status=status.HTTP_200_OK
                )
            
            serializer = DriverSerializer(filtered_drivers, many=True)
            return create_response(
                status_type="success",
                message=f"Liste des chauffeurs {status_name} récupérée avec succès",
                data=serializer.data
            )
        
        return create_response(
            status_type="error",
            message="Clé de recherche invalide",
            http_status=status.HTTP_400_BAD_REQUEST
        )