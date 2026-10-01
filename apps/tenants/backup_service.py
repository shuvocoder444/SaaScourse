"""
Multi-Tenant Academy Backup & Disaster Recovery Service.
Handles tenant-isolated data export and structured JSON backup & restore.
Strictly ensures multi-tenant isolation — only data matching the target tenant is exported or modified.
"""

import json
from decimal import Decimal
from django.utils import timezone
from django.utils.text import slugify
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from apps.tenants.models import Tenant
from apps.courses.models import (
    Course,
    Module,
    Lesson,
    Exam,
    ExamQuestion,
    ClassRoutine,
    Book,
    FreeResource,
    BlogPost,
    StudentClub,
    FinancialLedger,
    StudentInvoice,
)


def export_tenant_backup_data(tenant: Tenant) -> dict:
    """
    Serializes all data owned by the given tenant into a portable dictionary.
    """
    # 1. Tenant metadata & Branding
    tenant_info = {
        "name": tenant.name,
        "slug": tenant.slug,
        "header_style": tenant.header_style,
        "footer_style": tenant.footer_style,
        "landing_template": tenant.landing_template,
        "custom_domain": tenant.custom_domain,
        "branding": tenant.branding or {},
    }

    # 2. Courses, Modules & Lessons
    courses = []
    for course in Course.objects.filter(tenant=tenant).prefetch_related("modules__lessons"):
        modules_data = []
        for mod in course.modules.all().order_by("order"):
            lessons_data = []
            for les in mod.lessons.all().order_by("order"):
                lessons_data.append({
                    "title": les.title,
                    "slug": les.slug,
                    "content_type": les.content_type,
                    "order": les.order,
                    "video_url": les.video_url,
                    "content": les.content,
                    "duration_minutes": les.duration_minutes,
                    "is_preview": les.is_preview,
                })
            modules_data.append({
                "title": mod.title,
                "order": mod.order,
                "description": mod.description,
                "lessons": lessons_data,
            })

        courses.append({
            "title": course.title,
            "slug": course.slug,
            "description": course.description,
            "price": str(course.price),
            "is_free": course.is_free,
            "intro_video_url": course.intro_video_url,
            "status": course.status,
            "modules": modules_data,
        })

    # 3. Exams & MCQ Questions
    exams = []
    for exam in Exam.objects.filter(tenant=tenant).prefetch_related("questions"):
        questions_data = []
        for q in exam.questions.all().order_by("order"):
            questions_data.append({
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "correct_option": q.correct_option,
                "explanation": q.explanation,
                "marks": str(q.marks),
                "order": q.order,
            })
        exams.append({
            "title": exam.title,
            "slug": exam.slug,
            "description": exam.description,
            "duration_minutes": exam.duration_minutes,
            "pass_mark": str(exam.pass_mark),
            "negative_mark_per_question": str(exam.negative_mark_per_question),
            "total_marks": str(exam.total_marks),
            "is_published": exam.is_published,
            "course_slug": exam.course.slug if exam.course else None,
            "questions": questions_data,
        })

    # 4. Class Routine
    routines = []
    for r in ClassRoutine.objects.filter(tenant=tenant).select_related("course"):
        routines.append({
            "subject": r.subject,
            "mentor_name": r.mentor_name,
            "day": r.day,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "live_url": r.live_url,
            "is_active": r.is_active,
            "course_slug": r.course.slug if r.course else None,
        })

    # 5. Physical Books
    books = []
    for b in Book.objects.filter(tenant=tenant):
        books.append({
            "title": b.title,
            "subtitle": b.subtitle,
            "slug": b.slug,
            "author": b.author,
            "description": b.description,
            "price": str(b.price),
            "discount_price": str(b.discount_price) if b.discount_price else None,
            "edition": b.edition,
            "pages": b.pages,
            "in_stock": b.in_stock,
            "preview_pdf_url": b.preview_pdf_url,
            "buy_url": b.buy_url,
            "is_featured": b.is_featured,
        })

    # 6. Free Resources
    resources = []
    for res in FreeResource.objects.filter(tenant=tenant):
        resources.append({
            "title": res.title,
            "slug": res.slug,
            "resource_type": res.resource_type,
            "category": res.category,
            "description": res.description,
            "file_url": res.file_url,
            "video_url": res.video_url,
            "download_count": res.download_count,
            "is_published": res.is_published,
        })

    # 7. Blog Posts
    blog_posts = []
    for bp in BlogPost.objects.filter(tenant=tenant):
        blog_posts.append({
            "title": bp.title,
            "slug": bp.slug,
            "author_name": bp.author_name,
            "category": bp.category,
            "excerpt": bp.excerpt,
            "content": bp.content,
            "is_published": bp.is_published,
        })

    # 8. Study Clubs
    clubs = []
    for sc in StudentClub.objects.filter(tenant=tenant):
        clubs.append({
            "title": sc.title,
            "slug": sc.slug,
            "description": sc.description,
            "category": sc.category,
            "icon": sc.icon,
            "is_active": sc.is_active,
        })

    # 9. Financial Ledgers
    ledgers = []
    for fl in FinancialLedger.objects.filter(tenant=tenant):
        ledgers.append({
            "title": fl.title,
            "transaction_type": fl.transaction_type,
            "category": fl.category,
            "amount": str(fl.amount),
            "payment_method": fl.payment_method,
            "reference_no": fl.reference_no,
            "notes": fl.notes,
            "transaction_date": fl.transaction_date.isoformat() if fl.transaction_date else None,
        })

    # Compile Full Backup Package
    backup_data = {
        "version": "1.0",
        "exported_at": timezone.now().isoformat(),
        "tenant": tenant_info,
        "data": {
            "courses": courses,
            "exams": exams,
            "routines": routines,
            "books": books,
            "resources": resources,
            "blog_posts": blog_posts,
            "clubs": clubs,
            "financial_ledgers": ledgers,
        },
        "stats": {
            "total_courses": len(courses),
            "total_exams": len(exams),
            "total_books": len(books),
            "total_routines": len(routines),
            "total_resources": len(resources),
            "total_blog_posts": len(blog_posts),
        }
    }

    return backup_data


def restore_tenant_backup_data(tenant: Tenant, backup_payload: dict, restore_mode: str = "merge") -> dict:
    """
    Restores or imports academy data from a backup dictionary into the given tenant.
    Guarantees strict tenant isolation by always binding models to `tenant=tenant`.
    """
    data = backup_payload.get("data", {})
    tenant_meta = backup_payload.get("tenant", {})
    summary = {
        "courses_restored": 0,
        "lessons_restored": 0,
        "exams_restored": 0,
        "questions_restored": 0,
        "routines_restored": 0,
        "books_restored": 0,
        "resources_restored": 0,
        "posts_restored": 0,
    }

    with transaction.atomic():
        # 1. Update Tenant Branding / Styles if provided
        if tenant_meta:
            if "branding" in tenant_meta and isinstance(tenant_meta["branding"], dict):
                current_branding = tenant.branding or {}
                current_branding.update(tenant_meta["branding"])
                tenant.branding = current_branding
            if tenant_meta.get("header_style"):
                tenant.header_style = tenant_meta["header_style"]
            if tenant_meta.get("footer_style"):
                tenant.footer_style = tenant_meta["footer_style"]
            if tenant_meta.get("landing_template"):
                tenant.landing_template = tenant_meta["landing_template"]
            tenant.save()

        # 2. Courses, Modules, Lessons
        for c_data in data.get("courses", []):
            c_slug = c_data.get("slug") or slugify(c_data.get("title", "course"))
            course, _ = Course.objects.update_or_create(
                tenant=tenant,
                slug=c_slug,
                defaults={
                    "title": c_data["title"],
                    "description": c_data.get("description", ""),
                    "price": Decimal(c_data.get("price", "0")),
                    "is_free": c_data.get("is_free", False),
                    "intro_video_url": c_data.get("intro_video_url", ""),
                    "status": c_data.get("status", Course.Status.PUBLISHED),
                    "instructor": tenant.owner,
                }
            )
            summary["courses_restored"] += 1

            # Modules
            for mod_data in c_data.get("modules", []):
                mod_order = mod_data.get("order", 0)
                module, _ = Module.objects.update_or_create(
                    tenant=tenant,
                    course=course,
                    order=mod_order,
                    defaults={
                        "title": mod_data.get("title", f"Module {mod_order}"),
                        "description": mod_data.get("description", ""),
                    }
                )
                # Lessons
                for les_data in mod_data.get("lessons", []):
                    les_order = les_data.get("order", 0)
                    les_slug = les_data.get("slug") or slugify(les_data.get("title", f"lesson-{les_order}"))
                    Lesson.objects.update_or_create(
                        tenant=tenant,
                        module=module,
                        order=les_order,
                        defaults={
                            "title": les_data.get("title", f"Lesson {les_order}"),
                            "slug": les_slug,
                            "content_type": les_data.get("content_type", Lesson.ContentType.VIDEO),
                            "video_url": les_data.get("video_url", ""),
                            "content": les_data.get("content", ""),
                            "duration_minutes": les_data.get("duration_minutes", 10),
                            "is_preview": les_data.get("is_preview", False),
                        }
                    )
                    summary["lessons_restored"] += 1

        # 3. Exams & MCQ Questions
        for e_data in data.get("exams", []):
            exam_slug = e_data.get("slug") or slugify(e_data.get("title", "exam"))
            exam_course = None
            if e_data.get("course_slug"):
                exam_course = Course.objects.filter(tenant=tenant, slug=e_data["course_slug"]).first()

            exam, _ = Exam.objects.update_or_create(
                tenant=tenant,
                slug=exam_slug,
                defaults={
                    "title": e_data["title"],
                    "description": e_data.get("description", ""),
                    "duration_minutes": e_data.get("duration_minutes", 30),
                    "pass_mark": Decimal(str(e_data.get("pass_mark", 40.0))),
                    "negative_mark_per_question": Decimal(str(e_data.get("negative_mark_per_question", 0.25))),
                    "total_marks": Decimal(str(e_data.get("total_marks", 100.0))),
                    "is_published": e_data.get("is_published", True),
                    "course": exam_course,
                }
            )
            summary["exams_restored"] += 1

            for q_data in e_data.get("questions", []):
                ExamQuestion.objects.update_or_create(
                    tenant=tenant,
                    exam=exam,
                    order=q_data.get("order", 1),
                    defaults={
                        "question_text": q_data.get("question_text", ""),
                        "option_a": q_data.get("option_a", ""),
                        "option_b": q_data.get("option_b", ""),
                        "option_c": q_data.get("option_c", ""),
                        "option_d": q_data.get("option_d", ""),
                        "correct_option": q_data.get("correct_option") or q_data.get("correct_answer", "A"),
                        "explanation": q_data.get("explanation", ""),
                        "marks": Decimal(str(q_data.get("marks", "1.00"))),
                    }
                )
                summary["questions_restored"] += 1

        # 4. Routines
        for r_data in data.get("routines", []):
            course_obj = None
            if r_data.get("course_slug"):
                course_obj = Course.objects.filter(tenant=tenant, slug=r_data["course_slug"]).first()
            if not course_obj:
                course_obj = Course.objects.filter(tenant=tenant).first()

            if course_obj:
                ClassRoutine.objects.update_or_create(
                    tenant=tenant,
                    course=course_obj,
                    subject=r_data.get("subject", "General Class"),
                    day=r_data.get("day", ClassRoutine.DayOfWeek.SATURDAY),
                    defaults={
                        "mentor_name": r_data.get("mentor_name") or r_data.get("instructor_name", "Mentor"),
                        "start_time": r_data.get("start_time") or "08:00 PM",
                        "end_time": r_data.get("end_time") or "09:30 PM",
                        "live_url": r_data.get("live_url") or r_data.get("live_link", ""),
                        "is_active": r_data.get("is_active", True),
                    }
                )
                summary["routines_restored"] += 1

        # 5. Physical Books
        for b_data in data.get("books", []):
            book_slug = b_data.get("slug") or slugify(b_data.get("title", "book"))
            Book.objects.update_or_create(
                tenant=tenant,
                slug=book_slug,
                defaults={
                    "title": b_data["title"],
                    "subtitle": b_data.get("subtitle", ""),
                    "author": b_data.get("author", "একাডেমি ফ্যাকাল্টি"),
                    "description": b_data.get("description", ""),
                    "price": Decimal(b_data.get("price", "0")),
                    "discount_price": Decimal(b_data["discount_price"]) if b_data.get("discount_price") else None,
                    "edition": b_data.get("edition", "২০২৬ সংস্করণ"),
                    "pages": b_data.get("pages", 100),
                    "in_stock": b_data.get("in_stock", True),
                    "preview_pdf_url": b_data.get("preview_pdf_url", ""),
                    "buy_url": b_data.get("buy_url", ""),
                    "is_featured": b_data.get("is_featured", True),
                }
            )
            summary["books_restored"] += 1

        # 6. Free Resources
        for res_data in data.get("resources", []):
            res_slug = res_data.get("slug") or slugify(res_data.get("title", "resource"))
            FreeResource.objects.update_or_create(
                tenant=tenant,
                slug=res_slug,
                defaults={
                    "title": res_data["title"],
                    "resource_type": res_data.get("resource_type", FreeResource.ResourceType.PDF_NOTE),
                    "category": res_data.get("category", "এইচএসসি ও ভর্তি"),
                    "description": res_data.get("description", ""),
                    "file_url": res_data.get("file_url", ""),
                    "video_url": res_data.get("video_url", ""),
                    "download_count": res_data.get("download_count", 0),
                    "is_published": res_data.get("is_published", True),
                }
            )
            summary["resources_restored"] += 1

        # 7. Blog Posts
        for bp_data in data.get("blog_posts", []):
            blog_slug = bp_data.get("slug") or slugify(bp_data.get("title", "blog-post"))
            BlogPost.objects.update_or_create(
                tenant=tenant,
                slug=blog_slug,
                defaults={
                    "title": bp_data["title"],
                    "author_name": bp_data.get("author_name", "একাডেমি টিম"),
                    "category": bp_data.get("category", "ভর্তি পরামর্শ"),
                    "excerpt": bp_data.get("excerpt", ""),
                    "content": bp_data.get("content", ""),
                    "is_published": bp_data.get("is_published", True),
                }
            )
            summary["posts_restored"] += 1

        # 8. Study Clubs
        for sc_data in data.get("clubs", []):
            club_slug = sc_data.get("slug") or slugify(sc_data.get("title", "club"))
            StudentClub.objects.update_or_create(
                tenant=tenant,
                slug=club_slug,
                defaults={
                    "title": sc_data.get("title", "Club"),
                    "description": sc_data.get("description", ""),
                    "category": sc_data.get("category", "বিশ্ববিদ্যালয় ভর্তি"),
                    "icon": sc_data.get("icon", "🏛️"),
                    "is_active": sc_data.get("is_active", True),
                }
            )

    return summary
