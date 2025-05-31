from datetime import timezone
from django.db import models
from django.forms import ValidationError
from django.utils.timezone import now
from django.conf import settings

# models pour la gestion des vehicules 
class VehicleType(models.Model):
    """
    Type de véhicule associé à une entreprise.
    """

    business = models.ForeignKey(
        "utilisateurs.Business", on_delete=models.CASCADE, related_name="vehicle_types"
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

    def __str__(self):
        return self.name

class VehicleBase(models.Model):
    """
    Informations de base sur un véhicule.
    """

    business = models.ForeignKey(
        "utilisateurs.Business", on_delete=models.CASCADE, related_name="vehicles"
    )
    vehicle_type = models.ForeignKey(
        "VehicleType",
        on_delete=models.CASCADE,
        related_name="vehicles",
        help_text="Type de véhicule",
    )
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    manufacture_year = models.PositiveIntegerField(blank=True, null=True)
    registration_number = models.CharField(max_length=100, null=True, blank=True,)
    image = models.ImageField(upload_to="image/", blank=True, null=True)
    validation = models.BooleanField(default=False)

    # Caractéristiques techniques
    fuel_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("petrol", "Petrol"),
            ("diesel", "Diesel"),
            ("electric", "Electric"),
            ("hybrid", "Hybrid"),
        ],
    )
    engine = models.CharField(max_length=50, blank=True, null=True)
    interior_color = models.CharField(max_length=50, blank=True, null=True)
    exterior_color = models.CharField(max_length=50, blank=True, null=True)
    power = models.PositiveIntegerField(
        blank=True, null=True, help_text="Power in horsepower"
    )
    length = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Length in meters",
    )
    transmission = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("manual", "Manual"),
            ("automatic", "Automatic"),
        ],
    )

    class Meta:
        abstract = True

class Vehicle(VehicleBase):
    """
    Informations détaillées et relations d'un véhicule.
    """

    passenger_capacity = models.PositiveIntegerField(
        help_text="Maximum number of passengers"
    )
    luggage_capacity = models.CharField(max_length=255)
    base_location = models.CharField(max_length=255)
    availability_type = models.CharField(
        max_length=50,
        choices=[
            ("immediate", "Immediate"),
            ("delayed", "Delayed"),
            ("on_demand", "On Demand"),
        ],
        default="immediate",
        help_text="Availability type of the vehicle",
    )
    availability_time = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Time in hours before availability (only for 'delayed' vehicles)",
    )
    price = models.OneToOneField(
        "Price", on_delete=models.CASCADE, related_name="vehicle", null=True, blank=True
    )  # Association one-to-one avec le prix

    def clean(self):
        if self.availability_type == "delayed" and not self.availability_time:
            raise ValidationError(
                "The 'availability_time' field is required for vehicles with 'delayed' availability type."
            )
        if self.availability_type != "delayed" and self.availability_time:
            raise ValidationError(
                "The 'availability_time' field can only be set for vehicles with 'delayed' availability type."
            )
            
        valid_types = ["immediate", "delayed", "on_demand"]
        if self.availability_type not in valid_types:
            raise ValidationError(f"Type de disponibilité invalide : {self.availability_type}")
        if self.availability_type == "delayed" and not self.availability_time:
            raise ValidationError("Le champ 'availability_time' est requis pour les véhicules différés.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.vehicle_type.name}) - {self.registration_number or 'Unregistered'}"

class Price(models.Model):
    """
    Tarification associée à un véhicule.
    """

    price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_per_duration = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    default_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Prices for Vehicle"


# models pour la gestion des tarifications 
class Adjustment(models.Model):
    """
    Modèle de base pour les réductions et majorations.
    """

    adjustment_type = models.CharField(
        max_length=20,
        choices=[("discount", "Discount"), ("increase", "Increase")],
        default="discount",
        help_text="Type of adjustment",
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Percentage to apply (positive for increase, negative for discount)",
    )
    fixed_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Fixed value to add or subtract",
    )
    created_at = models.DateTimeField(auto_now_add=True)

class PromoCode(models.Model):
    """
    Gestion des codes promotionnels pour appliquer des réductions.
    """

    business = models.ForeignKey(
        "utilisateurs.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="promo_codes",
        help_text="Business linked to this promo code.",
    )
    code = models.CharField(max_length=50, unique=True, help_text="Unique promo code.")
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Percentage discount (e.g., 10.00 for 10%).",
    )
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Fixed discount amount (e.g., 5.00 €).",
    )
    usage_count = models.PositiveIntegerField(
        default=0, help_text="Number of times the promo code has been used."
    )
    usage_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Maximum number of times the promo code can be used.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

class Package(models.Model):
    """
    Modèle de base pour les forfaits.
    """

    package_type = models.CharField(
        max_length=20,
        choices=[("classic", "Classic"), ("radius", "Radius")],
        default="classic",
        help_text="Type of package",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Flat rate.")
    departure_latitude = models.DecimalField(
        max_digits=12, decimal_places=8, help_text="Departure point latitude."
    )
    departure_longitude = models.DecimalField(
        max_digits=12, decimal_places=8, help_text="Departure point longitude."
    )
    arrival_latitude = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        blank=True,
        null=True,
        help_text="Arrival point latitude.",
    )
    arrival_longitude = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        blank=True,
        null=True,
        help_text="Arrival point longitude.",
    )
    center_latitude = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        blank=True,
        null=True,
        help_text="Central point latitude.",
    )
    center_longitude = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        blank=True,
        null=True,
        help_text="Central point longitude.",
    )
    radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Radius in kilometers around the central point.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

class TariffRule(models.Model):
    """
    Modèle pour les règles tarifaires associées aux véhicules.
    """

    RULE_TYPE_CHOICES = [
        ("adjustment", "Réduction/Majoration"),
        ("package", "Forfait"),
        ("promo_code", "Code Promo"),
    ]
    ACTION_TYPE_CHOICES = [
        ("scheduled_adjustment", "Scheduled Adjustment"),
        ("fixed_adjustment", "Fixed Adjustment"),
        ("classic_package", "Classic Package"),
        ("radius_package", "Radius Package"),
        ("promo_code", "Promo Code"),
    ]

    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.CASCADE,
        related_name="tariff_rules",
        help_text="Vehicle this tariff rule applies to.",
    )
    name = models.CharField(max_length=255, help_text="Name of the tariff rule.")
    description = models.TextField(
        blank=True, null=True, help_text="Description of the tariff rule."
    )
    rule_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=RULE_TYPE_CHOICES,
        help_text="Type of the tariff rule (adjustment, package, promo code, etc.).",
    )
    action_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=ACTION_TYPE_CHOICES,
        help_text="Type of the action ",
    )

    # Validity properties
    start_date = models.DateTimeField(
        blank=True, null=True, help_text="Start date of validity."
    )
    end_date = models.DateTimeField(
        blank=True, null=True, help_text="End date of validity."
    )
    days_of_week = models.JSONField(
        blank=True,
        null=True,
        help_text="Specific days of the week (e.g., ['monday', 'tuesday', 'wednesday']).",
    )
    specific_hours = models.JSONField(
        blank=True,
        null=True,
        help_text="Specific time slots (e.g., [{'start': '08:00', 'end': '12:00'}]).",
    )
    application_date = models.DateField(
        blank=True, null=True, help_text="Specific date for application"
    )

    active = models.BooleanField(
        default=True, help_text="Is this tariff rule currently active?"
    )
    priority = models.PositiveIntegerField(
        default=1, help_text="Priority of the tariff rule (1 = lowest priority)."
    )

    # Client-related properties
    available_to_all = models.BooleanField(
        default=True, help_text="Is this tariff rule available to all clients?"
    )
    specific_clients = models.ManyToManyField(
        "utilisateurs.Client",
        blank=True,
        related_name="specific_tariff_rules",
        help_text="Specific clients allowed (only if available_to_all=False).",
    )
    excluded_clients = models.ManyToManyField(
        "utilisateurs.Client",
        blank=True,
        related_name="excluded_tariff_rules",
        help_text="Clients excluded from this tariff rule.",
    )

    # Relationships with concrete models
    adjustment = models.OneToOneField(
        "Adjustment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tariff_rules",
        help_text="Associated adjustment (discount or increase).",
    )
    package = models.OneToOneField(
        "Package",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tariff_rules",
        help_text="Associated package (fixed rate or radius).",
    )
    promo_code = models.OneToOneField(
        "PromoCode",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tariff_rules",
        help_text="Associated promo code.",
    )

    # Validation Functions
    def is_active(self, check_date=None):
        """
        Vérifie si cette règle est active à une date/heure donnée.
        """
        now = check_date or timezone.now()

        if not self.active:
            return False

        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False

        if self.days_of_week:
            current_day = now.strftime("%A").lower()
            if current_day not in [day.lower() for day in self.days_of_week]:
                return False

        if self.specific_hours:
            current_time = now.strftime("%H:%M")
            for time_range in self.specific_hours:
                if time_range["start"] <= current_time <= time_range["end"]:
                    return True
            return False

        return True

    def is_accessible_by(self, client):
        """
        Vérifie si cette règle est applicable à un client spécifique.
        """
        if client in self.excluded_clients.all():
            return False
        if not self.available_to_all and client not in self.specific_clients.all():
            return False
        return True

    def is_applicable(self, client, check_date=None):
        """
        Vérifie si cette règle est applicable à un client spécifique à une date/heure donnée.
        """
        return self.is_active(check_date) and self.is_accessible_by(client)

# models pour la gestions des payements 
class PaymentMethod(models.Model):
    """
    Modèle pour les méthodes de paiement.
    """

    business = models.ForeignKey(
        "utilisateurs.Business",
        on_delete=models.CASCADE,
        related_name="payment_methods",
        help_text="Business associated with this payment method.",
    )
    name = models.CharField(
        max_length=255, unique=True, help_text="Name of the payment method."
    )
    description = models.TextField(
        blank=True, null=True, help_text="Description of the payment method."
    )
    is_active = models.BooleanField(
        default=False, help_text="Is this payment method active?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.business.name})"

    @staticmethod
    def add_default_payment_methods(business):
        """
        Ajoute les méthodes de paiement par défaut pour une entreprise donnée.
        """
        default_methods = [
            {"name": "onboard_payment", "description": "Payment onboard"},
            {"name": "bank_transfer", "description": "Payment by bank transfer"},
            {"name": "paypal_payment", "description": "Payment via PayPal"},
            {"name": "stripe_payment", "description": "Payment via Stripe"},
            {"name": "account_payment", "description": "Payment on account"},
        ]
        for method_data in default_methods:
            PaymentMethod.objects.get_or_create(
                business=business,
                name=method_data["name"],
                defaults={"description": method_data["description"]},
            )

class PaymentConfigurationBase(models.Model):
    """
    Base model for payment configurations.
    """

    business = models.ForeignKey(
        "utilisateurs.Business",
        on_delete=models.CASCADE,
        related_name="%(class)s_configurations",
        help_text="Business associated with this payment method.",
    )
    payment_method = models.ForeignKey(
        "PaymentMethod",
        on_delete=models.SET_NULL,
        null=True ,
        related_name="%(class)s_configuration",
        help_text="Associated payment method.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.payment_method.name} ({self.business.name})"

class BankTransferPayment(PaymentConfigurationBase):
    """
    Configuration spécifique pour les virements bancaires.
    """

    bank_name = models.CharField(
        max_length=100, null=True, help_text="Name of the bank."
    )
    iban = models.CharField(
        max_length=34, help_text="International Bank Account Number (IBAN)."
    )
    bic = models.CharField(max_length=11, help_text="Bank Identifier Code (BIC).")
    account_label = models.CharField(max_length=100, help_text="Account label.")

class PayPalPayment(PaymentConfigurationBase):
    """
    Configuration spécifique pour PayPal.
    """

    client_id = models.CharField(max_length=255, help_text="PayPal Client ID.")
    client_secret = models.CharField(max_length=255, help_text="PayPal Client Secret.")
    api_url = models.URLField(
        default="https://api-m.sandbox.paypal.com",
        help_text="API URL for PayPal integration.",
    )

class StripePayment(PaymentConfigurationBase):
    """
    Configuration spécifique pour Stripe.
    """

    secret_key = models.CharField(
        max_length=255, blank=True, null=True, help_text="Stripe Secret Key."
    )
    publishable_key = models.CharField(
        max_length=255, blank=True, null=True, help_text="Stripe Publishable Key."
    )
    redirect_url = models.URLField(
        blank=True, null=True, help_text="Redirect URL for Stripe integration."
    )

#config globales 
class Attribute(models.Model):
    """
    Modèle pour les attributs liés à une entreprise.
    """

    business = models.ForeignKey("utilisateurs.Business", on_delete=models.CASCADE)
    attribute_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    maximum_quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.attribute_name} ({self.business.name})"

class MeetingPlace(models.Model):
    """
    Modèle pour les lieux de rendez-vous.
    """

    address = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.address

from django.conf import settings
from django.utils.timezone import now

class Notification(models.Model):
    STATUS_CHOICES = [
        ("unread", "Non lue"),
        ("archived", "Archivée"),
    ]

    TYPE_CHOICES = [
        ("expiration", "Expiration"),
        ("usage_limit", "Limite d'utilisation atteinte"),
    ]

    title = models.CharField(max_length=255, help_text="Titre de la notification.")
    message = models.TextField(help_text="Contenu de la notification.")
    type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        help_text="Type de la notification (expiration, limite d'utilisation, etc.)."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unread",
        help_text="Statut de la notification (non lue, archivée)."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date de création de la notification.")
    archived_at = models.DateTimeField(blank=True, null=True, help_text="Date d'archivage de la notification.")
    related_rule = models.ForeignKey(
        "TariffRule",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
        help_text="Règle tarifaire liée à la notification."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Utilisateur associé à la notification."
    )

    def archive(self):
        """
        Marquer la notification comme archivée.
        """
        self.status = "archived"
        self.archived_at = now()
        self.save()

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
