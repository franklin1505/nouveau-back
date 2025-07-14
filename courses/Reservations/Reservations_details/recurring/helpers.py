# courses/Reservations/Reservations_details/recurring_helpers.py

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.core.exceptions import ValidationError


class BookingExtractor:
    """Extracteur unifié pour données booking"""
    
    @staticmethod
    def get_pickup_date(booking):
        """Extrait pickup_date selon type booking"""
        if booking.booking_type == 'one_way':
            return booking.estimate.estimation_log.pickup_date
        else:
            outbound = booking.outbound_segment
            return outbound.pickup_date if outbound else timezone.now()
    
    @staticmethod
    def get_base_booking_info(booking):
        """Info booking minimal standard"""
        return {
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'booking_type': booking.booking_type,
            'client_id': booking.client.id if booking.client else None
        }
    
    @staticmethod
    def get_trip_data(booking):
        """Données trajet selon type booking"""
        if booking.booking_type == 'one_way' and booking.estimate:
            log = booking.estimate.estimation_log
            return {
                'departure': log.departure,
                'destination': log.destination,
                'pickup_date': log.pickup_date.isoformat(),
                'total_cost': booking.estimate.total_booking_cost or 0
            }
        elif booking.booking_type == 'round_trip':
            outbound = booking.outbound_segment
            if outbound:
                return {
                    'departure': outbound.departure,
                    'destination': outbound.destination,
                    'pickup_date': outbound.pickup_date.isoformat(),
                    'total_cost': booking.total_cost_calculated
                }
        return {}


class DateHelper:
    """Helper pour calculs de dates intelligents"""
    
    @staticmethod
    def calculate_intelligent_dates(base_date, recurrence_type):
        """Calcule start/end dates intelligentes selon type"""
        dates_map = {
            'daily': {
                'start': base_date,
                'end': base_date + timedelta(days=30),
                'max_occurrences': 22
            },
            'weekly': {
                'start': base_date + timedelta(days=7),
                'end': base_date + timedelta(days=90),
                'max_occurrences': 12
            },
            'monthly': {
                'start': base_date + relativedelta(months=1),
                'end': base_date + relativedelta(months=6),
                'max_occurrences': 6
            },
            'yearly': {
                'start': base_date + relativedelta(years=1),
                'end': base_date + relativedelta(years=3),
                'max_occurrences': 3
            },
            'custom': {
                'start': base_date,
                'end': base_date + timedelta(days=90),
                'max_occurrences': 50
            }
        }
        return dates_map.get(recurrence_type, dates_map['daily'])
    
    @staticmethod
    def format_date_range(start_date, end_date):
        """Formate range de dates pour affichage"""
        start_str = start_date.strftime("%d %B %Y")
        end_str = end_date.strftime("%d %B %Y")
        return start_str, end_str


class ConfigBuilder:
    """Builder pour configurations de récurrence"""
    
    @staticmethod
    def build_base_config(name, recurrence_type, dates_info):
        """Config de base commune à tous types"""
        return {
            "name": name,
            "recurrence_type": recurrence_type,
            "start_date": dates_info['start'].isoformat(),
            "end_date": dates_info['end'].isoformat(),
            "max_occurrences": dates_info['max_occurrences']
        }
    
    @staticmethod
    def build_daily_config(booking, dates_info):
        """Config spécifique daily"""
        base = ConfigBuilder.build_base_config(
            f"Transport quotidien - {booking.booking_number}",
            "daily",
            dates_info
        )
        base.update({
            "include_weekends": False,
            "weekdays": []
        })
        return base
    
    @staticmethod
    def build_weekly_config(booking, dates_info):
        """Config spécifique weekly"""
        base = ConfigBuilder.build_base_config(
            f"Transport hebdomadaire - {booking.booking_number}",
            "weekly",
            dates_info
        )
        base.update({
            "frequency_interval": 1
        })
        return base
    
    @staticmethod
    def build_monthly_config(booking, dates_info):
        """Config spécifique monthly"""
        base = ConfigBuilder.build_base_config(
            f"Transport mensuel - {booking.booking_number}",
            "monthly",
            dates_info
        )
        base.update({
            "monthly_type": "same_date",
            "frequency_interval": 1
        })
        return base
    
    @staticmethod
    def build_yearly_config(booking, dates_info):
        """Config spécifique yearly"""
        base = ConfigBuilder.build_base_config(
            f"Transport annuel - {booking.booking_number}",
            "yearly",
            dates_info
        )
        base.update({
            "frequency_interval": 1
        })
        return base
    
    @staticmethod
    def build_custom_config(booking, dates_info):
        """Config spécifique custom"""
        base = ConfigBuilder.build_base_config(
            f"Transport personnalisé - {booking.booking_number}",
            "custom",
            dates_info
        )
        base.update({
            "pattern_type": "days_of_week",
            "frequency_interval": 1,
            "include_weekends": False,
            "weekdays": [],
            "interval_days": None,
            "specific_dates": [],
            "enable_multiple_times": False,
            "time_slots": [],
            "enable_multiple_periods": False,
            "exclude_dates": []
        })
        return base


class DescriptionBuilder:
    """Builder pour descriptions dynamiques"""
    
    @staticmethod
    def build_description(recurrence_type, start_str, end_str, max_occurrences, params=None):
        """Description dynamique selon type"""
        params = params or {}
        
        templates = {
            'daily': "Répétition quotidienne du {start} au {end}, maximum {max} réservations{weekend_text}, génération automatique basée sur la date de pickup du booking source",
            'weekly': "Répétition hebdomadaire du {start} au {end}, maximum {max} réservations {interval_text}, génération automatique avec intervalle d'une semaine après la date de pickup du booking source", 
            'monthly': "Répétition mensuelle du {start} au {end}, maximum {max} réservations toutes les {interval_text} {type_text}, génération automatique avec même date que le booking source",
            'yearly': "Répétition annuelle du {start} au {end}, maximum {max} réservations toutes les {interval_text} à la même date anniversaire, génération automatique basée sur la date de pickup du booking source",
            'custom': "Configuration flexible du {start} au {end}, maximum {max} réservations avec patterns personnalisés (jours spécifiques, intervalles fixes, dates manuelles), créneaux multiples et périodes configurables selon besoins métier"
        }
        
        template = templates.get(recurrence_type, templates['daily'])
        
        # Variables spécifiques par type
        format_vars = {
            'start': start_str,
            'end': end_str,
            'max': max_occurrences
        }
        
        if recurrence_type == 'daily':
            weekend_text = " en jours ouvrables uniquement (weekends exclus)" if not params.get('include_weekends') else " incluant weekends"
            format_vars['weekend_text'] = weekend_text
        
        elif recurrence_type == 'weekly':
            interval = params.get('frequency_interval', 1)
            interval_text = f"toutes les {interval} semaine(s)" if interval > 1 else "chaque semaine"
            format_vars['interval_text'] = interval_text
        
        elif recurrence_type == 'monthly':
            interval = params.get('frequency_interval', 1)
            monthly_type = params.get('monthly_type', 'same_date')
            type_text = "à la même date du mois" if monthly_type == 'same_date' else "à la même position dans le mois"
            interval_text = f"{interval} mois" if interval > 1 else "1 mois"
            format_vars.update({
                'interval_text': interval_text,
                'type_text': type_text
            })
        
        elif recurrence_type == 'yearly':
            interval = params.get('frequency_interval', 1)
            interval_text = f"{interval} année(s)" if interval > 1 else "1 année(s)"
            format_vars['interval_text'] = interval_text
        
        return template.format(**format_vars)


class ValidationHelper:
    """Helper pour validations récurrentes"""
    
    @staticmethod
    def validate_booking_for_recurring(booking_id):
        """✅ CORRIGÉ : Validation avec chargement complet des relations"""
        try:
            from courses.models import Booking
            
            # ✅ CHARGEMENT COMPLET des relations nécessaires
            booking = Booking.objects.select_related(
                'estimate__estimation_log', 
                'estimate__user_choice', 
                'estimate__payment_method',
                'estimate__meeting_place',
                'client',
                'assigned_driver',
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute__attribute',
                'segments__estimate__estimation_log',
                'segments__estimate__passengers',
                'segments__estimate__estimate_attribute__attribute'
            ).get(id=booking_id)
            
            if booking.cancellation_status == 'cancelled':
                return None, "Impossible de créer une récurrence depuis un booking annulé"
            
            if hasattr(booking, 'recurring_templates') and booking.recurring_templates.filter(is_active=True).exists():
                return None, "Ce booking a déjà une récurrence active"
            
            # ✅ VÉRIFICATION que le booking a les données nécessaires
            if booking.booking_type == 'one_way':
                if not booking.estimate or not booking.estimate.estimation_log:
                    return None, "Booking one_way sans estimate/estimation_log complet"
            else:
                outbound = booking.outbound_segment
                if not outbound or not outbound.estimate or not outbound.estimate.estimation_log:
                    return None, "Booking round_trip sans segment outbound complet"
            
            print(f"✅ Booking {booking_id} validé avec relations chargées")
            return booking, None
            
        except Booking.DoesNotExist:
            return None, f"Booking avec l'ID {booking_id} non trouvé"
        except Exception as e:
            return None, f"Erreur lors de la validation: {str(e)}"
    
    @staticmethod
    def get_max_limits():
        """Limites max par type de récurrence"""
        return {
            'daily': {'max_occurrences_weekdays': 260, 'max_occurrences_with_weekends': 365, 'max_period_days': 365},
            'weekly': {'max_occurrences': 52, 'max_frequency_interval': 4, 'max_period_weeks': 52},
            'monthly': {'max_occurrences': 12, 'max_frequency_interval': 6, 'max_period_months': 12},
            'yearly': {'max_occurrences': 5, 'max_frequency_interval': 3, 'max_period_years': 5},
            'custom': {'max_occurrences': 365, 'max_time_slots': 5, 'max_periods': 4, 'max_specific_dates': 100, 'max_exclude_dates': 50}
        }


class ResponseHelper:
    """✅ SUPPRIMÉ - Utilisation directe de create_response des helpers existants"""
    pass


class LogHelper:
    """✅ OPTIMISÉ - Helper pour logs unifiés selon logique existante"""
    
    @staticmethod
    def create_template_log(template, user, total_occurrences):
        """Log création template sur le booking de base"""
        if not user:
            return
        
        try:
            from courses.models import BookingLog
            from courses.Reservations.Reservations_details.helpers import shorten_address, format_date_business
            
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            
            # Description détaillée de la config
            config_desc = f"Type: {template.get_recurrence_type_display()}"
            config_desc += f", {total_occurrences} occurrences"
            config_desc += f", période: {template.start_date.strftime('%d/%m/%Y')}"
            if template.end_date:
                config_desc += f" au {template.end_date.strftime('%d/%m/%Y')}"
            
            message = (
                f"Template récurrence créé par {user_display}. "
                f"{config_desc}. Booking source: {template.base_booking.booking_number}"
            )
            
            # ✅ LOG SUR LE BOOKING DE BASE
            BookingLog.objects.create(
                booking=template.base_booking, 
                user=user, 
                action=message
            )
            print(f"✅ Log template créé: {message}")
            
        except Exception as e:
            print(f"❌ Erreur log template: {e}")
    
    @staticmethod
    def create_recurring_booking_log(new_booking_id, user, template, occurrence, modifications=None):
        """Log création booking récurrent sur le nouveau booking"""
        if not user:
            return
        
        try:
            from courses.models import BookingLog, Booking
            from courses.Reservations.Reservations_details.helpers import format_date_business
            
            new_booking = Booking.objects.get(id=new_booking_id)
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            
            # Date formatée
            date_str = format_date_business(occurrence.scheduled_datetime)
            
            # Message de base
            message = (
                f"Course récurrente créée par {user_display} "
                f"le {date_str}. "
                f"Basée sur {template.base_booking.booking_number} "
                f"(occurrence #{occurrence.occurrence_number})"
            )
            
            # Ajout modifications si présentes
            if modifications:
                mod_list = list(modifications)
                if len(mod_list) <= 3:
                    message += f". Modifications: {', '.join(mod_list)}"
                else:
                    message += f". {len(mod_list)} champs modifiés"
            
            # ✅ LOG SUR LE NOUVEAU BOOKING
            BookingLog.objects.create(
                booking=new_booking, 
                user=user, 
                action=message
            )
            print(f"✅ Log booking récurrent créé: {message}")
            
        except Exception as e:
            print(f"❌ Erreur log booking récurrent: {e}")
    
    @staticmethod
    def create_creation_final_log(template, base_booking, created_count, errors_count, deleted_count, user):
        """Log final de création sur le booking de base"""
        if not user:
            return
        
        try:
            from courses.models import BookingLog
            
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            
            message = (
                f"Récurrence exécutée par {user_display}. "
                f"{created_count} courses créées"
            )
            
            if deleted_count > 0:
                message += f", {deleted_count} occurrences supprimées"
            
            if errors_count > 0:
                message += f", {errors_count} erreurs"
            
            message += f". Template: {template.name}"
            
            # ✅ LOG SUR LE BOOKING DE BASE
            BookingLog.objects.create(
                booking=base_booking, 
                user=user, 
                action=message
            )
            print(f"✅ Log création final: {message}")
            
        except Exception as e:
            print(f"❌ Erreur log création final: {e}")


class ConfigModelHelper:
    """Helper pour création modèles configuration"""
    
    @staticmethod
    def create_config_by_type(template, config_data):
        """Crée config selon type avec filtrage des champs spécifiques"""
        from courses.models import (
            DailyRecurrenceConfig, WeeklyRecurrenceConfig, MonthlyRecurrenceConfig,
            YearlyRecurrenceConfig, CustomRecurrenceConfig
        )
        
        recurrence_type = template.recurrence_type
        
        # ✅ FILTRAGE DES CHAMPS SELON LE TYPE
        field_mappings = {
            'daily': ['include_weekends', 'weekdays'],
            'weekly': ['frequency_interval'],
            'monthly': ['monthly_type', 'frequency_interval'],
            'yearly': ['frequency_interval'],
            'custom': [
                'pattern_type', 'frequency_interval', 'include_weekends', 'weekdays',
                'interval_days', 'specific_dates', 'enable_multiple_times', 'time_slots',
                'enable_multiple_periods', 'exclude_dates'
            ]
        }
        
        # Champs template à exclure
        template_fields = ['name', 'recurrence_type', 'start_date', 'end_date', 'max_occurrences']
        
        # Champs autorisés pour ce type
        allowed_fields = field_mappings.get(recurrence_type, [])
        
        # Nettoyer données selon le type
        clean_data = {}
        for key, value in config_data.items():
            if key not in template_fields and key in allowed_fields:
                clean_data[key] = value
        
        config_map = {
            'daily': DailyRecurrenceConfig,
            'weekly': WeeklyRecurrenceConfig,
            'monthly': MonthlyRecurrenceConfig,
            'yearly': YearlyRecurrenceConfig,
            'custom': CustomRecurrenceConfig
        }
        
        config_class = config_map.get(recurrence_type)
        if not config_class:
            raise ValidationError(f"Type de récurrence '{recurrence_type}' non supporté")
        
        print(f"✅ Création {recurrence_type} config avec: {clean_data}")
        return config_class.objects.create(template=template, **clean_data)


class EstimateHelper:
    """Helper pour données estimate selon type booking"""
    
    @staticmethod
    def get_estimate_data(booking):
        """Retourne estimate principal selon type booking"""
        if booking.booking_type == 'one_way':
            return booking.estimate
        else:
            outbound = booking.outbound_segment
            return outbound.estimate if outbound else None
    
    @staticmethod
    def get_estimation_log(booking):
        """Retourne estimation_log principal"""
        estimate = EstimateHelper.get_estimate_data(booking)
        return estimate.estimation_log if estimate else None