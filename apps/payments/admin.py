from django.contrib import admin
from .models import PaymentOrder


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_no",
        "tenant",
        "user",
        "order_type",
        "amount",
        "currency",
        "payment_status",
        "gateway_reference",
        "gateway_trx_id",
        "created_at",
    )
    list_filter = ("payment_status", "order_type", "tenant", "created_at")
    search_fields = (
        "order_no",
        "user__email",
        "user__phone_number",
        "gateway_reference",
        "gateway_trx_id",
        "customer_name",
        "customer_phone",
    )
    readonly_fields = ("order_no", "created_at", "updated_at")
    ordering = ("-created_at",)

