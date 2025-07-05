from django.urls import path
from utilisateurs.Clients.views import (
    ClientListView,
    ClientDetailView,
    ClientUpdateView,
    ClientActivationView,
    ClientAssociationView,
    GlobalClientStatisticsView,
    ClientStatisticsDetailView
)

urlpatterns = [
    path('', ClientListView.as_view(), name='client-list'),
    path('<int:pk>/', ClientDetailView.as_view(), name='client-detail'),
    path('<int:pk>/update/', ClientUpdateView.as_view(), name='client-update'),
    path('<int:pk>/action/', ClientActivationView.as_view(), name='client-activation'),
    path('<int:pk>/association/', ClientAssociationView.as_view(), name='client-association'),
    path('statistics/', GlobalClientStatisticsView.as_view(), name='client-statistics'),
    path('statistics/detail/', ClientStatisticsDetailView.as_view(), name='client-statistics-detail'),
]
