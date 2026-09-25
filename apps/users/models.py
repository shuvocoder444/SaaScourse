from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.tenancy.models import TenantAwareModel


class UserManager(BaseUserManager):
    """Custom manager for email-as-username User model."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email field must be provided."))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Global custom user entity across the platform.
    Uses email as the unique identifier.
    """

    username = None
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_role_in_tenant(self, tenant):
        """Retrieve this user's membership role in a given tenant."""
        membership = self.tenant_memberships.unscoped().filter(tenant=tenant).first()
        return membership.role if membership else None


class TenantMembership(TenantAwareModel):
    """
    Defines a user's tenancy context and role within an academy.
    Supports multi-tenant membership (e.g. Student in Academy A, Instructor in Academy B).
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Admin / Owner")
        INSTRUCTOR = "INSTRUCTOR", _("Instructor")
        STUDENT = "STUDENT", _("Student")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                name="unique_user_membership_per_tenant",
            )
        ]
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.tenant.name} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_instructor(self) -> bool:
        return self.role == self.Role.INSTRUCTOR

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT
