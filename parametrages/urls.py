from django.urls import path
from .views import (
    EmailSettingsListCreateView,
    EmailSettingsRetrieveUpdateDestroyView,
    APIKeyListCreateView,
    APIKeyRetrieveUpdateDestroyView,
    InvoiceConfigurationListCreateView,
    InvoiceConfigurationRetrieveUpdateDestroyView,
    QuoteConfigurationListCreateView,
    QuoteConfigurationRetrieveUpdateDestroyView,
    UrlsListCreateView,
    UrlsRetrieveUpdateDestroyView,
    AccessCodeListCreateView,
    AccessCodeRetrieveUpdateDestroyView,
    VATListCreateView,
    VATRetrieveUpdateDestroyView,
    StaticContentListCreateView,
    StaticContentRetrieveUpdateDestroyView,
)

urlpatterns = [
    # EmailSettings
    path(
        "email-settings/",
        EmailSettingsListCreateView.as_view(),
        name="email-settings-list-create",
    ),
    path(
        "email-settings/<int:pk>/",
        EmailSettingsRetrieveUpdateDestroyView.as_view(),
        name="email-settings-retrieve-update-destroy",
    ),
    # APIKey
    path("api-keys/", APIKeyListCreateView.as_view(), name="api-keys-list-create"),
    path(
        "api-keys/<int:pk>/",
        APIKeyRetrieveUpdateDestroyView.as_view(),
        name="api-keys-retrieve-update-destroy",
    ),
    # InvoiceConfiguration
    path(
        "invoice-configurations/",
        InvoiceConfigurationListCreateView.as_view(),
        name="invoice-configurations-list-create",
    ),
    path(
        "invoice-configurations/<int:pk>/",
        InvoiceConfigurationRetrieveUpdateDestroyView.as_view(),
        name="invoice-configurations-retrieve-update-destroy",
    ),
    # QuoteConfiguration
    path(
        "quote-configurations/",
        QuoteConfigurationListCreateView.as_view(),
        name="quote-configurations-list-create",
    ),
    path(
        "quote-configurations/<int:pk>/",
        QuoteConfigurationRetrieveUpdateDestroyView.as_view(),
        name="quote-configurations-retrieve-update-destroy",
    ),
    # Urls
    path("urls/", UrlsListCreateView.as_view(), name="urls-list-create"),
    path(
        "urls/<int:pk>/",
        UrlsRetrieveUpdateDestroyView.as_view(),
        name="urls-retrieve-update-destroy",
    ),
    # AccessCode
    path(
        "access-codes/",
        AccessCodeListCreateView.as_view(),
        name="access-codes-list-create",
    ),
    path(
        "access-codes/<int:pk>/",
        AccessCodeRetrieveUpdateDestroyView.as_view(),
        name="access-codes-retrieve-update-destroy",
    ),
    # VAT
    path("vats/", VATListCreateView.as_view(), name="vats-list-create"),
    path(
        "vats/<int:pk>/",
        VATRetrieveUpdateDestroyView.as_view(),
        name="vats-retrieve-update-destroy",
    ),
    # StaticContent
    path(
        "static-contents/",
        StaticContentListCreateView.as_view(),
        name="static-contents-list-create",
    ),
    path(
        "static-contents/<int:pk>/",
        StaticContentRetrieveUpdateDestroyView.as_view(),
        name="static-contents-retrieve-update-destroy",
    ),
]
