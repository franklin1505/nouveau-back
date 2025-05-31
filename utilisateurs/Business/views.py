from rest_framework import generics,status, permissions
from ..models import Business
from .serializers import BusinessSerializer
from configurations.helpers import create_response
from rest_framework.parsers import MultiPartParser, FormParser


class BusinessDetailUpdateView(generics.RetrieveUpdateAPIView):
    """
    Permet d'afficher (GET) et modifier (PUT/PATCH) une entreprise via son id.
    La réponse est formatée via create_response.
    """
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    lookup_field = 'id'
    parser_classes = [MultiPartParser, FormParser]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return create_response(
            status_type='success',
            message="Détails de l'entreprise récupérés avec succès.",
            data=serializer.data,
            http_status=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Mise à jour partielle pour ne modifier que les champs envoyés
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return create_response(
            status_type='success',
            message="Entreprise mise à jour avec succès.",
            data=serializer.data,
            http_status=status.HTTP_200_OK
        )