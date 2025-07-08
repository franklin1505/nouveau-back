from django.urls import path
from .views import BookingDetailView, GlobalBookingStatisticsView, BookingStatisticsDetailView , BookingUpdateView

urlpatterns = [
    path('statistics/', GlobalBookingStatisticsView.as_view(), name='booking-global-statistics'),
    path('statistics/detail/', BookingStatisticsDetailView.as_view(), name='booking-detail-statistics'),
    path('<int:booking_id>/update/', BookingUpdateView.as_view(), name= 'booking-update'),
    path('<int:booking_id>/detail/', BookingDetailView.as_view(), name= 'booking-detail')
]