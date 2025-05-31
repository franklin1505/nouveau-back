from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from courses.Reservations.helpers import create_booking, create_response, format_booking_display_data, format_booking_response, get_booking_email_context_and_send_emails, get_business_info_for_pdf, log_booking_action, process_booking_data, update_estimation_and_create_estimate, validate_booking_data
from courses.Reservations.renderers import WeasyPrintPDFRenderer
from courses.models import Booking
from parametrages.models import StaticContent
from io import BytesIO
from django.template.loader import render_to_string
from rest_framework import renderers
import logging


class BookingValidateView(APIView):
    def validate_request_data(self, request):
        """
        Valide les données de la requête en utilisant validate_booking_data.
        """
        data = request.data
        validated_data, errors = validate_booking_data(data)
        if errors:
            raise ValueError(f"Validation errors: {errors}")
        return validated_data

    def post(self, request, *args, **kwargs):
        try:
            # 1. Valider et formater les données de la requête
            validated_data = self.validate_request_data(request)
            formatted_data, errors = process_booking_data(validated_data)

            if errors:
                return create_response(
                    status_type="error",
                    message="Validation errors",
                    http_status=status.HTTP_400_BAD_REQUEST,
                    error=errors
                )

            # 2. Formater la réponse finale
            response_data = format_booking_response(validated_data, formatted_data)

            # 3. Mettre à jour l'EstimationLog, gérer le code promo et créer l'estimation
            estimate_id = update_estimation_and_create_estimate(
                estimation_log_id=validated_data.get('estimation_log'),
                user_id=formatted_data['user']['request_data'].get('id'),
                is_code_promo_used=formatted_data.get('is_code_promo_used', False),
                request_data=response_data["data"]["request_data"]
            )

            # 4. Mettre à jour request_data avec les informations spécifiques
            response_data["data"]["request_data"] = {
                "compensation": validated_data.get('compensation'),
                "commission": validated_data.get('commission'),
                "driver_sale_price": formatted_data.get('driver_sale_price'),
                "partner_sale_price": formatted_data.get('partner_sale_price'),
                "estimate": estimate_id,  # ID de l'estimation créée
                "client": formatted_data['user']['request_data'].get('id')  # ID de l'utilisateur
            }

            # 5. Retourner la réponse finale
            return create_response(
                status_type="success",
                message="Validation and processing successful",
                data=response_data,
                http_status=status.HTTP_200_OK
            )

        except ValueError as e:
            # Erreur de validation
            return create_response(
                status_type="error",
                message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            # Erreur inattendue
            return create_response(
                status_type="error",
                message=f"An unexpected error occurred: {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
   
class BookingCreateView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # 1. Récupérer les données de la requête
            data = request.data

            # 2. Valider les champs obligatoires
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

            # 3. Créer la réservation
            booking = create_booking(data)

            # 4. Enregistrer l'action "created" dans les logs
            user_id = request.user.id if request.user.is_authenticated else None
            log_booking_action(booking, user_id, "created")

            # 5. Formater les données de la réservation (uniquement display_data)
            display_data = format_booking_display_data(booking)
            
            # 6. Envoyer les e-mails au client et au manager
            get_booking_email_context_and_send_emails(booking.id ,display_data)

            # 7. Retourner la réponse avec les données formatées
            return create_response(
                status_type="success",
                message="Réservation créée avec succès.",
                data=display_data,  # Retourne uniquement display_data
                http_status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return create_response(
                status_type="error",
                message=f"Une erreur s'est produite lors de la création de la réservation : {str(e)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            

class DownloadBookingPDFView(APIView):
    renderer_classes = [WeasyPrintPDFRenderer]  # Utiliser le renderer personnalisé

    def get(self, request, booking_id):
        try:
            # Récupérer la réservation
            booking = Booking.objects.get(id=booking_id)
            static_content = StaticContent.objects.first()
            booking_data = format_booking_display_data(booking)
            business_info = get_business_info_for_pdf()

            # Préparer le contexte pour le template PDF
            context = {
                "reservation_details": booking_data,
                "business_info": business_info,
                "static_content": static_content,
            }

            # Rendre le template HTML en une chaîne de caractères
            html_string = render_to_string("fichiers_pdfs/pdf_booking_booked.html", context)

            # Retourner le HTML dans la réponse pour que le renderer le convertisse en PDF
            return Response({"html_string": html_string})

        except Booking.DoesNotExist:
            return Response(
                {"error": "La réservation spécifiée n'existe pas."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Une erreur s'est produite : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )