from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from apps.courses.models import Course, Lesson, LessonProgress


def course_list(request):
    """
    Frontend catalog of all published courses for the current tenant.
    Query is automatically scoped by TenantManager!
    """
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("instructor")
    return render(
        request,
        "courses/frontend/list.html",
        {
            "courses": courses,
        },
    )


def course_detail(request, slug):
    """Frontend detailed curriculum syllabus for a course."""
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons").select_related("instructor"),
        slug=slug,
    )
    progress_data = course.get_user_progress(request.user)
    first_lesson = Lesson.objects.filter(module__course=course).order_by("module__order", "order").first()

    return render(
        request,
        "courses/frontend/detail.html",
        {
            "course": course,
            "progress_data": progress_data,
            "first_lesson": first_lesson,
        },
    )


def lesson_player_view(request, course_slug, lesson_slug):
    """
    Main Course Player view.
    - If standard HTTP GET -> renders full player shell with responsive collapsible sidebar.
    - If HTMX GET -> renders only player_content.html partial with HX-Push-Url.
    """
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons"),
        slug=course_slug,
    )
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__course"),
        module__course=course,
        slug=lesson_slug,
    )

    progress_data = course.get_user_progress(request.user)
    next_lesson = lesson.get_next_lesson()
    prev_lesson = lesson.get_previous_lesson()

    progress = None
    if request.user.is_authenticated:
        progress, _ = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={"is_completed": False},
        )

    context = {
        "course": course,
        "lesson": lesson,
        "next_lesson": next_lesson,
        "prev_lesson": prev_lesson,
        "progress_data": progress_data,
        "progress": progress,
    }

    if request.headers.get("HX-Request"):
        response = render(request, "courses/frontend/partials/player_content.html", context)
        response["HX-Push-Url"] = reverse(
            "courses:player", kwargs={"course_slug": course.slug, "lesson_slug": lesson.slug}
        )
        return response

    return render(request, "courses/frontend/player.html", context)


def complete_and_next_lesson(request, lesson_id):
    """
    HTMX POST endpoint:
    1. Marks the current lesson as completed.
    2. Retrieves the next lesson in curriculum order.
    3. Returns new player_content.html with out-of-band updates (hx-swap-oob) for:
       - Sidebar progress percentage bar
       - Sidebar completed checkmark icon
    4. Pushes new lesson URL via HX-Push-Url header.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required to save course progress.")

    current_lesson = get_object_or_404(
        Lesson.objects.select_related("module__course"),
        id=lesson_id,
    )
    course = current_lesson.module.course

    # 1. Update progress
    progress, _ = LessonProgress.objects.get_or_create(
        user=request.user,
        lesson=current_lesson,
    )
    progress.is_completed = True
    progress.completed_at = timezone.now()
    progress.save()

    # 2. Get next lesson and updated course completion percentage
    next_lesson = current_lesson.get_next_lesson()
    progress_data = course.get_user_progress(request.user)

    if next_lesson:
        next_progress, _ = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=next_lesson,
            defaults={"is_completed": False},
        )
        context = {
            "course": course,
            "lesson": next_lesson,
            "next_lesson": next_lesson.get_next_lesson(),
            "prev_lesson": next_lesson.get_previous_lesson(),
            "progress_data": progress_data,
            "progress": next_progress,
            "completed_lesson_id": current_lesson.id,
            "just_completed": True,
        }
        response = render(request, "courses/frontend/partials/player_content.html", context)
        response["HX-Push-Url"] = reverse(
            "courses:player", kwargs={"course_slug": course.slug, "lesson_slug": next_lesson.slug}
        )
        return response

    # Course fully finished celebration
    context = {
        "course": course,
        "completed_lesson_id": current_lesson.id,
        "course_completed": True,
        "progress_data": progress_data,
    }
    return render(request, "courses/frontend/partials/player_content.html", context)


def toggle_lesson_progress(request, lesson_id):
    """
    HTMX endpoint to toggle completion status of a lesson without navigating away.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required.")

    lesson = get_object_or_404(Lesson, id=lesson_id)
    progress, _ = LessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson,
    )

    progress.is_completed = not progress.is_completed
    progress.completed_at = timezone.now() if progress.is_completed else None
    progress.save()

    course = lesson.module.course
    progress_data = course.get_user_progress(request.user)

    # Return updated button plus out-of-band updates for sidebar
    button_class = (
        "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-900/40"
        if progress.is_completed
        else "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
    )
    button_text = "✓ Completed" if progress.is_completed else "Mark as Complete"

    html = f"""
    <button
        id="lesson-toggle-btn-{lesson.id}"
        hx-post="/courses/lessons/{lesson.id}/toggle-progress/"
        hx-swap="outerHTML"
        class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-md {button_class}"
    >
        <span>{button_text}</span>
    </button>
    
    <!-- Out-of-band update for sidebar checkmark -->
    <span id="lesson-check-{lesson.id}" hx-swap-oob="true" class="w-5 h-5 flex items-center justify-center rounded-full text-xs {'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' if progress.is_completed else 'bg-slate-800 text-slate-600 border border-slate-700'}">
        {'✓' if progress.is_completed else lesson.order}
    </span>

    <!-- Out-of-band update for progress bar -->
    <div id="course-progress-container" hx-swap-oob="true" class="space-y-1.5">
      <div class="flex items-center justify-between text-xs font-mono">
        <span class="text-slate-400">Curriculum Progress</span>
        <span class="text-emerald-400 font-bold">{progress_data['percent']}%</span>
      </div>
      <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
        <div class="bg-gradient-to-r from-brand-primary to-emerald-400 h-2 rounded-full transition-all duration-500" style="width: {progress_data['percent']}%"></div>
      </div>
    </div>
    """
    return HttpResponse(html)


@login_required
def instructor_course_dashboard(request):
    """
    Backend studio dashboard for the active tenant creator/instructor.
    Displays course catalog, subscription limit meter, and academy analytics.
    """
    tenant = getattr(request, "tenant", None)
    courses = Course.objects.all().prefetch_related("modules", "enrollments")
    total_modules = sum(c.modules.count() for c in courses)
    total_enrollments = sum(c.enrollments.count() for c in courses)
    published_count = sum(1 for c in courses if c.status == Course.Status.PUBLISHED)
    draft_count = len(courses) - published_count

    subscription = getattr(tenant, "subscription", None) if tenant else None
    max_courses = subscription.plan.max_courses if (subscription and subscription.plan) else 5
    course_usage_percent = int((len(courses) / max_courses) * 100) if max_courses else 0

    if tenant:
        tenant.generate_domain_token()

    return render(
        request,
        "courses/backend/dashboard.html",
        {
            "courses": courses,
            "total_modules": total_modules,
            "total_enrollments": total_enrollments,
            "published_count": published_count,
            "draft_count": draft_count,
            "subscription": subscription,
            "max_courses": max_courses,
            "course_usage_percent": course_usage_percent,
            "tenant": tenant,
            "branding": tenant.branding if tenant else {},
        },
    )


@login_required
def student_learning_dashboard(request):
    """
    Personalized Learner / Student Dashboard for the current academy.
    Displays enrolled courses, completion progress bars, smart 'Resume Learning' links,
    and un-enrolled courses to explore.
    """
    from apps.courses.models import Enrollment, Lesson

    enrollments = Enrollment.objects.filter(
        user=request.user,
        status=Enrollment.Status.ACTIVE,
    ).select_related("course")

    enrolled_courses_data = []
    enrolled_course_ids = []

    for enrollment in enrollments:
        course = enrollment.course
        enrolled_course_ids.append(course.id)
        progress = course.get_user_progress(request.user)

        # Retrieve all lessons in proper curriculum sequence
        lessons = list(
            Lesson.objects.filter(module__course=course)
            .select_related("module")
            .order_by("module__order", "order")
        )

        # Smart Resume: find first uncompleted lesson
        resume_lesson = None
        for l in lessons:
            if l.id not in progress["completed_ids"]:
                resume_lesson = l
                break

        # If all completed or none found, default to first lesson
        if not resume_lesson and lessons:
            resume_lesson = lessons[0]

        enrolled_courses_data.append({
            "course": course,
            "progress": progress,
            "resume_lesson": resume_lesson,
            "is_completed": progress["percent"] == 100 and progress["total_lessons"] > 0,
            "enrolled_at": enrollment.enrolled_at,
        })

    # Summary statistics
    total_enrolled = len(enrolled_courses_data)
    completed_courses_count = sum(1 for item in enrolled_courses_data if item["is_completed"])
    total_lessons_completed = sum(item["progress"]["completed_count"] for item in enrolled_courses_data)

    # Discover other courses in this academy
    available_courses = Course.objects.filter(
        status=Course.Status.PUBLISHED
    ).exclude(id__in=enrolled_course_ids).select_related("instructor")

    return render(
        request,
        "courses/frontend/student_dashboard.html",
        {
            "enrolled_courses_data": enrolled_courses_data,
            "total_enrolled": total_enrolled,
            "completed_courses_count": completed_courses_count,
            "total_lessons_completed": total_lessons_completed,
            "available_courses": available_courses,
        },
    )

