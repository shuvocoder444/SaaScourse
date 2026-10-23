import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Raised when communication with Webkoders payment gateway fails."""
    pass


def get_gateway_credentials(tenant=None):
    """
    Resolves Gateway Base URL, API Key, and Secret.
    Allows per-tenant custom credentials in tenant.branding if configured,
    otherwise falls back to platform settings.
    """
    base_url = getattr(settings, "GATEWAY_BASE_URL", "https://payment.webkoders.com").rstrip("/")
    api_key = getattr(settings, "GATEWAY_API_KEY", "")
    api_secret = getattr(settings, "GATEWAY_API_SECRET", "")

    if tenant and hasattr(tenant, "branding") and isinstance(tenant.branding, dict):
        if tenant.branding.get("gateway_base_url"):
            base_url = str(tenant.branding.get("gateway_base_url")).rstrip("/")
        if tenant.branding.get("gateway_api_key"):
            api_key = str(tenant.branding.get("gateway_api_key")).strip()
        if tenant.branding.get("gateway_api_secret"):
            api_secret = str(tenant.branding.get("gateway_api_secret")).strip()

    return base_url, api_key, api_secret


def create_gateway_checkout(order):
    """
    Creates a hosted checkout session on Webkoders payment gateway.
    Returns:
        dict: {'status': 'success', 'checkout_url': '...', 'reference_id': '...'}
    Raises:
        GatewayError on network error or invalid response.
    """
    base_url, api_key, _ = get_gateway_credentials(order.tenant)

    if not api_key:
        raise GatewayError("Payment gateway API key is not configured on the server.")

    # Format customer details cleanly
    customer_name = order.customer_name
    if not customer_name and order.user:
        customer_name = order.user.get_full_name() or order.user.username or "Student"

    customer_email = order.customer_email
    if not customer_email and order.user and "@" in order.user.email:
        if not order.user.email.endswith("@student.academy"):
            customer_email = order.user.email
        else:
            customer_email = None

    customer_phone = order.customer_phone
    if not customer_phone and order.user:
        customer_phone = getattr(order.user, "phone_number", "") or ""

    payload = {
        "order_id": str(order.pk),
        "amount": f"{float(order.amount):.2f}",
        "currency": "BDT",
        "customer_name": customer_name or "Student",
        "customer_email": customer_email,
        "customer_phone": customer_phone or "",
        "metadata": {
            "local_order_id": str(order.pk),
            "order_no": order.order_no,
            "order_type": order.order_type,
            "tenant_slug": order.tenant.slug if order.tenant else "",
        },
    }

    create_url = f"{base_url}/api/v1/checkout/create/"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            create_url,
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        logger.error(f"Gateway request failed: {exc}")
        raise GatewayError(f"Gateway checkout তৈরি করা যায়নি: {str(exc)}") from exc
    except ValueError as exc:
        logger.error(f"Gateway invalid JSON response: {exc}")
        raise GatewayError("Gateway থেকে অকার্যকর রেসপন্স পাওয়া গেছে।") from exc

    if result.get("status") != "success" or not result.get("checkout_url"):
        error_msg = result.get("message") or result.get("error") or "Gateway checkout link দেয়নি"
        raise GatewayError(f"Gateway checkout তৈরি ব্যর্থ: {error_msg}")

    return result


def verify_gateway_invoice(reference_id, tenant=None):
    """
    Checks the status of a checkout invoice directly via Gateway API.
    GET /api/v1/checkout/<reference_id>/
    """
    base_url, api_key, _ = get_gateway_credentials(tenant)
    if not api_key or not reference_id:
        return None

    detail_url = f"{base_url}/api/v1/checkout/{reference_id}/"
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json",
    }

    try:
        response = requests.get(detail_url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as exc:
        logger.warning(f"Error querying gateway invoice {reference_id}: {exc}")

    return None

