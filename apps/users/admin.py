from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)

from apps.users.models import TenantMembership, User


class CustomUserCreationForm(UserCreationForm):
    """Admin form for creating a new user with email instead of username."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class CustomUserChangeForm(UserChangeForm):
    """Admin form for editing user profile and accessing password change."""

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "password" in self.fields:
            self.fields["password"].help_text = (
                'Raw passwords are not stored. '
                '<a href="../password/" style="display:inline-block; margin-top:6px; padding:6px 14px; '
                'background:#2563eb; color:#ffffff; font-weight:bold; border-radius:6px; text-decoration:none;">'
                '🔑 পাসওয়ার্ড পরিবর্তন করুন (Change Password Here) ➔</a>'
            )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    change_password_form = AdminPasswordChangeForm

    ordering = ["email"]
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "avatar")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "tenant")
    search_fields = ("user__email", "tenant__name")

    def get_queryset(self, request):
        # Allow superusers to see all memberships across tenants in django admin
        return super().get_queryset(request).model.all_objects.all()
