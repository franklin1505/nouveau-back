import secrets
from time import timezone
from rest_framework import serializers
from django.db import transaction
from configurations.models import PaymentMethod, VehicleType
from utilisateurs.helpers import generate_secure_password, generate_secure_username, send_reset_password_email
from ..models import Administrator, Business, Client, CustomUser, Driver, Partner
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password


#serializer pour la creation des differents comptes utilisateurs 
class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id' ,'name', 'email', 'phone_number', 'address', 'business_type']


class AdministratorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)  # Généré automatiquement
    user_type = serializers.CharField(read_only=True, default="administrator")
    password = serializers.CharField(write_only=True, required=False)  # Non requis
    role = serializers.ChoiceField(choices=[('super_admin', 'Super Admin'), ('manager', 'Manager'), ('admin_simple', 'Admin Simple')])

    business_name = serializers.CharField(required=False)  # Nom du business
    business_email = serializers.EmailField(required=False)  # Email du business
    business_phone_number = serializers.CharField(required=False)  # Téléphone du business
    business_address = serializers.CharField(required=False)  # Adresse du business

    business = BusinessSerializer(read_only=True, required=False)  # Champ pour les informations de l'entreprise

    class Meta:
        model = Administrator
        fields = [
            'username', 'user_type', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'password',
            'business_name', 'business_email', 'business_phone_number', 'business_address', 'business'
        ]

    def validate(self, data):
        if 'password' not in data or not data['password']:
            data['password'] = generate_secure_password()

        if data['role'] == 'super_admin' and Administrator.objects.filter(role='super_admin').exists():
            raise serializers.ValidationError("Un seul administrateur de type 'super_admin' est autorisé.")

        if data['role'] == 'manager' and Administrator.objects.filter(role='manager').exists():
            raise serializers.ValidationError("Un seul administrateur de type 'manager' est autorisé.")

        if data['role'] == 'manager':
            if not data.get('business_name') or not data.get('business_email') or not data.get('business_phone_number'):
                raise serializers.ValidationError("Les informations du business sont obligatoires pour un manager.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data['username'] = generate_secure_username()
        password = validated_data.pop('password')
        validated_data['user_type'] = "administrator"

        business_name = validated_data.pop('business_name', None)
        business_email = validated_data.pop('business_email', None)
        business_phone_number = validated_data.pop('business_phone_number', None)
        business_address = validated_data.pop('business_address', None)

        admin = Administrator.objects.create(**validated_data)
        admin.set_password(password)
        admin.save()

        if admin.role == 'manager':
            if Business.objects.filter(business_type='my_business').exists():
                raise serializers.ValidationError("Un seul business de type 'my_business' est autorisé.")
            
            # Création de l'entreprise
            business = Business.objects.create(
                name=business_name,
                email=business_email,
                phone_number=business_phone_number,
                address=business_address,
                main_user=admin,
                business_type='my_business'
            )

            # Création des VehicleType par défaut
            default_vehicle_types = [
                {"name": "Private Sedan", "description": "Berline standard économique"},
                {"name": "Executive Sedan", "description": "Berline de prestige classe S"},
                {"name": "Van", "description": "Mini Van et Van économique"},
                {"name": "Business Van", "description": "Van de prestige classe V"},
            ]
            VehicleType.objects.bulk_create([
                VehicleType(business=business, **vehicle_type)
                for vehicle_type in default_vehicle_types
            ])

            # Création des méthodes de paiement par défaut
            PaymentMethod.add_default_payment_methods(business)

            # Ajouter l'entreprise à l'administrateur pour la réponse
            admin.business = business

        return admin, password, None

class PartnerSerializer(serializers.ModelSerializer):
    # Champs utilisateur
    username = serializers.CharField(read_only=True)  # Généré automatiquement
    password = serializers.CharField(write_only=True, required=False)
    user_type = serializers.CharField(read_only=True, default="partner")

    # Champs Business (uniquement pour l'entrée de données)
    business_name = serializers.CharField(write_only=True, required=True)  # Nom du business
    business_email = serializers.EmailField(write_only=True, required=True)  # Email du business
    business_phone_number = serializers.CharField(write_only=True, required=True)  # Téléphone du business
    business_address = serializers.CharField(write_only=True, required=False)  # Adresse du business

    # Champs Business pour la réponse
    business = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = [
            # Champs utilisateur
            'username', 'user_type', 'email', 'first_name', 'last_name', 'phone_number', 'password',
            # Champs Business (entrée/sortie)
            'business_name', 'business_email', 'business_phone_number', 'business_address', 'business'
        ]

    def validate(self, data):
        # Générer un mot de passe si non fourni
        if 'password' not in data or not data['password']:
            data['password'] = generate_secure_password()
        return data

    def get_business(self, obj):
        # Retourne les informations du business associé
        business = Business.objects.filter(partner=obj).first()
        if business:
            return {
                "name": business.name,
                "email": business.email,
                "phone_number": business.phone_number,
                "address": business.address
            }
        return None

    @transaction.atomic
    def create(self, validated_data):
        validated_data['username'] = generate_secure_username()
        password = validated_data.pop('password')
        validated_data['user_type'] = "partner"

        # Extraction des champs Business
        business_name = validated_data.pop('business_name', None)
        business_email = validated_data.pop('business_email', None)
        business_phone_number = validated_data.pop('business_phone_number', None)
        business_address = validated_data.pop('business_address', None)

        # Crée le partenaire
        partner = Partner.objects.create(**validated_data)
        partner.set_password(password)
        partner.save()

        # Crée le business associé
        Business.objects.create(
            name=business_name,
            email=business_email,
            phone_number=business_phone_number,
            address=business_address,
            partner=partner,
            business_type='partner_business'
        )

        return partner, password, None

class DriverSerializer(serializers.ModelSerializer):
    # Champs utilisateur
    username = serializers.CharField(read_only=True)  # Généré automatiquement
    password = serializers.CharField(write_only=True, required=False) 
    user_type = serializers.CharField(read_only=True, default="driver")
    # Champs spécifiques au driver
    business_id = serializers.IntegerField(required=False, allow_null=True)  # ID du business (optionnel)
    is_independent = serializers.BooleanField(default=True)  # Chauffeur indépendant ou non
    years_experience = serializers.IntegerField(default=0)  # Années d'expérience
    spoken_languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )  # Liste des langues parlées

    class Meta:
        model = Driver
        fields = [
            # Champs utilisateur
            'username', 'user_type', 'email', 'first_name', 'last_name', 'phone_number', 'password',
            # Champs spécifiques au driver
            'business_id', 'is_independent', 'years_experience', 'spoken_languages'
        ]
       
    def validate(self, data):       
        # Vérifie si le chauffeur est indépendant ou lié à un business
        is_independent = data.get('is_independent', True)
        business_id = data.get('business_id', None)

        if 'password' not in data or not data['password']:
                data['password'] = generate_secure_password()
                
        # Un chauffeur ne peut pas être à la fois indépendant et lié à un business
        if is_independent and business_id:
            raise serializers.ValidationError(
                "Un chauffeur ne peut pas être indépendant et lié à un business en même temps."
            )

        # Un chauffeur doit être soit indépendant, soit lié à un business
        if not is_independent and not business_id:
            raise serializers.ValidationError(
                "Un chauffeur doit être soit indépendant, soit lié à un business."
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        # Générer un nom d'utilisateur sécurisé
        validated_data['username'] = generate_secure_username()
        password = validated_data.pop('password')
        validated_data['user_type'] = "driver"

        # Extraction des champs spécifiques
        business_id = validated_data.pop('business_id', None)
        # Crée le chauffeur
        driver = Driver.objects.create(**validated_data)
        driver.set_password(password)
        driver.save()

        # Si le chauffeur est lié à un business
        if not driver.is_independent and business_id:
            business = Business.objects.filter(id=business_id).first()
            if not business:
                raise serializers.ValidationError("Le business spécifié n'existe pas.")
            driver.business = business
            driver.save()

        return driver,password, None

class ClientSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)  # Généré automatiquement
    password = serializers.CharField(write_only=True, required=False)
    user_type = serializers.CharField(read_only=True, default="client")
    joint_key = serializers.CharField(write_only=True, required=False)  # Clé pour lier à une agence ou société
    address = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Client
        fields = [
            'username', 'user_type', 'email', 'first_name', 'last_name', 'phone_number',
            'password', 'client_type', 'joint_key', 'is_partial', 'address'
        ]

    def validate(self, data):
        client_type = data.get('client_type')
        is_partial = data.get('is_partial', False)
        joint_key = data.get('joint_key')

        # Générer un mot de passe si non fourni
        if 'password' not in data or not data['password']:
            data['password'] = secrets.token_urlsafe(12)

        # Validation pour les clients partiels
        if is_partial:
            required_fields = ['first_name', 'last_name']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field} est requis pour les clients partiels.")
            return data

        # Validation pour les clients non partiels
        required_fields = ['email', 'phone_number', 'first_name']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(f"{field} est requis pour les clients non partiels.")

        # Validation spécifique pour les agents et collaborateurs
        if client_type == 'agency_agent':
            if not joint_key:
                raise serializers.ValidationError("La clé de liaison est requise pour un agent lié à une agence.")
            parent = Client.objects.filter(joint_key=joint_key, client_type='agency').first()
            if not parent:
                raise serializers.ValidationError("La clé fournie ne correspond à aucune agence valide.")
            data['parent'] = parent

        elif client_type == 'company_collaborator':
            if not joint_key:
                raise serializers.ValidationError("La clé de liaison est requise pour un collaborateur lié à une société.")
            parent = Client.objects.filter(joint_key=joint_key, client_type='company').first()
            if not parent:
                raise serializers.ValidationError("La clé fournie ne correspond à aucune société valide.")
            data['parent'] = parent

        return data

    @transaction.atomic
    def create(self, validated_data):
        client_type = validated_data.get('client_type', 'simple')
        is_partial = validated_data.get('is_partial', False)
        joint_key = validated_data.pop('joint_key', None)  # Capture du joint_key pour les agents et collaborateurs

        # Générer un nom d'utilisateur sécurisé
        validated_data['username'] = f"usr_{secrets.token_urlsafe(8)}"
        password = validated_data.pop('password')
        validated_data['user_type'] = "client"

        # Création du client
        client = Client.objects.create(**validated_data)
        client.set_password(password)
        client.save()

        # Générer une clé unique pour les agences et sociétés
        if client_type in ['agency', 'company'] and not client.joint_key:
            client.joint_key = secrets.token_urlsafe(18)[:25]
            client.save()

        return client, password, client.joint_key if client_type in ['agency', 'company'] else None

# serializer pour l'authentification et le login des comptes utilisateurs 

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Les champs 'username' et 'password' sont requis.")

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError("Identifiants invalides. Veuillez vérifier vos informations.")
        if not user.is_active:
            raise serializers.ValidationError("Ce compte est désactivé.")

        refresh = RefreshToken.for_user(user)

        user_info = {
            'username': user.username,
            'user_type': user.user_type,
            'user_id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }

        if user.user_type == "client":
            try:
                client = Client.objects.get(id=user.id)  
                user_info['client_type'] = client.client_type
                user_info['is_partial'] = client.is_partial
            except Client.DoesNotExist:
                user_info['client_type'] = None
                user_info['is_partial'] = False
        
        elif user.user_type == "driver":
            user_info['is_independent'] = getattr(user, 'is_independent', False)

        elif user.user_type == "administrator":
            try:
                admin = Administrator.objects.get(id=user.id)
                user_info['role'] = admin.role  # Ajouter le rôle de l'administrateur
            except Administrator.DoesNotExist:
                user_info['role'] = None

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_info': user_info
        }

#serializer pour les reset de mots de passe 

class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)

    def validate(self, data):
        identifier = data.get('identifier')
        try:
            if '@' in identifier:
                user = CustomUser.objects.get(email=identifier)
            else:
                user = CustomUser.objects.get(username=identifier)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Aucun utilisateur n'est associé à cet identifiant.")

        if not user.is_active:
            raise serializers.ValidationError("Le compte de cet utilisateur est désactivé.")

        data['user'] = user  # Ajout de l'utilisateur dans les données validées
        return data

    def save(self):
        user = self.validated_data['user']
        user.generate_otp()  # Génère et enregistre l'OTP
        return user  # Retourne l'utilisateur pour capturer l'OTP

class PasswordResetValidationSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    otp_code = serializers.CharField(required=True)

    def validate(self, data):
        identifier = data.get('identifier')
        otp_code = data.get('otp_code')

        try:
            if '@' in identifier:
                user = CustomUser.objects.get(email=identifier)
            else:
                user = CustomUser.objects.get(username=identifier)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Aucun utilisateur n'est associé à cet identifiant.")

        if not user.is_otp_valid(otp_code):
            if user.otp_expires_at and timezone.now() > user.otp_expires_at:
                raise serializers.ValidationError("Le code OTP a expiré.")
            raise serializers.ValidationError("Le code OTP est invalide.")

        return {'user': user}

class PasswordChangeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate(self, data):
        user_id = data.get('user_id')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable.")

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']

        user.password = make_password(new_password)
        user.clear_otp()  
        user.save()
        return user, new_password  # Retourne l'utilisateur et le nouveau mot de passe
