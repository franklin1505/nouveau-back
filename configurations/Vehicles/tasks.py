from celery import shared_task
from django.utils.timezone import now, timedelta
from django.db import models
from ..models import TariffRule, Notification

@shared_task
def generate_tariff_rule_notifications():
    """
    Tâche pour détecter les règles expirant aujourd'hui, celles ayant atteint leur limite d'utilisation,
    et celles expirées hier selon 'application_date'.
    """
    current_date = now().date()
    yesterday_date = current_date - timedelta(days=1)
    tomorrow_date = current_date + timedelta(days=1)

    # 1. Règles expirant aujourd'hui (end_date)
    expiring_today_rules = TariffRule.objects.filter(
        active=True,
        end_date__date=current_date
    )

    for rule in expiring_today_rules:
        if not Notification.objects.filter(related_rule=rule, type="expiration", status="unread").exists():
            Notification.objects.create(
                title="Expiration aujourd'hui de la règle tarifaire",
                message=f"La règle '{rule.name}' expire aujourd'hui, le {current_date.strftime('%d/%m/%Y')}.",
                type="expiration",
                related_rule=rule
            )

    # 2. Règles ayant atteint leur limite d'utilisation
    usage_limit_reached_rules = TariffRule.objects.filter(
        active=True,
        promo_code__isnull=False,
        promo_code__usage_limit__isnull=False,
        promo_code__usage_count__gte=models.F("promo_code__usage_limit")
    )

    for rule in usage_limit_reached_rules:
        if not Notification.objects.filter(related_rule=rule, type="usage_limit", status="unread").exists():
            Notification.objects.create(
                title="Limite d'utilisation atteinte",
                message=f"La règle '{rule.name}' a atteint sa limite d'utilisation fixée à {rule.promo_code.usage_limit} utilisations.",
                type="usage_limit",
                related_rule=rule
            )

    # 3. Règles expirées hier selon 'application_date'
    expired_yesterday_rules = TariffRule.objects.filter(
        active=True,
        application_date=yesterday_date
    )

    for rule in expired_yesterday_rules:
        if not Notification.objects.filter(related_rule=rule, type="application_date_expired", status="unread").exists():
            Notification.objects.create(
                title="Expiration de la règle tarifaire hier",
                message=f"La règle '{rule.name}' configurée pour le {rule.application_date.strftime('%d/%m/%Y')} a expiré hier.",
                type="application_date_expired",
                related_rule=rule
            )
            
    # 4. Règles actives aujourd'hui selon 'application_date'
    active_today_rules = TariffRule.objects.filter(
        active=True,
        application_date=current_date
    )

    for rule in active_today_rules:
        if not Notification.objects.filter(related_rule=rule, type="application_date_active", status="unread").exists():
            Notification.objects.create(
                title="Règle tarifaire active aujourd'hui",
                message=f"La règle '{rule.name}' est active aujourd'hui, le {current_date.strftime('%d/%m/%Y')}.",
                type="application_date_active",
                related_rule=rule
            )
            
    # 5. Règles qui seront actives demain selon 'application_date'
    active_tomorrow_rules = TariffRule.objects.filter(
        active=True,
        application_date=tomorrow_date
    )

    for rule in active_tomorrow_rules:
        if not Notification.objects.filter(related_rule=rule, type="application_date_upcoming", status="unread").exists():
            Notification.objects.create(
                title="Règle tarifaire active demain",
                message=f"La règle '{rule.name}' sera active demain, le {tomorrow_date.strftime('%d/%m/%Y')}.",
                type="application_date_upcoming",
                related_rule=rule
            )

    return f"""
        {len(expiring_today_rules)} notifications d'expiration aujourd'hui, 
        {len(usage_limit_reached_rules)} notifications de limite d'utilisation, 
        {len(expired_yesterday_rules)} notifications de règles expirées hier,
        {len(active_today_rules)} notifications de règles actives aujourd'hui,
        {len(active_tomorrow_rules)} notifications de règles actives demain.
    """


""" celery -A backend worker --loglevel=info
celery -A backend beat --loglevel=info """
