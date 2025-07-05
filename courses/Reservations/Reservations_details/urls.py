from django.urls import path
from .views import GlobalBookingStatisticsView, BookingStatisticsDetailView

urlpatterns = [
    path('statistics/', GlobalBookingStatisticsView.as_view(), name='booking-global-statistics'),
    path('statistics/detail/', BookingStatisticsDetailView.as_view(), name='booking-detail-statistics'),
]