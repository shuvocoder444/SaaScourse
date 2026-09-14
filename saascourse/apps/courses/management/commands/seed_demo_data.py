from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription
from apps.users.models import TenantMembership
from apps.courses.models import Course, Module, Lesson, Enrollment
from core.tenancy.context import tenant_context

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds subscription plans, demo academies, users, courses, modules, and lessons for testing multi-tenancy."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding multi-tenant SaaS and subscription data..."))

        # 1. SaaS Subscription Plans (Sold by Platform Admin)
        plan_starter, _ = SubscriptionPlan.objects.get_or_create(
            slug="starter",
            defaults={
                "name": "Starter",
                "price_monthly": 29.00,
                "max_courses": 5,
                "max_students": 250,
                "custom_domain_allowed": False,
                "is_popular": False,
                "features": [
                    "Up to 5 Published Courses",
                    "Up to 250 Students",
                    "Custom Subdomain (e.g. brand.platform)",
                    "Video Streaming & Markdown Articles",
                    "Interactive HTMX Progress Tracking",
                    "Standard Community Support",
                ],
            },
        )

        plan_pro, _ = SubscriptionPlan.objects.get_or_create(
            slug="pro",
            defaults={
                "name": "Professional",
                "price_monthly": 79.00,
                "max_courses": 25,
                "max_students": 2500,
                "custom_domain_allowed": True,
                "is_popular": True,
                "features": [
                    "Up to 25 Published Courses",
                    "Up to 2,500 Students",
                    "White-Label Custom CNAME Domain",
                    "Custom Theme & Color Branding",
                    "Unlimited Video & Media Hosting",
                    "Advanced Student Analytics",
                    "Priority 24/7 Creator Support",
                ],
            },
        )

        plan_enterprise, _ = SubscriptionPlan.objects.get_or_create(
            slug="enterprise",
            defaults={
                "name": "Enterprise",
                "price_monthly": 199.00,
                "max_courses": 100,
                "max_students": 10000,
                "custom_domain_allowed": True,
                "is_popular": False,
                "features": [
                    "Up to 100 Published Courses",
                    "Up to 10,000 Students",
                    "White-Label Custom Domain & SSL",
                    "Multi-Instructor Role Management",
                    "Zero Platform Transaction Fees",
                    "Custom CSS & API Integrations",
                    "Dedicated Account Manager & SLA",
                ],
            },
        )
        self.stdout.write(self.style.SUCCESS("[OK] Seeded 3 Subscription Plans (Starter, Professional, Enterprise)"))

        # 2. Superadmin User
        admin_user, created = User.objects.get_or_create(
            email="admin@platform.com",
            defaults={
                "first_name": "Platform",
                "last_name": "Superadmin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
        self.stdout.write(self.style.SUCCESS("[OK] Created Superadmin: admin@platform.com (password: admin123)"))

        # 3. Instructors & Students
        instructor_1, _ = User.objects.get_or_create(
            email="sarah@alpha.io",
            defaults={"first_name": "Sarah", "last_name": "Connor"},
        )
        instructor_1.set_password("password123")
        instructor_1.save()

        instructor_2, _ = User.objects.get_or_create(
            email="marcus@designmaster.io",
            defaults={"first_name": "Marcus", "last_name": "Vance"},
        )
        instructor_2.set_password("password123")
        instructor_2.save()

        student, _ = User.objects.get_or_create(
            email="alex@student.com",
            defaults={"first_name": "Alex", "last_name": "Rivera"},
        )
        student.set_password("password123")
        student.save()

        # 4. Tenant 1: Alpha Code Academy
        tenant_alpha, _ = Tenant.objects.get_or_create(
            slug="alpha",
            defaults={
                "name": "Alpha Code Academy",
                "owner": instructor_1,
                "custom_domain": "learn.alpha.io",
                "is_active": True,
                "branding": {
                    "primary_color": "#4f46e5",  # Indigo
                    "accent_color": "#06b6d4",   # Cyan
                    "tagline": "Master modern Python, Django, and HTMX full-stack architectures.",
                    "hero_headline": "Level Up Your Engineering with Alpha Code",
                    "hero_subheadline": "Interactive, code-first courses covering modern Python, Django multi-tenancy, and reactive HTMX apps.",
                    "cta_text": "Start Learning Today",
                    "about_heading": "Why Join Alpha Code Academy?",
                    "about_text": "We build real-world software together. No boring slides, just practical architectures that prepare you for principal engineering roles.",
                },
            },
        )
        # Attach Pro Plan Subscription
        TenantSubscription.objects.update_or_create(
            tenant=tenant_alpha,
            defaults={
                "plan": plan_pro,
                "status": TenantSubscription.Status.ACTIVE,
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant_alpha,
            user=instructor_1,
            defaults={"role": TenantMembership.Role.ADMIN},
        )
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant_alpha,
            user=student,
            defaults={"role": TenantMembership.Role.STUDENT},
        )

        with tenant_context(tenant_alpha):
            course_alpha, _ = Course.objects.get_or_create(
                slug="django-htmx-mastery",
                defaults={
                    "title": "Full-Stack Django & HTMX Mastery",
                    "description": "Build reactive single-page feelings with Django, HTMX, and Tailwind CSS without massive JavaScript frameworks.",
                    "instructor": instructor_1,
                    "status": Course.Status.PUBLISHED,
                    "price": 49.00,
                    "is_free": False,
                },
            )
            m1, _ = Module.objects.get_or_create(
                course=course_alpha,
                order=1,
                defaults={"title": "Multi-Tenant Architecture Fundamentals"},
            )
            Lesson.objects.get_or_create(
                module=m1,
                slug="row-level-tenancy",
                defaults={
                    "title": "Implementing Row-Level Isolation in Django",
                    "content_type": Lesson.ContentType.ARTICLE,
                    "duration_minutes": 15,
                    "order": 1,
                    "is_preview": True,
                    "content": "Row-level tenancy with Django managers provides high scalability with minimal overhead.",
                },
            )
            Lesson.objects.get_or_create(
                module=m1,
                slug="htmx-integration",
                defaults={
                    "title": "Dynamic Partial Swaps with HTMX",
                    "content_type": Lesson.ContentType.ARTICLE,
                    "duration_minutes": 20,
                    "order": 2,
                    "content": "Learn how to use hx-post and hx-swap to build instant UI toggles.",
                },
            )
            Enrollment.objects.get_or_create(
                user=student,
                course=course_alpha,
                defaults={"status": Enrollment.Status.ACTIVE},
            )

        # 5. Tenant 2: Design Masterclass
        tenant_beta, _ = Tenant.objects.get_or_create(
            slug="beta",
            defaults={
                "name": "Design Masterclass",
                "owner": instructor_2,
                "custom_domain": "academy.designmaster.io",
                "is_active": True,
                "branding": {
                    "primary_color": "#ec4899",  # Pink
                    "accent_color": "#8b5cf6",   # Purple
                    "tagline": "Craft beautiful, modern design systems with Tailwind CSS and Alpine.js.",
                    "hero_headline": "Modern Product Design for Developers",
                    "hero_subheadline": "Transform plain HTML into breathtaking, polished user interfaces using Tailwind CSS design tokens.",
                    "cta_text": "Enroll In Design Courses",
                    "about_heading": "Design That Converts",
                    "about_text": "Learn visual hierarchy, typography pairings, color theories, and micro-interactions that elevate standard MVPs to world-class apps.",
                },
            },
        )
        # Attach Starter Plan Subscription
        TenantSubscription.objects.update_or_create(
            tenant=tenant_beta,
            defaults={
                "plan": plan_starter,
                "status": TenantSubscription.Status.ACTIVE,
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant_beta,
            user=instructor_2,
            defaults={"role": TenantMembership.Role.ADMIN},
        )

        with tenant_context(tenant_beta):
            course_beta, _ = Course.objects.get_or_create(
                slug="tailwind-design-systems",
                defaults={
                    "title": "Tailwind CSS & Alpine.js Design Systems",
                    "description": "Learn to design production-grade component systems, dynamic themes, and micro-interactions.",
                    "instructor": instructor_2,
                    "status": Course.Status.PUBLISHED,
                    "price": 0.00,
                    "is_free": True,
                },
            )
            m_design, _ = Module.objects.get_or_create(
                course=course_beta,
                order=1,
                defaults={"title": "CSS Variables & Dynamic Theming"},
            )
            Lesson.objects.get_or_create(
                module=m_design,
                slug="dynamic-css-tokens",
                defaults={
                    "title": "Injecting Tenant Branding via Custom CSS Properties",
                    "content_type": Lesson.ContentType.ARTICLE,
                    "duration_minutes": 10,
                    "order": 1,
                    "is_preview": True,
                    "content": "Tailwind can reference CSS custom properties for instant tenant white-labeling.",
                },
            )

        self.stdout.write(self.style.SUCCESS("[OK] Seeded Tenant 1: Alpha Code Academy (Pro Plan - http://alpha.localhost:8001/)"))
        self.stdout.write(self.style.SUCCESS("[OK] Seeded Tenant 2: Design Masterclass (Starter Plan - http://beta.localhost:8001/)"))
        self.stdout.write(self.style.SUCCESS("[OK] Seeded Courses, Modules, Lessons, Subscriptions, and Memberships."))
        self.stdout.write(self.style.SUCCESS("All SaaS subscription and academy data seeded successfully!"))
