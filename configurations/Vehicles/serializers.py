from datetime import timedelta
import json
from rest_framework import serializers
from configurations.models import Adjustment, Attribute, MeetingPlace, Package, Price, PromoCode, TariffRule, Vehicle, VehicleType
from django.utils import timezone

class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'description', 'business', 'created_at']

    def update(self, instance, validated_data):
        # Mettre à jour le champ created_at avec la date et l'heure actuelles
        instance.created_at = timezone.now()
        # Mettre à jour les autres champs
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()
        return instance
    

class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Price
        fields = ['price_per_km', 'price_per_duration', 'booking_fee', 'delivery_fee', 'default_fee']



class VehicleSerializer(serializers.ModelSerializer):
    price = PriceSerializer(required=False)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'business', 'vehicle_type', 'brand', 'model', 'manufacture_year',
            'registration_number', 'image', 'validation', 'fuel_type', 'engine',
            'interior_color', 'exterior_color', 'power', 'length', 'transmission',
            'passenger_capacity', 'luggage_capacity', 'base_location', 'availability_type',
            'availability_time', 'price'
        ]
        read_only_fields = ['validation']

    def to_internal_value(self, data):
        # Supporte QueryDict ou dict
        mutable_data = data.copy() if hasattr(data, 'copy') else data  
        price_data = {}

        # Extraction des données de tarification si présentes
        price_keys = ['price_per_km', 'price_per_duration', 'booking_fee', 'delivery_fee', 'default_fee']
        for key in price_keys:
            if key in mutable_data:
                value = mutable_data.pop(key, None)
                # Si value est une liste, on prend le premier élément
                if isinstance(value, list):
                    value = value[0]
                price_data[key] = None if value == '' else value

        # Si 'price' est dans les données, on le traite comme un objet imbriqué
        if 'price' in mutable_data:
            price_data = mutable_data.pop('price', {})
            if not isinstance(price_data, dict):  # Sécurité si 'price' n'est pas un objet
                price_data = {}

        # Valider les données de prix si présentes
        if price_data and any(v is not None for v in price_data.values()):
            price_serializer = PriceSerializer(data=price_data, partial=True)  # Partial pour Price
            price_serializer.is_valid(raise_exception=True)
            validated_price_data = price_serializer.validated_data
        else:
            validated_price_data = None

        # Valider les données de Vehicle
        validated = super().to_internal_value(mutable_data)
        if validated_price_data is not None:
            validated['price'] = validated_price_data

        print("Données internes après désérialisation:", validated)
        return validated

    def update(self, instance, validated_data):
        price_data = validated_data.pop('price', None)

        # Mise à jour des champs de Vehicle
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Mise à jour ou création de Price si fourni
        if price_data is not None:
            if instance.price:
                # Mise à jour partielle de l'objet Price existant
                for attr, value in price_data.items():
                    setattr(instance.price, attr, value)
                instance.price.save()
            else:
                # Création d’un nouvel objet Price si inexistant
                price = Price.objects.create(**price_data)
                instance.price = price

        # Logique de validation (inchangée)
        if instance.business.business_type == 'my_business' and instance.price:
            instance.validation = True
        else:
            instance.validation = False

        instance.save()
        return instance

    def create(self, validated_data):
        price_data = validated_data.pop('price', None)
        vehicle = Vehicle.objects.create(**validated_data)
        if price_data:
            price = Price.objects.create(**price_data)
            vehicle.price = price
        vehicle.validation = vehicle.business.business_type == 'my_business' and bool(vehicle.price)
        vehicle.save()
        return vehicle

class AdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adjustment
        fields = "__all__"

class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = "__all__"

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = "__all__"
        

class TariffRuleViewSerializer(serializers.ModelSerializer):
    # Utiliser les serializers imbriqués pour les objets liés
    promo_code = PromoCodeSerializer(read_only=True)
    package = PackageSerializer(read_only=True)
    adjustment = AdjustmentSerializer(read_only=True)

    specific_clients = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    excluded_clients = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    # Champs calculés pour l'expiration
    expiration_status = serializers.SerializerMethodField()
    days_until_expiration = serializers.SerializerMethodField()

    class Meta:
        model = TariffRule
        fields = [
            "id",
            "name",
            "description",
            "rule_type",
            "action_type",
            "start_date",
            "end_date",
            "days_of_week",
            "specific_hours",
            "application_date",
            "active",
            "priority",
            "available_to_all",
            "specific_clients",
            "excluded_clients",
            "adjustment",
            "package",
            "promo_code",
            "expiration_status",
            "days_until_expiration",
        ]
        
    def get_expiration_status(self, obj):
        """
        Retourne le statut d'expiration de la règle tarifaire.
        Valeurs possibles: 'expired', 'expiring_soon', 'active', 'inactive', 'no_expiration', 'date_specific'
        """
        now = timezone.now()
        current_date = now.date()
        
        if not obj.active:
            return "inactive"
            
        # Vérifier application_date (date spécifique)
        if obj.application_date:
            if obj.application_date < current_date:
                return "expired"
            elif obj.application_date == current_date:
                return "active_today"
            else:
                # Date future
                days_until = (obj.application_date - current_date).days
                if days_until <= 3:
                    return "upcoming_soon"
                return "date_specific"
            
        # Vérifier end_date
        if not obj.end_date:
            return "no_expiration"
            
        if obj.end_date < now:
            return "expired"
            
        # Expiration dans les 3 jours
        if obj.end_date < now + timedelta(days=3):
            return "expiring_soon"
            
        return "active"
    
    def get_days_until_expiration(self, obj):
        """
        Retourne le nombre de jours avant l'expiration de la règle.
        Prend en compte à la fois end_date et application_date.
        Retourne None si pas de date d'expiration.
        Retourne 0 si déjà expirée.
        """
        now = timezone.now()
        current_date = now.date()
        
        # Si application_date est définie, l'utiliser en priorité
        if obj.application_date:
            if obj.application_date < current_date:
                return 0  # Déjà expirée
            
            # Calculer le nombre de jours jusqu'à application_date
            days_until = (obj.application_date - current_date).days
            return days_until
            
        # Sinon, utiliser end_date
        if not obj.end_date:
            return None  # Pas d'expiration
            
        if obj.end_date < now:
            return 0  # Déjà expirée
            
        delta = obj.end_date - now
        return delta.days
        
class TariffRuleSerializer(serializers.ModelSerializer):
    adjustment = AdjustmentSerializer(required=False, allow_null=True)
    package = PackageSerializer(required=False, allow_null=True)
    promo_code = PromoCodeSerializer(required=False, allow_null=True)
    
    # Champs calculés pour l'expiration
    expiration_status = serializers.SerializerMethodField()
    days_until_expiration = serializers.SerializerMethodField()

    class Meta:
        model = TariffRule
        fields = "__all__"
    
    def get_expiration_status(self, obj):
        now = timezone.now()
        current_date = now.date()
        if not obj.active:
            return "inactive"
        if obj.application_date:
            if obj.application_date < current_date:
                return "expired"
            elif obj.application_date == current_date:
                return "active_today"
            else:
                days_until = (obj.application_date - current_date).days
                return "upcoming_soon" if days_until <= 3 else "date_specific"
        if not obj.end_date:
            return "no_expiration"
        if obj.end_date < now:
            return "expired"
        return "expiring_soon" if obj.end_date < now + timedelta(days=3) else "active"
    
    def get_days_until_expiration(self, obj):
        now = timezone.now()
        current_date = now.date()
        if obj.application_date:
            return 0 if obj.application_date < current_date else (obj.application_date - current_date).days
        if not obj.end_date:
            return None
        return 0 if obj.end_date < now else (obj.end_date - now).days

    # Méthode utilitaire pour la création de relations imbriquées
    def _handle_nested_create(self, parent, field_name, nested_data, model_class):
        if nested_data:
            instance = model_class.objects.create(**nested_data)
            setattr(parent, field_name, instance)

    # Méthode utilitaire pour la mise à jour de relations imbriquées
    def _handle_nested_update(self, parent, field_name, nested_data, model_class):
        if nested_data:
            current = getattr(parent, field_name, None)
            model_class.objects.update_or_create(
                pk=current.pk if current else None,
                defaults=nested_data
            )

    def create(self, validated_data):
        # Extraction des champs ManyToMany
        m2m_fields = ['specific_clients', 'excluded_clients']
        m2m_data = {field: validated_data.pop(field, []) for field in m2m_fields}
        
        # Extraction des champs imbriqués et définition des modèles associés
        nested_fields = {
            'adjustment': Adjustment,
            'package': Package,
            'promo_code': PromoCode
        }
        nested_data = {field: validated_data.pop(field, None) for field in nested_fields}
        
        # Création de l'objet principal
        tariff_rule = TariffRule.objects.create(**validated_data)
        
        # Affectation des ManyToMany
        for field, data in m2m_data.items():
            if data:
                getattr(tariff_rule, field).set(data)
                
        # Création des objets imbriqués
        for field, model_class in nested_fields.items():
            self._handle_nested_create(tariff_rule, field, nested_data.get(field), model_class)
        
        tariff_rule.save()
        return tariff_rule

    def update(self, instance, validated_data):
        # Mise à jour des champs ManyToMany
        m2m_fields = ['specific_clients', 'excluded_clients']
        for field in m2m_fields:
            if field in validated_data:
                getattr(instance, field).set(validated_data.pop(field))
                
        # Mise à jour des relations imbriquées
        nested_fields = {
            'adjustment': Adjustment,
            'package': Package,
            'promo_code': PromoCode
        }
        for field, model_class in nested_fields.items():
            if field in validated_data:
                self._handle_nested_update(instance, field, validated_data.pop(field), model_class)
                
        # Mise à jour des autres champs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
 
class TariffRuleStatusSerializer(serializers.ModelSerializer):
    """
    Serializer pour activer, désactiver ou reconfigurer une règle tarifaire.
    """
    class Meta:
        model = TariffRule
        fields = [
            'id', 'active', 'start_date', 'end_date', 'days_of_week',
            'specific_hours', 'application_date', 'priority',
            'specific_clients', 'excluded_clients','available_to_all'
        ]

    def validate(self, data):
        """
        Validation de l'activation, désactivation ou reconfiguration.
        """
        instance = self.instance
        check_date = timezone.now()

        # Vérifier l'activation
        if data.get('active', instance.active):  # Tentative d'activation
            # Vérifier si la période configurée est valide
            if (instance.start_date and check_date < instance.start_date) or \
               (instance.end_date and check_date > instance.end_date) or \
               (instance.application_date and check_date.date() != instance.application_date):
                # Période expirée
                raise serializers.ValidationError(
                    "La règle tarifaire ne peut pas être activée car la période configurée est expirée. "
                    "Veuillez reconfigurer les paramètres pour continuer."
                )

        return data

    def update(self, instance, validated_data):
        """
        Mise à jour des données de la règle tarifaire.
        """
        instance.active = validated_data.get('active', instance.active)
        instance.start_date = validated_data.get('start_date', instance.start_date)
        instance.end_date = validated_data.get('end_date', instance.end_date)
        instance.days_of_week = validated_data.get('days_of_week', instance.days_of_week)
        instance.specific_hours = validated_data.get('specific_hours', instance.specific_hours)
        instance.application_date = validated_data.get('application_date', instance.application_date)
        instance.priority = validated_data.get('priority', instance.priority)
        instance.available_to_all = validated_data.get('available_to_all', instance.available_to_all)
        instance.specific_clients.set(validated_data.get('specific_clients', instance.specific_clients.all()))
        instance.excluded_clients.set(validated_data.get('excluded_clients', instance.excluded_clients.all()))

        instance.save()
        return instance
    
class TariffRuleClientManagementSerializer(serializers.ModelSerializer):
    """
    Serializer pour gérer les clients associés à une règle de tarification.
    """

    class Meta:
        model = TariffRule
        fields = ['id', 'available_to_all', 'specific_clients', 'excluded_clients']

    def validate(self, data):
        """
        Valider les modifications sur les clients associés.
        """
        available_to_all = data.get('available_to_all', self.instance.available_to_all)

        specific_clients = data.get('specific_clients', self.instance.specific_clients.all())
        excluded_clients = data.get('excluded_clients', self.instance.excluded_clients.all())

        if not available_to_all and not (specific_clients or excluded_clients):
            raise serializers.ValidationError(
                "Si 'available_to_all' est défini sur False, au moins un client doit être spécifié dans 'specific_clients' ou 'excluded_clients'."
            )

        return data

class TariffRuleStatsSerializer(serializers.ModelSerializer):
    """
    Serializer pour résumer les données d'une règle tarifaire.
    """
    vehicle = VehicleSerializer(read_only=True)  # Récupère toutes les données du véhicule.

    class Meta:
        model = TariffRule
        fields = [
            "id",
            "name",
            "rule_type",
            "vehicle",
            "start_date",
            "end_date",
            "active",
            "priority",
        ]

class TariffRuleStatisticsSerializer(serializers.Serializer):
    """
    Serializer pour structurer les statistiques des règles tarifaires.
    """
    total_rules = serializers.IntegerField()
    total_adjustments = serializers.IntegerField()
    total_packages = serializers.IntegerField()
    total_promo_codes = serializers.IntegerField()
    active_rules = serializers.IntegerField()
    inactive_rules = serializers.IntegerField()
    rules_for_all_clients = serializers.IntegerField()
    restricted_rules = serializers.IntegerField()
    specific_rules = serializers.IntegerField()
    
    # Statistiques d'expiration
    expiring_soon_count = serializers.IntegerField()
    expiring_soon_rules = TariffRuleStatsSerializer(many=True)  # Inclut les détails des règles proches de l'expiration
    
    # Statistiques liées à application_date
    active_today_count = serializers.IntegerField()  # Règles actives aujourd'hui (application_date == aujourd'hui)
    date_specific_count = serializers.IntegerField()  # Règles avec date spécifique future


class AttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attribute
        fields = ['id', 'business', 'attribute_name', 'unit_price', 'maximum_quantity', 'created_at']
        
    def update(self, instance, validated_data):
        # Mettre à jour le champ created_at avec la date et l'heure actuelles
        instance.created_at = timezone.now()
        # Mettre à jour les autres champs
        instance.attribute_name = validated_data.get('attribute_name', instance.attribute_name)
        instance.unit_price = validated_data.get('unit_price', instance.unit_price)
        instance.maximum_quantity = validated_data.get('maximum_quantity', instance.maximum_quantity)
        instance.save()
        return instance
        
class MeetingPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingPlace
        fields = ['id', 'address', 'created_at']
        read_only_fields = ['created_at']



class VehicleStatsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'brand', 'model', 'registration_number', 'vehicle_type']

class TariffRuleStatsDetailSerializer(serializers.ModelSerializer):
    vehicle = VehicleStatsDetailSerializer(read_only=True)
    
    class Meta:
        model = TariffRule
        fields = ['id', 'name', 'rule_type', 'vehicle', 'start_date', 'end_date', 'active']
        
class StatisticsItemSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    search_key = serializers.CharField()

class GlobalStatisticsSerializer(serializers.Serializer):
    vehicle_stats = serializers.DictField(child=StatisticsItemSerializer())
    tariff_rule_stats = serializers.DictField(child=StatisticsItemSerializer())
