from rest_framework.response import Response
from rest_framework import status
import googlemaps
from rest_framework.exceptions import APIException
from django.utils.dateparse import parse_datetime
from math import radians, sin, cos, sqrt, atan2
from decimal import Decimal, ROUND_HALF_UP
from collections import OrderedDict
from configurations.models import TariffRule, Vehicle
from courses.models import AppliedTariff, EstimationLog, EstimationTariff
from parametrages.models import VAT
import logging

logger = logging.getLogger(__name__)

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

def handle_google_maps_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except googlemaps.exceptions.ApiError as e:
            raise APIException(f"Erreur API Google Maps : {str(e)}")
        except ValueError as e:
            raise APIException(str(e))
        except Exception as e:
            raise APIException(f"Erreur inattendue : {str(e)}")
    return wrapper

def geocode_location(gmaps, location):
    geo = gmaps.geocode(location)
    if not geo:
        raise ValueError(f"Impossible de géocoder l'adresse : {location}")
    return geo[0]["geometry"]["location"]

@handle_google_maps_errors
def calculate_distances_and_durations(api_key, departure, destination, origin=None, waypoints=None):
    gmaps = googlemaps.Client(key=api_key)
    locations = [departure, destination] + (waypoints or []) + ([origin] if origin else [])
    geo_results = [geocode_location(gmaps, loc) for loc in locations]
    
    coords = {
        "departure": geo_results[0],
        "destination": geo_results[1],
        "waypoints": geo_results[2:2 + len(waypoints or [])],
        "origin": geo_results[-1] if origin else None,
    }

    results = {
        "coords": coords,
        "dist_base_km": 0,
        "dist_parcourt_km": 0,
        "dist_retour_km": 0,
        "dur_parcourt_minutes": 0,
        "segments": [],
    }

    if origin:
        base_to_depart = gmaps.distance_matrix(origin, departure, mode="driving", units="metric")
        element = base_to_depart["rows"][0]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Erreur: {element['status']} entre {origin} et {departure}")
        results["dist_base_km"] = round(element["distance"]["value"] / 1000, 3)
        results["segments"].append({
            "from": origin,
            "to": departure,
            "distance_km": results["dist_base_km"],
            "duration_minutes": round(element["duration"]["value"] / 60, 3),
        })

    previous_point = departure
    parcours_distance_km = 0
    parcours_duration_minutes = 0
    route_points = (waypoints or []) + [destination]
    
    for point in route_points:
        segment = gmaps.distance_matrix(previous_point, point, mode="driving", units="metric")
        element = segment["rows"][0]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Erreur: {element['status']} entre {previous_point} et {point}")
        distance_km = round(element["distance"]["value"] / 1000, 3)
        duration_minutes = round(element["duration"]["value"] / 60, 3)
        parcours_distance_km += distance_km
        parcours_duration_minutes += duration_minutes
        results["segments"].append({
            "from": previous_point,
            "to": point,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
        })
        previous_point = point

    results["dist_parcourt_km"] = round(parcours_distance_km, 3)
    results["dur_parcourt_minutes"] = round(parcours_duration_minutes, 3)

    if origin:
        dest_to_base = gmaps.distance_matrix(destination, origin, mode="driving", units="metric")
        element = dest_to_base["rows"][0]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Erreur: {element['status']} entre {destination} et {origin}")
        results["dist_retour_km"] = round(element["distance"]["value"] / 1000, 3)
        results["segments"].append({
            "from": destination,
            "to": origin,
            "distance_km": results["dist_retour_km"],
            "duration_minutes": round(element["duration"]["value"] / 60, 3),
        })

    return results

@handle_google_maps_errors
def filter_and_group_vehicles(vehicles, departure_location, api_key, pickup_date):
    gmaps = googlemaps.Client(key=api_key)
    grouped_vehicles = {}
    base_distances = {}

    for vehicle in vehicles:
        if not vehicle.base_location:
            raise ValueError(f"Le véhicule {vehicle.id} n'a pas de base_location définie.")
        if vehicle.base_location not in grouped_vehicles:
            grouped_vehicles[vehicle.base_location] = []
        grouped_vehicles[vehicle.base_location].append(vehicle)

    bases = list(grouped_vehicles.keys())
    distance_results = gmaps.distance_matrix(bases, [departure_location], mode="driving", units="metric")
    
    for idx, base in enumerate(bases):
        element = distance_results["rows"][idx]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Erreur: {element['status']} entre {base} et {departure_location}")
        base_distances[base] = element["distance"]["value"] / 1000

    closest_base = min(base_distances.keys(), key=lambda x: base_distances[x])
    closest_distance = base_distances[closest_base]
    vehicle_availability = [
        {
            "vehicle_id": vehicle.id,
            "availability_type": vehicle.availability_type,
            "availability_time": vehicle.availability_time,
            "base_location": closest_base,
            "distance_to_departure": closest_distance,
        }
        for vehicle in grouped_vehicles[closest_base]
    ]

    return vehicle_availability

def is_within_hours(start_str, end_str, current_str):
    def to_minutes(hm):
        h, m = map(int, hm.split(":"))
        return h * 60 + m

    start_min = to_minutes(start_str)
    end_min = to_minutes(end_str)
    cur_min = to_minutes(current_str)

    if start_min < end_min:
        return start_min <= cur_min <= end_min
    else:
        return cur_min >= start_min or cur_min <= end_min

def filter_and_structure_rules(vehicle, pickup_date, departure_coords=None, destination_coords=None):
    if vehicle.availability_type == 'on_demand':
        return []

    pickup_dt = parse_datetime(pickup_date) if isinstance(pickup_date, str) else pickup_date
    if not pickup_dt:
        return []

    rules = vehicle.tariff_rules.filter(rule_type__in=["adjustment", "package"])
    valid_rules = []

    for rule in rules:
        if not rule.active or (rule.start_date and pickup_dt < rule.start_date) or (rule.end_date and pickup_dt > rule.end_date):
            continue

        if rule.days_of_week and pickup_dt.strftime("%A").lower() not in [d.lower() for d in rule.days_of_week]:
            continue

        if rule.specific_hours:
            pickup_time_str = pickup_dt.strftime("%H:%M")
            if not any(is_within_hours(time_range["start"], time_range["end"], pickup_time_str) for time_range in rule.specific_hours):
                continue

        if rule.application_date and pickup_dt.date() != rule.application_date:
            continue

        if rule.rule_type == "package" and rule.package:
            p = rule.package
            if p.package_type == "classic":
                if (p.departure_latitude is None or p.departure_longitude is None or
                    p.arrival_latitude is None or p.arrival_longitude is None or
                    abs(float(p.departure_latitude) - departure_coords[0]) > 0.0001 or
                    abs(float(p.departure_longitude) - departure_coords[1]) > 0.0001 or
                    abs(float(p.arrival_latitude) - destination_coords[0]) > 0.0001 or
                    abs(float(p.arrival_longitude) - destination_coords[1]) > 0.0001):
                    continue
            elif p.package_type == "radius":
                if (p.departure_latitude is None or p.departure_longitude is None or
                    p.center_latitude is None or p.center_longitude is None or p.radius_km is None or
                    abs(float(p.departure_latitude) - departure_coords[0]) > 0.0001 or
                    abs(float(p.departure_longitude) - departure_coords[1]) > 0.0001):
                    continue
                dest_lat, dest_lon = radians(destination_coords[0]), radians(destination_coords[1])
                center_lat, center_lon = radians(float(p.center_latitude)), radians(float(p.center_longitude))
                dlon, dlat = dest_lon - center_lon, dest_lat - center_lat
                a = sin(dlat / 2) ** 2 + cos(center_lat) * cos(dest_lat) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                if 6371.0 * c > float(p.radius_km):
                    continue

        valid_rules.append({
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "action_type": rule.action_type,
            "priority": rule.priority,
            "available_to_all": rule.available_to_all,
            "specific_clients": [c.id for c in rule.specific_clients.all()],
            "excluded_clients": [c.id for c in rule.excluded_clients.all()],
            "adjustment": (
                {
                    "adjustment_type": rule.adjustment.adjustment_type,
                    "percentage": rule.adjustment.percentage,
                    "fixed_value": rule.adjustment.fixed_value,
                } if rule.rule_type == "adjustment" and rule.adjustment else None
            ),
            "package": (
                {
                    "package_type": p.package_type,
                    "price": float(p.price),
                } if rule.rule_type == "package" and p else None
            ),
        })

    return sorted(valid_rules, key=lambda x: x["priority"], reverse=True)

def apply_rule_overrides(valid_rules):
    if not valid_rules:
        return []

    grouped_by_priority = OrderedDict()
    for rule in sorted(valid_rules, key=lambda r: r["priority"], reverse=True):
        prio = rule["priority"]
        grouped_by_priority.setdefault(prio, []).append(rule)

    final_rules = []
    for rules_at_priority in grouped_by_priority.values():
        final_rules.extend(rules_at_priority)
        if any(r["available_to_all"] for r in rules_at_priority):
            break

    return final_rules


def apply_adjustment(total_cost, adjustment_data):
    total_cost = Decimal(total_cost)
    if adjustment_data["adjustment_type"] == "discount":
        adjustment_value = (total_cost * Decimal(adjustment_data["percentage"]) / 100 if adjustment_data["percentage"]
                           else Decimal(adjustment_data["fixed_value"] or 0))
        result = max(total_cost - adjustment_value, Decimal(0))
    elif adjustment_data["adjustment_type"] == "increase":
        adjustment_value = (total_cost * Decimal(adjustment_data["percentage"]) / 100 if adjustment_data["percentage"]
                           else Decimal(adjustment_data["fixed_value"] or 0))
        result = total_cost + adjustment_value
    else:
        result = total_cost
    # Changement ici : utiliser 2 décimales au lieu de 3
    return float(result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def apply_package(package_data):
    # Changement ici : utiliser 2 décimales au lieu de 3
    return float(Decimal(str(package_data["price"])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def calculate_vehicle_pricing(vehicles, distances_and_durations, pickup_date, departure_coords, destination_coords, estimate_type):
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
        pricing = {"standard_cost": {"vehicle_id": vehicle.id, "vehicle_name": f"{vehicle.brand} {vehicle.model}"}}
        
        if vehicle.availability_type == 'on_demand':
            pricing["standard_cost"].update({"total_cost": 0.0})
            pricing["applied_rules"] = []
        else:
            price = vehicle.price
            if not price:
                print(f"Aucun tarif pour le véhicule {vehicle.id}.")
                continue

            calcul = (float(price.booking_fee) +
                      float(price.delivery_fee) * dist_base_km +
                      float(price.price_per_km) * dist_parcourt_km +
                      float(price.delivery_fee) * dist_retour_km +
                      float(price.price_per_duration) / 60 * dur_parcourt_minutes)
            # Changement ici : utiliser 2 décimales au lieu de 3
            calcul_tva = float(Decimal(str(calcul * vat_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            # Changement ici : utiliser 2 décimales au lieu de 3
            total_cost = float(Decimal(str(max(calcul + calcul_tva, price.default_fee or 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

            pricing["standard_cost"].update({
                "total_cost": total_cost,
            })

            valid_rules = filter_and_structure_rules(vehicle, pickup_date, departure_coords, destination_coords)
            final_rules = apply_rule_overrides(valid_rules)
            applied_rules = []
            current_cost = total_cost

            for rule in final_rules:
                if rule["rule_type"] == "package" and rule["package"]:
                    current_cost = apply_package(rule["package"])
                elif rule["rule_type"] == "adjustment" and rule["adjustment"]:
                    current_cost = apply_adjustment(current_cost, rule["adjustment"])
                applied_rules.append({
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "rule_description": rule["description"],
                    "rule_type": rule["rule_type"],
                    # Formatage à 2 décimales pour s'assurer de la cohérence
                    "calculated_cost": round(current_cost, 2),
                    "available_to_all": rule["available_to_all"],
                    "specific_clients": rule["specific_clients"],
                    "excluded_clients": rule["excluded_clients"], 
                })

            pricing["applied_rules"] = applied_rules

        results.append({"vehicle_id": vehicle.id, "pricing": pricing})

    return results

def create_estimation_log_and_tariffs(response_data, user=None):
    """
    Crée un EstimationLog et les EstimationTariff associés, retourne les IDs des tarifs.
    """
    try:
        trip_info = response_data["trip_informations"]
        distances = response_data["distances_and_durations"]
        
        estimation_log = EstimationLog.objects.create(
            departure=trip_info["departure_address"],
            destination=trip_info["destination_address"],
            pickup_date=trip_info["pickup_date"],
            waypoints=trip_info.get("waypoints", []),
            estimate_type="simple_transfer",
            user=user,
            distance_travelled=distances["dist_parcourt_km"],
            duration_travelled=str(distances["dur_parcourt_minutes"]),
        )

        vehicles_tariff_options = []
        
        for vehicle_info in response_data["vehicles_informations"]:
            vehicle_id = vehicle_info["id"]
            pricing = vehicle_info["pricing"]
            rule_tariffs = []
            
            standard_tariff = EstimationTariff.objects.create(
                estimation_log=estimation_log,
                vehicle_id=vehicle_id,
                standard_cost=pricing["standard_cost"]["total_cost"],
            )
            
            for rule in pricing["applied_rules"]:
                rule_tariff = EstimationTariff.objects.create(
                    estimation_log=estimation_log,
                    vehicle_id=vehicle_id,
                    standard_cost=rule["calculated_cost"],
                )
                
                applied_tariff = AppliedTariff.objects.create(
                    rule_id=rule["rule_id"],
                    calculated_cost=rule["calculated_cost"],
                )
                rule_tariff.applied_tariffs.add(applied_tariff)
                
                try:
                    tariff_rule = TariffRule.objects.get(id=rule["rule_id"])
                    rule_tariff.rules.add(tariff_rule)
                except TariffRule.DoesNotExist:
                    logger.warning(f"La règle tarifaire avec l'ID {rule['rule_id']} n'existe pas.")
                
                rule_tariffs.append({
                    "estimation_tariff_id": rule_tariff.id,
                    "rule_id": rule["rule_id"]
                })
            
            vehicles_tariff_options.append({
                "vehicle_id": vehicle_id,
                "standard_tariff_id": standard_tariff.id,
                "rule_tariffs": rule_tariffs
            })

        return {
            "estimation_log_id": estimation_log.id,
            "vehicles_tariff_options": vehicles_tariff_options
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'EstimationLog : {str(e)}")
        raise APIException(f"Erreur lors de la création de l'EstimationLog : {str(e)}")

def build_response_data(trip_data, distances_and_durations, vehicle_pricing_list, vehicle_availability_map, vehicles_queryset, user=None):
    """
    Construit les données de réponse pour l'estimation.
    """
    vehicle_dict = {v.id: v for v in vehicles_queryset}
    
    vehicles_informations = []
    for vp in vehicle_pricing_list:
        vehicle_id = vp["vehicle_id"]
        vehicle = vehicle_dict.get(vehicle_id)
        
        if not vehicle:
            logger.warning(f"Vehicle ID {vehicle_id} not found in vehicles_queryset")
            continue
        
        # Formatage des prix à 2 décimales dans le pricing
        pricing_data = vp["pricing"].copy()
        
        # Formater le coût standard
        if "standard_cost" in pricing_data and "total_cost" in pricing_data["standard_cost"]:
            pricing_data["standard_cost"]["total_cost"] = round(pricing_data["standard_cost"]["total_cost"], 2)
        
        # Formater les coûts des règles appliquées
        if "applied_rules" in pricing_data:
            for rule in pricing_data["applied_rules"]:
                if "calculated_cost" in rule:
                    rule["calculated_cost"] = round(rule["calculated_cost"], 2)
        
        vehicles_informations.append({
            "id": vehicle_id,
            "availability_type": vehicle_availability_map.get(vehicle_id, {}).get("availability_type", "unknown"),
            "availability_time": vehicle_availability_map.get(vehicle_id, {}).get("availability_time"),
            "passenger_capacity": vehicle.passenger_capacity,
            "luggage_capacity": vehicle.luggage_capacity,
            "vehicle_type": vehicle.vehicle_type.name if vehicle.vehicle_type else None,
            "vehicle_name": f"{vehicle.brand} {vehicle.model}",
            "image": vehicle.image.url if vehicle.image else None,
            "pricing": pricing_data
        })

    # Formatage des distances à 2 décimales aussi
    formatted_distances = {
        "dist_parcourt_km": round(distances_and_durations["dist_parcourt_km"], 2),
        "dur_parcourt_minutes": round(distances_and_durations["dur_parcourt_minutes"], 2),
    }

    response_data = {
        "trip_informations": {
            "pickup_date": trip_data["pickup_date"],
            "departure_address": trip_data["departure_location"],
            "destination_address": trip_data["destination_location"],
            "waypoints": trip_data.get("destinationInputs", []),
        },
        "distances_and_durations": formatted_distances,
        "vehicles_informations": vehicles_informations,
        "user_informations": {"id": user.id, "type_utilisateur": user.user_type} if user else {},
        "estimation_data": {},
    }
    return response_data