# courses/Reservations/Reservations_details/recurring_generators.py

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
import calendar


class DateCalculator:
    """Calculateur de dates pour tous types de récurrence"""
    
    @staticmethod
    def generate_occurrences(template, config):
        """Point d'entrée unifié pour génération d'occurrences"""
        recurrence_type = template.recurrence_type
        
        if recurrence_type == 'daily':
            return DateCalculator.generate_daily_occurrences(template, config)
        elif recurrence_type == 'weekly':
            return DateCalculator.generate_weekly_occurrences(template, config)
        elif recurrence_type == 'monthly':
            return DateCalculator.generate_monthly_occurrences(template, config)
        elif recurrence_type == 'yearly':
            return DateCalculator.generate_yearly_occurrences(template, config)
        elif recurrence_type == 'custom':
            return DateCalculator.generate_custom_occurrences(template, config)
        else:
            raise ValidationError(f"Type de récurrence '{recurrence_type}' non supporté")
    
    @staticmethod
    def generate_daily_occurrences(template, config):
        """Génère occurrences quotidiennes"""
        occurrences = []
        
        # Déterminer jours effectifs
        if config.weekdays:
            effective_days = config.weekdays
        else:
            effective_days = list(range(1, 8)) if config.include_weekends else list(range(1, 6))
        
        current_date = template.start_date
        occurrence_number = 1
        
        while (occurrence_number <= template.max_occurrences and 
               (not template.end_date or current_date <= template.end_date)):
            
            # Vérifier jour de la semaine
            if current_date.weekday() + 1 in effective_days:
                occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
                
                occurrences.append({
                    'occurrence_number': occurrence_number,
                    'scheduled_datetime': occurrence_datetime,
                    'template': template
                })
                occurrence_number += 1
            
            current_date += timedelta(days=1)
        
        return occurrences
    
    @staticmethod
    def generate_weekly_occurrences(template, config):
        """Génère occurrences hebdomadaires"""
        occurrences = []
        current_date = template.start_date
        
        for i in range(template.max_occurrences):
            if template.end_date and current_date > template.end_date:
                break
            
            occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
            
            occurrences.append({
                'occurrence_number': i + 1,
                'scheduled_datetime': occurrence_datetime,
                'template': template
            })
            
            # Avancer selon intervalle
            current_date += timedelta(weeks=config.frequency_interval)
        
        return occurrences
    
    @staticmethod
    def generate_monthly_occurrences(template, config):
        """Génère occurrences mensuelles"""
        occurrences = []
        current_date = template.start_date
        
        for i in range(template.max_occurrences):
            if template.end_date and current_date > template.end_date:
                break
            
            occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
            
            occurrences.append({
                'occurrence_number': i + 1,
                'scheduled_datetime': occurrence_datetime,
                'template': template
            })
            
            # Calculer prochaine date selon type
            if config.monthly_type == 'same_date':
                try:
                    current_date = current_date + relativedelta(months=config.frequency_interval)
                except ValueError:
                    # Gestion fin de mois (31 janvier -> février)
                    current_date = current_date.replace(day=1) + relativedelta(months=config.frequency_interval + 1)
                    current_date = current_date.replace(
                        day=min(template.start_date.day, 
                               calendar.monthrange(current_date.year, current_date.month)[1])
                    )
            else:  # same_position
                current_date = DateCalculator._calculate_same_position_date(
                    template.start_date, current_date, config.frequency_interval
                )
        
        return occurrences
    
    @staticmethod
    def generate_yearly_occurrences(template, config):
        """Génère occurrences annuelles"""
        occurrences = []
        current_date = template.start_date
        
        for i in range(template.max_occurrences):
            if template.end_date and current_date > template.end_date:
                break
            
            occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
            
            occurrences.append({
                'occurrence_number': i + 1,
                'scheduled_datetime': occurrence_datetime,
                'template': template
            })
            
            # Avancer selon intervalle
            try:
                current_date = current_date + relativedelta(years=config.frequency_interval)
            except ValueError:
                # Gestion année bissextile (29 février)
                current_date = current_date.replace(month=2, day=28) + relativedelta(years=config.frequency_interval)
        
        return occurrences
    
    @staticmethod
    def generate_custom_occurrences(template, config):
        """Génère occurrences personnalisées"""
        if config.pattern_type == 'days_of_week':
            return DateCalculator._generate_custom_days_of_week(template, config)
        elif config.pattern_type == 'interval_based':
            return DateCalculator._generate_custom_interval_based(template, config)
        elif config.pattern_type == 'specific_dates':
            return DateCalculator._generate_custom_specific_dates(template, config)
        else:
            raise ValidationError(f"Pattern type '{config.pattern_type}' non supporté")
    
    @staticmethod
    def _generate_custom_days_of_week(template, config):
        """Génère pour pattern days_of_week"""
        occurrences = []
        
        # Jours effectifs
        if config.weekdays:
            effective_days = config.weekdays
        else:
            effective_days = list(range(1, 8)) if config.include_weekends else list(range(1, 6))
        
        current_date = template.start_date
        occurrence_number = 1
        week_count = 0
        
        while (occurrence_number <= template.max_occurrences and 
               (not template.end_date or current_date <= template.end_date)):
            
            # Vérifier intervalle de semaines
            if week_count % config.frequency_interval == 0:
                if current_date.weekday() + 1 in effective_days:
                    occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
                    
                    # Gestion créneaux multiples
                    if config.enable_multiple_times and config.time_slots:
                        for time_slot in config.time_slots:
                            slot_datetime = DateCalculator._apply_time_slot(occurrence_datetime, time_slot)
                            occurrences.append({
                                'occurrence_number': occurrence_number,
                                'scheduled_datetime': slot_datetime,
                                'template': template
                            })
                            occurrence_number += 1
                            if occurrence_number > template.max_occurrences:
                                break
                    else:
                        occurrences.append({
                            'occurrence_number': occurrence_number,
                            'scheduled_datetime': occurrence_datetime,
                            'template': template
                        })
                        occurrence_number += 1
            
            current_date += timedelta(days=1)
            if current_date.weekday() == 0:  # Nouveau lundi
                week_count += 1
        
        return DateCalculator._apply_exclude_dates(occurrences, config.exclude_dates)
    
    @staticmethod
    def _generate_custom_interval_based(template, config):
        """Génère pour pattern interval_based"""
        occurrences = []
        current_date = template.start_date
        occurrence_number = 1
        
        while (occurrence_number <= template.max_occurrences and 
               (not template.end_date or current_date <= template.end_date)):
            
            occurrence_datetime = DateCalculator._combine_date_time(current_date, template.base_booking)
            
            # Gestion créneaux multiples
            if config.enable_multiple_times and config.time_slots:
                for time_slot in config.time_slots:
                    if occurrence_number > template.max_occurrences:
                        break
                    slot_datetime = DateCalculator._apply_time_slot(occurrence_datetime, time_slot)
                    occurrences.append({
                        'occurrence_number': occurrence_number,
                        'scheduled_datetime': slot_datetime,
                        'template': template
                    })
                    occurrence_number += 1
            else:
                occurrences.append({
                    'occurrence_number': occurrence_number,
                    'scheduled_datetime': occurrence_datetime,
                    'template': template
                })
                occurrence_number += 1
            
            current_date += timedelta(days=config.interval_days)
        
        return DateCalculator._apply_exclude_dates(occurrences, config.exclude_dates)
    
    @staticmethod
    def _generate_custom_specific_dates(template, config):
        """Génère pour pattern specific_dates"""
        occurrences = []
        
        for i, date_str in enumerate(config.specific_dates[:template.max_occurrences]):
            try:
                specific_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                
                # Appliquer timezone si nécessaire
                if timezone.is_naive(specific_datetime):
                    specific_datetime = timezone.make_aware(specific_datetime)
                
                # Vérifier plage autorisée
                if template.end_date and specific_datetime.date() > template.end_date:
                    continue
                
                # Gestion créneaux multiples
                if config.enable_multiple_times and config.time_slots:
                    for time_slot in config.time_slots:
                        slot_datetime = DateCalculator._apply_time_slot(specific_datetime, time_slot)
                        occurrences.append({
                            'occurrence_number': len(occurrences) + 1,
                            'scheduled_datetime': slot_datetime,
                            'template': template
                        })
                else:
                    occurrences.append({
                        'occurrence_number': i + 1,
                        'scheduled_datetime': specific_datetime,
                        'template': template
                    })
                    
            except (ValueError, TypeError) as e:
                print(f"Date invalide ignorée: {date_str} - {e}")
                continue
        
        return DateCalculator._apply_exclude_dates(occurrences, config.exclude_dates)
    
    @staticmethod
    def _combine_date_time(target_date, base_booking):
        """Combine date avec heure du booking de base"""
        if base_booking.booking_type == 'one_way':
            base_time = base_booking.estimate.estimation_log.pickup_date.time()
        else:
            outbound = base_booking.outbound_segment
            base_time = outbound.pickup_date.time() if outbound else datetime.now().time()
        
        combined = datetime.combine(target_date, base_time)
        return timezone.make_aware(combined) if timezone.is_naive(combined) else combined
    
    @staticmethod
    def _apply_time_slot(base_datetime, time_slot):
        """Applique créneau horaire spécifique"""
        try:
            slot_time = datetime.strptime(time_slot, '%H:%M').time()
            return base_datetime.replace(hour=slot_time.hour, minute=slot_time.minute)
        except ValueError:
            return base_datetime
    
    @staticmethod
    def _calculate_same_position_date(start_date, current_date, interval_months):
        """Calcule même position dans le mois (ex: 2ème mardi)"""
        # Position du jour dans le mois de départ
        start_weekday = start_date.weekday()
        start_week_of_month = (start_date.day - 1) // 7 + 1
        
        # Mois cible
        target_month = current_date + relativedelta(months=interval_months)
        
        # Trouver même jour de la semaine à même position
        first_day_of_month = target_month.replace(day=1)
        first_weekday = first_day_of_month.weekday()
        
        # Calculer décalage
        days_offset = (start_weekday - first_weekday) % 7
        target_day = 1 + days_offset + (start_week_of_month - 1) * 7
        
        # Vérifier que le jour existe
        last_day_of_month = calendar.monthrange(target_month.year, target_month.month)[1]
        
        if target_day <= last_day_of_month:
            return target_month.replace(day=target_day)
        else:
            # Prendre dernière occurrence du jour dans le mois
            target_day = target_day - 7
            return target_month.replace(day=target_day) if target_day > 0 else target_month.replace(day=1)
    
    @staticmethod
    def _apply_exclude_dates(occurrences, exclude_dates):
        """Applique les dates d'exclusion"""
        if not exclude_dates:
            return occurrences
        
        # Convertir exclude_dates en dates
        excluded_dates_set = set()
        for date_str in exclude_dates:
            try:
                excluded_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                excluded_dates_set.add(excluded_date)
            except (ValueError, TypeError):
                continue
        
        # Filtrer occurrences
        filtered_occurrences = []
        for occurrence in occurrences:
            if occurrence['scheduled_datetime'].date() not in excluded_dates_set:
                filtered_occurrences.append(occurrence)
        
        # Renuméroter
        for i, occurrence in enumerate(filtered_occurrences, 1):
            occurrence['occurrence_number'] = i
        
        return filtered_occurrences