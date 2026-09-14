from typing import Optional, Tuple
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.core.cache import cache

from apps.tenants.models import Tenant
from core.tenancy.context import set_current_tenant, reset_current_tenant


class TenantResolutionMiddleware:
    """
    Middleware that identifies the tenant from the HTTP Host header,
    sets request.tenant, and configures the thread/async contextvars tenant context.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.main_domains = getattr(
            settings, "TENANT_MAIN_DOMAINS", ["platform.com", "localhost", "127.0.0.1"]
        )

    def __call__(self, request):
        hostname = self._extract_hostname(request)
        tenant, is_main_site = self._resolve_tenant(hostname)

        # 1. Platform Landing / Marketing Site
        if is_main_site:
            request.tenant = None
            token = set_current_tenant(None)
            try:
                return self.get_response(request)
            finally:
                reset_current_tenant(token)

        # 2. Hostname looks like a tenant, but no matching tenant in DB
        if not tenant:
            raise Http404(f"Academy domain '{hostname}' was not found.")

        # 3. Tenant exists, but is currently marked inactive/suspended
        if not tenant.is_active:
            return render(
                request,
                "tenants/suspended.html",
                {"tenant": tenant},
                status=403,
            )

        # 4. Valid active tenant: inject into request and thread/async context
        request.tenant = tenant
        token = set_current_tenant(tenant)
        try:
            response = self.get_response(request)
        finally:
            reset_current_tenant(token)

        return response

    def _extract_hostname(self, request) -> str:
        """Removes the port number and converts to lowercase."""
        return request.get_host().split(":")[0].strip().lower()

    def _resolve_tenant(self, hostname: str) -> Tuple[Optional[Tenant], bool]:
        """
        Resolves hostname to a (Tenant or None, is_main_site boolean).
        Uses cache-first strategy.
        """
        # Exact match with main platform root domains
        if hostname in self.main_domains:
            return None, True

        # Check for tenant subdomain (e.g. 'alpha.localhost' or 'alpha.platform.com')
        for main_domain in self.main_domains:
            suffix = f".{main_domain}"
            if hostname.endswith(suffix):
                subdomain = hostname[: -len(suffix)]
                # Ensure it is a direct single-level subdomain
                if subdomain and "." not in subdomain:
                    return self._get_tenant_by_slug(subdomain), False

        # If not matched as subdomain, treat as Custom CNAME Domain (e.g. 'learn.custombrand.com')
        return self._get_tenant_by_custom_domain(hostname), False

    def _get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        cache_key = f"tenant:slug:{slug}"
        cached_id = cache.get(cache_key)

        if cached_id is not None:
            if cached_id is False:
                return None
            try:
                return Tenant.objects.get(id=cached_id)
            except Tenant.DoesNotExist:
                cache.delete(cache_key)

        try:
            tenant = Tenant.objects.get(slug=slug)
            cache.set(cache_key, tenant.id, timeout=300)
            return tenant
        except Tenant.DoesNotExist:
            cache.set(cache_key, False, timeout=60)
            return None

    def _get_tenant_by_custom_domain(self, domain: str) -> Optional[Tenant]:
        cache_key = f"tenant:domain:{domain}"
        cached_id = cache.get(cache_key)

        if cached_id is not None:
            if cached_id is False:
                return None
            try:
                return Tenant.objects.get(id=cached_id)
            except Tenant.DoesNotExist:
                cache.delete(cache_key)

        try:
            tenant = Tenant.objects.get(custom_domain=domain)
            cache.set(cache_key, tenant.id, timeout=300)
            return tenant
        except Tenant.DoesNotExist:
            cache.set(cache_key, False, timeout=60)
            return None
