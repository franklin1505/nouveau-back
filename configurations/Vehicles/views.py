from rest_framework import generics, status
from configurations.Vehicles.serializers import AttributeSerializer, GlobalStatisticsSerializer, MeetingPlaceSerializer, TariffRuleClientManagementSerializer, TariffRuleSerializer, TariffRuleStatisticsSerializer, TariffRuleStatsDetailSerializer, TariffRuleStatusSerializer, TariffRuleViewSerializer, VehicleSerializer, VehicleStatsDetailSerializer, VehicleTypeSerializer
from configurations.models import Attribute, MeetingPlace, TariffRule, Vehicle, VehicleType
from rest_framework.permissions import IsAuthenticated, AllowAny
from configurations.helpers import StatsGenerator, create_response
from configurations.pagination import CustomPagination
from rest_framework.views import APIView
from django.utils.timezone import now, timedelta
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count, Q
from django.utils import timezone 
from rest_framework.response import Response


class BaseAPIView:
    """
    Classe de base pour formater les réponses des vues.
    """
    permission_classes = [IsAuthenticated]
    def create_response(self, status_type, message, data=None, http_status=status.HTTP_200_OK, error=None):
        response_payload = {
            "status": status_type,
            "message": message,
            "data": data if data else {},
            "http_status": http_status,
        }
        if error:
            response_payload["error"] = str(error)
        return Response(response_payload, status=http_status)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="List retrieved successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object retrieved successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object created successfully.",
            data=response.data,
            http_status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object updated successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object deleted successfully.",
            http_status=status.HTTP_204_NO_CONTENT
        )
  # CRUD des types de vehicules 
      
class VehicleTypeListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer

class VehicleTypeDetailView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer

        
class AttributeListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = Attribute.objects.all()
    serializer_class = AttributeSerializer

class AttributeDetailView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Attribute.objects.all()
    serializer_class = AttributeSerializer
    
    
class MeetingPlaceListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = MeetingPlace.objects.all()
    serializer_class = MeetingPlaceSerializer

class MeetingPlaceDetailView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = MeetingPlace.objects.all()
    serializer_class = MeetingPlaceSerializer

# CRUD pour gerer les vehicules et les tarifs 
class VehicleListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]  # Modifier ici
    pagination_class = CustomPagination
    parser_classes = [MultiPartParser, FormParser]  # Ajouter les parsers pour gérer multipart/form-data

    def get_queryset(self):
        return Vehicle.objects.all().order_by('id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return create_response(
            status_type="success",
            message="Liste des véhicules récupérée avec succès.",
            data=serializer.data
        )

    def create(self, request, *args, **kwargs):
        print("Données brutes reçues dans la vue:", request.data)  # Log 7 : Données reçues
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save()
        return create_response(
            status_type="success",
            message="Véhicule créé avec succès.",
            data=serializer.data,
            http_status=201
        )

class VehicleRetrieveUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Vehicle.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return create_response(
            status_type="success",
            message="Véhicule récupéré avec succès.",
            data=serializer.data
        )

    def update(self, request, *args, **kwargs):
        partial = True  # Toujours partial pour permettre les mises à jour partielles
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        return create_response(
            status_type="success",
            message="Véhicule mis à jour avec succès.",
            data=serializer.data
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return create_response(
            status_type="success",
            message="Véhicule supprimé avec succès.",
            http_status=204
        )

# CRUD et actions pour la gestion des regles tarifaires 
class TariffRuleListCreateView(generics.ListCreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = TariffRuleSerializer

    def get_queryset(self):
        queryset = TariffRule.objects.select_related('vehicle').all()
        
        # Filtrage par statut d'expiration
        expiration_status = self.request.query_params.get('expiration_status')
        current_date = now()
        current_date_only = current_date.date()
        
        if expiration_status == 'expired':
            # Règles expirées (end_date passée ou application_date passée)
            queryset = queryset.filter(
                Q(end_date__lt=current_date) | 
                Q(application_date__lt=current_date_only)
            )
        elif expiration_status == 'expiring_soon':
            # Règles expirant bientôt (dans les 3 jours)
            expiration_threshold = current_date + timedelta(days=3)
            date_threshold = current_date_only + timedelta(days=3)
            
            queryset = queryset.filter(
                active=True
            ).filter(
                Q(end_date__range=[current_date, expiration_threshold]) |
                Q(application_date__range=[current_date_only, date_threshold])
            )
        elif expiration_status == 'active_today':
            # Règles actives aujourd'hui (application_date == aujourd'hui)
            queryset = queryset.filter(
                active=True,
                application_date=current_date_only
            )
        elif expiration_status == 'active':
            # Règles actives et non expirées
            queryset = queryset.filter(
                active=True
            ).filter(
                Q(end_date__gt=current_date) | Q(end_date__isnull=True)
            ).filter(
                Q(application_date__isnull=True) | Q(application_date=current_date_only)
            )
        elif expiration_status == 'inactive':
            # Règles inactives
            queryset = queryset.filter(active=False)
        elif expiration_status == 'date_specific':
            # Règles avec date spécifique future
            queryset = queryset.filter(
                active=True,
                application_date__gt=current_date_only
            )
            
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Validation additionnelle : priorité unique pour le véhicule
            vehicle_id = serializer.validated_data.get('vehicle').id
            priority = serializer.validated_data.get('priority')
            if TariffRule.objects.filter(vehicle_id=vehicle_id, priority=priority).exists():
                return create_response(
                    status_type="error",
                    message="Une règle avec cette priorité existe déjà pour ce véhicule",
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save()
            return create_response(
                status_type="success",
                message="Règle tarifaire créée avec succès",
                data=serializer.data,
                http_status=status.HTTP_201_CREATED
            )
        return create_response(
            status_type="error",
            message="Échec de la création de la règle tarifaire",
            error=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )
        
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        # Ajouter des informations sur l'expiration
        current_date = now()
        expiration_threshold = current_date + timedelta(days=3)
        
        # Compter les règles par statut d'expiration
        current_date_only = current_date.date()
        date_threshold = current_date_only + timedelta(days=3)
        
        expiration_stats = {
            'total': queryset.count(),
            'expired': queryset.filter(
                Q(end_date__lt=current_date) | 
                Q(application_date__lt=current_date_only)
            ).count(),
            'expiring_soon': queryset.filter(
                active=True
            ).filter(
                Q(end_date__range=[current_date, expiration_threshold]) |
                Q(application_date__range=[current_date_only, date_threshold])
            ).count(),
            'active_today': queryset.filter(
                active=True,
                application_date=current_date_only
            ).count(),
            'active': queryset.filter(
                active=True
            ).filter(
                Q(end_date__gt=expiration_threshold) | Q(end_date__isnull=True)
            ).filter(
                Q(application_date__isnull=True) | Q(application_date=current_date_only)
            ).count(),
            'inactive': queryset.filter(active=False).count(),
            'date_specific': queryset.filter(
                active=True,
                application_date__gt=current_date_only
            ).count(),
        }
        
        return create_response(
            status_type="success",
            message="Liste des règles tarifaires récupérée avec succès",
            data={
                'rules': serializer.data,
                'expiration_stats': expiration_stats
            }
        )

class VehicleTariffRulesView(APIView):
    """
    Vue pour retourner les règles tarifaires liées à un véhicule, avec un comptage par type de règle.
    """
    permission_classes = [AllowAny]
    def get(self, request, vehicle_id):
        try:
            # Récupérer le véhicule par son ID
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return create_response(
                status_type="error",
                message="Véhicule non trouvé.",
                http_status=status.HTTP_404_NOT_FOUND
            )

        # Récupérer toutes les règles tarifaires liées à ce véhicule
        tariff_rules = TariffRule.objects.filter(vehicle=vehicle).select_related(
            "adjustment", "package", "promo_code"
        )

        # Compter le nombre total de règles tarifaires
        total_rules = tariff_rules.count()

        # Compter les règles par type (rule_type)
        rules_by_type = tariff_rules.values('rule_type').annotate(count=Count('id')).order_by('rule_type')

        # Sérialiser les règles tarifaires avec TariffRuleSerializer
        serialized_rules = TariffRuleViewSerializer(tariff_rules, many=True).data

        # Structurer la réponse
        response_data = {
            "vehicle_id": vehicle.id,
            "total_rules": total_rules,
            "rules_by_type": list(rules_by_type),  # Convertir le QuerySet en liste
            "tariff_rules": serialized_rules,
        }

        # Retourner la réponse formatée
        return create_response(
            status_type="success",
            message="Règles tarifaires récupérées avec succès.",
            data=response_data,
            http_status=status.HTTP_200_OK
        )

class TariffRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TariffRule.objects.all()
    serializer_class = TariffRuleSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return create_response(
            status_type="success",
            message="Détails de la règle tarifaire récupérés avec succès",
            data=serializer.data
        )

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            new_priority = serializer.validated_data.get('priority', instance.priority)
            new_vehicle = serializer.validated_data.get('vehicle', instance.vehicle)
            if new_priority != instance.priority or new_vehicle != instance.vehicle:
                if TariffRule.objects.filter(vehicle_id=new_vehicle.id, priority=new_priority).exclude(id=instance.id).exists():
                    return create_response(
                        status_type="error",
                        message="Une règle avec cette priorité existe déjà pour ce véhicule",
                        http_status=status.HTTP_400_BAD_REQUEST
                    )
                    
            # Ici, on permet l'activation même si la date de début est dans le futur
            if serializer.validated_data.get('active', False):
                check_date = timezone.now()
                # On vérifie uniquement la date de fin et d'application
                if instance.end_date and check_date > instance.end_date:
                    return create_response(
                        status_type="error",
                        message="La période configurée est expirée.",
                        http_status=status.HTTP_400_BAD_REQUEST
                    )
                if instance.application_date and check_date.date() != instance.application_date:
                    return create_response(
                        status_type="error",
                        message="La date d'application ne correspond pas à la date actuelle.",
                        http_status=status.HTTP_400_BAD_REQUEST
                    )
            if 'available_to_all' in serializer.validated_data and not serializer.validated_data['available_to_all']:
                specific_clients = serializer.validated_data.get('specific_clients', None)
                excluded_clients = serializer.validated_data.get('excluded_clients', None)
                if specific_clients is not None and excluded_clients is not None and not specific_clients and not excluded_clients:
                    return create_response(
                        status_type="error",
                        message="Si 'available_to_all' est défini sur False, au moins un client doit être spécifié dans 'specific_clients' ou 'excluded_clients'.",
                        http_status=status.HTTP_400_BAD_REQUEST
                    )
            serializer.save()
            return create_response(
                status_type="success",
                message="Règle tarifaire mise à jour avec succès",
                data=serializer.data
            )
        return create_response(
            status_type="error",
            message="Échec de la mise à jour de la règle tarifaire",
            error=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return create_response(
            status_type="success",
            message="Règle tarifaire supprimée avec succès",
            http_status=status.HTTP_204_NO_CONTENT
        )

class TariffRuleStatisticsView(APIView):
    """
    Vue pour générer des statistiques sur les règles tarifaires.
    """

    def get(self, request, *args, **kwargs):
        try:
            current_date = now()
            expiration_threshold = current_date + timedelta(days=3)

            # Calcul des statistiques
            current_date_only = current_date.date()
            date_threshold = current_date_only + timedelta(days=3)
            
            # Règles expirant bientôt (end_date ou application_date)
            expiring_soon_rules = TariffRule.objects.filter(
                active=True
            ).filter(
                Q(end_date__range=[current_date, expiration_threshold]) |
                Q(application_date__range=[current_date_only, date_threshold])
            ).order_by('end_date', 'application_date')
            
            stats = {
                "total_rules": TariffRule.objects.count(),
                "total_adjustments": TariffRule.objects.filter(rule_type="adjustment").count(),
                "total_packages": TariffRule.objects.filter(rule_type="package").count(),
                "total_promo_codes": TariffRule.objects.filter(rule_type="promo_code").count(),
                "active_rules": TariffRule.objects.filter(active=True).count(),
                "inactive_rules": TariffRule.objects.filter(active=False).count(),
                "rules_for_all_clients": TariffRule.objects.filter(available_to_all=True).count(),
                "restricted_rules": TariffRule.objects.filter(available_to_all=False).count(),
                "specific_rules": TariffRule.objects.filter(specific_clients__isnull=False).distinct().count(),
                "expiring_soon_count": expiring_soon_rules.count(),
                "expiring_soon_rules": expiring_soon_rules,
                "active_today_count": TariffRule.objects.filter(
                    active=True,
                    application_date=current_date_only
                ).count(),
                "date_specific_count": TariffRule.objects.filter(
                    active=True,
                    application_date__gt=current_date_only
                ).count(),
            }

            # Sérialisation des données
            serializer = TariffRuleStatisticsSerializer(stats)
            return create_response(
                status_type="success",
                message="Statistiques des règles tarifaires récupérées avec succès.",
                data=serializer.data
            )

        except Exception as e:
            # Gérer toute exception imprévue
            return create_response(
                status_type="error",
                message="Une erreur s'est produite lors de la récupération des statistiques.",
                error=str(e),
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GlobalStatisticsView(APIView):
    def get(self, request):
        try:
            generator = StatsGenerator()
            
            stats_data = {
                'vehicle_stats': generator.get_vehicle_stats(),
                'tariff_rule_stats': generator.get_tariff_rule_stats()
            }
            
            serializer = GlobalStatisticsSerializer(stats_data)
            return create_response(
                status_type='success',
                message='Statistiques récupérées avec succès',
                data=serializer.data
            )
        except Exception as e:
            return create_response(
                status_type='error',
                message='Erreur lors de la récupération des statistiques',
                error=str(e),
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StatisticsDetailView(APIView):
    def get(self, request):
        search_key = request.query_params.get('search_key')
        if not search_key:
            return create_response(
                status_type='error',
                message='Clé de recherche manquante',
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        generator = StatsGenerator()
        query = generator.search_keys.get(search_key)
        
        if not query:
            return create_response(
                status_type='error',
                message='Clé de recherche invalide',
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        serializer_class = (
            VehicleStatsDetailSerializer if search_key.startswith('v_') 
            else TariffRuleStatsDetailSerializer
        )
            
        data = serializer_class(query, many=True).data
        return create_response(
            status_type='success',
            message='Détails récupérés avec succès',
            data=data
        )
