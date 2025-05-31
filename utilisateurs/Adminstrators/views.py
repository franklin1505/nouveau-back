from utilisateurs.Adminstrators.serializers import AdministratorUpdateSerializer
from ..models import Administrator
from rest_framework import generics,status, permissions
from configurations.helpers import create_response

class AdministratorDetailUpdateView(generics.RetrieveUpdateAPIView):
    """
    Permet de récupérer (GET) et de modifier (PUT/PATCH) les informations d'un administrateur grâce à son id.
    La réponse est formatée via la fonction create_response.
    """
    queryset = Administrator.objects.all()
    serializer_class = AdministratorUpdateSerializer
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return create_response(
            status_type='success',
            message="Détails de l'administrateur récupérés avec succès.",
            data=serializer.data,
            http_status=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return create_response(
            status_type='success',
            message="Informations de l'administrateur mises à jour avec succès.",
            data=serializer.data,
            http_status=status.HTTP_200_OK
        )
