from django.urls import path, include

urlpatterns = [
      path('estimate/', include('courses.Estimations.urls')),  
      path('booking/', include('courses.Reservations.urls')), 
      path('logs/', include('courses.Logs.urls')),  
]
