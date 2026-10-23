import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PaymentOrder
from .services import GatewayError, create_gateway_checkout, get_gateway_credentials, verify_gateway_invoice

logger = logging.getLogger(__name__)


@login_required
def start_payment(request, order_id):
    """
    Initiates payment for an existing local PaymentOrder.
    Redirects customer to the hosted checkout page on the gateway.
    """
    if str(order_id).isdigit():
        order = get_object_or_404(PaymentOrder, pk=int(order_id), user=request.user)
    else:
        order = get_object_or_404(PaymentOrder, order_no=str(order_id), user=request.user)

    if order.payment_status == PaymentOrder.PaymentStatus.PAID:
        messages.success(request, "এই অর্ডারের পেমেন্ট ইতিমধ্যে সম্পন্ন হয়েছে।")
        return redirect(order.get_success_redirect_url())

    try:
        invoice = create_gateway_checkout(order)
        order.gateway_reference = invoice.get("reference_id", "")
        order.gateway_checkout_url = invoice.get("checkout_url", "")
        order.payment_status = PaymentOrder.PaymentStatus.PENDING
        order.save(update_fields=["gateway_reference", "gateway_checkout_url", "payment_status"])
        return redirect(invoice["checkout_url"])
    except GatewayError as exc:
        logger.error(f"Failed to start payment for order {order.pk}: {exc}")
        messages.error(request, f"পেমেন্ট শুরু করতে সমস্যা হয়েছে: {str(exc)}")
        return redirect(order.get_success_redirect_url())


@csrf_exempt
@require_POST
def gateway_webhook(request):
    """
    Cryptographically verified Webhook handler for Webkoders Payment Gateway.
    Verifies HMAC-SHA256 signature using the specific order's tenant secret.
    """
    received_sig = request.headers.get("X-Signature", "").strip()
    if not received_sig:
        logger.warning("Gateway webhook missing X-Signature header.")
        return HttpResponse("Missing signature", status=400)

    try:
        event = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning(f"Gateway webhook invalid JSON body: {exc}")
        return HttpResponse("Invalid payload format", status=400)

    event_type = event.get("event")
    status = event.get("status")

    if event_type != "payment.completed":
        # Safe ignore for non-completion events
        return HttpResponse("Ignored", status=200)

    if status != "COMPLETED":
        return HttpResponse("Not completed", status=400)

    order_id = event.get("order_id")
    reference_id = event.get("reference_id")
    amount = event.get("amount")
    currency = event.get("currency", "BDT")
    trx_id = event.get("trx_id", "")

    # Lookup order to resolve tenant-specific secret
    order = None
    if order_id and str(order_id).isdigit():
        order = PaymentOrder.objects.filter(pk=int(order_id)).first()
    if not order and reference_id:
        order = PaymentOrder.objects.filter(gateway_reference=str(reference_id)).first()
    if not order and order_id:
        order = PaymentOrder.objects.filter(order_no=str(order_id)).first()

    if not order:
        logger.error(f"Order not found for webhook: order_id={order_id}, reference_id={reference_id}")
        return HttpResponse("Order not found", status=404)

    # Determine secret using order's tenant
    _, _, expected_secret = get_gateway_credentials(order.tenant)
    if not expected_secret:
        logger.error("GATEWAY_API_SECRET is not configured on server or tenant.")
        return HttpResponse("Server misconfiguration", status=500)

    computed_sig = hmac.new(
        expected_secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_sig, received_sig):
        logger.warning("Gateway webhook signature mismatch.")
        return HttpResponse("Invalid signature", status=400)

    try:
        with transaction.atomic():
            # Lookup order by primary key or order_no or gateway_reference
            order = None
            if order_id and str(order_id).isdigit():
                order = PaymentOrder.objects.select_for_update().filter(pk=int(order_id)).first()
            if not order and reference_id:
                order = PaymentOrder.objects.select_for_update().filter(gateway_reference=str(reference_id)).first()
            if not order and order_id:
                order = PaymentOrder.objects.select_for_update().filter(order_no=str(order_id)).first()

            if not order:
                logger.error(f"Order not found for webhook: order_id={order_id}, reference_id={reference_id}")
                return HttpResponse("Order not found", status=404)

            # Verification checks
            if order.gateway_reference and str(order.gateway_reference) != str(reference_id):
                logger.warning(f"Invoice reference mismatch: {order.gateway_reference} vs {reference_id}")
                return HttpResponse("Invoice mismatch", status=400)

            if Decimal(str(order.amount)) != Decimal(str(amount)):
                logger.warning(f"Amount mismatch for order {order.pk}: expected {order.amount}, got {amount}")
                return HttpResponse("Amount mismatch", status=400)

            if currency != "BDT":
                return HttpResponse("Currency mismatch", status=400)

            # Idempotent state update
            if order.payment_status != PaymentOrder.PaymentStatus.PAID:
                order.payment_status = PaymentOrder.PaymentStatus.PAID
                order.gateway_trx_id = trx_id or order.gateway_trx_id
                order.save(update_fields=["payment_status", "gateway_trx_id", "updated_at"])
                
                # Fulfill the order
                order.fulfill_order()
                logger.info(f"Successfully processed webhook and fulfilled order #{order.order_no} (TrxID: {trx_id})")

    except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
        logger.exception(f"Error handling webhook data: {exc}")
        return HttpResponse("Invalid notification", status=400)

    return HttpResponse("OK", status=200)


def payment_return_view(request):
    """
    Landing page for customer returning from gateway checkout.
    Performs real-time gateway status verification if order is pending.
    """
    reference_id = (
        request.GET.get("reference_id")
        or request.GET.get("ref")
        or request.GET.get("reference")
        or ""
    ).strip()
    order_id = request.GET.get("order_id", "").strip()

    order = None
    if reference_id:
        order = PaymentOrder.objects.filter(gateway_reference=reference_id).first()
    if not order and order_id:
        if order_id.isdigit():
            order = PaymentOrder.objects.filter(pk=int(order_id)).first()
        else:
            order = PaymentOrder.objects.filter(order_no=order_id).first()

    if not order and request.user.is_authenticated:
        order = PaymentOrder.objects.filter(user=request.user).order_by("-created_at").first()

    # Active Live Verification if pending
    if order and order.payment_status == PaymentOrder.PaymentStatus.PENDING and order.gateway_reference:
        try:
            live_data = verify_gateway_invoice(order.gateway_reference, order.tenant)
            if live_data and live_data.get("status") == "COMPLETED":
                with transaction.atomic():
                    order = PaymentOrder.objects.select_for_update().get(pk=order.pk)
                    if order.payment_status != PaymentOrder.PaymentStatus.PAID:
                        order.payment_status = PaymentOrder.PaymentStatus.PAID
                        order.gateway_trx_id = live_data.get("trx_id") or live_data.get("transaction_id", "")
                        order.save(update_fields=["payment_status", "gateway_trx_id", "updated_at"])
                        order.fulfill_order()
        except Exception as exc:
            logger.warning(f"Live verification check failed: {exc}")

    context = {
        "order": order,
        "is_paid": order.payment_status == PaymentOrder.PaymentStatus.PAID if order else False,
        "next_url": order.get_success_redirect_url() if order else "/dashboard/",
    }
    return render(request, "payments/return.html", context)

