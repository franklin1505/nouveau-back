from django.urls import path, include

from courses.Reservations.views import BookingPaymentView, BookingValidateView, BookingCreateView, DownloadBookingPDFView, PassengerListView, UpdateTariffView


urlpatterns = [
    path('', include('courses.Reservations.Reservations_details.urls')),  
    path('validate/', BookingValidateView.as_view(), name='validate-booking'),
    path('payment/', BookingPaymentView.as_view(), name='payment-booking'),
    path('booked/', BookingCreateView.as_view(), name='create-booking'),
    path('<int:booking_id>/pdf/', DownloadBookingPDFView.as_view(), name='download_booking_pdf'),
    path('update-tariff/', UpdateTariffView.as_view(), name='update-tariff'),
    path('passengers/', PassengerListView.as_view(), name='passenger-list'),
    path('passengers/<int:client_id>/', PassengerListView.as_view(), name='passenger-list-by-client'),
]
