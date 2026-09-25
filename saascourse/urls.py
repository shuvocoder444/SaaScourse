from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.courses import views as courses_views
from apps.tenants.views import tenant_registration_view
from apps.users.views import universal_dashboard_view
from saascourse.views import root_home_view

urlpatterns = [ 
    path("admin/", admin.site.urls),
    path("", root_home_view, name="home"),
    path("dashboard/", universal_dashboard_view, name="dashboard"),
    path("signup/", tenant_registration_view, name="signup"),
    
    # Direct Public Routes for Custom Navbar
    path("courses/", courses_views.course_list, name="courses"),
    path("books/", courses_views.book_list, name="books"),
    path("books/<str:slug>/", courses_views.book_detail, name="book_detail"),
    path("resources/", courses_views.resource_list, name="resources"),
    path("resources/<str:slug>/download/", courses_views.resource_download, name="resource_download"),
    path("blog/", courses_views.blog_list, name="blog"),
    path("blog/<str:slug>/", courses_views.blog_detail, name="blog_detail"),

    path("tenants/", include("apps.tenants.urls", namespace="tenants")),
    path("courses/", include("apps.courses.urls", namespace="courses")),
    path("", include("apps.users.urls", namespace="users")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
