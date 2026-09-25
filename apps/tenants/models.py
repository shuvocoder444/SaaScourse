from django.conf import settings
from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


def default_branding():
    return {
        "primary_color": "#16a34a",    # Green-600 (Fresh EdTech default)
        "accent_color": "#f59e0b",     # Amber-500
        "logo_url": "",
        "banner_url": "",
        "favicon_url": "",
        "tagline": "স্বপ্ন হোক সফলতার সূচনা।",
        "hero_badge": "HSC 2026 • DU ICU BATCH",
        "hero_headline": "সেরা শিক্ষক ও প্র্যাকটিস ব্যাচে নির্ভুল প্রস্তুতি",
        "hero_subheadline": "এইচএসসি, ঢাকা বিশ্ববিদ্যালয় ও মেডিকেল ভর্তি পরীক্ষার পূর্ণাঙ্গ প্রস্তুতি নিন ঘরে বসেই।",
        "cta_text": "সেরা কোর্স বেছে নাও",
        "cta_link": "#courses",
        "cta_secondary_text": "আমাদের বইসমূহ",
        "cta_secondary_link": "/books/",
        "notice_text": "📢 ভর্তি চলছে! আগামী ব্যাচের লাইভ ক্লাসে দ্রুত যুক্ত হোন। আসন সংখ্যা সীমিত।",
        "about_heading": "কেন আমাদের সাথে প্রস্তুতি নেবেন?",
        "about_text": "অভিজ্ঞ মেন্টর, সার্বক্ষণিক ডাউট সলভিং, প্র্যাকটিস এক্সাম ও লাইভ ক্লাসের মাধ্যমে আমরা নিশ্চিত করি সর্বোচ্চ প্রস্তুতি।",
        "app_promo_title": "ডাউনলোড করুন আমাদের মোবাইল অ্যাপ, শেখা শুরু করুন আজ থেকেই",
        "app_promo_subtitle": "লাইভ ক্লাস, মডেল টেস্ট, লেকচার শিট ও পরীক্ষার ফলাফল সব পাবেন এক অ্যাপে।",
        "app_rating": "4.8★ (৫,০০০+ রিভিউ)",
        "app_downloads": "৫০,০০০+ শিক্ষার্থী",
        "play_store_url": "https://play.google.com",
        "app_store_url": "https://apple.com/app-store/",
        "contact_phone": "+880 1800-123456",
        "contact_email": "support@academy.edu.bd",
        "contact_address": "ফার্মগেট / নীলক্ষেত, ঢাকা, বাংলাদেশ",
        "facebook_url": "https://facebook.com",
        "youtube_url": "https://youtube.com",
        "telegram_url": "https://t.me",
        "whatsapp_number": "+8801800123456",
        "trade_license": "TRAD/DSCC/029148/2024",
        "govt_reg_no": "Govt Reg: ED-9482-BD",
        "header_cta_text": "ভর্তি আবেদন",
        "header_cta_link": "/courses/",
        "show_header_notice": True,
        "show_header_search": True,
        "show_footer_payments": True,
        "show_footer_apps": True,
        "footer_about": "বাংলাদেশের শীর্ষস্থানীয় অনলাইন এডুকেশন প্ল্যাটফর্ম। আধুনিক কারিকুলাম ও অভিজ্ঞ শিক্ষক মণ্ডলীর তত্ত্বাবধানে প্রতিটি শিক্ষার্থীর পূর্ণাঙ্গ প্রস্তুতি নিশ্চিত করাই আমাদের লক্ষ্য।",
        "footer_copyright": "© 2026 সর্বস্বত্ব সংরক্ষিত।",
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

    class LandingTemplate(models.TextChoices):
        EDTECH_BANGLA = "edtech_bangla", "এডমিশন ও একাডেমি EdTech (ডিজাইন ১)"
        MODERN_SAAS = "modern_saas", "মডার্ন টেক ও প্রো একাডেমি (ডিজাইন ২)"
        CLASSIC_COACHING = "classic_coaching", "ক্লাসিক কোচিং সেন্টার ও লাইভ নোটিশ (ডিজাইন ৩)"

    class HeaderStyle(models.TextChoices):
        HEADER_1 = "header_1", "এডটেক নোটিশ ও হটলাইন টপবার (স্টাইল ১)"
        HEADER_2 = "header_2", "মডার্ন ফ্ল্যাটিং গ্লাস হেডার (স্টাইল ২)"
        HEADER_3 = "header_3", "ক্লাসিক একাডেমি ডুয়াল-টিয়ার হেডার (স্টাইল ৩)"

    class FooterStyle(models.TextChoices):
        FOOTER_1 = "footer_1", "এডটেক পেমেন্ট ও অ্যাপ সমৃদ্ধ ফুটার (স্টাইল ১)"
        FOOTER_2 = "footer_2", "মডার্ন মাল্টি-কলাম ও নিউজলেটার ফুটার (স্টাইল ২)"
        FOOTER_3 = "footer_3", "ক্লাসিক ক্যাম্পাস ব্রাঞ্চ ও হেল্পলাইন ফুটার (স্টাইল ৩)"

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
    landing_template = models.CharField(
        max_length=30,
        choices=LandingTemplate.choices,
        default=LandingTemplate.EDTECH_BANGLA,
        help_text="Selected landing page layout design for this academy storefront.",
    )
    header_style = models.CharField(
        max_length=30,
        choices=HeaderStyle.choices,
        default=HeaderStyle.HEADER_1,
        help_text="Selected header navigation style for this academy storefront.",
    )
    footer_style = models.CharField(
        max_length=30,
        choices=FooterStyle.choices,
        default=FooterStyle.FOOTER_1,
        help_text="Selected footer layout style for this academy storefront.",
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
        # Ensure default navigation menus exist for this tenant
        self.ensure_default_menus()
        # Invalidate middleware cache on update
        cache.delete(f"tenant:slug:{self.slug}")
        if self.custom_domain:
            cache.delete(f"tenant:domain:{self.custom_domain}")

    def ensure_default_menus(self):
        """Creates the standard 5 navigation items if none exist yet for this tenant."""
        if not self.pk:
            return
        if not self.menu_items.exists():
            default_items = [
                ("হোম", "/", 1),
                ("কোর্সসমূহ", "/courses/", 2),
                ("বইসমূহ", "/books/", 3),
                ("ফ্রি রিসোর্স", "/resources/", 4),
                ("ব্লগ", "/blog/", 5),
            ]
            for title, url, order in default_items:
                TenantMenuItem.objects.create(
                    tenant=self,
                    title=title,
                    url=url,
                    order=order,
                    is_active=True,
                )

    def get_menu_items(self):
        """Returns ordered active menu items for public storefront header."""
        items = list(self.menu_items.filter(is_active=True).order_by("order"))
        if not items:
            # Fallback in-memory list
            return [
                {"title": "হোম", "url": "/", "open_in_new_tab": False},
                {"title": "কোর্সসমূহ", "url": "/courses/", "open_in_new_tab": False},
                {"title": "বইসমূহ", "url": "/books/", "open_in_new_tab": False},
                {"title": "ফ্রি রিসোর্স", "url": "/resources/", "open_in_new_tab": False},
                {"title": "ব্লগ", "url": "/blog/", "open_in_new_tab": False},
            ]
        return items

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

    def get_subdomain_host(self, request=None) -> str:
        """Returns full subdomain host, e.g. slug.course.webkoders.com or slug.localhost:8001"""
        if request:
            host = request.get_host()
            if "localhost" in host or "127.0.0.1" in host:
                port_part = f":{host.split(':')[1]}" if ":" in host else ""
                return f"{self.slug}.localhost{port_part}"
        main_domain = getattr(settings, "PLATFORM_MAIN_DOMAIN", "course.webkoders.com").strip().lower()
        return f"{self.slug}.{main_domain}"

    @property
    def subdomain_host(self) -> str:
        return self.get_subdomain_host()

    def get_primary_domain(self, request=None) -> str:
        """Returns custom_domain if verified/present, otherwise the full subdomain."""
        if self.custom_domain:
            return self.custom_domain
        return self.get_subdomain_host(request)

    @property
    def primary_domain(self) -> str:
        return self.get_primary_domain()

    def get_storefront_url(self, request=None) -> str:
        scheme = "https"
        if request and not request.is_secure() and ("localhost" in request.get_host() or "127.0.0.1" in request.get_host()):
            scheme = "http"
        return f"{scheme}://{self.get_primary_domain(request)}/"

    @property
    def storefront_url(self) -> str:
        return self.get_storefront_url()

    def get_dashboard_url(self, request=None) -> str:
        scheme = "https"
        if request and not request.is_secure() and ("localhost" in request.get_host() or "127.0.0.1" in request.get_host()):
            scheme = "http"
        return f"{scheme}://{self.get_primary_domain(request)}/courses/manage/dashboard/"

    @property
    def dashboard_url(self) -> str:
        return self.get_dashboard_url()



class TenantMenuItem(models.Model):
    """
    Customizable navigation menu links for an academy tenant's header.
    Defaults to: [হোম] [কোর্সসমূহ] [বইসমূহ] [ফ্রি রিসোর্স] [ব্লগ]
    Academies can add custom external links, internal pages, and reorder them.
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    title = models.CharField(max_length=100, help_text="Label displayed in navigation (e.g., 'কোর্সসমূহ')")
    url = models.CharField(
        max_length=255,
        help_text="Path or external URL (e.g., '/courses/', '/books/', 'https://youtube.com')",
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order in the navigation bar")
    is_active = models.BooleanField(default=True, help_text="Visible in the public storefront header")
    open_in_new_tab = models.BooleanField(default=False, help_text="Open link in a new browser tab")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.tenant.slug}: {self.title} -> {self.url}"


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
        import logging
        import re
        logger = logging.getLogger(__name__)

        cleaned_number = re.sub(r"[^\d+]", "", str(recipient).strip())
        if not cleaned_number:
            return {"success": False, "error": "Invalid recipient phone number."}

        if not self.is_enabled:
            return {"success": False, "error": "SMS sending is currently disabled for this academy."}

        # If live credentials are provided, attempt real dispatch
        if self.api_key and self.provider != self.Provider.GENERIC:
            try:
                import json
                import urllib.parse
                import urllib.request

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
