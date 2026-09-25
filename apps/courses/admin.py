from django.contrib import admin
from apps.courses.models import (
    Course, Module, Lesson, Enrollment, LessonProgress,
    Book, FreeResource, BlogPost, GalleryImage,
    FeedPost, FeedComment, FeedLike,
    ClassRoutine, StudentResult,
    SupportThread, SupportChatMessage,
    StudentInvoice, BookOrder,
    StudentClub, ClubMembership, ClubPost, ClubComment, ClubLike,
    Exam, ExamQuestion, ExamAttempt
)



class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "instructor", "status", "price", "is_free", "created_at")
    list_filter = ("status", "is_free", "tenant")
    search_fields = ("title", "slug", "tenant__name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ModuleInline]

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "tenant")
    list_filter = ("course__tenant",)
    search_fields = ("title", "course__title")
    inlines = [LessonInline]

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "content_type", "order", "is_preview", "tenant")
    list_filter = ("content_type", "is_preview", "module__course__tenant")
    search_fields = ("title", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "status", "tenant", "enrolled_at")
    list_filter = ("status", "tenant")
    search_fields = ("user__email", "course__title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "completed_at", "tenant")
    list_filter = ("is_completed", "tenant")
    search_fields = ("user__email", "lesson__title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "author", "price", "discount_price", "in_stock", "is_featured", "created_at")
    list_filter = ("in_stock", "is_featured", "tenant")
    search_fields = ("title", "author", "tenant__name")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(FreeResource)
class FreeResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "resource_type", "category", "download_count", "is_published", "created_at")
    list_filter = ("resource_type", "category", "is_published", "tenant")
    search_fields = ("title", "category", "tenant__name")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "author_name", "category", "views_count", "is_published", "created_at")
    list_filter = ("category", "is_published", "tenant")
    search_fields = ("title", "author_name", "category", "tenant__name")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "order", "created_at")
    list_filter = ("tenant",)
    search_fields = ("title", "tenant__name")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(FeedPost)
class FeedPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "tenant", "created_at")
    list_filter = ("category", "tenant")
    search_fields = ("title", "content", "author__email")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(FeedComment)
class FeedCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "tenant", "created_at")
    list_filter = ("tenant",)

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(ClassRoutine)
class ClassRoutineAdmin(admin.ModelAdmin):
    list_display = ("course", "day", "start_time", "subject", "mentor_name", "tenant", "is_active")
    list_filter = ("day", "is_active", "tenant")
    search_fields = ("subject", "mentor_name", "course__title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ("student", "exam_title", "obtained_marks", "total_marks", "grade", "tenant", "published_date")
    list_filter = ("grade", "tenant")
    search_fields = ("student__email", "exam_title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = ("subject", "student", "category", "status", "tenant", "created_at")
    list_filter = ("status", "category", "tenant")
    search_fields = ("subject", "student__email")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(SupportChatMessage)
class SupportChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "is_staff_reply", "tenant", "created_at")
    list_filter = ("is_staff_reply", "tenant")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "student", "item_title", "amount", "payment_method", "status", "tenant", "paid_at")
    list_filter = ("status", "tenant")
    search_fields = ("invoice_no", "student__email", "item_title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(BookOrder)
class BookOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "book", "quantity", "total_amount", "status", "tenant", "created_at")
    list_filter = ("status", "tenant")
    search_fields = ("student__email", "book__title", "phone_number")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(StudentClub)
class StudentClubAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "icon", "is_active", "tenant", "created_at")
    list_filter = ("is_active", "category", "tenant")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(ClubPost)
class ClubPostAdmin(admin.ModelAdmin):
    list_display = ("club", "author", "title", "tenant", "created_at")
    list_filter = ("club", "tenant")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


class ExamQuestionInline(admin.StackedInline):
    model = ExamQuestion
    extra = 1


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "duration_minutes", "pass_mark", "is_published", "tenant", "created_at")
    list_filter = ("is_published", "tenant")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ExamQuestionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ("exam", "order", "question_text", "correct_option", "marks", "tenant")
    list_filter = ("exam__tenant", "correct_option")
    search_fields = ("question_text", "exam__title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "exam", "score", "total_marks", "is_passed", "tenant", "submitted_at")
    list_filter = ("is_passed", "tenant")
    search_fields = ("student__email", "exam__title")

    def get_queryset(self, request):
        return super().get_queryset(request).model.all_objects.all()

