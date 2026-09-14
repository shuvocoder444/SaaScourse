from django.shortcuts import render
from apps.courses.models import Course
from apps.tenants.views import platform_landing_view


def root_home_view(request):
    """
    Dual-purpose root router:
    - If accessed on tenant subdomain/domain -> renders that tenant's dedicated academy storefront.
    - If accessed on platform main domain -> renders platform owner's SaaS subscription sales page.
    """
    if request.tenant:
        courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("instructor")
        return render(
            request,
            "courses/frontend/academy_home.html",
            {
                "courses": courses,
            },
        )

    return platform_landing_view(request)
