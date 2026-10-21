import re
import urllib.parse
import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def clean_unquoted_slug(slug_str: str) -> str:
    """
    Safely decodes single or double URL/percent-encoded slugs
    (e.g., %25E0%25A6%25AC... -> %E0%A6%AC... -> বল-১ম-পতর-সনর-তর-2).
    """
    if not slug_str:
        return ""
    val = str(slug_str)
    for _ in range(3):
        if "%" in val:
            val = urllib.parse.unquote(val)
        else:
            break
    return val


def bangla_slugify(text: str) -> str:
    """
    Unicode-aware slugifier that fully preserves Bengali vowel signs (কার: া, ি, ী, ু, ূ, ৃ, ে, ৈ, ো, ৌ),
    virama (হসন্ত: ্ for যুক্তবর্ণ), nukta, hasanta, etc., preventing title corruption.
    """
    if not text:
        return ""
    import unicodedata
    text = str(text).strip()
    text = unicodedata.normalize("NFKC", text)
    # Remove unwanted punctuation while preserving word chars and Bengali Unicode block \u0980-\u09FF
    text = re.sub(r"[^\w\s\u0980-\u09FF-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-_")


def get_slug_variants(slug_str: str) -> list[str]:
    """
    Returns a deduplicated list of candidate slugs: clean decoded, raw, quoted,
    and both unicode-preserving and legacy-normalized variants so old and new links both work.
    """
    cleaned = clean_unquoted_slug(slug_str)
    variants = {
        cleaned,
        str(slug_str),
        urllib.parse.quote(cleaned),
        bangla_slugify(cleaned),
        slugify(cleaned, allow_unicode=True),
    }
    return [v for v in variants if v]


def get_og_image_data_for_exam(request, exam, tenant):
    """
    Resolves the best absolute HTTPS image URL and MIME type for Open Graph and WhatsApp link previews.
    Priority: exam thumbnail -> parent group thumbnail -> tenant banner -> tenant logo -> educational default.
    """
    og_image_url = ""
    if exam.thumbnail:
        og_image_url = request.build_absolute_uri(exam.thumbnail.url)
    elif exam.thumbnail_url:
        og_image_url = exam.thumbnail_url
    else:
        grp = exam.groups.filter(thumbnail__isnull=False).exclude(thumbnail="").first()
        if grp and grp.thumbnail:
            og_image_url = request.build_absolute_uri(grp.thumbnail.url)
        elif grp and grp.thumbnail_url:
            og_image_url = grp.thumbnail_url
        elif tenant and tenant.get_banner_url:
            b_url = tenant.get_banner_url
            og_image_url = b_url if b_url.startswith("http") else request.build_absolute_uri(b_url)
        elif tenant and tenant.get_logo_url:
            l_url = tenant.get_logo_url
            og_image_url = l_url if l_url.startswith("http") else request.build_absolute_uri(l_url)
        else:
            og_image_url = "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=1200&h=630&fit=crop&q=80"

    og_image_type = "image/png" if og_image_url.lower().endswith(".png") else "image/jpeg"
    return og_image_url, og_image_type


def get_og_image_data_for_group(request, group, tenant):
    """
    Resolves the best absolute HTTPS image URL and MIME type for ExamGroup Open Graph and WhatsApp previews.
    Priority: group thumbnail -> child exam thumbnail -> tenant banner -> tenant logo -> educational default.
    """
    og_image_url = ""
    if group.thumbnail:
        og_image_url = request.build_absolute_uri(group.thumbnail.url)
    elif group.thumbnail_url:
        og_image_url = group.thumbnail_url
    else:
        e = group.exams.filter(thumbnail__isnull=False).exclude(thumbnail="").first()
        if e and e.thumbnail:
            og_image_url = request.build_absolute_uri(e.thumbnail.url)
        elif tenant and tenant.get_banner_url:
            b_url = tenant.get_banner_url
            og_image_url = b_url if b_url.startswith("http") else request.build_absolute_uri(b_url)
        elif tenant and tenant.get_logo_url:
            l_url = tenant.get_logo_url
            og_image_url = l_url if l_url.startswith("http") else request.build_absolute_uri(l_url)
        else:
            og_image_url = "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=1200&h=630&fit=crop&q=80"

    og_image_type = "image/png" if og_image_url.lower().endswith(".png") else "image/jpeg"
    return og_image_url, og_image_type


from apps.courses.mcq_importer import (
    generate_exam_csv,
    generate_exam_json,
    generate_exam_txt,
    map_letter_to_bengali_option,
    parse_uploaded_file_or_text,
    to_bengali_numeral,
)
from apps.courses.models import (
    BlogPost,
    Book,
    BookOrder,
    ClassRoutine,
    ClubComment,
    ClubLike,
    ClubMembership,
    ClubPost,
    Course,
    Enrollment,
    Exam,
    ExamAttempt,
    ExamGroup,
    ExamGroupEnrollment,
    ExamQuestion,
    FeedComment,
    FeedLike,
    FeedPost,
    FinancialLedger,
    FreeResource,
    Lesson,
    LessonProgress,
    LiveClassSession,
    Module,
    StudentClub,
    StudentInvoice,
    StudentResult,
    SupportChatMessage,
    SupportThread,
)
from apps.tenants.models import SubscriptionPlan, TenantSubscription
from apps.users.models import TenantMembership


def course_list(request):
    """
    Frontend catalog of all published courses for the current tenant.
    Query is automatically scoped by TenantManager!
    """
    tenant = getattr(request, "tenant", None)
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related(
        "instructor"
    )
    enrolled_course_ids = set()
    if request.user.is_authenticated and tenant:
        enrolled_course_ids = set(
            Enrollment.objects.filter(
                tenant=tenant,
                user=request.user,
                status=Enrollment.Status.ACTIVE,
            ).values_list("course_id", flat=True)
        )
    return render(
        request,
        "courses/frontend/list.html",
        {
            "courses": courses,
            "enrolled_course_ids": enrolled_course_ids,
        },
    )


def course_detail(request, slug):
    """Frontend detailed curriculum syllabus for a course."""
    slug_variants = get_slug_variants(slug)
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons").select_related(
            "instructor", "tenant"
        ),
        slug__in=slug_variants,
    )
    tenant = getattr(request, "tenant", None) or course.tenant
    progress_data = course.get_user_progress(request.user)
    first_lesson = (
        Lesson.objects.filter(module__course=course)
        .order_by("module__order", "order")
        .first()
    )

    is_enrolled = False
    is_admin_or_instructor = False
    if request.user.is_authenticated:
        if (
            request.user.is_superuser
            or (tenant and tenant.owner == request.user)
            or course.instructor == request.user
        ):
            is_enrolled = True
            is_admin_or_instructor = True
        else:
            is_enrolled = Enrollment.objects.filter(
                tenant=tenant,
                user=request.user,
                course=course,
                status=Enrollment.Status.ACTIVE,
            ).exists()

    # Handle 1-Click Free Enrollment directly from single course page
    if request.method == "POST" and request.POST.get("action") == "free_enroll":
        if not request.user.is_authenticated:
            messages.info(
                request,
                "ফ্রি কোর্সে এনরোল করার জন্য অনুগ্রহ করে প্রথমে লগইন করুন বা অ্যাকাউন্ট খুলুন।",
            )
            return redirect(f"/login/?next={request.path}")

        if course.is_free:
            TenantMembership.objects.get_or_create(
                tenant=tenant,
                user=request.user,
                defaults={"role": TenantMembership.Role.STUDENT, "is_active": True},
            )
            enrollment, _ = Enrollment.objects.get_or_create(
                tenant=tenant,
                user=request.user,
                course=course,
                defaults={"status": Enrollment.Status.ACTIVE},
            )
            if enrollment.status != Enrollment.Status.ACTIVE:
                enrollment.status = Enrollment.Status.ACTIVE
                enrollment.save()

            # Record zero-amount invoice
            invoice_no = f"INV-{uuid.uuid4().hex[:8].upper()}"
            StudentInvoice.objects.get_or_create(
                tenant=tenant,
                student=request.user,
                item_title=f"Free Course: {course.title}",
                defaults={
                    "invoice_no": invoice_no,
                    "amount": 0,
                    "payment_method": "Free Enrollment",
                    "transaction_id": f"FREE-{uuid.uuid4().hex[:6].upper()}",
                    "status": "PAID",
                },
            )
            messages.success(
                request,
                f"🎉 অভিনন্দন! '{course.title}' কোর্সে আপনার ফ্রি এনরোলমেন্ট সফল হয়েছে। সব ক্লাস আনলক করা হয়েছে!",
            )
            if first_lesson:
                return redirect(
                    "courses:player",
                    course_slug=course.slug,
                    lesson_slug=first_lesson.slug,
                )
            return redirect("courses:detail", slug=course.slug)

    total_lessons_count = sum(m.lessons.count() for m in course.modules.all())
    total_duration_minutes = sum(
        sum(l.duration_minutes for l in m.lessons.all()) for m in course.modules.all()
    )
    total_duration_hours = (
        round(total_duration_minutes / 60, 1) if total_duration_minutes > 0 else 0
    )

    return render(
        request,
        "courses/frontend/detail.html",
        {
            "course": course,
            "progress_data": progress_data,
            "first_lesson": first_lesson,
            "is_enrolled": is_enrolled,
            "is_admin_or_instructor": is_admin_or_instructor,
            "total_lessons_count": total_lessons_count,
            "total_duration_minutes": total_duration_minutes,
            "total_duration_hours": total_duration_hours,
        },
    )


def course_checkout_view(request, slug):
    """
    Seamless Course Checkout and Instant Enrollment Portal:
    - If user is authenticated: enrolls immediately or confirms payment.
    - If user is a new student (signup mode): automatically creates User account (role STUDENT),
      logs in, enrolls in course, creates paid StudentInvoice, and redirects to the player.
    - If existing student (login mode): validates credentials, logs in, enrolls, and redirects to player.
    """
    course = get_object_or_404(
        Course.objects.select_related("tenant", "instructor"),
        slug=slug,
    )
    tenant = getattr(request, "tenant", None) or course.tenant

    # If already logged in and enrolled, jump straight to player
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            tenant=tenant,
            user=request.user,
            course=course,
            status=Enrollment.Status.ACTIVE,
        ).exists()
        if is_enrolled:
            first_lesson = (
                Lesson.objects.filter(module__course=course)
                .order_by("module__order", "order")
                .first()
            )
            if first_lesson:
                return redirect(
                    "courses:player",
                    course_slug=course.slug,
                    lesson_slug=first_lesson.slug,
                )
            return redirect("courses:detail", slug=course.slug)

    if request.method == "POST":
        user = request.user if request.user.is_authenticated else None

        if not user:
            checkout_mode = request.POST.get("checkout_mode", "signup")
            identifier = request.POST.get("identifier", "").strip()
            password = request.POST.get("password", "").strip()
            full_name = request.POST.get("full_name", "").strip()

            if not identifier or not password:
                messages.error(
                    request, "অনুগ্রহ করে মোবাইল নম্বর/ইমেইল এবং পাসওয়ার্ড প্রদান করুন।"
                )
                return render(
                    request,
                    "courses/frontend/checkout.html",
                    {"course": course, "identifier": identifier},
                )

            # Format email identifier
            if "@" in identifier:
                email = identifier.lower()
            else:
                clean_phone = re.sub(r"[^0-9+]", "", identifier)
                email = f"{clean_phone}@student.academy"

            User = get_user_model()

            if checkout_mode == "login":
                user = authenticate(request, email=email, password=password)
                if not user:
                    messages.error(
                        request,
                        "মোবাইল/ইমেইল অথবা পাসওয়ার্ড সঠিক নয়। অনুগ্রহ করে পুনরায় চেষ্টা করুন।",
                    )
                    return render(
                        request,
                        "courses/frontend/checkout.html",
                        {
                            "course": course,
                            "identifier": identifier,
                            "prompt_login": True,
                        },
                    )
                login(request, user)
            else:
                # Signup Mode
                if User.objects.filter(email=email).exists():
                    messages.info(
                        request,
                        "এই মোবাইল/ইমেইলে ইতিমধ্যে একটি অ্যাকাউন্ট রয়েছে। অনুগ্রহ করে পাসওয়ার্ড দিয়ে লগইন করুন।",
                    )
                    return render(
                        request,
                        "courses/frontend/checkout.html",
                        {
                            "course": course,
                            "identifier": identifier,
                            "prompt_login": True,
                        },
                    )

                name_parts = full_name.split(" ", 1)
                first_name = name_parts[0] if name_parts else "Student"
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                login(request, user)

        # 1. Ensure TenantMembership (Role: STUDENT)
        TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": TenantMembership.Role.STUDENT, "is_active": True},
        )

        # 2. Ensure Enrollment is ACTIVE
        enrollment, _ = Enrollment.objects.get_or_create(
            tenant=tenant,
            user=user,
            course=course,
            defaults={"status": Enrollment.Status.ACTIVE},
        )
        if enrollment.status != Enrollment.Status.ACTIVE:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save()

        # 3. Create StudentInvoice
        payment_method = request.POST.get("payment_method", "bKash Online")
        trx_id = (
            request.POST.get("trx_id", "").strip()
            or f"TRX{timezone.now().strftime('%Y%m%d%H%M%S')}"
        )
        invoice_no = f"INV-{uuid.uuid4().hex[:8].upper()}"
        amount = 0 if course.is_free else (course.price or 0)

        StudentInvoice.objects.create(
            tenant=tenant,
            student=user,
            invoice_no=invoice_no,
            item_title=f"Course: {course.title}",
            amount=amount,
            payment_method=payment_method,
            transaction_id=trx_id,
            status="PAID",
        )

        messages.success(
            request, f"🎉 অভিনন্দন! '{course.title}' কোর্সে আপনার ভর্তি সফল হয়েছে।"
        )

        first_lesson = (
            Lesson.objects.filter(module__course=course)
            .order_by("module__order", "order")
            .first()
        )
        if first_lesson:
            return redirect(
                "courses:player", course_slug=course.slug, lesson_slug=first_lesson.slug
            )
        return redirect("courses:detail", slug=course.slug)

    return render(
        request,
        "courses/frontend/checkout.html",
        {
            "course": course,
            "current_tenant": tenant,
        },
    )


def lesson_player_view(request, course_slug, lesson_slug):
    """
    Main Course Player view.
    - If standard HTTP GET -> renders full player shell with responsive collapsible sidebar.
    - If HTMX GET -> renders only player_content.html partial with HX-Push-Url.
    - Protects lessons: redirects non-enrolled guests/students to checkout if lesson is not preview.
    """
    course_slug_variants = get_slug_variants(course_slug)
    lesson_slug_variants = get_slug_variants(lesson_slug)
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons").select_related(
            "tenant", "instructor"
        ),
        slug__in=course_slug_variants,
    )
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__course"),
        module__course=course,
        slug__in=lesson_slug_variants,
    )
    tenant = getattr(request, "tenant", None) or course.tenant

    # Access Authorization Check:
    # 1. Preview lessons are freely viewable.
    # 2. All other lessons (Free OR Paid) REQUIRE user authentication & active enrollment!
    is_authorized = False
    if lesson.is_preview:
        is_authorized = True
    elif request.user.is_authenticated:
        if (
            request.user.is_superuser
            or request.user.is_staff
            or (course.tenant and course.tenant.owner == request.user)
            or course.instructor == request.user
        ):
            is_authorized = True
        else:
            membership = (
                TenantMembership.objects.unscoped()
                .filter(tenant=tenant, user=request.user)
                .first()
            )
            if (
                membership
                and membership.role
                in [TenantMembership.Role.ADMIN, TenantMembership.Role.INSTRUCTOR]
            ) or Enrollment.objects.filter(
                tenant=tenant,
                user=request.user,
                course=course,
                status=Enrollment.Status.ACTIVE,
            ).exists():
                is_authorized = True

    if not is_authorized:
        if course.is_free:
            messages.info(
                request,
                f"'{course.title}' একটি ফ্রি কোর্স! সম্পূর্ণ ক্লাসগুলো দেখতে অনুগ্রহ করে প্রথমে ফ্রিতে এনরোল করুন।",
            )
            return redirect("courses:checkout", slug=course.slug)
        else:
            messages.warning(
                request,
                f"'{course.title}' কোর্সের এই ক্লাসটি লক করা। ক্লাসটি আনলক করতে অনুগ্রহ করে ভর্তি সম্পূর্ণ করুন।",
            )
            return redirect("courses:checkout", slug=course.slug)

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

    # Supplementary tab content
    announcements = FeedPost.objects.filter(tenant=tenant).order_by("-created_at")[:6]
    if not announcements.exists():
        announcements = BlogPost.objects.filter(tenant=tenant).order_by("-created_at")[
            :6
        ]
    pdf_resources = FreeResource.objects.filter(tenant=tenant).order_by("-created_at")[
        :10
    ]
    exams = Exam.objects.filter(tenant=tenant).order_by("-created_at")[:10]

    context = {
        "course": course,
        "lesson": lesson,
        "next_lesson": next_lesson,
        "prev_lesson": prev_lesson,
        "progress_data": progress_data,
        "progress": progress,
        "announcements": announcements,
        "pdf_resources": pdf_resources,
        "exams": exams,
    }

    if request.headers.get("HX-Request"):
        response = render(
            request, "courses/frontend/partials/player_content.html", context
        )
        response["HX-Push-Url"] = reverse(
            "courses:player",
            kwargs={"course_slug": course.slug, "lesson_slug": lesson.slug},
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
        response = render(
            request, "courses/frontend/partials/player_content.html", context
        )
        response["HX-Push-Url"] = reverse(
            "courses:player",
            kwargs={"course_slug": course.slug, "lesson_slug": next_lesson.slug},
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
    <span id="lesson-check-{lesson.id}" hx-swap-oob="true" class="w-5 h-5 flex items-center justify-center rounded-full text-xs {"bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" if progress.is_completed else "bg-slate-800 text-slate-600 border border-slate-700"}">
        {"✓" if progress.is_completed else lesson.order}
    </span>

    <!-- Out-of-band update for progress bar -->
    <div id="course-progress-container" hx-swap-oob="true" class="space-y-1.5">
      <div class="flex items-center justify-between text-xs font-mono">
        <span class="text-slate-400">Curriculum Progress</span>
        <span class="text-emerald-400 font-bold">{progress_data["percent"]}%</span>
      </div>
      <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
        <div class="bg-gradient-to-r from-brand-primary to-emerald-400 h-2 rounded-full transition-all duration-500" style="width: {progress_data["percent"]}%"></div>
      </div>
    </div>
    """
    return HttpResponse(html)


@login_required
def instructor_course_dashboard(request):
    """
    Backend studio dashboard for the active tenant creator/instructor.
    Displays course catalog, subscription limit meter, academy analytics,
    and supports full in-studio Course Create, Edit, and Delete actions.
    """
    tenant = getattr(request, "tenant", None)
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Create Course
        if action == "create_course":
            title = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            intro_video_url = request.POST.get("intro_video_url", "").strip()
            price = request.POST.get("price", "0") or "0"
            is_free = (
                request.POST.get("is_free") == "on"
                or request.POST.get("is_free") == "true"
            )
            status = request.POST.get("status", Course.Status.PUBLISHED)

            if title:
                base_slug = (
                    slugify(title) or f"course-{int(timezone.now().timestamp())}"
                )
                slug = base_slug
                counter = 1
                while Course.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                course = Course.objects.create(
                    tenant=tenant,
                    instructor=request.user,
                    title=title,
                    slug=slug,
                    description=description,
                    intro_video_url=intro_video_url,
                    price=0.00 if is_free else price,
                    is_free=is_free,
                    status=status,
                )
                if "thumbnail" in request.FILES:
                    course.thumbnail = request.FILES["thumbnail"]
                    course.save(update_fields=["thumbnail"])

                # Create default 1st Module
                Module.objects.create(
                    tenant=tenant,
                    course=course,
                    title="মডিউল ০১: পরিচিতি ও বেসিক শুরু",
                    description="কোর্সের প্রাথমিক আলোচনা ও মৌলিক ধারণা",
                    order=1,
                )

                messages.success(
                    request,
                    f"কোর্স '{title}' সফলভাবে তৈরি হয়েছে! এখন কারিকুলাম ও লেসন যুক্ত করুন।",
                )
                return redirect(
                    reverse(
                        "courses:course_curriculum", kwargs={"course_id": course.id}
                    )
                )

        # 2. Update Course
        elif action == "update_course":
            course_id = request.POST.get("course_id")
            course = get_object_or_404(Course, id=course_id)
            course.title = request.POST.get("title", course.title).strip()
            course.description = request.POST.get(
                "description", course.description
            ).strip()
            course.intro_video_url = request.POST.get(
                "intro_video_url", course.intro_video_url
            ).strip()
            is_free = (
                request.POST.get("is_free") == "on"
                or request.POST.get("is_free") == "true"
            )
            course.is_free = is_free
            course.price = (
                0.00 if is_free else (request.POST.get("price", course.price) or 0)
            )
            course.status = request.POST.get("status", course.status)

            if "thumbnail" in request.FILES:
                course.thumbnail = request.FILES["thumbnail"]

            course.save()
            messages.success(request, f"কোর্স '{course.title}' সফলভাবে আপডেট করা হয়েছে!")
            return redirect(f"{request.path}?tab=courses")

        # 3. Delete Course
        elif action == "delete_course":
            course_id = request.POST.get("course_id")
            course = get_object_or_404(Course, id=course_id)
            course_title = course.title
            course.delete()
            messages.success(request, f"কোর্স '{course_title}' সফলভাবে মুছে ফেলা হয়েছে।")
            return redirect(f"{request.path}?tab=courses")

        # 4. Add Financial Ledger Entry (Income / Expense)
        elif action == "add_transaction":
            title = request.POST.get("title", "").strip()
            tx_type = request.POST.get(
                "transaction_type", FinancialLedger.TransactionType.INCOME
            )
            category = request.POST.get("category", FinancialLedger.Category.COURSE_FEE)
            amount = request.POST.get("amount", "0") or "0"
            payment_method = request.POST.get("payment_method", "bKash").strip()
            reference_no = request.POST.get("reference_no", "").strip()
            notes = request.POST.get("notes", "").strip()
            tx_date = request.POST.get("transaction_date") or timezone.now().date()

            if title and float(amount) > 0:
                FinancialLedger.objects.create(
                    tenant=tenant,
                    title=title,
                    transaction_type=tx_type,
                    category=category,
                    amount=amount,
                    payment_method=payment_method,
                    reference_no=reference_no,
                    notes=notes,
                    transaction_date=tx_date,
                )
                type_bn = (
                    "আয়" if tx_type == FinancialLedger.TransactionType.INCOME else "ব্যয়"
                )
                messages.success(
                    request, f"নতুন {type_bn} এন্ট্রি (৳{amount}) সফলভাবে লেজারে যুক্ত হয়েছে!"
                )
            return redirect(f"{request.path}?tab=finance")

        # 5. Delete Financial Ledger Entry
        elif action == "delete_transaction":
            tx_id = request.POST.get("transaction_id")
            FinancialLedger.objects.filter(tenant=tenant, id=tx_id).delete()
            messages.success(request, "লেনদেন রেকর্ডটি সফলভাবে মুছে ফেলা হয়েছে।")
            return redirect(f"{request.path}?tab=finance")

        # 6. Schedule Live Online Class
        elif action == "schedule_live_class":
            title = request.POST.get("title", "").strip()
            course_id = request.POST.get("course_id")
            platform = request.POST.get("platform", LiveClassSession.Platform.ZOOM)
            meeting_url = request.POST.get("meeting_url", "").strip()
            meeting_id = request.POST.get("meeting_id", "").strip()
            passcode = request.POST.get("passcode", "").strip()
            instructor_name = request.POST.get(
                "instructor_name", request.user.get_full_name() or "ইন্সট্রাক্টর"
            ).strip()
            scheduled_at = request.POST.get("scheduled_at")
            duration_minutes = int(request.POST.get("duration_minutes", 60) or 60)
            status = request.POST.get("status", LiveClassSession.Status.UPCOMING)

            course_obj = (
                Course.objects.filter(id=course_id).first() if course_id else None
            )

            if title and meeting_url and scheduled_at:
                LiveClassSession.objects.create(
                    tenant=tenant,
                    course=course_obj,
                    title=title,
                    platform=platform,
                    meeting_url=meeting_url,
                    meeting_id=meeting_id,
                    passcode=passcode,
                    instructor_name=instructor_name,
                    scheduled_at=scheduled_at,
                    duration_minutes=duration_minutes,
                    status=status,
                )
                messages.success(
                    request, f"নতুন লাইভ ক্লাস '{title}' সফলভাবে শিডিউল করা হয়েছে!"
                )
            return redirect(f"{request.path}?tab=live")

        # 7. Delete Live Online Class
        elif action == "delete_live_class":
            session_id = request.POST.get("session_id")
            LiveClassSession.objects.filter(tenant=tenant, id=session_id).delete()
            messages.success(request, "লাইভ ক্লাস শিডিউল মুছে ফেলা হয়েছে।")
            return redirect(f"{request.path}?tab=live")

        # 8. Renew or Upgrade SaaS Subscription
        elif action == "renew_subscription":
            plan_id = request.POST.get("plan_id")
            selected_plan = SubscriptionPlan.objects.filter(id=plan_id).first()
            if not selected_plan:
                messages.error(request, "অনুগ্রহ করে একটি সঠিক প্যাকেজ নির্বাচন করুন।")
                return redirect(f"{request.path}?tab=subscription")

            sub, _ = TenantSubscription.objects.get_or_create(
                tenant=tenant,
                defaults={
                    "plan": selected_plan,
                    "status": TenantSubscription.Status.ACTIVE,
                },
            )
            sub.plan = selected_plan
            sub.status = TenantSubscription.Status.ACTIVE
            # Extend 30 days from now
            sub.current_period_end = timezone.now() + timedelta(days=30)
            sub.trial_ends_at = None
            sub.save()

            payment_method = request.POST.get("payment_method", "bKash")
            reference_no = request.POST.get("reference_no", "").strip()

            # Record in Tenant Financial Ledger as an expense (server/software)
            FinancialLedger.objects.create(
                tenant=tenant,
                title=f"একাডেমি সাবস্ক্রিপশন প্যাকেজ রিনিউ ({selected_plan.name})",
                transaction_type=FinancialLedger.TransactionType.EXPENSE,
                category=FinancialLedger.Category.SERVER_SOFTWARE,
                amount=selected_plan.price_monthly,
                payment_method=payment_method,
                reference_no=reference_no or "SUB-PAID-INSTANT",
                notes=f"প্যাকেজ: {selected_plan.name}, মূল্য: ৳{selected_plan.price_monthly}, মেয়াদ: ৩০ দিন সফলভাবে বর্ধিত।",
                transaction_date=timezone.now().date(),
            )

            messages.success(
                request,
                f"🎉 অভিনন্দন! আপনার '{selected_plan.name}' সাবস্ক্রিপশন সফলভাবে সক্রিয় হয়েছে এবং ৩০ দিনের মেয়াদ যুক্ত হয়েছে।",
            )
            return redirect(f"{request.path}?tab=subscription")

        # 9. In-Dashboard Student Password Reset (No Django Admin needed)
        elif action == "reset_student_password":
            student_id = request.POST.get("student_id")
            new_password = request.POST.get("new_password", "").strip()

            if not student_id or not new_password:
                messages.error(request, "শিক্ষার্থী আইডি এবং নতুন পাসওয়ার্ড প্রদান করুন।")
                return redirect(f"{request.path}?tab=students")

            if len(new_password) < 6:
                messages.error(request, "পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।")
                return redirect(f"{request.path}?tab=students")

            # Verify student belongs to this academy/tenant
            User = get_user_model()
            student_user = User.objects.filter(id=student_id).first()
            if not student_user:
                messages.error(request, "শিক্ষার্থী পাওয়া যায়নি।")
                return redirect(f"{request.path}?tab=students")

            student_user.set_password(new_password)
            student_user.save()
            messages.success(
                request,
                f"✅ শিক্ষার্থী '{student_user.get_full_name() or student_user.email}' এর পাসওয়ার্ড সফলভাবে আপডেট করা হয়েছে!",
            )
            return redirect(f"{request.path}?tab=students")

        # 10. In-Dashboard Update Student Enrollment Status
        elif action == "update_enrollment_status":
            enrollment_id = request.POST.get("enrollment_id")
            new_status = request.POST.get("status")
            enr = Enrollment.objects.filter(
                id=enrollment_id, course__tenant=tenant
            ).first()
            if enr and new_status in [
                Enrollment.Status.ACTIVE,
                Enrollment.Status.CANCELLED,
                Enrollment.Status.COMPLETED,
            ]:
                enr.status = new_status
                enr.save()
                messages.success(
                    request, f"শিক্ষার্থীর কোর্সের স্ট্যাটাস '{new_status}' এ পরিবর্তিত হয়েছে।"
                )
            return redirect(f"{request.path}?tab=students")

        # 11. In-Dashboard Manual Student Course Enrollment
        elif action == "manual_enroll_student":
            student_id = request.POST.get("student_id")
            course_id = request.POST.get("course_id")
            course_obj = Course.objects.filter(tenant=tenant, id=course_id).first()
            User = get_user_model()
            student_user = User.objects.filter(id=student_id).first()

            if course_obj and student_user:
                TenantMembership.objects.unscoped().get_or_create(
                    tenant=tenant,
                    user=student_user,
                    defaults={"role": TenantMembership.Role.STUDENT, "is_active": True},
                )
                enr, created = Enrollment.objects.get_or_create(
                    tenant=tenant,
                    user=student_user,
                    course=course_obj,
                    defaults={"status": Enrollment.Status.ACTIVE},
                )
                if enr.status != Enrollment.Status.ACTIVE:
                    enr.status = Enrollment.Status.ACTIVE
                    enr.save()

                inv_no = f"INV-MANUAL-{uuid.uuid4().hex[:6].upper()}"
                StudentInvoice.objects.get_or_create(
                    tenant=tenant,
                    student=student_user,
                    item_title=f"Manual Enrollment: {course_obj.title}",
                    defaults={
                        "invoice_no": inv_no,
                        "amount": course_obj.price if not course_obj.is_free else 0,
                        "payment_method": "Admin Manual Entry",
                        "transaction_id": f"MANUAL-{uuid.uuid4().hex[:6].upper()}",
                        "status": "PAID",
                    },
                )
                messages.success(
                    request,
                    f"🎉 শিক্ষার্থী '{student_user.get_full_name() or student_user.email}' কে '{course_obj.title}' কোর্সে সফলভাবে ম্যানুয়ালি ভর্তি করা হয়েছে!",
                )
            else:
                messages.error(request, "কোর্স বা শিক্ষার্থী নির্বাচনে ত্রুটি হয়েছে।")
            return redirect(f"{request.path}?tab=students")

        # 12. In-Dashboard Toggle Student Active Status
        elif action == "toggle_student_status":
            student_id = request.POST.get("student_id")
            mem = TenantMembership.objects.unscoped().filter(
                tenant=tenant, user_id=student_id, role=TenantMembership.Role.STUDENT
            ).first()
            if mem:
                mem.is_active = not mem.is_active
                mem.save(update_fields=["is_active"])
                state_bn = "সক্রিয় (Active)" if mem.is_active else "নিষ্ক্রিয় (Inactive)"
                messages.success(request, f"শিক্ষার্থীর অ্যাকাউন্ট স্ট্যাটাস '{state_bn}' করা হয়েছে।")
            return redirect(f"{request.path}?tab=students")

    courses = Course.objects.all().prefetch_related("modules", "enrollments")
    total_modules = sum(c.modules.count() for c in courses)

    # 1. Fetch all TenantMemberships for students
    student_memberships = (
        TenantMembership.objects.unscoped()
        .filter(tenant=tenant, role=TenantMembership.Role.STUDENT)
        .select_related("user")
        .order_by("-joined_at")
    )
    membership_user_ids = set(student_memberships.values_list("user_id", flat=True))

    # 2. Also check if there are users with enrollments, invoices or exam attempts for this tenant
    enrollment_user_ids = set(
        Enrollment.objects.filter(tenant=tenant).values_list("user_id", flat=True)
    )
    invoice_user_ids = set(
        StudentInvoice.objects.filter(tenant=tenant).values_list("student_id", flat=True)
    )
    attempt_user_ids = set(
        ExamAttempt.objects.filter(tenant=tenant).values_list("student_id", flat=True)
    )
    all_student_user_ids = (
        membership_user_ids | enrollment_user_ids | invoice_user_ids | attempt_user_ids
    )

    # Auto-ensure TenantMembership for any student users who enrolled
    for u_id in (all_student_user_ids - membership_user_ids):
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant,
            user_id=u_id,
            defaults={"role": TenantMembership.Role.STUDENT, "is_active": True},
        )

    # Re-fetch memberships to have the complete, unified student list
    student_memberships = (
        TenantMembership.objects.unscoped()
        .filter(tenant=tenant, role=TenantMembership.Role.STUDENT)
        .select_related("user")
        .order_by("-joined_at")
    )

    # Pre-fetch enrollments, exams, and invoices by student
    tenant_enrollments = (
        Enrollment.objects.filter(tenant=tenant)
        .select_related("user", "course")
        .order_by("-enrolled_at")
    )

    # Map user_id to enrollments list
    user_enrollments_map = {}
    for enr in tenant_enrollments:
        user_enrollments_map.setdefault(enr.user_id, []).append(enr)

    # Map user_id to exams count
    exam_attempts_count_map = {}
    for att in ExamAttempt.objects.filter(tenant=tenant).values("student_id"):
        sid = att["student_id"]
        exam_attempts_count_map[sid] = exam_attempts_count_map.get(sid, 0) + 1

    # Map user_id to total paid invoices
    from decimal import Decimal
    invoices_paid_map = {}
    for inv in StudentInvoice.objects.filter(tenant=tenant, status="PAID").values(
        "student_id", "amount"
    ):
        sid = inv["student_id"]
        invoices_paid_map[sid] = invoices_paid_map.get(sid, Decimal("0")) + inv["amount"]

    # Compile comprehensive registered_students list
    registered_students_data = []
    for mem in student_memberships:
        u = mem.user
        enrs = user_enrollments_map.get(u.id, [])
        exams_cnt = exam_attempts_count_map.get(u.id, 0)
        total_paid = invoices_paid_map.get(u.id, Decimal("0"))

        phone = ""
        if "@student.academy" in u.email:
            phone = u.email.split("@")[0]

        registered_students_data.append(
            {
                "membership_id": mem.id,
                "user_id": u.id,
                "user": u,
                "name": u.get_full_name() or u.email,
                "email": u.email,
                "phone": phone,
                "joined_at": mem.joined_at or u.date_joined,
                "is_active": mem.is_active,
                "enrollments": enrs,
                "enrolled_courses_count": len(enrs),
                "exams_count": exams_cnt,
                "total_paid": total_paid,
            }
        )

    total_registered_students = len(registered_students_data)
    total_enrollments = tenant_enrollments.count()
    unique_students_count = total_registered_students
    total_exams_attempted = ExamAttempt.objects.filter(tenant=tenant).count()
    total_student_payments = sum(
        inv["amount"]
        for inv in StudentInvoice.objects.filter(tenant=tenant, status="PAID").values("amount")
    )

    # Financial Ledger & Accounts Metrics
    transactions = FinancialLedger.objects.filter(tenant=tenant).order_by(
        "-transaction_date", "-id"
    )
    total_income = sum(
        t.amount
        for t in transactions
        if t.transaction_type == FinancialLedger.TransactionType.INCOME
    )
    total_expense = sum(
        t.amount
        for t in transactions
        if t.transaction_type == FinancialLedger.TransactionType.EXPENSE
    )
    net_balance = total_income - total_expense

    # Live Online Class Sessions
    live_sessions = (
        LiveClassSession.objects.filter(tenant=tenant)
        .select_related("course")
        .order_by("-scheduled_at")
    )

    published_count = sum(1 for c in courses if c.status == Course.Status.PUBLISHED)
    draft_count = len(courses) - published_count

    subscription = getattr(tenant, "subscription", None) if tenant else None
    max_courses = (
        subscription.plan.max_courses if (subscription and subscription.plan) else 5
    )
    course_usage_percent = (
        int((len(courses) / max_courses) * 100) if max_courses else 0
    )

    plans = SubscriptionPlan.objects.all().order_by("price_monthly")
    is_subscription_expired = tenant.is_subscription_expired if tenant else False

    if tenant:
        tenant.generate_domain_token()

    return render(
        request,
        "courses/backend/dashboard.html",
        {
            "courses": courses,
            "enrollments": tenant_enrollments,
            "registered_students": registered_students_data,
            "total_registered_students": total_registered_students,
            "total_enrollments": total_enrollments,
            "unique_students_count": unique_students_count,
            "total_exams_attempted": total_exams_attempted,
            "total_student_payments": total_student_payments,
            "transactions": transactions,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": net_balance,
            "live_sessions": live_sessions,
            "total_modules": total_modules,
            "published_count": published_count,
            "draft_count": draft_count,
            "subscription": subscription,
            "plans": plans,
            "is_subscription_expired": is_subscription_expired,
            "max_courses": max_courses,
            "course_usage_percent": course_usage_percent,
            "tenant": tenant,
            "branding": tenant.branding if tenant else {},
        },
    )


@login_required
def student_learning_dashboard(request):
    """
    Comprehensive, Multi-Feature Student Dashboard & Learner Portal.
    Includes:
    1. [নিউজ ফিড] (Community News Feed & Student Blog Posts with likes & comments)
    2. [আমার কোর্সসমূহ] (Enrolled Courses with curriculum progress & resume player)
    3. [ক্লাস রুটিন] (Weekly Class Timetable with live class links)
    4. [ফলাফল] (Exam Results, Marksheets & Report Cards)
    5. [সাপোর্ট] (Live Messenger-Style Direct Chat Support)
    6. [প্রোফাইল] (Student Profile, Institution, Batch & Settings)
    7. [ইনভয়েস] (Official Billing Invoices & Receipts)
    8. [আমার অর্ডার] (Physical Book Store Order Tracking)
    9. [ক্লাব] (Study Clubs & Groups with discussions, likes & comments)
    10. ব্রাউজ ([সকল কোর্স] ও [সকল বই])
    """
    tenant = getattr(request, "tenant", None)
    active_tab = request.GET.get("tab") or request.POST.get("active_tab") or "overview"

    # -------------------------------------------------------------
    # POST ACTION HANDLERS
    # -------------------------------------------------------------
    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Feed: Create Post
        if action == "create_feed_post":
            content = request.POST.get("content", "").strip()
            title = request.POST.get("title", "").strip()
            category = request.POST.get("category", FeedPost.Category.GENERAL)
            if content:
                FeedPost.objects.create(
                    tenant=tenant,
                    author=request.user,
                    title=title,
                    content=content,
                    category=category,
                )
                messages.success(
                    request, "আপনার পোস্টটি সফলভাবে কমিউনিটি ফিডে প্রকাশিত হয়েছে!"
                )
            return redirect(f"{request.path}?tab=newsfeed")

        # 2. Feed: Like Post
        elif action == "like_feed_post":
            post_id = request.POST.get("post_id")
            post = FeedPost.objects.filter(id=post_id).first()
            if post:
                like, created = FeedLike.objects.get_or_create(
                    tenant=tenant, post=post, user=request.user
                )
                if not created:
                    like.delete()
            return redirect(f"{request.path}?tab=newsfeed#post-{post_id}")

        # 3. Feed: Comment on Post
        elif action == "comment_feed_post":
            post_id = request.POST.get("post_id")
            comment_text = (
                request.POST.get("comment_text", "").strip()
                or request.POST.get("content", "").strip()
            )
            post = FeedPost.objects.filter(id=post_id).first()
            if post and comment_text:
                FeedComment.objects.create(
                    tenant=tenant,
                    post=post,
                    author=request.user,
                    content=comment_text,
                )
                messages.success(request, "মন্তব্য যুক্ত হয়েছে!")
            return redirect(f"{request.path}?tab=newsfeed#post-{post_id}")

        # 4. Support: Create New Thread / Send Message
        elif action == "create_support_thread":
            subject = request.POST.get("subject", "").strip()
            category = request.POST.get("category", "কোর্স ও ক্লাস সংক্রান্ত")
            initial_message = request.POST.get("message", "").strip()
            if subject and initial_message:
                thread = SupportThread.objects.create(
                    tenant=tenant,
                    student=request.user,
                    subject=subject,
                    category=category,
                    status=SupportThread.Status.OPEN,
                )
                SupportChatMessage.objects.create(
                    tenant=tenant,
                    thread=thread,
                    sender=request.user,
                    message=initial_message,
                    is_staff_reply=False,
                )
                messages.success(
                    request, "সাপোর্ট মেসেজ পাঠানো হয়েছে! মেন্টর টিম দ্রুত উত্তর দেবে।"
                )
                return redirect(f"{request.path}?tab=support&thread_id={thread.id}")
            return redirect(f"{request.path}?tab=support")

        elif action == "send_support_message":
            thread_id = request.POST.get("thread_id")
            message_text = request.POST.get("message", "").strip()
            thread = SupportThread.objects.filter(
                id=thread_id, student=request.user
            ).first()
            if thread and message_text:
                SupportChatMessage.objects.create(
                    tenant=tenant,
                    thread=thread,
                    sender=request.user,
                    message=message_text,
                    is_staff_reply=False,
                )
                thread.updated_at = timezone.now()
                thread.save(update_fields=["updated_at"])
                return redirect(f"{request.path}?tab=support&thread_id={thread.id}")
            return redirect(f"{request.path}?tab=support")

        # 5. Profile: Update Profile Information
        elif action == "update_profile":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            user = request.user
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save()
            messages.success(request, "প্রোফাইল তথ্য সফলভাবে আপডেট হয়েছে!")
            return redirect(f"{request.path}?tab=profile")

        # 6. Clubs: Join Club
        elif action == "join_club":
            club_id = request.POST.get("club_id")
            club = StudentClub.objects.filter(id=club_id).first()
            if club:
                ClubMembership.objects.get_or_create(
                    tenant=tenant, club=club, user=request.user
                )
                messages.success(request, f"আপনি '{club.title}' ক্লাবে যুক্ত হয়েছেন!")
                return redirect(f"{request.path}?tab=clubs&club_slug={club.slug}")
            return redirect(f"{request.path}?tab=clubs")

        # 7. Clubs: Create Post in Club
        elif action == "create_club_post":
            club_id = request.POST.get("club_id")
            title = request.POST.get("title", "").strip()
            content = request.POST.get("content", "").strip()
            club = StudentClub.objects.filter(id=club_id).first()
            if club and content:
                ClubPost.objects.create(
                    tenant=tenant,
                    club=club,
                    author=request.user,
                    title=title,
                    content=content,
                )
                messages.success(request, "ক্লাব গ্রুপে আপনার পোস্ট প্রকাশিত হয়েছে!")
                return redirect(f"{request.path}?tab=clubs&club_slug={club.slug}")
            return redirect(f"{request.path}?tab=clubs")

        # 8. Clubs: Like Post
        elif action == "like_club_post":
            club_post_id = request.POST.get("club_post_id")
            club_post = ClubPost.objects.filter(id=club_post_id).first()
            if club_post:
                like, created = ClubLike.objects.get_or_create(
                    tenant=tenant, post=club_post, user=request.user
                )
                if not created:
                    like.delete()
                return redirect(
                    f"{request.path}?tab=clubs&club_slug={club_post.club.slug}#post-{club_post.id}"
                )
            return redirect(f"{request.path}?tab=clubs")

        # 9. Clubs: Comment on Club Post
        elif action == "comment_club_post":
            club_post_id = request.POST.get("club_post_id")
            comment_text = request.POST.get("comment_text", "").strip()
            club_post = ClubPost.objects.filter(id=club_post_id).first()
            if club_post and comment_text:
                ClubComment.objects.create(
                    tenant=tenant,
                    post=club_post,
                    author=request.user,
                    content=comment_text,
                )
                messages.success(request, "মন্তব্য সফলভাবে যোগ করা হয়েছে!")
                return redirect(
                    f"{request.path}?tab=clubs&club_slug={club_post.club.slug}#post-{club_post.id}"
                )
            return redirect(f"{request.path}?tab=clubs")

        # 10. Direct 1-Click Enroll Course
        elif action == "enroll_course":
            course_id = request.POST.get("course_id")
            course = Course.objects.filter(
                id=course_id, status=Course.Status.PUBLISHED
            ).first()
            if course:
                enrollment, created = Enrollment.objects.get_or_create(
                    tenant=tenant,
                    user=request.user,
                    course=course,
                    defaults={"status": Enrollment.Status.ACTIVE},
                )
                import secrets

                inv_no = f"INV-{timezone.now().year}-{secrets.token_hex(4).upper()}"
                StudentInvoice.objects.get_or_create(
                    tenant=tenant,
                    student=request.user,
                    item_title=course.title,
                    defaults={
                        "invoice_no": inv_no,
                        "amount": course.price,
                        "payment_method": "bKash Online Gateway",
                        "transaction_id": f"TRX{secrets.token_hex(5).upper()}",
                        "status": "PAID",
                    },
                )
                messages.success(
                    request,
                    f"অভিনন্দন! আপনি '{course.title}' কোর্সে সফলভাবে এনরোল করেছেন।",
                )
                return redirect(f"{request.path}?tab=my_courses")

        # 11. Direct 1-Click Order Book
        elif action == "order_book":
            book_id = request.POST.get("book_id")
            address = (
                request.POST.get("address", "").strip()
                or request.POST.get("shipping_address", "").strip()
            )
            phone = (
                request.POST.get("phone", "").strip()
                or request.POST.get("phone_number", "").strip()
            )
            quantity = int(request.POST.get("quantity", 1) or 1)
            book = Book.objects.filter(id=book_id).first()
            if book and address and phone:
                price = book.discount_price if book.discount_price else book.price
                total_amt = price * quantity
                order = BookOrder.objects.create(
                    tenant=tenant,
                    student=request.user,
                    book=book,
                    quantity=quantity,
                    total_amount=total_amt,
                    shipping_address=address,
                    phone_number=phone,
                    status=BookOrder.Status.PROCESSING,
                )
                import secrets

                inv_no = (
                    f"INV-BOOK-{timezone.now().year}-{secrets.token_hex(4).upper()}"
                )
                StudentInvoice.objects.create(
                    tenant=tenant,
                    student=request.user,
                    invoice_no=inv_no,
                    item_title=f"বই অর্ডার: {book.title} (Qty: {quantity})",
                    amount=total_amt,
                    payment_method="Cash on Delivery (COD)",
                    transaction_id=f"COD{secrets.token_hex(4).upper()}",
                    status="PAID",
                )
                messages.success(
                    request,
                    f"আপনার '{book.title}' বইয়ের অর্ডারটি সফলভাবে গ্রহণ করা হয়েছে! ট্র্যাকিং নিচে দেখতে পারেন।",
                )
                return redirect(f"{request.path}?tab=orders")

    # -------------------------------------------------------------
    # DATA AGGREGATION FOR ALL 10 TABS
    # -------------------------------------------------------------
    # Tab 1: Community News Feed
    feed_category = request.GET.get("feed_cat")
    feed_posts = (
        FeedPost.objects.all()
        .select_related("author")
        .prefetch_related("likes", "comments__author")
        .order_by("-created_at")
    )
    if feed_category:
        feed_posts = feed_posts.filter(category=feed_category)

    user_liked_feed_ids = set(
        FeedLike.objects.filter(user=request.user).values_list("post_id", flat=True)
    )

    # Tab 2: My Courses
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

        lessons = list(
            Lesson.objects.filter(module__course=course)
            .select_related("module")
            .order_by("module__order", "order")
        )

        resume_lesson = None
        for l in lessons:
            if l.id not in progress["completed_ids"]:
                resume_lesson = l
                break

        if not resume_lesson and lessons:
            resume_lesson = lessons[0]

        enrolled_courses_data.append(
            {
                "course": course,
                "progress": progress,
                "resume_lesson": resume_lesson,
                "is_completed": progress["percent"] == 100
                and progress["total_lessons"] > 0,
                "enrolled_at": enrollment.enrolled_at,
            }
        )

    total_enrolled = len(enrolled_courses_data)
    completed_courses_count = sum(
        1 for item in enrolled_courses_data if item["is_completed"]
    )
    total_lessons_completed = sum(
        item["progress"]["completed_count"] for item in enrolled_courses_data
    )

    # Tab 3: Class Routine
    routines = (
        ClassRoutine.objects.filter(is_active=True)
        .select_related("course")
        .order_by("day", "start_time")
    )

    # Tab 4: Exam & Academic Results
    results = StudentResult.objects.filter(student=request.user).order_by(
        "-published_date", "-id"
    )

    # Tab 5: Live Support Threads & Messages
    support_threads = (
        SupportThread.objects.filter(student=request.user)
        .prefetch_related("messages__sender")
        .order_by("-updated_at")
    )
    selected_thread_id = request.GET.get("thread_id")
    selected_thread = None
    if selected_thread_id:
        selected_thread = support_threads.filter(id=selected_thread_id).first()
    if not selected_thread:
        selected_thread = support_threads.first()

    # Tab 6: Invoices & Receipts
    invoices = StudentInvoice.objects.filter(student=request.user).order_by("-paid_at")

    # Tab 7: Book Orders
    orders = (
        BookOrder.objects.filter(student=request.user)
        .select_related("book")
        .order_by("-created_at")
    )

    # Tab 8: Study Clubs
    clubs = StudentClub.objects.filter(is_active=True).prefetch_related(
        "memberships", "posts__author", "posts__likes", "posts__comments__author"
    )
    user_joined_club_ids = set(
        ClubMembership.objects.filter(user=request.user).values_list(
            "club_id", flat=True
        )
    )
    user_liked_club_post_ids = set(
        ClubLike.objects.filter(user=request.user).values_list("post_id", flat=True)
    )
    selected_club_slug = request.GET.get("club_slug")
    selected_club = None
    if selected_club_slug:
        selected_club = clubs.filter(slug=selected_club_slug).first()
    if not selected_club:
        selected_club = clubs.first()

    # Tab 9 & 10: Browse Courses & Books
    available_courses = Course.objects.filter(
        status=Course.Status.PUBLISHED
    ).select_related("instructor")
    available_books = Book.objects.filter(in_stock=True).order_by(
        "-is_featured", "-created_at"
    )
    available_exams = (
        Exam.objects.filter(is_published=True)
        .prefetch_related("questions", "attempts")
        .order_by("-created_at")
    )

    # Exam Attempts & Stats for Student Dashboard Overview
    exam_attempts_qs = ExamAttempt.objects.filter(student=request.user)
    total_exams_taken = exam_attempts_qs.count()
    passed_exams_count = exam_attempts_qs.filter(is_passed=True).count()
    recent_exam_attempts = exam_attempts_qs.select_related("exam").order_by("-submitted_at")[:6]
    
    if total_exams_taken > 0:
        scores = [a.percentage for a in exam_attempts_qs]
        avg_exam_score = round(sum(scores) / len(scores), 1)
    else:
        avg_exam_score = 0.0

    in_progress_courses_count = max(0, total_enrolled - completed_courses_count)
    if total_enrolled > 0:
        overall_progress = round(sum(item["progress"]["percent"] for item in enrolled_courses_data) / total_enrolled)
    else:
        overall_progress = 0

    return render(
        request,
        "courses/frontend/student_dashboard.html",
        {
            "active_tab": active_tab,
            "feed_posts": feed_posts,
            "user_liked_feed_ids": user_liked_feed_ids,
            "enrolled_courses_data": enrolled_courses_data,
            "enrolled_course_ids": set(enrolled_course_ids),
            "total_enrolled": total_enrolled,
            "completed_courses_count": completed_courses_count,
            "in_progress_courses_count": in_progress_courses_count,
            "total_lessons_completed": total_lessons_completed,
            "overall_progress": overall_progress,
            "total_exams_taken": total_exams_taken,
            "passed_exams_count": passed_exams_count,
            "recent_exam_attempts": recent_exam_attempts,
            "avg_exam_score": avg_exam_score,
            "routines": routines,
            "results": results,
            "available_exams": available_exams,
            "support_threads": support_threads,
            "selected_thread": selected_thread,
            "invoices": invoices,
            "orders": orders,
            "clubs": clubs,
            "selected_club": selected_club,
            "user_joined_club_ids": user_joined_club_ids,
            "user_liked_club_post_ids": user_liked_club_post_ids,
            "available_courses": available_courses,
            "available_books": available_books,
            "tenant": tenant,
            "branding": tenant.branding if tenant else {},
        },
    )


# ==========================================
# 📚 BOOKS / PUBLICATIONS (বইসমূহ) VIEWS
# ==========================================


def book_list(request):
    """Public catalog of all published books for the active tenant."""
    search_query = request.GET.get("q", "").strip()
    books = Book.objects.all().order_by("-is_featured", "-created_at")

    if search_query:
        books = books.filter(title__icontains=search_query) | books.filter(
            author__icontains=search_query
        )

    return render(
        request,
        "courses/frontend/books/list.html",
        {
            "books": books,
            "search_query": search_query,
        },
    )


def book_detail(request, slug):
    """Detailed preview and order page for a specific book."""
    slug_variants = get_slug_variants(slug)
    book = get_object_or_404(Book, slug__in=slug_variants)
    related_books = Book.objects.exclude(id=book.id)[:4]
    return render(
        request,
        "courses/frontend/books/detail.html",
        {
            "book": book,
            "related_books": related_books,
        },
    )


# ==========================================
# 🎁 FREE RESOURCES (ফ্রি রিসোর্স) VIEWS
# ==========================================


def resource_list(request):
    """Public hub for free downloadable notes, model tests, and suggestions."""
    category_filter = request.GET.get("category", "")
    type_filter = request.GET.get("type", "")
    search_query = request.GET.get("q", "").strip()

    resources = FreeResource.objects.filter(is_published=True).order_by("-created_at")

    if category_filter:
        resources = resources.filter(category=category_filter)
    if type_filter:
        resources = resources.filter(resource_type=type_filter)
    if search_query:
        resources = resources.filter(title__icontains=search_query) | resources.filter(
            description__icontains=search_query
        )

    # Distinct categories for tab filters
    categories = (
        FreeResource.objects.filter(is_published=True)
        .values_list("category", flat=True)
        .distinct()
    )

    return render(
        request,
        "courses/frontend/resources/list.html",
        {
            "resources": resources,
            "categories": categories,
            "selected_category": category_filter,
            "selected_type": type_filter,
            "search_query": search_query,
            "resource_types": FreeResource.ResourceType.choices,
        },
    )


def resource_download(request, slug):
    """Increments download count and redirects to download file or external link."""
    slug_variants = get_slug_variants(slug)
    resource = get_object_or_404(FreeResource, slug__in=slug_variants, is_published=True)
    resource.download_count += 1
    resource.save(update_fields=["download_count"])

    download_url = resource.get_download_link
    if download_url and download_url != "#":
        return redirect(download_url)
    return redirect("courses:resources_list")


# ==========================================
# 📝 BLOG / ARTICLES (ব্লগ) VIEWS
# ==========================================


def blog_list(request):
    """Public blog article directory for the active tenant."""
    category_filter = request.GET.get("category", "")
    search_query = request.GET.get("q", "").strip()

    posts = BlogPost.objects.filter(is_published=True).order_by("-created_at")

    if category_filter:
        posts = posts.filter(category=category_filter)
    if search_query:
        posts = posts.filter(title__icontains=search_query) | posts.filter(
            content__icontains=search_query
        )

    categories = (
        BlogPost.objects.filter(is_published=True)
        .values_list("category", flat=True)
        .distinct()
    )
    featured_post = posts.first() if not category_filter and not search_query else None
    remaining_posts = posts.exclude(id=featured_post.id) if featured_post else posts

    return render(
        request,
        "courses/frontend/blog/list.html",
        {
            "posts": remaining_posts,
            "featured_post": featured_post,
            "categories": categories,
            "selected_category": category_filter,
            "search_query": search_query,
        },
    )


def blog_detail(request, slug):
    """Full reading view for an individual blog post."""
    slug_variants = get_slug_variants(slug)
    post = get_object_or_404(BlogPost, slug__in=slug_variants, is_published=True)
    post.views_count += 1
    post.save(update_fields=["views_count"])

    recent_posts = BlogPost.objects.filter(is_published=True).exclude(id=post.id)[:3]
    return render(
        request,
        "courses/frontend/blog/detail.html",
        {
            "post": post,
            "recent_posts": recent_posts,
        },
    )


# ==========================================
# 🛠️ INSTRUCTOR STUDIO MANAGERS
# ==========================================


def _check_tenant_admin(request):
    """Helper to verify creator/admin/instructor access."""
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return False
    if tenant.owner == request.user or request.user.is_superuser:
        return True
    membership = (
        TenantMembership.objects.unscoped()
        .filter(tenant=tenant, user=request.user)
        .first()
    )
    return bool(
        membership
        and membership.role
        in [TenantMembership.Role.ADMIN, TenantMembership.Role.INSTRUCTOR]
    )


@login_required
def manage_books_view(request):
    """Studio page to manage published books."""
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin permission required.")

    tenant = request.tenant
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            title = request.POST.get("title", "").strip()
            subtitle = request.POST.get("subtitle", "").strip()
            author = request.POST.get("author", "একাডেমি ফ্যাকাল্টি").strip()
            price = request.POST.get("price", "0") or "0"
            discount_price = request.POST.get("discount_price") or None
            edition = request.POST.get("edition", "২০২৬ সংস্করণ").strip()
            pages = int(request.POST.get("pages", 0) or 0)
            in_stock = request.POST.get("in_stock") == "on"
            description = request.POST.get("description", "").strip()
            cover_url = request.POST.get("cover_url", "").strip()
            buy_url = request.POST.get("buy_url", "").strip()

            base_slug = slugify(title) or f"book-{int(timezone.now().timestamp())}"
            slug = base_slug
            counter = 1
            while Book.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            book = Book.objects.create(
                tenant=tenant,
                title=title,
                subtitle=subtitle,
                slug=slug,
                author=author,
                price=price,
                discount_price=discount_price,
                edition=edition,
                pages=pages,
                in_stock=in_stock,
                description=description,
                cover_url=cover_url,
                buy_url=buy_url,
            )
            if "cover_image" in request.FILES:
                book.cover_image = request.FILES["cover_image"]
                book.save(update_fields=["cover_image"])

            messages.success(request, f"বই '{title}' সফলভাবে যুক্ত হয়েছে!")

        elif action == "delete":
            book_id = request.POST.get("book_id")
            Book.objects.filter(id=book_id).delete()
            messages.success(request, "বইটি ডিলিট করা হয়েছে।")

        return redirect("courses:manage_books")

    books = Book.objects.all().order_by("-created_at")
    return render(
        request,
        "courses/backend/manage_books.html",
        {
            "books": books,
            "tenant": tenant,
        },
    )


@login_required
def manage_resources_view(request):
    """Studio page to manage downloadable free resources."""
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin permission required.")

    tenant = request.tenant
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            title = request.POST.get("title", "").strip()
            category = request.POST.get("category", "এইচএসসি ও ভর্তি").strip()
            resource_type = request.POST.get(
                "resource_type", FreeResource.ResourceType.PDF_NOTE
            )
            file_url = request.POST.get("file_url", "").strip()
            video_url = request.POST.get("video_url", "").strip()
            description = request.POST.get("description", "").strip()

            base_slug = slugify(title) or f"res-{int(timezone.now().timestamp())}"
            slug = base_slug
            counter = 1
            while FreeResource.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            resource = FreeResource.objects.create(
                tenant=tenant,
                title=title,
                slug=slug,
                category=category,
                resource_type=resource_type,
                file_url=file_url,
                video_url=video_url,
                description=description,
                is_published=True,
            )
            if "file" in request.FILES:
                resource.file = request.FILES["file"]
                resource.save(update_fields=["file"])

            messages.success(request, f"রিসোর্স '{title}' সফলভাবে আপলোড হয়েছে!")

        elif action == "delete":
            res_id = request.POST.get("resource_id")
            FreeResource.objects.filter(id=res_id).delete()
            messages.success(request, "রিসোর্সটি ডিলিট করা হয়েছে।")

        return redirect("courses:manage_resources")

    resources = FreeResource.objects.all().order_by("-created_at")
    return render(
        request,
        "courses/backend/manage_resources.html",
        {
            "resources": resources,
            "resource_types": FreeResource.ResourceType.choices,
            "tenant": tenant,
        },
    )


@login_required
def manage_blog_view(request):
    """Studio page to manage blog articles."""
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin permission required.")

    tenant = request.tenant
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            title = request.POST.get("title", "").strip()
            category = request.POST.get("category", "ভর্তি প্রস্তুতি").strip()
            author_name = request.POST.get("author_name", "একাডেমি টিম").strip()
            excerpt = request.POST.get("excerpt", "").strip()
            content = request.POST.get("content", "").strip()
            cover_url = request.POST.get("cover_url", "").strip()

            base_slug = slugify(title) or f"post-{int(timezone.now().timestamp())}"
            slug = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            post = BlogPost.objects.create(
                tenant=tenant,
                title=title,
                slug=slug,
                category=category,
                author_name=author_name,
                excerpt=excerpt,
                content=content,
                cover_url=cover_url,
                is_published=True,
            )
            if "cover_image" in request.FILES:
                post.cover_image = request.FILES["cover_image"]
                post.save(update_fields=["cover_image"])

            messages.success(request, f"ব্লগ পোস্ট '{title}' প্রকাশিত হয়েছে!")

        elif action == "delete":
            post_id = request.POST.get("post_id")
            BlogPost.objects.filter(id=post_id).delete()
            messages.success(request, "ব্লগ পোস্ট ডিলিট করা হয়েছে।")

        return redirect("courses:manage_blog")

    posts = BlogPost.objects.all().order_by("-created_at")
    return render(
        request,
        "courses/backend/manage_blog.html",
        {
            "posts": posts,
            "tenant": tenant,
        },
    )


# =====================================================================
# 📚 CURRICULUM BUILDER (MODULES & LESSONS CRUD)
# =====================================================================


@login_required
def course_curriculum_builder(request, course_id):
    """
    Dedicated visual builder for Course Modules and Lessons.
    Supports creating, editing, reordering, and deleting modules and lessons.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons"), id=course_id
    )

    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Create Module
        if action == "create_module":
            title = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            order = int(request.POST.get("order", 0) or 0)
            if not order:
                order = course.modules.count() + 1

            if title:
                Module.objects.create(
                    tenant=tenant,
                    course=course,
                    title=title,
                    description=description,
                    order=order,
                )
                messages.success(request, f"মডিউল '{title}' সফলভাবে যুক্ত হয়েছে!")

        # 2. Update Module
        elif action == "update_module":
            module_id = request.POST.get("module_id")
            module = get_object_or_404(Module, id=module_id, course=course)
            module.title = request.POST.get("title", module.title).strip()
            module.description = request.POST.get(
                "description", module.description
            ).strip()
            module.order = int(request.POST.get("order", module.order) or module.order)
            module.save()
            messages.success(request, f"মডিউল '{module.title}' আপডেট হয়েছে!")

        # 3. Delete Module
        elif action == "delete_module":
            module_id = request.POST.get("module_id")
            module = get_object_or_404(Module, id=module_id, course=course)
            mod_title = module.title
            module.delete()
            messages.success(request, f"মডিউল '{mod_title}' মুছে ফেলা হয়েছে।")

        # 4. Create Lesson
        elif action == "create_lesson":
            module_id = request.POST.get("module_id")
            module = get_object_or_404(Module, id=module_id, course=course)
            title = request.POST.get("title", "").strip()
            content_type = request.POST.get("content_type", Lesson.ContentType.VIDEO)
            video_url = request.POST.get("video_url", "").strip()
            content = (
                request.POST.get("content_text", "").strip()
                or request.POST.get("content", "").strip()
            )
            duration_minutes = int(request.POST.get("duration_minutes", 0) or 0)
            is_preview = (
                request.POST.get("is_preview") == "on"
                or request.POST.get("is_preview") == "true"
            )
            order = int(request.POST.get("order", 0) or 0)
            if not order:
                order = module.lessons.count() + 1

            if title:
                base_slug = (
                    slugify(title) or f"lesson-{int(timezone.now().timestamp())}"
                )
                slug = base_slug
                counter = 1
                while Lesson.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                Lesson.objects.create(
                    tenant=tenant,
                    module=module,
                    title=title,
                    slug=slug,
                    content_type=content_type,
                    video_url=video_url,
                    content=content,
                    duration_minutes=duration_minutes,
                    is_preview=is_preview,
                    order=order,
                )
                messages.success(request, f"লেসন '{title}' সফলভাবে যুক্ত হয়েছে!")

        # 5. Update Lesson
        elif action == "update_lesson":
            lesson_id = request.POST.get("lesson_id")
            lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
            lesson.title = request.POST.get("title", lesson.title).strip()
            lesson.content_type = request.POST.get("content_type", lesson.content_type)
            lesson.video_url = request.POST.get("video_url", lesson.video_url).strip()
            lesson.content = (
                request.POST.get("content_text", lesson.content).strip()
                or request.POST.get("content", lesson.content).strip()
            )
            duration_minutes = int(
                request.POST.get("duration_minutes", lesson.duration_minutes)
                or lesson.duration_minutes
            )
            lesson.duration_minutes = duration_minutes
            lesson.is_preview = (
                request.POST.get("is_preview") == "on"
                or request.POST.get("is_preview") == "true"
            )
            lesson.order = int(request.POST.get("order", lesson.order) or lesson.order)
            lesson.save()
            messages.success(request, f"লেসন '{lesson.title}' আপডেট হয়েছে!")

        # 6. Delete Lesson
        elif action == "delete_lesson":
            lesson_id = request.POST.get("lesson_id")
            lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
            les_title = lesson.title
            lesson.delete()
            messages.success(request, f"লেসন '{les_title}' মুছে ফেলা হয়েছে।")

        return redirect(
            reverse("courses:course_curriculum", kwargs={"course_id": course.id})
        )

    return render(
        request,
        "courses/backend/curriculum_builder.html",
        {
            "course": course,
            "tenant": tenant,
            "content_types": Lesson.ContentType.choices,
        },
    )


# =====================================================================
# 📝 MCQ EXAM STUDIO (EXAM CRUD & QUESTION BUILDER)
# =====================================================================


@login_required
def manage_exams_view(request):
    """
    Studio page to manage all online MCQ exams in this academy.
    Supports Create, Update, Delete Exam actions.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Create Exam
        if action == "create_exam":
            title = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            course_id = request.POST.get("course_id")
            duration_minutes = int(request.POST.get("duration_minutes", 30) or 30)
            pass_mark = float(request.POST.get("pass_mark", 40) or 40)
            negative_mark = float(
                request.POST.get("negative_mark_per_question", 0.25) or 0.25
            )
            is_published = (
                request.POST.get("is_published") == "on"
                or request.POST.get("is_published") == "true"
            )

            course = Course.objects.filter(id=course_id).first() if course_id else None

            if not title:
                messages.error(request, "পরীক্ষার শিরোনাম প্রদান করা আবশ্যক।")
                return redirect("courses:manage_exams")

            import secrets

            custom_slug = request.POST.get("slug", "").strip()
            if custom_slug:
                base_slug = bangla_slugify(custom_slug) or f"exam-{secrets.token_hex(4)}"
            else:
                base_slug = (
                    bangla_slugify(title) or f"exam-{secrets.token_hex(4)}"
                )
            slug = base_slug
            counter = 1
            while Exam.objects.filter(tenant=tenant, slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            exam = Exam.objects.create(
                tenant=tenant,
                course=course,
                title=title,
                slug=slug,
                description=description,
                duration_minutes=duration_minutes,
                pass_mark=pass_mark,
                negative_mark_per_question=negative_mark,
                show_pass_mark=(request.POST.get("show_pass_mark") in ["on", "true", "1"]),
                show_negative_mark=(request.POST.get("show_negative_mark") in ["on", "true", "1"]),
                thumbnail=request.FILES.get("thumbnail"),
                thumbnail_url=request.POST.get("thumbnail_url", "").strip(),
                is_published=is_published,
            )
            messages.success(
                request, f"🎉 পরীক্ষা '{title}' সফলভাবে তৈরি হয়েছে! এখন প্রশ্ন যুক্ত করুন।"
            )
            return redirect(
                reverse("courses:exam_builder", kwargs={"exam_id": exam.id})
            )

        # 2. Update Exam
        elif action == "update_exam":
            exam_id = request.POST.get("exam_id")
            exam = get_object_or_404(Exam, id=exam_id)
            exam.title = request.POST.get("title", exam.title).strip()
            custom_slug = request.POST.get("slug", "").strip()
            if custom_slug:
                new_slug = bangla_slugify(custom_slug)
                if new_slug and new_slug != exam.slug:
                    test_slug = new_slug
                    counter = 1
                    while Exam.objects.filter(tenant=tenant, slug=test_slug).exclude(id=exam.id).exists():
                        test_slug = f"{new_slug}-{counter}"
                        counter += 1
                    exam.slug = test_slug
            exam.description = request.POST.get("description", exam.description).strip()
            course_id = request.POST.get("course_id")
            exam.course = (
                Course.objects.filter(id=course_id).first() if course_id else None
            )
            exam.duration_minutes = int(
                request.POST.get("duration_minutes", exam.duration_minutes)
                or exam.duration_minutes
            )
            exam.pass_mark = float(
                request.POST.get("pass_mark", exam.pass_mark) or exam.pass_mark
            )
            exam.negative_mark_per_question = float(
                request.POST.get(
                    "negative_mark_per_question", exam.negative_mark_per_question
                )
                or exam.negative_mark_per_question
            )
            exam.show_pass_mark = (request.POST.get("show_pass_mark") in ["on", "true", "1"])
            exam.show_negative_mark = (request.POST.get("show_negative_mark") in ["on", "true", "1"])
            if "thumbnail" in request.FILES:
                exam.thumbnail = request.FILES["thumbnail"]
            if "thumbnail_url" in request.POST:
                exam.thumbnail_url = request.POST.get("thumbnail_url", "").strip()
            exam.is_published = (
                request.POST.get("is_published") == "on"
                or request.POST.get("is_published") == "true"
            )
            exam.save()
            messages.success(request, f"পরীক্ষা '{exam.title}' আপডেট হয়েছে!")
            return redirect("courses:manage_exams")

        # 3. Delete Exam
        elif action == "delete_exam":
            exam_id = request.POST.get("exam_id")
            exam = get_object_or_404(Exam, id=exam_id)
            exam_title = exam.title
            exam.delete()
            messages.success(request, f"পরীক্ষা '{exam_title}' মুছে ফেলা হয়েছে।")
            return redirect("courses:manage_exams")

        # 4. Create Exam Group
        elif action == "create_exam_group":
            title = request.POST.get("title", "").strip()
            custom_slug = request.POST.get("slug", "").strip()
            description = request.POST.get("description", "").strip()
            is_free = (
                request.POST.get("is_free") == "on"
                or request.POST.get("is_free") == "true"
            )
            price = float(request.POST.get("price", 0) or 0)
            discount_price_raw = request.POST.get("discount_price")
            discount_price = (
                float(discount_price_raw) if discount_price_raw else None
            )
            thumbnail = request.FILES.get("thumbnail")
            thumbnail_url = request.POST.get("thumbnail_url", "").strip()
            is_published = (
                request.POST.get("is_published", "on") in ["on", "true"]
            )
            exam_ids = request.POST.getlist("exam_ids")

            if not title:
                messages.error(request, "এক্সাম গ্রুপের শিরোনাম প্রদান করা আবশ্যক।")
                return redirect("courses:manage_exams")

            import secrets

            if custom_slug:
                base_slug = bangla_slugify(custom_slug) or f"group-{secrets.token_hex(4)}"
            else:
                base_slug = bangla_slugify(title) or f"group-{secrets.token_hex(4)}"
            slug = base_slug
            counter = 1
            while ExamGroup.objects.filter(tenant=tenant, slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            group = ExamGroup.objects.create(
                tenant=tenant,
                title=title,
                slug=slug,
                description=description,
                is_free=is_free,
                price=price,
                discount_price=discount_price,
                thumbnail=thumbnail,
                thumbnail_url=thumbnail_url,
                is_published=is_published,
            )
            if exam_ids:
                group.exams.set(Exam.objects.filter(id__in=exam_ids))

            messages.success(
                request, f"🎉 এক্সাম গ্রুপ '{title}' সফলভাবে তৈরি হয়েছে!"
            )
            return redirect("courses:manage_exams")

        # 5. Update Exam Group
        elif action == "update_exam_group":
            group_id = request.POST.get("group_id")
            group = get_object_or_404(ExamGroup, id=group_id)
            group.title = request.POST.get("title", group.title).strip()
            custom_slug = request.POST.get("slug", "").strip()
            if custom_slug:
                new_slug = bangla_slugify(custom_slug)
                if new_slug and new_slug != group.slug:
                    test_slug = new_slug
                    counter = 1
                    while ExamGroup.objects.filter(tenant=tenant, slug=test_slug).exclude(id=group.id).exists():
                        test_slug = f"{new_slug}-{counter}"
                        counter += 1
                    group.slug = test_slug
            group.description = request.POST.get("description", group.description).strip()
            group.is_free = (
                request.POST.get("is_free") == "on"
                or request.POST.get("is_free") == "true"
            )
            group.price = float(request.POST.get("price", group.price) or group.price)
            discount_price_raw = request.POST.get("discount_price")
            group.discount_price = (
                float(discount_price_raw) if discount_price_raw else None
            )
            if "thumbnail" in request.FILES:
                group.thumbnail = request.FILES["thumbnail"]
            if "thumbnail_url" in request.POST:
                group.thumbnail_url = request.POST.get("thumbnail_url", "").strip()
            group.is_published = (
                request.POST.get("is_published", "on") in ["on", "true"]
            )
            exam_ids = request.POST.getlist("exam_ids")
            group.exams.set(Exam.objects.filter(id__in=exam_ids))
            group.save()
            messages.success(request, f"এক্সাম গ্রুপ '{group.title}' আপডেট হয়েছে!")
            return redirect("courses:manage_exams")

        # 6. Delete Exam Group
        elif action == "delete_exam_group":
            group_id = request.POST.get("group_id")
            group = get_object_or_404(ExamGroup, id=group_id)
            group_title = group.title
            group.delete()
            messages.success(
                request, f"এক্সাম গ্রুপ '{group_title}' মুছে ফেলা হয়েছে।"
            )
            return redirect("courses:manage_exams")

    exams = Exam.objects.all().prefetch_related("questions", "attempts", "course", "groups")
    exam_groups = ExamGroup.objects.all().prefetch_related("exams__questions", "enrollments")
    total_questions = sum(e.questions.count() for e in exams)
    courses = Course.objects.all()
    return render(
        request,
        "courses/backend/manage_exams.html",
        {
            "exams": exams,
            "exam_groups": exam_groups,
            "total_questions": total_questions,
            "courses": courses,
            "tenant": tenant,
        },
    )


@login_required
def exam_builder_view(request, exam_id):
    """
    Studio Question Bank Builder for an Exam.
    Allows adding, editing, and deleting MCQ questions, options, and explanations.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    exam = get_object_or_404(
        Exam.objects.prefetch_related("questions", "attempts__student"), id=exam_id
    )

    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Create Question
        if action == "create_question":
            question_text = request.POST.get("question_text", "").strip()
            image_url = request.POST.get("image_url", "").strip()
            option_a = request.POST.get("option_a", "").strip()
            option_b = request.POST.get("option_b", "").strip()
            option_c = request.POST.get("option_c", "").strip()
            option_d = request.POST.get("option_d", "").strip()
            correct_option = request.POST.get("correct_option", "A").upper()
            explanation = request.POST.get("explanation", "").strip()
            marks = float(request.POST.get("marks", 1.0) or 1.0)
            order = int(request.POST.get("order", 0) or 0)
            if not order:
                order = exam.questions.count() + 1

            if question_text and option_a and option_b:
                ExamQuestion.objects.create(
                    tenant=tenant,
                    exam=exam,
                    question_text=question_text,
                    image_url=image_url,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct_option,
                    explanation=explanation,
                    marks=marks,
                    order=order,
                )
                messages.success(request, f"প্রশ্ন #{order} সফলভাবে যুক্ত হয়েছে!")

        # 2. Update Question
        elif action == "update_question":
            question_id = request.POST.get("question_id")
            q = get_object_or_404(ExamQuestion, id=question_id, exam=exam)
            q.question_text = request.POST.get("question_text", q.question_text).strip()
            q.image_url = request.POST.get("image_url", q.image_url).strip()
            q.option_a = request.POST.get("option_a", q.option_a).strip()
            q.option_b = request.POST.get("option_b", q.option_b).strip()
            q.option_c = request.POST.get("option_c", q.option_c).strip()
            q.option_d = request.POST.get("option_d", q.option_d).strip()
            q.correct_option = request.POST.get(
                "correct_option", q.correct_option
            ).upper()
            q.explanation = request.POST.get("explanation", q.explanation).strip()
            q.marks = float(request.POST.get("marks", q.marks) or q.marks)
            q.order = int(request.POST.get("order", q.order) or q.order)
            q.save()
            messages.success(request, f"প্রশ্ন #{q.order} আপডেট হয়েছে!")

        # 3. Delete Question
        elif action == "delete_question":
            question_id = request.POST.get("question_id")
            q = get_object_or_404(ExamQuestion, id=question_id, exam=exam)
            q_order = q.order
            q.delete()
            messages.success(request, f"প্রশ্ন #{q_order} মুছে ফেলা হয়েছে।")

        return redirect(reverse("courses:exam_builder", kwargs={"exam_id": exam.id}))

    questions = exam.questions.all().order_by("order", "id")
    recent_attempts = exam.attempts.all().select_related("student")[:20]

    return render(
        request,
        "courses/backend/exam_builder.html",
        {
            "exam": exam,
            "questions": questions,
            "recent_attempts": recent_attempts,
            "tenant": tenant,
            "correct_options": ExamQuestion.CorrectOption.choices,
        },
    )


@login_required
def exam_import_questions_view(request, exam_id):
    """
    Handles bulk import and live interactive preview of MCQ questions
    from uploaded files (.txt, .docx, .csv, .json) or copy-pasted text.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method != "POST":
        return redirect(reverse("courses:exam_builder", kwargs={"exam_id": exam.id}))

    action = request.POST.get("action", "import")
    is_ajax_preview = (
        request.POST.get("preview_only") == "true"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        and action == "preview"
    )

    file_obj = request.FILES.get("file")
    raw_text = request.POST.get("raw_text", "").strip()
    questions_json_payload = request.POST.get("questions_json", "").strip()
    encoding_mode = request.POST.get("encoding_mode", "auto").strip().lower()

    parsed_questions = []

    # If already parsed and sent back as verified JSON
    if questions_json_payload:
        try:
            import json

            parsed_questions = json.loads(questions_json_payload)
        except Exception:
            parsed_questions = []

    if not parsed_questions:
        parsed_questions = parse_uploaded_file_or_text(
            file_obj=file_obj, raw_text=raw_text, encoding_mode=encoding_mode
        )

    # If this is an AJAX preview request, return JSON
    if is_ajax_preview or action == "preview":
        return JsonResponse(
            {
                "status": "success" if parsed_questions else "error",
                "count": len(parsed_questions),
                "questions": parsed_questions,
                "message": f"{len(parsed_questions)}টি প্রশ্ন সফলভাবে চিহ্নিত করা হয়েছে।"
                if parsed_questions
                else "কোনো প্রশ্ন চিহ্নিত করা যায়নি। ফরম্যাট চেক করুন।",
            }
        )

    # Action is Final Import
    if not parsed_questions:
        messages.error(
            request,
            "কোনো বৈধ MCQ প্রশ্ন পাওয়া যায়নি। অনুগ্রহ করে সঠিক ফরম্যাটে ফাইল আপলোড বা টেক্সট পেস্ট করুন।",
        )
        return redirect(reverse("courses:exam_builder", kwargs={"exam_id": exam.id}))

    import_mode = request.POST.get("import_mode", "append")  # 'append' or 'overwrite'
    if import_mode == "overwrite":
        deleted_count = exam.questions.count()
        exam.questions.all().delete()
        current_order = 0
    else:
        current_order = exam.questions.count()

    created_objs = []
    for q_data in parsed_questions:
        current_order += 1
        created_objs.append(
            ExamQuestion(
                tenant=tenant,
                exam=exam,
                question_text=q_data.get("question_text", ""),
                image_url=q_data.get("image_url", ""),
                option_a=q_data.get("option_a", ""),
                option_b=q_data.get("option_b", ""),
                option_c=q_data.get("option_c", ""),
                option_d=q_data.get("option_d", ""),
                correct_option=q_data.get("correct_option", "A"),
                explanation=q_data.get("explanation", ""),
                marks=float(q_data.get("marks", 1.0) or 1.0),
                order=current_order,
            )
        )

    ExamQuestion.objects.bulk_create(created_objs)

    # Update exam total marks based on calculated questions
    exam.total_marks = exam.calculated_total_marks
    exam.save(update_fields=["total_marks"])

    messages.success(
        request, f"🎉 সফলভাবে {len(created_objs)}টি MCQ প্রশ্ন ইমপোর্ট করা হয়েছে!"
    )
    return redirect(reverse("courses:exam_builder", kwargs={"exam_id": exam.id}))


@login_required
def exam_export_txt_view(request, exam_id):
    """
    Exports exam questions in standard Bengali/English text format.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    content = generate_exam_txt(exam)
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{exam.slug}_questions.txt"'
    )
    return response


@login_required
def exam_export_csv_view(request, exam_id):
    """
    Exports exam questions to CSV format with UTF-8 BOM for Microsoft Excel compatibility.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    content = generate_exam_csv(exam)
    # Include UTF-8-sig BOM so Bengali characters render without corruption in Excel
    response = HttpResponse(
        content.encode("utf-8-sig"), content_type="text/csv; charset=utf-8-sig"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{exam.slug}_questions.csv"'
    )
    return response


@login_required
def exam_export_json_view(request, exam_id):
    """
    Exports exam questions to JSON format.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    content = generate_exam_json(exam)
    response = HttpResponse(content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{exam.slug}_questions.json"'
    )
    return response


@login_required
def exam_print_paper_view(request, exam_id):
    """
    Renders clean, board-standard 2-column Question Paper layout for printing / PDF saving.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    questions = exam.questions.all().order_by("order", "id")

    # Group questions with Bengali numerals and metadata
    formatted_questions = []
    for idx, q in enumerate(questions, 1):
        formatted_questions.append(
            {
                "num_bn": to_bengali_numeral(idx),
                "num_en": idx,
                "q": q,
                "correct_bn": map_letter_to_bengali_option(q.correct_option),
            }
        )

    return render(
        request,
        "courses/backend/exam_print_paper.html",
        {
            "exam": exam,
            "questions": formatted_questions,
            "tenant": tenant,
            "show_answers": request.GET.get("answers") == "1",
        },
    )


# =====================================================================
# 🗂️ MCQ EXAM GROUP / MODEL TEST SERIES VIEWS
# =====================================================================


def exam_group_detail_view(request, group_slug):
    """
    Public landing and model test series dashboard for an ExamGroup.
    Displays custom thumbnail, syllabus, pricing, and all included subject exams.
    """
    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(group_slug)

    group_qs = ExamGroup.objects.prefetch_related("exams__questions").filter(slug__in=slug_variants)
    if tenant:
        group = group_qs.filter(tenant=tenant).first() or group_qs.first()
    else:
        group = group_qs.first()

    if not group:
        cleaned_target = slugify(clean_unquoted_slug(group_slug), allow_unicode=True)
        all_groups = ExamGroup.objects.filter(tenant=tenant) if tenant else ExamGroup.objects.all()
        for g in all_groups:
            if (
                slugify(g.slug, allow_unicode=True) == cleaned_target
                or slugify(g.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(g.slug) == clean_unquoted_slug(group_slug)
                or bangla_slugify(g.title) == clean_unquoted_slug(group_slug)
            ):
                group = g
                break

    if not group:
        raise Http404("No Exam Group matches the given query.")

    is_privileged = False
    if request.user.is_authenticated:
        is_privileged = (
            request.user.is_superuser
            or request.user.is_staff
            or (tenant and getattr(tenant, "owner", None) == request.user)
        )

    if not group.is_published and not is_privileged:
        raise Http404("এই মডেল টেস্ট গ্রুপটি বর্তমানে লাইভ নেই।")

    exams = list(group.exams.filter(is_published=True).prefetch_related("questions"))

    # Enrollment status
    is_enrolled = False
    attempts_map = {}
    if request.user.is_authenticated:
        if is_privileged:
            is_enrolled = True
        elif group.is_free:
            is_enrolled = ExamGroupEnrollment.objects.filter(
                tenant=tenant, user=request.user, group=group
            ).exists()
        else:
            is_enrolled = ExamGroupEnrollment.objects.filter(
                tenant=tenant, user=request.user, group=group, is_paid=True
            ).exists()

        # Find attempts for exams in this group
        user_attempts = ExamAttempt.objects.filter(exam__in=exams, student=request.user)
        for att in user_attempts:
            if att.exam_id not in attempts_map or att.submitted_at > attempts_map[att.exam_id].submitted_at:
                attempts_map[att.exam_id] = att

    # Attach attempt metadata to each exam
    exam_items = []
    for e in exams:
        att = attempts_map.get(e.id)
        exam_items.append({
            "exam": e,
            "attempt": att,
            "is_attempted": bool(att),
        })

    og_image_url, og_image_type = get_og_image_data_for_group(request, group, tenant)
    clean_canonical_url = f"{request.scheme}://{request.get_host()}/exams/groups/{urllib.parse.quote(group.slug)}/"

    return render(
        request,
        "courses/frontend/exam_group_detail.html",
        {
            "group": group,
            "exams": exams,
            "exam_items": exam_items,
            "is_enrolled": is_enrolled,
            "tenant": tenant,
            "is_privileged": is_privileged,
            "og_image_url": og_image_url,
            "og_image_type": og_image_type,
            "clean_canonical_url": clean_canonical_url,
        },
    )


def exam_group_enroll_view(request, group_slug):
    """
    Handles 1-click free enrollment or paid checkout for an ExamGroup.
    """
    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(group_slug)

    group_qs = ExamGroup.objects.prefetch_related("exams").filter(slug__in=slug_variants)
    if tenant:
        group = group_qs.filter(tenant=tenant).first() or group_qs.first()
    else:
        group = group_qs.first()

    if not group:
        cleaned_target = slugify(clean_unquoted_slug(group_slug), allow_unicode=True)
        all_groups = ExamGroup.objects.filter(tenant=tenant) if tenant else ExamGroup.objects.all()
        for g in all_groups:
            if (
                slugify(g.slug, allow_unicode=True) == cleaned_target
                or slugify(g.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(g.slug) == clean_unquoted_slug(group_slug)
                or bangla_slugify(g.title) == clean_unquoted_slug(group_slug)
            ):
                group = g
                break

    if not group:
        raise Http404("No Exam Group matches the given query.")

    if not request.user.is_authenticated:
        messages.info(request, "পরীক্ষায় এনরোল করতে অনুগ্রহ করে আগে প্রবেশ (Login) করুন বা নতুন অ্যাকাউন্ট তৈরি করুন।")
        return redirect(f"/login/?next=/exams/groups/{group.slug}/enroll/")

    # If Free Group
    if group.is_free:
        enrollment, _ = ExamGroupEnrollment.objects.get_or_create(
            tenant=tenant,
            user=request.user,
            group=group,
            defaults={"is_paid": True, "paid_amount": 0.00, "payment_method": "Free Enrollment"},
        )
        if not enrollment.is_paid:
            enrollment.is_paid = True
            enrollment.save()
        messages.success(request, f"🎉 অভিনন্দন! '{group.title}' গ্রুপে আপনি সফলভাবে যুক্ত হয়েছেন। এখন সব পরীক্ষা দিতে পারবেন।")
        return redirect(f"/exams/groups/{group.slug}/")

    # If Paid Group
    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "bKash Online Gateway").strip()
        transaction_id = request.POST.get("transaction_id", f"TRX-{uuid.uuid4().hex[:8].upper()}").strip()
        
        import secrets
        invoice_no = f"INV-GRP-{secrets.token_hex(4).upper()}"
        StudentInvoice.objects.create(
            tenant=tenant,
            student=request.user,
            invoice_no=invoice_no,
            item_title=f"মডেল টেস্ট সিরিজ: {group.title}",
            amount=group.effective_price,
            payment_method=payment_method,
            transaction_id=transaction_id,
            status="PAID",
        )

        enrollment, _ = ExamGroupEnrollment.objects.update_or_create(
            tenant=tenant,
            user=request.user,
            group=group,
            defaults={
                "is_paid": True,
                "paid_amount": group.effective_price,
                "payment_method": payment_method,
                "transaction_id": transaction_id,
            },
        )
        messages.success(request, f"🎉 অভিনন্দন! '{group.title}' সফলভাবে অ্যাক্টিভ হয়েছে। আপনি এখন এই গ্রুপের সব পরীক্ষায় অংশ নিতে পারবেন।")
        return redirect(f"/exams/groups/{group.slug}/")

    # GET request for paid group: render checkout screen
    return render(
        request,
        "courses/frontend/exam_group_checkout.html",
        {
            "group": group,
            "tenant": tenant,
        },
    )


# =====================================================================
# ⏱️ STUDENT LIVE MCQ EXAM ENGINE & EVALUATION
# =====================================================================


def exam_take_view(request, exam_slug):
    """
    Live real-time MCQ exam taking screen with live countdown timer.
    Also provides a public landing preview for unauthenticated visitors & social crawlers.
    """
    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(exam_slug)

    exam_qs = Exam.objects.prefetch_related("questions", "groups").filter(slug__in=slug_variants)
    if tenant:
        exam = exam_qs.filter(tenant=tenant).first() or exam_qs.first()
    else:
        exam = exam_qs.first()

    if not exam:
        cleaned_target = slugify(clean_unquoted_slug(exam_slug), allow_unicode=True)
        all_exams = Exam.objects.filter(tenant=tenant) if tenant else Exam.objects.all()
        for e in all_exams:
            if (
                slugify(e.slug, allow_unicode=True) == cleaned_target
                or slugify(e.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(e.slug) == clean_unquoted_slug(exam_slug)
                or bangla_slugify(e.title) == clean_unquoted_slug(exam_slug)
            ):
                exam = e
                break

    if not exam:
        raise Http404("No Exam matches the given query.")

    # Check publication status:
    # If not published, allow tenant owner, superuser or staff to preview
    is_privileged = False
    if request.user.is_authenticated:
        is_privileged = (
            request.user.is_superuser
            or request.user.is_staff
            or (tenant and getattr(tenant, "owner", None) == request.user)
        )
    if not exam.is_published and not is_privileged:
        raise Http404("এই পরীক্ষাটি বর্তমানে লাইভ নেই।")

    og_image_url, og_image_type = get_og_image_data_for_exam(request, exam, tenant)
    clean_canonical_url = f"{request.scheme}://{request.get_host()}/exams/{urllib.parse.quote(exam.slug)}/"

    questions = exam.questions.all().order_by("order", "id")

    # Check if this exam is part of a paid ExamGroup
    paid_groups = exam.groups.filter(is_free=False, is_published=True)
    paid_group = paid_groups.first() if paid_groups.exists() else None

    # If visitor is not logged in, show the Exam Landing / Preview card
    # so social crawlers (WhatsApp, Facebook) can parse OG tags and visitors can see details/pricing
    if not request.user.is_authenticated:
        return render(
            request,
            "courses/frontend/exam_preview.html",
            {
                "exam": exam,
                "questions_count": questions.count(),
                "tenant": tenant,
                "paid_group": paid_group,
                "og_image_url": og_image_url,
                "og_image_type": og_image_type,
                "clean_canonical_url": clean_canonical_url,
            },
        )

    # For authenticated students, check if this exam is restricted to an enrolled paid ExamGroup
    if paid_groups.exists() and not is_privileged:
        is_enrolled_in_group = ExamGroupEnrollment.objects.filter(
            tenant=tenant, user=request.user, group__in=paid_groups, is_paid=True
        ).exists()
        if not is_enrolled_in_group:
            target_group = paid_groups.first()
            messages.warning(
                request,
                f"🔒 এই পরীক্ষাটি '{target_group.title}' পেইড মডেল টেস্ট সিরিজের অন্তর্ভুক্ত। অংশ নিতে অনুগ্রহ করে সিরিজটিতে এনরোল করুন।"
            )
            return redirect(f"/exams/groups/{target_group.slug}/")

    if not questions.exists():
        messages.warning(
            request, "এই পরীক্ষায় এখনো কোনো প্রশ্ন যোগ করা হয়নি। অনুগ্রহ করে পরে চেষ্টা করুন।"
        )
        return redirect("dashboard")

    # Check if student already attempted
    previous_attempt = ExamAttempt.objects.filter(
        exam=exam, student=request.user
    ).first()

    return render(
        request,
        "courses/frontend/exam_take.html",
        {
            "exam": exam,
            "questions": questions,
            "previous_attempt": previous_attempt,
            "tenant": tenant,
            "og_image_url": og_image_url,
            "og_image_type": og_image_type,
            "clean_canonical_url": clean_canonical_url,
        },
    )


@login_required
def exam_submit_view(request, exam_slug):
    """
    Processes MCQ exam answers, computes scores with negative marks,
    creates ExamAttempt record, and syncs to StudentResult.
    """
    if request.method != "POST":
        return redirect(f"/exams/{exam_slug}/")

    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(exam_slug)
    exam_qs = Exam.objects.prefetch_related("questions").filter(slug__in=slug_variants)
    if tenant:
        exam = exam_qs.filter(tenant=tenant).first() or exam_qs.first()
    else:
        exam = exam_qs.first()

    if not exam:
        cleaned_target = slugify(clean_unquoted_slug(exam_slug), allow_unicode=True)
        all_exams = Exam.objects.filter(tenant=tenant) if tenant else Exam.objects.all()
        for e in all_exams:
            if (
                slugify(e.slug, allow_unicode=True) == cleaned_target
                or slugify(e.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(e.slug) == clean_unquoted_slug(exam_slug)
                or bangla_slugify(e.title) == clean_unquoted_slug(exam_slug)
            ):
                exam = e
                break

    if not exam:
        raise Http404("No Exam matches the given query.")

    questions = exam.questions.all()

    answers = {}
    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    total_score = 0.0
    total_marks = 0.0

    time_taken_seconds = int(request.POST.get("time_taken_seconds", 0) or 0)

    for q in questions:
        q_mark = float(q.marks)
        total_marks += q_mark
        user_choice = request.POST.get(f"q_{q.id}", "").strip().upper()
        answers[str(q.id)] = user_choice

        if not user_choice:
            skipped_count += 1
        elif user_choice == q.correct_option:
            correct_count += 1
            total_score += q_mark
        else:
            wrong_count += 1
            neg = float(exam.negative_mark_per_question)
            total_score -= neg

    total_score = max(0.0, round(total_score, 2))
    percent = (total_score / total_marks * 100) if total_marks > 0 else 0.0
    is_passed = percent >= float(exam.pass_mark)

    # Save ExamAttempt
    attempt = ExamAttempt.objects.create(
        tenant=tenant,
        exam=exam,
        student=request.user,
        score=total_score,
        total_marks=total_marks,
        correct_count=correct_count,
        wrong_count=wrong_count,
        skipped_count=skipped_count,
        is_passed=is_passed,
        answers_json=answers,
        time_taken_seconds=time_taken_seconds,
    )

    # Sync into StudentResult for Student Dashboard Results tab
    grade = (
        "A+"
        if percent >= 80
        else (
            "A"
            if percent >= 70
            else (
                "A-"
                if percent >= 60
                else ("B" if percent >= 50 else ("C" if percent >= 40 else "F"))
            )
        )
    )
    StudentResult.objects.create(
        tenant=tenant,
        student=request.user,
        exam_title=exam.title,
        course_name=exam.course.title if exam.course else "অনলাইন মডেল টেস্ট",
        subject="MCQ পরীক্ষা",
        total_marks=total_marks,
        obtained_marks=total_score,
        grade=grade,
        remarks=f"সঠিক: {correct_count}টি, ভুল: {wrong_count}টি, উত্তরহীন: {skipped_count}টি। ({'পাস' if is_passed else 'ফেল'})",
    )

    messages.success(
        request,
        f"পরীক্ষা সফলভাবে সম্পন্ন হয়েছে! আপনার প্রাপ্ত নম্বর: {total_score}/{total_marks}",
    )
    return redirect(f"/exams/{exam.slug}/result/{attempt.id}/")


@login_required
def exam_result_view(request, exam_slug, attempt_id):
    """
    Scorecard, Performance Analysis, and Question Solution Sheet with Explanations.
    """
    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(exam_slug)
    exam_qs = Exam.objects.prefetch_related("questions").filter(slug__in=slug_variants)
    if tenant:
        exam = exam_qs.filter(tenant=tenant).first() or exam_qs.first()
    else:
        exam = exam_qs.first()

    if not exam:
        cleaned_target = slugify(clean_unquoted_slug(exam_slug), allow_unicode=True)
        all_exams = Exam.objects.filter(tenant=tenant) if tenant else Exam.objects.all()
        for e in all_exams:
            if (
                slugify(e.slug, allow_unicode=True) == cleaned_target
                or slugify(e.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(e.slug) == clean_unquoted_slug(exam_slug)
                or bangla_slugify(e.title) == clean_unquoted_slug(exam_slug)
            ):
                exam = e
                break

    if not exam:
        raise Http404("No Exam matches the given query.")

    attempt = get_object_or_404(
        ExamAttempt, id=attempt_id, exam=exam, student=request.user
    )

    questions = exam.questions.all().order_by("order", "id")
    student_answers = attempt.answers_json or {}

    # Build detailed question review breakdown
    question_reviews = []
    for q in questions:
        user_choice = student_answers.get(str(q.id), "")
        is_correct = user_choice == q.correct_option
        is_skipped = not bool(user_choice)
        is_wrong = bool(user_choice) and not is_correct

        question_reviews.append(
            {
                "question": q,
                "user_choice": user_choice,
                "is_correct": is_correct,
                "is_skipped": is_skipped,
                "is_wrong": is_wrong,
            }
        )

    merit_list = get_exam_merit_list(exam)
    my_rank = next(
        (
            item
            for item in merit_list
            if item["attempt"].id == attempt.id or item["student"].id == request.user.id
        ),
        None,
    )

    return render(
        request,
        "courses/frontend/exam_result.html",
        {
            "exam": exam,
            "attempt": attempt,
            "question_reviews": question_reviews,
            "tenant": tenant,
            "merit_list": merit_list[:30],
            "total_candidates": len(merit_list),
            "my_rank": my_rank,
        },
    )


# =====================================================================
# 🏆 MCQ MERIT LIST & LEADERBOARD SYSTEM (Ranking & PDF Export)
# =====================================================================

def get_exam_merit_list(exam):
    """
    Computes a sorted merit list for an exam.
    Criteria:
    1. Highest score (-score)
    2. Faster completion time (time_taken_seconds ASC)
    3. Earlier submission timestamp (submitted_at ASC)

    Only the student's best attempt is counted so a single student doesn't duplicate ranks.
    """
    attempts = (
        ExamAttempt.objects.filter(exam=exam)
        .select_related("student")
        .order_by("-score", "time_taken_seconds", "submitted_at")
    )

    student_best_attempts = {}
    for att in attempts:
        std_id = att.student_id
        if std_id not in student_best_attempts:
            student_best_attempts[std_id] = att

    sorted_attempts = sorted(
        student_best_attempts.values(),
        key=lambda x: (-float(x.score), x.time_taken_seconds, x.submitted_at),
    )

    merit_list = []
    for rank, att in enumerate(sorted_attempts, start=1):
        minutes = att.time_taken_seconds // 60
        seconds = att.time_taken_seconds % 60
        time_formatted = (
            f"{to_bengali_numeral(minutes)}মি. {to_bengali_numeral(seconds)}সে."
            if minutes > 0
            else f"{to_bengali_numeral(seconds)} সেকেন্ড"
        )
        rank_bn = to_bengali_numeral(rank)
        badge = (
            "🥇"
            if rank == 1
            else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank_bn}"))
        )

        std_name = att.student.get_full_name() or att.student.first_name
        if not std_name or not std_name.strip():
            std_name = att.student.email.split("@")[0]

        merit_list.append(
            {
                "rank": rank,
                "rank_bn": rank_bn,
                "badge": badge,
                "attempt": att,
                "student": att.student,
                "student_name": std_name,
                "student_email": att.student.email,
                "score": att.score,
                "total_marks": att.total_marks,
                "percentage": att.percentage,
                "correct_count": att.correct_count,
                "wrong_count": att.wrong_count,
                "skipped_count": att.skipped_count,
                "is_passed": att.is_passed,
                "time_taken_seconds": att.time_taken_seconds,
                "time_formatted": time_formatted,
                "submitted_at": att.submitted_at,
            }
        )

    return merit_list


def exam_merit_list_view(request, exam_slug):
    """
    Public / Student Live Merit List & Leaderboard for an exam.
    """
    tenant = getattr(request, "tenant", None)
    slug_variants = get_slug_variants(exam_slug)
    exam_qs = Exam.objects.prefetch_related("questions").filter(slug__in=slug_variants)
    if tenant:
        exam = exam_qs.filter(tenant=tenant).first() or exam_qs.first()
    else:
        exam = exam_qs.first()

    if not exam:
        cleaned_target = slugify(clean_unquoted_slug(exam_slug), allow_unicode=True)
        all_exams = Exam.objects.filter(tenant=tenant) if tenant else Exam.objects.all()
        for e in all_exams:
            if (
                slugify(e.slug, allow_unicode=True) == cleaned_target
                or slugify(e.title, allow_unicode=True) == cleaned_target
                or bangla_slugify(e.slug) == clean_unquoted_slug(exam_slug)
                or bangla_slugify(e.title) == clean_unquoted_slug(exam_slug)
            ):
                exam = e
                break

    if not exam:
        raise Http404("No Exam matches the given query.")

    merit_list = get_exam_merit_list(exam)

    my_rank = None
    if request.user.is_authenticated:
        my_rank = next(
            (item for item in merit_list if item["student"].id == request.user.id),
            None,
        )

    return render(
        request,
        "courses/frontend/exam_merit_list.html",
        {
            "exam": exam,
            "merit_list": merit_list,
            "total_candidates": len(merit_list),
            "my_rank": my_rank,
            "tenant": tenant,
        },
    )


def admin_exam_merit_list_view(request, exam_id):
    """
    Instructor / Tenant Admin detailed Merit List dashboard with analytics and download actions.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    merit_list = get_exam_merit_list(exam)

    total_candidates = len(merit_list)
    scores = [float(item["score"]) for item in merit_list]
    highest_score = max(scores) if scores else 0.0
    avg_score = (
        round(sum(scores) / total_candidates, 2) if total_candidates > 0 else 0.0
    )
    passed_count = sum(1 for item in merit_list if item["is_passed"])
    pass_rate = (
        round((passed_count / total_candidates) * 100, 1)
        if total_candidates > 0
        else 0.0
    )

    return render(
        request,
        "courses/backend/exam_merit_list_admin.html",
        {
            "exam": exam,
            "tenant": tenant,
            "merit_list": merit_list,
            "total_candidates": total_candidates,
            "highest_score": highest_score,
            "avg_score": avg_score,
            "passed_count": passed_count,
            "pass_rate": pass_rate,
        },
    )


def admin_exam_merit_list_print_view(request, exam_id):
    """
    Board-Standard, Institutional Printable / PDF Merit List sheet.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    tenant = request.tenant
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), id=exam_id)
    merit_list = get_exam_merit_list(exam)

    total_candidates = len(merit_list)
    scores = [float(item["score"]) for item in merit_list]
    highest_score = max(scores) if scores else 0.0
    avg_score = (
        round(sum(scores) / total_candidates, 2) if total_candidates > 0 else 0.0
    )
    passed_count = sum(1 for item in merit_list if item["is_passed"])
    pass_rate = (
        round((passed_count / total_candidates) * 100, 1)
        if total_candidates > 0
        else 0.0
    )

    return render(
        request,
        "courses/backend/exam_merit_list_print.html",
        {
            "exam": exam,
            "tenant": tenant,
            "merit_list": merit_list,
            "total_candidates": total_candidates,
            "highest_score": highest_score,
            "avg_score": avg_score,
            "passed_count": passed_count,
            "pass_rate": pass_rate,
        },
    )


def admin_exam_merit_list_csv_view(request, exam_id):
    """
    Exports full Merit List to CSV for Excel analysis with UTF-8 BOM.
    """
    if not _check_tenant_admin(request):
        return HttpResponseForbidden("Admin or Instructor permission required.")

    import csv

    exam = get_object_or_404(Exam, id=exam_id)
    merit_list = get_exam_merit_list(exam)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    safe_title = slugify(exam.title, allow_unicode=True) or f"exam_{exam.id}"
    response["Content-Disposition"] = (
        f'attachment; filename="merit_list_{safe_title}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "মেধা স্থান (Rank)",
            "শিক্ষার্থীর নাম (Student Name)",
            "কলেজ / প্রতিষ্ঠান (College / Institution)",
            "সেশন / ব্যাচ (Session / Batch)",
            "প্রাপ্ত নম্বর (Obtained Score)",
            "মোট নম্বর (Total Marks)",
            "শতকরা হার (Percentage)",
            "সঠিক (Correct)",
            "ভুল (Wrong)",
            "উত্তরহীন (Skipped)",
            "ব্যয়িত সময় (Time Taken)",
            "ফলাফল (Status)",
            "জমা দেওয়ার তারিখ ও সময় (Submitted At)",
        ]
    )

    for item in merit_list:
        writer.writerow(
            [
                item["rank"],
                item["student_name"],
                item["institution"] or "—",
                item["batch"] or "—",
                item["score"],
                item["total_marks"],
                f'{item["percentage"]}%',
                item["correct_count"],
                item["wrong_count"],
                item["skipped_count"],
                item["time_formatted"],
                "উত্তীর্ণ" if item["is_passed"] else "অনুত্তীর্ণ",
                item["submitted_at"].strftime("%d/%m/%Y %I:%M %p") if item.get("submitted_at") else "—",
            ]
        )

    return response
