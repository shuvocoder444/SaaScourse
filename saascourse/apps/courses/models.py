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


class Book(TenantAwareModel):
    """Published Books and Publications for an academy tenant."""

    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=255)
    author = models.CharField(max_length=255, blank=True, default="একাডেমি ফ্যাকাল্টি")
    cover_image = models.ImageField(upload_to="books/covers/", null=True, blank=True)
    cover_url = models.URLField(blank=True, default="")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    discount_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True, default="২০২৬ সংস্করণ")
    pages = models.PositiveIntegerField(default=0)
    in_stock = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    preview_pdf_url = models.URLField(blank=True, default="")
    buy_url = models.CharField(max_length=500, blank=True, default="")
    is_featured = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_book_slug_per_tenant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Book: {self.title}"

    @property
    def get_cover_url(self):
        if self.cover_image:
            return self.cover_image.url
        return self.cover_url or ""


class FreeResource(TenantAwareModel):
    """Downloadable Free Resources: PDFs, Model Tests, Suggestions, Lecture Sheets."""

    class ResourceType(models.TextChoices):
        PDF_NOTE = "PDF_NOTE", "PDF নোট ও শিট"
        MODEL_TEST = "MODEL_TEST", "মডেল টেস্ট ও প্রশ্নব্যাংক"
        LECTURE_SHEET = "LECTURE_SHEET", "লেকচার শিট"
        SUGGESTION = "SUGGESTION", "পরীক্ষার সাজেশন"
        VIDEO_GUIDE = "VIDEO_GUIDE", "ভিডিও গাইড"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    resource_type = models.CharField(
        max_length=50,
        choices=ResourceType.choices,
        default=ResourceType.PDF_NOTE,
    )
    category = models.CharField(max_length=100, default="এইচএসসি ও ভর্তি", help_text="e.g. HSC, DU, Medical, BUET")
    file = models.FileField(upload_to="resources/files/", null=True, blank=True)
    file_url = models.URLField(blank=True, default="", help_text="External Google Drive / Dropbox link")
    video_url = models.URLField(blank=True, default="")
    description = models.TextField(blank=True)
    download_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_resource_slug_per_tenant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Resource: {self.title}"

    @property
    def get_download_link(self):
        if self.file:
            return self.file.url
        return self.file_url or "#"


class BlogPost(TenantAwareModel):
    """Academic and Admission Articles/Blogs for an academy tenant."""

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    author_name = models.CharField(max_length=150, default="একাডেমি টিম")
    category = models.CharField(max_length=100, default="ভর্তি পরামর্শ", help_text="e.g. প্রস্তুতি কৌশল, নোটিশ, টিপস")
    cover_image = models.ImageField(upload_to="blog/covers/", null=True, blank=True)
    cover_url = models.URLField(blank=True, default="")
    excerpt = models.TextField(blank=True, help_text="Short teaser summary")
    content = models.TextField(blank=True, help_text="Full post content (Markdown or HTML)")
    views_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_blog_slug_per_tenant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Blog: {self.title}"

    @property
    def get_cover_url(self):
        if self.cover_image:
            return self.cover_image.url
        return self.cover_url or ""


class GalleryImage(TenantAwareModel):
    """Community photo moments & success stories gallery for landing page."""

    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="gallery/", null=True, blank=True)
    image_url = models.URLField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Gallery: {self.title or self.id}"

    @property
    def get_image_url(self):
        if self.image:
            return self.image.url
        return self.image_url or ""


# =====================================================================
# STUDENT DASHBOARD MODULES
# =====================================================================

class FeedPost(TenantAwareModel):
    """Community news feed & student blog posts for an academy."""

    class Category(models.TextChoices):
        STUDY_TIPS = "tips", "💡 স্টাডি টিপস ও ট্রিকস"
        QUESTION = "question", "❓ প্রশ্ন ও সমাধান"
        MOTIVATION = "motivation", "🔥 মোটিভেশন ও অভিজ্ঞতা"
        GENERAL = "general", "📢 সাধারণ আলোচনা"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feed_posts",
    )
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.GENERAL,
    )
    image = models.ImageField(upload_to="feed/images/", null=True, blank=True)
    image_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Post by {self.author.get_full_name() or self.author.email}: {self.content[:30]}"

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()


class FeedLike(TenantAwareModel):
    """Like / React on a feed post."""

    post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "post", "user"],
                name="unique_feed_post_like_per_user",
            )
        ]


class FeedComment(TenantAwareModel):
    """Comments on a student feed post."""

    post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ClassRoutine(TenantAwareModel):
    """Class timetable and live class schedule for students."""

    class DayOfWeek(models.TextChoices):
        SATURDAY = "sat", "শনিবার (Saturday)"
        SUNDAY = "sun", "রবিবার (Sunday)"
        MONDAY = "mon", "সোমবার (Monday)"
        TUESDAY = "tue", "মঙ্গলবার (Tuesday)"
        WEDNESDAY = "wed", "বুধবার (Wednesday)"
        THURSDAY = "thu", "বৃহস্পতিবার (Thursday)"
        FRIDAY = "fri", "শুক্রবার (Friday)"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="routines")
    day = models.CharField(max_length=20, choices=DayOfWeek.choices, default=DayOfWeek.SATURDAY)
    start_time = models.CharField(max_length=50, help_text="e.g. 08:00 PM")
    end_time = models.CharField(max_length=50, blank=True, help_text="e.g. 09:30 PM")
    subject = models.CharField(max_length=200, help_text="e.g. উচ্চতর গণিত - ক্যালকুলাস")
    mentor_name = models.CharField(max_length=150, default="অভিজ্ঞ মেন্টর")
    live_url = models.URLField(blank=True, default="", help_text="Zoom / Google Meet / YouTube Live link")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "start_time"]

    def __str__(self):
        return f"[{self.tenant.slug}] {self.get_day_display()} - {self.subject} ({self.start_time})"


class StudentResult(TenantAwareModel):
    """Academic and test results published for a student."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="academic_results",
    )
    exam_title = models.CharField(max_length=255, help_text="e.g. DU ICU উইকলি মডেল টেস্ট ০১")
    course_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=150, default="পূর্ণাঙ্গ পরীক্ষা")
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    obtained_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    grade = models.CharField(max_length=20, default="A+")
    merit_position = models.PositiveIntegerField(null=True, blank=True)
    total_participants = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, default="দারুণ প্রস্তুতি! নিয়মিত রিভিশন চালিয়ে যান।")
    published_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-published_date", "-id"]

    def __str__(self):
        return f"{self.student.email} - {self.exam_title} ({self.obtained_marks}/{self.total_marks})"

    @property
    def percentage(self):
        if self.total_marks and self.total_marks > 0:
            return int((self.obtained_marks / self.total_marks) * 100)
        return 0


class SupportThread(TenantAwareModel):
    """Direct support / chat conversation between a student and academy staff."""

    class Status(models.TextChoices):
        OPEN = "open", "সক্রিয় / Open"
        IN_PROGRESS = "in_progress", "পর্যালোচনা চলছে / In Progress"
        RESOLVED = "resolved", "সমাধান হয়েছে / Resolved"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_threads",
    )
    subject = models.CharField(max_length=255, help_text="বিষয় বা সমস্যার বিবরণ")
    category = models.CharField(max_length=100, default="কোর্স ও ক্লাস সংক্রান্ত")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Support: {self.subject} ({self.student.email})"


class SupportChatMessage(TenantAwareModel):
    """An individual text message in a support thread."""

    thread = models.ForeignKey(SupportThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_staff_reply = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message by {self.sender.email}: {self.message[:30]}"


class StudentInvoice(TenantAwareModel):
    """Official payment invoices and billing receipts."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    invoice_no = models.CharField(max_length=50, unique=True)
    item_title = models.CharField(max_length=255, help_text="Course or Book purchase name")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="bKash Online Gateway")
    transaction_id = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=30, default="PAID")
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Invoice {self.invoice_no}: ৳{self.amount}"


class BookOrder(TenantAwareModel):
    """Storefront book orders placed by a student."""

    class Status(models.TextChoices):
        PENDING = "pending", "অপেক্ষমান (Pending)"
        PROCESSING = "processing", "প্যাকিং চলছে (Processing)"
        SHIPPED = "shipped", "কুরিয়ারে পাঠানো হয়েছে (Shipped)"
        DELIVERED = "delivered", "ডেলিভারি সম্পন্ন (Delivered)"
        CANCELLED = "cancelled", "বাতিল (Cancelled)"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_orders",
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="orders")
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=8, decimal_places=2)
    shipping_address = models.TextField()
    phone_number = models.CharField(max_length=50)
    courier_name = models.CharField(max_length=100, default="Steadfast Courier / Sundarban")
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PROCESSING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id}: {self.book.title} -> {self.student.email} ({self.status})"


class StudentClub(TenantAwareModel):
    """Subject and interest-based student study clubs."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, default="বিশ্ববিদ্যালয় ভর্তি")
    icon = models.CharField(max_length=20, default="🏛️")
    cover_image_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_club_slug_per_tenant",
            )
        ]
        ordering = ["title"]

    def __str__(self):
        return f"[{self.tenant.slug}] Club: {self.title}"

    @property
    def members_count(self):
        return self.memberships.count()

    @property
    def posts_count(self):
        return self.posts.count()


class ClubMembership(TenantAwareModel):
    """Student membership in a study club."""

    club = models.ForeignKey(StudentClub, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="club_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "club", "user"],
                name="unique_club_membership_per_user",
            )
        ]


class ClubPost(TenantAwareModel):
    """Post created inside a student club group."""

    club = models.ForeignKey(StudentClub, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.club.title} - Post by {self.author.email}"

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()


class ClubLike(TenantAwareModel):
    """Like on a club post."""

    post = models.ForeignKey(ClubPost, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "post", "user"],
                name="unique_club_post_like_per_user",
            )
        ]


class ClubComment(TenantAwareModel):
    """Comment on a club post."""

    post = models.ForeignKey(ClubPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


# =====================================================================
# ONLINE MCQ EXAM ENGINE MODELS
# =====================================================================

class Exam(TenantAwareModel):
    """Online MCQ Exam / Quiz created by an Academy Instructor."""

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exams",
        help_text="ঐচ্ছিক: কোনো নির্দিষ্ট কোর্সের সাথে যুক্ত করতে পারেন",
    )
    title = models.CharField(max_length=255, help_text="পরীক্ষার শিরোনাম (যেমন: ভেক্টর সাপ্তাহিক মডেল টেস্ট)")
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True, help_text="পরীক্ষার সিলেবাস ও নির্দেশিকা")
    duration_minutes = models.PositiveIntegerField(default=30, help_text="পরীক্ষার সময়কাল (মিনিটে)")
    pass_mark = models.DecimalField(max_digits=5, decimal_places=2, default=40.00, help_text="পাস মার্ক বা পার্সেন্টেজ")
    negative_mark_per_question = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.25, help_text="প্রতি ভুল উত্তরের জন্য কাটা নম্বর (যেমন: 0.25)"
    )
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="unique_exam_slug_per_tenant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.tenant.slug}] Exam: {self.title} ({self.duration_minutes}m)"

    @property
    def questions_count(self):
        return self.questions.count()

    @property
    def calculated_total_marks(self):
        total = self.questions.aggregate(total=models.Sum("marks"))["total"]
        return total or self.total_marks


class ExamQuestion(TenantAwareModel):
    """An individual MCQ question belonging to an Exam."""

    class CorrectOption(models.TextChoices):
        A = "A", "অপশন ক (A)"
        B = "B", "অপশন খ (B)"
        C = "C", "অপশন গ (C)"
        D = "D", "অপশন ঘ (D)"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField(help_text="প্রশ্নটি লিখুন (ম্যাথ ফর্মুলা বা টেক্সট)")
    image_url = models.URLField(blank=True, default="", help_text="ঐচ্ছিক: কোনো চিত্র বা ডায়াগ্রামের লিংক")
    option_a = models.CharField(max_length=500, help_text="অপশন ক")
    option_b = models.CharField(max_length=500, help_text="অপশন খ")
    option_c = models.CharField(max_length=500, help_text="অপশন গ")
    option_d = models.CharField(max_length=500, help_text="অপশন ঘ")
    correct_option = models.CharField(max_length=2, choices=CorrectOption.choices, default=CorrectOption.A)
    explanation = models.TextField(blank=True, help_text="সঠিক উত্তরের ব্যাখ্যা ও সমাধান কৌশল")
    marks = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.exam.title} - Q{self.order}: {self.question_text[:30]}"


class ExamAttempt(TenantAwareModel):
    """Student's exam submission, score calculation and answer record."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_attempts",
    )
    score = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    is_passed = models.BooleanField(default=False)
    answers_json = models.JSONField(default=dict, help_text="Keyed by question_id: selected_option")
    time_taken_seconds = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student.email} -> {self.exam.title}: Score {self.score}/{self.total_marks}"

    @property
    def percentage(self):
        if self.total_marks and self.total_marks > 0:
            return round((float(self.score) / float(self.total_marks)) * 100, 1)
        return 0.0



