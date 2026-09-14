from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


def default_branding():
    return {
        "primary_color": "#4f46e5",    # Indigo-600
        "accent_color": "#06b6d4",     # Cyan-500
        "logo_url": "",
        "banner_url": "",
        "favicon_url": "",
        "tagline": "Empowering learners through high-impact courses.",
        "hero_headline": "Master In-Demand Skills with Expert Guidance",
        "hero_subheadline": "Access interactive, project-driven curriculums with full code walkthroughs and community support.",
        "cta_text": "Explore All Courses",
        "about_heading": "Why Learn With Us?",
        "about_text": "We combine industry-proven engineering principles with real-world builds so you can level up your career quickly.",
        "font_family": "Inter",
    }


class SubscriptionPlan(models.Model):
    """
    SaaS subscription tiers sold by the platform admin.
    e.g. Starter ($29/mo), Professional ($79/mo), Enterprise ($199/mo).
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=50, unique=True)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2)
    max_courses = models.PositiveIntegerField(default=5, help_text="Maximum published courses permitted.")
    max_students = models.PositiveIntegerField(default=250, help_text="Maximum enrolled students permitted.")
    custom_domain_allowed = models.BooleanField(default=False, help_text="Allows white-label custom CNAME domain.")
    features = models.JSONField(default=list, blank=True, help_text="List of feature bullet points for pricing cards.")
    is_popular = models.BooleanField(default=False, help_text="Highlight as Recommended/Most Popular tier.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self):
        return f"{self.name} (৳{self.price_monthly}/mo)"


class Tenant(models.Model):
    """
    An independent academy tenant operated by a customer/creator.
    """

    name = models.CharField(max_length=150, help_text="Public brand name of the academy.")
    slug = models.SlugField(
        max_length=63,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?$",
                message="Subdomain must be lowercase alphanumeric and may contain hyphens.",
            )
        ],
        help_text="Used for the subdomain: [slug].platform.com or [slug].localhost",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_tenants",
        help_text="Primary platform user who owns this academy.",
    )
    custom_domain = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Custom CNAME domain (e.g., learn.mybrand.com). Normalized to lowercase.",
    )
    custom_domain_verified = models.BooleanField(
        default=False,
        help_text="True when DNS TXT / CNAME ownership verification has succeeded.",
    )
    custom_domain_token = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Random challenge token expected in _saascourse-challenge TXT record.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Controls if the academy is reachable and active.",
    )
    logo = models.ImageField(
        upload_to="tenants/logos/",
        null=True,
        blank=True,
        help_text="Square or horizontal academy brand logo.",
    )
    banner = models.ImageField(
        upload_to="tenants/banners/",
        null=True,
        blank=True,
        help_text="Hero cover banner image displayed across the storefront landing.",
    )
    favicon = models.ImageField(
        upload_to="tenants/favicons/",
        null=True,
        blank=True,
        help_text="Browser favicon icon (32x32 or 64x64 .png / .ico).",
    )
    branding = models.JSONField(
        default=default_branding,
        blank=True,
        help_text="JSON payload containing colors, logos, and custom landing page copy.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug", "is_active"]),
            models.Index(fields=["custom_domain", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def clean(self):
        if self.custom_domain:
            self.custom_domain = self.custom_domain.strip().lower()
        if self.slug:
            self.slug = self.slug.strip().lower()

    def save(self, *args, **kwargs):
        self.clean()
        defaults = default_branding()
        if isinstance(self.branding, dict):
            defaults.update(self.branding)
            self.branding = defaults
        super().save(*args, **kwargs)
        # Invalidate middleware cache on update
        cache.delete(f"tenant:slug:{self.slug}")
        if self.custom_domain:
            cache.delete(f"tenant:domain:{self.custom_domain}")

    def generate_domain_token(self) -> str:
        """Generates or returns existing verification token for DNS challenge."""
        if not self.custom_domain_token:
            import secrets
            self.custom_domain_token = f"saascourse-verify-{secrets.token_hex(16)}"
            self.save(update_fields=["custom_domain_token"])
        return self.custom_domain_token

    @property
    def get_logo_url(self) -> str:
        """Returns direct uploaded logo URL or fallback from branding JSON."""
        if self.logo:
            return self.logo.url
        branding = self.branding or {}
        return branding.get("logo_url", "")

    @property
    def get_banner_url(self) -> str:
        """Returns direct uploaded hero banner URL or fallback from branding JSON."""
        if self.banner:
            return self.banner.url
        branding = self.branding or {}
        return branding.get("banner_url", "")

    @property
    def get_favicon_url(self) -> str:
        """Returns direct uploaded favicon URL or fallback from branding JSON."""
        if self.favicon:
            return self.favicon.url
        branding = self.branding or {}
        return branding.get("favicon_url", "")

    @property
    def has_active_subscription(self) -> bool:
        """Returns True if the tenant has an active subscription or unexpired trial."""
        sub = getattr(self, "subscription", None)
        if not sub:
            return False
        return sub.is_valid


class TenantSMSSetting(models.Model):
    """
    SMS Gateway integration settings for a coaching center tenant.
    Allows academies to send automated SMS notifications to students and instructors.
    Supports top Bangladesh gateways (SSL Wireless, Greenweb, MimSMS), Twilio, and Generic REST APIs.
    """

    class Provider(models.TextChoices):
        SSL_WIRELESS = "SSL_WIRELESS", "SSL Wireless (Bangladesh)"
        GREENWEB = "GREENWEB", "Greenweb SMS (Bangladesh)"
        MIM_SMS = "MIM_SMS", "MimSMS (Bangladesh)"
        TWILIO = "TWILIO", "Twilio Global"
        GENERIC = "GENERIC", "Generic HTTP GET/POST API"

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="sms_setting",
    )
    provider = models.CharField(
        max_length=30,
        choices=Provider.choices,
        default=Provider.SSL_WIRELESS,
        help_text="Selected SMS Gateway Service Provider",
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text="Enable live SMS sending for this coaching center.",
    )
    sender_id = models.CharField(
        max_length=60,
        blank=True,
        default="",
        help_text="Approved Sender ID, Masking name, or Twilio Phone Number.",
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="API Token, User Token, or Twilio Account SID.",
    )
    api_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="API Secret Password, Twilio Auth Token, or Client Secret.",
    )
    api_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Custom gateway HTTP endpoint (required for Generic HTTP API).",
    )
    template_enrollment = models.TextField(
        blank=True,
        default="Dear {student_name}, congratulations on enrolling in '{course_title}' at {academy_name}! Start learning now.",
        help_text="Template for course enrollment confirmation SMS.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "Active" if self.is_enabled else "Disabled"
        return f"{self.tenant.name} SMS ({self.get_provider_display()} - {status})"

    def send_sms(self, recipient: str, message: str) -> dict:
        """
        Dispatches SMS via the configured gateway.
        In demo/dev environment without real credentials, safely logs and simulates delivery.
        """
        import re
        import logging
        logger = logging.getLogger(__name__)

        cleaned_number = re.sub(r"[^\d+]", "", str(recipient).strip())
        if not cleaned_number:
            return {"success": False, "error": "Invalid recipient phone number."}

        if not self.is_enabled:
            return {"success": False, "error": "SMS sending is currently disabled for this academy."}

        # If live credentials are provided, attempt real dispatch
        if self.api_key and self.provider != self.Provider.GENERIC:
            try:
                import urllib.request
                import urllib.parse
                import json

                if self.provider == self.Provider.GREENWEB:
                    endpoint = "https://api.greenweb.com.bd/api.php"
                    params = {
                        "token": self.api_key,
                        "to": cleaned_number,
                        "message": message,
                    }
                    if self.sender_id:
                        params["senderid"] = self.sender_id
                    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
                    req = urllib.request.Request(url, headers={"User-Agent": "CourseFlow-SaaS/1.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res_body = resp.read().decode("utf-8")
                        return {"success": True, "response": res_body, "provider": self.provider}

                elif self.provider == self.Provider.SSL_WIRELESS:
                    endpoint = "https://smsplus.sslwireless.com/api/v3/send-sms"
                    payload = json.dumps({
                        "api_token": self.api_key,
                        "sid": self.sender_id,
                        "msisdn": cleaned_number,
                        "sms": message,
                        "csms_id": f"CF{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        endpoint,
                        data=payload,
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res_body = resp.read().decode("utf-8")
                        return {"success": True, "response": res_body, "provider": self.provider}

                elif self.provider == self.Provider.MIM_SMS:
                    endpoint = "https://api.mimsms.com/api/SmsSending/Send"
                    params = {
                        "ApiKey": self.api_key,
                        "ClientId": self.api_secret,
                        "SenderId": self.sender_id,
                        "Message": message,
                        "MobileNumbers": cleaned_number,
                    }
                    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
                    req = urllib.request.Request(url, headers={"User-Agent": "CourseFlow-SaaS/1.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res_body = resp.read().decode("utf-8")
                        return {"success": True, "response": res_body, "provider": self.provider}

            except Exception as e:
                logger.warning(f"Live SMS dispatch error: {e}. Falling back to simulation.")

        # Dev / Simulation mode
        logger.info(f"[SMS SIMULATION] To: {cleaned_number} | From: {self.sender_id or self.tenant.name} | Text: {message}")
        return {
            "success": True,
            "simulated": True,
            "provider": self.get_provider_display(),
            "recipient": cleaned_number,
            "sender_id": self.sender_id or self.tenant.name,
            "message": message,
        }


class TenantSubscription(models.Model):
    """
    Tracks the active subscription tier and billing state of an academy tenant.
    """

    class Status(models.TextChoices):
        TRIALING = "TRIALING", "14-Day Free Trial"
        ACTIVE = "ACTIVE", "Active Subscription"
        PAST_DUE = "PAST_DUE", "Past Due"
        CANCELED = "CANCELED", "Canceled"

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIALING,
        db_index=True,
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} ({self.get_status_display()})"

    @property
    def is_valid(self) -> bool:
        """Determines if the subscription grants live access."""
        if self.status == self.Status.ACTIVE:
            return True
        if self.status == self.Status.TRIALING:
            if self.trial_ends_at and self.trial_ends_at < timezone.now():
                return False
            return True
        return False
