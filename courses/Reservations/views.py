from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated , AllowAny
from courses.Reservations.helpers import (
    create_booking_with_payment_timing, create_response, format_booking_data, format_booking_validation_response, get_booking_email_context_and_send_emails, get_payment_instructions, get_payment_notes, handle_api_exceptions, log_booking_action, process_booking_data, update_estimation_and_create_estimate, update_existing_estimate,
    validate_booking_data, update_estimation_tariff, calculate_booking_costs, validate_client_id_and_get_passengers
)
from courses.Reservations.pdf_service import generate_booking_pdf, get_booking_html
from courses.Reservations.serializers import PassengerListSerializer, PaymentSerializer, UpdateTariffSerializer
from courses.models import Booking, EstimationTariff, Estimate

class BookingValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def validate_request_data(self, request):
        data = request.data
        validated_data, errors = validate_booking_data(data, request=request)
        if errors:
            raise ValueError(f"Validation errors: {errors}")
        return validated_data

    def validate_estimate_for_modification(self, estimate_id, estimation_log_id):
        """Valide la cohérence estimate_id <-> estimation_log_id"""
        try:
            estimate = Estimate.objects.get(id=estimate_id)
            if estimate.estimation_log_id != estimation_log_id:
                raise ValueError("L'estimate_id ne correspond pas à l'estimation_log_id fourni")
            return estimate
        except Estimate.DoesNotExist:
            raise ValueError(f"Estimate avec l'ID {estimate_id} n'existe pas")

    @handle_api_exceptions
    def post(self, request, *args, **kwargs):
        validated_data = self.validate_request_data(request)
        
        # Détection du mode
        estimate_id = request.data.get('estimate_id')
        estimation_log_id = validated_data.get('estimation_log')
        
        if estimate_id:
            # MODE MODIFICATION
            estimate = self.validate_estimate_for_modification(estimate_id, estimation_log_id)
            return self.handle_modification(request, validated_data, estimate)
        else:
            # MODE CRÉATION (logique actuelle)
            return self.handle_creation(request, validated_data)

    def handle_creation(self, request, validated_data):
        """Logique de création existante"""
        user_choice_data = validated_data.get('user_choice', {})
        vehicle_id = user_choice_data.get('vehicle_id')
        standard_cost = user_choice_data.get('standard_cost')
        is_standard_cost = user_choice_data.get('is_standard_cost')
        estimation_log_id = validated_data.get('estimation_log')
        estimation_tariff_id = user_choice_data.get('estimation_tariff_id')

        # Validation optionnelle du meeting_place
        meeting_place_id = validated_data.get('meeting_place')
        if meeting_place_id:
            from configurations.models import MeetingPlace
            meeting_place = MeetingPlace.objects.filter(id=meeting_place_id).first()
            if not meeting_place:
                return create_response(
                    status_type="error",
                    message=f"Le lieu de rendez-vous avec l'ID {meeting_place_id} n'existe pas.",
                    http_status=status.HTTP_404_NOT_FOUND
                )

        # Mise à jour du tarif si nécessaire
        if standard_cost is not None and is_standard_cost:
            if estimation_tariff_id:
                estimation_tariff = EstimationTariff.objects.filter(id=estimation_tariff_id).first()
            else:
                estimation_tariff = EstimationTariff.objects.filter(
                    estimation_log_id=estimation_log_id, vehicle_id=vehicle_id
                ).first()
            if not estimation_tariff:
                return create_response(
                    status_type="error",
                    message="Tarif non trouvé pour ce véhicule.",
                    http_status=status.HTTP_404_NOT_FOUND
                )
            update_estimation_tariff(estimation_tariff, standard_cost)

        # Traitement des données
        formatted_data, errors = process_booking_data(validated_data)
        if errors:
            return create_response(
                status_type="error",
                message="Validation errors",
                http_status=status.HTTP_400_BAD_REQUEST,
                error=errors
            )

        request_data = {
            "estimation_log": estimation_log_id,
            "user_choice": formatted_data.get('user_choice_id'),
            "meeting_place": validated_data.get('meeting_place'),
            "passengers": formatted_data.get('passengers', {}).get('request_data', {}).get('ids', []),
            "estimate_attribute": formatted_data.get('estimate_attribute', {}).get('request_data', {}).get('ids', []),
            "flight_number": validated_data.get('flight_number'),
            "message": validated_data.get('message'),
            "total_booking_cost": formatted_data.get('total_booking_cost'),
            "total_attributes_cost": formatted_data.get('total_attributes_cost'),
            "number_of_luggages": validated_data.get('number_of_luggages'),
            "number_of_passengers": validated_data.get('number_of_passengers'),
            "case_number": validated_data.get('case_number')
        }

        try:
            estimate_id = update_estimation_and_create_estimate(
                estimation_log_id=estimation_log_id,
                user_id=formatted_data['user']['request_data'].get('id'),
                is_code_promo_used=formatted_data.get('is_code_promo_used', False),
                request_data=request_data
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la création de l'estimation: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_data = format_booking_validation_response(
            validated_data=validated_data,
            formatted_data=formatted_data,
            estimate_id=estimate_id
        )

        return Response(response_data, status=status.HTTP_200_OK)

    def handle_modification(self, request, validated_data, estimate):
        """Logique de modification"""
        user_choice_data = validated_data.get('user_choice', {})
        
        # Mise à jour du tarif si nécessaire
        if user_choice_data.get('standard_cost') and user_choice_data.get('is_standard_cost'):
            estimation_tariff_id = user_choice_data.get('estimation_tariff_id')
            if estimation_tariff_id:
                estimation_tariff = EstimationTariff.objects.filter(id=estimation_tariff_id).first()
            else:
                estimation_tariff = EstimationTariff.objects.filter(
                    estimation_log_id=estimate.estimation_log_id,
                    vehicle_id=user_choice_data['vehicle_id']
                ).first()
            
            if estimation_tariff:
                update_estimation_tariff(estimation_tariff, user_choice_data['standard_cost'])

        # Traitement des données
        formatted_data, errors = process_booking_data(validated_data)
        if errors:
            return create_response(
                status_type="error",
                message="Validation errors",
                http_status=status.HTTP_400_BAD_REQUEST,
                error=errors
            )

        try:
            # Modification de l'estimate existant
            update_existing_estimate(estimate, validated_data, formatted_data)
            
            response_data = format_booking_validation_response(
                validated_data=validated_data,
                formatted_data=formatted_data,
                estimate_id=estimate.id
            )

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Erreur lors de la modification: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BookingPaymentView(APIView):
    @handle_api_exceptions
    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return create_response(
                status_type="error",
                message="Validation errors",
                http_status=status.HTTP_400_BAD_REQUEST,
                error=serializer.errors
            )

        estimate_id = serializer.validated_data['estimate_id']
        payment_method_id = serializer.validated_data['payment_method']
        payment_timing = serializer.validated_data.get('payment_timing', 'later')
        code_promo = serializer.validated_data.get('code_promo')
        compensation = serializer.validated_data.get('compensation', 0)
        commission = serializer.validated_data.get('commission', 0)

        estimate = Estimate.objects.filter(id=estimate_id).first()
        if not estimate:
            return create_response(
                status_type="error",
                message="Estimation non trouvée.",
                http_status=status.HTTP_404_NOT_FOUND
            )

        # ✅ RÉCUPÉRATION du client_id dès le début
        client_id = None
        client_for_promo = None
        
        # Essayer de récupérer le client depuis l'estimate
        if hasattr(estimate, 'client') and estimate.client:
            client_id = estimate.client.id
            client_for_promo = estimate.client
        # Sinon, essayer de récupérer depuis l'estimation_log
        elif hasattr(estimate, 'estimation_log') and estimate.estimation_log and estimate.estimation_log.user:
            user = estimate.estimation_log.user
            client_id = user.id
            # Pour admin, client_for_promo reste None (pas de promo code)
            if user.user_type != 'administrator':
                try:
                    client_for_promo = user.client
                except:
                    client_for_promo = None

        estimation_tariff = EstimationTariff.objects.filter(
            estimation_log_id=estimate.estimation_log_id,
            vehicle_id=estimate.user_choice.vehicle_id
        ).first()
        
        if not estimation_tariff:
            return create_response(
                status_type="error",
                message="Aucun tarif trouvé pour cette estimation et ce véhicule.",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        user_choice = {
            'vehicle_id': estimate.user_choice.vehicle_id,
            'selected_tariff': estimate.user_choice.selected_tariff.id if estimate.user_choice.selected_tariff else None,
            'is_standard_cost': estimate.user_choice.is_standard_cost,
            'standard_cost': float(estimation_tariff.standard_cost) if estimate.user_choice.is_standard_cost else None
        }
        
        total_attributes_cost = float(sum(attr.total for attr in estimate.estimate_attribute.all()))
        
        # Recalcul avec les bons paramètres
        cost_result = calculate_booking_costs(
            user_choice=user_choice,
            estimation_tariff=estimation_tariff,
            client=client_for_promo,
            total_attributes_cost=total_attributes_cost,
            code_promo=code_promo,
            compensation=compensation,
            commission=commission
        )

        # Mise à jour de l'estimate
        estimate.payment_method_id = payment_method_id
        estimate.total_booking_cost = cost_result['total_booking_cost']
        
        if compensation > 0:
            estimate.compensation = compensation
            estimate.commission = 0
        elif commission > 0:
            estimate.commission = commission
            estimate.compensation = 0
            
        if payment_timing == 'later':
            estimate.is_payment_pending = True
            message = "Booking validated, payment will be processed later"
            payment_status_info = "Payment scheduled for later processing"
        else:
            estimate.is_payment_pending = True
            message = "Payment timing set to 'now' - processed as 'later' in current version"
            payment_status_info = "Immediate payment requested (feature in development)"
            
        estimate.save()

        # ✅ RÉPONSE ENRICHIE avec client_id et détails
        response_data = {
            "estimate_id": estimate_id,
            "client_id": client_id,  # ✅ NOUVEAU
            "base_cost": cost_result['selected_tariff'],
            "additional_services_cost": total_attributes_cost,
            "total_booking_cost": cost_result['total_booking_cost'],
            "promotion_message": cost_result.get('promotion_message'),
            "driver_sale_price": cost_result['driver_sale_price'],
            "partner_sale_price": cost_result['partner_sale_price'],
            "commission_applied": commission,
            "compensation_applied": compensation,
            "payment_method": payment_method_id,
            "payment_timing": payment_timing,
            "payment_status_info": payment_status_info,
            "ready_for_booking": True
        }
        
        return create_response(
            status_type="success",
            message=message,
            data=response_data,
            http_status=status.HTTP_200_OK
        )

class BookingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @handle_api_exceptions
    def post(self, request, *args, **kwargs):
        data = request.data
        required_fields = [
            'compensation', 'commission', 'driver_sale_price',
            'partner_sale_price', 'estimate', 'client'
        ]
        
        for field in required_fields:
            if field not in data:
                return create_response(
                    status_type="error",
                    message=f"Le champ '{field}' est obligatoire.",
                    http_status=status.HTTP_400_BAD_REQUEST
                )

        estimate = Estimate.objects.get(id=data['estimate'])
        payment_timing = data.get('payment_timing', 'later')
        
        # Vérification de la méthode de paiement
        if not estimate.payment_method:
            return create_response(
                status_type="error",
                message="Une méthode de paiement doit être sélectionnée.",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ UTILISATION de la fonction corrigée
        booking = create_booking_with_payment_timing(data, payment_timing)
        user_id = request.user.id if request.user.is_authenticated else None
        log_booking_action(booking, user_id, "created")
        
        display_data = format_booking_data(booking=booking, include_request_data=False)
        
        # ✅ AJOUTER payment_timing et instructions à la réponse
        display_data["display_data"]["payment_timing"] = payment_timing
        display_data["display_data"]["payment_instructions"] = get_payment_instructions(estimate.payment_method)
        
        # ✅ OPTIONNEL: Ajouter les notes de paiement dans la réponse (pas dans le modèle)
        payment_notes = get_payment_notes(estimate.payment_method, payment_timing)
        display_data["display_data"]["payment_notes"] = payment_notes
        
        get_booking_email_context_and_send_emails(booking.id, display_data["display_data"])

        return create_response(
            status_type="success",
            message="Réservation créée avec succès. Paiement à effectuer ultérieurement.",
            data=display_data["display_data"],
            http_status=status.HTTP_201_CREATED
        )

class UpdateTariffView(APIView):
    permission_classes = [IsAuthenticated]

    @handle_api_exceptions
    def post(self, request):
        serializer = UpdateTariffSerializer(data=request.data)
        if not serializer.is_valid():
            return create_response(
                status_type="error",
                message="Validation errors",
                http_status=status.HTTP_400_BAD_REQUEST,
                error=serializer.errors
            )

        estimation_tariff_id = serializer.validated_data['estimation_tariff_id']
        standard_cost = serializer.validated_data['standard_cost']

        estimation_tariff = EstimationTariff.objects.get(id=estimation_tariff_id)
        estimate = Estimate.objects.filter(estimation_log=estimation_tariff.estimation_log).first()
        total_booking_cost = None
        if estimate:
            cost_result = calculate_booking_costs(
                user_choice={
                    'vehicle_id': estimate.user_choice.vehicle_id,
                    'selected_tariff': estimate.user_choice.selected_tariff_id,
                    'is_standard_cost': True,
                    'standard_cost': standard_cost
                },
                estimation_tariff=estimation_tariff,
                client=estimate.client,
                total_attributes_cost=sum(attr.total for attr in estimate.estimate_attribute.all()),
                code_promo=estimate.code_promo,
                compensation=estimate.compensation,
                commission=estimate.commission
            )
            total_booking_cost = cost_result['total_booking_cost']
            estimate.total_booking_cost = total_booking_cost
            estimate.is_standard_cost = True
            estimate.driver_sale_price = cost_result['driver_sale_price']
            estimate.partner_sale_price = cost_result['partner_sale_price']
            estimate.save()

        booking = Booking.objects.filter(estimate=estimate).first()
        if booking:
            booking.total_booking_cost = total_booking_cost
            booking.driver_sale_price = cost_result['driver_sale_price']
            booking.partner_sale_price = cost_result['partner_sale_price']
            booking.save()
            display_data = format_booking_data(booking=booking, include_request_data=False)
            get_booking_email_context_and_send_emails(booking.id, display_data["display_data"], is_update=True)

        return create_response(
            status_type="success",
            message="Tarif mis à jour avec succès.",
            data={
                "estimation_tariff_id": estimation_tariff_id,
                "standard_cost": standard_cost,
                "total_booking_cost": total_booking_cost
            },
            http_status=status.HTTP_200_OK
        )
# ✅ SOLUTION DÉFINITIVE - Remplacez votre vue PDF
class DownloadBookingPDFView(APIView):
    """
    ✅ VUE PDF SIMPLIFIÉE utilisant le service dédié
    Plus de problème de renderer ou de décorateur
    """
    permission_classes = [AllowAny]

    def get(self, request, booking_id):
        """
        Génère et retourne le PDF de la réservation
        """
        # Génération directe via le service
        return generate_booking_pdf(booking_id)
    
class DebugBookingHTMLView(APIView):
    """
    Vue pour visualiser le HTML avant génération PDF (utile pour debugging)
    """
    permission_classes = [AllowAny]

    def get(self, request, booking_id):
        """
        Retourne le HTML généré pour vérification
        """
        html_string, error = get_booking_html(booking_id)
        
        if error:
            return HttpResponse(f"Erreur: {error}", status=500)
        
        # Retourne le HTML directement dans le navigateur
        return HttpResponse(html_string, content_type='text/html')

         
class PassengerListView(APIView):
    permission_classes = [IsAuthenticated]

    @handle_api_exceptions
    def get(self, request, client_id=None):
        """
        Récupère la liste des passagers en fonction de l'ID du client.
        Si aucun client_id n'est fourni, retourne les passagers avec client null.
        """
        # Valider le client_id et récupérer les passagers
        passengers_data, errors = validate_client_id_and_get_passengers(client_id)
        
        if errors:
            return create_response(
                status_type="error",
                message="Erreur lors de la récupération des passagers.",
                http_status=status.HTTP_400_BAD_REQUEST,
                error=errors
            )

        if not passengers_data:
            return create_response(
                status_type="success",
                message="Aucun passager trouvé.",
                data={"passagers": []},
                http_status=status.HTTP_200_OK
            )

        # Formatter les données avec le sérialiseur
        serializer = PassengerListSerializer(passengers_data, many=True)
        return create_response(
            status_type="success",
            message="Liste des passagers récupérée avec succès.",
            data={"passagers": serializer.data},
            http_status=status.HTTP_200_OK
        )
