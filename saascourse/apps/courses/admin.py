from django.contrib import admin
from apps.courses.models import Course, Module, Lesson, Enrollment, LessonProgress


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
