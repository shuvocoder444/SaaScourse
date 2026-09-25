from django.test import TestCase, RequestFactory
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.http import Http404

from apps.tenants.models import Tenant
from apps.courses.models import Course
from core.tenancy.context import tenant_context, set_current_tenant, reset_current_tenant
from core.tenancy.middleware import TenantResolutionMiddleware

User = get_user_model()


class TenancyIsolationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@platform.com", password="password123"
        )
        self.tenant_a = Tenant.objects.create(
            name="Alpha Academy",
            slug="alpha",
            owner=self.owner,
            is_active=True,
        )
        self.tenant_b = Tenant.objects.create(
            name="Beta Academy",
            slug="beta",
            owner=self.owner,
            is_active=True,
        )

    def test_tenant_context_scoping(self):
        """Test that TenantManager automatically filters queries to the active tenant."""
        with tenant_context(self.tenant_a):
            Course.objects.create(
                title="Django for Alpha",
                slug="django-alpha",
                instructor=self.owner,
                status=Course.Status.PUBLISHED,
            )

        with tenant_context(self.tenant_b):
            Course.objects.create(
                title="Next.js for Beta",
                slug="nextjs-beta",
                instructor=self.owner,
                status=Course.Status.PUBLISHED,
            )

        # In Tenant A context: should ONLY see Alpha's course
        with tenant_context(self.tenant_a):
            courses_a = Course.objects.all()
            self.assertEqual(courses_a.count(), 1)
            self.assertEqual(courses_a.first().title, "Django for Alpha")

        # In Tenant B context: should ONLY see Beta's course
        with tenant_context(self.tenant_b):
            courses_b = Course.objects.all()
            self.assertEqual(courses_b.count(), 1)
            self.assertEqual(courses_b.first().title, "Next.js for Beta")

        # Unscoped query: should see both courses across tenants
        total_courses = Course.objects.unscoped().count()
        self.assertEqual(total_courses, 2)

    def test_cross_tenant_integrity_guard(self):
        """Test that saving a model assigned to Tenant B while in Tenant A context raises ValidationError."""
        course = Course(
            title="Sneaky Course",
            slug="sneaky",
            instructor=self.owner,
            tenant=self.tenant_b,
        )
        with tenant_context(self.tenant_a):
            with self.assertRaises(ValidationError):
                course.save()


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = User.objects.create_user(
            email="admin@test.com", password="password123"
        )
        self.tenant = Tenant.objects.create(
            name="Alpha Tech",
            slug="alpha",
            custom_domain="courses.alphatech.com",
            owner=self.owner,
            is_active=True,
        )
        self.inactive_tenant = Tenant.objects.create(
            name="Suspended Academy",
            slug="suspended",
            owner=self.owner,
            is_active=False,
        )

    def test_root_domain_resolution(self):
        """Visiting localhost or platform.com sets request.tenant to None."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "localhost:8000"

        middleware = TenantResolutionMiddleware(lambda req: req)
        res = middleware(request)

        self.assertIsNone(res.tenant)

    def test_subdomain_resolution(self):
        """Visiting alpha.localhost:8000 resolves to Alpha Tech tenant."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "alpha.localhost:8000"

        middleware = TenantResolutionMiddleware(lambda req: req)
        res = middleware(request)

        self.assertIsNotNone(res.tenant)
        self.assertEqual(res.tenant.id, self.tenant.id)

    def test_custom_domain_resolution(self):
        """Visiting custom CNAME domain resolves to the correct tenant."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "courses.alphatech.com"

        middleware = TenantResolutionMiddleware(lambda req: req)
        res = middleware(request)

        self.assertIsNotNone(res.tenant)
        self.assertEqual(res.tenant.id, self.tenant.id)

    def test_unknown_subdomain_raises_404(self):
        """Visiting unknown.localhost:8000 raises Http404."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "unknown.localhost:8000"

        middleware = TenantResolutionMiddleware(lambda req: req)
        with self.assertRaises(Http404):
            middleware(request)

    def test_suspended_tenant_returns_403(self):
        """Visiting an inactive tenant returns HTTP 403."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "suspended.localhost:8000"

        middleware = TenantResolutionMiddleware(lambda req: req)
        response = middleware(request)

        self.assertEqual(response.status_code, 403)
