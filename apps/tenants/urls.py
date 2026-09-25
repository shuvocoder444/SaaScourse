from django.urls import path
from apps.tenants import views

app_name = "tenants"

urlpatterns = [
    path("signup/", views.tenant_registration_view, name="register"),
    path("settings/", views.tenant_branding_settings_view, name="settings"),
    path("platform/dashboard/", views.platform_admin_dashboard_view, name="platform_dashboard"),
    path("verify-domain/", views.verify_custom_domain_view, name="verify_domain"),
    path("verify-custom-domain/", views.verify_custom_domain_view, name="verify_custom_domain"),
    path("api/caddy-check/", views.caddy_ask_domain, name="caddy_ask"),
    path("send-test-sms/", views.send_test_sms_view, name="send_test_sms"),
]
