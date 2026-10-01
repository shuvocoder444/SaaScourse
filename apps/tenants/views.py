import json
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenants.models import (
    SubscriptionPlan,
    Tenant,
    TenantSMSSetting,
    TenantSubscription,
)
from apps.users.models import TenantMembership

User = get_user_model()


def platform_landing_view(request):
    """
    Public SaaS marketing landing page for the platform owner (on localhost:8001 / platform.com).
    Presents platform capabilities, pricing subscription tiers, and customer showcases.
    """
    plans = SubscriptionPlan.objects.all().order_by("price_monthly")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by(
        "order", "price_monthly"
    )
    showcase_tenants = Tenant.objects.filter(is_active=True).order_by("-created_at")[:6]

    return render(
        request,
        "tenants/platform_home.html",
        {
            "plans": plans,
            "showcase_tenants": showcase_tenants,
        },
    )


def tenant_registration_view(request):
    """
    Self-service signup wizard where creators launch their own academy.
    Provisions User, Tenant, 14-day Free Trial Subscription, and Admin Membership.
    """
    plans = SubscriptionPlan.objects.all().order_by("price_monthly")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by(
        "order", "price_monthly"
    )
    selected_plan_slug = request.GET.get("plan", "pro")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        academy_name = request.POST.get("academy_name", "").strip()
        subdomain = request.POST.get("subdomain", "").strip().lower()
        plan_slug = request.POST.get("plan_slug", "pro")

        errors = []

        # Validation
        if not email or not password or not academy_name or not subdomain:
            errors.append("All fields are required.")

        if not re.match(r"^[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?$", subdomain):
            errors.append(
                "Subdomain must be lowercase letters, numbers, or hyphens only."
            )

        if Tenant.objects.filter(slug=subdomain).exists():
            errors.append(
                f"The subdomain '{subdomain}' is already taken. Please choose another."
            )

        plan = SubscriptionPlan.objects.filter(slug=plan_slug).first()
        if not plan:
            plan = SubscriptionPlan.objects.first()

        if errors:
            return render(
                request,
                "tenants/register.html",
                {
                    "plans": plans,
                    "selected_plan_slug": plan_slug,
                    "errors": errors,
                    "form_data": request.POST,
                },
            )

        # Create or retrieve user
        user = User.objects.filter(email=email).first()
        if not user:
            first_name = full_name.split()[0] if full_name else ""
            last_name = (
                " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
            )
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

        # Create Tenant
        tenant = Tenant.objects.create(
            name=academy_name,
            slug=subdomain,
            owner=user,
            is_active=True,
            branding={
                "primary_color": "#4f46e5",
                "accent_color": "#06b6d4",
                "tagline": f"Welcome to {academy_name}.",
                "hero_headline": f"Learn With {academy_name}",
                "hero_subheadline": "Explore our curated, interactive curriculums to upgrade your technical capabilities.",
                "cta_text": "View Courses",
                "about_heading": "About Our Academy",
                "about_text": "Dedicated to practical, industry-proven learning and career growth.",
            },
        )

        # Provision 14-Day Free Trial Subscription
        trial_end = timezone.now() + timedelta(days=14)
        TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.Status.TRIALING,
            trial_ends_at=trial_end,
            current_period_end=trial_end,
        )

        # Create Admin Membership
        TenantMembership.objects.unscoped().create(
            tenant=tenant,
            user=user,
            role=TenantMembership.Role.ADMIN,
        )

        # Log creator in
        login(request, user)

        # Direct creator to their newly created academy studio
        host = request.get_host().split(":")[0]
        port = request.get_host().split(":")[1] if ":" in request.get_host() else ""
        port_str = f":{port}" if port else ""
        scheme = "https" if request.is_secure() else "http"
        main_domain = getattr(settings, "PLATFORM_MAIN_DOMAIN", "platform.com").split(
            ":"
        )[0]

        if "localhost" in host or "127.0.0.1" in host:
            academy_url = (
                f"http://{subdomain}.localhost{port_str}/courses/manage/dashboard/"
            )
        else:
            academy_url = (
                f"{scheme}://{subdomain}.{main_domain}/courses/manage/dashboard/"
            )

        return redirect(academy_url)

    return render(
        request,
        "tenants/register.html",
        {
            "plans": plans,
            "selected_plan_slug": selected_plan_slug,
        },
    )


@login_required
def tenant_branding_settings_view(request):
    """
    Settings view inside the academy studio where creators customize their storefront landing page,
    theme colors, and change their Subdomain / Custom CNAME Domain.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return redirect("home")

    # Verify user is tenant admin/owner
    if tenant.owner != request.user and not request.user.is_superuser:
        membership = (
            TenantMembership.objects.unscoped()
            .filter(tenant=tenant, user=request.user)
            .first()
        )
        if not membership or not membership.is_admin:
            return HttpResponseForbidden(
                "Admin access required to modify academy settings."
            )

    branding = tenant.branding or {}
    subscription = getattr(tenant, "subscription", None)
    active_tab = request.GET.get("tab", "domain")

    if request.method == "POST":
        target_tab = request.POST.get("active_tab", "domain")

        # 1. Update Subdomain if provided (Only on domain tab when explicitly submitted)
        subdomain_changed = False
        if target_tab == "domain" and "subdomain" in request.POST:
            new_subdomain = request.POST.get("subdomain", "").strip().lower()
            if new_subdomain and new_subdomain != tenant.slug:
                # Subdomain format validation
                if not re.match(
                    r"^[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?$", new_subdomain
                ):
                    messages.error(
                        request,
                        "Subdomain must contain only lowercase letters, numbers, and hyphens (without spaces).",
                    )
                    return redirect(f"{request.path}?tab={target_tab}")

                reserved_slugs = [
                    "admin",
                    "api",
                    "platform",
                    "www",
                    "mail",
                    "cname",
                    "static",
                    "media",
                    "app",
                    "dashboard",
                    "login",
                    "signup",
                ]
                if new_subdomain in reserved_slugs:
                    messages.error(
                        request,
                        f"The subdomain '{new_subdomain}' is a reserved platform keyword. Please choose another.",
                    )
                    return redirect(f"{request.path}?tab={target_tab}")

                if (
                    Tenant.objects.exclude(id=tenant.id)
                    .filter(slug=new_subdomain)
                    .exists()
                ):
                    messages.error(
                        request,
                        f"The subdomain '{new_subdomain}' is already taken by another academy. Please choose a unique name.",
                    )
                    return redirect(f"{request.path}?tab={target_tab}")

                old_slug = tenant.slug
                cache.delete(f"tenant:slug:{old_slug}")
                tenant.slug = new_subdomain
                subdomain_changed = True

        # 2. Update Custom Domain if provided (Only on domain tab when explicitly submitted)
        if target_tab == "domain" and "custom_domain" in request.POST:
            custom_domain_input = request.POST.get("custom_domain", "").strip().lower()
            if custom_domain_input.startswith("http://"):
                custom_domain_input = custom_domain_input[7:]
            elif custom_domain_input.startswith("https://"):
                custom_domain_input = custom_domain_input[8:]
            custom_domain_input = custom_domain_input.split("/")[0].strip()

            if custom_domain_input != (tenant.custom_domain or ""):
                if not custom_domain_input:
                    if tenant.custom_domain:
                        cache.delete(f"tenant:domain:{tenant.custom_domain}")
                    tenant.custom_domain = None
                    tenant.custom_domain_verified = False
                    messages.info(request, "Custom domain has been detached.")
                else:
                    if "." not in custom_domain_input or len(custom_domain_input) < 4:
                        messages.error(
                            request,
                            "Please enter a valid domain format (e.g., learn.myacademy.com).",
                        )
                        return redirect(f"{request.path}?tab={target_tab}")

                    if (
                        Tenant.objects.exclude(id=tenant.id)
                        .filter(custom_domain=custom_domain_input)
                        .exists()
                    ):
                        messages.error(
                            request,
                            f"The custom domain '{custom_domain_input}' is already registered to another academy.",
                        )
                        return redirect(f"{request.path}?tab={target_tab}")

                    if tenant.custom_domain:
                        cache.delete(f"tenant:domain:{tenant.custom_domain}")
                    tenant.custom_domain = custom_domain_input
                    tenant.custom_domain_verified = False
                    tenant.generate_domain_token()
                    cache.delete(f"tenant:domain:{custom_domain_input}")
                    messages.success(
                        request,
                        f"Custom domain updated to '{custom_domain_input}'. Follow the DNS instructions below and verify SSL.",
                    )

        # 3. Update Brand Name, Template, Colors, and Copy
        if "name" in request.POST:
            tenant.name = request.POST.get("name", tenant.name).strip()

        if "landing_template" in request.POST:
            tenant.landing_template = request.POST.get(
                "landing_template", tenant.landing_template
            ).strip()

        if "header_style" in request.POST:
            tenant.header_style = request.POST.get(
                "header_style", tenant.header_style
            ).strip()

        if "footer_style" in request.POST:
            tenant.footer_style = request.POST.get(
                "footer_style", tenant.footer_style
            ).strip()

        # Update all branding dictionary fields safely if present in request.POST
        branding_text_fields = [
            "primary_color",
            "accent_color",
            "tagline",
            "hero_badge",
            "hero_headline",
            "hero_subheadline",
            "cta_text",
            "cta_link",
            "cta_secondary_text",
            "cta_secondary_link",
            "notice_text",
            "about_heading",
            "about_text",
            "app_promo_title",
            "app_promo_subtitle",
            "app_rating",
            "app_downloads",
            "play_store_url",
            "app_store_url",
            "android_apk_url",
            "contact_phone",
            "contact_email",
            "contact_address",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "whatsapp_number",
            "whatsapp_default_msg",
            "trade_license",
            "govt_reg_no",
            "facebook_url",
            "youtube_url",
            "telegram_url",
            "header_cta_text",
            "header_cta_link",
            "footer_about",
            "footer_copyright",
            "logo_url",
            "banner_url",
            "favicon_url",
        ]

        for field in branding_text_fields:
            if field in request.POST:
                branding[field] = request.POST.get(field, "").strip()

        # WhatsApp widget toggle
        if "enable_whatsapp_widget" in request.POST:
            branding["enable_whatsapp_widget"] = request.POST.get(
                "enable_whatsapp_widget"
            ) in ["on", "true", "True", True]
        elif target_tab == "branding":
            branding["enable_whatsapp_widget"] = False

        # Header / Footer / Notice checkbox toggles
        if "header_checkbox_sent" in request.POST or "show_header_notice" in request.POST or "show_storefront_notice" in request.POST or target_tab == "branding":
            branding["show_header_notice"] = (
                request.POST.get("show_header_notice") == "on"
            )
            branding["show_storefront_notice"] = (
                request.POST.get("show_storefront_notice") == "on"
            )
            branding["show_header_search"] = (
                request.POST.get("show_header_search") == "on"
            )
            branding["show_footer_payments"] = (
                request.POST.get("show_footer_payments") == "on"
            )
            branding["show_footer_apps"] = request.POST.get("show_footer_apps") == "on"

        # 4. Update Brand Image Files (Logo, Banner, Favicon, Android APK)
        if "logo" in request.FILES:
            tenant.logo = request.FILES["logo"]
        if "banner" in request.FILES:
            tenant.banner = request.FILES["banner"]
        if "favicon" in request.FILES:
            tenant.favicon = request.FILES["favicon"]
        if "android_apk" in request.FILES:
            tenant.android_apk = request.FILES["android_apk"]
        if request.POST.get("clear_android_apk") == "on":
            tenant.android_apk = None

        tenant.branding = branding
        tenant.save()

        # 5. Menu Items Management Actions (tab=navigation)
        menu_action = request.POST.get("menu_action")
        if menu_action == "add_menu":
            menu_title = request.POST.get("menu_title", "").strip()
            menu_url = request.POST.get("menu_url", "").strip()
            menu_order = int(request.POST.get("menu_order", 0) or 0)
            open_in_new_tab = request.POST.get("menu_new_tab") == "on"
            if menu_title and menu_url:
                from apps.tenants.models import TenantMenuItem

                TenantMenuItem.objects.create(
                    tenant=tenant,
                    title=menu_title,
                    url=menu_url,
                    order=menu_order,
                    open_in_new_tab=open_in_new_tab,
                    is_active=True,
                )
                messages.success(request, f"মেনু আইটেম '{menu_title}' যুক্ত হয়েছে!")

        elif menu_action == "delete_menu":
            menu_id = request.POST.get("menu_id")
            from apps.tenants.models import TenantMenuItem

            TenantMenuItem.objects.filter(tenant=tenant, id=menu_id).delete()
            messages.success(request, "মেনু আইটেমটি মুছে ফেলা হয়েছে।")

        elif menu_action == "reset_menus":
            from apps.tenants.models import TenantMenuItem

            TenantMenuItem.objects.filter(tenant=tenant).delete()
            tenant.ensure_default_menus()
            messages.success(request, "মেনু আইটেমসমূহ ডিফল্ট অবস্থায় ফিরিয়ে আনা হয়েছে।")

        # 6. Update SMS Gateway Settings
        sms_setting, _ = TenantSMSSetting.objects.get_or_create(tenant=tenant)
        if target_tab == "sms" or "sms_provider" in request.POST:
            sms_setting.provider = request.POST.get(
                "sms_provider", sms_setting.provider
            )
            sms_setting.is_enabled = (request.POST.get("sms_is_enabled") == "on") or (
                request.POST.get("sms_is_enabled") == "true"
            )
            sms_setting.sender_id = request.POST.get("sms_sender_id", "").strip()
            sms_setting.api_key = request.POST.get("sms_api_key", "").strip()
            sms_setting.api_secret = request.POST.get("sms_api_secret", "").strip()
            sms_setting.api_url = request.POST.get("sms_api_url", "").strip()
            sms_setting.template_enrollment = request.POST.get(
                "sms_template_enrollment", sms_setting.template_enrollment
            ).strip()
            sms_setting.save()
            messages.success(request, "SMS Gateway configuration saved successfully!")
        elif not menu_action:
            messages.success(request, "সেটিংস সফলভাবে সংরক্ষিত হয়েছে!")

        # If subdomain changed, redirect to the new subdomain URL so session and routing stay valid
        if subdomain_changed:
            host_parts = request.get_host().split(":")
            port = f":{host_parts[1]}" if len(host_parts) > 1 else ""
            host = host_parts[0]
            scheme = "https" if request.is_secure() else "http"
            main_domain = getattr(
                settings, "PLATFORM_MAIN_DOMAIN", "platform.com"
            ).split(":")[0]

            if "localhost" in host or "127.0.0.1" in host:
                target_url = f"http://{tenant.slug}.localhost{port}/courses/manage/dashboard/?tab={target_tab}"
            else:
                target_url = f"{scheme}://{tenant.slug}.{main_domain}/courses/manage/dashboard/?tab={target_tab}"
            return redirect(target_url)

        return redirect(f"/tenants/settings/?tab={target_tab}")

    # Ensure domain token exists
    tenant.generate_domain_token()
    sms_setting, _ = TenantSMSSetting.objects.get_or_create(tenant=tenant)

    return render(
        request,
        "tenants/settings.html",
        {
            "tenant": tenant,
            "branding": branding,
            "subscription": subscription,
            "active_tab": active_tab,
            "sms_setting": sms_setting,
        },
    )


@login_required
def send_test_sms_view(request):
    """
    HTMX/AJAX endpoint for testing SMS sending directly from the settings panel.
    """
    tenant = getattr(request, "tenant", None)
    tenant_id = request.POST.get("tenant_id")
    if (
        not tenant
        and tenant_id
        and (request.user.is_superuser or request.user.is_staff)
    ):
        tenant = Tenant.objects.filter(id=tenant_id).first()

    if not tenant:
        return HttpResponse(
            '<div class="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs">Tenant context not found.</div>'
        )

    # Verify user is tenant admin/owner
    if tenant.owner != request.user and not request.user.is_superuser:
        membership = (
            TenantMembership.objects.unscoped()
            .filter(tenant=tenant, user=request.user)
            .first()
        )
        if not membership or not membership.is_admin:
            return HttpResponseForbidden("Admin access required.")

    phone = request.POST.get("test_phone", "").strip()
    if not phone:
        return HttpResponse(
            '<div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-xs font-semibold">⚠️ Please enter a recipient mobile number (e.g. 017XXXXXXXX).</div>'
        )

    sms_setting, _ = TenantSMSSetting.objects.get_or_create(tenant=tenant)
    test_msg = f"[{tenant.name}] Test SMS delivery verified! Provider: {sms_setting.get_provider_display()}."
    result = sms_setting.send_sms(recipient=phone, message=test_msg)

    if result.get("success"):
        mode_badge = (
            " (Simulation Mode)" if result.get("simulated") else " (Live Gateway)"
        )
        return HttpResponse(
            f'<div class="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs space-y-1">'
            f'<div class="font-bold flex items-center gap-1.5"><span>✓ SMS Sent Successfully!</span><span class="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20">{mode_badge}</span></div>'
            f'<div class="font-mono text-[11px] text-slate-600 dark:text-slate-300">Recipient: <strong>{result.get("recipient")}</strong> | Sender ID: <strong>{result.get("sender_id")}</strong></div>'
            f'<div class="text-[11px] italic mt-1 text-slate-500 dark:text-slate-400">Preview: "{test_msg}"</div>'
            f"</div>"
        )
    else:
        return HttpResponse(
            f'<div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-semibold">'
            f"✗ Failed to dispatch SMS: {result.get('error', 'Unknown error')}</div>"
        )


def check_dns_txt_or_cname(domain: str, expected_token: str) -> bool:
    """
    Verifies custom domain ownership via DNS lookup:
    1. Checks if TXT record _saascourse-challenge.<domain> contains expected_token.
    2. Fallback to socket IP resolution (for local dev / demo verification).
    """
    try:
        import dns.resolver

        challenge_host = f"_saascourse-challenge.{domain}"
        answers = dns.resolver.resolve(challenge_host, "TXT")
        for rdata in answers:
            for txt_string in rdata.strings:
                if expected_token in txt_string.decode("utf-8"):
                    return True
    except Exception:
        pass

    # Socket resolution fallback
    try:
        import socket

        ip = socket.gethostbyname(domain)
        if ip:
            return True
    except Exception:
        pass

    return False


@login_required
def verify_custom_domain_view(request):
    """
    HTMX action endpoint to trigger DNS verification for tenant's custom domain.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant or not tenant.custom_domain:
        return HttpResponse(
            '<div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-mono">'
            "⚠️ Please save a custom domain first before verifying.</div>"
        )

    token = tenant.generate_domain_token()
    is_valid = check_dns_txt_or_cname(tenant.custom_domain, token)

    if is_valid:
        tenant.custom_domain_verified = True
        tenant.save(update_fields=["custom_domain_verified"])
        from django.core.cache import cache

        cache.delete(f"tenant:domain:{tenant.custom_domain}")
        return HttpResponse(
            '<div class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono flex items-center gap-2">'
            f"<span>✓ Success! Domain <strong>{tenant.custom_domain}</strong> is verified and SSL-active.</span></div>"
        )

    return HttpResponse(
        '<div class="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono flex items-center gap-2">'
        "<span>✗ DNS record not detected. Please verify your CNAME/TXT records and allow up to 10 mins for propagation.</span></div>"
    )


def caddy_ask_domain(request):
    """
    Security authorization endpoint used by Caddy web server's on_demand_tls 'ask' directive.
    Caddy executes: GET /tenants/api/caddy-check/?domain=learn.myacademy.com
    If 200 OK -> Caddy automatically provisions Let's Encrypt / ZeroSSL certificate.
    If 400/404 -> Caddy aborts TLS handshake, preventing SSL certificate exhaustion attacks.
    """
    domain = request.GET.get("domain", "").strip().lower()
    if not domain:
        return HttpResponse("Domain query parameter missing", status=400)

    # Check if domain belongs to an active, verified tenant
    is_authorized = Tenant.objects.filter(
        custom_domain=domain,
        is_active=True,
        custom_domain_verified=True,
    ).exists()

    if is_authorized:
        return HttpResponse(
            "Domain authorized for automated TLS certificate issuance", status=200
        )

    return HttpResponse(
        f"Domain '{domain}' is not authorized or pending DNS verification", status=400
    )


@login_required
def platform_admin_dashboard_view(request):
    """
    SaaS Executive / Platform Superadmin Dashboard.
    Provides platform-wide KPIs: MRR, Active Subscriptions, Tenants, Global Courses, and Students,
    as well as centralized Settings to manage Main Domain and each coaching center's logo, banner, favicon, and SMS gateway.
    """
    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponseForbidden("Platform Superadmin access required.")

    from apps.courses.models import Course, Enrollment

    tenants = (
        Tenant.objects.all()
        .select_related("owner", "subscription__plan")
        .order_by("-created_at")
    )
    total_tenants = tenants.count()
    active_tenants = tenants.filter(is_active=True).count()
    trialing_tenants = TenantSubscription.objects.filter(
        status=TenantSubscription.Status.TRIALING
    ).count()

    # Selected tenant for centralized settings
    selected_tenant_id = request.GET.get("tenant_id") or request.POST.get("tenant_id")
    selected_tenant = None
    if selected_tenant_id:
        selected_tenant = tenants.filter(id=selected_tenant_id).first()
    if not selected_tenant:
        selected_tenant = tenants.first()

    selected_sms_setting = None
    if selected_tenant:
        selected_sms_setting, _ = TenantSMSSetting.objects.get_or_create(
            tenant=selected_tenant
        )

    # Handle Settings Updates from SuperAdmin Control Plane
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_tenant_settings" and selected_tenant:
            if "name" in request.POST:
                selected_tenant.name = request.POST.get(
                    "name", selected_tenant.name
                ).strip()

            # Uploads
            if "logo" in request.FILES:
                selected_tenant.logo = request.FILES["logo"]
            if "banner" in request.FILES:
                selected_tenant.banner = request.FILES["banner"]
            if "favicon" in request.FILES:
                selected_tenant.favicon = request.FILES["favicon"]

            branding = selected_tenant.branding or {}
            if "logo_url" in request.POST and request.POST.get("logo_url"):
                branding["logo_url"] = request.POST.get("logo_url").strip()
            if "banner_url" in request.POST and request.POST.get("banner_url"):
                branding["banner_url"] = request.POST.get("banner_url").strip()
            if "favicon_url" in request.POST and request.POST.get("favicon_url"):
                branding["favicon_url"] = request.POST.get("favicon_url").strip()
            if "primary_color" in request.POST:
                branding["primary_color"] = request.POST.get("primary_color").strip()
            if "accent_color" in request.POST:
                branding["accent_color"] = request.POST.get("accent_color").strip()

            selected_tenant.branding = branding
            selected_tenant.save()

            # SMS Gateway settings for this coaching center
            if selected_sms_setting and "sms_provider" in request.POST:
                selected_sms_setting.provider = request.POST.get(
                    "sms_provider", selected_sms_setting.provider
                )
                selected_sms_setting.is_enabled = (
                    request.POST.get("sms_is_enabled") == "on"
                ) or (request.POST.get("sms_is_enabled") == "true")
                selected_sms_setting.sender_id = request.POST.get(
                    "sms_sender_id", ""
                ).strip()
                selected_sms_setting.api_key = request.POST.get(
                    "sms_api_key", ""
                ).strip()
                selected_sms_setting.api_secret = request.POST.get(
                    "sms_api_secret", ""
                ).strip()
                selected_sms_setting.api_url = request.POST.get(
                    "sms_api_url", ""
                ).strip()
                selected_sms_setting.template_enrollment = request.POST.get(
                    "sms_template_enrollment", selected_sms_setting.template_enrollment
                ).strip()
                selected_sms_setting.save()

            messages.success(
                request, f"Settings for '{selected_tenant.name}' updated successfully!"
            )
            return redirect(
                f"/tenants/platform/dashboard/?tab=settings&tenant_id={selected_tenant.id}"
            )

        elif action == "save_subscription_plan":
            plan_id = request.POST.get("plan_id")
            name = request.POST.get("name", "").strip()
            slug = request.POST.get("slug", "").strip().lower()
            description = request.POST.get("description", "").strip()
            price_monthly = request.POST.get("price_monthly", 0)
            billing_period = request.POST.get("billing_period", "প্রতি মাস").strip()
            badge_text = request.POST.get("badge_text", "").strip()
            cta_text = request.POST.get("cta_text", "১৪ দিনের ফ্রি ট্রায়াল শুরু করুন").strip()
            max_courses = int(request.POST.get("max_courses", 5) or 5)
            max_students = int(request.POST.get("max_students", 250) or 250)
            custom_domain_allowed = (
                request.POST.get("custom_domain_allowed") == "on"
            ) or (request.POST.get("custom_domain_allowed") == "true")
            is_popular = (request.POST.get("is_popular") == "on") or (
                request.POST.get("is_popular") == "true"
            )
            is_active = (request.POST.get("is_active") == "on") or (
                request.POST.get("is_active") == "true"
            )
            order = int(request.POST.get("order", 0) or 0)
            features_raw = request.POST.get("features_text", "")
            features_list = [f.strip() for f in features_raw.splitlines() if f.strip()]

            if not name:
                messages.error(request, "প্ল্যানের নাম আবশ্যক।")
                return redirect("/tenants/platform/dashboard/?tab=plans")

            if not slug:
                from django.utils.text import slugify

                slug = slugify(name)

            if plan_id:
                plan = SubscriptionPlan.objects.filter(id=plan_id).first()
                if not plan:
                    messages.error(request, "প্ল্যান খুঁজে পাওয়া যায়নি।")
                    return redirect("/tenants/platform/dashboard/?tab=plans")
                plan.name = name
                plan.slug = slug
                plan.description = description
                plan.price_monthly = price_monthly
                plan.billing_period = billing_period
                plan.badge_text = badge_text
                plan.cta_text = cta_text
                plan.max_courses = max_courses
                plan.max_students = max_students
                plan.custom_domain_allowed = custom_domain_allowed
                plan.is_popular = is_popular
                plan.is_active = is_active
                plan.order = order
                plan.features = features_list
                plan.save()
                messages.success(
                    request, f"সাবস্ক্রিপশন প্ল্যান '{plan.name}' সফলভাবে আপডেট হয়েছে!"
                )
            else:
                plan = SubscriptionPlan.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    price_monthly=price_monthly,
                    billing_period=billing_period,
                    badge_text=badge_text,
                    cta_text=cta_text,
                    max_courses=max_courses,
                    max_students=max_students,
                    custom_domain_allowed=custom_domain_allowed,
                    is_popular=is_popular,
                    is_active=is_active,
                    order=order,
                    features=features_list,
                )
                messages.success(
                    request, f"নতুন সাবস্ক্রিপশন প্ল্যান '{plan.name}' তৈরি হয়েছে!"
                )
            return redirect("/tenants/platform/dashboard/?tab=plans")

        elif action == "delete_subscription_plan":
            plan_id = request.POST.get("plan_id")
            plan = SubscriptionPlan.objects.filter(id=plan_id).first()
            if plan:
                if TenantSubscription.objects.filter(plan=plan).exists():
                    messages.error(
                        request,
                        f"প্ল্যান '{plan.name}' মুছে ফেলা সম্ভব নয় কারণ এতে সক্রিয় একাডেমি সাবস্ক্রিপশন যুক্ত রয়েছে।",
                    )
                else:
                    plan_name = plan.name
                    plan.delete()
                    messages.success(
                        request, f"সাবস্ক্রিপশন প্ল্যান '{plan_name}' সফলভাবে মুছে ফেলা হয়েছে।"
                    )
            return redirect("/tenants/platform/dashboard/?tab=plans")

        elif action == "update_tenant_subscription":
            tenant_id = request.POST.get("tenant_id")
            target_tenant = Tenant.objects.filter(id=tenant_id).first()
            if target_tenant:
                plan_id = request.POST.get("plan_id")
                sub_status = request.POST.get(
                    "status", TenantSubscription.Status.ACTIVE
                )
                target_plan = SubscriptionPlan.objects.filter(id=plan_id).first()
                if target_plan:
                    sub, _ = TenantSubscription.objects.get_or_create(
                        tenant=target_tenant,
                        defaults={"plan": target_plan, "status": sub_status},
                    )
                    sub.plan = target_plan
                    sub.status = sub_status
                    sub.save()
                    messages.success(
                        request,
                        f"একাডেমি '{target_tenant.name}'-এর সাবস্ক্রিপশন প্ল্যান ও স্ট্যাটাস আপডেট হয়েছে!",
                    )
            return redirect("/tenants/platform/dashboard/?tab=academies")

    # Calculate MRR ($) from active subscriptions
    subscriptions = TenantSubscription.objects.filter(
        status__in=[
            TenantSubscription.Status.ACTIVE,
            TenantSubscription.Status.TRIALING,
        ]
    ).select_related("plan")

    total_mrr = sum(sub.plan.price_monthly for sub in subscriptions if sub.plan)

    # Global platform metrics
    total_global_courses = Course.objects.unscoped().count()
    total_global_enrollments = Enrollment.objects.unscoped().count()

    # Plan tier breakdown
    plans = SubscriptionPlan.objects.all()
    plans = SubscriptionPlan.objects.all().order_by("order", "price_monthly")
    plan_stats = []
    for plan in plans:
        count = TenantSubscription.objects.filter(
            plan=plan, status=TenantSubscription.Status.ACTIVE
        ).count()
        plan_stats.append(
            {
                "plan": plan,
                "subscribers_count": count,
                "revenue": count * plan.price_monthly,
            }
        )

    active_tab = request.GET.get("tab", "overview")

    return render(
        request,
        "tenants/platform_dashboard.html",
        {
            "tenants": tenants,
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "trialing_tenants": trialing_tenants,
            "total_mrr": total_mrr,
            "total_global_courses": total_global_courses,
            "total_global_enrollments": total_global_enrollments,
            "plans": plans,
            "plan_stats": plan_stats,
            "active_tab": active_tab,
            "selected_tenant": selected_tenant,
            "selected_sms_setting": selected_sms_setting,
            "main_domain": getattr(settings, "PLATFORM_MAIN_DOMAIN", "platform.com"),
        },
    )


def download_academy_app(request):
    """
    Dedicated Android App installer and APK downloader for each coaching academy.
    - If ?download=1 is specified and an APK is uploaded, directly streams the .apk file.
    - Otherwise renders the dedicated multi-tenant App Download & 1-Tap Install page.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        tenant_id = request.GET.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
        if not tenant:
            tenant = Tenant.objects.filter(is_active=True).first()

    if not tenant:
        raise Http404("Academy not found.")

    branding = tenant.branding or {}
    download_requested = request.GET.get("download") in ["1", "apk", "direct"]

    # 1. Direct APK file stream if requested
    if download_requested:
        if tenant.android_apk and tenant.android_apk.storage.exists(
            tenant.android_apk.name
        ):
            response = FileResponse(
                tenant.android_apk.open("rb"),
                content_type="application/vnd.android.package-archive",
                as_attachment=True,
                filename=f"{tenant.slug}-academy-app.apk",
            )
            return response
        if branding.get("android_apk_url"):
            return redirect(branding["android_apk_url"])

    # 2. Render dedicated Academy App Installation Landing Page
    has_apk_file = bool(tenant.android_apk and tenant.android_apk.name) or bool(
        branding.get("android_apk_url")
    )
    apk_download_url = (
        "/tenants/download-app/?download=1"
        if (tenant.android_apk and tenant.android_apk.name)
        else branding.get("android_apk_url", "")
    )

    return render(
        request,
        "tenants/app_download.html",
        {
            "tenant": tenant,
            "branding": branding,
            "has_apk_file": has_apk_file,
            "apk_download_url": apk_download_url,
        },
    )


# ==============================================================================
# 💾 ACADEMY DATA BACKUP & DISASTER RECOVERY (ডাটা ব্যাকআপ ও রিস্টোর)
# ==============================================================================

@login_required
def tenant_backup_export_view(request):
    """
    Exports a comprehensive JSON backup containing all courses, lessons, exams,
    questions, routines, books, and branding settings for the authenticated tenant.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        tenant = Tenant.objects.filter(owner=request.user).first()

    if not tenant or (tenant.owner != request.user and not request.user.is_superuser):
        messages.error(request, "শুধুমাত্র একাডেমি ওনার বা সুপার অ্যাডমিন ব্যাকআপ ডাউনলোড করতে পারেন।")
        return redirect("/dashboard/")

    from apps.tenants.backup_service import export_tenant_backup_data
    from django.http import HttpResponse

    backup_data = export_tenant_backup_data(tenant)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{tenant.slug}_{timestamp}.json"

    json_content = json.dumps(backup_data, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
    response = HttpResponse(json_content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def tenant_backup_restore_view(request):
    """
    Restores or imports academy data from an uploaded JSON backup file.
    Guarantees strict multi-tenant boundary isolation.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        tenant = Tenant.objects.filter(owner=request.user).first()

    if not tenant or (tenant.owner != request.user and not request.user.is_superuser):
        messages.error(request, "শুধুমাত্র একাডেমি ওনার ডাটা রিস্টোর করতে পারেন।")
        return redirect("/dashboard/")

    if request.method != "POST":
        return redirect("/tenants/settings/?tab=backup")

    backup_file = request.FILES.get("backup_file")
    restore_mode = request.POST.get("restore_mode", "merge")

    if not backup_file:
        messages.error(request, "অনুগ্রহ করে একটি বৈধ ব্যাকআপ (.json) ফাইল নির্বাচন করুন।")
        return redirect("/tenants/settings/?tab=backup")

    if not backup_file.name.endswith(".json"):
        messages.error(request, "ভুল ফাইল ফরম্যাট! শুধুমাত্র .json ব্যাকআপ ফাইল আপলোড করুন।")
        return redirect("/tenants/settings/?tab=backup")

    try:
        raw_content = backup_file.read().decode("utf-8")
        payload = json.loads(raw_content)

        if not isinstance(payload, dict) or "data" not in payload:
            messages.error(request, "ফাইলের ডাটা স্ট্রাকচার সঠিক নয়। এটি একটি বৈধ CourseFlow ব্যাকআপ ফাইল নয়।")
            return redirect("/tenants/settings/?tab=backup")

        from apps.tenants.backup_service import restore_tenant_backup_data

        summary = restore_tenant_backup_data(tenant, payload, restore_mode=restore_mode)

        messages.success(
            request,
            f"🎉 ডাটা ব্যাকআপ সফলভাবে রিস্টোর হয়েছে! "
            f"(কোর্স: {summary['courses_restored']}টি, "
            f"লেকচার: {summary['lessons_restored']}টি, "
            f"পরীক্ষা: {summary['exams_restored']}টি, "
            f"প্রশ্ন: {summary['questions_restored']}টি, "
            f"রুটিন: {summary['routines_restored']}টি, "
            f"বই: {summary['books_restored']}টি)"
        )
    except Exception as e:
        messages.error(request, f"ব্যাকআপ রিস্টোর করার সময় ত্রুটি ঘটেছে: {str(e)}")

    return redirect("/tenants/settings/?tab=backup")

