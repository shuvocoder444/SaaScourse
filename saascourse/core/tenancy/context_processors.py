def tenant_context(request):
    """
    Context processor that injects the resolved tenant, active menu items,
    and convenience flags into all template contexts.
    """
    tenant = getattr(request, "tenant", None)
    menu_items = tenant.get_menu_items() if tenant else []
    return {
        "current_tenant": tenant,
        "is_tenant_site": tenant is not None,
        "tenant_menu_items": menu_items,
    }

