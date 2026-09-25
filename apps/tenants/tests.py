from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription
from apps.users.models import TenantMembership

User = get_user_model()


class SaaSPlatformAndSubscriptionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.plan_starter = SubscriptionPlan.objects.create(
            name="Starter",
            slug="starter",
            price_monthly=29.00,
            max_courses=5,
            features=["Up to 5 Courses"],
        )
        self.plan_pro = SubscriptionPlan.objects.create(
            name="Professional",
            slug="pro",
            price_monthly=79.00,
            max_courses=25,
            custom_domain_allowed=True,
            features=["Up to 25 Courses", "Custom Domain"],
        )

    def test_platform_landing_renders_pricing(self):
        """Platform root domain (localhost:8001) renders subscription pricing tiers."""
        response = self.client.get("/", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Starter", content)
        self.assertIn("Professional", content)
        self.assertIn("৳79", content)

    def test_tenant_self_service_registration(self):
        """A new creator can sign up, creating User, Tenant, Subscription, and Membership."""
        response = self.client.post(
            "/signup/",
            data={
                "full_name": "David Miller",
                "email": "david@bootcamp.io",
                "password": "strongpassword123",
                "academy_name": "Dev Bootcamp",
                "subdomain": "devbootcamp",
                "plan_slug": "pro",
            },
            HTTP_HOST="localhost:8001",
        )
        # Should redirect to the new academy dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn("devbootcamp", response.url)

        # Verify DB records
        user = User.objects.filter(email="david@bootcamp.io").first()
        self.assertIsNotNone(user)

        tenant = Tenant.objects.filter(slug="devbootcamp").first()
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.name, "Dev Bootcamp")
        self.assertEqual(tenant.owner, user)

        # Verify 14-day trial subscription
        subscription = TenantSubscription.objects.filter(tenant=tenant).first()
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.plan, self.plan_pro)
        self.assertEqual(subscription.status, TenantSubscription.Status.TRIALING)
        self.assertTrue(tenant.has_active_subscription)

        # Verify Admin Membership
        membership = TenantMembership.objects.unscoped().filter(tenant=tenant, user=user).first()
        self.assertIsNotNone(membership)
        self.assertTrue(membership.is_admin)

    def test_tenant_storefront_landing(self):
        """Visiting an academy subdomain renders its own custom storefront, not the SaaS page."""
        owner = User.objects.create_user(email="creator@test.com", password="password123")
        tenant = Tenant.objects.create(
            name="Cloud Academy",
            slug="cloud",
            owner=owner,
            is_active=True,
            branding={
                "hero_headline": "Master AWS & GCP Cloud Architecture",
                "cta_text": "Join Cloud Track",
            },
        )
        TenantSubscription.objects.create(
            tenant=tenant,
            plan=self.plan_starter,
            status=TenantSubscription.Status.ACTIVE,
        )

        response = self.client.get("/", HTTP_HOST="cloud.localhost:8001")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Cloud Academy", content)
        self.assertIn("Master AWS &amp; GCP Cloud Architecture", content)
        self.assertIn("Join Cloud Track", content)


class CustomDomainAndCaddySecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(email="owner@academy.com", password="password123")
        self.tenant = Tenant.objects.create(
            name="Pro Academy",
            slug="proacademy",
            owner=self.owner,
            is_active=True,
            custom_domain="learn.proacademy.com",
            custom_domain_verified=False,
        )

    def test_caddy_ask_domain_missing_param(self):
        """Caddy ask request without domain query param returns 400 Bad Request."""
        response = self.client.get("/tenants/api/caddy-check/", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 400)

    def test_caddy_ask_domain_unverified(self):
        """Caddy ask request for an unverified custom domain returns 400 to block TLS cert issuance."""
        response = self.client.get("/tenants/api/caddy-check/?domain=learn.proacademy.com", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 400)

    def test_caddy_ask_domain_verified_success(self):
        """Caddy ask request for an active and verified custom domain returns 200 OK."""
        self.tenant.custom_domain_verified = True
        self.tenant.save()

        response = self.client.get("/tenants/api/caddy-check/?domain=learn.proacademy.com", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 200)
        self.assertIn("authorized", response.content.decode().lower())

    def test_caddy_ask_domain_unknown_attacker_domain(self):
        """Caddy ask request for an unknown domain returns 400, preventing TLS exhaustion DoS."""
        response = self.client.get("/tenants/api/caddy-check/?domain=attacker-domain.org", HTTP_HOST="localhost:8001")
        self.assertEqual(response.status_code, 400)


class DomainManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.plan = SubscriptionPlan.objects.create(
            name="Pro",
            slug="pro",
            price_monthly=79.00,
            max_courses=25,
            custom_domain_allowed=True,
        )
        self.owner = User.objects.create_user(email="sarah@alpha.io", password="password123")
        self.tenant = Tenant.objects.create(
            name="Alpha Academy",
            slug="alpha",
            owner=self.owner,
            is_active=True,
        )
        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.Status.ACTIVE,
        )
        TenantMembership.objects.unscoped().create(
            tenant=self.tenant,
            user=self.owner,
            role=TenantMembership.Role.ADMIN,
        )

    def test_change_subdomain_success(self):
        """Owner can change the academy subdomain, updating slug and redirecting."""
        self.client.force_login(self.owner)
        response = self.client.post(
            "/tenants/settings/",
            data={
                "subdomain": "alphanew",
                "active_tab": "domain",
            },
            HTTP_HOST="alpha.localhost:8001",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("alphanew.localhost", response.url)

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.slug, "alphanew")

    def test_change_subdomain_duplicate_fails(self):
        """Cannot take a subdomain that belongs to another tenant."""
        other_owner = User.objects.create_user(email="other@test.com", password="password123")
        Tenant.objects.create(name="Beta", slug="beta", owner=other_owner)

        self.client.force_login(self.owner)
        response = self.client.post(
            "/tenants/settings/",
            data={
                "subdomain": "beta",
                "active_tab": "domain",
            },
            HTTP_HOST="alpha.localhost:8001",
        )
        self.assertEqual(response.status_code, 302)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.slug, "alpha")

    def test_change_custom_domain_success(self):
        """Owner can set and update custom CNAME domain."""
        self.client.force_login(self.owner)
        response = self.client.post(
            "/tenants/settings/",
            data={
                "custom_domain": "learn.mybrand.com",
                "active_tab": "domain",
            },
            HTTP_HOST="alpha.localhost:8001",
        )
        self.assertEqual(response.status_code, 302)

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.custom_domain, "learn.mybrand.com")
        self.assertFalse(self.tenant.custom_domain_verified)
        self.assertTrue(self.tenant.custom_domain_token.startswith("saascourse-verify-"))

    def test_tenant_branding_visual_assets(self):
        """Tenant properties get_logo_url, get_banner_url, get_favicon_url resolve correctly."""
        self.tenant.branding = {
            "logo_url": "https://example.com/logo.png",
            "banner_url": "https://example.com/cover.jpg",
            "favicon_url": "https://example.com/icon.ico",
        }
        self.tenant.save()
        self.assertEqual(self.tenant.get_logo_url, "https://example.com/logo.png")
        self.assertEqual(self.tenant.get_banner_url, "https://example.com/cover.jpg")
        self.assertEqual(self.tenant.get_favicon_url, "https://example.com/icon.ico")

    def test_tenant_sms_setting_save_and_test_dispatch(self):
        """Owner can save SMS settings and trigger a test SMS dispatch."""
        self.client.force_login(self.owner)
        response = self.client.post(
            "/tenants/settings/",
            data={
                "active_tab": "sms",
                "sms_provider": "SSL_WIRELESS",
                "sms_is_enabled": "on",
                "sms_sender_id": "ALPHASMS",
                "sms_api_key": "test_api_token_12345",
                "sms_template_enrollment": "Hello {student_name}, welcome!",
            },
            HTTP_HOST="alpha.localhost:8001",
        )
        self.assertEqual(response.status_code, 302)

        from apps.tenants.models import TenantSMSSetting
        sms_setting = TenantSMSSetting.objects.get(tenant=self.tenant)
        self.assertTrue(sms_setting.is_enabled)
        self.assertEqual(sms_setting.provider, TenantSMSSetting.Provider.SSL_WIRELESS)
        self.assertEqual(sms_setting.sender_id, "ALPHASMS")

        # Test live dispatch endpoint
        test_response = self.client.post(
            "/tenants/send-test-sms/",
            data={"test_phone": "01711223344"},
            HTTP_HOST="alpha.localhost:8001",
        )
        self.assertEqual(test_response.status_code, 200)
        self.assertIn("SMS Sent Successfully", test_response.content.decode())


