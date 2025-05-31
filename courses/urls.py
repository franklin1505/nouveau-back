from django.urls import path, include
from .views import TestNotificationsView, TestAnonymousNotificationsView

urlpatterns = [
      path('estimate/', include('courses.Estimations.urls')),  
      path('booking/', include('courses.Reservations.urls')),  
      path('test-notifications/', TestNotificationsView.as_view(), name='test-notifications'),
      path('test-anonymous-notifications/', TestAnonymousNotificationsView.as_view(), name='test-anonymous-notifications'),
]
