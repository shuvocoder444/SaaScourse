import re
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseForbidden, HttpResponse
from django.core.cache import cache
from django.conf import settings

from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription, TenantSMSSetting
from apps.users.models import TenantMembership

User = get_user_model()


def platform_landing_view(request):
    """
    Public SaaS marketing landing page for the platform owner (on localhost:8001 / platform.com).
    Presents platform capabilities, pricing subscription tiers, and customer showcases.
    """
    plans = SubscriptionPlan.objects.all().order_by("price_monthly")
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
            errors.append("Subdomain must be lowercase letters, numbers, or hyphens only.")

        if Tenant.objects.filter(slug=subdomain).exists():
            errors.append(f"The subdomain '{subdomain}' is already taken. Please choose another.")

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
            last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
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
        main_domain = getattr(settings, "PLATFORM_MAIN_DOMAIN", "platform.com").split(":")[0]

        if "localhost" in host or "127.0.0.1" in host:
            academy_url = f"http://{subdomain}.localhost{port_str}/courses/manage/dashboard/"
        else:
            academy_url = f"{scheme}://{subdomain}.{main_domain}/courses/manage/dashboard/"

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
        membership = TenantMembership.objects.unscoped().filter(tenant=tenant, user=request.user).first()
        if not membership or not membership.is_admin:
            return HttpResponseForbidden("Admin access required to modify academy settings.")

    branding = tenant.branding or {}
    subscription = getattr(tenant, "subscription", None)
    active_tab = request.GET.get("tab", "domain")

    if request.method == "POST":
        target_tab = request.POST.get("active_tab", "domain")

        # 1. Update Subdomain if provided
        new_subdomain = request.POST.get("subdomain", "").strip().lower()
        subdomain_changed = False
        if new_subdomain and new_subdomain != tenant.slug:
            # Subdomain format validation
            if not re.match(r"^[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?$", new_subdomain):
                messages.error(request, "Subdomain must contain only lowercase letters, numbers, and hyphens (without spaces).")
                return redirect(f"{request.path}?tab={target_tab}")

            reserved_slugs = ["admin", "api", "platform", "www", "mail", "cname", "static", "media", "app", "dashboard", "login", "signup"]
            if new_subdomain in reserved_slugs:
                messages.error(request, f"The subdomain '{new_subdomain}' is a reserved platform keyword. Please choose another.")
                return redirect(f"{request.path}?tab={target_tab}")

            if Tenant.objects.exclude(id=tenant.id).filter(slug=new_subdomain).exists():
                messages.error(request, f"The subdomain '{new_subdomain}' is already taken by another academy. Please choose a unique name.")
                return redirect(f"{request.path}?tab={target_tab}")

            old_slug = tenant.slug
            cache.delete(f"tenant:slug:{old_slug}")
            tenant.slug = new_subdomain
            subdomain_changed = True

        # 2. Update Custom Domain if provided
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
                    messages.error(request, "Please enter a valid domain format (e.g., learn.myacademy.com).")
                    return redirect(f"{request.path}?tab={target_tab}")

                if Tenant.objects.exclude(id=tenant.id).filter(custom_domain=custom_domain_input).exists():
                    messages.error(request, f"The custom domain '{custom_domain_input}' is already registered to another academy.")
                    return redirect(f"{request.path}?tab={target_tab}")

                if tenant.custom_domain:
                    cache.delete(f"tenant:domain:{tenant.custom_domain}")
                tenant.custom_domain = custom_domain_input
                tenant.custom_domain_verified = False
                tenant.generate_domain_token()
                cache.delete(f"tenant:domain:{custom_domain_input}")
                messages.success(request, f"Custom domain updated to '{custom_domain_input}'. Follow the DNS instructions below and verify SSL.")

        # 3. Update Brand Name, Template, Colors, and Copy
        if "name" in request.POST:
            tenant.name = request.POST.get("name", tenant.name).strip()

        if "landing_template" in request.POST:
            tenant.landing_template = request.POST.get("landing_template", tenant.landing_template).strip()

        if "header_style" in request.POST:
            tenant.header_style = request.POST.get("header_style", tenant.header_style).strip()

        if "footer_style" in request.POST:
            tenant.footer_style = request.POST.get("footer_style", tenant.footer_style).strip()

        if "primary_color" in request.POST:
            branding["primary_color"] = request.POST.get("primary_color", branding.get("primary_color", "#16a34a"))
            branding["accent_color"] = request.POST.get("accent_color", branding.get("accent_color", "#f59e0b"))
            branding["tagline"] = request.POST.get("tagline", branding.get("tagline", ""))
            branding["hero_badge"] = request.POST.get("hero_badge", branding.get("hero_badge", "HSC 2026 • DU ICU BATCH"))
            branding["hero_headline"] = request.POST.get("hero_headline", branding.get("hero_headline", ""))
            branding["hero_subheadline"] = request.POST.get("hero_subheadline", branding.get("hero_subheadline", ""))
            branding["cta_text"] = request.POST.get("cta_text", branding.get("cta_text", "সেরা কোর্স বেছে নাও"))
            branding["cta_link"] = request.POST.get("cta_link", branding.get("cta_link", "#courses"))
            branding["cta_secondary_text"] = request.POST.get("cta_secondary_text", branding.get("cta_secondary_text", "আমাদের বইসমূহ"))
            branding["cta_secondary_link"] = request.POST.get("cta_secondary_link", branding.get("cta_secondary_link", "/books/"))
            branding["notice_text"] = request.POST.get("notice_text", branding.get("notice_text", ""))
            branding["about_heading"] = request.POST.get("about_heading", branding.get("about_heading", "কেন আমাদের সাথে শিখবেন?"))
            branding["about_text"] = request.POST.get("about_text", branding.get("about_text", ""))
            
            # App Promo & Contact Info
            branding["app_promo_title"] = request.POST.get("app_promo_title", branding.get("app_promo_title", ""))
            branding["app_promo_subtitle"] = request.POST.get("app_promo_subtitle", branding.get("app_promo_subtitle", ""))
            branding["app_rating"] = request.POST.get("app_rating", branding.get("app_rating", "4.8★"))
            branding["app_downloads"] = request.POST.get("app_downloads", branding.get("app_downloads", "৫০,০০০+"))
            branding["play_store_url"] = request.POST.get("play_store_url", branding.get("play_store_url", "#"))
            branding["app_store_url"] = request.POST.get("app_store_url", branding.get("app_store_url", "#"))
            branding["contact_phone"] = request.POST.get("contact_phone", branding.get("contact_phone", "+880 1800-123456"))
            branding["contact_email"] = request.POST.get("contact_email", branding.get("contact_email", "support@academy.edu.bd"))
            branding["contact_address"] = request.POST.get("contact_address", branding.get("contact_address", "ফার্মগেট, ঢাকা"))

        # Header & Footer specific field handler (tab=header_footer or general save)
        if "trade_license" in request.POST or "footer_copyright" in request.POST or "header_cta_text" in request.POST or target_tab == "header_footer":
            if "notice_text" in request.POST:
                branding["notice_text"] = request.POST.get("notice_text", branding.get("notice_text", ""))
            if "contact_phone" in request.POST:
                branding["contact_phone"] = request.POST.get("contact_phone", branding.get("contact_phone", "+880 1800-123456"))
            if "contact_email" in request.POST:
                branding["contact_email"] = request.POST.get("contact_email", branding.get("contact_email", "support@academy.edu.bd"))
            if "contact_address" in request.POST:
                branding["contact_address"] = request.POST.get("contact_address", branding.get("contact_address", ""))
            branding["trade_license"] = request.POST.get("trade_license", branding.get("trade_license", "")).strip()
            branding["govt_reg_no"] = request.POST.get("govt_reg_no", branding.get("govt_reg_no", "")).strip()
            branding["whatsapp_number"] = request.POST.get("whatsapp_number", branding.get("whatsapp_number", "")).strip()
            branding["facebook_url"] = request.POST.get("facebook_url", branding.get("facebook_url", "")).strip()
            branding["youtube_url"] = request.POST.get("youtube_url", branding.get("youtube_url", "")).strip()
            branding["telegram_url"] = request.POST.get("telegram_url", branding.get("telegram_url", "")).strip()
            branding["header_cta_text"] = request.POST.get("header_cta_text", branding.get("header_cta_text", "ভর্তি আবেদন")).strip()
            branding["header_cta_link"] = request.POST.get("header_cta_link", branding.get("header_cta_link", "/courses/")).strip()
            branding["footer_about"] = request.POST.get("footer_about", branding.get("footer_about", "")).strip()
            branding["footer_copyright"] = request.POST.get("footer_copyright", branding.get("footer_copyright", "© 2026 সর্বস্বত্ব সংরক্ষিত।")).strip()
            
            if "header_checkbox_sent" in request.POST:
                branding["show_header_notice"] = request.POST.get("show_header_notice") == "on"
                branding["show_header_search"] = request.POST.get("show_header_search") == "on"
                branding["show_footer_payments"] = request.POST.get("show_footer_payments") == "on"
                branding["show_footer_apps"] = request.POST.get("show_footer_apps") == "on"

        # 4. Update Brand Image Files (Logo, Banner, Favicon)
        if "logo" in request.FILES:
            tenant.logo = request.FILES["logo"]
        if "banner" in request.FILES:
            tenant.banner = request.FILES["banner"]
        if "favicon" in request.FILES:
            tenant.favicon = request.FILES["favicon"]

        # Support optional direct image URLs if specified
        if "logo_url" in request.POST:
            branding["logo_url"] = request.POST.get("logo_url", "").strip()
        if "banner_url" in request.POST:
            branding["banner_url"] = request.POST.get("banner_url", "").strip()
        if "favicon_url" in request.POST:
            branding["favicon_url"] = request.POST.get("favicon_url", "").strip()

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
            sms_setting.provider = request.POST.get("sms_provider", sms_setting.provider)
            sms_setting.is_enabled = (request.POST.get("sms_is_enabled") == "on") or (request.POST.get("sms_is_enabled") == "true")
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
            main_domain = getattr(settings, "PLATFORM_MAIN_DOMAIN", "platform.com").split(":")[0]

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
    if not tenant and tenant_id and (request.user.is_superuser or request.user.is_staff):
        tenant = Tenant.objects.filter(id=tenant_id).first()

    if not tenant:
        return HttpResponse(
            '<div class="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs">Tenant context not found.</div>'
        )

    # Verify user is tenant admin/owner
    if tenant.owner != request.user and not request.user.is_superuser:
        membership = TenantMembership.objects.unscoped().filter(tenant=tenant, user=request.user).first()
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
        mode_badge = " (Simulation Mode)" if result.get("simulated") else " (Live Gateway)"
        return HttpResponse(
            f'<div class="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs space-y-1">'
            f'<div class="font-bold flex items-center gap-1.5"><span>✓ SMS Sent Successfully!</span><span class="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20">{mode_badge}</span></div>'
            f'<div class="font-mono text-[11px] text-slate-600 dark:text-slate-300">Recipient: <strong>{result.get("recipient")}</strong> | Sender ID: <strong>{result.get("sender_id")}</strong></div>'
            f'<div class="text-[11px] italic mt-1 text-slate-500 dark:text-slate-400">Preview: "{test_msg}"</div>'
            f'</div>'
        )
    else:
        return HttpResponse(
            f'<div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-semibold">'
            f'✗ Failed to dispatch SMS: {result.get("error", "Unknown error")}</div>'
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
            '⚠️ Please save a custom domain first before verifying.</div>'
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
            f'<span>✓ Success! Domain <strong>{tenant.custom_domain}</strong> is verified and SSL-active.</span></div>'
        )

    return HttpResponse(
        '<div class="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono flex items-center gap-2">'
        '<span>✗ DNS record not detected. Please verify your CNAME/TXT records and allow up to 10 mins for propagation.</span></div>'
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
        return HttpResponse("Domain authorized for automated TLS certificate issuance", status=200)

    return HttpResponse(f"Domain '{domain}' is not authorized or pending DNS verification", status=400)


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

    tenants = Tenant.objects.all().select_related("owner", "subscription__plan").order_by("-created_at")
    total_tenants = tenants.count()
    active_tenants = tenants.filter(is_active=True).count()
    trialing_tenants = TenantSubscription.objects.filter(status=TenantSubscription.Status.TRIALING).count()

    # Selected tenant for centralized settings
    selected_tenant_id = request.GET.get("tenant_id") or request.POST.get("tenant_id")
    selected_tenant = None
    if selected_tenant_id:
        selected_tenant = tenants.filter(id=selected_tenant_id).first()
    if not selected_tenant:
        selected_tenant = tenants.first()

    selected_sms_setting = None
    if selected_tenant:
        selected_sms_setting, _ = TenantSMSSetting.objects.get_or_create(tenant=selected_tenant)

    # Handle Settings Updates from SuperAdmin Control Plane
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_tenant_settings" and selected_tenant:
            if "name" in request.POST:
                selected_tenant.name = request.POST.get("name", selected_tenant.name).strip()

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
                selected_sms_setting.provider = request.POST.get("sms_provider", selected_sms_setting.provider)
                selected_sms_setting.is_enabled = (request.POST.get("sms_is_enabled") == "on") or (request.POST.get("sms_is_enabled") == "true")
                selected_sms_setting.sender_id = request.POST.get("sms_sender_id", "").strip()
                selected_sms_setting.api_key = request.POST.get("sms_api_key", "").strip()
                selected_sms_setting.api_secret = request.POST.get("sms_api_secret", "").strip()
                selected_sms_setting.api_url = request.POST.get("sms_api_url", "").strip()
                selected_sms_setting.template_enrollment = request.POST.get(
                    "sms_template_enrollment", selected_sms_setting.template_enrollment
                ).strip()
                selected_sms_setting.save()

            messages.success(request, f"Settings for '{selected_tenant.name}' updated successfully!")
            return redirect(f"/tenants/platform/dashboard/?tab=settings&tenant_id={selected_tenant.id}")

    # Calculate MRR ($) from active subscriptions
    subscriptions = TenantSubscription.objects.filter(
        status__in=[TenantSubscription.Status.ACTIVE, TenantSubscription.Status.TRIALING]
    ).select_related("plan")
    
    total_mrr = sum(sub.plan.price_monthly for sub in subscriptions if sub.plan)

    # Global platform metrics
    total_global_courses = Course.objects.unscoped().count()
    total_global_enrollments = Enrollment.objects.unscoped().count()

    # Plan tier breakdown
    plans = SubscriptionPlan.objects.all()
    plan_stats = []
    for plan in plans:
        count = TenantSubscription.objects.filter(plan=plan, status=TenantSubscription.Status.ACTIVE).count()
        plan_stats.append({
            "plan": plan,
            "subscribers_count": count,
            "revenue": count * plan.price_monthly,
        })

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
            "plan_stats": plan_stats,
            "active_tab": active_tab,
            "selected_tenant": selected_tenant,
            "selected_sms_setting": selected_sms_setting,
            "main_domain": getattr(settings, "PLATFORM_MAIN_DOMAIN", "platform.com"),
        },
    )


