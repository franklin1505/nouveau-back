from django.urls import path

from courses.Reservations.Reservations_details.recurring.views import RecurringCreateView, RecurringPreviewView, RecurringTypesView

from .views import (
    BookingDetailView, BookingDuplicateCreateView, BookingDuplicatePreviewView, 
    BookingReturnCreateView, BookingReturnPreviewView, BookingSegmentUpdateView, BookingTextDetailView, 
    BookingUpdateView, GlobalBookingStatisticsView, BookingStatisticsDetailView
)

urlpatterns = [
    # Routes existantes (compatibilité - utilisent maintenant les vues étendues)
    path('statistics/', GlobalBookingStatisticsView.as_view(), name='booking-global-statistics'),
    path('statistics/detail/', BookingStatisticsDetailView.as_view(), name='booking-detail-statistics'),
    
    # Routes de gestion des bookings
    path('<int:booking_id>/update/', BookingUpdateView.as_view(), name='booking-update'),
    path('<int:booking_id>/detail/', BookingDetailView.as_view(), name='booking-detail'),
    path('<int:booking_id>/getText/', BookingTextDetailView.as_view(), name='booking-text'),

    
    # Routes aller-retour
    path('<int:booking_id>/return-preview/', BookingReturnPreviewView.as_view(), name='booking-return-preview'),
    path('<int:booking_id>/create-return/', BookingReturnCreateView.as_view(), name='booking-create-return'),
    path('<int:booking_id>/segments/<str:segment_type>/', BookingSegmentUpdateView.as_view(), name='booking-segment-update'),
    
    # Routes duplication
    path('<int:booking_id>/duplicate-preview/', BookingDuplicatePreviewView.as_view(), name='booking-duplicate-preview'),
    path('<int:booking_id>/duplicate/', BookingDuplicateCreateView.as_view(), name='booking-duplicate-create'),
    
    # Routes récurrence
    path('<int:booking_id>/recurring/types/', RecurringTypesView.as_view(), name='recurring-types'),
    path('<int:booking_id>/recurring/preview/', RecurringPreviewView.as_view(), name='recurring-preview'),
    path('<int:template_id>/recurring/create/', RecurringCreateView.as_view(), name='recurring-create'),
]