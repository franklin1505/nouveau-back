# courses/Reservations/Reservations_details/recurring_services.py

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from courses.Reservations.Reservations_details.recurring.generators import DateCalculator
from courses.Reservations.Reservations_details.recurring.helpers import BookingExtractor, ConfigBuilder, ConfigModelHelper, DateHelper, DescriptionBuilder, EstimateHelper, LogHelper, ValidationHelper
from courses.models import Booking, RecurringBookingTemplate, RecurringBookingOccurrence
from courses.Reservations.Reservations_details.helpers import (
    extract_booking_template_data, duplicate_booking_unified, 
    calculate_trip_metrics, format_booking_data, 
    format_round_trip_booking_data, format_duplication_booking_data
)


class RecurringConfigService:
    """Service pour génération de configurations intelligentes"""
    
    @staticmethod
    def get_intelligent_configs(booking):
        """Génère configurations basées sur pickup_date du booking"""
        
        # Extraire pickup_date et calculer dates intelligentes
        pickup_date = BookingExtractor.get_pickup_date(booking)
        base_date = pickup_date.date()
        
        # Limites par type
        limits = ValidationHelper.get_max_limits()
        
        # Générer configs pour tous types
        configs = {}
        for recurrence_type in ['daily', 'weekly', 'monthly', 'yearly', 'custom']:
            dates_info = DateHelper.calculate_intelligent_dates(base_date, recurrence_type)
            config = RecurringConfigService._build_type_config(
                booking, recurrence_type, dates_info, limits[recurrence_type]
            )
            configs[recurrence_type] = config
        
        return configs
    
    @staticmethod
    def _build_type_config(booking, recurrence_type, dates_info, limits):
        """Construit config pour un type spécifique"""
        
        # Config de base selon type
        config_builders = {
            'daily': ConfigBuilder.build_daily_config,
            'weekly': ConfigBuilder.build_weekly_config,
            'monthly': ConfigBuilder.build_monthly_config,
            'yearly': ConfigBuilder.build_yearly_config,
            'custom': ConfigBuilder.build_custom_config
        }
        
        default_config = config_builders[recurrence_type](booking, dates_info)
        
        # Description dynamique
        start_str, end_str = DateHelper.format_date_range(dates_info['start'], dates_info['end'])
        description = DescriptionBuilder.build_description(
            recurrence_type, start_str, end_str, dates_info['max_occurrences'], default_config
        )
        
        # Détails config selon type
        config_details = RecurringConfigService._get_config_details(recurrence_type, dates_info)
        
        return {
            "name": f"Récurrence {recurrence_type.title()}",
            "description": description,
            "default_config": default_config,
            "configuration_details": config_details,
            "limits": limits,
            "is_modifiable": True
        }
    
    @staticmethod
    def _get_config_details(recurrence_type, dates_info):
        """Détails config selon type"""
        details_map = {
            'daily': {
                "include_weekends": "false = jours ouvrables seulement (lundi-vendredi)",
                "weekdays": "[] = tous les jours ouvrables, ou spécifier [1,2,3,4,5] pour personnaliser",
                "period_calculation": "Début = pickup_date du booking, fin = +30 jours calendaires"
            },
            'weekly': {
                "frequency_interval": "1 = chaque semaine, 2 = toutes les 2 semaines, etc.",
                "period_calculation": "Début = pickup_date +7 jours, fin = +3 mois",
                "pattern": "Même jour de la semaine que le booking source"
            },
            'monthly': {
                "monthly_type": "same_date = même date du mois, same_position = même position (ex: 2ème lundi)",
                "frequency_interval": "1 = chaque mois, 2 = tous les 2 mois, etc.",
                "period_calculation": "Début = pickup_date +1 mois, fin = +6 mois"
            },
            'yearly': {
                "frequency_interval": "1 = chaque année, 2 = toutes les 2 années, etc.",
                "period_calculation": "Début = pickup_date +1 an, fin = +3 ans",
                "leap_year_handling": "Gestion automatique des années bissextiles"
            },
            'custom': {
                "pattern_type": "days_of_week = jours spécifiques, interval_based = tous les X jours, specific_dates = dates manuelles",
                "enable_multiple_times": "true = plusieurs créneaux par jour (ex: 8h + 18h)",
                "enable_multiple_periods": "true = périodes multiples (ex: rentrées scolaires)",
                "exclude_dates": "Dates à exclure (vacances, jours fériés) format ISO"
            }
        }
        
        base_details = details_map.get(recurrence_type, {})
        base_details[f"max_occurrences"] = f"{dates_info['max_occurrences']} occurrences maximum sur la période"
        
        return base_details


class RecurringPreviewService:
    """Service pour génération et gestion des previews"""
    
    @staticmethod
    def validate_booking_for_recurring(booking_id):
        """Validation booking pour récurrence"""
        return ValidationHelper.validate_booking_for_recurring(booking_id)
    
    @staticmethod
    @transaction.atomic
    def create_template_and_preview(booking_id, config, user):
        """Crée template + occurrences et retourne preview avec booking complet"""
        
        # ✅ VALIDATION ET CHARGEMENT COMPLET du booking
        base_booking, error = RecurringPreviewService.validate_booking_for_recurring(booking_id)
        if error:
            raise ValidationError(error)
        
        # ✅ RECHARGEMENT COMPLET avec toutes les relations pour le formatage
        base_booking = RecurringPreviewService._reload_booking_with_full_relations(booking_id)
        
        # Création template
        template = RecurringBookingTemplate.objects.create(
            base_booking=base_booking,
            name=config.get('name', f"Récurrence {base_booking.booking_number}"),
            recurrence_type=config['recurrence_type'],
            start_date=config['start_date'],
            end_date=config.get('end_date'),
            max_occurrences=config['max_occurrences'],
            is_active=True
        )
        
        # Configuration spécifique selon type
        config_instance = ConfigModelHelper.create_config_by_type(template, config)
        
        # Génération occurrences
        occurrences_data = DateCalculator.generate_occurrences(template, config_instance)
        
        # Sauvegarde occurrences
        occurrence_objects = []
        for occ_data in occurrences_data:
            occurrence = RecurringBookingOccurrence.objects.create(**occ_data)
            occurrence_objects.append(occurrence)
        
        # ✅ LOG UNIFIÉ
        LogHelper.create_template_log(template, user, len(occurrence_objects))
        
        return template, occurrence_objects
    
    @staticmethod
    def _reload_booking_with_full_relations(booking_id):
        """✅ NOUVEAU : Recharge le booking avec TOUTES les relations nécessaires pour format_booking_data"""
        from courses.models import Booking
        
        return Booking.objects.select_related(
            'estimate__estimation_log__user',
            'estimate__user_choice', 
            'estimate__payment_method',
            'estimate__meeting_place',
            'client',
            'assigned_driver',
            'assigned_partner'
        ).prefetch_related(
            'estimate__passengers',
            'estimate__estimate_attribute__attribute',
            'estimate__estimation_log__tariffs',  # ✅ IMPORTANT pour format_booking_data
            'segments__estimate__estimation_log',
            'segments__estimate__passengers',
            'segments__estimate__estimate_attribute__attribute'
        ).get(id=booking_id)
    
    @staticmethod
    def format_occurrences_preview(occurrences_page, base_booking):
        """✅ UTILISATION de format_duplication_booking_data qui gère correctement les tariffs"""
        preview_data = []
        
        print(f"🔍 DEBUG Booking {base_booking.id} avec relations:")
        print(f"  - Type: {base_booking.booking_type}")
        print(f"  - Estimate: {base_booking.estimate}")
        print(f"  - Client: {base_booking.client}")
        if base_booking.booking_type == 'one_way' and base_booking.estimate:
            print(f"  - Estimation Log: {base_booking.estimate.estimation_log}")
            print(f"  - User: {base_booking.estimate.estimation_log.user if base_booking.estimate.estimation_log else None}")
            print(f"  - Passengers count: {base_booking.estimate.passengers.count()}")
            print(f"  - User choice: {base_booking.estimate.user_choice}")
            print(f"  - Vehicle ID: {base_booking.estimate.user_choice.vehicle_id if base_booking.estimate.user_choice else None}")
        
        for occurrence in occurrences_page:
            try:
                # ✅ UTILISATION de format_duplication_booking_data au lieu de format_booking_data
                if base_booking.booking_type == 'round_trip':
                    base_format_result = format_round_trip_booking_data(base_booking, include_request_data=False)
                else:
                    # ✅ CORRECTION : Utiliser format_duplication_booking_data
                    base_format_result = format_duplication_booking_data(base_booking, include_request_data=False)
                
                print(f"🔍 Format result keys: {base_format_result.keys()}")
                display_data = base_format_result.get("display_data", {})
                print(f"🔍 Display data keys: {list(display_data.keys())}")
                print(f"🔍 Display data length: {len(display_data)}")
                
                if not display_data:
                    print("❌ Display data toujours vide - problème dans format_duplication_booking_data")
                    continue
                
                # ✅ COPIE ET ADAPTATION des données
                occurrence_booking = display_data.copy()
                
                # ✅ MISE À JOUR DE LA DATE dans estimation_log
                if base_booking.booking_type == 'one_way':
                    if "estimation_log" in occurrence_booking:
                        occurrence_booking["estimation_log"]["pickup_date"] = occurrence.scheduled_datetime.isoformat()
                else:
                    # Pour round_trip, mettre à jour les segments
                    if "segments" in occurrence_booking:
                        for segment in occurrence_booking["segments"]:
                            if segment.get("type") == "outbound":
                                segment["pickup_date"] = occurrence.scheduled_datetime.isoformat()
                            elif segment.get("type") == "return":
                                # Calculer date retour basée sur l'original
                                original_gap = (base_booking.return_segment.pickup_date - base_booking.outbound_segment.pickup_date)
                                return_datetime = occurrence.scheduled_datetime + original_gap
                                segment["pickup_date"] = return_datetime.isoformat()
                
                # ✅ MÉTADONNÉES DE PREVIEW
                occurrence_booking["preview_info"] = {
                    "is_preview": True,
                    "occurrence_id": occurrence.id,
                    "occurrence_number": occurrence.occurrence_number,
                    "scheduled_date": occurrence.scheduled_datetime.date().isoformat(),
                    "scheduled_time": occurrence.scheduled_datetime.time().strftime("%H:%M"),
                    "template_id": occurrence.template.id,
                    "based_on_booking": base_booking.booking_number
                }
                
                print(f"✅ Occurrence booking final keys: {list(occurrence_booking.keys())}")
                preview_data.append(occurrence_booking)
                
            except Exception as e:
                import traceback
                print(f"❌ Erreur formatage occurrence {occurrence.id}: {e}")
                print(f"❌ Traceback: {traceback.format_exc()}")
                continue
        
        print(f"✅ Preview data final: {len(preview_data)} éléments")
        return preview_data


class RecurringCreationService:
    """Service pour création finale des bookings"""
    
    @staticmethod
    @transaction.atomic
    def create_final_bookings(template_id, valid_occurrences, modified_occurrences, user):
        """Création optimisée avec structure valid/modified/deleted"""
        
        try:
            template = RecurringBookingTemplate.objects.get(id=template_id)
            base_booking = template.base_booking
            base_template_data = extract_booking_template_data(base_booking)
            
            created_bookings = []
            creation_errors = []
            
            # Toutes les occurrences à traiter
            all_occurrence_ids = valid_occurrences + [mod['occurrence_id'] for mod in modified_occurrences]
            
            # Traitement occurrences valides
            for occurrence_id in valid_occurrences:
                try:
                    occurrence = template.occurrences.get(id=occurrence_id)
                    
                    # Données finales standard
                    final_data = RecurringCreationService._prepare_final_data(
                        base_template_data, base_booking, occurrence.scheduled_datetime
                    )
                    
                    # Création booking avec fonction existante
                    new_booking = duplicate_booking_unified(base_booking.id, final_data, user)
                    
                    # Liaison occurrence
                    occurrence.booking_id = new_booking['new_booking_id']
                    occurrence.save()
                    
                    # ✅ LOG RÉCURRENCE sur le nouveau booking
                    LogHelper.create_recurring_booking_log(new_booking['new_booking_id'], user, template, occurrence)
                    
                    created_bookings.append({
                        'occurrence_id': occurrence.id,
                        'booking_id': new_booking['new_booking_id'],
                        'booking_number': new_booking['new_booking_number'],
                        'type': 'valid_default'
                    })
                    
                except Exception as e:
                    creation_errors.append({'occurrence_id': occurrence_id, 'error': str(e)})
            
            # Traitement occurrences modifiées
            for modification_data in modified_occurrences:
                try:
                    occurrence_id = modification_data['occurrence_id']
                    modifications = modification_data['modifications']
                    
                    occurrence = template.occurrences.get(id=occurrence_id)
                    
                    # Données finales avec modifications
                    final_data = RecurringCreationService._prepare_final_data(
                        base_template_data, base_booking, occurrence.scheduled_datetime
                    )
                    
                    # Appliquer modifications
                    processed_modifications = RecurringCreationService._process_modifications(
                        modifications, base_booking
                    )
                    final_data.update(processed_modifications)
                    
                    # Recalcul métriques si trajet modifié
                    if 'departure' in modifications or 'destination' in modifications:
                        metrics = calculate_trip_metrics(
                            final_data.get('departure'),
                            final_data.get('destination'),
                            final_data.get('waypoints', [])
                        )
                        final_data.update(metrics)
                    
                    # Création booking avec fonction existante
                    new_booking = duplicate_booking_unified(base_booking.id, final_data, user)
                    
                    # Liaison occurrence
                    occurrence.booking_id = new_booking['new_booking_id']
                    occurrence.save()
                    
                    # ✅ LOG RÉCURRENCE avec modifications
                    LogHelper.create_recurring_booking_log(new_booking['new_booking_id'], user, template, occurrence, modifications.keys())
                    
                    created_bookings.append({
                        'occurrence_id': occurrence.id,
                        'booking_id': new_booking['new_booking_id'],
                        'booking_number': new_booking['new_booking_number'],
                        'type': 'modified',
                        'modifications_applied': list(modifications.keys())
                    })
                    
                except Exception as e:
                    creation_errors.append({
                        'occurrence_id': modification_data.get('occurrence_id'),
                        'error': str(e)
                    })
            
            # Nettoyage automatique
            unused_occurrences = template.occurrences.exclude(id__in=all_occurrence_ids)
            deleted_count = unused_occurrences.count()
            unused_occurrences.delete()
            
            # Finalisation template
            template.is_active = False
            template.save()
            
            # ✅ LOG FINAL SUR BOOKING DE BASE
            LogHelper.create_creation_final_log(
                template, base_booking, len(created_bookings), 
                len(creation_errors), deleted_count, user
            )
            
            # ✅ ENVOI DES COMMUNICATIONS CENTRALISÉES - AVEC DÉTAILS COMPLETS
            try:
                from courses.Reservations.communication_service import BookingCommunicationService
                
                # ✅ NOUVEAU : Récupérer les détails complets des bookings créés
                detailed_bookings = RecurringCreationService._get_detailed_created_bookings(
                    created_bookings, base_booking
                )
                
                # ✅ UTILISATION DIRECTE du service unifié avec toutes les données nécessaires
                comm_success, comm_message = BookingCommunicationService.handle_booking_event(
                    booking_id=created_bookings[0]['booking_id'] if created_bookings else base_booking.id,
                    event_type='recurring_creation',
                    user=user,
                    additional_data={
                        'template_id': template_id,
                        'total_bookings': len(created_bookings),
                        'base_booking': base_booking.booking_number,
                        'has_errors': len(creation_errors) > 0,
                        'created_bookings': created_bookings,
                        'base_booking_obj': base_booking,
                        # ✅ AJOUT : Détails complets des bookings
                        'detailed_bookings': detailed_bookings,
                        # Infos détaillées pour l'email
                        'trip_info': RecurringCreationService._get_trip_info_safe(base_booking),
                        'vehicle_info': RecurringCreationService._get_vehicle_info_safe(created_bookings, base_booking),
                        'total_cost': sum(RecurringCreationService._get_booking_cost(b['booking_id']) for b in created_bookings),
                        'created_by': f"{user.first_name} {user.last_name}".strip() if user else "Admin"
                    }
                )
                
                print(f"📧 Communications récurrence: {comm_success} - {comm_message}")
                
            except Exception as comm_error:
                import traceback
                print(f"❌ Erreur communications récurrence: {comm_error}")
                print(f"❌ Traceback: {traceback.format_exc()}")
                comm_success = False
                comm_message = f"Erreur envoi: {str(comm_error)}"
            
            # ✅ RÉSULTAT AVEC INFOS COMMUNICATIONS CORRIGÉES
            result = {
                'template_id': template.id,
                'base_booking_number': base_booking.booking_number,
                'created_bookings': created_bookings,
                'creation_errors': creation_errors,
                'summary': {
                    'total_requested': len(all_occurrence_ids),
                    'valid_created': len([b for b in created_bookings if b['type'] == 'valid_default']),
                    'modified_created': len([b for b in created_bookings if b['type'] == 'modified']),
                    'total_created': len(created_bookings),
                    'total_errors': len(creation_errors),
                    'unused_deleted': deleted_count
                },
                'communication_status': {
                    'emails_sent': comm_success,
                    'notifications_sent': comm_success,
                    'status_message': comm_message
                }
            }
            
            return result
            
        except RecurringBookingTemplate.DoesNotExist:
            raise ValidationError("Template de récurrence non trouvé")
        except Exception as e:
            raise ValidationError(f"Erreur création: {str(e)}")
    
    @staticmethod
    def _prepare_final_data(base_template_data, base_booking, scheduled_datetime):
        """Prépare données finales de base"""
        return {
            **base_template_data,
            'client_id': base_booking.client.id if base_booking.client else None,
            'pickup_date': scheduled_datetime
        }
    
    @staticmethod
    def _process_modifications(modifications, base_booking):
        """Traite modifications selon structure booking/shared/segments"""
        processed = {}
        
        # Modifications niveau booking
        if 'booking_level' in modifications:
            processed.update(modifications['booking_level'])
        
        # Modifications partagées
        if 'shared_segments' in modifications:
            processed.update(modifications['shared_segments'])
        
        # Modifications directes (compatibilité)
        for key, value in modifications.items():
            if key not in ['booking_level', 'shared_segments', 'outbound_segment', 'return_segment']:
                processed[key] = value
        
        # TODO: Gestion segments spécifiques pour aller-retour
        # Pour l'instant, les modifications globales s'appliquent
        
        return processed
    
    @staticmethod
    def _get_detailed_created_bookings(created_bookings, base_booking):
        """Récupère les détails complets des bookings créés, similaire au preview"""
        detailed_bookings = []
        
        try:
            from courses.Reservations.Reservations_details.helpers import format_duplication_booking_data
            
            for booking_data in created_bookings:
                try:
                    # Recharger le booking avec toutes ses relations
                    booking = Booking.objects.select_related(
                        'estimate__estimation_log__user',
                        'estimate__user_choice', 
                        'estimate__payment_method',
                        'estimate__meeting_place',
                        'client',
                        'assigned_driver',
                        'assigned_partner'
                    ).prefetch_related(
                        'estimate__passengers',
                        'estimate__estimate_attribute__attribute'
                    ).get(id=booking_data['booking_id'])
                    
                    # Utiliser le même formatage que le preview
                    format_result = format_duplication_booking_data(booking, include_request_data=False)
                    display_data = format_result.get("display_data", {})
                    
                    if display_data:
                        # Ajouter les métadonnées de récurrence
                        display_data["recurring_info"] = {
                            "is_recurring": True,
                            "occurrence_id": booking_data.get('occurrence_id'),
                            "booking_id": booking_data['booking_id'],
                            "booking_number": booking_data['booking_number'],
                            "type": booking_data['type'],
                            "based_on_booking": base_booking.booking_number,
                            "modifications_applied": booking_data.get('modifications_applied', [])
                        }
                        
                        detailed_bookings.append(display_data)
                        
                except Exception as e:
                    print(f"❌ Erreur formatage booking {booking_data['booking_id']}: {e}")
                    continue
            
            print(f"✅ Détails complets récupérés pour {len(detailed_bookings)} bookings")
            return detailed_bookings
            
        except Exception as e:
            print(f"❌ Erreur récupération détails complets: {e}")
            return []
    
    @staticmethod
    def _get_vehicle_info_safe(created_bookings, base_booking):
        """Récupère infos véhicule de manière sécurisée"""
        try:
            if created_bookings:
                from courses.models import Booking
                first_booking = Booking.objects.select_related(
                    'estimate__user_choice'
                ).get(id=created_bookings[0]['booking_id'])
                
                if first_booking.estimate and first_booking.estimate.user_choice:
                    vehicle_id = first_booking.estimate.user_choice.vehicle_id
                    try:
                        from configurations.models import Vehicle
                        vehicle = Vehicle.objects.get(id=vehicle_id)
                        return f"{vehicle.brand} {vehicle.model}"
                    except:
                        return f"Véhicule ID {vehicle_id}"
            
            # Fallback sur le booking de base
            if base_booking.estimate and base_booking.estimate.user_choice:
                vehicle_id = base_booking.estimate.user_choice.vehicle_id
                try:
                    from configurations.models import Vehicle
                    vehicle = Vehicle.objects.get(id=vehicle_id)
                    return f"{vehicle.brand} {vehicle.model}"
                except:
                    return f"Véhicule ID {vehicle_id}"
            
            return "N/A"
        except Exception as e:
            print(f"❌ Erreur récupération véhicule: {e}")
            return "N/A"
    
    @staticmethod
    def _get_trip_info_safe(base_booking):
        """Récupère infos trajet de manière sécurisée"""
        try:
            if base_booking.estimate and base_booking.estimate.estimation_log:
                return {
                    'departure': base_booking.estimate.estimation_log.departure,
                    'destination': base_booking.estimate.estimation_log.destination
                }
            return {'departure': 'N/A', 'destination': 'N/A'}
        except Exception as e:
            print(f"❌ Erreur récupération trajet: {e}")
            return {'departure': 'N/A', 'destination': 'N/A'}
    
    @staticmethod
    def _get_booking_cost(booking_id):
        """Récupère le coût d'un booking de manière sécurisée"""
        try:
            from courses.models import Booking
            booking = Booking.objects.get(id=booking_id)
            return booking.estimate.total_booking_cost if booking.estimate else 0
        except:
            return 0