from django.urls import path
from utilisateurs.Drivers.views import (
    DriverListView,
    DriverDetailView,
    DriverUpdateView,
    DriverActivationView,
    DriverBusinessAssociationView,
    GlobalDriverStatisticsView,
    DriverStatisticsDetailView
)

urlpatterns = [
    # List all drivers
    path('', DriverListView.as_view(), name='driver-list'),
    
    # Get, update, and manage a specific driver
    path('<int:pk>/', DriverDetailView.as_view(), name='driver-detail'),
    path('<int:pk>/update/', DriverUpdateView.as_view(), name='driver-update'),
    
    # New endpoints for activation/deactivation and business association
    path('<int:pk>/action/', DriverActivationView.as_view(), name='driver-activation'),
    path('<int:pk>/business-association/', DriverBusinessAssociationView.as_view(), name='driver-business-association'),
    
    # Statistics
    path('statistics/', GlobalDriverStatisticsView.as_view(), name='driver-statistics'),
    path('statistics/detail/', DriverStatisticsDetailView.as_view(), name='driver-statistics-detail'),
    
]