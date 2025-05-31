import random
import string
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from configurations.models import TariffRule, Vehicle

def create_response(status_type, message, data=None, http_status=status.HTTP_200_OK, error=None):
    response_payload = {
        "status": status_type,
        "message": message,
        "data": data if data else {},
        "http_status": http_status,
    }
    if error:
        response_payload["error"] = str(error)

    return Response(response_payload, status=http_status)

class StatsGenerator:
    def __init__(self):
        self.current_date = timezone.now()
        self.expiration_threshold = self.current_date + timedelta(days=3)
        self.search_keys = {}
        self.used_keys = set()

    def generate_search_key(self, prefix=''):
        """Génère une clé de recherche courte et unique (6 caractères + préfixe)"""
        characters = string.ascii_lowercase + string.digits
        while True:
            key = prefix + ''.join(random.choices(characters, k=6))
            if key not in self.used_keys:
                self.used_keys.add(key)
                return key

    def get_vehicle_stats(self):
        """Génère les statistiques des véhicules"""
        stats = {
            'totalVehicles': {
                'query': Vehicle.objects.all(),
                'label': 'Nombre total de véhicules enregistrés'
            },
            'activeVehicles': {
                'query': Vehicle.objects.filter(validation=True),
                'label': 'Nombre de véhicules actifs'
            },
            'inactiveVehicles': {
                'query': Vehicle.objects.filter(validation=False),
                'label': 'Nombre de véhicules inactifs'
            },
            'vehiclesWithPricingRules': {
                'query': Vehicle.objects.filter(tariff_rules__isnull=False).distinct(),
                'label': 'Nombre de véhicules avec des règles tarifaires'
            },
            'classicPricingVehicles': {
                'query': Vehicle.objects.filter(
                    tariff_rules__package__package_type='classic'
                ).distinct(),
                'label': 'Nombre de véhicules sous forfait classique'
            },
            'rangePricingVehicles': {
                'query': Vehicle.objects.filter(
                    tariff_rules__package__package_type='radius'
                ).distinct(),
                'label': 'Nombre de véhicules sous forfait de rayon'
            },
            'vehiclesWithSurcharges': {
                'query': Vehicle.objects.filter(
                    tariff_rules__adjustment__adjustment_type='increase'
                ).distinct(),
                'label': 'Nombre de véhicules avec majorations'
            },
            'vehiclesWithDiscounts': {
                'query': Vehicle.objects.filter(
                    tariff_rules__adjustment__adjustment_type='discount'
                ).distinct(),
                'label': 'Nombre de véhicules avec réductions'
            },
            'vehiclesWithPromoCodes': {
                'query': Vehicle.objects.filter(
                    tariff_rules__promo_code__isnull=False
                ).distinct(),
                'label': 'Nombre de véhicules avec codes promo'
            },
            'vehiclesWithExpiringRules': {
                'query': Vehicle.objects.filter(
                    tariff_rules__active=True,
                    tariff_rules__end_date__range=[self.current_date, self.expiration_threshold]
                ).distinct(),
                'label': 'Nombre de véhicules avec règles expirant sous 3 jours'
            },
            'vehiclesWithExpiredRules': {
                'query': Vehicle.objects.filter(
                    tariff_rules__end_date__lt=self.current_date
                ).distinct(),
                'label': 'Nombre de véhicules avec règles expirées'
            }
        }
        
        result = {}
        for key, config in stats.items():
            search_key = self.generate_search_key('v_')
            result[key] = {
                'count': config['query'].count(),
                'search_key': search_key
            }
            self.search_keys[search_key] = config['query']
        return result

    def get_tariff_rule_stats(self):
        """Génère les statistiques des règles tarifaires"""
        stats = {
            'totalRules': {
                'query': TariffRule.objects.all(),
                'label': 'Nombre total de règles tarifaires'
            },
            'totalAdjustments': {
                'query': TariffRule.objects.filter(rule_type='adjustment'),
                'label': 'Nombre total de règles d’ajustement'
            },
            'totalPackages': {
                'query': TariffRule.objects.filter(rule_type='package'),
                'label': 'Nombre total de règles de forfait'
            },
            'totalPromoCodes': {
                'query': TariffRule.objects.filter(rule_type='promo_code'),
                'label': 'Nombre total de règles de code promo'
            },
            'activeRules': {
                'query': TariffRule.objects.filter(active=True),
                'label': 'Nombre de règles tarifaires actives'
            },
            'inactiveRules': {
                'query': TariffRule.objects.filter(active=False),
                'label': 'Nombre de règles tarifaires inactives'
            },
            'rulesForAllClients': {
                'query': TariffRule.objects.filter(available_to_all=True),
                'label': 'Nombre de règles accessibles à tous'
            },
            'restrictedRules': {
                'query': TariffRule.objects.filter(available_to_all=False),
                'label': 'Nombre de règles restreintes'
            },
            'specificRules': {
                'query': TariffRule.objects.filter(specific_clients__isnull=False).distinct(),
                'label': 'Nombre de règles pour clients spécifiques'
            },
            'expiringSoonRules': {
                'query': TariffRule.objects.filter(
                    active=True,
                    end_date__range=[self.current_date, self.expiration_threshold]
                ),
                'label': 'Nombre de règles actives expirant sous 3 jours'
            }
        }
        
        result = {}
        for key, config in stats.items():
            search_key = self.generate_search_key('t_')
            result[key] = {
                'count': config['query'].count(),
                'search_key': search_key
            }
            self.search_keys[search_key] = config['query']
        return result

#