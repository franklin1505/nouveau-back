from django.urls import path
from courses.Estimations.views import EstimateView


urlpatterns = [
    path('', EstimateView.as_view(), name='estimate-create'),
]
