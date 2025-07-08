from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from courses.models import Booking
from .services import BookingLogService

_booking_old_values = {}

@receiver(pre_save, sender=Booking)
def store_old_booking_values(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute'
            ).get(pk=instance.pk)
            old_values = {
                'status': old_instance.status,
                'billing_status': old_instance.billing_status,
                'cancellation_status': old_instance.cancellation_status,
                'payment_timing': old_instance.payment_timing,
                'driver_sale_price': old_instance.driver_sale_price,
                'partner_sale_price': old_instance.partner_sale_price,
                'compensation': old_instance.compensation,
                'commission': old_instance.commission,
                'assigned_driver': old_instance.assigned_driver,
                'assigned_partner': old_instance.assigned_partner,
                'is_archived': old_instance.is_archived,
                'is_driver_paid': old_instance.is_driver_paid,
                'is_partner_paid': old_instance.is_partner_paid,
            }
            if old_instance.estimate:
                old_values['estimate_snapshot'] = {
                    'total_booking_cost': old_instance.estimate.total_booking_cost,
                    'total_attributes_cost': old_instance.estimate.total_attributes_cost,
                    'flight_number': old_instance.estimate.flight_number,
                    'number_of_luggages': old_instance.estimate.number_of_luggages,
                    'number_of_passengers': old_instance.estimate.number_of_passengers,
                    'message': old_instance.estimate.message,
                    'case_number': old_instance.estimate.case_number,
                    'is_payment_pending': old_instance.estimate.is_payment_pending,
                }
                if old_instance.estimate.estimation_log:
                    old_values['estimation_log_snapshot'] = {
                        'departure': old_instance.estimate.estimation_log.departure,
                        'destination': old_instance.estimate.estimation_log.destination,
                        'pickup_date': old_instance.estimate.estimation_log.pickup_date,
                        'distance_travelled': old_instance.estimate.estimation_log.distance_travelled,
                        'duration_travelled': old_instance.estimate.estimation_log.duration_travelled,
                        'estimate_type': old_instance.estimate.estimation_log.estimate_type,
                    }
            _booking_old_values[instance.pk] = old_values
        except Booking.DoesNotExist:
            pass

@receiver(post_save, sender=Booking)
def log_booking_save(sender, instance, created, **kwargs):
    if created:
        current_user = BookingLogService.get_current_user()
        if not current_user and instance.estimate and instance.estimate.estimation_log and instance.estimate.estimation_log.user:
            BookingLogService.log_detailed_creation(instance, instance.estimate.estimation_log.user)
        else:
            BookingLogService.log_detailed_creation(instance, current_user)
    else:
        old_values = _booking_old_values.get(instance.pk, {})
        if old_values:
            instance.refresh_from_db()
            instance = Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute'
            ).get(pk=instance.pk)
            BookingLogService.log_comprehensive_modification(instance, old_values)
            _booking_old_values.pop(instance.pk, None)

@receiver(post_delete, sender=Booking)
def log_booking_deletion(sender, instance, **kwargs):
    BookingLogService.log_deletion(instance)