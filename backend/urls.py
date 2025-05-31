from django.urls import path, include

from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/usr/", include("utilisateurs.urls")),
    path("api/configurations/", include("configurations.urls")),
    path("api/reservations/", include("courses.urls")),
    path("api/parametrages/", include("parametrages.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)