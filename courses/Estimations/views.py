from rest_framework.views import APIView
from rest_framework import status
from .helpers import build_response_data, calculate_distances_and_durations, collect_vehicle_pricing_info, create_estimation_log_and_tariffs, create_response, filter_and_group_vehicles
from parametrages.models import APIKey
from configurations.models import Vehicle  

class EstimateView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        departure = data.get("departure_location")
        destination = data.get("destination_location")
        pickup_date = data.get("pickup_date")
        waypoints = data.get("destinationInputs", [])
        estimate_type = data.get("estimate_type", "simple_transfer")

        # Validation des champs requis
        if not all([departure, destination, pickup_date]):
            return create_response(
                "error",
                "Les champs 'departure_location', 'destination_location' et 'pickup_date' sont obligatoires.",
                http_status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1) Clé API
            api_key = APIKey.objects.first()
            if not api_key:
                return create_response(
                    "error",
                    "Clé API Google introuvable.",
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 2) Récup véhicules
            vehicles = Vehicle.objects.filter(validation=True)
            if not vehicles.exists():
                return create_response(
                    "error",
                    "Aucun véhicule disponible.",
                    http_status=status.HTTP_404_NOT_FOUND
                )

            # 3) Filtrer et obtenir SEULEMENT les véhicules de la base la plus proche
            vehicle_availability = filter_and_group_vehicles(
                vehicles,
                departure_location=departure,
                api_key=api_key.key_value,
                pickup_date=pickup_date
            )
            
            # Vérifier qu'on a des véhicules disponibles
            if not vehicle_availability:
                return create_response(
                    "error",
                    "Aucun véhicule disponible dans la base la plus proche.",
                    http_status=status.HTTP_404_NOT_FOUND
                )

            # 4) La base la plus proche (maintenant c'est sûr que c'est la bonne)
            closest_base = vehicle_availability[0]["base_location"]

            # 5) Filtrer les véhicules pour ne garder que ceux de la base la plus proche
            vehicle_ids_from_closest_base = [v["vehicle_id"] for v in vehicle_availability]
            vehicles_from_closest_base = vehicles.filter(id__in=vehicle_ids_from_closest_base)

            # 6) Distances et durées + géocodage
            distances_and_durations = calculate_distances_and_durations(
                api_key=api_key.key_value,
                departure=departure,
                destination=destination,
                origin=closest_base,
                waypoints=waypoints
            )

            # 7) Extraire coords départ / arrivée
            departure_coords = None
            destination_coords = None

            if distances_and_durations["coords"].get("departure"):
                dep_lat = distances_and_durations["coords"]["departure"]["lat"]
                dep_lng = distances_and_durations["coords"]["departure"]["lng"]
                departure_coords = (dep_lat, dep_lng)

            if distances_and_durations["coords"].get("destination"):
                dest_lat = distances_and_durations["coords"]["destination"]["lat"]
                dest_lng = distances_and_durations["coords"]["destination"]["lng"]
                destination_coords = (dest_lat, dest_lng)

            # 8) Collecter les info de pricing SEULEMENT pour les véhicules de la base la plus proche
            vehicle_pricing_list = collect_vehicle_pricing_info(
                vehicles=vehicles_from_closest_base,  # <-- Changement ici
                distances_and_durations=distances_and_durations,
                pickup_date=pickup_date,
                departure_coords=departure_coords,
                destination_coords=destination_coords,
                estimate_type=estimate_type
            )

            # 9) Récupérer l'utilisateur connecté
            user = request.user if request.user.is_authenticated else None

            # 10) Construire la réponse
            response_data = build_response_data(
                trip_data=data,
                distances_and_durations=distances_and_durations,
                vehicle_pricing_list=vehicle_pricing_list,
                vehicle_availability_map={av["vehicle_id"]: av for av in vehicle_availability},
                vehicles_queryset=vehicles_from_closest_base,  # <-- Changement ici
                user=user
            )

            # 11) Enregistrer l'EstimationLog et les EstimationTariff
            estimation_data = create_estimation_log_and_tariffs(
                response_data=response_data,
                user=user
            )

            # 12) Ajouter les IDs à la réponse
            response_data["estimation_data"] = estimation_data

            return create_response(
                "success",
                "Estimation calculée avec succès.",
                data=response_data,
                http_status=status.HTTP_200_OK
            )

        except Exception as e:
            return create_response(
                "error",
                "Une erreur s'est produite lors du calcul.",
                error=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )