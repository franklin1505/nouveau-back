from rest_framework import serializers
from courses.models import Booking, Estimate, EstimationLog, Passenger, EstimateAttribute

# Serializers pour les objets liés
class EstimationLogSerializer(serializers.ModelSerializer):
    """Serializer pour EstimationLog avec toutes les données"""
    # 🔍 DEBUG: Ajouter des champs pour vérifier les fuseaux
    pickup_date_debug = serializers.SerializerMethodField()
    
    class Meta:
        model = EstimationLog
        fields = [
            'id', 'departure', 'destination', 'pickup_date', 'pickup_date_debug', 'waypoints',
            'estimate_type', 'created_at', 'is_booked', 'distance_travelled',
            'duration_travelled'
        ]
    
    def get_pickup_date_debug(self, obj):
        """Debug pour voir exactement ce qui est stocké et ce qui est retourné"""
        pickup = obj.pickup_date
        return {
            'raw_value': str(pickup),
            'isoformat': pickup.isoformat(),
            'date_only': pickup.date().isoformat(),
            'time_only': pickup.time().isoformat(),
            'timezone': str(pickup.tzinfo),
            'utc_offset': pickup.utctimetuple()
        }

class PassengerSerializer(serializers.ModelSerializer):
    """Serializer pour Passenger avec les données essentielles"""
    class Meta:
        model = Passenger
        fields = [
            'id', 'name', 'phone_number', 'email', 'is_main_client', 'created_at'
        ]

class EstimateAttributeSerializer(serializers.ModelSerializer):
    """Serializer pour EstimateAttribute avec calculs"""
    unit_price = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()
    
    class Meta:
        model = EstimateAttribute
        fields = ['id', 'quantity', 'unit_price', 'total']

class EstimateSerializer(serializers.ModelSerializer):
    """Serializer pour Estimate avec tous les objets liés"""
    estimation_log = EstimationLogSerializer(read_only=True)
    passengers = PassengerSerializer(many=True, read_only=True)
    estimate_attribute = EstimateAttributeSerializer(many=True, read_only=True)
    
    class Meta:
        model = Estimate
        fields = [
            'id', 'estimation_log', 'flight_number', 'created_at', 'message',
            'total_booking_cost', 'total_attributes_cost', 'number_of_luggages',
            'number_of_passengers', 'case_number', 'is_payment_pending',
            'passengers', 'estimate_attribute'
        ]

class ClientBasicSerializer(serializers.Serializer):
    """Serializer basique pour Client (éviter les imports circulaires)"""
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()

class DriverBasicSerializer(serializers.Serializer):
    """Serializer basique pour Driver"""
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone_number = serializers.CharField()

class PartnerBasicSerializer(serializers.Serializer):
    """Serializer basique pour Partner"""
    id = serializers.IntegerField()
    company_name = serializers.CharField()
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField()

class BookingCompleteSerializer(serializers.ModelSerializer):
    """Serializer complet pour Booking avec toutes les relations"""
    estimate = EstimateSerializer(read_only=True)
    client = ClientBasicSerializer(read_only=True)
    assigned_driver = DriverBasicSerializer(read_only=True)
    assigned_partner = PartnerBasicSerializer(read_only=True)
    
    # Ajout des displays pour les choix
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_status_display = serializers.CharField(source='get_billing_status_display', read_only=True)
    cancellation_status_display = serializers.CharField(source='get_cancellation_status_display', read_only=True)
    payment_timing_display = serializers.CharField(source='get_payment_timing_display', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'created_at',
            # Status et états
            'status', 'status_display',
            'billing_status', 'billing_status_display', 
            'cancellation_status', 'cancellation_status_display',
            'payment_timing', 'payment_timing_display',
            # Flags
            'is_archived', 'is_driver_paid', 'is_partner_paid',
            # Prix et finances
            'driver_sale_price', 'partner_sale_price', 'compensation', 'commission',
            # Relations complètes
            'estimate', 'client', 'assigned_driver', 'assigned_partner'
        ]

class BookingBasicSerializer(serializers.ModelSerializer):
    """Serializer basique pour Booking (pour les listes simples)"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_status_display = serializers.CharField(source='get_billing_status_display', read_only=True)
    
    # Données essentielles de l'estimation
    pickup_date = serializers.SerializerMethodField()
    departure = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'status', 'status_display',
            'billing_status', 'billing_status_display', 'created_at',
            'pickup_date', 'departure', 'destination', 'client_name'
        ]
    
    def get_pickup_date(self, obj):
        if obj.estimate and obj.estimate.estimation_log:
            return obj.estimate.estimation_log.pickup_date
        return None
    
    def get_departure(self, obj):
        if obj.estimate and obj.estimate.estimation_log:
            return obj.estimate.estimation_log.departure
        return None
    
    def get_destination(self, obj):
        if obj.estimate and obj.estimate.estimation_log:
            return obj.estimate.estimation_log.destination
        return None
    
    def get_client_name(self, obj):
        if obj.client:
            return f"{obj.client.first_name} {obj.client.last_name}"
        return None

# Serializers pour les statistiques (inchangés)
class StatusWorkflowItemSerializer(serializers.Serializer):
    """Serializer pour un item du workflow de statut"""
    status = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()

class MainStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques principales"""
    total_bookings = serializers.IntegerField()
    today_bookings = serializers.IntegerField()
    past_bookings = serializers.IntegerField()
    future_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    archived_bookings = serializers.IntegerField()

class GlobalBookingStatisticsSerializer(serializers.Serializer):
    """Serializer pour les statistiques globales"""
    main_stats = MainStatsSerializer()
    status_workflow = StatusWorkflowItemSerializer(many=True)
    
    def to_representation(self, instance):
        """Override pour s'assurer que les données sont correctement structurées"""
        if not isinstance(instance, dict):
            raise serializers.ValidationError("Instance doit être un dictionnaire")
        
        if 'main_stats' not in instance or 'status_workflow' not in instance:
            raise serializers.ValidationError("Instance doit contenir 'main_stats' et 'status_workflow'")
        
        return super().to_representation(instance)

class BookingDetailStatisticsSerializer(serializers.Serializer):
    """Serializer pour les statistiques détaillées"""
    bookings = BookingCompleteSerializer(many=True)  # 🔥 Utiliser le serializer complet
    sub_stats = serializers.DictField()
    pagination = serializers.DictField()
    
class BookingUpdateSerializer(serializers.ModelSerializer):
    """Serializer optimisé pour les mises à jour de Booking"""
    
    # Relations en écriture pour modifications partielles
    estimate = EstimateSerializer(required=False)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'status', 'billing_status', 
            'cancellation_status', 'payment_timing', 'is_archived',
            'is_driver_paid', 'is_partner_paid', 'driver_sale_price',
            'partner_sale_price', 'compensation', 'commission',
            'estimate', 'assigned_driver', 'assigned_partner'
        ]
        read_only_fields = ['id', 'booking_number', 'created_at']
    
    def update(self, instance, validated_data):
        """Custom update avec gestion des relations"""
        estimate_data = validated_data.pop('estimate', None)
        
        # Mise à jour des champs directs du booking
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        
        # Mise à jour de l'estimate si fourni
        if estimate_data and instance.estimate:
            self._update_estimate(instance.estimate, estimate_data)
        
        return instance
    
    def _update_estimate(self, estimate_instance, estimate_data):
        """Mise à jour de l'estimate et ses relations"""
        estimation_log_data = estimate_data.pop('estimation_log', None)
        passengers_data = estimate_data.pop('passengers', None)
        estimate_attributes_data = estimate_data.pop('estimate_attribute', None)
        
        # Mise à jour des champs directs de l'estimate
        for field, value in estimate_data.items():
            setattr(estimate_instance, field, value)
        
        estimate_instance.save()
        
        # Mise à jour de l'estimation_log
        if estimation_log_data and estimate_instance.estimation_log:
            for field, value in estimation_log_data.items():
                setattr(estimate_instance.estimation_log, field, value)
            estimate_instance.estimation_log.save()
        
        # Mise à jour des passengers (simple update des existants)
        if passengers_data:
            for passenger_data in passengers_data:
                passenger_id = passenger_data.get('id')
                if passenger_id:
                    try:
                        passenger = estimate_instance.passengers.get(id=passenger_id)
                        for field, value in passenger_data.items():
                            if field != 'id':
                                setattr(passenger, field, value)
                        passenger.save()
                    except Passenger.DoesNotExist:
                        pass
        
        # Mise à jour des estimate_attributes
        if estimate_attributes_data:
            for attr_data in estimate_attributes_data:
                attr_id = attr_data.get('id')
                if attr_id:
                    try:
                        attribute = estimate_instance.estimate_attribute.get(id=attr_id)
                        for field, value in attr_data.items():
                            if field != 'id':
                                setattr(attribute, field, value)
                        attribute.save()
                    except EstimateAttribute.DoesNotExist:
                        pass