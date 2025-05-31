from django.urls import path

from utilisateurs.Business.views import BusinessDetailUpdateView

urlpatterns = [
    path(
        "<int:id>/",
        BusinessDetailUpdateView.as_view(),
        name="business-details-and-update",
    ),
]
