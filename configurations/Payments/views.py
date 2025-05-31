from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from configurations.Payments.serializers import BankTransferPaymentSerializer, PayPalPaymentSerializer, PaymentMethodSerializer, StripePaymentSerializer
from configurations.models import BankTransferPayment, PayPalPayment, PaymentMethod, StripePayment

class BaseAPIView:
    """
    Classe de base pour formater les réponses des vues.
    """
    permission_classes = [AllowAny]
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
        
  
class PaymentMethodListCreateView(BaseAPIView, generics.ListCreateAPIView):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer

class PaymentMethodRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer


class BankTransferPaymentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """
    Permet de lister et de créer des configurations de paiement par virement bancaire.
    Réponses formatées via BaseAPIView.
    """
    queryset = BankTransferPayment.objects.all()
    serializer_class = BankTransferPaymentSerializer


class BankTransferPaymentRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    """
    Permet de récupérer, mettre à jour (partiellement) et supprimer une configuration de paiement par virement bancaire.
    Réponses formatées via BaseAPIView.
    """
    queryset = BankTransferPayment.objects.all()
    serializer_class = BankTransferPaymentSerializer

    def update(self, request, *args, **kwargs):
        # Forcer la mise à jour partielle (PATCH)
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class PayPalPaymentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """
    Permet de lister et de créer des configurations de paiement PayPal.
    Réponses formatées via BaseAPIView.
    """
    queryset = PayPalPayment.objects.all()
    serializer_class = PayPalPaymentSerializer


class PayPalPaymentRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    """
    Permet de récupérer, mettre à jour (partiellement) et supprimer une configuration de paiement PayPal.
    Réponses formatées via BaseAPIView.
    """
    queryset = PayPalPayment.objects.all()
    serializer_class = PayPalPaymentSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class StripePaymentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """
    Permet de lister et de créer des configurations de paiement Stripe.
    Réponses formatées via BaseAPIView.
    """
    queryset = StripePayment.objects.all()
    serializer_class = StripePaymentSerializer


class StripePaymentRetrieveUpdateDestroyView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):

    queryset = StripePayment.objects.all()
    serializer_class = StripePaymentSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)