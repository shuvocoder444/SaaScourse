from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from core.tenancy.models import TenantAwareModel


class Course(TenantAwareModel):
    """A course offering published within a specific academy tenant."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to="courses/thumbnails/", null=True, blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="instructed_courses",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_course_slug_per_tenant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] {self.title}"

    def get_user_progress(self, user):
        """Calculates completed lesson IDs, count, and overall percentage for a user."""
        total_lessons = Lesson.objects.filter(module__course=self).count()
        if not user or not user.is_authenticated:
            return {
                "completed_ids": set(),
                "total_lessons": total_lessons,
                "completed_count": 0,
                "percent": 0,
            }

        completed_ids = set(
            LessonProgress.objects.filter(
                user=user,
                lesson__module__course=self,
                is_completed=True,
            ).values_list("lesson_id", flat=True)
        )
        completed_count = len(completed_ids)
        percent = int((completed_count / total_lessons * 100)) if total_lessons > 0 else 0

        return {
            "completed_ids": completed_ids,
            "total_lessons": total_lessons,
            "completed_count": completed_count,
            "percent": percent,
        }


class Module(TenantAwareModel):
    """A chapter or section within a Course."""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "order"],
                name="unique_module_order_per_course",
            )
        ]
        ordering = ["order"]

    def clean(self):
        if self.course_id and self.tenant_id and self.tenant_id != self.course.tenant_id:
            raise ValidationError("Cross-tenant violation: Module tenant must match Course tenant.")

    def __str__(self):
        return f"{self.course.title} - Module: {self.title}"


class Lesson(TenantAwareModel):
    """An individual instructional unit (video, article, quiz) inside a Module."""

    class ContentType(models.TextChoices):
        VIDEO = "VIDEO", "Video Lesson"
        ARTICLE = "ARTICLE", "Text / Markdown Article"
        QUIZ = "QUIZ", "Interactive Quiz"

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.VIDEO,
    )
    video_url = models.URLField(blank=True, help_text="Direct or embedded video URL.")
    content = models.TextField(blank=True, help_text="Reading material in Markdown or HTML.")
    duration_minutes = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(
        default=False,
        help_text="Allows public preview before enrollment.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["module", "slug"],
                name="unique_lesson_slug_per_module",
            ),
            models.UniqueConstraint(
                fields=["module", "order"],
                name="unique_lesson_order_per_module",
            ),
        ]
        ordering = ["order"]

    def clean(self):
        if self.module_id and self.tenant_id and self.tenant_id != self.module.tenant_id:
            raise ValidationError("Cross-tenant violation: Lesson tenant must match Module tenant.")

    def __str__(self):
        return f"{self.module.title} - Lesson: {self.title}"

    def get_next_lesson(self):
        """Finds the next lesson in the current module or the first lesson in the subsequent module."""
        next_in_module = (
            Lesson.objects.filter(module=self.module, order__gt=self.order)
            .order_by("order")
            .first()
        )
        if next_in_module:
            return next_in_module

        # Subsequent module in the same course
        next_module = (
            Module.objects.filter(course=self.module.course, order__gt=self.module.order)
            .order_by("order")
            .first()
        )
        if next_module:
            return next_module.lessons.order_by("order").first()

        return None

    def get_previous_lesson(self):
        """Finds the previous lesson in the current module or the last lesson in the preceding module."""
        prev_in_module = (
            Lesson.objects.filter(module=self.module, order__lt=self.order)
            .order_by("-order")
            .first()
        )
        if prev_in_module:
            return prev_in_module

        prev_module = (
            Module.objects.filter(course=self.module.course, order__lt=self.module.order)
            .order_by("-order")
            .first()
        )
        if prev_module:
            return prev_module.lessons.order_by("-order").first()

        return None


class Enrollment(TenantAwareModel):
    """Student registration status for a course."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user", "course"],
                name="unique_user_course_enrollment",
            )
        ]
        ordering = ["-enrolled_at"]

    def clean(self):
        if self.course_id and self.tenant_id and self.tenant_id != self.course.tenant_id:
            raise ValidationError("Cross-tenant violation: Enrollment tenant must match Course tenant.")

    def __str__(self):
        return f"{self.user.email} -> {self.course.title} ({self.status})"


class LessonProgress(TenantAwareModel):
    """Tracks a student's completion and access state for each lesson."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="user_progress",
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user", "lesson"],
                name="unique_user_lesson_progress",
            )
        ]

    def clean(self):
        if self.lesson_id and self.tenant_id and self.tenant_id != self.lesson.tenant_id:
            raise ValidationError("Cross-tenant violation: Progress tenant must match Lesson tenant.")

    def __str__(self):
        state = "Completed" if self.is_completed else "In Progress"
        return f"{self.user.email} -> {self.lesson.title}: {state}"
