from django.conf import settings


def tenant_context(request):
    """
    Context processor that injects the resolved tenant, active menu items,
    and convenience flags into all template contexts.
    """
    tenant = getattr(request, "tenant", None)
    menu_items = tenant.get_menu_items() if tenant else []
    
    platform_main_domain = getattr(settings, "PLATFORM_MAIN_DOMAIN", "course.webkoders.com").strip().lower()
    scheme = "https" if request.is_secure() else "http"
    if not request.is_secure() and ("localhost" in request.get_host() or "127.0.0.1" in request.get_host()):
        host_with_port = request.get_host()
        platform_url = f"{scheme}://{host_with_port}/"
    else:
        platform_url = f"https://{platform_main_domain}/"

    return {
        "current_tenant": tenant,
        "is_tenant_site": tenant is not None,
        "tenant_menu_items": menu_items,
        "PLATFORM_MAIN_DOMAIN": platform_main_domain,
        "platform_url": platform_url,
    }
