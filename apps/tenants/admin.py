from django import forms
from django.contrib import admin

from apps.tenants.models import (
    SubscriptionPlan,
    Tenant,
    TenantMenuItem,
    TenantSMSSetting,
    TenantSubscription,
)


class SubscriptionPlanForm(forms.ModelForm):
    features_lines = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "প্রতি লাইনে একটি করে ফিচার লিখুন, যেমন:\nসম্পূর্ণ LMS ও কোর্স বিল্ডার\nসুরক্ষিত ভিডিও ক্লাস ও অ্যান্টি-পাইরেসি\nমডেল টেস্ট ও রেজাল্ট সিস্টেম\nলাইভ সাপোর্ট",
                "class": "vLargeTextField",
            }
        ),
        required=False,
        label="প্ল্যানের সুবিধাসমূহ (Features - প্রতি লাইনে ১টি)",
        help_text="প্রতি লাইনে ১টি করে সুবিধা/ফিচার লিখুন। এটি প্রাইসিং টেবিলে টিকমার্কসহ প্রদর্শিত হবে।",
    )

    class Meta:
        model = SubscriptionPlan
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if isinstance(self.instance.features, list):
                self.fields["features_lines"].initial = "\n".join(
                    str(f) for f in self.instance.features
                )

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_lines = self.cleaned_data.get("features_lines", "")
        features_list = [
            line.strip() for line in raw_lines.splitlines() if line.strip()
        ]
        instance.features = features_list
        if commit:
            instance.save()
        return instance


class TenantMenuItemInline(admin.TabularInline):
    model = TenantMenuItem
    extra = 1


class TenantSubscriptionInline(admin.StackedInline):
    model = TenantSubscription
    extra = 0
    can_delete = False
    fields = ("plan", "status", "trial_ends_at", "current_period_end")


class TenantSMSSettingInline(admin.StackedInline):
    model = TenantSMSSetting
    extra = 0
    can_delete = False


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "owner",
        "landing_template",
        "custom_domain",
        "is_active",
        "get_plan",
        "get_sub_status",
        "created_at",
    )
    list_filter = (
        "is_active",
        "landing_template",
        "subscription__status",
        "created_at",
    )
    search_fields = ("name", "slug", "custom_domain", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TenantMenuItemInline, TenantSubscriptionInline, TenantSMSSettingInline]
    fieldsets = (
        (
            "General Info",
            {"fields": ("name", "slug", "owner", "landing_template", "is_active")},
        ),
        (
            "Domain Routing",
            {
                "fields": (
                    "custom_domain",
                    "custom_domain_verified",
                    "custom_domain_token",
                )
            },
        ),
        (
            "Brand Assets (Logo, Banner, Favicon, Android APK)",
            {"fields": ("logo", "banner", "favicon", "android_apk")},
        ),
        ("Branding & Theme Settings", {"fields": ("branding",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_plan(self, obj):
        return (
            obj.subscription.plan.name
            if hasattr(obj, "subscription") and obj.subscription.plan
            else "No Plan"
        )

    get_plan.short_description = "Subscription Plan"

    def get_sub_status(self, obj):
        return (
            obj.subscription.get_status_display()
            if hasattr(obj, "subscription")
            else "—"
        )

    get_sub_status.short_description = "Subscription Status"


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    form = SubscriptionPlanForm
    list_display = (
        "name",
        "price_monthly",
        "billing_period",
        "description",
        "max_courses",
        "max_students",
        "custom_domain_allowed",
        "is_popular",
        "is_active",
        "order",
    )
    list_editable = ("price_monthly", "is_popular", "is_active", "order")
    list_filter = ("is_active", "is_popular", "custom_domain_allowed")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (
            "বেসিক তথ্য (Plan Info)",
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "is_active",
                    "order",
                )
            },
        ),
        (
            "মূল্য ও বিলিং (Pricing & Badges)",
            {
                "fields": (
                    "price_monthly",
                    "billing_period",
                    "badge_text",
                    "is_popular",
                    "cta_text",
                )
            },
        ),
        (
            "একাডেমির লিমিটেশন (Limits & Quotas)",
            {
                "fields": (
                    "max_courses",
                    "max_students",
                    "custom_domain_allowed",
                )
            },
        ),
        (
            "ফিচারসমূহ (Bullet Points)",
            {
                "fields": ("features_lines",),
                "description": "প্রতি লাইনে একটি করে ফিচার লিখুন যা প্রাইসিং কার্ডে প্রদর্শিত হবে।",
            },
        ),
    )


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "plan",
        "status",
        "trial_ends_at",
        "current_period_end",
        "is_valid",
    )
    list_filter = ("status", "plan")
    search_fields = ("tenant__name", "tenant__slug", "tenant__owner__email")
    list_editable = ("plan", "status")


@admin.register(TenantSMSSetting)
class TenantSMSSettingAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "is_enabled", "sender_id", "updated_at")
    list_filter = ("provider", "is_enabled")
    search_fields = ("tenant__name", "tenant__slug", "sender_id")
