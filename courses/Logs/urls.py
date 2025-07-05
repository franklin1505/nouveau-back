from django.urls import path
from .views import BookingTimelineView, UserActionsView

urlpatterns = [
    path('<int:booking_id>/timeline/', BookingTimelineView.as_view(), name='booking-timeline'),
    path('user/actions/', UserActionsView.as_view(), name='user-actions'),
]