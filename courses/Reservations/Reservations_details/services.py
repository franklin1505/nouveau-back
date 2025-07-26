from django.utils import timezone
from django.db.models import Q, Count, Case, When
from django.shortcuts import get_object_or_404
from courses.models import Booking, RecurringBookingTemplate

class BookingStatsService:
    
    @staticmethod
    def get_base_queryset():
        return Booking.objects.filter(is_archived=False)
    
    @staticmethod
    def get_booking_by_id(booking_id):
        return get_object_or_404(
            Booking.objects.select_related(
                'estimate__estimation_log', 'client', 'assigned_driver', 'assigned_partner'
            ).prefetch_related(
                'estimate__passengers', 'estimate__estimate_attribute__attribute',
                'segments__estimate__estimation_log', 'segments__estimate__passengers',
                'segments__estimate__estimate_attribute__attribute',
                'recurring_occurrence__template__monthly_configuration',
                'recurring_occurrence__template__custom_configuration'
            ),
            id=booking_id
        )
    
    @staticmethod
    def get_global_stats_data(scope=None, search_key=None):
        if scope and scope != 'total':
            filtered_queryset = BookingStatsService._apply_scope_filter(scope)
            main_stats = BookingStatsService._calculate_main_stats_for_queryset(filtered_queryset)
        else:
            main_stats = BookingStatsService.get_main_stats()
        
        status_workflow = BookingStatsService.get_status_workflow_stats(scope, search_key)
        
        response_data = {
            'main_stats': main_stats,
            'status_workflow': status_workflow
        }
        
        BookingStatsService._add_specialized_workflows(response_data, scope, search_key)
        return response_data
    
    @staticmethod
    def get_user_filtered_stats(user, scope=None, search_key=None):
        from .user_permissions import BookingUserPermissionService
        
        if scope and scope != 'total':
            scope_filtered_queryset = BookingStatsService._apply_scope_filter(scope)
            user_filtered_queryset = BookingUserPermissionService.apply_user_booking_filter(scope_filtered_queryset, user)
            main_stats = BookingStatsService._calculate_main_stats_for_queryset(user_filtered_queryset)
        else:
            base_queryset = BookingStatsService.get_base_queryset()
            user_filtered_queryset = BookingUserPermissionService.apply_user_booking_filter(base_queryset, user)
            main_stats = BookingStatsService._calculate_main_stats_for_queryset(user_filtered_queryset)
        
        status_workflow = BookingStatsService._get_user_status_workflow(user_filtered_queryset, scope, search_key)
        
        response_data = {
            'main_stats': main_stats,
            'status_workflow': status_workflow
        }
        
        BookingStatsService._add_specialized_workflows(response_data, scope, search_key)
        return response_data
    
    @staticmethod
    def get_filtered_bookings(params):
        additional_filters = {
            k: v for k, v in params.items() 
            if k in ['billing_status', 'cancellation_status', 'payment_timing'] and v
        }
        
        return BookingStatsService.filter_bookings(
            scope=params.get('scope'),
            search_key=params.get('search_key'),
            **additional_filters
        )
    
    @staticmethod
    def get_user_filtered_bookings(user, params):
        from .user_permissions import BookingUserPermissionService
        
        queryset = BookingStatsService.get_filtered_bookings(params)
        return BookingUserPermissionService.apply_user_booking_filter(queryset, user)
    
    @staticmethod
    def get_funnel_sub_stats(queryset, scope, search_key):
        """Calcule les sub_stats selon la logique d'entonnoir"""
        filter_level = BookingStatsService._determine_filter_level(scope, search_key)
        
        if filter_level == 1:
            return BookingStatsService._get_level_1_sub_stats(queryset, scope)
        elif filter_level == 2:
            return BookingStatsService._get_level_2_sub_stats(queryset)
        else:
            return BookingStatsService._get_level_3_sub_stats(queryset)
    
    @staticmethod
    def _determine_filter_level(scope, search_key):
        """Détermine le niveau de filtrage actuel"""
        if not search_key or search_key == 'total':
            return 1
        
        level_2_prefixes = ['status_', 'booking_type_', 'recurring_type_', 'recurring_monthly_', 'recurring_custom_']
        level_3_keys = ['billing_status', 'cancellation_status', 'payment_timing']
        
        if any(search_key.startswith(prefix) for prefix in level_2_prefixes):
            return 2
        elif any(key in search_key for key in level_3_keys):
            return 3
        
        return 1
    
    @staticmethod
    def _get_level_1_sub_stats(queryset, scope):
        """Sub-stats niveau 1 : status et booking_type ou recurring_types"""
        base_stats = {'total': queryset.count()}
        
        if scope == 'recurring':
            base_stats.update(BookingStatsService._get_recurring_types_stats(queryset))
            base_stats.update(BookingStatsService._get_template_status_stats(queryset))
        else:
            base_stats.update(BookingStatsService._get_status_stats(queryset))
            base_stats.update(BookingStatsService._get_booking_type_stats(queryset))
        
        return base_stats
    
    @staticmethod
    def _get_level_2_sub_stats(queryset):
        """Sub-stats niveau 2 : billing_status, cancellation_status, payment_timing"""
        return {
            'total': queryset.count(),
            'billing_status': BookingStatsService._aggregate_field_stats(queryset, 'billing_status', Booking.BILLING_STATUS_CHOICES),
            'cancellation_status': BookingStatsService._aggregate_field_stats(queryset, 'cancellation_status', Booking.CANCELLATION_STATUS_CHOICES),
            'payment_timing': BookingStatsService._aggregate_field_stats(queryset, 'payment_timing', Booking.PAYMENT_TIMING_CHOICES)
        }
    
    @staticmethod
    def _get_level_3_sub_stats(queryset):
        """Sub-stats niveau 3 : liste finale, pas de sous-statistiques"""
        return {'total': queryset.count()}
    
    @staticmethod
    def _get_status_stats(queryset):
        """Stats de statut avec consolidation des doublons"""
        status_aggregation = {}
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        # Consolider les counts par statut
        for item in status_counts:
            status_code = item['status']
            if status_code in status_aggregation:
                status_aggregation[status_code] += item['count']
            else:
                status_aggregation[status_code] = item['count']
        
        # Initialiser tous les statuts possibles à 0
        status_dict = {code: 0 for code, _ in Booking.STATUS_CHOICES}
        
        # Mettre à jour avec les vraies valeurs
        for status_code, count in status_aggregation.items():
            if status_code in status_dict:
                status_dict[status_code] = count
        
        return {'status': status_dict}
    
    @staticmethod
    def _get_booking_type_stats(queryset):
        """Stats de type de booking avec consolidation des doublons"""
        booking_type_aggregation = {}
        booking_type_counts = queryset.values('booking_type').annotate(count=Count('id'))
        
        # Consolider les counts par type
        for item in booking_type_counts:
            booking_type = item['booking_type']
            if booking_type in booking_type_aggregation:
                booking_type_aggregation[booking_type] += item['count']
            else:
                booking_type_aggregation[booking_type] = item['count']
        
        # Initialiser tous les types possibles à 0
        booking_type_dict = {code: 0 for code, _ in Booking.BOOKING_TYPE_CHOICES}
        
        # Mettre à jour avec les vraies valeurs
        for booking_type, count in booking_type_aggregation.items():
            if booking_type in booking_type_dict:
                booking_type_dict[booking_type] = count
        
        return {'booking_type': booking_type_dict}
    
    @staticmethod
    def _get_recurring_types_stats(queryset):
        """Stats de types de récurrence avec consolidation des doublons"""
        recurring_qs = queryset.filter(recurring_occurrence__isnull=False)
        
        recurring_aggregation = {}
        recurring_counts = recurring_qs.values(
            'recurring_occurrence__template__recurrence_type'
        ).annotate(count=Count('id'))
        
        # Consolider les counts par type de récurrence
        for item in recurring_counts:
            rec_type = item['recurring_occurrence__template__recurrence_type']
            if rec_type in recurring_aggregation:
                recurring_aggregation[rec_type] += item['count']
            else:
                recurring_aggregation[rec_type] = item['count']
        
        # Initialiser tous les types possibles à 0
        recurring_types = {code: 0 for code, _ in RecurringBookingTemplate.RECURRENCE_TYPE_CHOICES}
        
        # Mettre à jour avec les vraies valeurs
        for rec_type, count in recurring_aggregation.items():
            if rec_type in recurring_types:
                recurring_types[rec_type] = count
        
        return {'recurring_types': recurring_types}
    
    @staticmethod
    def _get_template_status_stats(queryset):
        recurring_qs = queryset.filter(recurring_occurrence__isnull=False)
        return {
            'template_status': {
                'active': recurring_qs.filter(recurring_occurrence__template__is_active=True).count(),
                'inactive': recurring_qs.filter(recurring_occurrence__template__is_active=False).count()
            }
        }
    
    @staticmethod
    def _aggregate_field_stats(queryset, field_name, choices):
        """Agrège les statistiques pour un champ donné - retourne tous les choix même avec count=0"""
        # Initialiser tous les choix à 0
        field_dict = {code: 0 for code, _ in choices}
        
        # Agrégation avec consolidation des doublons
        field_aggregation = {}
        field_counts = queryset.values(field_name).annotate(count=Count('id'))
        
        # Consolider les counts
        for item in field_counts:
            field_value = item[field_name]
            if field_value in field_aggregation:
                field_aggregation[field_value] += item['count']
            else:
                field_aggregation[field_value] = item['count']
        
        # Mettre à jour le dictionnaire avec les vraies valeurs
        for field_value, count in field_aggregation.items():
            if field_value in field_dict:
                field_dict[field_value] = count
        
        return field_dict
    
    @staticmethod
    def _calculate_main_stats_for_queryset(queryset):
        bookings_with_dates = queryset.select_related('estimate__estimation_log').annotate(
            pickup_date_only=Case(
                When(booking_type='one_way', then='estimate__estimation_log__pickup_date'),
                default=None
            )
        ).filter(pickup_date_only__isnull=False)
        
        today_date = timezone.now().date()
        temporal_counts = {'today': 0, 'past': 0, 'future': 0}
        
        for booking in bookings_with_dates:
            pickup_date = booking.pickup_date_only.date() if booking.pickup_date_only else None
            if pickup_date:
                if pickup_date == today_date:
                    temporal_counts['today'] += 1
                elif pickup_date < today_date:
                    temporal_counts['past'] += 1
                else:
                    temporal_counts['future'] += 1
        
        stats_qs = queryset.aggregate(
            total=Count('id'),
            cancelled=Count('id', filter=Q(cancellation_status='cancelled')),
            recurring=Count('id', filter=Q(recurring_occurrence__isnull=False))
        )
        
        return {
            'total_bookings': stats_qs['total'],
            'today_bookings': temporal_counts['today'],
            'past_bookings': temporal_counts['past'],
            'future_bookings': temporal_counts['future'],
            'cancelled_bookings': stats_qs['cancelled'],
            'recurring_bookings': stats_qs['recurring'],
            'archived_bookings': queryset.filter(is_archived=True).count()
        }
    
    @staticmethod
    def get_main_stats():
        base_qs = BookingStatsService.get_base_queryset()
        return BookingStatsService._calculate_main_stats_for_queryset(base_qs)
    
    @staticmethod
    def get_status_workflow_stats(scope=None, search_key=None):
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        if scope == 'recurring':
            return BookingStatsService._get_recurring_workflow_stats(search_key)
        
        workflow_data = [
            {'status': 'total', 'status_display': 'Total', 'count': queryset.count(), 'search_key': 'total'}
        ]
        
        status_counts = queryset.values('status').annotate(count=Count('status'))
        for item in status_counts:
            status_code = item['status']
            status_display = dict(Booking.STATUS_CHOICES).get(status_code, status_code)
            workflow_data.append({
                'status': status_code,
                'status_display': status_display,
                'count': item['count'],
                'search_key': f'status_{status_code}'
            })
        
        booking_type_counts = queryset.values('booking_type').annotate(count=Count('booking_type'))
        booking_type_map = {'one_way': 'Aller Simple', 'round_trip': 'Aller-Retour'}
        
        for item in booking_type_counts:
            booking_type = item['booking_type']
            workflow_data.append({
                'status': booking_type,
                'status_display': booking_type_map.get(booking_type, booking_type),
                'count': item['count'],
                'search_key': f'booking_type_{booking_type}'
            })
        
        return workflow_data
    
    @staticmethod
    def _get_user_status_workflow(queryset, scope, search_key):
        """Status workflow pour un queryset filtré par utilisateur - corrigé"""
        if scope == 'recurring':
            return BookingStatsService._get_recurring_workflow_stats_for_queryset(queryset, search_key)
        
        workflow_data = [
            {'status': 'total', 'status_display': 'Total', 'count': queryset.count(), 'search_key': 'total'}
        ]
        
        # ✅ CORRECTION : Agrégation correcte des statuts (consolider les doublons)
        status_aggregation = {}
        status_counts = queryset.values('status').annotate(count=Count('status'))
        
        # Consolider les counts par statut
        for item in status_counts:
            status_code = item['status']
            if status_code in status_aggregation:
                status_aggregation[status_code] += item['count']
            else:
                status_aggregation[status_code] = item['count']
        
        # Ajouter tous les statuts possibles (même ceux à 0)
        all_status_choices = dict(Booking.STATUS_CHOICES)
        for status_code, status_display in all_status_choices.items():
            count = status_aggregation.get(status_code, 0)
            workflow_data.append({
                'status': status_code,
                'status_display': status_display,
                'count': count,
                'search_key': f'status_{status_code}'
            })
        
        # ✅ CORRECTION : Agrégation correcte des types de booking (consolider les doublons)
        booking_type_aggregation = {}
        booking_type_counts = queryset.values('booking_type').annotate(count=Count('booking_type'))
        
        # Consolider les counts par type
        for item in booking_type_counts:
            booking_type = item['booking_type']
            if booking_type in booking_type_aggregation:
                booking_type_aggregation[booking_type] += item['count']
            else:
                booking_type_aggregation[booking_type] = item['count']
        
        # Ajouter tous les types possibles (même ceux à 0)
        booking_type_map = {'one_way': 'Aller Simple', 'round_trip': 'Aller-Retour'}
        for booking_type, type_display in booking_type_map.items():
            count = booking_type_aggregation.get(booking_type, 0)
            workflow_data.append({
                'status': booking_type,
                'status_display': type_display,
                'count': count,
                'search_key': f'booking_type_{booking_type}'
            })
        
        return workflow_data
    
    @staticmethod
    def _get_recurring_workflow_stats(search_key=None):
        base_recurring_qs = BookingStatsService.get_base_queryset().filter(
            recurring_occurrence__isnull=False
        ).select_related('recurring_occurrence__template')
        
        if not search_key or search_key == 'total':
            recurrence_counts = base_recurring_qs.values(
                'recurring_occurrence__template__recurrence_type'
            ).annotate(count=Count('id'))
            
            workflow_data = []
            type_map = dict(RecurringBookingTemplate.RECURRENCE_TYPE_CHOICES)
            
            for item in recurrence_counts:
                rec_type = item['recurring_occurrence__template__recurrence_type']
                workflow_data.append({
                    'status': rec_type,
                    'status_display': type_map.get(rec_type, rec_type),
                    'count': item['count'],
                    'search_key': f'recurring_type_{rec_type}'
                })
            
            return workflow_data
        
        elif search_key == 'recurring_type_monthly':
            monthly_qs = base_recurring_qs.filter(
                recurring_occurrence__template__recurrence_type='monthly'
            ).select_related('recurring_occurrence__template__monthly_configuration')
            
            monthly_counts = monthly_qs.values(
                'recurring_occurrence__template__monthly_configuration__monthly_type'
            ).annotate(count=Count('id'))
            
            from courses.models import MonthlyRecurrenceConfig
            type_map = dict(MonthlyRecurrenceConfig.MONTHLY_TYPE_CHOICES)
            
            workflow_data = []
            for item in monthly_counts:
                monthly_type = item['recurring_occurrence__template__monthly_configuration__monthly_type']
                workflow_data.append({
                    'status': f'monthly_{monthly_type}',
                    'status_display': type_map.get(monthly_type, monthly_type),
                    'count': item['count'],
                    'search_key': f'recurring_monthly_{monthly_type}'
                })
            
            return workflow_data
        
        elif search_key == 'recurring_type_custom':
            custom_qs = base_recurring_qs.filter(
                recurring_occurrence__template__recurrence_type='custom'
            ).select_related('recurring_occurrence__template__custom_configuration')
            
            custom_counts = custom_qs.values(
                'recurring_occurrence__template__custom_configuration__pattern_type'
            ).annotate(count=Count('id'))
            
            from courses.models import CustomRecurrenceConfig
            pattern_map = dict(CustomRecurrenceConfig.PATTERN_CHOICES)
            
            workflow_data = []
            for item in custom_counts:
                pattern_type = item['recurring_occurrence__template__custom_configuration__pattern_type']
                workflow_data.append({
                    'status': f'custom_{pattern_type}',
                    'status_display': pattern_map.get(pattern_type, pattern_type),
                    'count': item['count'],
                    'search_key': f'recurring_custom_{pattern_type}'
                })
            
            return workflow_data
        
        return []
    
    @staticmethod
    def _get_recurring_workflow_stats_for_queryset(queryset, search_key):
        recurring_qs = queryset.filter(recurring_occurrence__isnull=False)
        
        if not search_key or search_key == 'total':
            recurrence_counts = recurring_qs.values(
                'recurring_occurrence__template__recurrence_type'
            ).annotate(count=Count('id'))
            
            workflow_data = []
            type_map = dict(RecurringBookingTemplate.RECURRENCE_TYPE_CHOICES)
            
            for item in recurrence_counts:
                rec_type = item['recurring_occurrence__template__recurrence_type']
                workflow_data.append({
                    'status': rec_type,
                    'status_display': type_map.get(rec_type, rec_type),
                    'count': item['count'],
                    'search_key': f'recurring_type_{rec_type}'
                })
            
            return workflow_data
        
        return []
    
    @staticmethod
    def _add_specialized_workflows(response_data, scope, search_key):
        if scope == 'recurring' or (search_key and search_key.startswith('recurring_')):
            if not search_key or search_key == 'total':
                response_data['recurring_workflow'] = BookingStatsService._get_recurring_workflow_stats()
            elif search_key == 'recurring_type_monthly':
                response_data['recurring_monthly_workflow'] = BookingStatsService._get_recurring_workflow_stats('recurring_type_monthly')
            elif search_key == 'recurring_type_custom':
                response_data['recurring_custom_workflow'] = BookingStatsService._get_recurring_workflow_stats('recurring_type_custom')
    
    @staticmethod
    def _apply_scope_filter(scope):
        base_qs = BookingStatsService.get_base_queryset()
        
        if scope in ['today', 'past', 'future']:
            today_date = timezone.now().date()
            
            if scope == 'today':
                date_filter = Q(estimate__estimation_log__pickup_date__date=today_date)
            elif scope == 'past':
                date_filter = Q(estimate__estimation_log__pickup_date__date__lt=today_date)
            else:
                date_filter = Q(estimate__estimation_log__pickup_date__date__gt=today_date)
            
            return base_qs.filter(date_filter).select_related('estimate__estimation_log').order_by(
                '-estimate__estimation_log__pickup_date' if scope == 'past' 
                else 'estimate__estimation_log__pickup_date'
            )
        
        elif scope == 'cancelled':
            return base_qs.filter(cancellation_status='cancelled').order_by('-created_at')
        
        elif scope == 'archived':
            return Booking.objects.filter(is_archived=True).order_by('-created_at')
        
        elif scope == 'recurring':
            return base_qs.filter(
                recurring_occurrence__isnull=False
            ).select_related(
                'recurring_occurrence__template'
            ).order_by('-created_at')
        
        return base_qs.select_related('estimate__estimation_log').order_by(
            'estimate__estimation_log__pickup_date'
        )
    
    @staticmethod
    def filter_bookings(scope=None, search_key=None, **filters):
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        if search_key and search_key != 'total':
            queryset = BookingStatsService._apply_search_key_filter(queryset, search_key)
        
        for field in ['billing_status', 'cancellation_status', 'payment_timing']:
            if field in filters:
                queryset = queryset.filter(**{field: filters[field]})
        
        return queryset.select_related(
            'estimate__estimation_log', 'client', 'assigned_driver', 'assigned_partner',
            'recurring_occurrence__template', 'recurring_occurrence__template__monthly_configuration',
            'recurring_occurrence__template__custom_configuration'
        ).prefetch_related(
            'estimate__passengers', 'estimate__estimate_attribute__attribute',
            'segments__estimate__estimation_log', 'segments__estimate__passengers', 
            'segments__estimate__estimate_attribute__attribute'
        )
    
    @staticmethod
    def _apply_search_key_filter(queryset, search_key):
        filter_map = {
            'status_': ('status', lambda sk: sk.replace('status_', '')),
            'booking_type_': ('booking_type', lambda sk: sk.replace('booking_type_', '')),
            'recurring_type_': (
                'recurring_occurrence__template__recurrence_type',
                lambda sk: sk.replace('recurring_type_', '')
            ),
            'recurring_monthly_': (
                {
                    'recurring_occurrence__template__recurrence_type': 'monthly',
                    'recurring_occurrence__template__monthly_configuration__monthly_type': True
                },
                lambda sk: sk.replace('recurring_monthly_', '')
            ),
            'recurring_custom_': (
                {
                    'recurring_occurrence__template__recurrence_type': 'custom',
                    'recurring_occurrence__template__custom_configuration__pattern_type': True
                },
                lambda sk: sk.replace('recurring_custom_', '')
            )
        }
        
        for prefix, (field_config, value_extractor) in filter_map.items():
            if search_key.startswith(prefix):
                value = value_extractor(search_key)
                
                if isinstance(field_config, dict):
                    filters = field_config.copy()
                    for k, v in filters.items():
                        if v is True:
                            filters[k] = value
                    queryset = queryset.filter(**filters)
                else:
                    queryset = queryset.filter(**{field_config: value})
                break
        
        return queryset