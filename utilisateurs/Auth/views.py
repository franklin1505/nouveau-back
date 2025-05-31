from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from utilisateurs.helpers import create_response, send_reset_password_email, send_user_email
from utilisateurs.Auth.serializers import AdministratorSerializer, ClientSerializer, DriverSerializer, LoginSerializer, PartnerSerializer, PasswordChangeSerializer, PasswordResetRequestSerializer, PasswordResetValidationSerializer
from utilisateurs.models import Administrator, Client, Driver, Partner
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenRefreshView

# views pour la creation des comptes utilisateurs 
class UserCreationView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        try:
            user_type = request.data.get('user_type')
            if not user_type:
                return create_response(
                    status_type="error",
                    message="Le type d'utilisateur est requis.",
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            serializer_mapping = {
                'administrator': AdministratorSerializer,
                'partner': PartnerSerializer,
                'driver': DriverSerializer,
                'client': ClientSerializer,
            }
            serializer_class = serializer_mapping.get(user_type)
            if not serializer_class:
                return create_response(
                    status_type="error",
                    message=f"Type d'utilisateur non supporté : {user_type}.",
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            serializer = serializer_class(data=request.data)
            if serializer.is_valid():
                user, temporary_password, joint_key = serializer.save()  # Récupérer le mot de passe généré ici

                response_serializer = serializer_class(user)
                response_data = response_serializer.data

                # Ajouter le mot de passe généré à la réponse
                response_data["generated_password"] = temporary_password

                if joint_key:
                    response_data["joint_key"] = joint_key
                if user_type == "client" and user.is_partial:
                    if not user.email:
                        return create_response(
                            status_type="success",
                            message="Le client partiel a été créé avec succès, mais aucun e-mail n'a été envoyé car l'adresse e-mail n'est pas renseignée.",
                            data=response_data,
                            http_status=status.HTTP_201_CREATED
                        )
                    else:
                        try:
                            send_user_email(user, temporary_password, joint_key)
                            return create_response(
                                status_type="success",
                                message="Le client partiel a été créé avec succès, et un e-mail a été envoyé.",
                                data=response_data,
                                http_status=status.HTTP_201_CREATED
                            )
                        except Exception as e:
                            return create_response(
                                status_type="warning",
                                message="Le client partiel a été créé, mais l'e-mail n'a pas pu être envoyé.",
                                data=response_data,
                                error=str(e),
                                http_status=status.HTTP_201_CREATED
                            )

                try:
                    send_user_email(user, temporary_password, joint_key)
                    return create_response(
                        status_type="success",
                        message=f"L'utilisateur {user_type} a été créé avec succès, et un e-mail a été envoyé.",
                        data=response_data,
                        http_status=status.HTTP_201_CREATED
                    )
                except Exception as e:
                    return create_response(
                        status_type="warning",
                        message=f"L'utilisateur {user_type} a été créé, mais l'e-mail n'a pas pu être envoyé.",
                        data=response_data,
                        error=str(e),
                        http_status=status.HTTP_201_CREATED
                    )

            return create_response(
                status_type="error",
                message="Échec de la validation des données.",
                data=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return create_response(
                status_type="error",
                message="Une erreur interne est survenue.",
                error=str(e),
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# views de connexion login 
class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return create_response(
                status_type="success",
                message="Connexion réussie.",
                data=serializer.validated_data,
                http_status=status.HTTP_200_OK
            )
        return create_response(
            status_type="error",
            message="Échec de la connexion.",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )
        
#views pour reset password 
class PasswordResetRequestView(APIView):
    permission_classes= [AllowAny]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()  # Capture l'utilisateur avec l'OTP généré
            try:
                send_reset_password_email(
                    user,
                    otp_code=user.otp_code,  # Passe l'OTP à la fonction d'envoi
                    email_type="otp"
                )
                return create_response(
                    status_type="success",
                    message="Un code OTP a été envoyé à votre e-mail.",
                    data={"otp_code": user.otp_code},  # Facultatif : pour les tests ou debug
                    http_status=status.HTTP_200_OK
                )
            except Exception as e:
                return create_response(
                    status_type="error",
                    message="Une erreur est survenue lors de l'envoi de l'e-mail.",
                    error=str(e),
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return create_response(
            status_type="error",
            message="Erreur de validation des données.",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class PasswordResetValidationView(APIView):
    permission_classes= [AllowAny]

    def post(self, request):
        serializer = PasswordResetValidationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.clear_otp()  # Efface l'OTP après validation
            return create_response(
                status_type="success",
                message="Code OTP validé avec succès. Vous pouvez maintenant réinitialiser votre mot de passe.",
                data={"user_id": user.id},
                http_status=status.HTTP_200_OK
            )
        return create_response(
            status_type="error",
            message="Erreur de validation des données.",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class PasswordChangeView(APIView):
    permission_classes= [AllowAny]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            user, new_password = serializer.save()  # Récupère le nouvel utilisateur et le mot de passe
            try:
                send_reset_password_email(user, email_type="confirmation", otp_code=None, new_password=new_password)  # Passe le nouveau mot de passe
                return create_response(
                    status_type="success",
                    message="Votre mot de passe a été modifié avec succès, et un e-mail de confirmation a été envoyé.",
                    data={"username": user.username},
                    http_status=status.HTTP_200_OK
                )
            except Exception as e:
                return create_response(
                    status_type="warning",
                    message="Votre mot de passe a été modifié avec succès, mais l'e-mail de confirmation n'a pas pu être envoyé.",
                    data={"username": user.username},
                    error=str(e),
                    http_status=status.HTTP_200_OK
                )
        return create_response(
            status_type="error",
            message="Erreur de validation des données.",
            data=serializer.errors,
            http_status=status.HTTP_400_BAD_REQUEST
        )

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'user_type': user.user_type,
        }

        if user.user_type == "client":
            client = Client.objects.get(id=user.id)
            data.update(ClientSerializer(client).data)
        
        elif user.user_type == "driver":
            driver = Driver.objects.get(id=user.id)
            data.update(DriverSerializer(driver).data)
        
        elif user.user_type == "administrator":
            admin = Administrator.objects.get(id=user.id)
            data.update(AdministratorSerializer(admin).data)
        
        elif user.user_type == "partner":
            partner = Partner.objects.get(id=user.id)
            data.update(PartnerSerializer(partner).data)

        return create_response(
            status_type="success",
            message="Informations utilisateur récupérées avec succès.",
            data=data,
            http_status=status.HTTP_200_OK
        )

