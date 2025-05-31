
from rest_framework import generics, status
from utilisateurs.helpers import create_response
from utilisateurs.models import Administrator, Client, CustomUser, Driver, Partner
from .serializers import UserDynamicSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserDynamicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # On sélectionne le queryset du modèle spécifique en fonction du type d'utilisateur
        if user.user_type == 'administrator':
            qs = Administrator.objects.all().prefetch_related('businesses__vehicles', 'businesses__driver_set')
        elif user.user_type == 'partner':
            qs = Partner.objects.all().prefetch_related('partner_businesses__vehicles', 'partner_businesses__driver_set')
        elif user.user_type == 'client':
            qs = Client.objects.all().prefetch_related('children', 'parent')
        elif user.user_type == 'driver':
            qs = Driver.objects.all().select_related('business')
        else:
            qs = CustomUser.objects.all()
        return qs

    def get_object(self):
        qs = self.get_queryset()
        return qs.get(pk=self.request.user.pk)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return create_response(
                status_type="success",
                message="Utilisateur récupéré avec succès",
                data=serializer.data
            )
        except Exception as e:
            return create_response(
                status_type="error",
                message="Erreur lors de la récupération de l'utilisateur",
                error=str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )