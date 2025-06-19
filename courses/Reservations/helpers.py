from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.test import APIRequestFactory
from configurations.models import Attribute, MeetingPlace, PaymentMethod, Vehicle
from courses.models import AppliedTariff, Booking, BookingLog, Estimate, EstimateAttribute, EstimationLog, EstimationTariff, Passenger, UserChoice
from parametrages.models import StaticContent, Urls
from utilisateurs.Auth.views import LoginView, UserCreationView
from utilisateurs.helpers import get_business_info, send_email
from utilisateurs.models import Business, Client, CustomUser
from django.db import transaction
from courses.Reservations.serializers import ClientInfoSerializer, ClientResponseSerializer, EstimateAttributeResponseSerializer, EstimateAttributeSerializer, EstimationLogIdSerializer, PassengerResponseSerializer, PassengerSerializer, UserChoiceSerializer
from django.utils import timezone
from rest_framework.request import Request
from decimal import Decimal
from django.template.loader import render_to_string
from django.conf import settings
from urllib.parse import urljoin

def handle_api_exceptions(view_func):
    """
    Décorateur pour gérer les exceptions dans les vues API.
    """
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except ValueError as e:
            return create_response(
                status_type="error",
                message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"An unexpected error occurred: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return wrapper

def create_response(status_type, message, data=None, http_status=status.HTTP_200_OK, error=None):
    """
    Crée une réponse API standardisée.
    """
    response_payload = {
        "status": status_type,
        "message": message,
        "data": data if data else {},
        "http_status": http_status,
    }
    if error:
        response_payload["error"] = str(error)
    return Response(response_payload, status=http_status)

def validate_serializer(serializer_class, data, error_key):
    """
    Valide les données avec un sérialiseur et retourne les données validées ou les erreurs.
    """
    serializer = serializer_class(data=data)
    if serializer.is_valid():
        return serializer.validated_data, None
    return None, {error_key: serializer.errors}

def validate_client_info(client_data):
    """
    Valide les informations client (existant, connexion, ou nouveau).
    ✅ SIMPLE : Admin n'a pas besoin de compte client
    """
    errors = {}
    validated_data = {}

    if 'existing_user' in client_data:
        custom_user = get_object_or_404(CustomUser, id=client_data['existing_user']['id'])
        
        # ✅ SIMPLE : Si c'est un admin, pas besoin de profil Client
        if custom_user.user_type == 'administrator':
            user_data = client_data['existing_user']
            user_data['client_type_display'] = "Administrator"
            validated_data['user'] = {"existing_user": user_data}
        else:
            # Pour les autres, on garde la logique normale
            client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
            user_data = client_data['existing_user']
            user_data['client_type_display'] = client.get_client_type_display()
            validated_data['user'] = {"existing_user": user_data}
    
    elif 'username' in client_data and 'password' in client_data:
        factory = APIRequestFactory()
        request = factory.post('/login/', data=client_data, format='json')
        drf_request = Request(request)
        drf_request._full_data = client_data
        login_view = LoginView()
        login_response = login_view.post(drf_request)
        
        if login_response.status_code == status.HTTP_200_OK:
            user_info = login_response.data.get("data", {}).get("user_info", {})
            custom_user = get_object_or_404(CustomUser, id=user_info['user_id'])
            
            # ✅ SIMPLE : Admin ou Client normal
            if custom_user.user_type == 'administrator':
                client_type_display = "Administrator"
            else:
                client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
                client_type_display = client.get_client_type_display()
            
            user_info.update({
                "first_name": custom_user.first_name,
                "last_name": custom_user.last_name,
                "email": custom_user.email,
                "phone_number": custom_user.phone_number,
                "address": custom_user.address,
                "client_type_display": client_type_display
            })
            validated_data['user'] = {"logged_user": login_response.data}
        else:
            errors['user'] = "Échec de la connexion avec les identifiants fournis."
    
    elif 'new_user' in client_data:
        # Cette partie reste identique (création de nouveaux clients)
        factory = APIRequestFactory()
        request = factory.post('/register/', data=client_data['new_user'], format='json')
        drf_request = Request(request)
        drf_request._full_data = client_data['new_user']
        user_creation_view = UserCreationView()
        creation_response = user_creation_view.post(drf_request)
        
        if creation_response.status_code == status.HTTP_201_CREATED:
            user_data = creation_response.data.get("data", {})
            custom_user = get_object_or_404(CustomUser, username=user_data['username'])
            client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
            user_data.update({
                "id": custom_user.id,
                "client_type_display": client.get_client_type_display()
            })
            validated_data['user'] = {"new_user": {**creation_response.data, "data": user_data}}
        else:
            errors['user'] = "Échec de la création de l'utilisateur."
    
    else:
        errors['user'] = "Informations client invalides."

    if not errors and 'user' in validated_data:
        formatted_data = ClientResponseSerializer(validated_data['user']).data
        return formatted_data, errors
    return {}, errors

def create_and_associate_passengers(user_id, passengers_data):
    """
    Crée et associe des passagers à un utilisateur.
    ✅ SIMPLE : Support admin sans compte client
    """
    user = get_object_or_404(CustomUser, id=user_id)
    passenger_ids = []
    display_data = []

    # ✅ Pour admin : pas besoin de client, on crée les passagers "orphelins"
    if user.user_type == 'administrator':
        client_for_passengers = None  # Admin n'a pas de profil client
    else:
        client_for_passengers = user.client

    # Passagers existants
    for passenger_id in passengers_data.get('existing', []):
        passenger = get_object_or_404(Passenger, id=passenger_id)
        passenger_ids.append(passenger.id)
        display_data.append({
            "name": passenger.name, 
            "phone_number": passenger.phone_number,
            "email": passenger.email or "Non renseigné",
            "is_main_client": passenger.is_main_client
        })

    # Nouveaux passagers
    for new_passenger in passengers_data.get('new', []):
        # ✅ CORRECTION : Gestion sécurisée de l'email
        email = new_passenger.get('email')
        if email:
            email = email.strip() or None
        else:
            email = None
            
        passenger = Passenger.objects.create(
            name=new_passenger['name'],
            phone_number=new_passenger['phone_number'],
            email=email,  # ✅ email déjà traité
            is_main_client=new_passenger.get('is_main_client', False),
            client=client_for_passengers  # Peut être None pour admin
        )
        passenger_ids.append(passenger.id)
        display_data.append({
            "name": passenger.name, 
            "phone_number": passenger.phone_number,
            "email": passenger.email or "Non renseigné",
            "is_main_client": passenger.is_main_client
        })

    return {
        "display_data": display_data,
        "request_data": passenger_ids
    }

def process_estimate_attributes(estimate_attributes_data):
    """
    Traite les attributs d'estimation.
    """
    total_attributes_cost = 0
    estimate_attribute_ids = []
    display_data = []

    with transaction.atomic():
        for attribute_data in estimate_attributes_data:
            attribute = Attribute.objects.get(id=attribute_data['attribute'])
            existing_estimate_attribute = EstimateAttribute.objects.filter(
                attribute=attribute,
                quantity=attribute_data['quantity']
            ).first()

            estimate_attribute = existing_estimate_attribute or EstimateAttribute.objects.create(
                attribute=attribute,
                quantity=attribute_data['quantity']
            )

            estimate_attribute_ids.append(estimate_attribute.id)
            total_attributes_cost += estimate_attribute.total
            display_data.append({
                "attribute_name": attribute.attribute_name,
                "unit_price": float(attribute.unit_price),
                "quantity": estimate_attribute.quantity,
                "total": float(estimate_attribute.total)
            })

    return {
        "display_data": display_data,
        "request_data": {
            "ids": estimate_attribute_ids,
            "total_attributes_cost": float(total_attributes_cost)
        },
        "total_attributes_cost": float(total_attributes_cost)
    }

def apply_commission_or_compensation(total_booking_cost, compensation=None, commission=None):
    """
    Applique la commission ou la compensation au coût total.
    ✅ CORRECTION: Commission = pourcentage prélevé sur le prix client
    """
    total_booking_cost = Decimal(str(total_booking_cost))
    
    if compensation is not None and compensation > 0:
        # Compensation = montant ajouté au prix de base
        driver_sale_price = total_booking_cost + Decimal(str(compensation))
        partner_sale_price = total_booking_cost + Decimal(str(compensation))
        commission = Decimal('0')
        
    elif commission is not None and commission > 0:
        # ✅ CORRECTION: Commission = pourcentage du prix client
        # Le prix client reste inchangé, mais chauffeur/partenaire reçoivent moins
        commission_amount = total_booking_cost * (Decimal(str(commission)) / Decimal('100'))
        driver_sale_price = total_booking_cost - commission_amount  # ✅ CORRECT
        partner_sale_price = total_booking_cost - commission_amount  # ✅ CORRECT
        compensation = Decimal('0')
        
    else:
        driver_sale_price = total_booking_cost
        partner_sale_price = total_booking_cost
        compensation = commission = Decimal('0')

    return {
        "driver_sale_price": float(max(driver_sale_price, Decimal('0'))),
        "partner_sale_price": float(max(partner_sale_price, Decimal('0'))),
        "compensation": float(compensation),
        "commission": float(commission)
    }
    
def process_booking_data(validated_data):
    errors = {}
    formatted_data = {}

    client_data = validated_data.get('user')
    if client_data:
        client_info, client_errors = validate_client_info(client_data)
        if client_errors:
            errors['user'] = client_errors
        else:
            formatted_data['user'] = client_info

    passengers_data = validated_data.get('passengers')
    if passengers_data and 'user' in formatted_data:
        user_id = formatted_data['user']['request_data'].get('id')
        if user_id:
            try:
                passengers_response = create_and_associate_passengers(user_id, passengers_data)
                formatted_data['passengers'] = PassengerResponseSerializer(passengers_response).data
            except Exception as e:
                errors['passengers'] = str(e)
        else:
            errors['passengers'] = "L'ID de l'utilisateur est manquant."

    estimate_attributes_data = validated_data.get('estimate_attribute')
    if estimate_attributes_data:
        try:
            attributes_result = process_estimate_attributes(estimate_attributes_data)
            formatted_data['estimate_attribute'] = EstimateAttributeResponseSerializer(attributes_result).data
        except Exception as e:
            errors['estimate_attribute'] = str(e)

    user_choice = validated_data.get('user_choice')
    estimation_log_id = validated_data.get('estimation_log')
    total_attributes_cost = formatted_data.get('estimate_attribute', {}).get('request_data', {}).get('total_attributes_cost', 0)
    code_promo = validated_data.get('code_promo')
    compensation = validated_data.get('compensation')
    commission = validated_data.get('commission')

    if user_choice and estimation_log_id:
        try:
            if user_choice.get('estimation_tariff_id'):
                estimation_tariff = get_object_or_404(EstimationTariff, id=user_choice['estimation_tariff_id'])
            else:
                estimation_tariff = get_object_or_404(
                    EstimationTariff,
                    estimation_log_id=estimation_log_id,
                    vehicle_id=user_choice['vehicle_id']
                )
            cost_result = calculate_booking_costs(
                user_choice=user_choice,
                estimation_tariff=estimation_tariff,
                client=formatted_data['user'],
                total_attributes_cost=total_attributes_cost,
                code_promo=code_promo,
                compensation=compensation,
                commission=commission,
                save_user_choice=True
            )
            formatted_data.update(cost_result)
        except Exception as e:
            errors['cost_calculation'] = str(e)

    return formatted_data, errors

def get_meeting_place_data(meeting_place_id):
    """
    Récupère les informations du lieu de rendez-vous.
    ✅ CORRECTION: Gestion du cas où meeting_place_id est None
    """
    from configurations.models import MeetingPlace
    
    if meeting_place_id is None:
        return {
            "display_data": "Aucun lieu de rendez-vous spécifié",
            "request_data": None
        }
    
    try:
        meeting_place = MeetingPlace.objects.get(id=meeting_place_id)
        return {
            "display_data": meeting_place.address,
            "request_data": meeting_place.id
        }
    except MeetingPlace.DoesNotExist:
        return {
            "display_data": f"Lieu de rendez-vous non trouvé (ID: {meeting_place_id})",
            "request_data": None
        }
    except Exception as e:
        return {
            "display_data": f"Erreur lieu de rendez-vous: {str(e)}",
            "request_data": None
        }

def get_payment_method_data(payment_method_id):
    """
    Récupère les informations de la méthode de paiement.
    """
    try:
        payment_method = PaymentMethod.objects.get(id=payment_method_id)
        payment_method_name = format_payment_method_name(payment_method.name)
        return {
            "display_data": payment_method_name,
            "request_data": payment_method.id
        }
    except PaymentMethod.DoesNotExist:
        return {
            "display_data": "Méthode de paiement non trouvée",
            "request_data": None
        }

def format_payment_method_name(name):
    """
    Formate le nom de la méthode de paiement en français.
    """
    payment_methods_mapping = {
        "onboard_payment": "Paiement à bord",
        "bank_transfer": "Virement bancaire",
        "paypal_payment": "Paiement via PayPal",
        "stripe_payment": "Paiement via Stripe",
        "account_payment": "Paiement sur compte"
    }
    return payment_methods_mapping.get(name, name)

def get_estimation_log_data(estimation_log_id):
    """
    Récupère les informations de l'estimation.
    """
    try:
        estimation_log = EstimationLog.objects.get(id=estimation_log_id)
        return {
            "display_data": {
                "departure": estimation_log.departure,
                "destination": estimation_log.destination,
                "pickup_date": estimation_log.pickup_date.isoformat(),
                "waypoints": estimation_log.waypoints or [],
                "estimate_type": estimation_log.get_estimate_type_display(),
                "distance_travelled": estimation_log.distance_travelled,
                "duration_travelled": estimation_log.duration_travelled
            },
            "request_data": estimation_log.id
        }
    except EstimationLog.DoesNotExist:
        return {
            "display_data": "Estimation non trouvée",
            "request_data": None
        }

def update_estimation_and_create_estimate(estimation_log_id, user_id, is_code_promo_used, request_data):
    """
    Met à jour l'EstimationLog et crée une estimation.
    """
    estimation_log = get_object_or_404(EstimationLog, id=estimation_log_id)
    user = get_object_or_404(CustomUser, id=user_id)
    estimation_log.user = user
    estimation_log.is_booked = True
    estimation_log.save()

    if is_code_promo_used:
        tariff_rule = estimation_log.tariffs.first().rules.filter(rule_type="promo_code").first()
        if tariff_rule and tariff_rule.promo_code:
            promo_code = tariff_rule.promo_code
            promo_code.usage_count += 1
            promo_code.save()

    return create_estimate(request_data)

def log_booking_action(booking, user_id, action, custom_message=None):
    """
    Enregistre une action dans les logs de réservation.
    """
    user = get_object_or_404(CustomUser, id=user_id) if user_id else None
    predefined_messages = {
        "created": "La réservation a été créée avec succès.",
        "updated": "Les détails de la réservation ont été mis à jour.",
        "cancelled": "La réservation a été annulée.",
        "assigned_to_driver": f"La réservation a été assignée au chauffeur {user.get_full_name() if user else 'Utilisateur inconnu'}.",
        "assigned_to_partner": f"La réservation a été assignée au partenaire {user.get_full_name() if user else 'Utilisateur inconnu'}.",
        "invoice_generated": "La facture pour la réservation a été générée.",
        "payment_received": "Le paiement pour la réservation a été reçu.",
        "status_changed": f"Le statut de la réservation a été changé à '{action}'."
    }
    message = custom_message or predefined_messages.get(action, action)
    return BookingLog.objects.create(booking=booking, user=user, action=message)

def get_business_info_for_pdf():
    """
    Récupère les informations de l'entreprise pour les PDF.
    """
    default_business_info = {
        "name": "Votre Entreprise",
        "email": "support@votreentreprise.com",
        "phone_number": "+1234567890",
        "address": "123 Rue de l'Entreprise, Ville, Pays",
        "logo_url": None,
        "operator_url": "http://127.0.0.1:8000",
    }
    business = Business.objects.filter(business_type="my_business").first()
    operator_url = Urls.objects.first()
    business_info = {
        "name": business.name if business else default_business_info["name"],
        "email": business.email if business else default_business_info["email"],
        "phone_number": business.phone_number if business else default_business_info["phone_number"],
        "address": business.address if business else default_business_info["address"],
        "operator_url": operator_url.operator_url if operator_url else default_business_info["operator_url"],
    }
    if business and business.logo:
        business_info["logo_url"] = urljoin(settings.BASE_URL, business.logo.url)
    return business_info

def get_selected_tariff(user_choice, estimation_tariff):
    """
    Retourne le tarif sélectionné.
    """
    if user_choice['is_standard_cost']:
        return estimation_tariff.standard_cost
    
    # CORRECTION: Chercher l'AppliedTariff correct
    from courses.models import AppliedTariff
    try:
        applied_tariff = AppliedTariff.objects.get(
            estimation_tariff_id=estimation_tariff.id,
            id=user_choice['selected_tariff']
        )
        return applied_tariff.calculated_cost
    except AppliedTariff.DoesNotExist:
        # Fallback vers le tarif standard si l'applied_tariff n'existe pas
        return estimation_tariff.standard_cost
    
def validate_and_apply_promo_code(code_promo, client, estimation_tariff):
    """
    Valide et applique un code promo.
    """
    try:
        tariff_rule = estimation_tariff.rules.filter(
            rule_type="promo_code",
            promo_code__code=code_promo
        ).first()
        if not tariff_rule or not tariff_rule.is_applicable(client, timezone.now()):
            return None
        promo_code = tariff_rule.promo_code
        if promo_code.usage_limit and promo_code.usage_count >= promo_code.usage_limit:
            return None
        return {
            "percentage": promo_code.percentage,
            "fixed_amount": promo_code.fixed_amount,
            "promo_code_id": promo_code.id
        }
    except Exception as e:
        return None

def calculate_final_cost(selected_tariff, promo_code_info, total_attributes_cost):
    """
    Calcule le coût final.
    """
    final_cost = Decimal(str(selected_tariff))
    if promo_code_info:
        if promo_code_info['percentage']:
            final_cost *= (Decimal('1') - Decimal(str(promo_code_info['percentage'])) / Decimal('100'))
        if promo_code_info['fixed_amount']:
            final_cost -= Decimal(str(promo_code_info['fixed_amount']))
    total_booking_cost = final_cost + Decimal(str(total_attributes_cost))
    return {
        "total_booking_cost": float(max(total_booking_cost, Decimal('0'))),
        "total_attributes_cost": float(max(total_attributes_cost, Decimal('0')))
    }

def update_estimation_tariff(estimation_tariff, standard_cost):
    """
    Met à jour les champs d'un EstimationTariff.
    """
    # CORRECTION: Convertir standard_cost en Decimal
    
    standard_cost_decimal = Decimal(str(standard_cost))
    
    estimation_tariff.standard_cost = standard_cost_decimal
    estimation_tariff.coutBrute = standard_cost_decimal
    estimation_tariff.tva = standard_cost_decimal * Decimal('0.1')  # 10% de TVA
    estimation_tariff.total_cost = standard_cost_decimal + estimation_tariff.tva
    estimation_tariff.save()
    return estimation_tariff

def calculate_booking_costs(user_choice, estimation_tariff, client, total_attributes_cost, code_promo=None, compensation=None, commission=None, save_user_choice=False):
    """
    Calcule les coûts d'une réservation ou estimation.
    ✅ CORRECTION: Gestion du client None + amélioration robustesse
    """
    # Vérifier que l'applied_tariff existe avant de l'utiliser
    if user_choice.get('standard_cost') is not None and user_choice['is_standard_cost']:
        update_estimation_tariff(estimation_tariff, user_choice['standard_cost'])

    try:
        selected_tariff = get_selected_tariff(user_choice, estimation_tariff)
    except Exception as e:
        # Si erreur avec applied_tariff, utiliser le tarif standard
        selected_tariff = estimation_tariff.standard_cost
        user_choice['is_standard_cost'] = True

    # ✅ CORRECTION: Code promo seulement si client existe
    promo_code_info = None
    if code_promo and client:  # ✅ Vérifier que client n'est pas None
        promo_code_info = validate_and_apply_promo_code(code_promo, client, estimation_tariff)
    
    cost_result = calculate_final_cost(selected_tariff, promo_code_info, total_attributes_cost)
    commission_compensation_result = apply_commission_or_compensation(
        cost_result["total_booking_cost"], compensation, commission
    )
    cost_result.update(commission_compensation_result)

    promotion_message = None
    is_code_promo_used = False
    if promo_code_info:
        is_code_promo_used = True
        if promo_code_info['percentage']:
            promotion_message = (
                f"Le code promo « {code_promo} » a permis d'appliquer une réduction de "
                f"{promo_code_info['percentage']}% sur le tarif de votre réservation."
            )
        elif promo_code_info['fixed_amount']:
            promotion_message = (
                f"Le code promo « {code_promo} » a permis d'appliquer une réduction de "
                f"{promo_code_info['fixed_amount']}€ sur le tarif de votre réservation."
            )

    user_choice_id = None
    if save_user_choice:
        from courses.models import AppliedTariff
        selected_tariff_obj = None
        if not user_choice['is_standard_cost'] and user_choice.get('selected_tariff'):
            try:
                selected_tariff_obj = AppliedTariff.objects.get(id=user_choice['selected_tariff'])
            except AppliedTariff.DoesNotExist:
                user_choice['is_standard_cost'] = True
                
        user_choice_instance = UserChoice.objects.create(
            vehicle_id=user_choice['vehicle_id'],
            selected_tariff=selected_tariff_obj,
            is_standard_cost=user_choice['is_standard_cost']
        )
        user_choice_id = user_choice_instance.id

    return {
        "selected_tariff": selected_tariff,
        "promo_code_info": promo_code_info,
        "total_booking_cost": cost_result["total_booking_cost"],
        "total_attributes_cost": cost_result["total_attributes_cost"],
        "promotion_message": promotion_message,
        "is_code_promo_used": is_code_promo_used,
        "user_choice_id": user_choice_id,
        "driver_sale_price": cost_result["driver_sale_price"],
        "partner_sale_price": cost_result["partner_sale_price"],
        "compensation": cost_result["compensation"],
        "commission": cost_result["commission"]
    }

def format_booking_data(validated_data=None, formatted_data=None, booking=None, include_request_data=True):
    """
    Formate les données de réservation ou d'estimation.
    """
    display_data = {}
    request_data = {} if include_request_data else None

    if booking:
        simple_fields = [
            'compensation', 'commission', 'driver_sale_price', 'booking_number',
            'partner_sale_price', 'flight_number', 'message', 'created_at', 'case_number'
        ]
        for field in simple_fields:
            value = getattr(booking, field, None)
            if value is not None:
                display_data[field] = value
                if include_request_data:
                    request_data[field] = value

        # ✅ NOUVELLE LOGIQUE : Gestion admin vs client
        if booking.client:
            # Réservation CLIENT normale
            display_data["user"] = {
                "email": booking.client.email,
                "first_name": booking.client.first_name,
                "last_name": booking.client.last_name,
                "phone_number": booking.client.phone_number,
                "address": booking.client.address,
                "client_type": booking.client.get_client_type_display()
            }
            if include_request_data:
                request_data["user_id"] = booking.client.id
        else:
            # Réservation ADMIN - récupérer l'admin qui l'a créée
            admin_user = booking.estimate.estimation_log.user
            if admin_user and admin_user.user_type == 'administrator':
                display_data["user"] = {
                    "email": admin_user.email,
                    "first_name": admin_user.first_name,
                    "last_name": admin_user.last_name,
                    "phone_number": admin_user.phone_number,
                    "address": admin_user.address,
                    "client_type": "Réservation Administrateur"
                }
                if include_request_data:
                    request_data["user_id"] = admin_user.id
                    request_data["is_admin_booking"] = True

        if booking.estimate.passengers.exists():
            passengers_data = [
                {
                    "name": p.name,
                    "phone_number": p.phone_number,
                    "email": p.email or "Non renseigné",
                    "is_main_client": p.is_main_client
                }
                for p in booking.estimate.passengers.all()
            ]
            display_data["passengers"] = passengers_data
            if include_request_data:
                request_data["passengers"] = [p.id for p in booking.estimate.passengers.all()]

        if booking.estimate.estimate_attribute.exists():
            attributes_data = [
                {
                    "attribute_name": a.attribute.attribute_name,
                    "unit_price": float(a.attribute.unit_price),
                    "quantity": a.quantity,
                    "total": float(a.total)
                }
                for a in booking.estimate.estimate_attribute.all()
            ]
            display_data["estimate_attribute"] = attributes_data
            if include_request_data:
                request_data["estimate_attribute"] = [a.id for a in booking.estimate.estimate_attribute.all()]

        if booking.estimate.user_choice:
            vehicle = Vehicle.objects.get(id=booking.estimate.user_choice.vehicle_id)
            display_data["vehicle"] = {
                "brand": vehicle.brand,
                "model": vehicle.model,
                "vehicle_type": vehicle.vehicle_type.name
            }
            display_data.update({
                "number_of_luggages": booking.estimate.number_of_luggages,
                "number_of_passengers": booking.estimate.number_of_passengers,
                "total_booking_cost": booking.estimate.total_booking_cost,
                "total_attributes_cost": booking.estimate.total_attributes_cost,
                "driver_sale_price": booking.driver_sale_price,
                "partner_sale_price": booking.partner_sale_price,
                "standard_cost": booking.estimate.user_choice.is_standard_cost and booking.estimate.estimation_log.tariffs.first().standard_cost or None
            })
            if include_request_data:
                request_data.update({
                    "user_choice": booking.estimate.user_choice.id,
                    "total_booking_cost": booking.estimate.total_booking_cost,
                    "total_attributes_cost": booking.estimate.total_attributes_cost,
                    "driver_sale_price": booking.driver_sale_price,
                    "partner_sale_price": booking.partner_sale_price,
                    "standard_cost": booking.estimate.user_choice.is_standard_cost and booking.estimate.estimation_log.tariffs.first().standard_cost or None
                })

        display_data["total_trajet"] = booking.estimate.total_booking_cost - booking.estimate.total_attributes_cost if booking.estimate.total_booking_cost else 0.0

        if booking.estimate.meeting_place:
            meeting_place_data = get_meeting_place_data(booking.estimate.meeting_place.id)
            display_data["meeting_place"] = meeting_place_data["display_data"]
            if include_request_data:
                request_data["meeting_place"] = meeting_place_data["request_data"]
        else:
            display_data["meeting_place"] = "Aucun lieu de rendez-vous spécifié"
            if include_request_data:
                request_data["meeting_place"] = None
                
        if booking.estimate.payment_method:
            payment_method_data = get_payment_method_data(booking.estimate.payment_method.id)
            display_data["payment_method"] = payment_method_data["display_data"]
            if include_request_data:
                request_data["payment_method"] = payment_method_data["request_data"]

        if booking.estimate.estimation_log:
            estimation_log_data = get_estimation_log_data(booking.estimate.estimation_log.id)
            display_data["estimation_log"] = estimation_log_data["display_data"]
            if include_request_data:
                request_data["estimation_log"] = estimation_log_data["request_data"]

    elif validated_data and formatted_data:
        simple_fields = [
            'code_promo', 'flight_number', 'message', 'number_of_luggages',
            'number_of_passengers', 'case_number', 'compensation', 'commission'
        ]
        for field in simple_fields:
            if field in validated_data:
                display_data[field] = validated_data[field]
                if include_request_data:
                    request_data[field] = validated_data[field]

        if 'user' in formatted_data:
            display_data.update(formatted_data['user']['display_data'])
            if include_request_data:
                request_data["user_id"] = formatted_data['user']['request_data'].get('id')

        if 'passengers' in formatted_data:
            display_data["passengers"] = formatted_data['passengers']['display_data']
            if include_request_data:
                request_data["passengers"] = formatted_data['passengers']['request_data'].get('ids')

        if 'estimate_attribute' in formatted_data:
            attributes_data = [
                {
                    "attribute_name": attr['attribute_name'],
                    "unit_price": attr['unit_price'],
                    "quantity": attr['quantity'],
                    "total": attr['total']
                }
                for attr in formatted_data['estimate_attribute']['display_data']
                if "total_attributes_cost" not in attr
            ]
            display_data["estimate_attribute"] = attributes_data
            if include_request_data:
                request_data["estimate_attribute"] = formatted_data['estimate_attribute']['request_data'].get('ids')

        if 'user_choice_id' in formatted_data:
            user_choice = UserChoice.objects.get(id=formatted_data['user_choice_id'])
            vehicle = Vehicle.objects.get(id=user_choice.vehicle_id)
            display_data["vehicle"] = {
                "brand": vehicle.brand,
                "model": vehicle.model,
                "vehicle_type": vehicle.vehicle_type.name
            }
            display_data.update({
                "total_booking_cost": formatted_data['total_booking_cost'],
                "total_attributes_cost": formatted_data['total_attributes_cost'],
                "promotion_message": formatted_data.get('promotion_message'),
                "driver_sale_price": formatted_data['driver_sale_price'],
                "partner_sale_price": formatted_data['partner_sale_price'],
                "standard_cost": user_choice.is_standard_cost and formatted_data['selected_tariff'] or None
            })
            if include_request_data:
                request_data.update({
                    "user_choice": formatted_data['user_choice_id'],
                    "total_booking_cost": formatted_data['total_booking_cost'],
                    "total_attributes_cost": formatted_data['total_attributes_cost'],
                    "driver_sale_price": formatted_data['driver_sale_price'],
                    "partner_sale_price": formatted_data['partner_sale_price'],
                    "standard_cost": user_choice.is_standard_cost and formatted_data['selected_tariff'] or None
                })

        if 'meeting_place' in validated_data and validated_data['meeting_place']:
            meeting_place_data = get_meeting_place_data(validated_data['meeting_place'])
            display_data["meeting_place"] = meeting_place_data["display_data"]
            if include_request_data:
                request_data["meeting_place"] = meeting_place_data["request_data"]
        else:
            display_data["meeting_place"] = "Aucun lieu de rendez-vous spécifié"
            if include_request_data:
                request_data["meeting_place"] = None
                
        if 'estimation_log' in validated_data:
            estimation_log_data = get_estimation_log_data(validated_data['estimation_log'])
            display_data["estimation_log"] = estimation_log_data["display_data"]
            if include_request_data:
                request_data["estimation_log"] = estimation_log_data["request_data"]

    result = {"display_data": display_data}
    if include_request_data:
        result["request_data"] = request_data
    return result


def get_booking_email_context_and_send_emails(booking_id, display_data=None, is_update=False):
    """
    ✅ FONCTION PRINCIPALE SIMPLIFIÉE
    Point d'entrée unique pour création ET mise à jour
    Compatible avec l'ancienne interface mais utilise le nouveau système unifié
    """
    # Le paramètre display_data est ignoré car on reconstruit les données
    # pour garantir la cohérence et éviter la redondance
    send_unified_emails(booking_id, is_update)
    
def validate_booking_data(data, request=None):
    """
    Validation des données de booking avec support de modification via estimate_id
    """
    errors = {}
    validated_data = {}

    # Validation de estimation_log (obligatoire)
    estimation_log_value = data.get('estimation_log')
    if estimation_log_value:
        try:
            EstimationLog.objects.get(id=estimation_log_value)
            validated_data['estimation_log'] = estimation_log_value
        except EstimationLog.DoesNotExist:
            errors['estimation_log'] = f"L'estimation avec l'ID {estimation_log_value} n'existe pas."
        except Exception as e:
            errors['estimation_log'] = f"Erreur lors de la validation de estimation_log: {str(e)}"
    else:
        errors['estimation_log'] = "estimation_log est obligatoire."

    # Validation optionnelle du meeting_place
    meeting_place_id = data.get('meeting_place')
    if meeting_place_id:
        try:
            from configurations.models import MeetingPlace
            MeetingPlace.objects.get(id=meeting_place_id)
            validated_data['meeting_place'] = meeting_place_id
        except MeetingPlace.DoesNotExist:
            errors['meeting_place'] = f"Le lieu de rendez-vous avec l'ID {meeting_place_id} n'existe pas."
        except Exception as e:
            errors['meeting_place'] = f"Erreur lors de la validation du lieu de rendez-vous: {str(e)}"
    else:
        validated_data['meeting_place'] = None

    # Validation des champs simples (optionnels)
    simple_fields = [
        'flight_number', 'code_promo', 'compensation',
        'message', 'number_of_luggages', 'number_of_passengers', 'case_number', 'commission'
    ]
    for field in simple_fields:
        validated_data[field] = data.get(field, None)

    # Validation user_choice (conditionnelle selon le mode)
    estimate_id = data.get('estimate_id')
    user_choice_data = data.get('user_choice')
    
    if user_choice_data:
        try:
            if 'vehicle_id' not in user_choice_data:
                errors['user_choice'] = "vehicle_id est obligatoire dans user_choice."
            else:
                try:
                    Vehicle.objects.get(id=user_choice_data['vehicle_id'])
                    if request:
                        serializer = UserChoiceSerializer(
                            data=user_choice_data,
                            context={'request': request, 'estimation_log_id': estimation_log_value}
                        )
                        if serializer.is_valid():
                            validated_data['user_choice'] = serializer.validated_data
                        else:
                            errors['user_choice'] = serializer.errors
                    else:
                        validated_data['user_choice'] = {
                            'vehicle_id': user_choice_data['vehicle_id'],
                            'estimation_tariff_id': user_choice_data.get('estimation_tariff_id'),
                            'selected_tariff': user_choice_data.get('selected_tariff'),
                            'is_standard_cost': user_choice_data.get('is_standard_cost', False),
                            'standard_cost': user_choice_data.get('standard_cost'),
                            'admin_booking': user_choice_data.get('admin_booking', False)
                        }
                except Vehicle.DoesNotExist:
                    errors['user_choice'] = f"Le véhicule avec l'ID {user_choice_data['vehicle_id']} n'existe pas."
        except Exception as e:
            errors['user_choice'] = f"Erreur lors de la validation de user_choice: {str(e)}"
    elif not estimate_id:
        # user_choice obligatoire seulement en création
        errors['user_choice'] = "user_choice est obligatoire pour la création d'une estimation."

    # Validation passengers
    if passengers_data := data.get('passengers'):
        validated_passengers, error = validate_serializer(PassengerSerializer, passengers_data, 'passengers')
        if validated_passengers:
            validated_data['passengers'] = {
                "existing": validated_passengers.get('existing', []),
                "new": [
                    {
                        "name": p['name'], 
                        "phone_number": p['phone_number'],
                        "email": p.get('email').strip() if p.get('email') else None,
                        "is_main_client": p.get('is_main_client', False)
                    }
                    for p in validated_passengers.get('new', [])
                ]
            }
        if error:
            errors.update(error)

    # Validation estimate_attribute
    if estimate_attribute_data := data.get('estimate_attribute'):
        attribute_list = []
        for attr in estimate_attribute_data:
            attribute_serializer, error = validate_serializer(EstimateAttributeSerializer, attr, 'estimate_attribute')
            if attribute_serializer:
                try:
                    attribute = Attribute.objects.get(id=attr['attribute'])
                    attribute_list.append({
                        "attribute": attribute.id,
                        "quantity": attr['quantity']
                    })
                except Attribute.DoesNotExist:
                    errors.setdefault('estimate_attribute', []).append(f"L'attribut avec l'ID {attr['attribute']} n'existe pas.")
            if error:
                errors.setdefault('estimate_attribute', []).append(error)
        validated_data['estimate_attribute'] = attribute_list

    # Validation user
    if user_info := data.get('user'):
        validated_data['user'], error = validate_serializer(ClientInfoSerializer, user_info, 'user')
        if error:
            errors.update(error)

    # Validation des champs obligatoires selon le mode
    if not estimate_id:
        # Mode création - champs obligatoires
        required_fields = ['estimation_log', 'user_choice', 'number_of_luggages', 'number_of_passengers']
        for field in required_fields:
            if not validated_data.get(field):
                errors.setdefault('fields', []).append(f"{field} est obligatoire.")
    else:
        # Mode modification - seulement estimation_log obligatoire
        if not validated_data.get('estimation_log'):
            errors.setdefault('fields', []).append("estimation_log est obligatoire.")

    return validated_data, errors  


def create_booking_with_payment_timing(data, payment_timing='later'):
    """
    Crée une réservation avec payment_timing
    ✅ SOLUTION SIMPLE : Admin = pas de client requis
    """
    estimate = get_object_or_404(Estimate, id=data['estimate'])
    user = get_object_or_404(CustomUser, id=data['client'])
    
    # ✅ SOLUTION SIMPLE : Si admin, pas de client
    if user.user_type == 'administrator':
        client_profile = None  # Pas de client pour les admins
    else:
        client_profile = user.client
    
    return Booking.objects.create(
        compensation=data['compensation'],
        commission=data['commission'],
        driver_sale_price=data['driver_sale_price'],
        partner_sale_price=data['partner_sale_price'],
        estimate=estimate,
        client=client_profile,  # None pour admin, client réel sinon
        payment_timing=payment_timing,
    )

def create_booking(data):
    """
    Crée une réservation.
    ✅ SOLUTION SIMPLE : Même logique
    """
    estimate = get_object_or_404(Estimate, id=data['estimate'])
    user = get_object_or_404(CustomUser, id=data['client'])
    
    # ✅ SOLUTION SIMPLE : Si admin, pas de client
    if user.user_type == 'administrator':
        client_profile = None
    else:
        client_profile = user.client
    
    return Booking.objects.create(
        compensation=data['compensation'],
        commission=data['commission'],
        driver_sale_price=data['driver_sale_price'],
        partner_sale_price=data['partner_sale_price'],
        estimate=estimate,
        client=client_profile,  # None pour admin, client réel sinon
    )

def create_estimate(request_data):
    """
    Crée une estimation.
    ✅ CORRECTION: MeetingPlace est maintenant optionnel
    """
    from django.shortcuts import get_object_or_404
    from configurations.models import MeetingPlace
    from courses.models import EstimationLog, UserChoice, Estimate
    
    # ✅ VALIDATIONS ROBUSTES
    try:
        estimation_log = get_object_or_404(EstimationLog, id=request_data.get('estimation_log'))
    except:
        raise ValueError(f"EstimationLog avec l'ID {request_data.get('estimation_log')} n'existe pas.")
    
    try:
        user_choice = get_object_or_404(UserChoice, id=request_data.get('user_choice'))
    except:
        raise ValueError(f"UserChoice avec l'ID {request_data.get('user_choice')} n'existe pas.")
    
    # ✅ MEETING_PLACE OPTIONNEL
    meeting_place = None
    meeting_place_id = request_data.get('meeting_place')
    if meeting_place_id:  # Seulement si fourni
        try:
            meeting_place = get_object_or_404(MeetingPlace, id=meeting_place_id)
        except:
            raise ValueError(f"MeetingPlace avec l'ID {meeting_place_id} n'existe pas.")

    estimate = Estimate.objects.create(
        estimation_log=estimation_log,
        user_choice=user_choice,
        meeting_place=meeting_place,  # ✅ Peut être None
        flight_number=request_data.get('flight_number'),
        message=request_data.get('message'),
        total_booking_cost=request_data.get('total_booking_cost'),
        total_attributes_cost=request_data.get('total_attributes_cost'),
        number_of_luggages=request_data.get('number_of_luggages'),
        number_of_passengers=request_data.get('number_of_passengers'),
        case_number=request_data.get('case_number'),
        is_payment_pending=True
    )

    # Gestion des passagers
    passengers_ids = request_data.get('passengers', [])
    if passengers_ids:
        from courses.models import Passenger
        passengers = Passenger.objects.filter(id__in=passengers_ids)
        estimate.passengers.set(passengers)

    # Gestion des attributs d'estimation
    estimate_attributes_ids = request_data.get('estimate_attribute', [])
    if estimate_attributes_ids:
        from courses.models import EstimateAttribute
        estimate_attributes = EstimateAttribute.objects.filter(id__in=estimate_attributes_ids)
        estimate.estimate_attribute.set(estimate_attributes)

    estimate.save()
    return estimate.id

def validate_client_id_and_get_passengers(client_id=None):
    """
    Valide l'ID du client et récupère les passagers associés.
    Si client_id est None, récupère les passagers avec client null.
    Retourne une liste de dictionnaires avec les données des passagers.
    """
    try:
        if client_id:
            # Vérifier si le client existe
            client = get_object_or_404(Client, id=client_id)
            passengers = Passenger.objects.filter(client=client)
        else:
            # Récupérer les passagers avec client null
            passengers = Passenger.objects.filter(client__isnull=True)

        # Formatter les données des passagers
        passengers_data = [
            {
                "id": passenger.id,
                "name": passenger.name,
                "phone_number": passenger.phone_number,
                "email": passenger.email,
                "is_main_client": passenger.is_main_client,
                "created_at": passenger.created_at
            }
            for passenger in passengers
        ]
        # Retourner une liste vide avec un message si aucun passager n'est trouvé
        if not passengers_data:
            return [], None
        return passengers_data, None
    except Exception as e:
        return [], {"client_id": f"Erreur lors de la récupération des passagers: {str(e)}"}

def format_booking_validation_response(validated_data, formatted_data, estimate_id):
    """
    Formate la réponse de validation de booking selon la nouvelle structure organisée.
    
    Args:
        validated_data: Données validées de la requête
        formatted_data: Données formatées après traitement
        estimate_id: ID de l'estimate créé
    
    Returns:
        dict: Réponse formatée selon la nouvelle structure
    """
    
    # 1. BOOKING INFO - Informations de base de la réservation
    booking_info = {
        "case_number": validated_data.get('case_number'),
        "flight_number": validated_data.get('flight_number'),
        "message": validated_data.get('message', ''),
        "number_of_passengers": validated_data.get('number_of_passengers'),
        "number_of_luggages": validated_data.get('number_of_luggages')
    }
    
    # 2. TRIP INFO - Informations du trajet
    estimation_log_data = get_estimation_log_data(validated_data.get('estimation_log'))
    meeting_place_data = get_meeting_place_data(validated_data.get('meeting_place'))
    
    trip_info = {
        "departure": estimation_log_data["display_data"]["departure"],
        "destination": estimation_log_data["display_data"]["destination"],
        "pickup_date": estimation_log_data["display_data"]["pickup_date"],
        "distance_travelled": estimation_log_data["display_data"]["distance_travelled"],
        "duration_travelled": estimation_log_data["display_data"]["duration_travelled"],
        "estimate_type": estimation_log_data["display_data"]["estimate_type"],
        "waypoints": estimation_log_data["display_data"]["waypoints"],
        "meeting_place": meeting_place_data["display_data"]
    }
    
    # 3. VEHICLE - Véhicule sélectionné
    user_choice = formatted_data.get('user_choice_id')
    if user_choice:
        user_choice_obj = UserChoice.objects.get(id=user_choice)
        vehicle = Vehicle.objects.get(id=user_choice_obj.vehicle_id)
        vehicle_info = {
            "brand": vehicle.brand,
            "model": vehicle.model,
            "vehicle_type": vehicle.vehicle_type.name
        }
    else:
        vehicle_info = {}
    
    # 4. CLIENT INFO - Informations du client
    client_data = formatted_data.get('user', {})
    client_info = {
        "name": client_data.get('display_data', {}).get('name', ''),
        "email": client_data.get('display_data', {}).get('email', ''),
        "phone_number": client_data.get('display_data', {}).get('phone_number', ''),
        "address": client_data.get('display_data', {}).get('address'),
        "user_type": client_data.get('display_data', {}).get('user_type', '')
    }
    
    # 5. PASSENGERS - Liste des passagers
    passengers_data = formatted_data.get('passengers', {}).get('display_data', [])
    passengers = [
        {
            "name": passenger['name'],
            "phone_number": passenger['phone_number'],
            "email": passenger.get('email', 'Non renseigné'),
            "is_main_client": passenger.get('is_main_client', False)
        }
        for passenger in passengers_data
    ]
    
    # 6. ADDITIONAL SERVICES - Services supplémentaires
    attributes_data = formatted_data.get('estimate_attribute', {}).get('display_data', [])
    additional_services = [
        {
            "name": attr['attribute_name'],
            "quantity": attr['quantity'],
            "unit_price": attr['unit_price'],
            "total": attr['total']
        }
        for attr in attributes_data
        if 'attribute_name' in attr  # Éviter les éléments de total
    ]
    
    # 7. PRICING - Tarification simplifiée (sans commission/compensation)
    pricing = {
        "base_cost": formatted_data.get('selected_tariff', 0),
        "additional_services_cost": formatted_data.get('total_attributes_cost', 0),
        "total_cost": formatted_data.get('total_booking_cost', 0)
    }
    
    # 8. TECHNICAL IDS - Seulement client_id et estimate_id
    technical_ids = {
        "client_id": client_data.get('request_data', {}).get('id'),
        "estimate_id": estimate_id
    }
    
    return {
        "status": "success",
        "message": "Validation successful, proceed to payment",
        "data": {
            "booking_info": booking_info,
            "trip_info": trip_info,
            "vehicle": vehicle_info,
            "client_info": client_info,
            "passengers": passengers,
            "additional_services": additional_services,
            "pricing": pricing,
            "technical_ids": technical_ids
        },
        "http_status": 200
    }

def get_payment_notes(payment_method, payment_timing):
    """
    Génère des notes de paiement selon la méthode et le timing
    ✅ CORRECTION: Cette fonction peut être conservée pour les logs ou autres usages
    """
    if not payment_method:
        return "Méthode de paiement non définie"
    
    method_name = payment_method.name
    notes_mapping = {
        'onboard_payment': 'Paiement à bord du véhicule',
        'bank_transfer': 'Virement bancaire - facture à envoyer',
        'account_payment': 'Paiement sur compte client',
        'paypal_payment': 'Paiement PayPal (à développer)',
        'stripe_payment': 'Paiement carte bancaire (à développer)'
    }
    
    base_note = notes_mapping.get(method_name, f"Paiement via {method_name}")
    
    if payment_timing == 'later':
        return f"{base_note} - À effectuer ultérieurement"
    else:
        return f"{base_note} - Paiement immédiat demandé (en développement)"

def get_payment_instructions(payment_method):
    """
    Retourne les instructions de paiement pour le client
    """
    if not payment_method:
        return "Contactez notre service client pour les modalités de paiement."
    
    instructions = {
        'onboard_payment': 'Vous pourrez régler directement auprès du chauffeur.',
        'bank_transfer': 'Vous recevrez prochainement nos coordonnées bancaires par email.',
        'account_payment': 'Le montant sera débité de votre compte client.',
        'paypal_payment': 'Le lien de paiement PayPal vous sera envoyé prochainement.',
        'stripe_payment': 'Le lien de paiement sécurisé vous sera envoyé prochainement.'
    }
    
    return instructions.get(payment_method.name, 
                          "Vous recevrez prochainement les instructions de paiement.")

# ✅ FONCTIONS UTILITAIRES SUPPLÉMENTAIRES
def is_admin_booking(booking):
    """
    Détermine si une réservation a été créée par un admin
    """
    return booking.client is None

def get_booking_creator_info(booking):
    """
    Retourne les infos sur qui a créé la réservation
    """
    if booking.client is None:
        # Réservation admin
        admin_user = booking.estimate.estimation_log.user
        return {
            "type": "admin",
            "user": admin_user,
            "name": admin_user.get_full_name() if admin_user else "Admin inconnu"
        }
    else:
        # Réservation client
        return {
            "type": "client", 
            "user": booking.client,
            "name": booking.client.get_full_name()
        }

def get_admin_bookings(admin_user):
    """
    Récupère toutes les réservations créées par un admin
    """
    if admin_user.user_type != 'administrator':
        return Booking.objects.none()
    
    # Réservations où client=None ET créées par cet admin
    return Booking.objects.filter(
        client__isnull=True,
        estimate__estimation_log__user=admin_user
    )
    
# ✅ NOUVELLES FONCTIONS À AJOUTER dans helpers.py

def get_unified_booking_context(booking_id, is_update=False):
    """
    ✅ FONCTION CENTRALE : Prépare toutes les données nécessaires pour emails et PDF
    Utilisée pour création ET mise à jour
    """
    booking = Booking.objects.get(id=booking_id)
    business_info = get_business_info()
    
    # Données de base de la réservation
    booking_data = format_booking_data(booking=booking, include_request_data=False)
    reservation_details = booking_data["display_data"]
    
    # Informations sur qui a créé la réservation
    booking_creator = get_booking_creator_info(booking)
    
    # URL du PDF
    pdf_url = f"{business_info['operator_url']}/api/reservations/booking/{booking_id}/pdf/"
    
    # Instructions de paiement si applicable
    if booking.estimate.payment_method:
        payment_instructions = get_payment_instructions(booking.estimate.payment_method)
        reservation_details["payment_instructions"] = payment_instructions
    
    # Context unifié pour tous les templates
    unified_context = {
        "reservation_details": reservation_details,
        "business_info": business_info,
        "booking_creator": booking_creator,
        "pdf_url": pdf_url,
        "is_update": is_update,
    }
    
    return unified_context, booking

def send_unified_emails(booking_id, is_update=False):
    """
    ✅ FONCTION OPTIMISÉE : Envoi unifié des emails selon le type de réservation
    Gère création ET mise à jour avec les mêmes templates
    """
    unified_context, booking = get_unified_booking_context(booking_id, is_update)
    
    # 1. Email MANAGER (toujours envoyé)
    send_manager_email(unified_context)
    
    # 2. Emails CLIENT/PASSAGERS selon le type de réservation
    if booking.client is None:
        # Réservation ADMIN → Emails aux passagers
        send_passenger_emails(unified_context, booking)
    else:
        # Réservation CLIENT → Email au client
        send_client_email(unified_context, booking)

def send_manager_email(context):
    """
    Envoie l'email au manager avec le template unifié
    """
    try:
        business = Business.objects.filter(business_type="my_business").first()
        if not (business and business.main_user and business.main_user.role == "manager"):
            raise Exception("Aucun manager trouvé pour cette entreprise.")
        
        manager_email = business.main_user.email
        subject = f"{'Mise à jour' if context['is_update'] else 'Nouvelle'} réservation - {context['reservation_details']['booking_number']}"
        
        html_content = render_to_string("fichiers_mails/email_booking_admin.html", context)
        send_email(manager_email, subject, html_content)
        
        print(f"✅ Email manager envoyé à {manager_email}")
    except Exception as e:
        print(f"❌ Erreur envoi email manager: {str(e)}")

def send_client_email(context, booking):
    """
    Envoie l'email au client avec le template unifié
    """
    if not booking.client or not booking.client.email:
        print("ℹ️ Réservation client : Pas d'email client")
        return
    
    try:
        client_email = booking.client.email
        client_name = booking.client.get_full_name()
        
        # Context spécifique client
        client_context = {
            **context,
            "recipient_name": client_name,
            "recipient_role": "client",
        }
        
        subject = f"{'Mise à jour de votre' if context['is_update'] else 'Confirmation de'} réservation - {context['reservation_details']['booking_number']}"
        
        html_content = render_to_string("fichiers_mails/email_booking_client.html", client_context)
        send_email(client_email, subject, html_content)
        
        print(f"✅ Email client envoyé à {client_email}")
    except Exception as e:
        print(f"❌ Erreur envoi email client: {str(e)}")

def send_passenger_emails(context, booking):
    """
    Envoie les emails aux passagers pour les réservations admin
    """
    passengers = context['reservation_details'].get("passengers", [])
    emails_sent = 0
    
    for passenger in passengers:
        passenger_email = passenger.get("email")
        if not passenger_email or passenger_email == "Non renseigné":
            continue
            
        try:
            # Context spécifique passager
            passenger_context = {
                **context,
                "recipient_name": passenger["name"],
                "recipient_role": "passenger",
                "recipient_is_main": passenger.get("is_main_client", False),
            }
            
            if passenger.get("is_main_client"):
                subject = f"{'Mise à jour de votre' if context['is_update'] else 'Confirmation de'} réservation - {context['reservation_details']['booking_number']}"
            else:
                subject = f"{'Mise à jour -' if context['is_update'] else ''} Vous êtes inscrit comme passager - {context['reservation_details']['booking_number']}"
            
            html_content = render_to_string("fichiers_mails/email_booking_client.html", passenger_context)
            send_email(passenger_email, subject, html_content)
            emails_sent += 1
            print(f"✅ Email passager envoyé à {passenger_email}")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi de l'email à {passenger_email}: {str(e)}")
    
    if emails_sent == 0:
        print("ℹ️ Réservation admin : Aucun passager avec email")
    else:
        print(f"ℹ️ Réservation admin : {emails_sent} email(s) envoyé(s) aux passagers")

def get_unified_pdf_context(booking_id):
    """
    ✅ FONCTION OPTIMISÉE : Prépare le contexte pour génération PDF
    """
    unified_context, booking = get_unified_booking_context(booking_id, is_update=False)
    
    # Ajouter le contenu statique pour PDF
    static_content = StaticContent.objects.first()
    pdf_context = {
        **unified_context,
        "static_content": static_content,
    }
    
    return pdf_context

def update_existing_estimate(estimate, validated_data, formatted_data):
    """
    Met à jour un estimate existant avec les nouvelles données
    """
    from django.db import transaction
    
    with transaction.atomic():
        # 1. CHAMPS SIMPLES - Modification directe
        simple_fields = [
            'meeting_place', 'flight_number', 'message',
            'number_of_luggages', 'number_of_passengers', 'case_number'
        ]
        
        for field in simple_fields:
            if field in validated_data:
                if field == 'meeting_place':
                    # Gérer le cas None pour meeting_place
                    meeting_place_id = validated_data[field]
                    if meeting_place_id:
                        from configurations.models import MeetingPlace
                        meeting_place = MeetingPlace.objects.get(id=meeting_place_id)
                        estimate.meeting_place = meeting_place
                    else:
                        estimate.meeting_place = None
                else:
                    setattr(estimate, field, validated_data[field])

        # 2. USER CHOICE - Modification directe de l'objet existant
        if 'user_choice' in validated_data and estimate.user_choice:
            user_choice = estimate.user_choice
            user_choice_data = validated_data['user_choice']
            
            user_choice.vehicle_id = user_choice_data['vehicle_id']
            user_choice.is_standard_cost = user_choice_data.get('is_standard_cost', False)
            
            # Gestion du selected_tariff
            if user_choice_data.get('selected_tariff'):
                from courses.models import AppliedTariff
                try:
                    selected_tariff_obj = AppliedTariff.objects.get(id=user_choice_data['selected_tariff'])
                    user_choice.selected_tariff = selected_tariff_obj
                except AppliedTariff.DoesNotExist:
                    user_choice.selected_tariff = None
                    user_choice.is_standard_cost = True
            else:
                user_choice.selected_tariff = None
            
            user_choice.save()

        # 3. PASSENGERS - Remplacement complet avec .set()
        if 'passengers' in formatted_data:
            passenger_ids = formatted_data['passengers']['request_data'].get('ids', [])
            estimate.passengers.set(passenger_ids)

        # 4. ESTIMATE ATTRIBUTES - Remplacement complet avec .set()
        if 'estimate_attribute' in formatted_data:
            attribute_ids = formatted_data['estimate_attribute']['request_data'].get('ids', [])
            estimate.estimate_attribute.set(attribute_ids)

        # 5. INFORMATIONS UTILISATEUR - Modification via EstimationLog
        if 'user' in formatted_data:
            new_user_id = formatted_data['user']['request_data'].get('id')
            if new_user_id:
                estimate.estimation_log.user_id = new_user_id
                estimate.estimation_log.save()

        # 6. COÛTS - Mise à jour des totaux
        if 'total_booking_cost' in formatted_data:
            estimate.total_booking_cost = formatted_data['total_booking_cost']
        
        if 'total_attributes_cost' in formatted_data:
            estimate.total_attributes_cost = formatted_data['total_attributes_cost']

        # 7. SAUVEGARDE
        estimate.save()
        
    return estimate.id