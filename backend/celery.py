from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery import shared_task
from celery.schedules import crontab

# Définir les paramètres Django par défaut pour Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# Charger les paramètres Celery à partir du fichier settings.py avec le préfixe CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Recherche automatique des tâches dans les modules de l'application
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

app.conf.beat_schedule = {
    'generate_notifications_daily': {
        'task': 'configurations.Vehicles.tasks.generate_tariff_rule_notifications',
        'schedule': crontab(hour=6, minute=0),  # Exécution quotidienne à 6h du matin
    },
}