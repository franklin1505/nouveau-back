from django.urls import path
from .views import BookingDetailView, BookingDuplicateCreateView, BookingDuplicatePreviewView, BookingReturnCreateView, BookingReturnPreviewView, BookingSegmentUpdateView, GlobalBookingStatisticsView, BookingStatisticsDetailView , BookingUpdateView

urlpatterns = [
    path('statistics/', GlobalBookingStatisticsView.as_view(), name='booking-global-statistics'),
    path('statistics/detail/', BookingStatisticsDetailView.as_view(), name='booking-detail-statistics'),
    path('<int:booking_id>/update/', BookingUpdateView.as_view(), name= 'booking-update'),
    path('<int:booking_id>/detail/', BookingDetailView.as_view(), name= 'booking-detail'),
    path('<int:booking_id>/return-preview/', BookingReturnPreviewView.as_view(), name='booking-return-preview'),
    path('<int:booking_id>/create-return/', BookingReturnCreateView.as_view(), name='booking-create-return'),
    path('<int:booking_id>/segments/<str:segment_type>/', BookingSegmentUpdateView.as_view(), name='booking-segment-update'),
    path('<int:booking_id>/duplicate-preview/', BookingDuplicatePreviewView.as_view(), name='booking-duplicate-preview'),
    path('<int:booking_id>/duplicate/', BookingDuplicateCreateView.as_view(), name='booking-duplicate-create'),
]