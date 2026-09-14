from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription
from apps.users.models import TenantMembership
from apps.courses.models import Course, Module, Lesson, Enrollment, LessonProgress
from core.tenancy.context import tenant_context

User = get_user_model()


class RoleBasedDashboardsAndAuthTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Subscription Plans
        self.plan_pro = SubscriptionPlan.objects.create(
            name="Professional",
            slug="pro",
            price_monthly=79.00,
            max_courses=25,
            custom_domain_allowed=True,
        )

        # 1. SuperAdmin
        self.superadmin = User.objects.create_superuser(
            email="admin@platform.com",
            password="admin123",
            first_name="Platform",
            last_name="Superadmin",
        )

        # 2. Academy Creator / Instructor
        self.creator = User.objects.create_user(
            email="sarah@alpha.io",
            password="password123",
            first_name="Sarah",
            last_name="Connor",
        )

        # 3. Student
        self.student = User.objects.create_user(
            email="alex@student.com",
            password="password123",
            first_name="Alex",
            last_name="Rivera",
        )

        # Tenant: Alpha Academy
        self.tenant = Tenant.objects.create(
            name="Alpha Code Academy",
            slug="alpha",
            owner=self.creator,
            is_active=True,
            branding={"primary_color": "#4f46e5", "hero_headline": "Learn Alpha"},
        )
        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan_pro,
            status=TenantSubscription.Status.ACTIVE,
        )
        TenantMembership.objects.unscoped().create(
            tenant=self.tenant,
            user=self.creator,
            role=TenantMembership.Role.ADMIN,
        )
        TenantMembership.objects.unscoped().create(
            tenant=self.tenant,
            user=self.student,
            role=TenantMembership.Role.STUDENT,
        )

        # Courses & Curriculum
        with tenant_context(self.tenant):
            self.course = Course.objects.create(
                title="Full-Stack Django & HTMX",
                slug="django-htmx",
                instructor=self.creator,
                status=Course.Status.PUBLISHED,
                price=49.00,
            )
            self.module = Module.objects.create(
                course=self.course,
                title="Architecture",
                order=1,
            )
            self.lesson1 = Lesson.objects.create(
                module=self.module,
                title="Lesson 1: Multi-Tenancy",
                slug="lesson-1",
                order=1,
            )
            self.lesson2 = Lesson.objects.create(
                module=self.module,
                title="Lesson 2: HTMX Swaps",
                slug="lesson-2",
                order=2,
            )
            Enrollment.objects.create(
                user=self.student,
                course=self.course,
                status=Enrollment.Status.ACTIVE,
            )

    def test_login_page_renders_with_demo_roles(self):
        """Login page displays 1-Click quick login buttons for all roles."""
        response = self.client.get("/login/", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("1-Click Demo Login", content)
        self.assertIn("Platform SuperAdmin", content)
        self.assertIn("Academy Creator", content)
        self.assertIn("Student / Learner", content)

    def test_demo_login_instant_authentication(self):
        """1-Click demo login authenticates the user immediately."""
        response = self.client.post(
            "/login/",
            data={"demo_role": "student"},
            HTTP_HOST="localhost:8001",
        )
        self.assertEqual(response.status_code, 302)
        # Verify authenticated user
        user = User.objects.get(email="alex@student.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_unauthenticated_dashboard_redirects_to_login(self):
        """Visiting /dashboard/ anonymously redirects to /login/?next=/dashboard/."""
        response = self.client.get("/dashboard/", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/?next=/dashboard/", response.url)

    def test_superadmin_dashboard_on_platform_domain(self):
        """SuperAdmin visiting /dashboard/ on platform root sees SaaS Executive Dashboard."""
        self.client.force_login(self.superadmin)
        response = self.client.get("/dashboard/", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("SaaS Executive Dashboard", content)
        self.assertIn("Monthly Recurring Revenue", content)
        self.assertIn("Multi-Tenant Academies Directory", content)
        self.assertIn("Alpha Code Academy", content)

    def test_instructor_dashboard_on_tenant_subdomain(self):
        """Academy creator visiting /dashboard/ on academy subdomain sees Instructor Studio."""
        self.client.force_login(self.creator)
        response = self.client.get("/dashboard/", HTTP_HOST="alpha.localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Course Management Studio", content)
        self.assertIn("Course Plan Limit", content)
        self.assertIn("Full-Stack Django &amp; HTMX", content)

    def test_student_dashboard_on_tenant_subdomain(self):
        """Student visiting /dashboard/ on academy subdomain sees Student Learning Dashboard."""
        self.client.force_login(self.student)
        response = self.client.get("/dashboard/", HTTP_HOST="alpha.localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Student Learning Dashboard", content)
        self.assertIn("Your Learning Journey", content)
        self.assertIn("Full-Stack Django &amp; HTMX", content)
        self.assertIn("Resume Learning", content)
        # Direct link to player for lesson 1 (the unfinished lesson)
        self.assertIn("/courses/django-htmx/player/lesson-1/", content)
