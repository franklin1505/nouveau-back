from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from courses.models import Booking
from .services import BookingLogService

_booking_old_values = {}

@receiver(pre_save, sender=Booking)
def store_old_booking_values(sender, instance, **kwargs):
    """Stocker les anciennes valeurs avant modification"""
    if instance.pk:
        try:
            old_instance = Booking.objects.get(pk=instance.pk)
            _booking_old_values[instance.pk] = {
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
        except Booking.DoesNotExist:
            pass

@receiver(post_save, sender=Booking)
def log_booking_save(sender, instance, created, **kwargs):
    """Logger les créations et modifications de booking"""
    if created:
        BookingLogService.log_creation(instance)
    else:
        old_values = _booking_old_values.get(instance.pk, {})
        if old_values:
            changed_fields = _detect_changed_fields(instance, old_values)
            if changed_fields:
                _log_specific_changes(instance, old_values, changed_fields)
            
            _booking_old_values.pop(instance.pk, None)

@receiver(post_delete, sender=Booking)
def log_booking_deletion(sender, instance, **kwargs):
    """Logger les suppressions de booking"""
    BookingLogService.log_deletion(instance)

def _detect_changed_fields(instance, old_values):
    """Détecter les champs qui ont changé"""
    changed_fields = []
    
    for field, old_value in old_values.items():
        current_value = getattr(instance, field)
        if old_value != current_value:
            changed_fields.append(field)
    
    return changed_fields

def _log_specific_changes(instance, old_values, changed_fields):
    """Logger les changements spécifiques selon le type"""
    
    if 'status' in changed_fields:
        old_status = old_values['status']
        new_status = instance.status
        status_display_map = dict(Booking.STATUS_CHOICES)
        old_display = status_display_map.get(old_status, old_status)
        new_display = status_display_map.get(new_status, new_status)
        BookingLogService.log_status_change(instance, old_display, new_display)
    
    financial_fields = ['driver_sale_price', 'partner_sale_price', 'compensation', 'commission']
    for field in financial_fields:
        if field in changed_fields:
            old_value = old_values[field] or 0
            new_value = getattr(instance, field) or 0
            field_display = field.replace('_', ' ').title()
            BookingLogService.log_financial_change(instance, field_display, old_value, new_value)
    
    if 'assigned_driver' in changed_fields:
        new_driver = instance.assigned_driver
        if new_driver:
            driver_name = f"{new_driver.first_name} {new_driver.last_name}"
            BookingLogService.log_assignment(instance, "chauffeur", driver_name)
    
    if 'assigned_partner' in changed_fields:
        new_partner = instance.assigned_partner
        if new_partner:
            partner_name = new_partner.company_name
            BookingLogService.log_assignment(instance, "partenaire", partner_name)
    
    payment_fields = ['is_driver_paid', 'is_partner_paid']
    for field in payment_fields:
        if field in changed_fields:
            if getattr(instance, field):
                payment_type = "chauffeur" if "driver" in field else "partenaire"
                action = f"Paiement {payment_type} marqué comme effectué"
                BookingLogService.log_action(instance, action)
    
    if 'is_archived' in changed_fields and instance.is_archived:
        BookingLogService.log_action(instance, "Réservation archivée")
    
    other_fields = [f for f in changed_fields if f not in ['status', 'assigned_driver', 'assigned_partner', 'is_driver_paid', 'is_partner_paid', 'is_archived'] + financial_fields]
    if other_fields:
        BookingLogService.log_modification(instance, other_fields)