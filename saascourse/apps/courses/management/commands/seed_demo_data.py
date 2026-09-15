from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import Tenant, SubscriptionPlan, TenantSubscription, TenantMenuItem
from apps.users.models import TenantMembership
from apps.courses.models import Course, Module, Lesson, Enrollment, Book, FreeResource, BlogPost, GalleryImage
from core.tenancy.context import tenant_context

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds subscription plans, demo academies, courses, books, free resources, blog posts, and custom menus."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding multi-tenant SaaS, 3 templates, books, resources, blogs, and menus..."))

        # 1. SaaS Subscription Plans
        plan_starter, _ = SubscriptionPlan.objects.get_or_create(
            slug="starter",
            defaults={
                "name": "Starter",
                "price_monthly": 1500.00,
                "max_courses": 5,
                "max_students": 250,
                "custom_domain_allowed": False,
                "is_popular": False,
                "features": [
                    "Up to 5 Published Courses",
                    "Up to 250 Students",
                    "Custom Subdomain (e.g. brand.platform)",
                    "Video Lessons & Notes",
                    "Standard Support",
                ],
            },
        )

        plan_pro, _ = SubscriptionPlan.objects.get_or_create(
            slug="pro",
            defaults={
                "name": "Professional",
                "price_monthly": 3500.00,
                "max_courses": 25,
                "max_students": 2500,
                "custom_domain_allowed": True,
                "is_popular": True,
                "features": [
                    "Up to 25 Published Courses",
                    "Up to 2,500 Students",
                    "White-Label Custom CNAME Domain",
                    "3 Premium Landing Page Templates",
                    "Custom Menu Builder",
                    "SMS Gateway Integration",
                    "Books & Free Resources Storefront",
                ],
            },
        )

        plan_enterprise, _ = SubscriptionPlan.objects.get_or_create(
            slug="enterprise",
            defaults={
                "name": "Enterprise",
                "price_monthly": 7500.00,
                "max_courses": 100,
                "max_students": 10000,
                "custom_domain_allowed": True,
                "is_popular": False,
                "features": [
                    "Unlimited Courses & Students",
                    "All 3 Landing Page Templates",
                    "Custom Domain with Auto SSL",
                    "Multi-Instructor Roles",
                    "24/7 Dedicated Support",
                ],
            },
        )
        self.stdout.write(self.style.SUCCESS("[OK] Seeded 3 Subscription Plans"))

        # 2. Superadmin User
        admin_user, created = User.objects.get_or_create(
            email="admin@platform.com",
            defaults={
                "first_name": "Platform",
                "last_name": "Superadmin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
        self.stdout.write(self.style.SUCCESS("[OK] Created Superadmin: admin@platform.com (password: admin123)"))

        # 3. Instructors & Students
        instructor_1, _ = User.objects.get_or_create(
            email="sarah@alpha.io",
            defaults={"first_name": "সাকিব", "last_name": "আহমেদ (ঢাবি)"},
        )
        instructor_1.set_password("password123")
        instructor_1.save()

        instructor_2, _ = User.objects.get_or_create(
            email="marcus@designmaster.io",
            defaults={"first_name": "ডা. মাহমুদ", "last_name": "হাসান (DMC)"},
        )
        instructor_2.set_password("password123")
        instructor_2.save()

        student, _ = User.objects.get_or_create(
            email="student@demo.com",
            defaults={"first_name": "রাকিব", "last_name": "চৌধুরী"},
        )
        student.set_password("password123")
        student.save()

        # 4. Tenant 1: Alpha Academy (Template 1: Bangladeshi EdTech & Admission LMS)
        tenant_alpha, _ = Tenant.objects.get_or_create(
            slug="alpha",
            defaults={
                "name": "Alpha Academy (DU ICU Batch)",
                "owner": instructor_1,
                "landing_template": Tenant.LandingTemplate.EDTECH_BANGLA,
                "is_active": True,
                "branding": {
                    "primary_color": "#16a34a",
                    "accent_color": "#f59e0b",
                    "tagline": "স্বপ্ন হোক সফলতার সূচনা।",
                    "hero_badge": "HSC 2026 • DU ICU BATCH",
                    "hero_headline": "সেরা শিক্ষক ও প্র্যাকটিস ব্যাচে নির্ভুল প্রস্তুতিতে স্বপ্ন হোক সফলতার সূচনা",
                    "hero_subheadline": "এইচএসসি, ঢাকা বিশ্ববিদ্যালয় ও মেডিকেল ভর্তি পরীক্ষার পূর্ণাঙ্গ প্রস্তুতি নিন ঘরে বসেই অভিজ্ঞ মেন্টরদের সাথে।",
                    "cta_text": "সেরা কোর্স বেছে নাও",
                    "cta_link": "#courses",
                    "cta_secondary_text": "আমাদের বইসমূহ",
                    "cta_secondary_link": "/books/",
                    "notice_text": "📢 ভর্তি চলছে! আগামী ব্যাচের লাইভ ক্লাসে দ্রুত যুক্ত হোন। আসন সংখ্যা সীমিত।",
                    "about_heading": "কেন আমাদের সাথে প্রস্তুতি নেবেন?",
                    "about_text": "অভিজ্ঞ মেন্টর, সার্বক্ষণিক ডাউট সলভিং, প্র্যাকটিস এক্সাম ও লাইভ ক্লাসের মাধ্যমে আমরা নিশ্চিত করি সর্বোচ্চ প্রস্তুতি।",
                    "app_promo_title": "ডাউনলোড করুন আমাদের মোবাইল অ্যাপ, শেখা শুরু করুন আজ থেকেই",
                    "app_promo_subtitle": "লাইভ ক্লাস, প্র্যাকটিস এক্সাম, পিডিএফ লেকচার শিট ও পরীক্ষার ফলাফল সব পাবেন হাতের মুঠোয়।",
                    "app_rating": "4.8★ (৫,০০০+ রিভিউ)",
                    "app_downloads": "৫০,০০০+ শিক্ষার্থী",
                    "play_store_url": "https://play.google.com",
                    "app_store_url": "https://apple.com/app-store/",
                    "contact_phone": "+880 1800-123456",
                    "contact_email": "support@alpha-academy.edu.bd",
                    "contact_address": "ফার্মগেট / নীলক্ষেত, ঢাকা, বাংলাদেশ",
                },
            },
        )
        TenantSubscription.objects.update_or_create(
            tenant=tenant_alpha,
            defaults={
                "plan": plan_pro,
                "status": TenantSubscription.Status.ACTIVE,
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant_alpha,
            user=instructor_1,
            defaults={"role": TenantMembership.Role.ADMIN},
        )

        # Seed Alpha Menus
        tenant_alpha.ensure_default_menus()

        # Seed Alpha Courses, Books, Resources, Blogs
        with tenant_context(tenant_alpha):
            courses_data = [
                ("DU ICU BATCH 2026 - খ ও গ ইউনিট", "du-icu-batch-2026", "বাংলা, ইংরেজি, সাধারণ জ্ঞান ও ব্যবসায় শিক্ষার পূর্ণাঙ্গ প্র্যাকটিস ব্যাচ।", 1999.00),
                ("Commerce Hub - একাউন্টিং ও ম্যানেজমেন্ট স্পেশাল", "commerce-hub-special", "বাণিজ্য অনুষদের জন্য ঢাকা বিশ্ববিদ্যালয় ও গুচ্ছ ভর্তি পরীক্ষা স্পেশাল কোর্স।", 2499.00),
                ("Varsity Unit A - ফিজিক্স, কেমিস্ট্রি ও ম্যাথ", "varsity-unit-a-mega", "বিজ্ঞান বিভাগের শিক্ষার্থীদের জন্য ইঞ্জিনিয়ারিং ও ভার্সিটি ক-ইউনিট প্রস্তুতি।", 2999.00),
                ("2nd Time Optimistic Batch - মেডিকেল ও ডেন্টাল ক্র্যাশ", "2nd-time-optimistic-batch", "সেকেন্ড টাইমারদের জন্য স্পেশাল রিভিশন ও ডেইলি মডেল টেস্ট ব্যাচ।", 1750.00),
                ("English Text Book & Grammar Masterclass", "english-text-book-grammar", "এইচএসসি ও এডমিশন ইংরেজি ফার্স্ট ও সেকেন্ড পেপারের পূর্ণাঙ্গ সমাধান।", 699.00),
                ("বাংলা ব্যাকরণ ও সাহিত্য স্পেশাল কোর্স", "bangla-grammar-literature", "বিসিএস ও এডমিশন উপযোগী বাংলা ব্যাকরণের সম্পূর্ণ শর্টকাট টেকনিক।", 750.00),
            ]
            for title, slug, desc, price in courses_data:
                c, _ = Course.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "description": desc,
                        "instructor": instructor_1,
                        "status": Course.Status.PUBLISHED,
                        "price": price,
                        "is_free": False,
                    },
                )
                m1, _ = Module.objects.get_or_create(course=c, order=1, defaults={"title": "মডিউল ১: মৌলিক সিলেবাস ও প্রস্তুতি কৌশল"})
                Lesson.objects.get_or_create(
                    module=m1,
                    slug=f"intro-{slug}",
                    defaults={
                        "title": "কোর্স পরিচিতি ও ১০০ দিনের রুটিন",
                        "content_type": Lesson.ContentType.ARTICLE,
                        "duration_minutes": 15,
                        "order": 1,
                        "is_preview": True,
                        "content": "এই কোর্সে সম্পূর্ণ সিলেবাস কভার করা হবে নিয়মিত লাইভ ক্লাস ও প্র্যাকটিস টেস্টের মাধ্যমে।",
                    },
                )

            # Seed Books for Alpha
            books_data = [
                ("DU ICU প্রশ্নব্যাংক ও সমাধান ২০২৬", "du-icu-question-bank-2026", "বিগত ১৫ বছরের ব্যাখ্যাসহ ঢাবি প্রশ্ন সমাধান", 350.00, 450.00, "২০২৬ সংস্করণ"),
                ("মেডিকেল ভর্তি সহায়িকা ও মডেল টেস্ট", "medical-admission-guide-2026", "বায়োলজি, কেমিস্ট্রি ও ফিজিক্স চূড়ান্ত শিট", 420.00, 500.00, "২০২৬ সংস্করণ"),
                ("ভার্সিটি ক-ইউনিট ফর্মুলা বুক", "varsity-a-formula-book", "পদার্থ ও গণিত শর্টকাট টেকনিক সংকলন", 290.00, 350.00, "২০২৬ সংস্করণ"),
                ("ইংলিশ গ্রামার বুলেটিন ও ভোকাবুলারি", "english-grammar-bulletin", "এডমিশন ইংরেজির মোস্ট ইমপর্ট্যান্ট রুলস", 250.00, 300.00, "২০২৬ সংস্করণ"),
                ("বাংলা ব্যাকরণ ও সাহিত্য হ্যান্ড নোট", "bangla-grammar-hand-notes", "সহজে মনে রাখার অভিনব ছন্দ ও চার্ট", 200.00, 250.00, "২০২৬ সংস্করণ"),
                ("জেনারেল নলেজ ক্যাপসুল ২০২৬", "gk-capsule-2026", "বাংলাদেশ ও আন্তর্জাতিক সাম্প্রতিক ঘটনাবলী", 180.00, 220.00, "২০২৬ সংস্করণ"),
            ]
            for title, slug, subtitle, price, disc_price, edition in books_data:
                Book.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "subtitle": subtitle,
                        "author": "ইউনিক পাঠশালা ফ্যাকাল্টি",
                        "price": price,
                        "discount_price": disc_price,
                        "edition": edition,
                        "pages": 280,
                        "in_stock": True,
                        "description": f"{title} বইটি শিক্ষার্থীদের বোর্ড পরীক্ষা ও বিশ্ববিদ্যালয় ভর্তি পরীক্ষায় সর্বোচ্চ ফলাফলের জন্য রচিত।",
                    },
                )

            # Seed Free Resources for Alpha
            resources_data = [
                ("ঢাকা বিশ্ববিদ্যালয় বিগত ১০ বছরের প্রশ্ন ও সমাধান PDF", "du-past-10-years-pdf", FreeResource.ResourceType.PDF_NOTE, "DU এডমিশন", 1250),
                ("মেডিকেল ভর্তি পরীক্ষা ২০২৬ চূড়ান্ত মডেল টেস্ট পেপার", "medical-model-test-paper-2026", FreeResource.ResourceType.MODEL_TEST, "মেডিকেল ভর্তি", 980),
                ("এইচএসসি ২০২৬ বাংলা ব্যাকরণ শর্টকাট শিট", "hsc-2026-bangla-grammar-sheet", FreeResource.ResourceType.LECTURE_SHEET, "HSC ও আলিম", 1640),
                ("বুয়েট ও ইঞ্জিনিয়ারিং ফিজিক্স সুপার সাজেশন", "buet-engineering-physics-suggestion", FreeResource.ResourceType.SUGGESTION, "ইঞ্জিনিয়ারিং", 840),
            ]
            for title, slug, r_type, cat, count in resources_data:
                FreeResource.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "resource_type": r_type,
                        "category": cat,
                        "description": "ফ্রি ডাউনলোড করে প্রিন্ট নিয়ে পড়ালেখা চালিয়ে যান।",
                        "download_count": count,
                        "is_published": True,
                    },
                )

            # Seed Blog Posts for Alpha
            blogs_data = [
                ("ঢাকা বিশ্ববিদ্যালয়ে ১ম হওয়ার পড়ার রুটিন ও গোপন কৌশল", "how-to-top-in-dhaka-university", "ভর্তি প্রস্তুতি", "সাকিব আহমেদ (ঢাবি)", "প্রতিদিন কত ঘণ্টা পড়বেন এবং কীভাবে রিভিশন দিবেন তার বিস্তারিত গাইডলাইন।"),
                ("মেডিকেল ভর্তি পরীক্ষায় চান্স পাওয়ার ৫০ দিনের মাস্টারপ্ল্যান", "medical-admission-50-days-plan", "মেডিকেল প্রস্তুতি", "ডা. মাহমুদ হাসান", "বায়োলজি ও কেমিস্ট্রিতে ফুল মার্কস তোলার নির্ভুল কৌশল।"),
                ("ইংরেজি প্রথম ও দ্বিতীয় পত্রে A+ নিশ্চিত করার নিয়ম", "hsc-english-a-plus-technique", "বোর্ড পরীক্ষা", "একাডেমি টিম", "গ্রামার ও রাইটিং পার্টে বেশি নম্বর পাওয়ার কার্যকরী কৌশল।"),
            ]
            for title, slug, cat, author, excerpt in blogs_data:
                BlogPost.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "category": cat,
                        "author_name": author,
                        "excerpt": excerpt,
                        "content": f"{title}\n\n{excerpt}\n\nসফলতার মূল চাবিকাঠি হলো ধারাবাহিক প্র্যাকটিস ও সঠিক গাইডলাইন মেনে চলা। নিয়মিত মডেল টেস্ট দিন এবং ভুলগুলো সংশোধন করুন।",
                        "views_count": 520,
                        "is_published": True,
                    },
                )

        # 5. Tenant 2: Beta Academy (Template 2: Modern SaaS)
        tenant_beta, _ = Tenant.objects.get_or_create(
            slug="beta",
            defaults={
                "name": "Design & Tech Masterclass",
                "owner": instructor_2,
                "landing_template": Tenant.LandingTemplate.MODERN_SAAS,
                "is_active": True,
                "branding": {
                    "primary_color": "#4f46e5",
                    "accent_color": "#06b6d4",
                    "tagline": "Master modern software engineering and UI design.",
                    "hero_headline": "Level Up Your Career with High-Impact Tech Curriculums",
                    "hero_subheadline": "Interactive coding courses covering modern Python, Django multi-tenancy, and reactive Tailwind CSS applications.",
                    "cta_text": "Explore All Courses",
                    "cta_link": "#courses",
                },
            },
        )
        TenantSubscription.objects.update_or_create(
            tenant=tenant_beta,
            defaults={
                "plan": plan_starter,
                "status": TenantSubscription.Status.ACTIVE,
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        TenantMembership.objects.unscoped().get_or_create(
            tenant=tenant_beta,
            user=instructor_2,
            defaults={"role": TenantMembership.Role.ADMIN},
        )
        tenant_beta.ensure_default_menus()

        self.stdout.write(self.style.SUCCESS("[OK] Seeded Tenant 1: Alpha Academy (Template 1 EdTech - http://alpha.localhost:8001/)"))
        self.stdout.write(self.style.SUCCESS("[OK] Seeded Tenant 2: Beta Academy (Template 2 Modern SaaS - http://beta.localhost:8001/)"))
        self.stdout.write(self.style.SUCCESS("All demo courses, books, resources, blogs, and menus seeded successfully!"))
