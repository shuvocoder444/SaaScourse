def tenant_context(request):
    """
    Context processor that injects the resolved tenant and convenience flags
    into all template contexts.
    """
    tenant = getattr(request, "tenant", None)
    return {
        "current_tenant": tenant,
        "is_tenant_site": tenant is not None,
    }
