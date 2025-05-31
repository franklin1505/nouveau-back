from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from .models import VAT, APIKey, AccessCode, EmailSettings, InvoiceConfiguration, QuoteConfiguration, StaticContent, Urls
from .serializers import APIKeySerializer, AccessCodeSerializer, EmailSettingsSerializer, InvoiceConfigurationSerializer, QuoteConfigurationSerializer, StaticContentSerializer, UrlsSerializer, VATSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

class BaseAPIView:
    """
    Classe de base pour formater les réponses des vues.
    """
    permission_classes = [AllowAny]  # Modifier ici

    def create_response(self, status_type, message, data=None, http_status=status.HTTP_200_OK, error=None):
        response_payload = {
            "status": status_type,
            "message": message,
            "data": data if data else {},
            "http_status": http_status,
        }
        if error:
            response_payload["error"] = str(error)
        return Response(response_payload, status=http_status)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="List retrieved successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object retrieved successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object created successfully.",
            data=response.data,
            http_status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object updated successfully.",
            data=response.data,
            http_status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return self.create_response(
            status_type="success",
            message="Object deleted successfully.",
            http_status=status.HTTP_204_NO_CONTENT
        )

class APIKeyListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = APIKey.objects.all()
    serializer_class = APIKeySerializer

class APIKeyRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = APIKey.objects.all()
    serializer_class = APIKeySerializer
    
class EmailSettingsListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = EmailSettings.objects.all()
    serializer_class = EmailSettingsSerializer

class EmailSettingsRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = EmailSettings.objects.all()
    serializer_class = EmailSettingsSerializer 

class InvoiceConfigurationListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = InvoiceConfiguration.objects.all()
    serializer_class = InvoiceConfigurationSerializer

class InvoiceConfigurationRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = InvoiceConfiguration.objects.all()
    serializer_class = InvoiceConfigurationSerializer

    def update(self, request, *args, **kwargs):
        # Forcer la mise à jour partielle
        kwargs['partial'] = True
        # Appeler la méthode update du parent (BaseAPIView va ensuite formater la réponse)
        return super().update(request, *args, **kwargs)

class QuoteConfigurationListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = QuoteConfiguration.objects.all()
    serializer_class = QuoteConfigurationSerializer

class QuoteConfigurationRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = QuoteConfiguration.objects.all()
    serializer_class = QuoteConfigurationSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class UrlsListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = Urls.objects.all()
    serializer_class = UrlsSerializer

class UrlsRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Urls.objects.all()
    serializer_class = UrlsSerializer

class AccessCodeListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = AccessCode.objects.all()
    serializer_class = AccessCodeSerializer

class AccessCodeRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = AccessCode.objects.all()
    serializer_class = AccessCodeSerializer
    
class VATListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = VAT.objects.all()
    serializer_class = VATSerializer

class VATRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = VAT.objects.all()
    serializer_class = VATSerializer
    
class StaticContentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = StaticContent.objects.all()
    serializer_class = StaticContentSerializer


class StaticContentRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = StaticContent.objects.all()
    serializer_class = StaticContentSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
