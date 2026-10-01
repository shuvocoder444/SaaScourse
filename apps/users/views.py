import re

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import redirect, render

from apps.tenants.models import Tenant
from apps.users.models import TenantMembership

User = get_user_model()

 
 
def login_view(request):
    """
    Modern Authentication & Student Registration Portal.
    - Login: Validates email or mobile + password.
    - Register: Creates user (STUDENT role), assigns tenant membership, logs in.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"
    current_tenant = getattr(request, "tenant", None)
    initial_mode = request.GET.get("mode") or "login"

    if request.method == "POST":
        demo_role = request.POST.get("demo_role")
        if demo_role:
            demo_email_map = {
                "superadmin": "admin@platform.com",
                "creator": "sarah@academy.com",
                "student": "alex@student.com",
            }
            demo_email = demo_email_map.get(demo_role)
            if demo_email:
                demo_user = User.objects.filter(email=demo_email).first()
                if demo_user:
                    login(request, demo_user)
                    return redirect(next_url)

        auth_mode = request.POST.get("auth_mode", "login")
        identifier = request.POST.get("identifier", "").strip() or request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not identifier or not password:
            messages.error(request, "অনুগ্রহ করে মোবাইল নম্বর/ইমেইল এবং পাসওয়ার্ড প্রদান করুন।")
            return render(
                request,
                "users/login.html",
                {
                    "next": next_url,
                    "current_tenant": current_tenant,
                    "initial_mode": auth_mode,
                    "identifier": identifier,
                },
            )

        # Normalize email / phone
        if "@" in identifier:
            email = identifier.lower()
        else:
            clean_phone = re.sub(r"[^0-9+]", "", identifier)
            email = f"{clean_phone}@student.academy"

        if auth_mode == "login":
            user = authenticate(request, email=email, password=password)
            if user:
                login(request, user)
                if current_tenant:
                    TenantMembership.objects.get_or_create(
                        tenant=current_tenant,
                        user=user,
                        defaults={"role": TenantMembership.Role.STUDENT, "is_active": True},
                    )
                messages.success(request, f"স্বাগতম, {user.get_full_name() or user.email}!")
                return redirect(next_url)
            else:
                messages.error(request, "মোবাইল/ইমেইল অথবা পাসওয়ার্ড সঠিক নয়। অনুগ্রহ করে পুনরায় চেষ্টা করুন।")
                return render(
                    request,
                    "users/login.html",
                    {
                        "next": next_url,
                        "current_tenant": current_tenant,
                        "initial_mode": "login",
                        "identifier": identifier,
                    },
                )

        elif auth_mode == "register":
            full_name = request.POST.get("full_name", "").strip()
            if User.objects.filter(email=email).exists():
                messages.info(request, "এই মোবাইল/ইমেইলে ইতিমধ্যে অ্যাকাউন্ট রয়েছে। দয়া করে পাসওয়ার্ড দিয়ে লগইন করুন।")
                return render(
                    request,
                    "users/login.html",
                    {
                        "next": next_url,
                        "current_tenant": current_tenant,
                        "initial_mode": "login",
                        "identifier": identifier,
                    },
                )

            name_parts = full_name.split(" ", 1)
            first_name = name_parts[0] if name_parts else "Student"
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            if current_tenant:
                TenantMembership.objects.create(
                    tenant=current_tenant,
                    user=user,
                    role=TenantMembership.Role.STUDENT,
                    is_active=True,
                )

            login(request, user)
            messages.success(request, f"🎉 অ্যাকাউন্ট সফলভাবে তৈরি হয়েছে! স্বাগতম, {user.get_full_name()}।")
            return redirect(next_url)

    return render(
        request,
        "users/login.html",
        {
            "next": next_url,
            "current_tenant": current_tenant,
            "initial_mode": initial_mode,
        },
    )


def logout_view(request):
    """Logs out the user and redirects to home."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


def universal_dashboard_view(request):
    """
    Universal Smart Dashboard Dispatcher.
    Directs users to the appropriate role-specific dashboard:
    1. Root Domain + Superuser/Staff -> Platform Owner SaaS Executive Dashboard.
    2. Root Domain + Creator -> Platform Hub listing all their academies.
    3. Academy Subdomain + Admin/Instructor -> Instructor Studio Dashboard.
    4. Academy Subdomain + Student -> Student Learning Dashboard.
    """
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    tenant = getattr(request, "tenant", None)

    # -------------------------------------------------------------
    # CASE A: User is on Root Platform Domain (localhost:8001 / platform.com)
    # -------------------------------------------------------------
    if tenant is None:
        if request.user.is_superuser or request.user.is_staff:
            from apps.tenants.views import platform_admin_dashboard_view
            return platform_admin_dashboard_view(request)

        # Creator / Instructor who owns academies visiting platform root
        owned_academies = Tenant.objects.filter(owner=request.user)
        memberships = TenantMembership.objects.unscoped().filter(user=request.user).select_related("tenant")

        return render(
            request,
            "users/creator_portal.html",
            {
                "owned_academies": owned_academies,
                "memberships": memberships,
            },
        )

    # -------------------------------------------------------------
    # CASE B: User is on an Academy Subdomain (alpha.localhost:8001 / CNAME)
    # -------------------------------------------------------------
    # Check if user is academy owner, superuser, or instructor/admin member
    is_admin_or_instructor = (
        tenant.owner == request.user
        or request.user.is_superuser
    )

    if not is_admin_or_instructor:
        membership = TenantMembership.objects.unscoped().filter(
            tenant=tenant, user=request.user
        ).first()
        if membership and membership.role in [TenantMembership.Role.ADMIN, TenantMembership.Role.INSTRUCTOR]:
            is_admin_or_instructor = True

    if is_admin_or_instructor:
        from apps.courses.views import instructor_course_dashboard
        return instructor_course_dashboard(request)
    else:
        from apps.courses.views import student_learning_dashboard
        return student_learning_dashboard(request)
