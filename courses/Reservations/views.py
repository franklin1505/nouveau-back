from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated , AllowAny
from courses.Reservations.helpers import (
    create_booking_with_payment_timing, create_response, format_booking_data, 
    format_booking_validation_response, get_booking_email_context_and_send_emails, 
    get_payment_instructions, get_payment_notes, handle_api_exceptions, 
    handle_payment_creation_logic, handle_payment_update_logic, 
    process_booking_data, send_unified_emails_with_notifications, update_estimation_and_create_estimate, update_existing_estimate,
    validate_booking_data, update_estimation_tariff, calculate_booking_costs, 
    validate_client_id_and_get_passengers, validate_estimate_for_payment, 
    validate_payment_request_data
)
from courses.Reservations.pdf_service import generate_booking_pdf, get_booking_html
from courses.Reservations.serializers import PassengerListSerializer, PaymentSerializer, UpdateTariffSerializer
from courses.models import Booking, EstimationTariff, Estimate
from utilisateurs.models import Administrator, Business

class BookingValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def validate_request_data(self, request):
        """Valide les données de la requête"""
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
            # MODE CRÉATION
            return self.handle_creation(request, validated_data)

    def handle_creation(self, request, validated_data):
        """Logique de création d'estimation"""
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
        """Logique de modification d'estimation"""
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
    """
    Vue pour le paiement avec support de création/modification
    
    Modes supportés :
    - Création : mode='create' (défaut)
    - Modification : mode='update'
    """
    permission_classes = [IsAuthenticated]

    @handle_api_exceptions
    def post(self, request):
        """Gère les requêtes de paiement avec support création/modification"""
        # 1. Validation des données d'entrée
        validated_data = validate_payment_request_data(request.data)
        
        # 2. Validation de l'estimate
        estimate_id = validated_data['estimate_id']
        estimate = validate_estimate_for_payment(estimate_id)
        
        # 3. Détermination du mode
        mode = request.data.get('mode', 'create')
        
        # 4. Traitement selon le mode
        if mode == 'update':
            result = handle_payment_update_logic(estimate, validated_data)
        else:
            result = handle_payment_creation_logic(estimate, validated_data)
        
        # 5. Retour de la réponse
        return create_response(
            status_type=result["status"],
            message=result["message"],
            data=result.get("data", {}),
            http_status=result["http_status"]
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

class DownloadBookingPDFView(APIView):
    """Vue pour télécharger le PDF de réservation"""
    permission_classes = [AllowAny]

    def get(self, request, booking_id):
        """Génère et retourne le PDF de la réservation"""
        return generate_booking_pdf(booking_id)
    
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
        
# class BookingCreateView(APIView):
#     permission_classes = [IsAuthenticated]

#     @handle_api_exceptions
#     def post(self, request, *args, **kwargs):
#         data = request.data
#         required_fields = [
#             'compensation', 'commission', 'driver_sale_price',
#             'partner_sale_price', 'estimate', 'client'
#         ]
        
#         for field in required_fields:
#             if field not in data:
#                 return create_response(
#                     status_type="error",
#                     message=f"Le champ '{field}' est obligatoire.",
#                     http_status=status.HTTP_400_BAD_REQUEST
#                 )

#         estimate = Estimate.objects.get(id=data['estimate'])
#         payment_timing = data.get('payment_timing', 'later')
        
#         if not estimate.payment_method:
#             return create_response(
#                 status_type="error",
#                 message="Une méthode de paiement doit être sélectionnée.",
#                 http_status=status.HTTP_400_BAD_REQUEST
#             )
        
#         booking = create_booking_with_payment_timing(data, payment_timing)
#         user_id = request.user.id if request.user.is_authenticated else None
#         # log_booking_action(booking, user_id, "created")
        
#         display_data = format_booking_data(booking=booking, include_request_data=False)
        
#         display_data["display_data"]["payment_timing"] = payment_timing
#         display_data["display_data"]["payment_instructions"] = get_payment_instructions(estimate.payment_method)
        
#         payment_notes = get_payment_notes(estimate.payment_method, payment_timing)
#         display_data["display_data"]["payment_notes"] = payment_notes
        
#         try:
#             send_unified_emails_with_notifications(booking.id, is_update=False)
#         except Exception as e:
#             print(f"Erreur envoi emails/notifications: {e}")

#         return create_response(
#             status_type="success",
#             message="Réservation créée avec succès. Paiement à effectuer ultérieurement.",
#             data=display_data["display_data"],
#             http_status=status.HTTP_201_CREATED
#         )

# 1. VIEWS.PY - BookingCreateView complète avec debugging
class BookingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @handle_api_exceptions
    def post(self, request, *args, **kwargs):
        print("="*80)
        print("🔍 DEBUT DEBUG - BookingCreateView")
        print("="*80)
        
        # 🔍 1. VERIFIER LES DONNEES BRUTES
        print(f"📨 request.data TYPE: {type(request.data)}")
        print(f"📨 request.data CONTENT: {request.data}")
        print(f"📨 request.data KEYS: {list(request.data.keys()) if hasattr(request.data, 'keys') else 'Pas de keys'}")
        
        # 🔍 2. VERIFIER CHAQUE CHAMP INDIVIDUELLEMENT
        data = request.data
        for key, value in data.items():
            print(f"📋 {key}: {value} (type: {type(value)})")
        
        # 🔍 3. VERIFIER L'UTILISATEUR AUTHENTIFIE
        print(f"👤 request.user: {request.user}")
        print(f"👤 request.user.id: {request.user.id} (type: {type(request.user.id)})")
        print(f"👤 request.user.is_authenticated: {request.user.is_authenticated}")
        
        # 🔍 4. VERIFIER LES CHAMPS SPECIFIQUES
        required_fields = ['compensation', 'commission', 'driver_sale_price', 'partner_sale_price', 'estimate', 'client']
        
        print("\n📋 VERIFICATION DES CHAMPS REQUIS:")
        for field in required_fields:
            if field in data:
                value = data[field]
                print(f"   ✅ {field}: {value} (type: {type(value)})")
                
                # Verification speciale pour les IDs
                if field in ['estimate', 'client']:
                    print(f"      🔍 Tentative de conversion en int:")
                    try:
                        converted = int(value)
                        print(f"      ✅ Conversion réussie: {converted}")
                    except Exception as e:
                        print(f"      ❌ ERREUR conversion: {str(e)}")
            else:
                print(f"   ❌ {field}: MANQUANT")
        
        print("="*50)
        
        # Validation des champs obligatoires
        for field in required_fields:
            if field not in data:
                print(f"❌ ERREUR: Champ manquant {field}")
                return create_response(
                    status_type="error",
                    message=f"Le champ '{field}' est obligatoire.",
                    http_status=status.HTTP_400_BAD_REQUEST
                )

        print("🔍 AVANT get_object_or_404 pour Estimate")
        print(f"   estimate_id: {data['estimate']} (type: {type(data['estimate'])})")
        
        try:
            estimate = Estimate.objects.get(id=data['estimate'])
            print(f"✅ Estimate trouvé: {estimate}")
        except Exception as e:
            print(f"❌ ERREUR get Estimate: {str(e)}")
            return create_response(
                status_type="error",
                message=f"Erreur récupération estimate: {str(e)}",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_timing = data.get('payment_timing', 'later')
        print(f"🔍 payment_timing: {payment_timing}")
        
        if not estimate.payment_method:
            print("❌ ERREUR: Pas de méthode de paiement")
            return create_response(
                status_type="error",
                message="Une méthode de paiement doit être sélectionnée.",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        print("🔍 AVANT create_booking_with_payment_timing")
        print(f"   data passé: {data}")
        print(f"   payment_timing passé: {payment_timing}")
        
        try:
            booking = create_booking_with_payment_timing(data, payment_timing)
            print(f"✅ Booking créé avec succès: {booking}")
        except Exception as e:
            print(f"❌ ERREUR create_booking_with_payment_timing: {str(e)}")
            return create_response(
                status_type="error",
                message=f"Erreur création booking: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        user_id = request.user.id if request.user.is_authenticated else None
        print(f"🔍 user_id pour log: {user_id} (type: {type(user_id)})")
        
        # log_booking_action(booking, user_id, "created")
        
        print("🔍 AVANT format_booking_data")
        display_data = format_booking_data(booking=booking, include_request_data=False)
        print(f"✅ display_data généré")
        
        display_data["display_data"]["payment_timing"] = payment_timing
        display_data["display_data"]["payment_instructions"] = get_payment_instructions(estimate.payment_method)
        
        payment_notes = get_payment_notes(estimate.payment_method, payment_timing)
        display_data["display_data"]["payment_notes"] = payment_notes
        
        try:
            print("🔍 AVANT send_unified_emails_with_notifications")
            send_unified_emails_with_notifications(booking.id, is_update=False)
            print("✅ Emails/notifications envoyés")
        except Exception as e:
            print(f"❌ Erreur envoi emails/notifications: {e}")

        print("="*80)
        print("🔍 FIN DEBUG - BookingCreateView - SUCCES")
        print("="*80)

        return create_response(
            status_type="success",
            message="Réservation créée avec succès. Paiement à effectuer ultérieurement.",
            data=display_data["display_data"],
            http_status=status.HTTP_201_CREATED
        )