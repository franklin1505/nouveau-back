from django.urls import include, path

from configurations.views import *

urlpatterns = [
    path('vehicles/', include('configurations.Vehicles.urls')),
    path('payments/', include('configurations.Payments.urls')),
     # geston des notifications 
    path('notifications/unread/', UnreadNotificationsView.as_view(), name='unread-notifications'),
    path('notifications/archived/', ArchivedNotificationsView.as_view(), name='archived-notifications'),
    path('notifications/archive/', NotificationArchiveView.as_view(), name='archive-notifications'),

]