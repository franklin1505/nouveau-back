from django.urls import path

from configurations.Payments.views import (
    BankTransferPaymentListCreateView,
    BankTransferPaymentRetrieveUpdateDestroyView,
    PayPalPaymentListCreateView,
    PayPalPaymentRetrieveUpdateDestroyView,
    PaymentMethodListCreateView,
    PaymentMethodRetrieveUpdateDestroyView,
    StripePaymentListCreateView,
    StripePaymentRetrieveUpdateDestroyView,
)

urlpatterns = [
    path(
        "payement-method/",
        PaymentMethodListCreateView.as_view(),
        name="payement-method-list-create",
    ),
    path(
        "payement-method/<int:pk>/",
        PaymentMethodRetrieveUpdateDestroyView.as_view(),
        name="payement-method-retrieve-update-destroy",
    ),
    path(
        "bank-transfer/",
        BankTransferPaymentListCreateView.as_view(),
        name="bank-transfer-list-create",
    ),
    path(
        "bank-transfer/<int:pk>/",
        BankTransferPaymentRetrieveUpdateDestroyView.as_view(),
        name="bank-transfer-retrieve-update-destroy",
    ),
    path(
        "paypal/", 
         PayPalPaymentListCreateView.as_view(),
         name="paypal-list-create"
    ),
    path(
        "paypal/<int:pk>/",
        PayPalPaymentRetrieveUpdateDestroyView.as_view(),
        name="paypal-retrieve-update-destroy",
    ),
    path(
        "stripe/",
        StripePaymentListCreateView.as_view(),
        name="stripe-list-create"
    ),
    path(
        "stripe/<int:pk>/",
        StripePaymentRetrieveUpdateDestroyView.as_view(),
        name="stripe-retrieve-update-destroy",
    ),
]
