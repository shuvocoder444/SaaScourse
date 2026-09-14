from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from apps.courses.models import Course, Module, Lesson, LessonProgress
from core.tenancy.context import tenant_context

User = get_user_model()


class CoursePlayerAndTrackerTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="student@academy.io", password="password123"
        )
        self.tenant = Tenant.objects.create(
            name="Code Academy",
            slug="code",
            owner=self.user,
            is_active=True,
        )

        with tenant_context(self.tenant):
            self.course = Course.objects.create(
                title="Django Full Stack",
                slug="django-fullstack",
                instructor=self.user,
                status=Course.Status.PUBLISHED,
            )
            self.m1 = Module.objects.create(course=self.course, title="Module 1", order=1)
            self.l1 = Lesson.objects.create(
                module=self.m1,
                title="Lesson 1",
                slug="lesson-1",
                order=1,
            )
            self.l2 = Lesson.objects.create(
                module=self.m1,
                title="Lesson 2",
                slug="lesson-2",
                order=2,
            )
            self.m2 = Module.objects.create(course=self.course, title="Module 2", order=2)
            self.l3 = Lesson.objects.create(
                module=self.m2,
                title="Lesson 3",
                slug="lesson-3",
                order=1,
            )

    def test_lesson_next_and_previous_navigation(self):
        """Test get_next_lesson and get_previous_lesson within module and across modules."""
        # Lesson 1 -> Next is Lesson 2
        self.assertEqual(self.l1.get_next_lesson(), self.l2)
        self.assertIsNone(self.l1.get_previous_lesson())

        # Lesson 2 (end of Module 1) -> Next is Lesson 3 (start of Module 2)
        self.assertEqual(self.l2.get_next_lesson(), self.l3)
        self.assertEqual(self.l2.get_previous_lesson(), self.l1)

        # Lesson 3 (end of Course) -> Next is None
        self.assertIsNone(self.l3.get_next_lesson())
        self.assertEqual(self.l3.get_previous_lesson(), self.l2)

    def test_course_progress_calculation(self):
        """Test calculation of percentage and completed IDs."""
        progress = self.course.get_user_progress(self.user)
        self.assertEqual(progress["percent"], 0)
        self.assertEqual(progress["total_lessons"], 3)

        # Complete Lesson 1 (1 out of 3 = 33%)
        with tenant_context(self.tenant):
            LessonProgress.objects.create(
                user=self.user,
                lesson=self.l1,
                is_completed=True,
            )

        progress = self.course.get_user_progress(self.user)
        self.assertEqual(progress["completed_count"], 1)
        self.assertEqual(progress["percent"], 33)
        self.assertIn(self.l1.id, progress["completed_ids"])

    def test_complete_and_next_htmx_endpoint(self):
        """HTMX POST to complete_and_next marks lesson complete and returns next lesson with OOB swaps."""
        self.client.force_login(self.user)
        response = self.client.post(
            f"/courses/lessons/{self.l1.id}/complete-and-next/",
            HTTP_HOST="code.localhost:8001",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

        # Verify in DB that l1 is completed
        lp = LessonProgress.objects.get(user=self.user, lesson=self.l1)
        self.assertTrue(lp.is_completed)

        content = response.content.decode()
        # Next lesson (Lesson 2) content is present
        self.assertIn("Lesson 2", content)
        # Out-of-band progress bar is present
        self.assertIn('id="course-progress-container" hx-swap-oob="true"', content)
        # Out-of-band completed checkmark for l1 is present
        self.assertIn(f'id="lesson-check-{self.l1.id}"', content)
        self.assertIn('hx-swap-oob="true"', content)
        # HX-Push-Url header pushes new lesson URL
        self.assertIn("HX-Push-Url", response.headers)
