from rest_framework import serializers
from configurations.models import Attribute
from courses.Logs.services import BookingChangeTracker, BookingLogService
from courses.models import Booking, Estimate, EstimationLog, Passenger, EstimateAttribute
from utilisateurs.models import Client, Driver, Partner
from django.db import transaction

class EstimationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstimationLog
        fields = ['id', 'departure', 'destination', 'pickup_date', 'waypoints', 'estimate_type', 'created_at', 'is_booked', 'distance_travelled', 'duration_travelled']

class PassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passenger
        fields = ['id', 'name', 'phone_number', 'email', 'is_main_client', 'created_at']

class EstimateAttributeSerializer(serializers.ModelSerializer):
    unit_price = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()
    class Meta:
        model = EstimateAttribute
        fields = ['id', 'quantity', 'unit_price', 'total']

class EstimateSerializer(serializers.ModelSerializer):
    estimation_log = EstimationLogSerializer(read_only=True)
    passengers = PassengerSerializer(many=True, read_only=True)
    estimate_attribute = EstimateAttributeSerializer(many=True, read_only=True)
    class Meta:
        model = Estimate
        fields = ['id', 'estimation_log', 'flight_number', 'created_at', 'message', 'total_booking_cost', 'total_attributes_cost', 'number_of_luggages', 'number_of_passengers', 'case_number', 'is_payment_pending', 'passengers', 'estimate_attribute']

class ClientBasicSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()

class DriverBasicSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone_number = serializers.CharField()

class PartnerBasicSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_name = serializers.CharField()
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField()

class BookingCompleteSerializer(serializers.ModelSerializer):
    estimate = EstimateSerializer(read_only=True)
    client = ClientBasicSerializer(read_only=True)
    assigned_driver = DriverBasicSerializer(read_only=True)
    assigned_partner = PartnerBasicSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_status_display = serializers.CharField(source='get_billing_status_display', read_only=True)
    cancellation_status_display = serializers.CharField(source='get_cancellation_status_display', read_only=True)
    payment_timing_display = serializers.CharField(source='get_payment_timing_display', read_only=True)
    class Meta:
        model = Booking
        fields = ['id', 'booking_number', 'created_at', 'status', 'status_display', 'billing_status', 'billing_status_display', 'cancellation_status', 'cancellation_status_display', 'payment_timing', 'payment_timing_display', 'is_archived', 'is_driver_paid', 'is_partner_paid', 'driver_sale_price', 'partner_sale_price', 'compensation', 'commission', 'estimate', 'client', 'assigned_driver', 'assigned_partner']

class BookingBasicSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_status_display = serializers.CharField(source='get_billing_status_display', read_only=True)
    pickup_date = serializers.SerializerMethodField()
    departure = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    class Meta:
        model = Booking
        fields = ['id', 'booking_number', 'status', 'status_display', 'billing_status', 'billing_status_display', 'created_at', 'pickup_date', 'departure', 'destination', 'client_name']
    
    def get_pickup_date(self, obj):
        return obj.estimate.estimation_log.pickup_date if obj.estimate and obj.estimate.estimation_log else None
    
    def get_departure(self, obj):
        return obj.estimate.estimation_log.departure if obj.estimate and obj.estimate.estimation_log else None
    
    def get_destination(self, obj):
        return obj.estimate.estimation_log.destination if obj.estimate and obj.estimate.estimation_log else None
    
    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}" if obj.client else None

class StatusWorkflowItemSerializer(serializers.Serializer):
    status = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()

class MainStatsSerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    today_bookings = serializers.IntegerField()
    past_bookings = serializers.IntegerField()
    future_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    archived_bookings = serializers.IntegerField()

class GlobalBookingStatisticsSerializer(serializers.Serializer):
    main_stats = MainStatsSerializer()
    status_workflow = StatusWorkflowItemSerializer(many=True)
    
    def to_representation(self, instance):
        if not isinstance(instance, dict):
            raise serializers.ValidationError("Instance doit être un dictionnaire")
        if 'main_stats' not in instance or 'status_workflow' not in instance:
            raise serializers.ValidationError("Instance doit contenir 'main_stats' et 'status_workflow'")
        return super().to_representation(instance)

class BookingDetailStatisticsSerializer(serializers.Serializer):
    bookings = BookingCompleteSerializer(many=True)
    sub_stats = serializers.DictField()
    pagination = serializers.DictField()

class PassengerUpdateSerializer(serializers.ModelSerializer):
    mode = serializers.ChoiceField(choices=['add', 'update', 'delete'], required=False, default='add')
    id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = Passenger
        fields = ['id', 'name', 'phone_number', 'email', 'is_main_client', 'mode']
        extra_kwargs = {'name': {'required': False}, 'phone_number': {'required': False}, 'is_main_client': {'required': False}}
    
    def validate(self, attrs):
        mode = attrs.get('mode', 'add')
        passenger_id = attrs.get('id')
        if mode in ['update', 'delete'] and (passenger_id is None or not isinstance(passenger_id, int)):
            raise serializers.ValidationError("ID requis et doit être un entier pour les modes 'update' et 'delete'")
        if mode in ['add', 'update']:
            if not attrs.get('name'):
                raise serializers.ValidationError("Nom requis pour les modes 'add' et 'update'")
            if not attrs.get('phone_number'):
                raise serializers.ValidationError("Téléphone requis pour les modes 'add' et 'update'")
        return attrs

class EstimateAttributeUpdateSerializer(serializers.ModelSerializer):
    attribute_id = serializers.IntegerField(required=False)
    mode = serializers.ChoiceField(choices=['add', 'update', 'delete'], required=False, default='add')
    id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = EstimateAttribute
        fields = ['id', 'attribute_id', 'quantity', 'mode']
        extra_kwargs = {'quantity': {'required': False, 'min_value': 1}}
    
    def validate(self, attrs):
        mode = attrs.get('mode', 'add')
        attr_id = attrs.get('id')
        attribute_id = attrs.get('attribute_id')
        if mode in ['update', 'delete'] and (attr_id is None or not isinstance(attr_id, int)):
            raise serializers.ValidationError("ID requis et doit être un entier pour les modes 'update' et 'delete'")
        if mode in ['add', 'update']:
            if not attribute_id:
                raise serializers.ValidationError("attribute_id requis pour les modes 'add' et 'update'")
            if not attrs.get('quantity'):
                raise serializers.ValidationError("Quantité requise pour les modes 'add' et 'update'")
        return attrs

class EstimationLogUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstimationLog
        fields = ['departure', 'destination', 'pickup_date', 'waypoints', 'estimate_type', 'distance_travelled', 'duration_travelled']
        extra_kwargs = {'departure': {'required': False}, 'destination': {'required': False}, 'pickup_date': {'required': False}, 'distance_travelled': {'required': False}, 'duration_travelled': {'required': False}}

class EstimateUpdateSerializer(serializers.ModelSerializer):
    estimation_log = EstimationLogUpdateSerializer(required=False)
    passengers = PassengerUpdateSerializer(many=True, required=False)
    estimate_attribute = EstimateAttributeUpdateSerializer(many=True, required=False)
    class Meta:
        model = Estimate
        fields = ['flight_number', 'message', 'total_booking_cost', 'total_attributes_cost', 'number_of_luggages', 'number_of_passengers', 'case_number', 'is_payment_pending', 'estimation_log', 'passengers', 'estimate_attribute']
    
    def validate_passengers(self, passengers_data):
        validated_passengers = []
        for passenger_data in passengers_data:
            passenger_data_copy = passenger_data.copy()
            passenger_serializer = PassengerUpdateSerializer(data=passenger_data_copy)
            if not passenger_serializer.is_valid():
                raise serializers.ValidationError(passenger_serializer.errors)
            validated_passengers.append(passenger_serializer.validated_data)
        return validated_passengers

class BookingUpdateSerializer(serializers.ModelSerializer):
    estimate = EstimateUpdateSerializer(required=False)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_driver_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_partner_id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = Booking
        fields = ['status', 'billing_status', 'cancellation_status', 'payment_timing', 'is_archived', 'is_driver_paid', 'is_partner_paid', 'driver_sale_price', 'partner_sale_price', 'compensation', 'commission', 'estimate', 'client_id', 'assigned_driver_id', 'assigned_partner_id']
    
    def validate_client_id(self, value):
        if value is not None:
            try:
                Client.objects.get(id=value)
            except Client.DoesNotExist:
                raise serializers.ValidationError("Client introuvable")
        return value
    
    def validate_assigned_driver_id(self, value):
        if value is not None:
            try:
                Driver.objects.get(id=value)
            except Driver.DoesNotExist:
                raise serializers.ValidationError("Chauffeur introuvable")
        return value
    
    def validate_assigned_partner_id(self, value):
        if value is not None:
            try:
                Partner.objects.get(id=value)
            except Partner.DoesNotExist:
                raise serializers.ValidationError("Partenaire introuvable")
        return value
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            estimate_data = validated_data.pop('estimate', None)
            client_id = validated_data.pop('client_id', None)
            assigned_driver_id = validated_data.pop('assigned_driver_id', None)
            assigned_partner_id = validated_data.pop('assigned_partner_id', None)
            
            for field, value in validated_data.items():
                setattr(instance, field, value)
            
            if client_id is not None:
                instance.client = Client.objects.get(id=client_id) if client_id else None
            
            if assigned_driver_id is not None:
                instance.assigned_driver = Driver.objects.get(id=assigned_driver_id) if assigned_driver_id else None
            
            if assigned_partner_id is not None:
                instance.assigned_partner = Partner.objects.get(id=assigned_partner_id) if assigned_partner_id else None
            
            instance.save()
            
            if estimate_data and instance.estimate:
                self._update_estimate_complete(instance.estimate, estimate_data, instance)
            
            instance.refresh_from_db()
            user = self.context['request'].user if hasattr(self, 'context') and 'request' in self.context else BookingLogService.get_current_user()
            BookingChangeTracker.detect_and_log_changes(instance, BookingChangeTracker.capture_booking_state(instance), user)
            return instance

    def _update_estimate_complete(self, estimate_instance, estimate_data, booking_instance):
        relations_modified = False
        estimation_log_data = estimate_data.pop('estimation_log', None)
        passengers_data = estimate_data.pop('passengers', None)
        estimate_attributes_data = estimate_data.pop('estimate_attribute', None)
        
        for field, value in estimate_data.items():
            if getattr(estimate_instance, field) != value:
                relations_modified = True
            setattr(estimate_instance, field, value)
        
        if estimate_data:
            estimate_instance.save()
        
        if estimation_log_data and estimate_instance.estimation_log:
            for field, value in estimation_log_data.items():
                if getattr(estimate_instance.estimation_log, field) != value:
                    relations_modified = True
                setattr(estimate_instance.estimation_log, field, value)
            estimate_instance.estimation_log.save()
        
        if passengers_data is not None:
            relations_modified = True
            self._manage_passengers(estimate_instance, passengers_data, booking_instance)
        
        if estimate_attributes_data is not None:
            relations_modified = True
            self._manage_estimate_attributes(estimate_instance, estimate_attributes_data)
        
        return relations_modified
    
    def _manage_passengers(self, estimate_instance, passengers_data, booking_instance):
        for passenger_data in passengers_data:
            mode = passenger_data.get('mode', 'add')
            passenger_id = passenger_data.get('id')
            if mode == 'add':
                self._add_passenger(estimate_instance, passenger_data, booking_instance)
            elif mode == 'update':
                self._update_passenger(estimate_instance, passenger_data)
            elif mode == 'delete':
                self._delete_passenger(estimate_instance, passenger_id)

    def _add_passenger(self, estimate_instance, passenger_data, booking_instance):
        passenger_create_data = {k: v for k, v in passenger_data.items() if k != 'mode'}
        if booking_instance.client:
            passenger_create_data['client'] = booking_instance.client
        new_passenger = Passenger.objects.create(**passenger_create_data)
        estimate_instance.passengers.add(new_passenger)

    def _update_passenger(self, estimate_instance, passenger_data):
        passenger_id = passenger_data.get('id')
        try:
            passenger = estimate_instance.passengers.get(id=passenger_id)
            for field, value in passenger_data.items():
                if field not in ['id', 'mode']:
                    setattr(passenger, field, value)
            passenger.save()
        except Passenger.DoesNotExist:
            raise serializers.ValidationError(f"Passager avec ID {passenger_id} introuvable")

    def _delete_passenger(self, estimate_instance, passenger_id):
        try:
            passenger = estimate_instance.passengers.get(id=passenger_id)
            estimate_instance.passengers.remove(passenger)
            passenger.delete()
        except Passenger.DoesNotExist:
            raise serializers.ValidationError(f"Passager avec ID {passenger_id} introuvable")

    def _manage_estimate_attributes(self, estimate_instance, attributes_data):
        for attr_data in attributes_data:
            mode = attr_data.get('mode', 'add')
            attr_id = attr_data.get('id')
            if mode == 'add':
                self._add_attribute(estimate_instance, attr_data)
            elif mode == 'update':
                self._update_attribute(estimate_instance, attr_data)
            elif mode == 'delete':
                self._delete_attribute(estimate_instance, attr_id)

    def _add_attribute(self, estimate_instance, attr_data):
        attribute_id = attr_data.get('attribute_id')
        quantity = attr_data.get('quantity')
        try:
            config_attribute = Attribute.objects.get(id=attribute_id)
            new_attr = EstimateAttribute.objects.create(attribute=config_attribute, quantity=quantity)
            estimate_instance.estimate_attribute.add(new_attr)
        except Attribute.DoesNotExist:
            raise serializers.ValidationError(f"Attribut de configuration avec ID {attribute_id} introuvable")

    def _update_attribute(self, estimate_instance, attr_data):
        attr_id = attr_data.get('id')
        attribute_id = attr_data.get('attribute_id')
        quantity = attr_data.get('quantity')
        try:
            estimate_attr = estimate_instance.estimate_attribute.get(id=attr_id)
            if attribute_id:
                config_attribute = Attribute.objects.get(id=attribute_id)
                estimate_attr.attribute = config_attribute
            if quantity:
                estimate_attr.quantity = quantity
            estimate_attr.save()
        except EstimateAttribute.DoesNotExist:
            raise serializers.ValidationError(f"Attribut d'estimation avec ID {attr_id} introuvable")
        except Attribute.DoesNotExist:
            raise serializers.ValidationError(f"Attribut de configuration avec ID {attribute_id} introuvable")

    def _delete_attribute(self, estimate_instance, attr_id):
        try:
            estimate_attr = estimate_instance.estimate_attribute.get(id=attr_id)
            estimate_instance.estimate_attribute.remove(estimate_attr)
            estimate_attr.delete()
        except EstimateAttribute.DoesNotExist:
            raise serializers.ValidationError(f"Attribut avec ID {attr_id} introuvable")