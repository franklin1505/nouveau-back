from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from courses.Estimations.serializers import EstimateSerializer
from courses.Reservations.helpers import handle_api_exceptions
from .helpers import (
    create_response, calculate_distances_and_durations,
    filter_and_group_vehicles, calculate_vehicle_pricing, build_response_data,
    create_estimation_log_and_tariffs
)
from parametrages.models import APIKey
from configurations.models import Vehicle

@handle_api_exceptions
def process_estimation(data, user):
    """
    Traite les données d'estimation et retourne la réponse avec les options tarifaires.
    """
    api_key = APIKey.objects.first()
    if not api_key:
        return create_response(
            "error", "Clé API Google introuvable.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    vehicles = Vehicle.objects.filter(validation=True)
    if not vehicles.exists():
        return create_response(
            "error", "Aucun véhicule disponible.", http_status=status.HTTP_404_NOT_FOUND
        )

    vehicle_availability = filter_and_group_vehicles(
        vehicles, data["departure_location"], api_key.key_value, data["pickup_date"]
    )
    if not vehicle_availability:
        return create_response(
            "error", "Aucun véhicule disponible dans la base la plus proche.", http_status=status.HTTP_404_NOT_FOUND
        )

    vehicle_ids = [v["vehicle_id"] for v in vehicle_availability]
    vehicles_from_closest_base = vehicles.filter(id__in=vehicle_ids)
    distances_and_durations = calculate_distances_and_durations(
        api_key.key_value, data["departure_location"], data["destination_location"],
        vehicle_availability[0]["base_location"], data.get("destinationInputs")
    )

    departure_coords = (distances_and_durations["coords"]["departure"]["lat"],
                        distances_and_durations["coords"]["departure"]["lng"]) if distances_and_durations["coords"].get("departure") else None
    destination_coords = (distances_and_durations["coords"]["destination"]["lat"],
                         distances_and_durations["coords"]["destination"]["lng"]) if distances_and_durations["coords"].get("destination") else None

    vehicle_pricing_list = calculate_vehicle_pricing(
        vehicles_from_closest_base, distances_and_durations, data["pickup_date"],
        departure_coords, destination_coords, data["estimate_type"]
    )

    response_data = build_response_data(
        data, distances_and_durations, vehicle_pricing_list,
        {av["vehicle_id"]: av for av in vehicle_availability}, vehicles_from_closest_base, user
    )

    # Créer les tarifs et mettre à jour pricing avec estimation_tariff_id
    estimation_data = create_estimation_log_and_tariffs(response_data, user)
    
    # Mettre à jour pricing avec les estimation_tariff_id
    for vehicle_info in response_data["vehicles_informations"]:
        vehicle_id = vehicle_info["id"]
        for tariff in estimation_data["vehicles_tariff_options"]:
            if tariff["vehicle_id"] == vehicle_id:
                vehicle_info["pricing"]["standard_cost"]["estimation_tariff_id"] = tariff["standard_tariff_id"]
                for rule, tariff_rule in zip(vehicle_info["pricing"]["applied_rules"], tariff["rule_tariffs"]):
                    rule["estimation_tariff_id"] = tariff_rule["estimation_tariff_id"]

    response_data["estimation_data"] = {
        "estimation_log_id": estimation_data["estimation_log_id"]
    }

    return create_response(
        "success", "Estimation calculée avec succès.", data=response_data, http_status=status.HTTP_200_OK
    )

class EstimateView(APIView):
    permission_classes = [AllowAny]

    @handle_api_exceptions
    def post(self, request, *args, **kwargs):
        serializer = EstimateSerializer(data=request.data)
        if not serializer.is_valid():
            return create_response(
                "error", "Données invalides.", error=serializer.errors, http_status=status.HTTP_400_BAD_REQUEST
            )

        return process_estimation(serializer.validated_data, request.user if request.user.is_authenticated else None)