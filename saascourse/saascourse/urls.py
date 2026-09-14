from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from saascourse.views import root_home_view
from apps.tenants.views import tenant_registration_view

from apps.users.views import universal_dashboard_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", root_home_view, name="home"),
    path("dashboard/", universal_dashboard_view, name="dashboard"),
    path("signup/", tenant_registration_view, name="signup"),
    path("tenants/", include("apps.tenants.urls", namespace="tenants")),
    path("courses/", include("apps.courses.urls", namespace="courses")),
    path("", include("apps.users.urls", namespace="users")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
