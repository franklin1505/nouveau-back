from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.test import APIRequestFactory
from configurations.models import Attribute, MeetingPlace, PaymentMethod, Vehicle
from courses.models import AppliedTariff, Booking, BookingLog, Estimate, EstimateAttribute, EstimationLog, EstimationTariff, Passenger, UserChoice
from parametrages.models import Urls
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


# fonctions validate booking
 
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

def validate_booking_data(data):
    errors = {}
    validated_data = {}

    # 1. Récupération de l'identifiant de estimation_log
    estimation_log_serializer = EstimationLogIdSerializer(data={'estimation_log': data.get('estimation_log')})
    if estimation_log_serializer.is_valid():
        validated_data['estimation_log'] = estimation_log_serializer.validated_data['estimation_log']
    else:
        errors['estimation_log'] = estimation_log_serializer.errors

    # 2. Informations simples
    simple_fields = [
        'meeting_place', 'payment_method', 'flight_number', 'code_promo', 'compensation',
        'message', 'number_of_luggages', 'number_of_passengers', 'case_number', 'commission'
    ]
    for field in simple_fields:
        validated_data[field] = data.get(field, None)

    # 3. Validation complexe pour user_choice
    user_choice_data = data.get('user_choice')
    if user_choice_data:
        user_choice_serializer = UserChoiceSerializer(data=user_choice_data)
        if user_choice_serializer.is_valid():
            validated_data['user_choice'] = user_choice_serializer.validated_data
        else:
            errors['user_choice'] = user_choice_serializer.errors

    # 4. Validation pour passengers
    passengers_data = data.get('passengers')
    if passengers_data:
        passenger_serializer = PassengerSerializer(data=passengers_data)
        if passenger_serializer.is_valid():
            validated_passengers = passenger_serializer.validated_data
            # Formater les données pour create_and_associate_passengers
            validated_data['passengers'] = {
                "existing": validated_passengers.get('existing', []),  # Liste d'IDs
                "new": [
                    {"name": passenger['name'], "phone_number": passenger['phone_number']}
                    for passenger in validated_passengers.get('new', [])
                ]
            }
        else:
            errors['passengers'] = passenger_serializer.errors

    # 5. Validation pour estimate_attribute
    estimate_attribute_data = data.get('estimate_attribute')
    if estimate_attribute_data:
        attribute_list = []
        for attr in estimate_attribute_data:
            attribute_serializer = EstimateAttributeSerializer(data=attr)
            if attribute_serializer.is_valid():
                # Vérifier que l'attribut existe dans la base de données
                try:
                    attribute = Attribute.objects.get(id=attr['attribute'])
                    attribute_list.append({
                        "attribute": attribute.id,  # ID de l'attribut
                        "quantity": attr['quantity']  # Quantité
                    })
                except Attribute.DoesNotExist:
                    errors.setdefault('estimate_attribute', []).append(f"L'attribut avec l'ID {attr['attribute']} n'existe pas.")
            else:
                errors.setdefault('estimate_attribute', []).append(attribute_serializer.errors)
        validated_data['estimate_attribute'] = attribute_list

    # 6. Validation des informations utilisateur
    user_info = data.get('user')
    if user_info:
        client_info_serializer = ClientInfoSerializer(data=user_info)
        if client_info_serializer.is_valid():
            validated_data['user'] = client_info_serializer.validated_data
        else:
            errors['user'] = client_info_serializer.errors

    # 7. Vérifier les champs obligatoires de base
    required_fields = ['estimation_log', 'payment_method', 'number_of_luggages', 'number_of_passengers']
    for field in required_fields:
        if not validated_data.get(field):
            errors.setdefault('fields', []).append(f"{field} est obligatoire.")

    return validated_data, errors

def validate_client_info(client_data):
    """
    Valide les informations client en fonction de trois cas possibles :
    1. Un ID est fourni : vérifie si l'utilisateur existe dans la base de données.
    2. Un username et un password sont fournis : tente de connecter l'utilisateur.
    3. Aucun ID ni credentials : crée un nouvel utilisateur.
    """
    errors = {}
    validated_data = {}

    # Cas 1 : ID fourni
    if 'existing_user' in client_data:
        user = client_data['existing_user']
        # Récupérer l'utilisateur à partir de CustomUser
        custom_user = get_object_or_404(CustomUser, id=user['id'])
        # Récupérer le Client associé
        client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
        user['client_type_display'] = client.get_client_type_display()
        validated_data['user'] = {"existing_user": user}
    
    # Cas 2 : Username et password fournis
    elif 'username' in client_data and 'password' in client_data:
        factory = APIRequestFactory()
        request = factory.post('/login/', data=client_data, format='json')
        
        # Convertir la requête WSGI en requête DRF
        drf_request = Request(request)
        drf_request._full_data = client_data  # Ajouter les données au format DRF
        
        login_view = LoginView()
        login_response = login_view.post(drf_request)
        
        if login_response.status_code == status.HTTP_200_OK:
            user_info = login_response.data.get("data", {}).get("user_info", {})
            # Récupérer l'utilisateur à partir de CustomUser
            custom_user = get_object_or_404(CustomUser, id=user_info['user_id'])
            # Récupérer le Client associé
            client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
            
            # Ajouter les informations manquantes à user_info
            user_info.update({
                "first_name": custom_user.first_name,
                "last_name": custom_user.last_name,
                "email": custom_user.email,
                "phone_number": custom_user.phone_number,
                "address": custom_user.address,
                "client_type_display": client.get_client_type_display()
            })
            
            validated_data['user'] = {"logged_user": login_response.data}
        else:
            errors['user'] = "Échec de la connexion avec les identifiants fournis."
    
    # Cas 3 : Nouvel utilisateur
    elif 'new_user' in client_data:
        factory = APIRequestFactory()
        request = factory.post('/register/', data=client_data['new_user'], format='json')
        
        # Convertir la requête WSGI en requête DRF
        drf_request = Request(request)
        drf_request._full_data = client_data['new_user']  # Ajouter les données au format DRF
        
        user_creation_view = UserCreationView()
        creation_response = user_creation_view.post(drf_request)
        
        if creation_response.status_code == status.HTTP_201_CREATED:
            user_data = creation_response.data.get("data", {})
            # Récupérer l'utilisateur à partir de CustomUser
            custom_user = get_object_or_404(CustomUser, username=user_data['username'])
            # Récupérer le Client associé
            client = get_object_or_404(Client, customuser_ptr_id=custom_user.id)
            
            # Ajouter l'ID et les informations manquantes à user_data
            user_data.update({
                "id": custom_user.id,  # Ajouter l'ID de CustomUser
                "client_type_display": client.get_client_type_display()
            })
            
            validated_data['user'] = {
                "new_user": {
                    **creation_response.data,
                    "data": user_data  # Mettre à jour les données avec l'ID
                }
            }
        else:
            errors['user'] = "Échec de la création de l'utilisateur."
    
    else:
        errors['user'] = "Informations client invalides."

    # Formater les données validées
    if not errors and 'user' in validated_data:
        formatted_data = ClientResponseSerializer(validated_data['user']).data
        return formatted_data, errors
    else:
        return {}, errors
    
def create_and_associate_passengers(user_id, passengers_data):
    """
    Crée les nouveaux passagers et associe tous les passagers (existants et nouveaux) à un utilisateur.
    Retourne un dictionnaire contenant les données formatées pour les passagers.
    """
    user = get_object_or_404(CustomUser, id=user_id) 
    passenger_ids = []
    display_data = []

    # Associer les passagers existants
    for passenger_id in passengers_data.get('existing', []):
        passenger = get_object_or_404(Passenger, id=passenger_id)
        passenger_ids.append(passenger.id)
        display_data.append({"name": passenger.name, "phone_number": passenger.phone_number})

    # Créer les nouveaux passagers
    for new_passenger in passengers_data.get('new', []):
        passenger = Passenger.objects.create(
            name=new_passenger['name'],
            phone_number=new_passenger['phone_number'],
            client=user.client  
        )
        passenger_ids.append(passenger.id)
        display_data.append({"name": passenger.name, "phone_number": passenger.phone_number})

    # Retourner les données formatées
    return {
        "display_data": display_data,
        "request_data": passenger_ids
    }    

def process_estimate_attributes(estimate_attributes_data):
    """
    Traite les données des estimate_attribute :
    - Vérifie si un enregistrement correspondant existe déjà.
    - Réutilise l'enregistrement existant ou en crée un nouveau.
    - Calcule le coût total des attributs.
    - Retourne les données formatées pour l'affichage.
    """
    total_attributes_cost = 0
    estimate_attribute_ids = []
    display_data = []

    try:
        with transaction.atomic():  
            for attribute_data in estimate_attributes_data:
                attribute = Attribute.objects.get(id=attribute_data['attribute'])

                # Vérifier si un enregistrement correspondant existe déjà
                existing_estimate_attribute = EstimateAttribute.objects.filter(
                    attribute=attribute,
                    quantity=attribute_data['quantity']
                ).first()

                if existing_estimate_attribute:
                    # Réutiliser l'enregistrement existant
                    estimate_attribute = existing_estimate_attribute
                else:
                    # Créer un nouvel enregistrement
                    estimate_attribute = EstimateAttribute.objects.create(
                        attribute=attribute,
                        quantity=attribute_data['quantity']
                    )

                estimate_attribute_ids.append(estimate_attribute.id)
                total_attributes_cost += estimate_attribute.total

                # Ajouter les données pour l'affichage
                display_data.append({
                    "attribute_name": attribute.attribute_name,
                    "unit_price": float(attribute.unit_price),  # Convertir en float pour le serializer
                    "quantity": estimate_attribute.quantity,
                    "total": float(estimate_attribute.total)  # Convertir en float pour le serializer
                })

        return {
            "display_data": display_data,
            "request_data": {
                "ids": estimate_attribute_ids,
                "total_attributes_cost": float(total_attributes_cost)  # Convertir en float pour le serializer
            },
            "total_attributes_cost": float(total_attributes_cost)  # Ajout du total global
        }
    except Exception as e:
        raise Exception(f"Erreur lors du traitement des estimate_attribute : {str(e)}")

def get_selected_tariff(user_choice, estimation_tariff):
    """Retourne le tarif sélectionné par l'utilisateur."""
    if user_choice['is_standard_cost']:
        return estimation_tariff.standard_cost
    else:
        selected_tariff = estimation_tariff.applied_tariffs.get(id=user_choice['selected_tariff'])
        return selected_tariff.calculated_cost
    
def validate_and_apply_promo_code(code_promo, client, estimation_tariff):
    """Valide et applique un code promo. Retourne les informations de réduction si valide, sinon None."""
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
        print(f"Erreur lors de la validation du code promo : {str(e)}")
        return None 

def calculate_final_cost(selected_tariff, promo_code_info, total_attributes_cost):
    """
    Calcule le coût final (total_booking_cost) en appliquant les réductions du code promo,
    en ajoutant total_attributes_cost, et en calculant driver_sale_price et partner_sale_price
    en fonction de compensation et commission.
    """
    # Convertir selected_tariff en Decimal pour éviter les problèmes de type
    final_cost = Decimal(str(selected_tariff))

    # Appliquer la réduction du code promo
    if promo_code_info:
        if promo_code_info['percentage']:
            final_cost *= (Decimal('1') - Decimal(str(promo_code_info['percentage'])) / Decimal('100'))
        if promo_code_info['fixed_amount']:
            final_cost -= Decimal(str(promo_code_info['fixed_amount']))

    # Calculer le coût final en incluant total_attributes_cost
    total_booking_cost = final_cost + Decimal(str(total_attributes_cost))

    # Retourner les valeurs en float pour compatibilité
    return {
        "total_booking_cost": float(max(total_booking_cost, Decimal('0'))),  # Assurer que le coût final n'est pas négatif
        "total_attributes_cost": float(max(total_attributes_cost, Decimal('0'))), 
    }
    
def apply_commission_or_compensation(total_booking_cost, compensation=None, commission=None):
    """
    Applique la commission ou la compensation au total_booking_cost et retourne
    les valeurs de driver_sale_price et partner_sale_price.
    """
    # Convertir total_booking_cost en Decimal pour éviter les problèmes de type
    total_booking_cost = Decimal(str(total_booking_cost))

    # Calculer driver_sale_price et partner_sale_price en fonction de compensation ou commission
    if compensation is not None and compensation > 0:
        # Si compensation est appliquée, on ajoute la compensation au total_booking_cost
        driver_sale_price = total_booking_cost + Decimal(str(compensation))
        partner_sale_price = total_booking_cost + Decimal(str(compensation))
        commission = Decimal('0')  # La commission est nulle si compensation est appliquée
    elif commission is not None and commission > 0:
        # Si commission est appliquée, on déduit la commission du total_booking_cost
        commission_amount = total_booking_cost * (Decimal(str(commission)) / Decimal('100'))
        driver_sale_price = total_booking_cost - commission_amount
        partner_sale_price = total_booking_cost - commission_amount
        compensation = Decimal('0')  # La compensation est nulle si commission est appliquée
    else:
        # Si ni compensation ni commission n'est appliquée
        driver_sale_price = total_booking_cost
        partner_sale_price = total_booking_cost
        compensation = Decimal('0')
        commission = Decimal('0')

    # Retourner les valeurs en float pour compatibilité
    return {
        "driver_sale_price": float(max(driver_sale_price, Decimal('0'))),
        "partner_sale_price": float(max(partner_sale_price, Decimal('0'))),
        "compensation": float(compensation),
        "commission": float(commission)
    }
    
def process_user_choice(user_choice, estimation_tariff, client, total_attributes_cost, code_promo=None, compensation=None, commission=None):
    """
    Traite les choix de l'utilisateur et retourne :
    - Le coût final (total_booking_cost).
    - Une phrasologie expliquant la réduction appliquée (si applicable).
    - Un booléen indiquant si un code promo a été utilisé (is_code_promo_used).
    - L'ID de l'enregistrement UserChoice créé.
    - Les valeurs de driver_sale_price et partner_sale_price.
    """
    selected_tariff = get_selected_tariff(user_choice, estimation_tariff)

    promo_code_info = validate_and_apply_promo_code(code_promo, client, estimation_tariff) if code_promo else None

    # Calculer le coût final en incluant total_attributes_cost
    cost_result = calculate_final_cost(selected_tariff, promo_code_info, total_attributes_cost)

    # Appliquer la commission ou la compensation
    commission_compensation_result = apply_commission_or_compensation(
        cost_result["total_booking_cost"],
        compensation,
        commission
    )

    # Mettre à jour les valeurs de driver_sale_price et partner_sale_price
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

    # Enregistrer le choix de l'utilisateur dans la base de données
    user_choice_instance = UserChoice.objects.create(
        vehicle_id=user_choice['vehicle_id'],
        selected_tariff=AppliedTariff.objects.get(id=user_choice['selected_tariff']) if not user_choice['is_standard_cost'] else None,
        is_standard_cost=user_choice['is_standard_cost']
    )

    return {
        "selected_tariff": selected_tariff,
        "promo_code_info": promo_code_info,
        "total_booking_cost": cost_result["total_booking_cost"],
        "total_attributes_cost": cost_result["total_attributes_cost"],
        "promotion_message": promotion_message,
        "is_code_promo_used": is_code_promo_used,
        "user_choice_id": user_choice_instance.id,  # Ajouter l'ID de l'enregistrement UserChoice
        "driver_sale_price": cost_result["driver_sale_price"],
        "partner_sale_price": cost_result["partner_sale_price"],
        "compensation": cost_result["compensation"],
        "commission": cost_result["commission"]
    }

def process_booking_data(validated_data):
    """
    Orchestre le traitement des données de réservation validées.
    - Valide les informations client.
    - Crée et associe les passagers.
    - Traite les estimate_attributes.
    - Calcule le coût final.
    - Retourne les données formatées pour la réservation.
    """
    errors = {}
    formatted_data = {}

    # 1. Validation des informations client
    client_data = validated_data.get('user')
    if client_data:
        client_info, client_errors = validate_client_info(client_data)
        if client_errors:
            errors['user'] = client_errors
        else:
            formatted_data['user'] = client_info

    # 2. Création et association des passagers
    passengers_data = validated_data.get('passengers')
    if passengers_data and 'user' in formatted_data:
        # Récupérer l'ID de l'utilisateur à partir des données formatées
        user_id = formatted_data['user']['request_data'].get('id')
        if user_id:
            try:
                passengers_response = create_and_associate_passengers(user_id, passengers_data)
                formatted_data['passengers'] = PassengerResponseSerializer(passengers_response).data
            except Exception as e:
                errors['passengers'] = str(e)
        else:
            errors['passengers'] = "L'ID de l'utilisateur est manquant."

    # 3. Traitement des estimate_attributes
    estimate_attributes_data = validated_data.get('estimate_attribute')
    if estimate_attributes_data:
        try:
            attributes_result = process_estimate_attributes(estimate_attributes_data)
            formatted_data['estimate_attribute'] = EstimateAttributeResponseSerializer(attributes_result).data
        except Exception as e:
            errors['estimate_attribute'] = str(e)

    # 4. Calcul du coût final
    user_choice = validated_data.get('user_choice')
    estimation_log_id = validated_data.get('estimation_log')
    total_attributes_cost = formatted_data.get('estimate_attribute', {}).get('request_data', {}).get('total_attributes_cost', 0)
    code_promo = validated_data.get('code_promo')

    # Récupérer compensation et commission depuis validated_data
    compensation = validated_data.get('compensation')
    commission = validated_data.get('commission')

    if user_choice and estimation_log_id:
        try:
            # Récupérer l'instance de EstimationTariff associée à l'estimation_log
            estimation_tariff = get_object_or_404(
                EstimationTariff,
                estimation_log_id=estimation_log_id,
                vehicle_id=user_choice['vehicle_id']
            )

            # Traiter les choix de l'utilisateur en passant compensation et commission
            cost_result = process_user_choice(
                user_choice=user_choice,
                estimation_tariff=estimation_tariff,
                client=formatted_data['user'],
                total_attributes_cost=total_attributes_cost,
                code_promo=code_promo,
                compensation=compensation,  # Passer compensation
                commission=commission  # Passer commission
            )
            formatted_data.update(cost_result)
        except Exception as e:
            errors['cost_calculation'] = str(e)

    return formatted_data, errors

def get_meeting_place_data(meeting_place_id):
    """
    Récupère et formate les informations du lieu de rendez-vous.
    """
    try:
        meeting_place = MeetingPlace.objects.get(id=meeting_place_id)
        return {
            "display_data": meeting_place.address,
            "request_data": meeting_place.id
        }
    except MeetingPlace.DoesNotExist:
        return {
            "display_data": "Lieu de rendez-vous non trouvé",
            "request_data": None
        }
        
def get_payment_method_data(payment_method_id):
    """
    Récupère et formate les informations de la méthode de paiement.
    """
    try:
        payment_method = PaymentMethod.objects.get(id=payment_method_id)
        # Formatage du nom de la méthode de paiement en français
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
    Récupère et formate les informations de l'estimation.
    """
    try:
        estimation_log = EstimationLog.objects.get(id=estimation_log_id)
        return {
            "display_data": {
                "departure": estimation_log.departure,
                "destination": estimation_log.destination,
                "pickup_date": estimation_log.pickup_date.isoformat(),
                "waypoints": estimation_log.waypoints if estimation_log.waypoints else [],
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
        
def format_booking_response(validated_data, formatted_data):
    """
    Formate la réponse finale pour la validation de la réservation.
    """
    response_data = {
        "data": {
            "display_data": {},
            "request_data": {}
        }
    }

    # 1. Ajout des données simples
    simple_fields = [
        'code_promo', 'flight_number', 'message', 
        'number_of_luggages', 'number_of_passengers', 'case_number',
        'compensation', 'commission'
    ]
    for field in simple_fields:
        if field in validated_data:
            response_data["data"]["display_data"][field] = validated_data[field]
            response_data["data"]["request_data"][field] = validated_data[field]

    # 2. Ajout des données complexes (user, passengers, estimate_attribute)
    if 'user' in formatted_data:
        response_data["data"]["display_data"].update(formatted_data['user']['display_data'])
        response_data["data"]["request_data"]["user_id"] = formatted_data['user']['request_data'].get('id')

    if 'passengers' in formatted_data:
        response_data["data"]["display_data"]["passengers"] = formatted_data['passengers']['display_data']
        response_data["data"]["request_data"]["passengers"] = formatted_data['passengers']['request_data'].get('ids')

    if 'estimate_attribute' in formatted_data:
        # Récupérer les données des attributs sans total_attributes_cost
        estimate_attribute_display_data = [
            {
                "attribute_name": attr['attribute_name'],
                "unit_price": attr['unit_price'],
                "quantity": attr['quantity'],
                "total": attr['total']
            }
            for attr in formatted_data['estimate_attribute']['display_data']
            if "total_attributes_cost" not in attr  # Exclure total_attributes_cost
        ]
        
        # Ajouter les données des attributs à display_data
        response_data["data"]["display_data"]["estimate_attribute"] = estimate_attribute_display_data
        response_data["data"]["request_data"]["estimate_attribute"] = formatted_data['estimate_attribute']['request_data'].get('ids')

    # 3. Ajout des informations de coût et du véhicule
    if 'user_choice_id' in formatted_data:
        user_choice = UserChoice.objects.get(id=formatted_data['user_choice_id'])
        vehicle = Vehicle.objects.get(id=user_choice.vehicle_id)

        response_data["data"]["display_data"]["vehicle"] = {
            "brand": vehicle.brand,
            "model": vehicle.model,
            "vehicle_type": vehicle.vehicle_type.name
        }

        response_data["data"]["display_data"].update({
            "total_booking_cost": formatted_data['total_booking_cost'],
            "total_attributes_cost": formatted_data['total_attributes_cost'],
            "promotion_message": formatted_data.get('promotion_message', None),
            "driver_sale_price": formatted_data['driver_sale_price'],
            "partner_sale_price": formatted_data['partner_sale_price']
        })

        response_data["data"]["request_data"].update({
            "user_choice": formatted_data['user_choice_id'],
            "total_booking_cost": formatted_data['total_booking_cost'],
            "total_attributes_cost": formatted_data['total_attributes_cost'],
            "driver_sale_price": formatted_data['driver_sale_price'],
            "partner_sale_price": formatted_data['partner_sale_price']
        })

    # 4. Ajout des informations de meeting_place, payment_method, et estimation_log
    if 'meeting_place' in validated_data:
        meeting_place_data = get_meeting_place_data(validated_data['meeting_place'])
        response_data["data"]["display_data"]["meeting_place"] = meeting_place_data["display_data"]
        response_data["data"]["request_data"]["meeting_place"] = meeting_place_data["request_data"]

    if 'payment_method' in validated_data:
        payment_method_data = get_payment_method_data(validated_data['payment_method'])
        response_data["data"]["display_data"]["payment_method"] = payment_method_data["display_data"]
        response_data["data"]["request_data"]["payment_method"] = payment_method_data["request_data"]

    if 'estimation_log' in validated_data:
        estimation_log_data = get_estimation_log_data(validated_data['estimation_log'])
        response_data["data"]["display_data"]["estimation_log"] = estimation_log_data["display_data"]
        response_data["data"]["request_data"]["estimation_log"] = estimation_log_data["request_data"]

    return response_data

def update_estimation_and_create_estimate(estimation_log_id, user_id, is_code_promo_used, request_data):
    """
    Met à jour l'EstimationLog, gère le code promo, lie le client et crée l'estimation.
    Retourne l'ID de l'estimation créée.
    """
    try:
        # 1. Récupérer l'EstimationLog et l'utilisateur
        estimation_log = get_object_or_404(EstimationLog, id=estimation_log_id)
        user = get_object_or_404(CustomUser, id=user_id)

        # 2. Mettre à jour l'EstimationLog
        estimation_log.user = user
        estimation_log.is_booked = True
        estimation_log.save()

        # 3. Gérer le code promo si applicable
        if is_code_promo_used:
            tariff_rule = estimation_log.tariffs.first().rules.filter(rule_type="promo_code").first()
            if tariff_rule and tariff_rule.promo_code:
                promo_code = tariff_rule.promo_code
                promo_code.usage_count += 1
                promo_code.save()

        # 4. Créer l'estimation
        estimate = create_estimate(request_data)
        return estimate

    except Exception as e:
        raise Exception(f"Erreur lors de la mise à jour de l'estimation et de la création de l'estimation : {str(e)}")
    
def create_estimate(request_data):
    """
    Crée une nouvelle estimation dans la base de données en utilisant les données de request_data.
    Retourne l'ID de l'estimation créée.
    """
    try:
        # Récupérer les objets liés à partir des IDs dans request_data
        estimation_log = get_object_or_404(EstimationLog, id=request_data.get('estimation_log'))
        user_choice = get_object_or_404(UserChoice, id=request_data.get('user_choice'))
        meeting_place = get_object_or_404(MeetingPlace, id=request_data.get('meeting_place'))
        payment_method = get_object_or_404(PaymentMethod, id=request_data.get('payment_method'))

        # Créer l'estimation
        estimate = Estimate.objects.create(
            estimation_log=estimation_log,
            user_choice=user_choice,
            meeting_place=meeting_place,
            payment_method=payment_method,
            flight_number=request_data.get('flight_number'),
            message=request_data.get('message'),
            total_booking_cost=request_data.get('total_booking_cost'),
            total_attributes_cost=request_data.get('total_attributes_cost'),
            number_of_luggages=request_data.get('number_of_luggages'),
            number_of_passengers=request_data.get('number_of_passengers'),
            case_number=request_data.get('case_number')
        )

        # Associer les passagers à l'estimation
        passengers_ids = request_data.get('passengers', [])
        passengers = Passenger.objects.filter(id__in=passengers_ids)
        estimate.passengers.set(passengers)

        # Associer les estimate_attributes à l'estimation
        estimate_attributes_ids = request_data.get('estimate_attribute', [])
        estimate_attributes = EstimateAttribute.objects.filter(id__in=estimate_attributes_ids)
        estimate.estimate_attribute.set(estimate_attributes)

        estimate.save()

        return estimate.id

    except Exception as e:
        raise Exception(f"Erreur lors de la création de l'estimation : {str(e)}")
    

#fonctions create booking 

def create_booking(data):
    """
    Crée une réservation (Booking) à partir des données fournies.
    Retourne l'instance de Booking créée.
    """
    try:
        # 1. Récupérer les objets liés
        estimate = get_object_or_404(Estimate, id=data['estimate'])
        client = get_object_or_404(CustomUser, id=data['client'])

        # 2. Créer la réservation
        booking = Booking.objects.create(
            compensation=data['compensation'],
            commission=data['commission'],
            driver_sale_price=data['driver_sale_price'],
            partner_sale_price=data['partner_sale_price'],
            estimate=estimate,
            client=client.client  # Lier le client (instance de Client)
        )

        return booking

    except Exception as e:
        raise Exception(f"Erreur lors de la création de la réservation : {str(e)}")

def log_booking_action(booking, user_id, action, custom_message=None):
    """
    Enregistre une action dans les logs de réservation (BookingLog).
    Si un message personnalisé est fourni, il est utilisé. Sinon, un message prédéfini est utilisé.
    Si aucun utilisateur n'est fourni (user_id est None), aucun utilisateur n'est enregistré dans le log.
    """
    try:
        # Récupérer l'utilisateur si user_id est fourni
        user = get_object_or_404(CustomUser, id=user_id) if user_id else None

        # Messages prédéfinis pour certaines actions
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

        # Utiliser le message personnalisé s'il est fourni, sinon utiliser un message prédéfini
        message = custom_message if custom_message else predefined_messages.get(action, action)

        # Créer une entrée dans les logs
        booking_log = BookingLog.objects.create(
            booking=booking,
            user=user,  
            action=message
        )
        return booking_log

    except Exception as e:
        raise Exception(f"Erreur lors de l'enregistrement du log de réservation : {str(e)}")

def format_booking_display_data(booking):
    """
    Formate les données d'une réservation (Booking) pour retourner uniquement display_data.
    """
    display_data = {}

    # 1. Ajout des données simples
    simple_fields = [
        'compensation', 'commission', 'driver_sale_price', 'booking_number',
        'partner_sale_price', 'flight_number', 'message', 'created_at', 'case_number'
    ]
    for field in simple_fields:
        value = getattr(booking, field, None)
        if value is not None:
            display_data[field] = value

    # 2. Ajout des données complexes (user, passengers, estimate_attribute)
    if booking.client:
        display_data["user"] = {
            "email": booking.client.email,
            "first_name": booking.client.first_name,
            "last_name": booking.client.last_name,
            "phone_number": booking.client.phone_number,
            "address": booking.client.address,
            "client_type": booking.client.get_client_type_display()  # Ajouter le type de client
        }

    if booking.estimate.passengers.exists():
        passengers_display_data = [
            {"name": passenger.name, "phone_number": passenger.phone_number}
            for passenger in booking.estimate.passengers.all()
        ]
        display_data["passengers"] = passengers_display_data

    if booking.estimate.estimate_attribute.exists():
        estimate_attribute_display_data = [
            {
                "attribute_name": attr.attribute.attribute_name,
                "unit_price": float(attr.attribute.unit_price),
                "quantity": attr.quantity,
                "total": float(attr.total)
            }
            for attr in booking.estimate.estimate_attribute.all()
        ]
        display_data["estimate_attribute"] = estimate_attribute_display_data

    # 3. Ajout des informations de coût et du véhicule
    if booking.estimate.user_choice:
        user_choice = booking.estimate.user_choice
        
        try:
            vehicle = Vehicle.objects.get(id=user_choice.vehicle_id)
            display_data["vehicle"] = {
                "brand": vehicle.brand,
                "model": vehicle.model,
                "vehicle_type": vehicle.vehicle_type.name
            }
        except Vehicle.DoesNotExist:
            display_data["vehicle"] = None  

        display_data.update({
            "number_of_luggages":booking.estimate.number_of_luggages,
            "number_of_passengers":booking.estimate.number_of_passengers,
            "total_booking_cost": booking.estimate.total_booking_cost,
            "total_attributes_cost": booking.estimate.total_attributes_cost,
            "driver_sale_price": booking.driver_sale_price,
            "partner_sale_price": booking.partner_sale_price
        })


    # 4. Calcul du total_trajet et de la TVA
    if booking.estimate.total_booking_cost and booking.estimate.total_attributes_cost:
        display_data["total_trajet"] = booking.estimate.total_booking_cost - booking.estimate.total_attributes_cost
    else:
        display_data["total_trajet"] = 0.0
        
    # 5. Ajout des informations de meeting_place, payment_method, et estimation_log
    if booking.estimate.meeting_place:
        meeting_place_data = get_meeting_place_data(booking.estimate.meeting_place.id)
        display_data["meeting_place"] = meeting_place_data["display_data"]

    if booking.estimate.payment_method:
        payment_method_data = get_payment_method_data(booking.estimate.payment_method.id)
        display_data["payment_method"] = payment_method_data["display_data"]

    if booking.estimate.estimation_log:
        estimation_log_data = get_estimation_log_data(booking.estimate.estimation_log.id)
        display_data["estimation_log"] = estimation_log_data["display_data"]

    return display_data 



def get_booking_email_context_and_send_emails(booking_id, display_data):
    """
    Génère le contexte pour les e-mails de réservation et envoie les e-mails avec un lien de téléchargement.
    
    :param display_data: Les données formatées de la réservation.
    """
    # Récupérer les informations de l'entreprise
    business_info = get_business_info()

    # Récupérer l'e-mail du manager
    business = Business.objects.filter(business_type="my_business").first()
    if business and business.main_user and business.main_user.role == "manager":
        manager_email = business.main_user.email
    else:
        raise Exception("Aucun manager trouvé pour cette entreprise.")

    # Récupérer l'e-mail du client depuis display_data
    client_email = display_data["user"]["email"]

    # Construire le contexte pour le client
    client_context = {
        "recipient_name": display_data["user"]["first_name"],
        "reservation_details": display_data,
        "business_info": business_info,
    }

    # Construire le contexte pour le manager
    manager_context = {
        "reservation_details": display_data,
        "business_info": business_info,
    }

    # Générer l'URL de téléchargement du PDF
    booking_id = booking_id
    pdf_url = f"{business_info['operator_url']}/api/reservations/booking/{booking_id}/pdf/"

    # Ajouter l'URL du PDF au contexte des e-mails
    client_context["pdf_url"] = pdf_url
    manager_context["pdf_url"] = pdf_url

    # Charger les templates HTML pour les e-mails
    client_html_content = render_to_string("fichiers_mails/email_booking_booked_client.html", client_context)
    manager_html_content = render_to_string("fichiers_mails/email_booking_booked_admin.html", manager_context)

    # Définir les sujets des e-mails
    client_subject = "Votre réservation est confirmée"
    manager_subject = "Notification de nouvelle réservation"

    # Envoyer les e-mails avec le lien de téléchargement
    try:
        send_email(
            client_email,
            client_subject,
            client_html_content,
        )
        send_email(
            manager_email,
            manager_subject,
            manager_html_content,
        )
    except Exception as e:
        print(f"Erreur lors de l'envoi des e-mails : {e}")
        raise
    

def get_business_info_for_pdf():
    """
    Récupère les informations de l'entreprise pour les fichiers PDF.
    Ajuste le logo pour qu'il soit utilisable dans un PDF (URL absolue).
    """
    # Valeurs par défaut
    default_business_info = {
        "name": "Votre Entreprise",
        "email": "support@votreentreprise.com",
        "phone_number": "+1234567890",
        "address": "123 Rue de l'Entreprise, Ville, Pays",
        "logo_url": None,  
        "operator_url": "http://127.0.0.1:8000",
    }

    # Récupère l'entreprise de type "my_business"
    business = Business.objects.filter(business_type="my_business").first()
    operator_url = Urls.objects.first()

    # Récupère les informations de l'entreprise ou utilise les valeurs par défaut
    business_info = {
        "name": business.name if business else default_business_info["name"],
        "email": business.email if business else default_business_info["email"],
        "phone_number": business.phone_number if business else default_business_info["phone_number"],
        "address": business.address if business else default_business_info["address"],
        "operator_url": operator_url.operator_url if operator_url else default_business_info["operator_url"],
    }

    # Gestion du logo
    if business and business.logo:
        # Génère une URL absolue pour le logo
        logo_url = urljoin(settings.BASE_URL, business.logo.url)  # Utilisez BASE_URL pour l'URL absolue
        business_info["logo_url"] = logo_url
    else:
        business_info["logo_url"] = default_business_info["logo_url"]

    return business_info