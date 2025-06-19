from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.forms import ValidationError
from django.utils.timezone import now
import secrets
from django.db import transaction
import random
from django.utils import timezone
from datetime import timedelta

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError("L'utilisateur doit avoir un email")
        if not username:
            raise ValueError("L'utilisateur doit avoir un nom d'utilisateur")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        return self.create_user(username, email, first_name, last_name, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)  
    address = models.TextField(blank=True, null=True)
    date_added = models.DateTimeField(default=now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    user_choices = [
        ('administrator', 'Administrator'),
        ('driver', 'Driver'),
        ('partner', 'Partner'),
        ('client', 'Client')
    ]
    
    user_type = models.CharField(
        max_length=50,
        choices=user_choices,
        default='client'
    )

    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expires_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def clean(self):
        if CustomUser.objects.exclude(pk=self.pk).filter(email=self.email).exists():
            raise ValidationError("Un utilisateur avec cet email existe déjà.")
        if CustomUser.objects.exclude(pk=self.pk).filter(phone_number=self.phone_number).exists():
            raise ValidationError("Un utilisateur avec ce numéro de téléphone existe déjà.")
        super().clean()

    def generate_otp(self):
        self.otp_code = f"{random.randint(100000, 999999)}"  # Génère un OTP de 6 chiffres
        self.otp_expires_at = timezone.now() + timedelta(minutes=10)  # OTP valide 10 minutes
        self.save()

    def is_otp_valid(self, otp_code):
        return (
            self.otp_code == otp_code and
            self.otp_expires_at and
            timezone.now() <= self.otp_expires_at
        )

    def clear_otp(self):
        self.otp_code = None
        self.otp_expires_at = None
        self.save()
        
    def get_full_name(self):
        """
        Retourne le nom complet de l'utilisateur.
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username

    def get_short_name(self):
        """
        Retourne le prénom de l'utilisateur.
        """
        return self.first_name or self.username
        
class Administrator(CustomUser):
    role = models.CharField(
        max_length=50,
        choices=[
            ('super_admin', 'Super Admin'),
            ('manager', 'Manager'),
            ('admin_simple', 'Admin Simple')
        ],
        default='admin_simple'
    )

    class Meta:
        verbose_name = 'Administrator'
        verbose_name_plural = 'Administrators'

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"

class Partner(CustomUser):

    class Meta:
        verbose_name = 'Partner'
        verbose_name_plural = 'Partners'

    def __str__(self):
        return f"Partner: {self.first_name} {self.last_name}"
    
class Driver(CustomUser):
    business = models.ForeignKey('Business', on_delete=models.SET_NULL, null=True, blank=True)
    is_independent = models.BooleanField(default=True)
    years_experience = models.PositiveIntegerField(default=0)  # Années d'expérience
    is_validated = models.BooleanField(default=False)  # Validation du chauffeur
    spoken_languages = models.JSONField(default=list, blank=True)  # Liste des langues parlées

    class Meta:
        verbose_name = 'Driver'
        verbose_name_plural = 'Drivers'

    def __str__(self):
        return f"Driver: {self.first_name} {self.last_name}"

class Client(CustomUser):
    CLIENT_TYPES = [
        ('simple', 'Client Simple'),
        ('agency', 'Agence'),
        ('company', 'Société'),
        ('agency_agent', 'Agent lié à une agence'),
        ('company_collaborator', 'Collaborateur lié à une société'),
        ('is_partial', 'Client Partiel')
    ]

    client_type = models.CharField(
        max_length=50,
        choices=CLIENT_TYPES,
        default='simple'
    )
    is_partial = models.BooleanField(default=False)

    # Relation hiérarchique
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Clé unique pour lier les agents/collaborateurs à leur agence/société
    joint_key = models.CharField(
        max_length=25,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        # Générer une clé unique uniquement pour les agences et sociétés
        if self.client_type in ['agency', 'company'] and not self.joint_key:
            self.joint_key = secrets.token_urlsafe(18)[:25]
        super().save(*args, **kwargs)
    
    def clean(self):
        if self.client_type in ['agency_agent', 'company_collaborator'] and not self.parent:
            raise ValidationError("Un agent ou collaborateur doit être lié à une agence ou société.")
        if self.client_type == 'agency_agent' and self.parent and self.parent.client_type != 'agency':
            raise ValidationError("Un agent doit être lié à une agence.")
        if self.client_type == 'company_collaborator' and self.parent and self.parent.client_type != 'company':
            raise ValidationError("Un collaborateur doit être lié à une société.")
    
    def get_client_type_display(self):
        """
        Retourne la valeur d'affichage correspondante au client_type.
        """
        return dict(self.CLIENT_TYPES).get(self.client_type, "Inconnu")
    
    def __str__(self):
        return f"{self.get_client_type_display()} - {self.first_name} {self.last_name}"

class Contact(models.Model):
    """
    Represents a specific contact for a company (e.g., CEO, Finance Director, Client Manager).
    """
    ROLE_CHOICES = [
        ('CEO', 'Chief Executive Officer'),
        ('FINANCE', 'Finance Director'),
        ('CLIENT_MANAGER', 'Client Manager'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.role} - {self.name}"

class BusinessBaseInfo(models.Model):
    """
    Contient les informations de base communes à toutes les entreprises.
    """
    TYPE_CHOICES = [
        ('my_business', 'My Business'),
        ('partner_business', 'Partner Business'),
    ]

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=50, unique=True)
    website = models.CharField(max_length=255, blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    operation_location = models.CharField(max_length=255, blank=True, null=True)
    business_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default="partner_business")
    validation = models.BooleanField(default=False)

    class Meta:
        abstract = True

class Business(BusinessBaseInfo):
    """
    Contient les relations spécifiques aux entreprises.
    """
    main_user = models.ForeignKey(
        'Administrator',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses"
    )
    partner = models.ForeignKey(
        'Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partner_businesses'
    )
    contacts = models.ManyToManyField('Contact', blank=True, related_name="businesses")
    siren_siret = models.CharField(max_length=100, blank=True, null=True)
    naf_code = models.CharField(max_length=100, blank=True, null=True)
    vat_number = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    def clean(self):
        """
        Validation logique selon le type d'entreprise.
        """
        if self.business_type == 'my_business':
            if not self.main_user:
                raise ValidationError("A 'my_business' must have a main user of type 'Administrator'.")
            if Business.objects.filter(business_type='my_business').exclude(pk=self.pk).exists():
                raise ValidationError("There can only be one 'my_business'.")
        elif self.business_type == 'partner_business' and not self.partner:
            raise ValidationError("A 'partner_business' must have an associated partner.")

    def save(self, *args, **kwargs):
        """
        Sauvegarde sécurisée avec transaction.
        """
        if self.business_type == 'my_business':
            with transaction.atomic():
                if Business.objects.filter(business_type='my_business').exclude(pk=self.pk).exists():
                    raise ValidationError("There can only be one 'my_business'.")
        super().save(*args, **kwargs)

