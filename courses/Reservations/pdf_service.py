# ✅ NOUVELLE APPROCHE - Créer ce fichier : courses/Reservations/pdf_service.py

from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
from courses.models import Booking
from courses.Reservations.helpers import format_booking_data, get_business_info_for_pdf
from parametrages.models import StaticContent
import logging

logger = logging.getLogger(__name__)

class BookingPDFService:
    """
    Service dédié pour la génération de PDF de réservation
    Approche simple et robuste
    """
    
    def __init__(self, booking_id):
        self.booking_id = booking_id
        self.booking = None
        self.context = None
    
    def load_booking_data(self):
        """
        Charge et valide les données de la réservation
        """
        try:
            self.booking = Booking.objects.select_related(
                'estimate__estimation_log',
                'estimate__user_choice',
                'estimate__meeting_place',
                'estimate__payment_method',
                'client'
            ).prefetch_related(
                'estimate__passengers',
                'estimate__estimate_attribute__attribute'
            ).get(id=self.booking_id)
            
            logger.info(f"Booking {self.booking_id} loaded successfully")
            return True
            
        except Booking.DoesNotExist:
            logger.error(f"Booking {self.booking_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error loading booking {self.booking_id}: {str(e)}")
            return False
    
    def prepare_context(self):
        """
        Prépare le contexte pour le template PDF
        """
        try:
            # Données business
            business_info = get_business_info_for_pdf()
            
            # Contenu statique
            static_content = StaticContent.objects.first()
            
            # Données de réservation formatées
            booking_data = format_booking_data(booking=self.booking, include_request_data=False)
            
            # Context unifié
            self.context = {
                "reservation_details": booking_data["display_data"],
                "business_info": business_info,
                "static_content": static_content,
                "booking": self.booking,  # Objet booking pour accès direct si besoin
            }
            
            logger.info(f"Context prepared for booking {self.booking_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error preparing context for booking {self.booking_id}: {str(e)}")
            return False
    
    def generate_html(self, template_name="fichiers_pdfs/pdf_booking_booked.html"):
        """
        Génère le HTML à partir du template
        """
        try:
            html_string = render_to_string(template_name, self.context)
            logger.info(f"HTML generated for booking {self.booking_id}")
            return html_string
            
        except Exception as e:
            logger.error(f"Error generating HTML for booking {self.booking_id}: {str(e)}")
            return None
    
    def generate_pdf_response(self, template_name="fichiers_pdfs/pdf_booking_booked.html"):
        """
        Génère et retourne la réponse PDF complète
        """
        # 1. Charger les données
        if not self.load_booking_data():
            return HttpResponse(
                f"Erreur: Réservation {self.booking_id} non trouvée", 
                status=404
            )
        
        # 2. Préparer le contexte
        if not self.prepare_context():
            return HttpResponse(
                f"Erreur: Impossible de préparer les données pour la réservation {self.booking_id}", 
                status=500
            )
        
        # 3. Générer le HTML
        html_string = self.generate_html(template_name)
        if not html_string:
            return HttpResponse(
                f"Erreur: Impossible de générer le HTML pour la réservation {self.booking_id}", 
                status=500
            )
        
        # 4. Générer le PDF
        try:
            pdf_file = HTML(string=html_string).write_pdf()
            
            # 5. Préparer la réponse
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="reservation_{self.booking.booking_number}.pdf"'
            
            logger.info(f"PDF generated successfully for booking {self.booking_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating PDF for booking {self.booking_id}: {str(e)}")
            return HttpResponse(
                f"Erreur: Impossible de générer le PDF - {str(e)}", 
                status=500
            )

# ✅ FONCTION UTILITAIRE SIMPLE
def generate_booking_pdf(booking_id, template_name=None):
    """
    Fonction utilitaire simple pour générer un PDF de réservation
    
    Args:
        booking_id: ID de la réservation
        template_name: Nom du template (optionnel)
    
    Returns:
        HttpResponse avec le PDF ou erreur
    """
    service = BookingPDFService(booking_id)
    
    if template_name:
        return service.generate_pdf_response(template_name)
    else:
        return service.generate_pdf_response()

# ✅ FONCTION POUR RÉCUPÉRER JUSTE LE HTML (pour debugging)
def get_booking_html(booking_id, template_name="fichiers_pdfs/pdf_booking_booked.html"):
    """
    Récupère juste le HTML généré (utile pour debugging)
    """
    service = BookingPDFService(booking_id)
    
    if not service.load_booking_data():
        return None, "Réservation non trouvée"
    
    if not service.prepare_context():
        return None, "Erreur préparation contexte"
    
    html_string = service.generate_html(template_name)
    if not html_string:
        return None, "Erreur génération HTML"
    
    return html_string, None