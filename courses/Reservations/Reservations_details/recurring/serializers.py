# courses/Reservations/Reservations_details/recurring_serializers.py

from rest_framework import serializers
from django.core.exceptions import ValidationError
from datetime import datetime, date, timedelta
from courses.Reservations.Reservations_details.recurring.helpers import ValidationHelper
from courses.models import RecurringBookingTemplate


class RecurringConfigSerializer(serializers.Serializer):
    """Serializer pour configuration initiale de récurrence"""
    
    # Champs communs
    name = serializers.CharField(max_length=255)
    recurrence_type = serializers.ChoiceField(choices=['daily', 'weekly', 'monthly', 'yearly', 'custom'])
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    max_occurrences = serializers.IntegerField(min_value=1)
    
    # Champs daily
    include_weekends = serializers.BooleanField(required=False, default=False)
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=7),
        required=False, default=list
    )
    
    # Champs weekly/monthly/yearly
    frequency_interval = serializers.IntegerField(required=False, min_value=1, default=1)
    
    # Champs monthly
    monthly_type = serializers.ChoiceField(
        choices=['same_date', 'same_position'], required=False, default='same_date'
    )
    
    # Champs custom
    pattern_type = serializers.ChoiceField(
        choices=['days_of_week', 'interval_based', 'specific_dates'], required=False
    )
    interval_days = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    specific_dates = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    enable_multiple_times = serializers.BooleanField(required=False, default=False)
    time_slots = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    enable_multiple_periods = serializers.BooleanField(required=False, default=False)
    exclude_dates = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    
    def validate_start_date(self, value):
        """Valide date début avec utilitaire"""
        if value < date.today() - timedelta(days=30):
            raise serializers.ValidationError("Date de début trop ancienne (>30 jours)")
        return value
    
    def validate_weekdays(self, value):
        """Valide jours semaine avec helper"""
        if value and (len(value) != len(set(value)) or len(value) > 7):
            raise serializers.ValidationError("Jours invalides ou doublons")
        return value
    
    def validate_time_slots(self, value):
        """Valide créneaux horaires"""
        if value:
            if len(value) > 5:
                raise serializers.ValidationError("Maximum 5 créneaux par jour")
            for slot in value:
                try:
                    datetime.strptime(slot, '%H:%M')
                except ValueError:
                    raise serializers.ValidationError(f"Format horaire invalide: {slot}")
        return value
    
    def validate_specific_dates(self, value):
        """Valide dates spécifiques"""
        if value:
            if len(value) > 100:
                raise serializers.ValidationError("Maximum 100 dates spécifiques")
            for date_str in value:
                try:
                    datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    raise serializers.ValidationError(f"Format date invalide: {date_str}")
        return value
    
    def validate(self, data):
        """Validation croisée avec helper"""
        # Validation dates
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if end_date and start_date and end_date <= start_date:
            raise serializers.ValidationError("Date fin doit être > date début")
        
        if end_date and start_date and (end_date - start_date).days > 365:
            raise serializers.ValidationError("Récurrence ne peut pas dépasser 1 an")
        
        # Validation par type avec helper
        recurrence_type = data.get('recurrence_type')
        max_occurrences = data.get('max_occurrences')
        
        limits = ValidationHelper.get_max_limits()
        type_limits = limits.get(recurrence_type, {})
        
        if recurrence_type == 'daily':
            self._validate_daily_specific(data, max_occurrences, type_limits)
        elif recurrence_type in ['weekly', 'monthly', 'yearly']:
            max_allowed = type_limits.get('max_occurrences', 365)
            if max_occurrences > max_allowed:
                raise serializers.ValidationError(f"Maximum {max_allowed} pour {recurrence_type}")
        elif recurrence_type == 'custom':
            self._validate_custom_specific(data, max_occurrences, type_limits)
        
        return data
    
    def _validate_daily_specific(self, data, max_occurrences, limits):
        """Validation daily avec limites"""
        include_weekends = data.get('include_weekends', False)
        weekdays = data.get('weekdays', [])
        
        effective_days = weekdays if weekdays else (list(range(1, 8)) if include_weekends else list(range(1, 6)))
        includes_weekends = any(day in [6, 7] for day in effective_days)
        
        max_limit = limits['max_occurrences_with_weekends'] if includes_weekends else limits['max_occurrences_weekdays']
        
        if max_occurrences > max_limit:
            raise serializers.ValidationError(f"Maximum {max_limit} occurrences pour daily")
    
    def _validate_custom_specific(self, data, max_occurrences, limits):
        """Validation custom avec patterns"""
        pattern_type = data.get('pattern_type')
        
        if not pattern_type:
            raise serializers.ValidationError("pattern_type requis pour custom")
        
        if pattern_type == 'interval_based' and not data.get('interval_days'):
            raise serializers.ValidationError("interval_days requis pour interval_based")
        
        if pattern_type == 'specific_dates' and not data.get('specific_dates'):
            raise serializers.ValidationError("specific_dates requis pour specific_dates")
        
        if data.get('enable_multiple_times') and not data.get('time_slots'):
            raise serializers.ValidationError("time_slots requis si enable_multiple_times=True")
        
        if max_occurrences > limits['max_occurrences']:
            raise serializers.ValidationError(f"Maximum {limits['max_occurrences']} pour custom")


class RecurringCreationSerializer(serializers.Serializer):
    """Serializer pour création finale optimisée"""
    
    template_id = serializers.IntegerField()
    valid_occurrences = serializers.ListField(child=serializers.IntegerField())
    modified_occurrences = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    
    def validate_template_id(self, value):
        """Valide template avec helper"""
        try:
            template = RecurringBookingTemplate.objects.get(id=value)
            if not template.is_active:
                raise serializers.ValidationError("Template inactif")
            return value
        except RecurringBookingTemplate.DoesNotExist:
            raise serializers.ValidationError("Template non trouvé")
    
    def validate_valid_occurrences(self, value):
        """Valide occurrences valides"""
        if not value:
            raise serializers.ValidationError("Au moins une occurrence valide requise")
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Doublons dans valid_occurrences")
        return value
    
    def validate_modified_occurrences(self, value):
        """Valide occurrences modifiées"""
        occurrence_ids = []
        
        for modification in value:
            if 'occurrence_id' not in modification or 'modifications' not in modification:
                raise serializers.ValidationError("occurrence_id et modifications requis")
            
            occurrence_id = modification['occurrence_id']
            if occurrence_id in occurrence_ids:
                raise serializers.ValidationError(f"Occurrence {occurrence_id} en double")
            occurrence_ids.append(occurrence_id)
            
            # Valider champs autorisés
            self._validate_modification_fields(modification['modifications'], occurrence_id)
        
        return value
    
    def _validate_modification_fields(self, modifications, occurrence_id):
        """Valide champs modification"""
        allowed_fields = [
            'pickup_date', 'departure', 'destination', 'waypoints', 'total_booking_cost', 
            'compensation', 'commission', 'vehicle_id', 'payment_method_id', 'passengers', 
            'estimate_attributes', 'flight_number', 'message', 'number_of_passengers', 
            'number_of_luggages', 'booking_level', 'shared_segments', 'outbound_segment', 'return_segment'
        ]
        
        invalid_fields = set(modifications.keys()) - set(allowed_fields)
        if invalid_fields:
            raise serializers.ValidationError(f"Champs invalides pour {occurrence_id}: {list(invalid_fields)}")
        
        # Validation compensation/commission
        compensation = modifications.get('compensation', 0)
        commission = modifications.get('commission', 0)
        if compensation > 0 and commission > 0:
            raise serializers.ValidationError(f"Occurrence {occurrence_id}: compensation et commission exclusives")
        
        # Validation passengers
        if 'passengers' in modifications:
            self._validate_passengers_structure(modifications['passengers'], occurrence_id)
        
        # Validation attributes
        if 'estimate_attributes' in modifications:
            self._validate_attributes_structure(modifications['estimate_attributes'], occurrence_id)
    
    def _validate_passengers_structure(self, passengers, occurrence_id):
        """Valide structure passengers"""
        if not isinstance(passengers, dict):
            raise serializers.ValidationError(f"Occurrence {occurrence_id}: passengers doit être dict")
        
        existing = passengers.get('existing', [])
        new = passengers.get('new', [])
        
        if existing and not all(isinstance(id, int) for id in existing):
            raise serializers.ValidationError(f"Occurrence {occurrence_id}: existing doit contenir des IDs entiers")
        
        if new:
            for passenger in new:
                if not isinstance(passenger, dict) or 'name' not in passenger or 'phone_number' not in passenger:
                    raise serializers.ValidationError(f"Occurrence {occurrence_id}: nouveau passager invalide")
    
    def _validate_attributes_structure(self, attributes, occurrence_id):
        """Valide structure attributs"""
        if not isinstance(attributes, list):
            raise serializers.ValidationError(f"Occurrence {occurrence_id}: attributes doit être liste")
        
        for attr in attributes:
            if not isinstance(attr, dict) or 'attribute' not in attr or 'quantity' not in attr:
                raise serializers.ValidationError(f"Occurrence {occurrence_id}: attribut invalide")
            
            if not isinstance(attr['attribute'], int) or not isinstance(attr['quantity'], int) or attr['quantity'] < 1:
                raise serializers.ValidationError(f"Occurrence {occurrence_id}: attribute/quantity invalides")
    
    def validate(self, data):
        """Validation croisée finale"""
        valid_ids = set(data['valid_occurrences'])
        modified_ids = set(mod['occurrence_id'] for mod in data.get('modified_occurrences', []))
        
        overlap = valid_ids & modified_ids
        if overlap:
            raise serializers.ValidationError(f"Occurrences {list(overlap)} ne peuvent être valides ET modifiées")
        
        return data


class BookingModificationSerializer(serializers.Serializer):
    """Serializer pour modifications occurrence spécifique"""
    
    # Structures modificatons niveau booking/segments
    booking_level = serializers.DictField(required=False, default=dict)
    shared_segments = serializers.DictField(required=False, default=dict)
    outbound_segment = serializers.DictField(required=False, default=dict)
    return_segment = serializers.DictField(required=False, default=dict)
    
    # Modifications directes (compatibilité)
    pickup_date = serializers.DateTimeField(required=False)
    departure = serializers.CharField(required=False)
    destination = serializers.CharField(required=False)
    waypoints = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    total_booking_cost = serializers.FloatField(required=False, min_value=0)
    compensation = serializers.FloatField(required=False, default=0, min_value=0)
    commission = serializers.FloatField(required=False, default=0, min_value=0)
    vehicle_id = serializers.IntegerField(required=False, allow_null=True)
    payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    flight_number = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    number_of_passengers = serializers.IntegerField(required=False, min_value=1)
    number_of_luggages = serializers.CharField(required=False, allow_blank=True)
    passengers = serializers.DictField(required=False, default=dict)
    estimate_attributes = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    
    def validate_passengers(self, value):
        """Valide structure passengers avec helper"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Passengers doit être dict avec existing/new")
        
        existing = value.get('existing', [])
        new = value.get('new', [])
        
        if existing and not all(isinstance(id, int) for id in existing):
            raise serializers.ValidationError("existing doit contenir IDs entiers")
        
        if new:
            for passenger in new:
                if not isinstance(passenger, dict) or 'name' not in passenger or 'phone_number' not in passenger:
                    raise serializers.ValidationError("nouveau passager doit avoir name et phone_number")
        
        return value
    
    def validate_estimate_attributes(self, value):
        """Valide attributs avec helper"""
        for attr in value:
            if 'attribute' not in attr or 'quantity' not in attr:
                raise serializers.ValidationError("attribute et quantity requis")
            if not isinstance(attr['attribute'], int) or not isinstance(attr['quantity'], int):
                raise serializers.ValidationError("attribute et quantity doivent être entiers")
        return value
    
    def validate(self, data):
        """Validation compensation/commission avec helper"""
        compensation = data.get('compensation', 0)
        commission = data.get('commission', 0)
        
        if compensation > 0 and commission > 0:
            raise serializers.ValidationError("Compensation et commission exclusives")
        
        return data


class RecurringTemplateSerializer(serializers.Serializer):
    """Serializer minimal pour template display"""
    
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    recurrence_type = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    max_occurrences = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    # Stats calculées
    total_occurrences = serializers.SerializerMethodField()
    created_bookings = serializers.SerializerMethodField()
    pending_occurrences = serializers.SerializerMethodField()
    
    def get_total_occurrences(self, obj):
        return obj.occurrences.count()
    
    def get_created_bookings(self, obj):
        return obj.occurrences.filter(booking__isnull=False).count()
    
    def get_pending_occurrences(self, obj):
        return obj.occurrences.filter(booking__isnull=True).count()