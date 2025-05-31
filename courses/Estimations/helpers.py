from rest_framework.response import Response
from rest_framework import status
import googlemaps
from rest_framework.exceptions import APIException
from django.utils.dateparse import parse_datetime
from math import radians, sin, cos, sqrt, atan2
from decimal import Decimal, ROUND_HALF_UP

from configurations.models import TariffRule
from courses.models import AppliedTariff, EstimationLog, EstimationTariff
from parametrages.models import VAT


def create_response(
    status_type, message, data=None, http_status=status.HTTP_200_OK, error=None
):
    response_payload = {
        "status": status_type,
        "message": message,
        "data": data if data else {},
        "http_status": http_status,
    }
    if error:
        response_payload["error"] = str(error)

    return Response(response_payload, status=http_status)


def check_element_status(element, origin, destination):
    """
    Vérifie le statut de l'élément dans la réponse Google Maps.
    """
    if element["status"] != "OK":
        raise ValueError(
            f"Erreur: {element['status']} entre {origin} et {destination}."
        )


def calculate_distances_and_durations(
    api_key, departure, destination, origin=None, waypoints=None
):
    try:
        gmaps = googlemaps.Client(key=api_key)

        # 1) Géocodage des points
        departure_geo = gmaps.geocode(departure)
        if not departure_geo:
            raise ValueError(
                f"Impossible de géocoder l'adresse de départ : {departure}"
            )
        dep_coords = departure_geo[0]["geometry"]["location"]

        destination_geo = gmaps.geocode(destination)
        if not destination_geo:
            raise ValueError(f"Impossible de géocoder la destination : {destination}")
        dest_coords = destination_geo[0]["geometry"]["location"]

        origin_coords = None
        if origin:
            origin_geo = gmaps.geocode(origin)
            if not origin_geo:
                raise ValueError(f"Impossible de géocoder l'origin (base) : {origin}")
            origin_coords = origin_geo[0]["geometry"]["location"]

        wpts_coords = []
        if waypoints:
            for wpt in waypoints:
                wpt_geo = gmaps.geocode(wpt)
                if not wpt_geo:
                    raise ValueError(f"Impossible de géocoder le waypoint : {wpt}")
                wpt_coord = wpt_geo[0]["geometry"]["location"]
                wpts_coords.append(wpt_coord)

        # 2) Initialiser la structure de résultat
        results = {
            "coords": {
                "origin": origin_coords,
                "departure": dep_coords,
                "destination": dest_coords,
                "waypoints": wpts_coords,
            },
            "dist_base_km": 0,
            "dist_parcourt_km": 0,
            "dist_retour_km": 0,
            "dur_parcourt_minutes": 0,
            "segments": [],
        }

        # 3) Calculer la distance entre la base et le départ
        if origin:
            base_to_depart_result = gmaps.distance_matrix(
                origin, departure, mode="driving", units="metric"
            )
            base_to_depart_element = base_to_depart_result["rows"][0]["elements"][0]
            check_element_status(base_to_depart_element, origin, departure)

            results["dist_base_km"] = round(
                base_to_depart_element["distance"]["value"] / 1000, 3
            )
            results["segments"].append(
                {
                    "from": origin,
                    "to": departure,
                    "distance_km": results["dist_base_km"],
                    "duration_minutes": round(
                        base_to_depart_element["duration"]["value"] / 60, 3
                    ),
                }
            )

        # 4) Parcours principal : Départ → Waypoints → Destination
        previous_point = departure
        parcours_distance_km = 0
        parcours_duration_minutes = 0

        route_points = (waypoints or []) + [destination]
        for point in route_points:
            segment_result = gmaps.distance_matrix(
                previous_point, point, mode="driving", units="metric"
            )
            segment_element = segment_result["rows"][0]["elements"][0]
            check_element_status(segment_element, previous_point, point)

            distance_km = round(segment_element["distance"]["value"] / 1000, 3)
            duration_minutes = round(segment_element["duration"]["value"] / 60, 3)
            parcours_distance_km += distance_km
            parcours_duration_minutes += duration_minutes

            results["segments"].append(
                {
                    "from": previous_point,
                    "to": point,
                    "distance_km": distance_km,
                    "duration_minutes": duration_minutes,
                }
            )

            previous_point = point

        results["dist_parcourt_km"] = round(parcours_distance_km, 3)
        results["dur_parcourt_minutes"] = round(parcours_duration_minutes, 3)

        # 5) Calculer la distance entre la destination et la base
        if origin:
            dest_to_base_result = gmaps.distance_matrix(
                destination, origin, mode="driving", units="metric"
            )
            dest_to_base_element = dest_to_base_result["rows"][0]["elements"][0]
            check_element_status(dest_to_base_element, destination, origin)

            results["dist_retour_km"] = round(
                dest_to_base_element["distance"]["value"] / 1000, 3
            )
            results["segments"].append(
                {
                    "from": destination,
                    "to": origin,
                    "distance_km": results["dist_retour_km"],
                    "duration_minutes": round(
                        dest_to_base_element["duration"]["value"] / 60, 3
                    ),
                }
            )

        return results

    except Exception as e:
        raise APIException(f"Erreur lors du calcul des distances et durées : {str(e)}")

def calculate_vehicle_costs(vehicles, distances_and_durations, estimate_type):
    """
    Calcule les coûts de transport pour une liste de véhicules, avec arrondi à 3 décimales.
    Traitement spécial pour les véhicules on_demand.
    """
    results = []
    dist_base_km = float(distances_and_durations["dist_base_km"])
    dist_parcourt_km = float(distances_and_durations["dist_parcourt_km"])
    dist_retour_km = float(distances_and_durations["dist_retour_km"])
    dur_parcourt_minutes = float(distances_and_durations["dur_parcourt_minutes"])

    try:
        vat = VAT.objects.get(name=estimate_type)
        vat_rate = float(vat.rate) / 100
    except VAT.DoesNotExist:
        vat_rate = 0.10

    for vehicle in vehicles:
        try:
            # NOUVEAU: Traitement spécial pour les véhicules on_demand
            if vehicle.availability_type == 'on_demand':
                results.append({
                    "vehicle_id": vehicle.id,
                    "vehicle_name": f"{vehicle.brand} {vehicle.model}",
                    "coutBrute": 0.0,
                    "tva": 0.0,
                    "total_cost": 0.0,
                })
                continue  # Passer au véhicule suivant sans calculer le coût
            
            # Logique existante pour les autres types de véhicules
            price = vehicle.price
            if not price:
                raise ValueError(
                    f"Aucun tarif disponible pour le véhicule {vehicle.id}."
                )

            frais_reservation = float(price.booking_fee)
            frais_livraison = float(price.delivery_fee)
            prix_par_km = float(price.price_per_km)
            prix_par_duree = float(price.price_per_duration) / 60
            frais_par_defaut = float(price.default_fee)

            calcul = (
                frais_reservation
                + (frais_livraison * dist_base_km)
                + (prix_par_km * dist_parcourt_km)
                + (frais_livraison * dist_retour_km)
                + (prix_par_duree * dur_parcourt_minutes)
            )

            calcul_tva = float(Decimal(str(calcul * vat_rate)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
            total_cost = float(Decimal(str(calcul + calcul_tva)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
            cout_brute = float(Decimal(str(calcul)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

            if total_cost < frais_par_defaut:
                total_cost = float(Decimal(str(frais_par_defaut)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

            results.append(
                {
                    "vehicle_id": vehicle.id,
                    "vehicle_name": f"{vehicle.brand} {vehicle.model}",
                    "coutBrute": cout_brute,
                    "tva": calcul_tva,
                    "total_cost": total_cost,
                }
            )

        except ValueError as e:
            print(f"Erreur pour le véhicule {vehicle.id}: {e}")

    return results

def filter_and_group_vehicles(vehicles, departure_location, api_key, pickup_date):
    """
    Filtre les véhicules validés et retourne SEULEMENT ceux de la base la plus proche.
    """
    gmaps = googlemaps.Client(key=api_key)
    grouped_vehicles = {}
    base_distances = {}

    # 1. Grouper les véhicules par base_location
    for vehicle in vehicles:
        if not vehicle.base_location:
            raise ValueError(
                f"Le véhicule {vehicle.id} n'a pas de base_location définie."
            )
        if vehicle.base_location not in grouped_vehicles:
            grouped_vehicles[vehicle.base_location] = []
        grouped_vehicles[vehicle.base_location].append(vehicle)

    # 2. Calculer la distance de chaque base vers le départ
    for base, base_vehicles in grouped_vehicles.items():
        distance_result = gmaps.distance_matrix(
            base, departure_location, mode="driving", units="metric"
        )
        element = distance_result["rows"][0]["elements"][0]
        check_element_status(element, base, departure_location)

        distance_km = element["distance"]["value"] / 1000
        base_distances[base] = distance_km

    # 3. Trouver la base la plus proche
    closest_base = min(base_distances.keys(), key=lambda x: base_distances[x])
    closest_distance = base_distances[closest_base]

    # 4. Retourner SEULEMENT les véhicules de la base la plus proche
    vehicle_availability = []
    closest_base_vehicles = grouped_vehicles[closest_base]
    
    for vehicle in closest_base_vehicles:
        vehicle_availability.append(
            {
                "vehicle_id": vehicle.id,
                "availability_type": vehicle.availability_type,
                "availability_time": vehicle.availability_time,
                "base_location": closest_base,
                "distance_to_departure": closest_distance,  # Info supplémentaire
            }
        )

    return vehicle_availability

def is_within_hours(start_str, end_str, current_str):
    """
    Vérifie si une heure donnée est dans une plage horaire, même si elle enjambe minuit.
    """
    def to_minutes(hm):
        h, m = map(int, hm.split(":"))
        return h * 60 + m

    start_min = to_minutes(start_str)
    end_min = to_minutes(end_str)
    cur_min = to_minutes(current_str)

    if start_min < end_min:
        return start_min <= cur_min <= end_min
    else:
        return (cur_min >= start_min) or (cur_min <= end_min)


def filter_and_structure_rules(
    vehicle, pickup_date, departure_coords=None, destination_coords=None
):
    """
    Filtre et structure les règles tarifaires applicables, en excluant les promo_code.
    Inclut les IDs des specific_clients pour les règles avec available_to_all=False.
    NOUVEAU: Retourne une liste vide pour les véhicules on_demand.
    """
    # NOUVEAU: Pas de règles pour les véhicules on_demand
    if vehicle.availability_type == 'on_demand':
        return []
    
    if isinstance(pickup_date, str):
        pickup_dt = parse_datetime(pickup_date)
        if not pickup_dt:
            return []
    else:
        pickup_dt = pickup_date

    rules = vehicle.tariff_rules.filter(rule_type__in=["adjustment", "package"])
    if not rules.exists():
        return []

    valid_rules = []

    for rule in rules:
        if not rule.active:
            continue

        if rule.start_date and pickup_dt < rule.start_date:
            continue
        if rule.end_date and pickup_dt > rule.end_date:
            continue

        if rule.days_of_week:
            current_day = pickup_dt.strftime("%A").lower()
            valid_days = [d.lower() for d in rule.days_of_week]
            if current_day not in valid_days:
                continue

        if rule.specific_hours:
            pickup_time_str = pickup_dt.strftime("%H:%M")
            found_slot = False
            for time_range in rule.specific_hours:
                start = time_range.get("start")
                end = time_range.get("end")
                if is_within_hours(start, end, pickup_time_str):
                    found_slot = True
                    break
            if not found_slot:
                continue

        if rule.application_date and pickup_dt.date() != rule.application_date:
            continue

        if rule.rule_type == "package" and rule.package:
            p = rule.package
            if p.package_type == "classic":
                if (
                    p.departure_latitude is None
                    or p.departure_longitude is None
                    or p.arrival_latitude is None
                    or p.arrival_longitude is None
                ):
                    continue
                if (
                    abs(float(p.departure_latitude) - departure_coords[0]) > 0.0001
                    or abs(float(p.departure_longitude) - departure_coords[1]) > 0.0001
                ):
                    continue
                if (
                    abs(float(p.arrival_latitude) - destination_coords[0]) > 0.0001
                    or abs(float(p.arrival_longitude) - destination_coords[1]) > 0.0001
                ):
                    continue
            elif p.package_type == "radius":
                if (
                    p.departure_latitude is None
                    or p.departure_longitude is None
                    or p.center_latitude is None
                    or p.center_longitude is None
                    or p.radius_km is None
                ):
                    continue
                if (
                    abs(float(p.departure_latitude) - departure_coords[0]) > 0.0001
                    or abs(float(p.departure_longitude) - departure_coords[1]) > 0.0001
                ):
                    continue
                dest_lat = radians(destination_coords[0])
                dest_lon = radians(destination_coords[1])
                center_lat = radians(float(p.center_latitude))
                center_lon = radians(float(p.center_longitude))
                dlon = dest_lon - center_lon
                dlat = dest_lat - center_lat
                a = (
                    sin(dlat / 2) ** 2
                    + cos(center_lat) * cos(dest_lat) * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                R = 6371.0
                distance = R * c
                if distance > float(p.radius_km):
                    continue

        valid_rules.append(
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "rule_type": rule.rule_type,
                "action_type": rule.action_type,
                "priority": rule.priority,
                "available_to_all": rule.available_to_all,
                "specific_clients": [c.id for c in rule.specific_clients.all()],
                "adjustment": (
                    {
                        "adjustment_type": rule.adjustment.adjustment_type,
                        "percentage": rule.adjustment.percentage,
                        "fixed_value": rule.adjustment.fixed_value,
                    }
                    if rule.rule_type == "adjustment" and rule.adjustment
                    else None
                ),
                "package": (
                    {
                        "package_type": p.package_type,
                        "price": float(p.price),
                    }
                    if rule.rule_type == "package" and p
                    else None
                ),
            }
        )

    valid_rules.sort(key=lambda x: x["priority"], reverse=True)
    return valid_rules

def apply_rule_overrides(valid_rules):
    """
    Applique la logique d'écrasement des règles non-promo.
    """
    if not valid_rules:
        return []

    sorted_rules = sorted(valid_rules, key=lambda r: r["priority"], reverse=True)
    from collections import OrderedDict

    grouped_by_priority = OrderedDict()
    for rule in sorted_rules:
        prio = rule["priority"]
        if prio not in grouped_by_priority:
            grouped_by_priority[prio] = []
        grouped_by_priority[prio].append(rule)

    final_rules = []
    for priority_level, rules_at_this_priority in grouped_by_priority.items():
        final_rules.extend(rules_at_this_priority)
        if any(r["available_to_all"] for r in rules_at_this_priority):
            break

    return final_rules


def apply_adjustment(total_cost, adjustment_data):
    """
    Applique une réduction ou une majoration à un coût total, avec arrondi à 3 décimales.
    """
    total_cost = Decimal(total_cost)

    if adjustment_data["adjustment_type"] == "discount":
        if adjustment_data["percentage"]:
            adjustment_value = total_cost * (Decimal(adjustment_data["percentage"]) / 100)
        elif adjustment_data["fixed_value"]:
            adjustment_value = Decimal(adjustment_data["fixed_value"])
        else:
            adjustment_value = Decimal(0)
        result = max(total_cost - adjustment_value, Decimal(0))
        return float(result.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

    elif adjustment_data["adjustment_type"] == "increase":
        if adjustment_data["percentage"]:
            adjustment_value = total_cost * (Decimal(adjustment_data["percentage"]) / 100)
        elif adjustment_data["fixed_value"]:
            adjustment_value = Decimal(adjustment_data["fixed_value"])
        else:
            adjustment_value = Decimal(0)
        result = total_cost + adjustment_value
        return float(result.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

    return float(total_cost.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))


def apply_package(package_data):
    """
    Retourne le prix d'un forfait, avec arrondi à 3 décimales.
    """
    return float(Decimal(str(package_data["price"])).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))


def apply_rules_to_vehicle(standard_cost, final_rules):
    """
    Applique les règles pertinentes à un véhicule, avec arrondi à 3 décimales.
    """
    applied_rules = []

    for rule in final_rules:
        total_cost = standard_cost["total_cost"]

        if rule["rule_type"] == "package" and rule["package"]:
            total_cost = apply_package(rule["package"])
        elif rule["rule_type"] == "adjustment" and rule["adjustment"]:
            total_cost = apply_adjustment(total_cost, rule["adjustment"])

        applied_rules.append({
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "rule_description": rule["description"],
            "rule_type": rule["rule_type"],
            "calculated_cost": total_cost,
            "available_to_all": rule["available_to_all"],
            "specific_clients": rule["specific_clients"],
        })

    return applied_rules


def collect_vehicle_pricing_info(
    vehicles,
    distances_and_durations,
    pickup_date,
    departure_coords=None,
    destination_coords=None,
    estimate_type="simple_transfer",
):
    """
    Collecte les informations tarifaires pour chaque véhicule, avec une structure pricing.
    """
    standard_costs = calculate_vehicle_costs(vehicles, distances_and_durations, estimate_type)
    results = []

    for vehicle in vehicles:
        cost_data = next(
            (c for c in standard_costs if c["vehicle_id"] == vehicle.id), None
        )
        if not cost_data:
            cost_data = {
                "vehicle_id": vehicle.id,
                "vehicle_name": f"{vehicle.brand} {vehicle.model}",
                "coutBrute": 0,
                "tva": 0,
                "total_cost": 0,
            }

        valid_rules = filter_and_structure_rules(
            vehicle=vehicle,
            pickup_date=pickup_date,
            departure_coords=departure_coords,
            destination_coords=destination_coords,
        )

        final_rules = apply_rule_overrides(valid_rules)
        applied_rules = apply_rules_to_vehicle(cost_data, final_rules)

        results.append(
            {
                "vehicle_id": vehicle.id,
                "pricing": {
                    "standard_cost": cost_data,
                    "applied_rules": applied_rules,
                },
            }
        )

    return results


def build_response_data(trip_data, distances_and_durations, vehicle_pricing_list, vehicle_availability_map, vehicles_queryset, user=None):
    """
    Construit les données de réponse avec une structure pricing et sans filtrage par utilisateur.
    """
    trip_informations = {
        "pickup_date": trip_data["pickup_date"],
        "departure_address": trip_data["departure_location"],
        "destination_address": trip_data["destination_location"],
        "waypoints": trip_data.get("destinationInputs", []),
    }

    distances_and_durations_data = {
        "dist_parcourt_km": distances_and_durations["dist_parcourt_km"],
        "dur_parcourt_minutes": distances_and_durations["dur_parcourt_minutes"],
    }

    vehicles_informations = []
    vehicle_dict = {v.id: v for v in vehicles_queryset}

    for vehicle_pricing in vehicle_pricing_list:
        vehicle_id = vehicle_pricing["vehicle_id"]
        pricing = vehicle_pricing["pricing"]
        availability = vehicle_availability_map.get(vehicle_id, {
            "availability_type": "unknown",
            "availability_time": None,
        })
        vehicle = vehicle_dict.get(vehicle_id)

        vehicles_informations.append({
            "id": vehicle_id,
            "availability_type": availability["availability_type"],
            "availability_time": availability["availability_time"],
            "passenger_capacity": vehicle.passenger_capacity if vehicle else None,
            "luggage_capacity": vehicle.luggage_capacity if vehicle else None,
            "vehicle_type": vehicle.vehicle_type.name if vehicle and vehicle.vehicle_type else None,
            "vehicle_name": f"{vehicle.brand} {vehicle.model}" if vehicle else None,
            "image": vehicle.image.url if vehicle and vehicle.image else None,
            "pricing": pricing,
        })

    user_informations = []
    if user:
        user_informations = {
            "id": user.id,
            "type_utilisateur": user.user_type,
        }

    response_data = {
        "trip_informations": trip_informations,
        "distances_and_durations": distances_and_durations_data,
        "vehicles_informations": vehicles_informations,
        "user_informations": user_informations,
        "estimation_data": {},  # Rempli par create_estimation_log_and_tariffs
    }

    return response_data


def create_estimation_log_and_tariffs(response_data, user=None):
    """
    Crée un EstimationLog et les EstimationTariff associés.
    """
    try:
        trip_informations = response_data["trip_informations"]
        distances_and_durations = response_data["distances_and_durations"]
        vehicles_informations = response_data["vehicles_informations"]

        estimation_log = EstimationLog.objects.create(
            departure=trip_informations["departure_address"],
            destination=trip_informations["destination_address"],
            pickup_date=trip_informations["pickup_date"],
            waypoints=trip_informations.get("waypoints", []),
            estimate_type="simple_transfer",
            user=user,
            distance_travelled=distances_and_durations["dist_parcourt_km"],
            duration_travelled=str(distances_and_durations["dur_parcourt_minutes"]),
        )

        estimation_tariff_ids = []
        for vehicle_info in vehicles_informations:
            vehicle_id = vehicle_info["id"]
            pricing = vehicle_info["pricing"]
            standard_cost = pricing["standard_cost"]["total_cost"]
            applied_rules = pricing["applied_rules"]

            estimation_tariff = EstimationTariff.objects.create(
                estimation_log=estimation_log,
                vehicle_id=vehicle_id,
                standard_cost=standard_cost,
            )
            estimation_tariff_ids.append(estimation_tariff.id)

            for applied_rule in applied_rules:
                applied_tariff_instance = AppliedTariff.objects.create(
                    rule_id=applied_rule["rule_id"],
                    calculated_cost=applied_rule["calculated_cost"],
                )
                estimation_tariff.applied_tariffs.add(applied_tariff_instance)

            for rule in applied_rules:
                rule_id = rule["rule_id"]
                try:
                    tariff_rule = TariffRule.objects.get(id=rule_id)
                    estimation_tariff.rules.add(tariff_rule)
                except TariffRule.DoesNotExist:
                    print(f"La règle tarifaire avec l'ID {rule_id} n'existe pas.")

        return {
            "estimation_log_id": estimation_log.id,
            "estimation_tariff_ids": estimation_tariff_ids,
        }

    except Exception as e:
        raise APIException(f"Erreur lors de la création de l'EstimationLog et des tarifs : {str(e)}")