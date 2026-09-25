from django.shortcuts import render

from apps.courses.models import BlogPost, Book, Course, FreeResource, GalleryImage
from apps.tenants.views import platform_landing_view


def root_home_view(request):
    """
    Dual-purpose root router:
    - If accessed on tenant subdomain/domain -> renders that tenant's dedicated academy storefront
      using their chosen landing page layout (edtech_bangla, modern_saas, or classic_coaching).
    - If accessed on platform main domain -> renders platform owner's SaaS subscription sales page.
    """
    if request.tenant: 
        tenant = request.tenant
        courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("instructor")
        books = Book.objects.filter(in_stock=True).order_by("-is_featured", "-created_at")[:8]
        resources = FreeResource.objects.filter(is_published=True).order_by("-created_at")[:6]
        blog_posts = BlogPost.objects.filter(is_published=True).order_by("-created_at")[:6]
        gallery_images = GalleryImage.objects.all().order_by("order", "-created_at")[:8]

        # Select template based on tenant configuration
        template_name = getattr(tenant, "landing_template", "edtech_bangla")
        template_map = {
            "edtech_bangla": "courses/frontend/templates/edtech_bangla.html",
            "modern_saas": "courses/frontend/templates/modern_saas.html",
            "classic_coaching": "courses/frontend/templates/classic_coaching.html",
        }
        target_template = template_map.get(template_name, "courses/frontend/templates/edtech_bangla.html")

        enrolled_course_ids = set()
        if request.user.is_authenticated:
            from apps.courses.models import Enrollment
            enrolled_course_ids = set(
                Enrollment.objects.filter(
                    tenant=tenant,
                    user=request.user,
                    status=Enrollment.Status.ACTIVE,
                ).values_list("course_id", flat=True)
            )

        context = {
            "tenant": tenant,
            "branding": tenant.branding or {},
            "courses": courses,
            "books": books,
            "resources": resources,
            "blog_posts": blog_posts,
            "gallery_images": gallery_images,
            "enrolled_course_ids": enrolled_course_ids,
        }

        return render(request, target_template, context)

    return platform_landing_view(request)
