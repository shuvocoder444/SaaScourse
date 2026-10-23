from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<int:order_id>/", views.start_payment, name="start_payment"),
    path("pay/order/<str:order_id>/", views.start_payment, name="start_payment_by_no"),
    path("gateway-webhook/", views.gateway_webhook, name="gateway_webhook"),
    path("return/", views.payment_return_view, name="payment_return"),

    # Direct Webhook and Return Aliases for gateway default destinations
    path("webhook/", views.gateway_webhook, name="gateway_webhook_short"),
    path("callback/", views.payment_return_view, name="gateway_return_callback"),
]

