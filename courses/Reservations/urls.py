from django.urls import path

from courses.Reservations.views import BookingValidateView, BookingCreateView, DownloadBookingPDFView


urlpatterns = [
    path('validate/', BookingValidateView.as_view(), name='validate-booking'),
    path('booked/', BookingCreateView.as_view(), name='create-booking'),
    path('<int:booking_id>/pdf/', DownloadBookingPDFView.as_view(), name='download_booking_pdf'),

]
