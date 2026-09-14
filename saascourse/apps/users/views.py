from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from apps.tenants.models import Tenant
from apps.users.models import TenantMembership

User = get_user_model()


def login_view(request):
    """
    Authentication portal supporting standard credentials and 1-Click Quick Demo logins.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"

    if request.method == "POST":
        demo_role = request.POST.get("demo_role")

        if demo_role:
            # 1-Click Quick Demo Login
            email_map = {
                "superadmin": "admin@platform.com",
                "instructor": "sarah@alpha.io",
                "student": "alex@student.com",
            }
            target_email = email_map.get(demo_role)
            if target_email:
                user = User.objects.filter(email=target_email).first()
                if user:
                    login(request, user)
                    messages.success(request, f"Logged in successfully as {user.get_full_name() or user.email} ({demo_role.title()})")
                    return redirect(next_url)

        # Standard Email & Password
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.email}!")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email address or password. Please try again.")

    return render(
        request,
        "users/login.html",
        {
            "next": next_url,
            "current_tenant": getattr(request, "tenant", None),
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
