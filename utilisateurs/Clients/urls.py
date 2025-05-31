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
    # List all clients
    path('', ClientListView.as_view(), name='client-list'),
    
    # Get, update, and deactivate a specific client
    path('<int:pk>/', ClientDetailView.as_view(), name='client-detail'),
    path('<int:pk>/update/', ClientUpdateView.as_view(), name='client-update'),
    
    # New endpoints for activation/deactivation and association/dissociation
    path('<int:pk>/action/', ClientActivationView.as_view(), name='client-activation'),
    path('<int:pk>/association/', ClientAssociationView.as_view(), name='client-association'),
    
    # Statistics
    path('statistics/', GlobalClientStatisticsView.as_view(), name='client-statistics'),
    path('statistics/detail/', ClientStatisticsDetailView.as_view(), name='client-statistics-detail'),
    
    # Note: Create operation is handled by UserCreationView in Auth module
]
