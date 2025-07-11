from django.db import models
from datetime import datetime
from utilisateurs.models import CustomUser

class EstimateAttribute(models.Model):
    """
    Model for attributes associated with an estimation in Courses.
    """
    attribute = models.ForeignKey(
        "configurations.Attribute",  # Remplacez `app_name` par le nom de l'application où `Attribute` est défini.
        on_delete=models.CASCADE,
        help_text="Reference to the attribute defined in the business configuration."
    )
    quantity = models.PositiveIntegerField(help_text="Quantity of the attribute used in the estimation.")

    @property
    def unit_price(self):

        return self.attribute.unit_price

    @property
    def total(self):
    
        return self.quantity * self.unit_price

    def __str__(self):
        return (
            f"{self.attribute.attribute_name} - {self.quantity} x {self.unit_price} "
            f"(Total: {self.total})"
        )

class Passenger(models.Model):
    name = models.CharField(max_length=255, help_text="Name of the passenger.")
    phone_number = models.CharField(max_length=50, help_text="Phone number of the passenger.")
    email = models.EmailField(blank=True, null=True, help_text="Email of the passenger.")  # ✅ NOUVEAU
    is_main_client = models.BooleanField(default=False, help_text="Indicates if this passenger is the main client.")  # ✅ NOUVEAU
    client = models.ForeignKey(
        "utilisateurs.Client",
        on_delete=models.CASCADE,
        related_name="passengers",
        null=True,  # ✅ PERMETTRE NULL pour les réservations admin
        blank=True,
        help_text="Client associated with this passenger."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        main_indicator = " (Client principal)" if self.is_main_client else ""
        return f"{self.name}{main_indicator}"

class EstimationLog(models.Model):
    """
    Model for logging each estimation made by users.
    """
    ESTIMATE_TYPE_CHOICES = [
        ('simple_transfer', 'Transfert Simple'),
        ('made_available', 'Mise à Disposition'),
    ]

    departure = models.CharField(max_length=255, help_text="Lieu de départ.")
    destination = models.CharField(max_length=255, help_text="Lieu de destination.")
    pickup_date = models.DateTimeField(help_text="Date et heure de prise en charge.")
    waypoints = models.JSONField(null=True, blank=True, help_text="Points d'étape (optionnel).")
    estimate_type = models.CharField(
        max_length=50,
        choices=ESTIMATE_TYPE_CHOICES,
        default='simple_transfer',
        help_text="Type d'estimation (Transfert Simple ou Mise à Disposition)."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date et heure de création de l'estimation.")
    user = models.ForeignKey(
        CustomUser,  # Référence à l'utilisateur
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimation_logs",
        help_text="Utilisateur qui a effectué l'estimation."
    )
    is_booked = models.BooleanField(default=False, help_text="Indique si l'estimation a été convertie en réservation.")
    distance_travelled = models.FloatField(help_text="Distance parcourue en kilomètres.")
    duration_travelled = models.CharField(max_length=255, help_text="Durée du trajet.")

    def __str__(self):
        return f"EstimationLog {self.id}: {self.departure} → {self.destination}"
    
    def get_estimate_type_display(self):
        """
        Retourne la valeur d'affichage correspondante au client_type.
        """
        return dict(self.ESTIMATE_TYPE_CHOICES).get(self.estimate_type, "Inconnu")

class AppliedTariff(models.Model):
    """
    Model for storing applied tariffs.
    """
    rule_id = models.IntegerField(help_text="ID of the tariff rule.")
    calculated_cost = models.FloatField(help_text="Calculated cost after applying the rule.")

    def __str__(self):
        return f"AppliedTariff {self.id} for Rule {self.rule_id}"

class EstimationTariff(models.Model):
    """
    Model for storing essential tariffs and rules returned for each vehicle in an estimation.
    """
    estimation_log = models.ForeignKey(
        "EstimationLog",
        on_delete=models.CASCADE,
        related_name="tariffs",
        help_text="Estimation associated with this tariff."
    )
    vehicle_id = models.IntegerField(help_text="ID of the vehicle.")
    standard_cost = models.FloatField(help_text="Standard cost of the vehicle (without rules).")

    # Tarifs appliqués
    applied_tariffs = models.ManyToManyField(
        "AppliedTariff",
        related_name="estimation_tariffs",
        help_text="List of calculated tariffs after applying rules."
    )

    # Règles tarifaires (stockage des ID seulement)
    rules = models.ManyToManyField(
        "configurations.TariffRule",
        related_name="estimation_tariffs",
        help_text="List of tariff rules applied to this estimation."
    )

    def __str__(self):
        return f"EstimationTariff {self.id} for Vehicle {self.vehicle_id}"

class UserChoice(models.Model):
    """
    Model for storing the user's choice of vehicle and tariff.
    """
    vehicle_id = models.IntegerField(help_text="ID of the selected vehicle.")
    selected_tariff = models.ForeignKey(
        "AppliedTariff",  # Si tu utilises un modèle AppliedTariff
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Selected tariff (if not standard cost)."
    )
    is_standard_cost = models.BooleanField(
        default=False,
        help_text="Indicates if the selected tariff is the standard cost."
    )

    def __str__(self):
        return f"UserChoice {self.id} for Vehicle {self.vehicle_id}"
class Estimate(models.Model):
    """
    Model for travel estimates.
    """
    estimation_log = models.OneToOneField(
        "EstimationLog",
        on_delete=models.CASCADE,
        null=True,
        related_name="estimate",
        help_text="Log associated with this estimate."
    )
    user_choice = models.ForeignKey(
        "UserChoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
        help_text="User's choice of vehicle and tariff."
    )
    meeting_place = models.ForeignKey(
        "configurations.MeetingPlace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
        help_text="Meeting place associated with the estimate."
    )
    payment_method = models.ForeignKey(
        "configurations.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
        help_text="Payment method associated with the estimate."
    )
    passengers = models.ManyToManyField(
        "Passenger",
        related_name="estimates",
        help_text="Passengers associated with this estimate."
    )
    estimate_attribute = models.ManyToManyField(
        "EstimateAttribute",
        related_name="estimates",
        help_text="Attribute associated with this estimate."
    )
    flight_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Flight number associated with the estimate."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when the estimate was created.")
    message = models.TextField(null=True, blank=True, help_text="Additional message for the estimate.")
    total_booking_cost = models.FloatField(null=True, blank=True, help_text="Total cost of the booking.")
    total_attributes_cost = models.FloatField(null=True, blank=True, help_text="Total cost of the attributes.")
    number_of_luggages = models.CharField(max_length=100, null=True, blank=True, help_text="Number of luggages.")
    number_of_passengers = models.PositiveIntegerField(null=True, blank=True, help_text="Number of passengers.")
    case_number = models.CharField(max_length=100, null=True, blank=True, help_text="booking case number.")
    is_payment_pending = models.BooleanField(default=False)

    def __str__(self):
        # ✅ CORRECTION : Utiliser les données de estimation_log
        if self.estimation_log:
            departure = self.estimation_log.departure
            destination = self.estimation_log.destination
            return f"Estimate {self.id}: {departure} → {destination}"
        else:
            return f"Estimate {self.id}: Sans estimation_log"

    # ✅ BONUS : Ajouter des propriétés pour faciliter l'accès aux données
    @property
    def departure_location(self):
        """Retourne le lieu de départ depuis l'estimation_log"""
        return self.estimation_log.departure if self.estimation_log else None
    
    @property
    def destination_location(self):
        """Retourne le lieu de destination depuis l'estimation_log"""
        return self.estimation_log.destination if self.estimation_log else None
    
    @property
    def pickup_date(self):
        """Retourne la date de prise en charge depuis l'estimation_log"""
        return self.estimation_log.pickup_date if self.estimation_log else None

class Booking(models.Model):
    """
    Model for managing bookings.
    """

    # Status Choices
    PENDING = "pending"
    IN_PROCESS = "in_process"
    ASSIGNED_TO_DRIVER = "assigned_to_driver"
    ASSIGNED_TO_PARTNER = "assigned_to_partner"
    NOT_ASSIGNED = "not_assigned"
    DRIVER_NOTIFIED = "driver_notified"
    APPROACHING = "approaching"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    BILLING_NOT_INVOICED = "not_invoiced"
    BILLING_INVOICE_REQUESTED = "invoice_requested"
    BILLING_INVOICED = "invoiced"

    NOT_CANCELLED = "not_cancelled"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    LATER = "later"
    NOW = "now"
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"
    
    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (IN_PROCESS, "In Process"),
        (ASSIGNED_TO_DRIVER, "Assigned to Driver"),
        (ASSIGNED_TO_PARTNER, "Assigned to Partner"),
        (NOT_ASSIGNED, "Not Assigned"),
        (DRIVER_NOTIFIED, "Driver Notified"),
        (APPROACHING, "Approaching"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
    )
    BOOKING_TYPE_CHOICES = [
        (ONE_WAY, "Aller simple"),
        (ROUND_TRIP, "Aller-retour"),
    ]

    BILLING_STATUS_CHOICES = (
        (BILLING_NOT_INVOICED, "Not Invoiced"),
        (BILLING_INVOICE_REQUESTED, "Invoice Requested"),
        (BILLING_INVOICED, "Invoiced"),
    )

    CANCELLATION_STATUS_CHOICES = (
        (NOT_CANCELLED, "Not Cancelled"),
        (CANCELLATION_REQUESTED, "Cancellation Requested"),
        (CANCELLED, "Cancelled"),
    )
    
    PAYMENT_TIMING_CHOICES = [
        (LATER, 'Deferred Payment'),  
        (NOW, 'Immediate Payment'),
    ]
    
    # Fields
    is_archived = models.BooleanField(default=False, help_text="Indicates if the booking has been archived.")
    is_driver_paid = models.BooleanField(default=False, help_text="Indicates if the driver has been paid.")
    is_partner_paid = models.BooleanField(default=False, help_text="Indicates if the partner has been paid.")
    client = models.ForeignKey(
        "utilisateurs.Client",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Client associated with the booking."
    )
    assigned_partner = models.ForeignKey(
        "utilisateurs.Partner",
        related_name="partner_bookings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Partner assigned to the booking."
    )
    assigned_driver = models.ForeignKey(
        "utilisateurs.Driver",
        related_name="driver_bookings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Driver assigned to the booking."
    )

    estimate = models.ForeignKey(
        "Estimate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Estimate associated with the booking (NULL for round-trip bookings)."
    )
    driver_sale_price = models.FloatField(null=True, blank=True, help_text="Sale price for the driver")
    partner_sale_price = models.FloatField(null=True, blank=True, help_text="Sale price for the partner.")
    compensation = models.FloatField(null=True, blank=True, help_text="Compensation amount.")
    commission = models.FloatField(null=True, blank=True, help_text="Commission amount.")
    booking_number = models.CharField(max_length=255, null=True, unique=True, help_text="Unique booking number.")
    cancellation_status = models.CharField(
        max_length=25,
        choices=CANCELLATION_STATUS_CHOICES,
        default=NOT_CANCELLED,
        help_text="Cancellation status of the booking."
    )
    booking_type = models.CharField(
        max_length=20,
        choices=BOOKING_TYPE_CHOICES,
        default=ONE_WAY,
        help_text="Type de réservation (simple ou aller-retour)"
    )
    is_billable_when_cancelled = models.BooleanField(
        default=False,
        help_text="Si True, ce segment reste facturable même s'il est annulé"
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default=PENDING,
        help_text="Status of the booking."
    )
    billing_status = models.CharField(
        max_length=25,
        choices=BILLING_STATUS_CHOICES,
        default=BILLING_NOT_INVOICED,
        help_text="Billing status of the booking."
    )
    payment_timing = models.CharField(
        max_length=10,
        choices=PAYMENT_TIMING_CHOICES,
        default=LATER,
        help_text="Indique quand le paiement sera effectué"
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date when the booking was created.")

    def _get_relevant_segments_for_payment(self):
        """Retourne les segments concernés par le paiement"""
        from django.db.models import Q
        return self.segments.filter(
            Q(status='cancelled', is_billable_when_cancelled=True) |
            ~Q(status='cancelled')
        )

    @property
    def total_cost_calculated(self):
        """Calcule le coût total selon le type de booking"""
        if self.booking_type == 'one_way':
            return self.estimate.total_booking_cost if self.estimate else 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.segment_cost or 0 for segment in relevant_segments)

    @property
    def total_attributes_cost_calculated(self):
        """Calcule le coût total des attributs"""
        if self.booking_type == 'one_way':
            return self.estimate.total_attributes_cost if self.estimate else 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.estimate.total_attributes_cost or 0 for segment in relevant_segments)
            
    @property
    def effective_estimate(self):
        """Retourne l'estimate actif selon le type de booking"""
        if self.booking_type == 'one_way':
            return self.estimate
        outbound = self.outbound_segment
        return outbound.estimate if outbound else None
    
    @property
    def effective_status(self):
        """Calcule le statut global depuis les segments pour aller-retour"""
        if self.booking_type == 'one_way':
            return self.status
        return self._calculate_round_trip_status()

    @property
    def effective_driver_sale_price(self):
        """Calcule le prix de vente chauffeur total"""
        if self.booking_type == 'one_way':
            return self.driver_sale_price or 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.calculated_driver_price for segment in relevant_segments)

    @property
    def effective_partner_sale_price(self):
        """Calcule le prix de vente partenaire total"""
        if self.booking_type == 'one_way':
            return self.partner_sale_price or 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.calculated_partner_price for segment in relevant_segments)
    
    @property
    def effective_compensation(self):
        """Calcule la compensation totale"""
        if self.booking_type == 'one_way':
            return self.compensation or 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.compensation or 0 for segment in relevant_segments)
    
    @property
    def effective_commission(self):
        """Calcule la commission totale"""
        if self.booking_type == 'one_way':
            return self.commission or 0
        relevant_segments = self._get_relevant_segments_for_payment()
        return sum(segment.commission or 0 for segment in relevant_segments)

    @property
    def effective_is_driver_paid(self):
        """Détermine si le chauffeur est effectivement payé"""
        if self.booking_type == 'one_way':
            return self.is_driver_paid
        relevant_segments = self._get_relevant_segments_for_payment()
        return relevant_segments.exists() and all(s.is_driver_paid_segment for s in relevant_segments)

    @property
    def effective_is_partner_paid(self):
        """Détermine si le partenaire est effectivement payé"""
        if self.booking_type == 'one_way':
            return self.is_partner_paid
        relevant_segments = self._get_relevant_segments_for_payment()
        return relevant_segments.exists() and all(s.is_partner_paid_segment for s in relevant_segments)
    
    def _calculate_round_trip_status(self):
        """Calcule le statut global pour un aller-retour"""
        segments = self.segments.all()
        if not segments.exists():
            return 'pending'
        
        statuses = [s.status for s in segments]
        
        if all(s == 'cancelled' for s in statuses):
            return 'cancelled'
        elif all(s in ['completed', 'cancelled'] for s in statuses):
            return 'completed'
        elif any(s in ['in_progress', 'approaching', 'driver_notified', 'assigned_to_driver', 'assigned_to_partner'] for s in statuses):
            return 'in_progress'
        else:
            return 'pending'
        
    @property
    def outbound_segment(self):
        """Retourne le segment aller"""
        return self.segments.filter(segment_type='outbound').first()
    
    @property
    def return_segment(self):
        """Retourne le segment retour"""
        return self.segments.filter(segment_type='return').first()
    
    @property
    def is_round_trip(self):
        """Vérifie si c'est un aller-retour"""
        return self.booking_type == 'round_trip'
    
    def __str__(self):
        return f"Booking {self.booking_number or self.id}"

    def clean_for_round_trip(self):
        """Nettoie les champs globaux lors de la conversion en aller-retour"""
        self.estimate = None
        self.save(update_fields=['estimate'])
        
    def save(self, *args, **kwargs):
        """Generate a booking number if it doesn't exist."""
        if not self.booking_number:
            self.booking_number = self.generate_booking_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_booking_number():
        """Generate a sequential booking number using the last two digits of the current year."""
        current_year_short = datetime.now().strftime("%y")
        
        pattern_prefix = f"BK-{current_year_short}-"
        
        valid_bookings = Booking.objects.filter(
            booking_number__startswith=pattern_prefix,
            booking_number__regex=r'^BK-\d{2}-\d{6}$'  
        ).order_by('-id')
        
        if valid_bookings.exists():
            last_booking = valid_bookings.first()
            try:
                # Extraire le numéro séquentiel de la fin
                last_number_str = last_booking.booking_number.split("-")[-1]
                last_number = int(last_number_str)
                next_number = last_number + 1
            except (ValueError, IndexError) as e:
                # Si conversion échoue, partir de 1
                print(f"⚠️ Erreur conversion booking_number {last_booking.booking_number}: {e}")
                next_number = 1
        else:
            # Aucun booking valide trouvé pour cette année
            next_number = 1
        
        return f"BK-{current_year_short}-{str(next_number).zfill(6)}"


class BookingSegment(models.Model):
    """
    Modèle pour gérer les segments de voyage dans un booking aller-retour
    """
    OUTBOUND = "outbound"
    RETURN = "return"
    
    SEGMENT_TYPE_CHOICES = [
        (OUTBOUND, "Aller"),
        (RETURN, "Retour"),
    ]
    
    booking = models.ForeignKey(
        'Booking',
        on_delete=models.CASCADE,
        related_name='segments',
        help_text="Booking parent contenant ce segment"
    )
    
    segment_type = models.CharField(
        max_length=20,
        choices=SEGMENT_TYPE_CHOICES,
        help_text="Type de segment (aller ou retour)"
    )
    
    estimate = models.ForeignKey(
        'Estimate',
        on_delete=models.CASCADE,
        related_name='booking_segments',
        help_text="Estimation associée à ce segment"
    )
    
    status = models.CharField(
        max_length=25,
        choices=Booking.STATUS_CHOICES,
        default=Booking.PENDING,
        help_text="Statut du segment"
    )
    
    segment_cost = models.FloatField(
        null=True, 
        blank=True,
        help_text="Coût de ce segment"
    )
    
    compensation = models.FloatField(
        null=True, 
        blank=True,
        help_text="Compensation pour ce segment (en €)"
    )
    
    commission = models.FloatField(
        null=True, 
        blank=True,
        help_text="Commission pour ce segment (en %)"
    )
    
    order = models.PositiveIntegerField(
        help_text="Ordre du segment (1=aller, 2=retour)"
    )
    
    is_driver_paid_segment = models.BooleanField(
        default=False,
        help_text="Indique si le chauffeur est payé pour ce segment"
    )
    
    is_partner_paid_segment = models.BooleanField(
        default=False,
        help_text="Indique si le partenaire est payé pour ce segment"
    )
    
    is_billable_when_cancelled = models.BooleanField(
        default=False,
        help_text="Si True, ce segment reste facturable même s'il est annulé"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du segment"
    )
    
    class Meta:
        verbose_name = "Segment de réservation"
        verbose_name_plural = "Segments de réservation"
        unique_together = ['booking', 'segment_type'] 
        ordering = ['order']
    
    @property
    def departure(self):
        """Lieu de départ du segment"""
        return self.estimate.estimation_log.departure
    
    @property
    def destination(self):
        """Lieu de destination du segment"""
        return self.estimate.estimation_log.destination
    
    @property
    def pickup_date(self):
        """Date et heure de prise en charge"""
        return self.estimate.estimation_log.pickup_date
    
    @property
    def distance_travelled(self):
        """Distance parcourue"""
        return self.estimate.estimation_log.distance_travelled
    
    @property
    def duration_travelled(self):
        """Durée du trajet"""
        return self.estimate.estimation_log.duration_travelled

    @property
    def calculated_driver_price(self):
        """Prix chauffeur calculé pour ce segment"""
        segment_cost = self.segment_cost or 0
        if self.compensation and self.compensation > 0:
            return segment_cost + self.compensation
        elif self.commission and self.commission > 0:
            commission_amount = segment_cost * (self.commission / 100)
            return segment_cost - commission_amount
        return segment_cost

    @property
    def calculated_partner_price(self):
        """Prix partenaire calculé pour ce segment"""
        return self.calculated_driver_price
    
    def __str__(self):
        segment_name = "Aller" if self.segment_type == 'outbound' else "Retour"
        return f"{segment_name} - {self.booking.booking_number} ({self.departure} → {self.destination})"

class Quote(models.Model):
    """
    Model for managing quotes.
    """
    client = models.ForeignKey(
        "utilisateurs.Client",
        on_delete=models.CASCADE,
        related_name="quotes",
        help_text="Client associated with the quote."
    )
    estimates = models.ManyToManyField(
        "Estimate",
        related_name="quotes",
        blank=True,
        help_text="Estimates included in this quote."
    )
    quote_number = models.CharField(
        max_length=255,
        null=True,
        unique=True,
        help_text="Unique number for the quote."
    )
    total_cost = models.FloatField(
        null=True,
        blank=True,
        help_text="Total cost of the quote."
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Indicates whether the quote is validated."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when the quote was created."
    )

    def save(self, *args, **kwargs):
        """
        Override save method to generate a sequential quote number if not already set.
        """
        if not self.quote_number:
            self.quote_number = self.generate_sequential_quote_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_sequential_quote_number():
        """
        Generates a sequential quote number based on the current year.
        Format: QTE-YYYY-XXXXXX
        """
        current_year = datetime.now().strftime("%Y")
        last_quote = (
            Quote.objects.filter(quote_number__startswith=f"QTE-{current_year}")
            .order_by("id")
            .last()
        )
        if last_quote:
            last_number = int(last_quote.quote_number.split("-")[-1])
            next_number = last_number + 1
        else:
            next_number = 1
        return f"QTE-{current_year}-{str(next_number).zfill(6)}"

    def calculate_total_cost(self):
        """
        Calculate the total cost of the quote based on included estimates.
        """
        total = sum(
            estimate.total_booking_cost or 0 for estimate in self.estimates.all()
        )
        self.total_cost = total
        self.save(update_fields=["total_cost"])

    def __str__(self):
        return f"Quote {self.quote_number} ({'Validated' if self.is_validated else 'Pending'})"
    
class Feedback(models.Model):
    """
    Model for managing feedback between clients and drivers.
    """
    booking = models.ForeignKey(
        "Booking",
        on_delete=models.CASCADE,
        related_name="feedbacks",
        help_text="booking associated with this feedback."
    )
    client = models.ForeignKey(
        "utilisateurs.Client",
        on_delete=models.SET_NULL,
        related_name="feedbacks",
        null=True,
        help_text="Client providing the feedback."
    )
    driver = models.ForeignKey(
        "utilisateurs.Driver",
        on_delete=models.SET_NULL,
        related_name="feedbacks",
        null=True,
        blank=True,
        help_text="Driver associated with the feedback."
    )

    client_comment = models.TextField(
        null=True,
        blank=True,
        help_text="Comment provided by the client."
    )
    driver_comment = models.TextField(
        null=True,
        blank=True,
        help_text="Comment provided by the driver."
    )
    driver_rating = models.IntegerField(
        default=0,
        help_text="Rating for the driver, from 0 to 100."
    )
    loyalty_points = models.IntegerField(
        default=10,
        help_text="Default loyalty points awarded."
    )
    client_comment_saved = models.BooleanField(
        default=False,
        help_text="Indicates if the client's comment has been saved."
    )
    driver_comment_saved = models.BooleanField(
        default=False,
        help_text="Indicates if the driver's comment has been saved."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the feedback was created."
    )

    def __str__(self):
        return f"Feedback for booking {self.booking.id}"
 
class AdditionalData(models.Model):
    """
    Model for additional data related to an invoice.
    """
    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.CASCADE,
        related_name="additional_data",
        help_text="Invoice associated with this additional data."
    )
    item = models.CharField(
        max_length=255,
        help_text="Item name or identifier."
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the additional data."
    )
    unit_price_excl_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Unit price excluding taxes."
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantity of the item."
    )
    vat = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.1,
        help_text="Value-added tax (VAT) as a decimal (e.g., 0.1 for 10%)."
    )
    total_ttc = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total price including taxes."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when the additional data was added."
    )

    def calculate_total_ttc(self):
        """
        Calculate the total price including taxes.
        """
        return (self.unit_price_excl_tax * self.quantity) * (1 + self.vat)

    def save(self, *args, **kwargs):
        """
        Override save to calculate and store the total TTC.
        """
        self.total_ttc = self.calculate_total_ttc()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item} ({self.quantity} units) - {self.total_ttc} TTC"
     
class Invoice(models.Model):
    """
    Model for managing invoices.
    """
    client = models.ForeignKey(
        "utilisateurs.Client",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="invoices",
        help_text="Client associated with the invoice."
    )
    bookings = models.ManyToManyField(
        "Booking",
        related_name="invoices",
        help_text="Bookings associated with the invoice."
    )
    invoice_number = models.CharField(
        max_length=255,
        unique=True,
        editable=False,
        help_text="Unique invoice number."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when the invoice was created."
    )
    issued_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when the invoice was issued."
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when the invoice was paid."
    )
    total_excluding_tax = models.FloatField(help_text="Total amount excluding taxes.")
    total_tax = models.FloatField(help_text="Total amount of taxes.")
    total_including_tax = models.FloatField(help_text="Total amount including taxes.")
    amount_paid = models.FloatField(
        default=0.0,
        help_text="Total amount paid towards the invoice."
    )
    remaining_balance = models.FloatField(
        default=0.0,
        help_text="Remaining balance to be paid for the invoice."
    )
    payment_method = models.ForeignKey(
        "configurations.PaymentMethod",  # Chemin complet vers PaymentMethod
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        help_text="Payment method used for the invoice."
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Due date for the invoice payment."
    )
    is_cancelled = models.BooleanField(
        default=False,
        help_text="Indicates whether the invoice is cancelled."
    )

    INVOICE_TYPE_CHOICES = [
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
        ("partially_paid", "Partially Paid"),
        ("cancelled", "Cancelled"),
    ]
    invoice_type = models.CharField(
        max_length=50,
        choices=INVOICE_TYPE_CHOICES,
        default="unpaid",
        help_text="Status of the invoice."
    )

    def save(self, *args, **kwargs):
        """
        Override save to calculate remaining balance and set invoice number if not set.
        """
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()

        self.remaining_balance = self.total_including_tax - self.amount_paid
        super().save(*args, **kwargs)
        self.update_booking_billing_status("BILLING_INVOICED")

    @staticmethod
    def generate_invoice_number():
        """
        Generate a unique sequential invoice number.
        """
        current_year = datetime.now().strftime("%Y")
        last_invoice = Invoice.objects.filter(invoice_number__startswith=f"INV-{current_year}").last()
        if last_invoice:
            last_number = int(last_invoice.invoice_number.split("-")[-1])
            next_number = last_number + 1
        else:
            next_number = 1
        return f"INV-{current_year}-{str(next_number).zfill(6)}"

    def calculate_totals(self):
        """
        Calculate totals based on bookings and additional data.
        """
        total_excluding_tax = 0
        total_tax = 0

        # Add totals from bookings
        for booking in self.bookings.all():
            if booking.total_sale_price:
                total_excluding_tax += booking.total_sale_price
                total_tax += booking.total_sale_price * 0.2  # Assuming 20% tax rate

        # Add totals from additional data
        for additional in self.additional_data.all():
            total_excluding_tax += additional.unit_price_excl_tax * additional.quantity
            total_tax += additional.unit_price_excl_tax * additional.quantity * additional.vat

        self.total_excluding_tax = total_excluding_tax
        self.total_tax = total_tax
        self.total_including_tax = total_excluding_tax + total_tax
        self.save(update_fields=["total_excluding_tax", "total_tax", "total_including_tax"])

    def update_booking_billing_status(self, status):
        """
        Update the billing status of all associated bookings.
        """
        for booking in self.bookings.all():
            booking.billing_status = status
            booking.save(update_fields=["billing_status"])

    def delete(self, *args, **kwargs):
        """
        Override delete to reset billing status of associated bookings.
        """
        self.update_booking_billing_status("BILLING_NOT_INVOICED")
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.client}"

class BookingLog(models.Model):
    """
    Model for tracking actions performed on a booking.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="Booking associated with this log entry."
    )
    user = models.ForeignKey(
        "utilisateurs.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_logs",
        help_text="User who performed the action."
    )
    action = models.CharField(
        max_length=255,
        help_text="Description of the action performed."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the action was performed."
    )

    class Meta:
        verbose_name = "Booking Log"
        verbose_name_plural = "Booking Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Log for Booking {self.booking.id} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
