from django.db import models
from django.core.exceptions import ValidationError
from core.tenancy.context import get_current_tenant


class TenantQuerySet(models.QuerySet):
    """
    QuerySet providing automatic scoping by tenant and explicit bypass capabilities.
    """

    def for_tenant(self, tenant):
        """Explicitly filter this QuerySet for a specific tenant."""
        return self.filter(tenant=tenant)

    def unscoped(self):
        """
        Explicitly bypass tenant isolation filter.
        Use for cross-tenant operations, global platform reports, or superuser tasks.
        """
        clone = self._chain()
        clone._is_unscoped = True
        return clone


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Model manager that automatically filters queries by the currently active tenant in context.
    """

    def get_queryset(self):
        qs = super().get_queryset()

        # If explicitly marked as unscoped, do not apply tenant filter
        if getattr(qs, "_is_unscoped", False):
            return qs

        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(tenant=tenant)

        return qs


class TenantAwareModel(models.Model):
    """
    Abstract base model for all tenant-partitioned entities.
    Enforces row-level tenant association, automated injection, and isolation integrity.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    objects = TenantManager()
    all_objects = models.Manager()  # Direct unscoped access for system maintenance

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Automatically assign the active tenant if none is provided
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
            else:
                raise ValidationError("Cannot persist TenantAwareModel without an active tenant context.")

        # Defense-in-depth: Guard against cross-tenant assignment
        active_tenant = get_current_tenant()
        if active_tenant and self.tenant_id != active_tenant.id:
            raise ValidationError(
                f"Tenant mismatch: Object assigned to tenant #{self.tenant_id}, "
                f"but execution context is tenant #{active_tenant.id}."
            )

        super().save(*args, **kwargs)
