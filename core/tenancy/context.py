import contextvars
from contextlib import contextmanager
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenants.models import Tenant

# Thread-safe and asyncio-safe context variable for current active tenant
_current_tenant: contextvars.ContextVar[Optional["Tenant"]] = contextvars.ContextVar(
    "current_tenant", default=None
)


def get_current_tenant() -> Optional["Tenant"]:
    """Retrieve the active tenant for the current thread/task."""
    return _current_tenant.get()


def set_current_tenant(tenant: Optional["Tenant"]):
    """Set the active tenant and return the context reset token."""
    return _current_tenant.set(tenant)


def reset_current_tenant(token) -> None:
    """Reset the tenant context back to its previous state using the token."""
    _current_tenant.reset(token)


@contextmanager
def tenant_context(tenant: Optional["Tenant"]):
    """
    Context manager for background tasks, Celery jobs, management scripts, or tests.
    
    Usage:
        with tenant_context(my_tenant):
            Course.objects.all()  # Automatically scoped to my_tenant
    """
    token = set_current_tenant(tenant)
    try:
        yield
    finally:
        reset_current_tenant(token)
