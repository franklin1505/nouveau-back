from django.urls import path
from django.urls import path
from .views import AdministratorDetailUpdateView

urlpatterns = [
    path(
        "<int:id>/",
        AdministratorDetailUpdateView.as_view(),
        name="administrator_detail_update",
    ),
]
