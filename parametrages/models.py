from django.db import models
from django.core.validators import URLValidator
from django.forms import ValidationError
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class EmailSettings(models.Model):
    """
    Modèle pour les paramètres d'email.
    """
    email_name = models.CharField(max_length=100, help_text="email name.")
    smtp_server = models.CharField(max_length=100, help_text="SMTP server address.")
    host_user = models.CharField(max_length=100, help_text="Email host user.")
    host_password = models.CharField(max_length=100, help_text="Email host password.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when the configuration was created.")

    def __str__(self):
        return f"Email Settings for {self.host_user}"

class APIKey(models.Model):
    """
    Modèle pour les clés API.
    """
    key_value = models.CharField(max_length=100, help_text="API key value.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when the API key was created.")

    def __str__(self):
        return f"API Key: {self.key_value[:6]}..."  # Afficher seulement une partie de la clé pour éviter les fuites

class BaseConfiguration(models.Model):
    """
    Modèle de base pour les configurations de factures et devis.
    """
    business = models.ForeignKey(
        "utilisateurs.Business",
        on_delete=models.CASCADE,
        related_name="%(class)s_configurations",
        help_text="Business associated with this configuration."
    )
    introductory_text = models.TextField(blank=True, null=True, help_text="Introductory text for the document.")
    default_footer = models.TextField(blank=True, null=True, help_text="Default footer text.")
    general_terms = models.TextField(blank=True, null=True, help_text="General terms and conditions.")
    default_payment_method = models.ForeignKey(
        "configurations.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_default_payment_methods",
        help_text="Default payment method associated with this configuration."
    )
    late_interest = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Interest rate or penalties for late payments."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date when the configuration was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Date when the configuration was last updated.")

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.business.name} Configuration ({self.__class__.__name__})"

class InvoiceConfiguration(BaseConfiguration):
    """
    Configuration spécifique pour les factures.
    """
    class Meta:
        verbose_name = "Invoice Configuration"
        verbose_name_plural = "Invoice Configurations"

class QuoteConfiguration(BaseConfiguration):
    """
    Configuration spécifique pour les devis.
    """
    class Meta:
        verbose_name = "Quote Configuration"
        verbose_name_plural = "Quote Configurations"

class Urls(models.Model):
    """
    Modèle pour les URLs des opérateurs.
    """
    operator_url = models.CharField(
        max_length=255,
        validators=[URLValidator()],
        help_text="URL for the operator."
    )
    interface_url = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        validators=[URLValidator()],
        help_text="URL for the operator."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date when the URL was created.")

    def __str__(self):
        return f"Operator URL: {self.operator_url}"
    
class AccessCode(models.Model):
    """
    Modèle pour les codes d'accès.
    """
    standard_password = models.CharField(
        max_length=6, 
        default='000000',
        help_text="Standard access password (6 digits)."
    )
    admin_password = models.CharField(
        max_length=6, 
        default='123456',
        help_text="Admin access password (6 digits)."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date when the access code was created.")

    def clean(self):
        """
        Valide que les mots de passe contiennent exactement 6 chiffres.
        """
        if not self.standard_password.isdigit() or len(self.standard_password) != 6:
            raise ValidationError("The standard password must be exactly 6 digits.")
        if not self.admin_password.isdigit() or len(self.admin_password) != 6:
            raise ValidationError("The admin password must be exactly 6 digits.")

    def __str__(self):
        return f"AccessCode created at {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def create_default_access_codes(cls):
        """
        Crée les codes d'accès par défaut (standard et admin) s'ils n'existent pas déjà.
        """
        if not cls.objects.exists():
            cls.objects.create(
                standard_password='000000',
                admin_password='123456'
            )

class VAT(models.Model):
    """
    Modèle pour gérer les informations sur la TVA (Taxe sur la Valeur Ajoutée).
    """
    VAT_TYPE_CHOICES = [
        ('simple_transfer', 'Transfert Simple'),
        ('made_available', 'Mise à Disposition'),
    ]

    name = models.CharField(
        max_length=50,
        choices=VAT_TYPE_CHOICES,
        help_text="Type de TVA (Transfert Simple ou Mise à Disposition)."
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Taux de TVA en pourcentage (10% par défaut)."
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description de la TVA."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de création de la TVA."
    )

    def __str__(self):
        return f"{self.get_name_display()} - {self.rate}%"

    @classmethod
    def create_default_vat_types(cls):
        """
        Crée les deux types de TVA par défaut (Transfert Simple et Mise à Disposition).
        """
        if not cls.objects.filter(name='simple_transfer').exists():
            cls.objects.create(
                name='simple_transfer',
                rate=10.00,
                description="TVA applicable pour les transferts simples."
            )

        if not cls.objects.filter(name='made_available').exists():
            cls.objects.create(
                name='made_available',
                rate=10.00,
                description="TVA applicable pour les mises à disposition."
            )

class StaticContent(models.Model):
    """
    Modèle pour gérer les contenus statiques utilisés dans les templates PDF.
    """
    service_description = models.TextField(
        help_text="Description du service de voiture de transport avec chauffeur."
    )
    legal_notice_1 = models.TextField(
        help_text="Première mention légale (Billet collectif : Arrêté du 14 Février 1986 - Article 5)."
    )
    legal_notice_2 = models.TextField(
        help_text="Deuxième mention légale (Ordre de mission : Arrêté du 6 Janvier 1993 - Article 3)."
    )
    vehicle_rental_description = models.TextField(
        help_text="Description de la location de véhicule avec chauffeur."
    )
    pricing_details = models.TextField(
        help_text="Détails sur les tarifs et les conditions de facturation."
    )
    default_footer = models.TextField(
        help_text="Contenu du pied de page pour les PDF.",
        default="",  # Valeur par défaut vide
    )

    def __str__(self):
        return "Static Content for PDF Templates"

    @classmethod
    def create_default_static_content(cls):
        """
        Crée les contenus statiques par défaut pour les templates PDF.
        """
        if not cls.objects.exists():  # Vérifie si la table est vide
            cls.objects.create(
                service_description="Service de voiture de transport avec chauffeur.",
                legal_notice_1="Billet collectif : Arrêté du 14 Février 1986 - Article 5.",
                legal_notice_2="Ordre de mission : Arrêté du 6 Janvier 1993 - Article 3.",
                vehicle_rental_description="Location de véhicule avec chauffeur.",
                pricing_details=(
                    "Le tarif ci-dessus inclut toutes les charges : parking, péage et attente "
                    "du chauffeur à la prise en charge (15 minutes à la gare, 60 minutes à "
                    "l'aéroport et 15 minutes aux autres adresses). Au-delà de ce temps "
                    "d’attente, le client est notifié avant le décompte du temps additionnel "
                    "facturé. Les retards de train et d’avion ne sont pas facturés."
                ),
                default_footer=(
                    "Merci de faire confiance à notre service. Pour toute question, "
                    "contactez-nous à contact@entreprise.com."
                ),
            )

# Signal pour créer les contenus statiques par défaut après la migration
@receiver(post_migrate)
def create_default_static_content(sender, **kwargs):
    if sender.name == 'parametrages':  
        StaticContent.create_default_static_content()

@receiver(post_migrate)
def create_default_vat_types(sender, **kwargs):
    if sender.name == 'parametrages': 
        VAT.create_default_vat_types()
        
@receiver(post_migrate)
def create_default_access_codes(sender, **kwargs):
    if sender.name == 'parametrages':  
        AccessCode.create_default_access_codes()