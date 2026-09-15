from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from apps.users.models import TenantMembership



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
            price = request.POST.get("price", "0") or "0"
            is_free = request.POST.get("is_free") == "on" or request.POST.get("is_free") == "true"
            status = request.POST.get("status", Course.Status.PUBLISHED)
            
            if title:
                base_slug = slugify(title) or f"course-{int(timezone.now().timestamp())}"
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

                messages.success(request, f"কোর্স '{title}' সফলভাবে তৈরি হয়েছে! এখন কারিকুলাম ও লেসন যুক্ত করুন।")
                return redirect(reverse("courses:course_curriculum", kwargs={"course_id": course.id}))

        # 2. Update Course
        elif action == "update_course":
            course_id = request.POST.get("course_id")
            course = get_object_or_404(Course, id=course_id)
            course.title = request.POST.get("title", course.title).strip()
            course.description = request.POST.get("description", course.description).strip()
            is_free = request.POST.get("is_free") == "on" or request.POST.get("is_free") == "true"
            course.is_free = is_free
            course.price = 0.00 if is_free else (request.POST.get("price", course.price) or 0)
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
    active_tab = request.GET.get("tab") or request.POST.get("active_tab") or "newsfeed"

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
                messages.success(request, "আপনার পোস্টটি সফলভাবে কমিউনিটি ফিডে প্রকাশিত হয়েছে!")
            return redirect(f"{request.path}?tab=newsfeed")

        # 2. Feed: Like Post
        elif action == "like_feed_post":
            post_id = request.POST.get("post_id")
            post = FeedPost.objects.filter(id=post_id).first()
            if post:
                like, created = FeedLike.objects.get_or_create(tenant=tenant, post=post, user=request.user)
                if not created:
                    like.delete()
            return redirect(f"{request.path}?tab=newsfeed#post-{post_id}")

        # 3. Feed: Comment on Post
        elif action == "comment_feed_post":
            post_id = request.POST.get("post_id")
            comment_text = request.POST.get("comment_text", "").strip() or request.POST.get("content", "").strip()
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
                messages.success(request, "সাপোর্ট মেসেজ পাঠানো হয়েছে! মেন্টর টিম দ্রুত উত্তর দেবে।")
                return redirect(f"{request.path}?tab=support&thread_id={thread.id}")
            return redirect(f"{request.path}?tab=support")

        elif action == "send_support_message":
            thread_id = request.POST.get("thread_id")
            message_text = request.POST.get("message", "").strip()
            thread = SupportThread.objects.filter(id=thread_id, student=request.user).first()
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
                ClubMembership.objects.get_or_create(tenant=tenant, club=club, user=request.user)
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
                like, created = ClubLike.objects.get_or_create(tenant=tenant, post=club_post, user=request.user)
                if not created:
                    like.delete()
                return redirect(f"{request.path}?tab=clubs&club_slug={club_post.club.slug}#post-{club_post.id}")
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
                return redirect(f"{request.path}?tab=clubs&club_slug={club_post.club.slug}#post-{club_post.id}")
            return redirect(f"{request.path}?tab=clubs")

        # 10. Direct 1-Click Enroll Course
        elif action == "enroll_course":
            course_id = request.POST.get("course_id")
            course = Course.objects.filter(id=course_id, status=Course.Status.PUBLISHED).first()
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
                messages.success(request, f"অভিনন্দন! আপনি '{course.title}' কোর্সে সফলভাবে এনরোল করেছেন।")
                return redirect(f"{request.path}?tab=my_courses")

        # 11. Direct 1-Click Order Book
        elif action == "order_book":
            book_id = request.POST.get("book_id")
            address = request.POST.get("address", "").strip() or request.POST.get("shipping_address", "").strip()
            phone = request.POST.get("phone", "").strip() or request.POST.get("phone_number", "").strip()
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
                inv_no = f"INV-BOOK-{timezone.now().year}-{secrets.token_hex(4).upper()}"
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
                messages.success(request, f"আপনার '{book.title}' বইয়ের অর্ডারটি সফলভাবে গ্রহণ করা হয়েছে! ট্র্যাকিং নিচে দেখতে পারেন।")
                return redirect(f"{request.path}?tab=orders")

    # -------------------------------------------------------------
    # DATA AGGREGATION FOR ALL 10 TABS
    # -------------------------------------------------------------
    # Tab 1: Community News Feed
    feed_category = request.GET.get("feed_cat")
    feed_posts = FeedPost.objects.all().select_related("author").prefetch_related("likes", "comments__author").order_by("-created_at")
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

        enrolled_courses_data.append({
            "course": course,
            "progress": progress,
            "resume_lesson": resume_lesson,
            "is_completed": progress["percent"] == 100 and progress["total_lessons"] > 0,
            "enrolled_at": enrollment.enrolled_at,
        })

    total_enrolled = len(enrolled_courses_data)
    completed_courses_count = sum(1 for item in enrolled_courses_data if item["is_completed"])
    total_lessons_completed = sum(item["progress"]["completed_count"] for item in enrolled_courses_data)

    # Tab 3: Class Routine
    routines = ClassRoutine.objects.filter(is_active=True).select_related("course").order_by("day", "start_time")

    # Tab 4: Exam & Academic Results
    results = StudentResult.objects.filter(student=request.user).order_by("-published_date", "-id")

    # Tab 5: Live Support Threads & Messages
    support_threads = SupportThread.objects.filter(student=request.user).prefetch_related("messages__sender").order_by("-updated_at")
    selected_thread_id = request.GET.get("thread_id")
    selected_thread = None
    if selected_thread_id:
        selected_thread = support_threads.filter(id=selected_thread_id).first()
    if not selected_thread:
        selected_thread = support_threads.first()

    # Tab 6: Invoices & Receipts
    invoices = StudentInvoice.objects.filter(student=request.user).order_by("-paid_at")

    # Tab 7: Book Orders
    orders = BookOrder.objects.filter(student=request.user).select_related("book").order_by("-created_at")

    # Tab 8: Study Clubs
    clubs = StudentClub.objects.filter(is_active=True).prefetch_related("memberships", "posts__author", "posts__likes", "posts__comments__author")
    user_joined_club_ids = set(
        ClubMembership.objects.filter(user=request.user).values_list("club_id", flat=True)
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
    available_courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("instructor")
    available_books = Book.objects.filter(in_stock=True).order_by("-is_featured", "-created_at")
    available_exams = Exam.objects.filter(is_published=True).prefetch_related("questions", "attempts").order_by("-created_at")

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
            "total_lessons_completed": total_lessons_completed,
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
        books = books.filter(title__icontains=search_query) | books.filter(author__icontains=search_query)

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
    book = get_object_or_404(Book, slug=slug)
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
        resources = resources.filter(title__icontains=search_query) | resources.filter(description__icontains=search_query)

    # Distinct categories for tab filters
    categories = FreeResource.objects.filter(is_published=True).values_list("category", flat=True).distinct()

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
    resource = get_object_or_404(FreeResource, slug=slug, is_published=True)
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
        posts = posts.filter(title__icontains=search_query) | posts.filter(content__icontains=search_query)

    categories = BlogPost.objects.filter(is_published=True).values_list("category", flat=True).distinct()
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
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
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
    membership = TenantMembership.objects.unscoped().filter(tenant=tenant, user=request.user).first()
    return bool(membership and membership.role in [TenantMembership.Role.ADMIN, TenantMembership.Role.INSTRUCTOR])


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
            resource_type = request.POST.get("resource_type", FreeResource.ResourceType.PDF_NOTE)
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
    course = get_object_or_404(Course.objects.prefetch_related("modules__lessons"), id=course_id)

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
            module.description = request.POST.get("description", module.description).strip()
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
            content = request.POST.get("content_text", "").strip() or request.POST.get("content", "").strip()
            duration_minutes = int(request.POST.get("duration_minutes", 0) or 0)
            is_preview = request.POST.get("is_preview") == "on" or request.POST.get("is_preview") == "true"
            order = int(request.POST.get("order", 0) or 0)
            if not order:
                order = module.lessons.count() + 1

            if title:
                base_slug = slugify(title) or f"lesson-{int(timezone.now().timestamp())}"
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
            lesson.content = request.POST.get("content_text", lesson.content).strip() or request.POST.get("content", lesson.content).strip()
            duration_minutes = int(request.POST.get("duration_minutes", lesson.duration_minutes) or lesson.duration_minutes)
            lesson.duration_minutes = duration_minutes
            lesson.is_preview = request.POST.get("is_preview") == "on" or request.POST.get("is_preview") == "true"
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

        return redirect(reverse("courses:course_curriculum", kwargs={"course_id": course.id}))

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
            negative_mark = float(request.POST.get("negative_mark_per_question", 0.25) or 0.25)
            is_published = request.POST.get("is_published") == "on" or request.POST.get("is_published") == "true"

            course = Course.objects.filter(id=course_id).first() if course_id else None

            if title:
                base_slug = slugify(title) or f"exam-{int(timezone.now().timestamp())}"
                slug = base_slug
                counter = 1
                while Exam.objects.filter(slug=slug).exists():
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
                    is_published=is_published,
                )
                messages.success(request, f"পরীক্ষা '{title}' তৈরি হয়েছে! এখন প্রশ্ন যুক্ত করুন।")
                return redirect(reverse("courses:exam_builder", kwargs={"exam_id": exam.id}))

        # 2. Update Exam
        elif action == "update_exam":
            exam_id = request.POST.get("exam_id")
            exam = get_object_or_404(Exam, id=exam_id)
            exam.title = request.POST.get("title", exam.title).strip()
            exam.description = request.POST.get("description", exam.description).strip()
            course_id = request.POST.get("course_id")
            exam.course = Course.objects.filter(id=course_id).first() if course_id else None
            exam.duration_minutes = int(request.POST.get("duration_minutes", exam.duration_minutes) or exam.duration_minutes)
            exam.pass_mark = float(request.POST.get("pass_mark", exam.pass_mark) or exam.pass_mark)
            exam.negative_mark_per_question = float(request.POST.get("negative_mark_per_question", exam.negative_mark_per_question) or exam.negative_mark_per_question)
            exam.is_published = request.POST.get("is_published") == "on" or request.POST.get("is_published") == "true"
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

    exams = Exam.objects.all().prefetch_related("questions", "attempts", "course")
    total_questions = sum(e.questions.count() for e in exams)
    courses = Course.objects.all()
    return render(
        request,
        "courses/backend/manage_exams.html",
        {
            "exams": exams,
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
    exam = get_object_or_404(Exam.objects.prefetch_related("questions", "attempts__student"), id=exam_id)

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
            q.correct_option = request.POST.get("correct_option", q.correct_option).upper()
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


# =====================================================================
# ⏱️ STUDENT LIVE MCQ EXAM ENGINE & EVALUATION
# =====================================================================

@login_required
def exam_take_view(request, exam_slug):
    """
    Live real-time MCQ exam taking screen with live countdown timer.
    """
    tenant = getattr(request, "tenant", None)
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), slug=exam_slug, is_published=True)
    questions = exam.questions.all().order_by("order", "id")

    if not questions.exists():
        messages.warning(request, "এই পরীক্ষায় এখনো কোনো প্রশ্ন যোগ করা হয়নি। অনুগ্রহ করে পরে চেষ্টা করুন।")
        return redirect("dashboard")

    # Check if student already attempted
    previous_attempt = ExamAttempt.objects.filter(exam=exam, student=request.user).first()

    return render(
        request,
        "courses/frontend/exam_take.html",
        {
            "exam": exam,
            "questions": questions,
            "previous_attempt": previous_attempt,
            "tenant": tenant,
        },
    )


@login_required
def exam_submit_view(request, exam_slug):
    """
    Processes MCQ exam answers, computes scores with negative marks,
    creates ExamAttempt record, and syncs to StudentResult.
    """
    if request.method != "POST":
        return redirect(reverse("courses:exam_take", kwargs={"exam_slug": exam_slug}))

    tenant = getattr(request, "tenant", None)
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), slug=exam_slug)
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
    grade = "A+" if percent >= 80 else ("A" if percent >= 70 else ("A-" if percent >= 60 else ("B" if percent >= 50 else ("C" if percent >= 40 else "F"))))
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

    messages.success(request, f"পরীক্ষা সফলভাবে সম্পন্ন হয়েছে! আপনার প্রাপ্ত নম্বর: {total_score}/{total_marks}")
    return redirect(reverse("courses:exam_result", kwargs={"exam_slug": exam.slug, "attempt_id": attempt.id}))


@login_required
def exam_result_view(request, exam_slug, attempt_id):
    """
    Scorecard, Performance Analysis, and Question Solution Sheet with Explanations.
    """
    tenant = getattr(request, "tenant", None)
    exam = get_object_or_404(Exam.objects.prefetch_related("questions"), slug=exam_slug)
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, exam=exam, student=request.user)

    questions = exam.questions.all().order_by("order", "id")
    student_answers = attempt.answers_json or {}

    # Build detailed question review breakdown
    question_reviews = []
    for q in questions:
        user_choice = student_answers.get(str(q.id), "")
        is_correct = (user_choice == q.correct_option)
        is_skipped = not bool(user_choice)
        is_wrong = bool(user_choice) and not is_correct

        question_reviews.append({
            "question": q,
            "user_choice": user_choice,
            "is_correct": is_correct,
            "is_skipped": is_skipped,
            "is_wrong": is_wrong,
        })

    return render(
        request,
        "courses/frontend/exam_result.html",
        {
            "exam": exam,
            "attempt": attempt,
            "question_reviews": question_reviews,
            "tenant": tenant,
        },
    )



