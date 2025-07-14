from django.utils import timezone
from django.db.models import Q, Count, Case, When, BooleanField
from courses.models import Booking, RecurringBookingTemplate
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

class BookingStatsService:
    
    @staticmethod
    def get_base_queryset():
        return Booking.objects.filter(is_archived=False)
    
    @staticmethod
    def get_booking_by_id(booking_id):
        """Récupère un booking avec toutes ses relations optimisées"""
        return get_object_or_404(
            Booking.objects.select_related(
                'estimate__estimation_log',
                'client', 
                'assigned_driver', 
                'assigned_partner'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute__attribute',
                'segments__estimate__estimation_log',
                'segments__estimate__passengers',
                'segments__estimate__estimate_attribute__attribute',
                'recurring_occurrence__template__monthly_configuration',
                'recurring_occurrence__template__custom_configuration'
            ),
            id=booking_id
        )
    
    @staticmethod
    def get_global_stats_data(scope=None, search_key=None):
        """Méthode centralisée pour récupérer toutes les données des statistiques globales"""
        # ✅ CORRECTION : Appliquer le scope sur main_stats
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
        """✅ NOUVEAU : Stats globales filtrées par utilisateur"""
        from .user_permissions import BookingUserPermissionService
        
        # ✅ CORRECTION : Appliquer le scope d'abord, puis le filtre utilisateur
        if scope and scope != 'total':
            scope_filtered_queryset = BookingStatsService._apply_scope_filter(scope)
            user_filtered_queryset = BookingUserPermissionService.apply_user_booking_filter(scope_filtered_queryset, user)
            main_stats = BookingStatsService._calculate_main_stats_for_queryset(user_filtered_queryset)
        else:
            base_queryset = BookingStatsService.get_base_queryset()
            user_filtered_queryset = BookingUserPermissionService.apply_user_booking_filter(base_queryset, user)
            main_stats = BookingStatsService._calculate_main_stats_for_queryset(user_filtered_queryset)
        
        # Recalculer status_workflow avec le queryset filtré utilisateur
        status_workflow = BookingStatsService._get_user_status_workflow(user_filtered_queryset, scope, search_key)
        
        response_data = {
            'main_stats': main_stats,
            'status_workflow': status_workflow
        }
        
        # Ajouter les workflows spécialisés si nécessaire
        BookingStatsService._add_specialized_workflows(response_data, scope, search_key)
        
        return response_data
    
    @staticmethod
    def _get_user_status_workflow(queryset, scope, search_key):
        """✅ NOUVEAU : Status workflow pour un queryset filtré par utilisateur"""
        if scope == 'recurring':
            return BookingStatsService._get_recurring_workflow_stats_for_queryset(queryset, search_key)
        
        workflow_data = [
            {'status': 'total', 'status_display': 'Total', 'count': queryset.count(), 'search_key': 'total'}
        ]
        
        # Agrégation des statuts
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
        
        # Agrégation des types de booking
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
    def _get_recurring_workflow_stats_for_queryset(queryset, search_key):
        """✅ NOUVEAU : Workflow récurrence pour queryset spécifique"""
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
    def get_user_filtered_bookings(user, params):
        """✅ NOUVEAU : Méthode pour bookings filtrés par utilisateur"""
        from .user_permissions import BookingUserPermissionService
        
        # Récupérer les bookings selon les paramètres
        queryset = BookingStatsService.get_filtered_bookings(params)
        
        # Appliquer le filtre utilisateur
        user_filtered_queryset = BookingUserPermissionService.apply_user_booking_filter(queryset, user)
        
        return user_filtered_queryset
    
    @staticmethod
    def _calculate_main_stats_for_queryset(queryset):
        """✅ NOUVEAU : Recalcule les stats principales avec le queryset filtré"""
        from django.utils import timezone
        from django.db.models import Q, Count, Case, When
        
        # Calculs temporels sur le queryset filtré
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
        
        # Agrégations sur le queryset filtré
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
    def _add_specialized_workflows(response_data, scope, search_key):
        """Ajoute les workflows spécialisés selon le contexte"""
        if scope == 'recurring' or (search_key and search_key.startswith('recurring_')):
            if not search_key or search_key == 'total':
                response_data['recurring_workflow'] = BookingStatsService._get_recurring_workflow_stats()
            elif search_key == 'recurring_type_monthly':
                response_data['recurring_monthly_workflow'] = BookingStatsService._get_recurring_workflow_stats('recurring_type_monthly')
            elif search_key == 'recurring_type_custom':
                response_data['recurring_custom_workflow'] = BookingStatsService._get_recurring_workflow_stats('recurring_type_custom')
    
    @staticmethod
    def get_filtered_bookings(params):
        """Méthode centralisée pour construire le queryset filtré"""
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
    def get_extended_sub_stats(queryset, params):
        """Méthode centralisée pour les sous-statistiques étendues"""
        base_stats = BookingStatsService.get_sub_stats(queryset)
        scope = params.get('scope')
        search_key = params.get('search_key', '')
        
        if scope == 'recurring' or search_key.startswith('recurring_'):
            BookingStatsService._add_recurring_sub_stats(base_stats, queryset, search_key)
        
        return base_stats
    
    @staticmethod
    def _add_recurring_sub_stats(base_stats, queryset, search_key):
        """Ajoute les sous-statistiques spécifiques aux récurrences"""
        recurring_qs = queryset.filter(recurring_occurrence__isnull=False)
        
        recurring_types = {}
        for rec_type, display in RecurringBookingTemplate.RECURRENCE_TYPE_CHOICES:
            count = recurring_qs.filter(
                recurring_occurrence__template__recurrence_type=rec_type
            ).count()
            recurring_types[rec_type] = count
        
        base_stats['recurring_types'] = recurring_types
        
        if search_key.startswith('recurring_type_monthly') or search_key.startswith('recurring_monthly_'):
            base_stats['recurring_monthly_details'] = BookingStatsService._get_monthly_details(recurring_qs)
        
        if search_key.startswith('recurring_type_custom') or search_key.startswith('recurring_custom_'):
            base_stats['recurring_custom_details'] = BookingStatsService._get_custom_details(recurring_qs)
        
        active_count = recurring_qs.filter(recurring_occurrence__template__is_active=True).count()
        inactive_count = recurring_qs.filter(recurring_occurrence__template__is_active=False).count()
        
        base_stats['template_status'] = {
            'active': active_count,
            'inactive': inactive_count
        }
    
    @staticmethod
    def _get_monthly_details(recurring_qs):
        """Détails pour récurrences mensuelles"""
        from courses.models import MonthlyRecurrenceConfig
        
        monthly_details = {}
        for monthly_type, display in MonthlyRecurrenceConfig.MONTHLY_TYPE_CHOICES:
            count = recurring_qs.filter(
                recurring_occurrence__template__recurrence_type='monthly',
                recurring_occurrence__template__monthly_configuration__monthly_type=monthly_type
            ).count()
            monthly_details[monthly_type] = count
        
        return monthly_details
    
    @staticmethod
    def _get_custom_details(recurring_qs):
        """Détails pour récurrences personnalisées"""
        from courses.models import CustomRecurrenceConfig
        
        custom_details = {}
        for pattern_type, display in CustomRecurrenceConfig.PATTERN_CHOICES:
            count = recurring_qs.filter(
                recurring_occurrence__template__recurrence_type='custom',
                recurring_occurrence__template__custom_configuration__pattern_type=pattern_type
            ).count()
            custom_details[pattern_type] = count
        
        return custom_details
    
    @staticmethod
    def get_main_stats():
        """Statistiques principales optimisées avec récurrences"""
        base_qs = BookingStatsService.get_base_queryset()
        
        bookings_with_dates = base_qs.select_related('estimate__estimation_log').annotate(
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
        
        stats_qs = base_qs.aggregate(
            total=Count('id'),
            cancelled=Count('id', filter=Q(cancellation_status=Booking.CANCELLED)),
            recurring=Count('id', filter=Q(recurring_occurrence__isnull=False))
        )
        
        return {
            'total_bookings': stats_qs['total'],
            'today_bookings': temporal_counts['today'],
            'past_bookings': temporal_counts['past'],
            'future_bookings': temporal_counts['future'],
            'cancelled_bookings': stats_qs['cancelled'],
            'recurring_bookings': stats_qs['recurring'],
            'archived_bookings': Booking.objects.filter(is_archived=True).count()
        }
    
    @staticmethod
    def get_status_workflow_stats(scope=None, search_key=None):
        """Workflow étendu optimisé corrigé"""
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        if scope == 'recurring':
            return BookingStatsService._get_recurring_workflow_stats(search_key)
        
        workflow_data = [
            {'status': 'total', 'status_display': 'Total', 'count': queryset.count(), 'search_key': 'total'}
        ]
        
        # ✅ CORRECTION : Agrégation correcte des statuts (sans doublons)
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
        
        # ✅ CORRECTION : Agrégation correcte des types de booking (sans doublons)
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
    def _get_recurring_workflow_stats(search_key=None):
        """Workflow spécialisé pour les récurrences optimisé"""
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
    def get_sub_stats(queryset):
        """Sous-statistiques universelles optimisées"""
        aggregated_stats = queryset.aggregate(
            total=Count('id'),
            **{
                f'billing_{code}': Count('id', filter=Q(billing_status=code))
                for code, _ in Booking.BILLING_STATUS_CHOICES
            },
            **{
                f'cancellation_{code}': Count('id', filter=Q(cancellation_status=code))
                for code, _ in Booking.CANCELLATION_STATUS_CHOICES
            },
            **{
                f'payment_{code}': Count('id', filter=Q(payment_timing=code))
                for code, _ in Booking.PAYMENT_TIMING_CHOICES
            }
        )
        
        return {
            'total': aggregated_stats['total'],
            'billing_status': {
                code: aggregated_stats[f'billing_{code}']
                for code, _ in Booking.BILLING_STATUS_CHOICES
            },
            'cancellation_status': {
                code: aggregated_stats[f'cancellation_{code}']
                for code, _ in Booking.CANCELLATION_STATUS_CHOICES
            },
            'payment_timing': {
                code: aggregated_stats[f'payment_{code}']
                for code, _ in Booking.PAYMENT_TIMING_CHOICES
            }
        }
    
    @staticmethod
    def _apply_scope_filter(scope):
        """✅ CORRECTION : Filtrage par scope corrigé"""
        base_qs = BookingStatsService.get_base_queryset()
        
        if scope in ['today', 'past', 'future']:
            today_date = timezone.now().date()
            
            if scope == 'today':
                date_filter = Q(estimate__estimation_log__pickup_date__date=today_date)
            elif scope == 'past':
                date_filter = Q(estimate__estimation_log__pickup_date__date__lt=today_date)
            else:  # future
                date_filter = Q(estimate__estimation_log__pickup_date__date__gt=today_date)
            
            return base_qs.filter(date_filter).select_related('estimate__estimation_log').order_by(
                '-estimate__estimation_log__pickup_date' if scope == 'past' 
                else 'estimate__estimation_log__pickup_date'
            )
        
        elif scope == 'cancelled':
            # ✅ CORRECTION : Filtre de cancellation corrigé
            return base_qs.filter(cancellation_status='cancelled').order_by('-created_at')
        
        elif scope == 'archived':
            return Booking.objects.filter(is_archived=True).order_by('-created_at')
        
        elif scope == 'recurring':
            # ✅ CORRECTION : Filtrer seulement les récurrents
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
        """Filtrage complet optimisé avec gestion des récurrences"""
        queryset = BookingStatsService._apply_scope_filter(scope)
        
        if search_key and search_key != 'total':
            queryset = BookingStatsService._apply_search_key_filter(queryset, search_key)
        
        for field in ['billing_status', 'cancellation_status', 'payment_timing']:
            if field in filters:
                queryset = queryset.filter(**{field: filters[field]})
        
        return queryset.select_related(
            'estimate__estimation_log',
            'client', 
            'assigned_driver', 
            'assigned_partner',
            'recurring_occurrence__template',
            'recurring_occurrence__template__monthly_configuration',
            'recurring_occurrence__template__custom_configuration'
        ).prefetch_related(
            'estimate__passengers',
            'estimate__estimate_attribute__attribute',
            'segments__estimate__estimation_log',
            'segments__estimate__passengers', 
            'segments__estimate__estimate_attribute__attribute'
        )
    
    @staticmethod
    def _apply_search_key_filter(queryset, search_key):
        """Application optimisée des filtres search_key"""
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