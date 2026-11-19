from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.ratelimit import ratelimit

admin.site.login = ratelimit("admin-login", 10, 900)(admin.site.login)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
