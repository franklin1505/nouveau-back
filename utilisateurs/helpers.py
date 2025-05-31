from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from email.utils import formataddr
from django.http import JsonResponse
from django.template.loader import render_to_string
from parametrages.models import EmailSettings, Urls
from rest_framework.response import Response
from rest_framework import status
from utilisateurs.models import Administrator, Business
import string
import secrets
from rest_framework.permissions import  AllowAny

def check_manager_exists(request):
    manager_exists = Administrator.objects.filter(role='manager').exists()
    return JsonResponse({'manager_exists': manager_exists})

def generate_secure_username():
    return 'usr_' + secrets.token_hex(6)

def generate_secure_password():
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for _ in range(15))

def create_response(status_type, message, data=None, http_status=status.HTTP_200_OK, error=None):
    response_payload = {
        "status": status_type,
        "message": message,
        "data": data if data else {},
        "http_status": http_status,
    }
    if error:
        response_payload["error"] = str(error)

    return Response(response_payload, status=http_status)

def get_business_info():
    """Récupère les informations de l'entreprise ou utilise des valeurs par défaut."""
    default_business_info = {
        "name": "Votre Entreprise",
        "email": "support@votreentreprise.com",
        "phone_number": "+1234567890",
        "address": "123 Rue de l'Entreprise, Ville, Pays",
        "operator_url": "http://127.0.0.1:8000",
    }

    business = Business.objects.filter(business_type="my_business").first()
    operator_url = Urls.objects.first()

    return {
        "name": business.name if business else default_business_info["name"],
        "email": business.email if business else default_business_info["email"],
        "phone_number": business.phone_number if business else default_business_info["phone_number"],
        "address": business.address if business else default_business_info["address"],
        "operator_url": operator_url.operator_url if operator_url else default_business_info["operator_url"],
    }

def send_email(recipient_email, subject, html_content):
    
    email_settings = EmailSettings.objects.first()
    if not email_settings:
        raise Exception("Les paramètres d'e-mail ne sont pas configurés.")

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = formataddr((email_settings.email_name, email_settings.host_user))
    message["To"] = recipient_email
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(email_settings.smtp_server, 587) as server:
            server.starttls()
            server.login(email_settings.host_user, email_settings.host_password)
            server.sendmail(email_settings.host_user, recipient_email, message.as_string())
    except smtplib.SMTPException as e:
        print(f"Erreur lors de l'envoi de l'e-mail : {e}")
        raise

def send_user_email(user, temporary_password, joint_key=None):
   
    if not user.email:
        raise ValueError("L'utilisateur doit avoir une adresse e-mail valide.")

    # Génération du contexte pour l'e-mail
    context = generate_user_email_context(user, temporary_password, joint_key)
    html_content = render_to_string('emails/user_creation.html', context)
    subject = f"Création d'un compte utilisateur de type {user.user_type} sur le système NDJO"

    send_email(user.email, subject, html_content)

def generate_user_email_context(user, temporary_password, joint_key=None):

    # Mapping des types formatés
    user_type_map = {
        'administrator': 'Administrateur',
        'driver': 'Chauffeur',
        'partner': 'Partenaire',
        'client': 'Client'
    }

    client_type_map = {
        'simple': 'Client Simple',
        'agency': 'Agence',
        'company': 'Société',
        'agency_agent': 'Agent lié à une agence',
        'company_collaborator': 'Collaborateur lié à une société',
        'is_partial': 'Client Partiel'
    }

    business_info = get_business_info();
    # Contexte de base
    context = {
        "full_name": f"{user.first_name} {user.last_name}",
        "username": user.username,
        "email": user.email,
        "phone_number": user.phone_number,
        "user_type": user_type_map.get(user.user_type, user.user_type),  # Type formaté
        "temporary_password": temporary_password,
        "business_info": business_info,
        "specific_info": [],
        "joint_key": joint_key if joint_key else None,  # Inclure la clé si elle existe
    }

    # Informations spécifiques par type d'utilisateur
    if user.user_type == "administrator":
        role = getattr(user, "role", "Administrateur")
        context["specific_info"].append({"Rôle": role})
        if role == "manager" and user.businesses.exists():
            business = user.businesses.first()
            context["specific_info"].append({
                "Nom de l'entreprise": getattr(business, "name", "Non spécifié"),
                "E-mail": getattr(business, "email", "Non spécifié"),
                "Téléphone": getattr(business, "phone_number", "Non spécifié"),
                "Adresse": getattr(business, "address", "Non spécifié"),
            })

    elif user.user_type == "partner" and user.partner_businesses.exists():
        business = user.partner_businesses.first()
        context["specific_info"].append({
            "Nom de l'entreprise": getattr(business, "name", "Non spécifié"),
            "E-mail": getattr(business, "email", "Non spécifié"),
            "Téléphone": getattr(business, "phone_number", "Non spécifié"),
            "Adresse": getattr(business, "address", "Non spécifié"),
        })

    elif user.user_type == "driver":
        context["specific_info"].append({"Indépendant": "Oui" if user.is_independent else "Non"})
        if not user.is_independent and user.business:
            context["specific_info"].append({
                "Nom de l'entreprise": getattr(user.business, "name", "Non spécifié"),
                "E-mail": getattr(user.business, "email", "Non spécifié"),
                "Téléphone": getattr(user.business, "phone_number", "Non spécifié"),
                "Adresse": getattr(user.business, "address", "Non spécifié"),
            })

    elif user.user_type == "client":
        client_type = getattr(user, "client_type", "Client Simple")
        formatted_client_type = client_type_map.get(client_type, client_type)
        context["specific_info"].append({"Type de client": formatted_client_type})

        if client_type in ["agency", "company"]:
            # Récupération de l'entité par le champ parent
            entity = user if user.client_type in ['agency', 'company'] else None
            if entity:
                context["specific_info"].append({
                    "Nom de l'entité(Agence/Société)": getattr(entity, "first_name", "Non spécifié"),
                    "E-mail": getattr(entity, "email", "Non spécifié"),
                    "Téléphone": getattr(entity, "phone_number", "Non spécifié"),
                    "Adresse": getattr(entity, "address", "Non spécifié"),  # Ajout de l'adresse
                })

        if client_type in ["agency_agent", "company_collaborator"]:
            # Récupération de l'entité par le champ parent
            related_entity = user.parent
            if related_entity:
                context["specific_info"].append({
                    "Nom de l'entité(Agence/Société)liée": getattr(related_entity, "first_name", "Non spécifié"),
                    "E-mail": getattr(related_entity, "email", "Non spécifié"),
                    "Téléphone": getattr(related_entity, "phone_number", "Non spécifié"),
                    "Adresse": getattr(related_entity, "address", "Non spécifié"),  # Ajout de l'adresse
                })

    return context

def send_reset_password_email(user, otp_code=None, email_type="otp", new_password=None):
    email_settings = EmailSettings.objects.first()
    if not email_settings:
        raise Exception("Les paramètres d'e-mail ne sont pas configurés.")

    business_info = get_business_info();


    context = {
        "full_name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "username": user.username,
        "business_info": business_info,
    }

    if email_type == "otp":
        context["otp_code"] = otp_code
        subject = "Réinitialisation de votre mot de passe utilisateur"
        template_name = 'emails/password_reset.html'
    elif email_type == "confirmation":
        context["new_password"] = new_password  # Inclure le mot de passe dans le contexte
        subject = "Confirmation de changement de mot de passe utilisateur"
        template_name = 'emails/password_change_confirmation.html'
    else:
        raise ValueError("Type d'e-mail invalide.")

    email_html_content = render_to_string(template_name, context)
    
    send_email(user.email, subject, email_html_content)

    