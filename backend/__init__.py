from __future__ import absolute_import, unicode_literals

# Charger Celery quand Django démarre
from .celery import app as celery_app

__all__ = ['celery_app']
