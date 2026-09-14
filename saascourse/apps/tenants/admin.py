from django.contrib import admin
from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription, TenantSMSSetting


class TenantSubscriptionInline(admin.StackedInline):
    model = TenantSubscription
    extra = 0
    can_delete = False


class TenantSMSSettingInline(admin.StackedInline):
    model = TenantSMSSetting
    extra = 0
    can_delete = False


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "custom_domain", "is_active", "get_plan", "created_at")
    list_filter = ("is_active", "subscription__status", "created_at")
    search_fields = ("name", "slug", "custom_domain", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TenantSubscriptionInline, TenantSMSSettingInline]
    fieldsets = (
        ("General Info", {"fields": ("name", "slug", "owner", "is_active")}),
        ("Domain Routing", {"fields": ("custom_domain", "custom_domain_verified")}),
        ("Brand Assets (Logo, Banner, Favicon)", {"fields": ("logo", "banner", "favicon")}),
        ("Branding & Theme Settings", {"fields": ("branding",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_plan(self, obj):
        return obj.subscription.plan.name if hasattr(obj, "subscription") else "No Plan"
    get_plan.short_description = "Subscription Plan"


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price_monthly", "max_courses", "max_students", "custom_domain_allowed", "is_popular")
    list_filter = ("custom_domain_allowed", "is_popular")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "plan", "status", "trial_ends_at", "current_period_end")
    list_filter = ("status", "plan")
    search_fields = ("tenant__name", "tenant__slug")


@admin.register(TenantSMSSetting)
class TenantSMSSettingAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "is_enabled", "sender_id", "updated_at")
    list_filter = ("provider", "is_enabled")
    search_fields = ("tenant__name", "tenant__slug", "sender_id")
