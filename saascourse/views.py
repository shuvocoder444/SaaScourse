from django.http import HttpResponse, JsonResponse
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
        courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related(
            "instructor"
        )
        books = Book.objects.filter(in_stock=True).order_by(
            "-is_featured", "-created_at"
        )[:10]
        resources = FreeResource.objects.filter(is_published=True).order_by(
            "-created_at"
        )[:6]
        blog_posts = BlogPost.objects.filter(is_published=True).order_by("-created_at")[
            :6
        ]
        gallery_images = GalleryImage.objects.all().order_by("order", "-created_at")[:8]

        # Select template based on tenant configuration
        template_name = getattr(tenant, "landing_template", "edtech_bangla")
        template_map = {
            "edtech_bangla": "courses/frontend/templates/edtech_bangla.html",
            "modern_saas": "courses/frontend/templates/modern_saas.html",
            "classic_coaching": "courses/frontend/templates/classic_coaching.html",
        }
        target_template = template_map.get(
            template_name, "courses/frontend/templates/edtech_bangla.html"
        )

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


def manifest_json_view(request):
    """
    Generates a dynamic WebApp Manifest per tenant academy.
    Allows Android Chrome/Edge/Samsung Internet and iOS to install each coaching academy
    as its own standalone Progressive Web App (PWA) with custom brand icon, title and theme colors.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        from apps.tenants.models import Tenant

        tenant_id = request.GET.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()

    name = tenant.name if tenant else "CourseFlow Academy"
    short_name = (
        (tenant.name[:12] if len(tenant.name) > 12 else tenant.name)
        if tenant
        else "CourseFlow"
    )
    branding = tenant.branding if tenant and tenant.branding else {}
    primary_color = branding.get("primary_color", "#16a34a")
    tagline = branding.get("tagline", "স্মার্ট এডুকেশন একাডেমি")

    # Icon resolution: Tenant logo or dynamic branded PWA icon
    icon_src = (
        tenant.get_logo_url if (tenant and tenant.get_logo_url) else "/pwa-icon.svg"
    )

    manifest_data = {
        "id": f"academy-{tenant.slug if tenant else 'default'}",
        "name": f"{name} - {tagline}",
        "short_name": short_name,
        "description": tenant.meta_description
        if (tenant and tenant.meta_description)
        else f"{name} এর অফিসিয়াল মোবাইল অ্যাপ। ঘরে বসেই লাইভ ক্লাস, মডেল টেস্ট ও স্টাডি মেটেরিয়ালস উপভোগ করুন।",
        "start_url": "/?utm_source=pwa",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "window-controls-overlay"],
        "orientation": "portrait-primary",
        "background_color": "#ffffff",
        "theme_color": primary_color,
        "categories": ["education", "courses", "learning"],
        "icons": [
            {
                "src": icon_src,
                "sizes": "192x192 512x512",
                "type": "image/svg+xml" if icon_src.endswith(".svg") else "image/png",
                "purpose": "any maskable",
            },
            {
                "src": icon_src,
                "sizes": "512x512",
                "type": "image/svg+xml" if icon_src.endswith(".svg") else "image/png",
                "purpose": "any maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "কোর্সসমূহ",
                "short_name": "কোর্স",
                "description": f"{name} এর সকল কোর্স দেখুন",
                "url": "/courses/?utm_source=pwa_shortcut",
                "icons": [{"src": icon_src, "sizes": "192x192"}],
            },
            {
                "name": "আমার ড্যাশবোর্ড",
                "short_name": "ড্যাশবোর্ড",
                "description": "ক্লাস ও পরীক্ষার ড্যাশবোর্ড",
                "url": "/dashboard/?utm_source=pwa_shortcut",
                "icons": [{"src": icon_src, "sizes": "192x192"}],
            },
            {
                "name": "বই ও প্রকাশনা",
                "short_name": "বইসমূহ",
                "description": "একাডেমির প্রকাশিত বই ও গাইড",
                "url": "/books/?utm_source=pwa_shortcut",
                "icons": [{"src": icon_src, "sizes": "192x192"}],
            },
            {
                "name": "ফ্রি রিসোর্স",
                "short_name": "রিসোর্স",
                "description": "ফ্রি লেকচার শিট ও সাজেশন",
                "url": "/resources/?utm_source=pwa_shortcut",
                "icons": [{"src": icon_src, "sizes": "192x192"}],
            },
        ],
    }
    return JsonResponse(manifest_data, content_type="application/manifest+json")


def pwa_icon_svg_view(request):
    """
    Dynamically generates a high-resolution SVG app icon styled with the current tenant's brand color & initial.
    """
    tenant = getattr(request, "tenant", None)
    letter = tenant.name[0].upper() if (tenant and tenant.name) else "A"
    branding = tenant.branding if tenant and tenant.branding else {}
    primary_color = branding.get("primary_color", "#16a34a")

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{primary_color}" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="128" fill="url(#brandGrad)" />
  <circle cx="256" cy="256" r="190" fill="#ffffff" fill-opacity="0.1" />
  <text x="50%" y="54%" text-anchor="middle" dominant-baseline="central" fill="#ffffff" font-size="230" font-family="'Hind Siliguri', 'Segoe UI', sans-serif" font-weight="900">{letter}</text>
  <path d="M 180 390 L 332 390" stroke="#f59e0b" stroke-width="18" stroke-linecap="round" />
</svg>"""
    return HttpResponse(svg_content, content_type="image/svg+xml")


def service_worker_view(request):
    """
    High-performance Service Worker for Progressive Web App.
    Provides offline fallback and network-first shell caching.
    """
    sw_code = """// Academy Mobile Progressive Web App Service Worker
const CACHE_NAME = 'academy-pwa-cache-v2';
const OFFLINE_URL = '/offline/';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                OFFLINE_URL,
                '/manifest.json',
                '/pwa-icon.svg'
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(
                keyList.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.open(CACHE_NAME).then((cache) => {
                    return cache.match(OFFLINE_URL);
                });
            })
        );
    }
});
"""
    return HttpResponse(sw_code, content_type="application/javascript")


def offline_view(request):
    """
    Custom branded offline page served by the Service Worker when internet connection is lost.
    """
    tenant = getattr(request, "tenant", None)
    return render(
        request,
        "offline.html",
        {
            "tenant": tenant,
            "branding": tenant.branding if tenant and tenant.branding else {},
        },
    )
