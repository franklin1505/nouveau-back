from django.utils import timezone
from rest_framework import serializers
from configurations.models import Attribute
from courses.Logs.services import BookingChangeTracker, BookingLogService
from courses.Reservations.Reservations_details.helpers import DataSerializer
from courses.models import Booking, BookingSegment, Estimate, EstimationLog, Passenger, EstimateAttribute
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

class StatusWorkflowItemSerializer(serializers.Serializer):
    status = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()

class RecurringInfoSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    template_name = serializers.CharField()
    recurrence_type = serializers.CharField()
    recurrence_type_display = serializers.CharField()
    occurrence_number = serializers.IntegerField()
    is_active = serializers.BooleanField()
    monthly_type = serializers.CharField(required=False, allow_null=True)
    monthly_type_display = serializers.CharField(required=False, allow_null=True)
    custom_pattern = serializers.CharField(required=False, allow_null=True)
    custom_pattern_display = serializers.CharField(required=False, allow_null=True)

class RecurringWorkflowItemSerializer(serializers.Serializer):
    status = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()
    level = serializers.IntegerField(default=1)
    parent_key = serializers.CharField(required=False, allow_null=True)

class ExtendedMainStatsSerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    today_bookings = serializers.IntegerField()
    past_bookings = serializers.IntegerField()
    future_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    recurring_bookings = serializers.IntegerField()
    archived_bookings = serializers.IntegerField()

class ExtendedGlobalBookingStatisticsSerializer(serializers.Serializer):
    main_stats = ExtendedMainStatsSerializer()
    status_workflow = StatusWorkflowItemSerializer(many=True)
    recurring_workflow = RecurringWorkflowItemSerializer(many=True, required=False)
    recurring_monthly_workflow = RecurringWorkflowItemSerializer(many=True, required=False)
    recurring_custom_workflow = RecurringWorkflowItemSerializer(many=True, required=False)

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            raise serializers.ValidationError("Instance must be a dictionary")
        for field in ['main_stats', 'status_workflow']:
            if field not in instance:
                raise serializers.ValidationError(f"Instance must contain '{field}'")
        return super().to_representation(instance)

class BookingSegmentSerializer(serializers.ModelSerializer):
    departure = serializers.ReadOnlyField()
    destination = serializers.ReadOnlyField()
    pickup_date = serializers.ReadOnlyField()
    distance_travelled = serializers.ReadOnlyField()
    duration_travelled = serializers.ReadOnlyField()
    vehicle = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    meeting_place = serializers.SerializerMethodField()
    flight_number = serializers.CharField(source='estimate.flight_number', read_only=True)
    message = serializers.CharField(source='estimate.message', read_only=True)
    number_of_luggages = serializers.CharField(source='estimate.number_of_luggages', read_only=True)
    number_of_passengers = serializers.IntegerField(source='estimate.number_of_passengers', read_only=True)

    class Meta:
        model = BookingSegment
        fields = ['id', 'segment_type', 'status', 'segment_cost', 'compensation', 'commission', 'order', 'created_at', 'departure', 'destination', 'pickup_date', 'distance_travelled', 'duration_travelled', 'flight_number','vehicle', 'payment_method', 'meeting_place', 'message', 'number_of_luggages', 'number_of_passengers']
        read_only_fields = ['id', 'created_at', 'departure', 'destination', 'pickup_date', 'distance_travelled', 'duration_travelled', 'flight_number', 'message', 'number_of_luggages', 'number_of_passengers']

    def get_vehicle(self, obj):
        if not obj.estimate or not obj.estimate.user_choice:
            return None
        return DataSerializer.serialize_vehicle(obj.estimate.user_choice)

    def get_payment_method(self, obj):
        if not obj.estimate:
            return None
        return DataSerializer.serialize_payment_method(obj.estimate.payment_method)

    def get_meeting_place(self, obj):
        if not obj.estimate:
            return None
        return DataSerializer.serialize_meeting_place(obj.estimate.meeting_place)

class ExtendedBookingCompleteSerializer(serializers.ModelSerializer):
    estimate = EstimateSerializer(read_only=True)
    client = ClientBasicSerializer(read_only=True)
    assigned_driver = DriverBasicSerializer(read_only=True)
    assigned_partner = PartnerBasicSerializer(read_only=True)
    vehicle = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    meeting_place = serializers.SerializerMethodField()
    segments = BookingSegmentSerializer(many=True, read_only=True)
    recurring_info = RecurringInfoSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'booking_type', 'created_at', 'status', 
            'billing_status', 'cancellation_status', 'payment_timing', 
            'is_archived', 'is_driver_paid', 'is_partner_paid', 
            'driver_sale_price', 'partner_sale_price', 'compensation', 'commission',
            'vehicle', 'payment_method', 'meeting_place', 'estimate', 'segments', 
            'client', 'assigned_driver', 'assigned_partner', 'recurring_info'
        ]

    def get_vehicle(self, obj):
        estimate = self._get_primary_estimate(obj)
        if not estimate or not estimate.user_choice:
            return None
            
        user_choice = estimate.user_choice
        try:
            from configurations.models import Vehicle
            vehicle = Vehicle.objects.get(id=user_choice.vehicle_id) if user_choice.vehicle_id else None
            
            if vehicle:
                return {
                    'vehicle_type': vehicle.vehicle_type.name if vehicle.vehicle_type else 'N/A',
                    'brand': vehicle.brand if vehicle.brand else 'N/A',
                    'model': vehicle.model if vehicle.model else 'N/A'
                }
        except:
            pass
        
        return {'vehicle_type': 'N/A', 'brand': 'N/A', 'model': 'N/A'}

    def get_payment_method(self, obj):
        estimate = self._get_primary_estimate(obj)
        return DataSerializer.serialize_payment_method(estimate.payment_method) if estimate and estimate.payment_method else None

    def get_meeting_place(self, obj):
        estimate = self._get_primary_estimate(obj)
        return DataSerializer.serialize_meeting_place(estimate.meeting_place) if estimate and estimate.meeting_place else None

    def _get_primary_estimate(self, obj):
        if obj.booking_type == 'one_way':
            return obj.estimate
        elif obj.booking_type == 'round_trip':
            outbound = obj.segments.filter(segment_type='outbound').first()
            return outbound.estimate if outbound else None
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Ajouter les données effectives pour les round_trip
        if instance.booking_type == 'round_trip':
            data.update({
                'effective_status': instance.effective_status,
                'effective_compensation': instance.effective_compensation,
                'effective_commission': instance.effective_commission,
                'total_cost': instance.total_cost_calculated,
                'effective_driver_sale_price': instance.effective_driver_sale_price,
                'effective_partner_sale_price': instance.effective_partner_sale_price
            })
        else:
            # Pour one_way, utiliser les valeurs directes
            data.update({
                'total_cost': instance.estimate.total_booking_cost if instance.estimate else 0
            })
        
        # Gestion des informations de récurrence
        if hasattr(instance, 'recurring_occurrence') and instance.recurring_occurrence:
            occurrence = instance.recurring_occurrence
            template = occurrence.template
            recurring_data = {
                'template_id': template.id,
                'template_name': template.name,
                'recurrence_type': template.recurrence_type,
                'recurrence_type_display': template.get_recurrence_type_display(),
                'occurrence_number': occurrence.occurrence_number,
                'is_active': template.is_active
            }
            
            if template.recurrence_type == 'monthly' and hasattr(template, 'monthly_configuration'):
                recurring_data.update({
                    'monthly_type': template.monthly_configuration.monthly_type,
                    'monthly_type_display': template.monthly_configuration.get_monthly_type_display()
                })
            elif template.recurrence_type == 'custom' and hasattr(template, 'custom_configuration'):
                recurring_data.update({
                    'custom_pattern': template.custom_configuration.pattern_type,
                    'custom_pattern_display': template.custom_configuration.get_pattern_type_display()
                })
            
            data['recurring_info'] = recurring_data
        else:
            data['recurring_info'] = None
        
        return data

class PassengerUpdateSerializer(serializers.ModelSerializer):
    mode = serializers.ChoiceField(choices=['add', 'update', 'delete'], required=False, default='add')
    id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Passenger
        fields = ['id', 'name', 'phone_number', 'email', 'is_main_client', 'mode']
        extra_kwargs = {
            'name': {'required': False}, 
            'phone_number': {'required': False}, 
            'is_main_client': {'required': False}
        }

    def validate(self, attrs):
        mode = attrs.get('mode', 'add')
        if mode in ['update', 'delete'] and not isinstance(attrs.get('id'), int):
            raise serializers.ValidationError("ID required and must be an integer for 'update' and 'delete' modes")
        if mode in ['add', 'update'] and not (attrs.get('name') and attrs.get('phone_number')):
            raise serializers.ValidationError("Name and phone number required for 'add' and 'update' modes")
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
        if mode in ['update', 'delete'] and not isinstance(attrs.get('id'), int):
            raise serializers.ValidationError("ID required and must be an integer for 'update' and 'delete' modes")
        if mode in ['add', 'update'] and not (attrs.get('attribute_id') and attrs.get('quantity')):
            raise serializers.ValidationError("attribute_id and quantity required for 'add' and 'update' modes")
        return attrs

class EstimationLogUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstimationLog
        fields = ['departure', 'destination', 'pickup_date', 'waypoints', 'estimate_type', 'distance_travelled', 'duration_travelled']
        extra_kwargs = {
            'departure': {'required': False}, 
            'destination': {'required': False}, 
            'pickup_date': {'required': False}, 
            'distance_travelled': {'required': False}, 
            'duration_travelled': {'required': False}
        }

class EstimateUpdateSerializer(serializers.ModelSerializer):
    estimation_log = EstimationLogUpdateSerializer(required=False)
    passengers = PassengerUpdateSerializer(many=True, required=False)
    estimate_attribute = EstimateAttributeUpdateSerializer(many=True, required=False)
    
    class Meta:
        model = Estimate
        fields = [
            'flight_number', 'message', 'total_booking_cost', 'total_attributes_cost', 
            'number_of_luggages', 'number_of_passengers', 'case_number', 'is_payment_pending', 
            'estimation_log', 'passengers', 'estimate_attribute'
        ]

    def validate_passengers(self, passengers_data):
        return [PassengerUpdateSerializer(data=p).validated_data for p in passengers_data if PassengerUpdateSerializer(data=p).is_valid(raise_exception=True)]

class BookingUpdateSerializer(serializers.ModelSerializer):
    estimate = EstimateUpdateSerializer(required=False)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_driver_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_partner_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Booking
        fields = [
            'status', 'billing_status', 'cancellation_status', 'payment_timing', 
            'is_archived', 'is_driver_paid', 'is_partner_paid', 'driver_sale_price', 
            'partner_sale_price', 'compensation', 'commission', 'estimate', 
            'client_id', 'assigned_driver_id', 'assigned_partner_id'
        ]

    def validate_client_id(self, value):
        if value is not None and not Client.objects.filter(id=value).exists():
            raise serializers.ValidationError("Client not found")
        return value

    def validate_assigned_driver_id(self, value):
        if value is not None and not Driver.objects.filter(id=value).exists():
            raise serializers.ValidationError("Driver not found")
        return value

    def validate_assigned_partner_id(self, value):
        if value is not None and not Partner.objects.filter(id=value).exists():
            raise serializers.ValidationError("Partner not found")
        return value

    def update(self, instance, validated_data):
        with transaction.atomic():
            old_state = BookingChangeTracker.capture_booking_state(instance)
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
            user = self.context.get('request').user if self.context.get('request') else BookingLogService.get_current_user()
            if not getattr(instance, '_skip_change_tracking', False):
                BookingChangeTracker.detect_and_log_changes(instance, old_state, user)
            return instance

    def _update_estimate_complete(self, estimate_instance, estimate_data, booking_instance):
        estimation_log_data = estimate_data.pop('estimation_log', None)
        passengers_data = estimate_data.pop('passengers', None)
        estimate_attributes_data = estimate_data.pop('estimate_attribute', None)

        for field, value in estimate_data.items():
            setattr(estimate_instance, field, value)

        if estimate_data:
            estimate_instance.save()

        if estimation_log_data and estimate_instance.estimation_log:
            for field, value in estimation_log_data.items():
                setattr(estimate_instance.estimation_log, field, value)
            estimate_instance.estimation_log.save()

        if passengers_data:
            self._manage_passengers(estimate_instance, passengers_data, booking_instance)

        if estimate_attributes_data:
            self._manage_estimate_attributes(estimate_instance, estimate_attributes_data)

    def _manage_passengers(self, estimate_instance, passengers_data, booking_instance):
        for p in passengers_data:
            mode = p.get('mode', 'add')
            if mode == 'add':
                self._add_passenger(estimate_instance, p, booking_instance)
            elif mode == 'update':
                self._update_passenger(estimate_instance, p)
            elif mode == 'delete':
                self._delete_passenger(estimate_instance, p.get('id'))

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
            raise serializers.ValidationError(f"Passenger with ID {passenger_id} not found")

    def _delete_passenger(self, estimate_instance, passenger_id):
        try:
            passenger = estimate_instance.passengers.get(id=passenger_id)
            estimate_instance.passengers.remove(passenger)
            passenger.delete()
        except Passenger.DoesNotExist:
            raise serializers.ValidationError(f"Passenger with ID {passenger_id} not found")

    def _manage_estimate_attributes(self, estimate_instance, attributes_data):
        for attr_data in attributes_data:
            mode = attr_data.get('mode', 'add')
            if mode == 'add':
                self._add_attribute(estimate_instance, attr_data)
            elif mode == 'update':
                self._update_attribute(estimate_instance, attr_data)
            elif mode == 'delete':
                self._delete_attribute(estimate_instance, attr_data.get('id'))

    def _add_attribute(self, estimate_instance, attr_data):
        try:
            config_attribute = Attribute.objects.get(id=attr_data.get('attribute_id'))
            new_attr = EstimateAttribute.objects.create(attribute=config_attribute, quantity=attr_data.get('quantity'))
            estimate_instance.estimate_attribute.add(new_attr)
        except Attribute.DoesNotExist:
            raise serializers.ValidationError(f"Configuration attribute with ID {attr_data.get('attribute_id')} not found")

    def _update_attribute(self, estimate_instance, attr_data):
        attr_id = attr_data.get('id')
        try:
            estimate_attr = estimate_instance.estimate_attribute.get(id=attr_id)
            if attr_data.get('attribute_id'):
                estimate_attr.attribute = Attribute.objects.get(id=attr_data.get('attribute_id'))
            if attr_data.get('quantity'):
                estimate_attr.quantity = attr_data.get('quantity')
            estimate_attr.save()
        except (EstimateAttribute.DoesNotExist, Attribute.DoesNotExist) as e:
            raise serializers.ValidationError(f"Attribute with ID {attr_id} not found" if isinstance(e, EstimateAttribute.DoesNotExist) else f"Configuration attribute with ID {attr_data.get('attribute_id')} not found")

    def _delete_attribute(self, estimate_instance, attr_id):
        try:
            estimate_attr = estimate_instance.estimate_attribute.get(id=attr_id)
            estimate_instance.estimate_attribute.remove(estimate_attr)
            estimate_attr.delete()
        except EstimateAttribute.DoesNotExist:
            raise serializers.ValidationError(f"Attribute with ID {attr_id} not found")

class ReturnTripDataSerializer(serializers.Serializer):
    departure = serializers.CharField(max_length=255)
    destination = serializers.CharField(max_length=255)
    pickup_date = serializers.DateTimeField()
    waypoints = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    flight_number = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    number_of_luggages = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    number_of_passengers = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    total_cost = serializers.FloatField(min_value=0)
    total_attributes_cost = serializers.FloatField(min_value=0, default=0)
    compensation = serializers.FloatField(required=False, default=0, min_value=0)
    commission = serializers.FloatField(required=False, default=0, min_value=0)
    passengers = serializers.DictField(required=False)
    estimate_attributes = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    vehicle_id = serializers.IntegerField(required=False, allow_null=True)
    payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    distance_travelled = serializers.FloatField(required=False, default=0, min_value=0)
    duration_travelled = serializers.CharField(required=False, default="0h0min")

    def validate_passengers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Passengers must be an object with 'existing' and/or 'new'")
        existing_ids = value.get('existing', [])
        new_passengers = value.get('new', [])
        if existing_ids and (not isinstance(existing_ids, list) or not all(isinstance(id, int) for id in existing_ids)):
            raise serializers.ValidationError("'existing' must be a list of integers")
        if new_passengers and (not isinstance(new_passengers, list) or any(not isinstance(p, dict) or not p.get('name') or not p.get('phone_number') for p in new_passengers)):
            raise serializers.ValidationError("'new' must be a list of objects with 'name' and 'phone_number'")
        return value

    def validate_estimate_attributes(self, value):
        if not isinstance(value, list) or any(not isinstance(attr, dict) or 'attribute' not in attr or 'quantity' not in attr or not isinstance(attr['attribute'], int) or not isinstance(attr['quantity'], int) or attr['quantity'] < 1 for attr in value):
            raise serializers.ValidationError("Attributes must be a list of objects with valid 'attribute' and 'quantity'")
        return value

    def validate(self, data):
        if data.get('compensation', 0) > 0 and data.get('commission', 0) > 0:
            raise serializers.ValidationError("Cannot set both compensation and commission for return trip")
        if data.get('total_attributes_cost', 0) > data.get('total_cost', 0):
            raise serializers.ValidationError("Attributes cost cannot exceed total cost")
        return data

class DuplicateModificationSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    pickup_date = serializers.DateTimeField()
    departure = serializers.CharField()
    destination = serializers.CharField()
    vehicle_id = serializers.IntegerField()
    number_of_passengers = serializers.IntegerField()
    number_of_luggages = serializers.CharField(required=False, allow_blank=True)
    total_booking_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    waypoints = serializers.ListField(child=serializers.CharField(), default=list)
    payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    meeting_place_id = serializers.IntegerField(required=False, allow_null=True)
    flight_number = serializers.CharField(default='', allow_blank=True)
    message = serializers.CharField(default='', allow_blank=True)
    case_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    compensation = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    assigned_driver_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_partner_id = serializers.IntegerField(required=False, allow_null=True)
    passengers = serializers.DictField(child=serializers.ListField(), default=dict)
    estimate_attributes = serializers.ListField(child=serializers.DictField(), default=list)

    def validate_passengers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Passengers must be a dictionary with 'existing' and 'new'")
        existing = value.get('existing', [])
        new = value.get('new', [])
        if not isinstance(existing, list) or any(not isinstance(pid, int) for pid in existing):
            raise serializers.ValidationError("'existing' must be a list of integer IDs")
        if not isinstance(new, list) or any(not isinstance(p, dict) or 'name' not in p or 'phone_number' not in p for p in new):
            raise serializers.ValidationError("'new' must be a list of objects with 'name' and 'phone_number'")
        return value

    def validate_estimate_attributes(self, value):
        if any('attribute' not in attr or 'quantity' not in attr for attr in value):
            raise serializers.ValidationError("Each attribute must have 'attribute' and 'quantity'")
        return value

class RoundTripDuplicateModificationSerializer(serializers.Serializer):
    client_id = serializers.IntegerField(required=True)
    shared_modifications = serializers.DictField(required=False, default=dict)
    outbound_modifications = serializers.DictField(required=False, default=dict)
    return_modifications = serializers.DictField(required=False, default=dict)

    def validate_client_id(self, value):
        if not Client.objects.filter(id=value).exists():
            raise serializers.ValidationError("Client not found")
        return value

class RecurringSearchParamsSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(
        choices=['total', 'today', 'past', 'future', 'cancelled', 'recurring', 'archived'], 
        required=False, default='total'
    )
    search_key = serializers.CharField(required=False, allow_blank=True)
    billing_status = serializers.ChoiceField(choices=Booking.BILLING_STATUS_CHOICES, required=False)
    cancellation_status = serializers.ChoiceField(choices=Booking.CANCELLATION_STATUS_CHOICES, required=False)
    payment_timing = serializers.ChoiceField(choices=Booking.PAYMENT_TIMING_CHOICES, required=False)

    def validate_search_key(self, value):
        if not value or value == 'total':
            return value
        valid_prefixes = ['status_', 'booking_type_', 'recurring_type_', 'recurring_monthly_', 'recurring_custom_']
        if not any(value.startswith(p) for p in valid_prefixes):
            raise serializers.ValidationError("Invalid search_key. Must start with specific prefixes or be 'total'")
        return value

    def validate(self, attrs):
        scope = attrs.get('scope', 'total')
        search_key = attrs.get('search_key', '')
        if scope == 'recurring' and search_key and search_key != 'total' and not search_key.startswith('recurring_'):
            raise serializers.ValidationError("With scope='recurring', search_key must start with 'recurring_' or be 'total'")
        if search_key.startswith('recurring_') and scope not in ['total', 'recurring']:
            raise serializers.ValidationError("Recurring search_key requires scope='total' or 'recurring'")
        return attrs