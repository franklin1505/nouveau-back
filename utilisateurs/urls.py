from django.urls import include, path

from utilisateurs.helpers import check_manager_exists
from utilisateurs.views import CurrentUserView


urlpatterns = [
    path('drivers/', include('utilisateurs.Drivers.urls')),  
    path('partners/', include('utilisateurs.Partners.urls')),  
    path('admin/', include('utilisateurs.Adminstrators.urls')),  
    path('clients/', include('utilisateurs.Clients.urls')),  
    path('auth/', include('utilisateurs.Auth.urls')), 
    path('business/', include('utilisateurs.Business.urls')),  
    path('check-manager/', check_manager_exists, name='check_manager_exists'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
          
]