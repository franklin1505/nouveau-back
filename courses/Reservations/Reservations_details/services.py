from django.utils import timezone
from courses.models import Booking
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

class BookingStatsService:
    
    @staticmethod
    def get_base_queryset():
        return Booking.objects.filter(is_archived=False)
    
    @staticmethod
    def get_booking_by_id(booking_id):
        return get_object_or_404(
            Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute__attribute'
            ),
            id=booking_id
        )
    
    @staticmethod
    def get_main_stats():
        base_qs = BookingStatsService.get_base_queryset()
        bookings_with_dates = base_qs.select_related('estimate__estimation_log').filter(
            estimate__estimation_log__pickup_date__isnull=False
        ).order_by('estimate__estimation_log__pickup_date')
        
        today_date = timezone.now().date()
        today_count = 0
        past_count = 0
        future_count = 0
        
        for booking in bookings_with_dates:
            pickup_date = booking.estimate.estimation_log.pickup_date.date()
            if pickup_date == today_date:
                today_count += 1
            elif pickup_date < today_date:
                past_count += 1
            else:
                future_count += 1
        
        return {
            'total_bookings': base_qs.count(),
            'today_bookings': today_count,
            'past_bookings': past_count,
            'future_bookings': future_count,
            'cancelled_bookings': base_qs.filter(cancellation_status=Booking.CANCELLED).count(),
            'archived_bookings': Booking.objects.filter(is_archived=True).count()
        }
    
    @staticmethod
    def get_status_workflow_stats(scope=None):
        queryset = BookingStatsService._apply_scope_filter(scope)
        status_data = [{'status': 'total', 'status_display': 'Total', 'count': queryset.count(), 'search_key': 'total'}]
        
        for status_code, status_display in Booking.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            status_data.append({
                'status': status_code,
                'status_display': status_display,
                'count': count,
                'search_key': f'status_{status_code}'
            })
        
        return status_data
    
    @staticmethod
    def get_sub_stats(queryset):
        return {
            'total': queryset.count(),
            'billing_status': {code: queryset.filter(billing_status=code).count() for code, _ in Booking.BILLING_STATUS_CHOICES},
            'cancellation_status': {code: queryset.filter(cancellation_status=code).count() for code, _ in Booking.CANCELLATION_STATUS_CHOICES},
            'payment_timing': {code: queryset.filter(payment_timing=code).count() for code, _ in Booking.PAYMENT_TIMING_CHOICES}
        }
    
    @staticmethod
    def _apply_scope_filter(scope):
        base_qs = BookingStatsService.get_base_queryset()
        
        if scope in ['today', 'past', 'future']:
            today_date = timezone.now().date()
            base_qs_with_relations = base_qs.select_related('estimate__estimation_log').filter(
                estimate__estimation_log__pickup_date__isnull=False
            )
            filtered_ids = [
                booking.id for booking in base_qs_with_relations
                if (scope == 'today' and booking.estimate.estimation_log.pickup_date.date() == today_date) or
                   (scope == 'past' and booking.estimate.estimation_log.pickup_date.date() < today_date) or
                   (scope == 'future' and booking.estimate.estimation_log.pickup_date.date() > today_date)
            ]
            filtered_qs = base_qs.filter(id__in=filtered_ids)
            return filtered_qs.order_by('-estimate__estimation_log__pickup_date' if scope == 'past' else 'estimate__estimation_log__pickup_date')
        
        elif scope == 'cancelled':
            return base_qs.filter(cancellation_status=Booking.CANCELLED).order_by('-created_at')
        
        elif scope == 'archived':
            return Booking.objects.filter(is_archived=True).order_by('-created_at')
        
        return base_qs.select_related('estimate__estimation_log').order_by('estimate__estimation_log__pickup_date')
    
    @staticmethod
    def filter_bookings(scope=None, search_key=None, **filters):
        queryset = BookingStatsService._apply_scope_filter(scope)
        if search_key and search_key != 'total' and search_key.startswith('status_'):
            queryset = queryset.filter(status=search_key.replace('status_', ''))
        for field in ['billing_status', 'cancellation_status', 'payment_timing']:
            if field in filters:
                queryset = queryset.filter(**{field: filters[field]})
        return queryset.select_related(
            'estimate__estimation_log',
            'client', 
            'assigned_driver', 
            'assigned_partner'
        ).prefetch_related(
            'estimate__passengers',
            'estimate__estimate_attribute__attribute'
        )
    
    @staticmethod
    @transaction.atomic
    def update_booking_complete(booking_id, validated_data):
        return BookingStatsService.get_booking_by_id(booking_id)