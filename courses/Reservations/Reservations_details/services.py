from django.utils import timezone
from datetime import datetime, date
from courses.models import Booking
from django.db import transaction
from django.core.exceptions import ValidationError
from courses.models import Booking, Estimate, EstimationLog, Passenger, EstimateAttribute
from django.shortcuts import get_object_or_404

class BookingStatsService:
    
    @staticmethod
    def get_base_queryset():
        """Base queryset excluding archived by default"""
        return Booking.objects.filter(is_archived=False)
    
    @staticmethod
    def get_booking_by_id(booking_id):
        """Get booking by ID with all relations optimized"""
        return get_object_or_404(
            Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute'
            ),
            id=booking_id
        )
    
    @staticmethod
    def get_main_stats():
        """Calculate main dashboard statistics avec tri datetime optimal"""
        base_qs = BookingStatsService.get_base_queryset()
        
        bookings_with_dates = base_qs.select_related('estimate__estimation_log').filter(
            estimate__estimation_log__pickup_date__isnull=False
        ).order_by('estimate__estimation_log__pickup_date')
        
        today_date = timezone.now().date()
        
        today_count = 0
        past_count = 0
        future_count = 0
        
        print(f"🔍 Réservations triées par ordre chronologique:")
        for i, booking in enumerate(bookings_with_dates):
            pickup_datetime = booking.estimate.estimation_log.pickup_date
            pickup_date = pickup_datetime.date()
            
            if pickup_date == today_date:
                today_count += 1
                status = 'AUJOURD\'HUI'
            elif pickup_date < today_date:
                past_count += 1
                status = 'PASSÉ'
            else:
                future_count += 1
                status = 'FUTUR'
            
            print(f"  {i+1}. Booking {booking.id}: {pickup_datetime} [{status}]")
        
        return {
            'total_bookings': base_qs.count(),
            'today_bookings': today_count,
            'past_bookings': past_count,
            'future_bookings': future_count,
            'cancelled_bookings': base_qs.filter(
                cancellation_status=Booking.CANCELLED
            ).count(),
            'archived_bookings': Booking.objects.filter(is_archived=True).count()
        }
    
    @staticmethod
    def get_status_workflow_stats(scope=None):
        """Get status workflow statistics for given scope avec tri datetime"""
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        status_data = []
        total_count = queryset.count()
        
        status_data.append({
            'status': 'total',
            'status_display': 'Total',
            'count': total_count,
            'search_key': 'total'
        })
        
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
        """Calculate sub-statistics for billing, cancellation, payment"""
        return {
            'total': queryset.count(),
            'billing_status': BookingStatsService._get_billing_stats(queryset),
            'cancellation_status': BookingStatsService._get_cancellation_stats(queryset),
            'payment_timing': BookingStatsService._get_payment_timing_stats(queryset)
        }
    
    @staticmethod
    def _get_billing_stats(queryset):
        """Get billing status statistics with zeros"""
        stats = {}
        for status_code, status_display in Booking.BILLING_STATUS_CHOICES:
            stats[status_code] = queryset.filter(billing_status=status_code).count()
        return stats
    
    @staticmethod
    def _get_cancellation_stats(queryset):
        """Get cancellation status statistics with zeros"""
        stats = {}
        for status_code, status_display in Booking.CANCELLATION_STATUS_CHOICES:
            stats[status_code] = queryset.filter(cancellation_status=status_code).count()
        return stats
    
    @staticmethod
    def _get_payment_timing_stats(queryset):
        """Get payment timing statistics with zeros"""
        stats = {}
        for status_code, status_display in Booking.PAYMENT_TIMING_CHOICES:
            stats[status_code] = queryset.filter(payment_timing=status_code).count()
        return stats
    
    @staticmethod
    def _apply_scope_filter(scope):
        """Apply scope filter with optimized datetime sorting per scope"""
        base_qs = BookingStatsService.get_base_queryset()
        
        if scope in ['today', 'past', 'future']:
            today_date = timezone.now().date()
            
            base_qs_with_relations = base_qs.select_related('estimate__estimation_log').filter(
                estimate__estimation_log__pickup_date__isnull=False
            )
            
            filtered_ids = []
            
            for booking in base_qs_with_relations:
                pickup_date = booking.estimate.estimation_log.pickup_date.date()
                
                if scope == 'today' and pickup_date == today_date:
                    filtered_ids.append(booking.id)
                elif scope == 'past' and pickup_date < today_date:
                    filtered_ids.append(booking.id)
                elif scope == 'future' and pickup_date > today_date:
                    filtered_ids.append(booking.id)
            
            filtered_qs = base_qs.filter(id__in=filtered_ids)
            
            if scope == 'past':
                filtered_qs = filtered_qs.order_by('-estimate__estimation_log__pickup_date')
                print(f"🔍 Past bookings (plus récent → plus ancien):")
            elif scope == 'future':
                filtered_qs = filtered_qs.order_by('estimate__estimation_log__pickup_date')
                print(f"🔍 Future bookings (plus proche → plus éloigné):")
            else:
                filtered_qs = filtered_qs.order_by('estimate__estimation_log__pickup_date')
                print(f"🔍 Today bookings (chronologique):")
            
            for booking in filtered_qs:
                pickup = booking.estimate.estimation_log.pickup_date
                print(f"  -> Booking {booking.id}: {pickup}")
            
            return filtered_qs
            
        elif scope == 'cancelled':
            filtered_qs = base_qs.filter(cancellation_status=Booking.CANCELLED).order_by('-created_at')
            print(f"🔍 Cancelled bookings (plus récent → plus ancien):")
            for booking in filtered_qs:
                print(f"  -> Booking {booking.id}: créé le {booking.created_at}")
            return filtered_qs
            
        elif scope == 'archived':
            filtered_qs = Booking.objects.filter(is_archived=True).order_by('-created_at')
            print(f"🔍 Archived bookings (plus récent → plus ancien):")
            for booking in filtered_qs:
                print(f"  -> Booking {booking.id}: créé le {booking.created_at}")
            return filtered_qs
        
        return base_qs.select_related('estimate__estimation_log').order_by('estimate__estimation_log__pickup_date')
    
    @staticmethod
    def filter_bookings(scope=None, search_key=None, **filters):
        """Filter bookings avec tri optimisé par scope et optimisation des requêtes"""
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        if search_key and search_key != 'total':
            if search_key.startswith('status_'):
                status = search_key.replace('status_', '')
                queryset = queryset.filter(status=status)
        
        if 'billing_status' in filters:
            queryset = queryset.filter(billing_status=filters['billing_status'])
        if 'cancellation_status' in filters:
            queryset = queryset.filter(cancellation_status=filters['cancellation_status'])
        if 'payment_timing' in filters:
            queryset = queryset.filter(payment_timing=filters['payment_timing'])
        
        return queryset.select_related(
            'estimate__estimation_log',
            'client', 
            'assigned_driver', 
            'assigned_partner'
        ).prefetch_related(
            'estimate__passengers',
            'estimate__estimate_attribute'
        )