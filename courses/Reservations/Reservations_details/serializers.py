from django.utils import timezone
from rest_framework import serializers
from configurations.models import Attribute
from courses.Logs.services import BookingChangeTracker, BookingLogService
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
    """Serializer pour les informations de récurrence"""
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
    """Serializer pour les éléments du workflow récurrence"""
    status = serializers.CharField()
    status_display = serializers.CharField()
    count = serializers.IntegerField()
    search_key = serializers.CharField()
    level = serializers.IntegerField(default=1)
    parent_key = serializers.CharField(required=False, allow_null=True)

class ExtendedMainStatsSerializer(serializers.Serializer):
    """Extension des statistiques principales"""
    total_bookings = serializers.IntegerField()
    today_bookings = serializers.IntegerField()
    past_bookings = serializers.IntegerField()
    future_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    recurring_bookings = serializers.IntegerField()
    archived_bookings = serializers.IntegerField()

class ExtendedGlobalBookingStatisticsSerializer(serializers.Serializer):
    """Extension du serializer global avec récurrences"""
    main_stats = ExtendedMainStatsSerializer()
    status_workflow = StatusWorkflowItemSerializer(many=True)
    recurring_workflow = RecurringWorkflowItemSerializer(many=True, required=False)
    recurring_monthly_workflow = RecurringWorkflowItemSerializer(many=True, required=False)
    recurring_custom_workflow = RecurringWorkflowItemSerializer(many=True, required=False)
    
    def to_representation(self, instance):
        if not isinstance(instance, dict):
            raise serializers.ValidationError("Instance doit être un dictionnaire")
        
        required_fields = ['main_stats', 'status_workflow']
        for field in required_fields:
            if field not in instance:
                raise serializers.ValidationError(f"Instance doit contenir '{field}'")
        
        return super().to_representation(instance)

class BookingSegmentSerializer(serializers.ModelSerializer):
    """Serializer pour l'affichage des segments de booking"""
    departure = serializers.ReadOnlyField()
    destination = serializers.ReadOnlyField()
    pickup_date = serializers.ReadOnlyField()
    distance_travelled = serializers.ReadOnlyField()
    duration_travelled = serializers.ReadOnlyField()
    flight_number = serializers.CharField(source='estimate.flight_number', read_only=True)
    message = serializers.CharField(source='estimate.message', read_only=True)
    number_of_luggages = serializers.CharField(source='estimate.number_of_luggages', read_only=True)
    number_of_passengers = serializers.IntegerField(source='estimate.number_of_passengers', read_only=True)
    
    class Meta:
        model = BookingSegment
        fields = [
            'id', 'segment_type', 'status', 'segment_cost', 
            'compensation', 'commission', 'order', 'created_at',
            'departure', 'destination', 'pickup_date', 
            'distance_travelled', 'duration_travelled',
            'flight_number', 'message', 'number_of_luggages', 'number_of_passengers'
        ]
        read_only_fields = [
            'id', 'created_at', 'departure', 'destination', 'pickup_date',
            'distance_travelled', 'duration_travelled', 'flight_number', 
            'message', 'number_of_luggages', 'number_of_passengers'
        ]

class ExtendedBookingCompleteSerializer(serializers.ModelSerializer):
    """Extension avec informations de récurrence"""
    estimate = EstimateSerializer(read_only=True)
    client = ClientBasicSerializer(read_only=True)
    assigned_driver = DriverBasicSerializer(read_only=True)
    assigned_partner = PartnerBasicSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_status_display = serializers.CharField(source='get_billing_status_display', read_only=True)
    cancellation_status_display = serializers.CharField(source='get_cancellation_status_display', read_only=True)
    payment_timing_display = serializers.CharField(source='get_payment_timing_display', read_only=True)
    effective_status = serializers.ReadOnlyField()
    effective_compensation = serializers.ReadOnlyField()
    effective_commission = serializers.ReadOnlyField()
    effective_estimate = EstimateSerializer(read_only=True)
    segments = BookingSegmentSerializer(many=True, read_only=True)
    total_cost = serializers.ReadOnlyField(source='total_cost_calculated')
    recurring_info = RecurringInfoSerializer(read_only=True, allow_null=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'booking_type', 'created_at', 
            'status', 'status_display', 'effective_status',
            'billing_status', 'billing_status_display', 
            'cancellation_status', 'cancellation_status_display', 
            'payment_timing', 'payment_timing_display', 
            'is_archived', 'is_driver_paid', 'is_partner_paid', 
            'driver_sale_price', 'partner_sale_price', 
            'compensation', 'commission',
            'effective_compensation', 'effective_commission',
            'total_cost', 'estimate', 'effective_estimate', 'segments',
            'client', 'assigned_driver', 'assigned_partner', 'recurring_info'
        ]
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        
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
                monthly_config = template.monthly_configuration
                recurring_data.update({
                    'monthly_type': monthly_config.monthly_type,
                    'monthly_type_display': monthly_config.get_monthly_type_display()
                })
            
            elif template.recurrence_type == 'custom' and hasattr(template, 'custom_configuration'):
                custom_config = template.custom_configuration
                recurring_data.update({
                    'custom_pattern': custom_config.pattern_type,
                    'custom_pattern_display': custom_config.get_pattern_type_display()
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
            
            user = self.context['request'].user if hasattr(self, 'context') and 'request' in self.context else BookingLogService.get_current_user()
            
            if not (hasattr(instance, '_skip_change_tracking') and instance._skip_change_tracking):
                BookingChangeTracker.detect_and_log_changes(instance, old_state, user)
            
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

class ReturnTripDataSerializer(serializers.Serializer):
    """Serializer pour les données du trajet retour avec structures validées"""
    departure = serializers.CharField(max_length=255, help_text="Lieu de départ du retour")
    destination = serializers.CharField(max_length=255, help_text="Lieu de destination du retour")
    pickup_date = serializers.DateTimeField(help_text="Date et heure de prise en charge du retour")
    waypoints = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Points d'étape pour le retour")
    flight_number = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True, help_text="Numéro de vol pour le retour")
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Message spécifique au retour")
    number_of_luggages = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True, help_text="Nombre de bagages pour le retour")
    number_of_passengers = serializers.IntegerField(required=False, allow_null=True, min_value=1, help_text="Nombre de passagers pour le retour")
    total_cost = serializers.FloatField(min_value=0, help_text="Coût total du trajet retour")
    total_attributes_cost = serializers.FloatField(min_value=0, default=0, help_text="Coût total des attributs du retour")
    compensation = serializers.FloatField(required=False, default=0, min_value=0, help_text="Compensation pour le retour (en €)")
    commission = serializers.FloatField(required=False, default=0, min_value=0, help_text="Commission pour le retour (en %)")
    passengers = serializers.DictField(required=False, help_text="Passagers pour le retour")
    estimate_attributes = serializers.ListField(child=serializers.DictField(), required=False, default=list, help_text="Attributs d'estimation pour le retour")
    vehicle_id = serializers.IntegerField(required=False, allow_null=True, help_text="ID du véhicule pour le retour (optionnel)")
    payment_method_id = serializers.IntegerField(required=False, allow_null=True, help_text="ID de la méthode de paiement pour le retour (optionnel)")
    distance_travelled = serializers.FloatField(required=False, default=0, min_value=0, help_text="Distance parcourue pour le retour")
    duration_travelled = serializers.CharField(required=False, default="0h0min", help_text="Durée du trajet retour")

    def validate_passengers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Les passagers doivent être un objet avec 'existing' et/ou 'new'")
        
        existing_ids = value.get('existing', [])
        new_passengers = value.get('new', [])
        
        if existing_ids:
            if not isinstance(existing_ids, list) or not all(isinstance(id, int) for id in existing_ids):
                raise serializers.ValidationError("'existing' doit être une liste d'entiers")
        
        if new_passengers:
            if not isinstance(new_passengers, list):
                raise serializers.ValidationError("'new' doit être une liste")
            
            for passenger in new_passengers:
                if not isinstance(passenger, dict):
                    raise serializers.ValidationError("Chaque nouveau passager doit être un objet")
                if not passenger.get('name') or not passenger.get('phone_number'):
                    raise serializers.ValidationError("Nom et téléphone requis pour nouveaux passagers")
        
        return value

    def validate_estimate_attributes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Les attributs doivent être une liste")
        
        for attr in value:
            if not isinstance(attr, dict):
                raise serializers.ValidationError("Chaque attribut doit être un objet")
            if 'attribute' not in attr or 'quantity' not in attr:
                raise serializers.ValidationError("Chaque attribut doit avoir 'attribute' et 'quantity'")
            if not isinstance(attr['attribute'], int) or not isinstance(attr['quantity'], int):
                raise serializers.ValidationError("'attribute' et 'quantity' doivent être des entiers")
            if attr['quantity'] < 1:
                raise serializers.ValidationError("La quantité doit être supérieure à 0")
        
        return value

    def validate(self, data):
        compensation = data.get('compensation', 0)
        commission = data.get('commission', 0)
        
        if compensation > 0 and commission > 0:
            raise serializers.ValidationError("Vous ne pouvez pas définir à la fois compensation et commission pour le retour.")
        
        total_cost = data.get('total_cost', 0)
        total_attributes_cost = data.get('total_attributes_cost', 0)
        
        if total_attributes_cost > total_cost:
            raise serializers.ValidationError("Le coût des attributs ne peut pas être supérieur au coût total.")
        
        return data

class DuplicateModificationSerializer(serializers.Serializer):
    """Serializer pour les modifications de duplication one_way"""
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
    passengers = serializers.DictField(child=serializers.ListField(), default=dict, help_text="Structure: {'existing': [1,2,3], 'new': [{'name': '...', 'phone_number': '...'}]}")
    estimate_attributes = serializers.ListField(child=serializers.DictField(), default=list, help_text="Liste d'attributs: [{'attribute': 1, 'quantity': 2}]")
    
    def validate_passengers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Les passagers doivent être un dictionnaire avec 'existing' et 'new'.")
        
        existing = value.get('existing', [])
        if not isinstance(existing, list):
            raise serializers.ValidationError("'existing' doit être une liste d'IDs.")
        
        for passenger_id in existing:
            if not isinstance(passenger_id, int):
                raise serializers.ValidationError("Les IDs de passagers existants doivent être des entiers.")
        
        new = value.get('new', [])
        if not isinstance(new, list):
            raise serializers.ValidationError("'new' doit être une liste de nouveaux passagers.")
        
        for passenger in new:
            if not isinstance(passenger, dict):
                raise serializers.ValidationError("Chaque nouveau passager doit être un dictionnaire.")
            
            if 'name' not in passenger or 'phone_number' not in passenger:
                raise serializers.ValidationError("Chaque nouveau passager doit avoir 'name' et 'phone_number'.")
        
        return value
    
    def validate_estimate_attributes(self, value):
        for attr in value:
            if 'attribute' not in attr or 'quantity' not in attr:
                raise serializers.ValidationError("Chaque attribut doit avoir 'attribute' et 'quantity'.")
        return value

class RoundTripDuplicateModificationSerializer(serializers.Serializer):
    """Serializer pour les modifications de duplication round_trip"""
    client_id = serializers.IntegerField(required=True)
    shared_modifications = serializers.DictField(required=False, default=dict)
    outbound_modifications = serializers.DictField(required=False, default=dict)
    return_modifications = serializers.DictField(required=False, default=dict)
    
    def validate_client_id(self, value):
        try:
            Client.objects.get(id=value)
            return value
        except Client.DoesNotExist:
            raise serializers.ValidationError("Client introuvable")

class RecurringSearchParamsSerializer(serializers.Serializer):
    """Validation des paramètres de recherche pour récurrences"""
    scope = serializers.ChoiceField(
        choices=['total', 'today', 'past', 'future', 'cancelled', 'recurring', 'archived'],
        required=False,
        default='total'
    )
    search_key = serializers.CharField(required=False, allow_blank=True)
    billing_status = serializers.ChoiceField(choices=Booking.BILLING_STATUS_CHOICES, required=False)
    cancellation_status = serializers.ChoiceField(choices=Booking.CANCELLATION_STATUS_CHOICES, required=False)
    payment_timing = serializers.ChoiceField(choices=Booking.PAYMENT_TIMING_CHOICES, required=False)
    
    def validate_search_key(self, value):
        if not value:
            return value
        
        valid_prefixes = ['status_', 'booking_type_', 'recurring_type_', 'recurring_monthly_', 'recurring_custom_']
        
        if value != 'total' and not any(value.startswith(prefix) for prefix in valid_prefixes):
            raise serializers.ValidationError(f"search_key invalide. Doit commencer par: {', '.join(valid_prefixes)} ou être 'total'")
        
        return value
    
    def validate(self, attrs):
        scope = attrs.get('scope', 'total')
        search_key = attrs.get('search_key', '')
        
        if scope == 'recurring' and search_key:
            if search_key != 'total' and not search_key.startswith('recurring_'):
                raise serializers.ValidationError("Avec scope='recurring', search_key doit commencer par 'recurring_' ou être 'total'")
        
        if search_key.startswith('recurring_') and scope not in ['total', 'recurring']:
            raise serializers.ValidationError("search_key de récurrence nécessite scope='total' ou scope='recurring'")
        
        return attrs