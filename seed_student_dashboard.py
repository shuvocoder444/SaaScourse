import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership
from apps.courses.models import (
    Course, Book, Enrollment,
    FeedPost, FeedLike, FeedComment,
    ClassRoutine, StudentResult,
    SupportThread, SupportChatMessage,
    StudentInvoice, BookOrder,
    StudentClub, ClubMembership, ClubPost, ClubLike, ClubComment
)
from decimal import Decimal

def seed():
    tenant = Tenant.objects.filter(slug='alpha').first()
    if not tenant:
        tenant = Tenant.objects.first()
    if not tenant:
        print("No tenant found!")
        return

    # Student user
    student, _ = User.objects.get_or_create(
        email='alex@student.com',
        defaults={
            'first_name': 'Alex',
            'last_name': 'Hasan',
        }
    )
    student.set_password('password123')
    student.first_name = 'Alex'
    student.last_name = 'Hasan'
    student.save()

    TenantMembership.objects.update_or_create(
        tenant=tenant,
        user=student,
        defaults={'role': TenantMembership.Role.STUDENT, 'is_active': True}
    )

    # Instructor user
    teacher, _ = User.objects.get_or_create(
        email='teacher@alpha.com',
        defaults={
            'first_name': 'অধ্যাপক ড. রফিকুল',
            'last_name': 'ইসলাম',
        }
    )
    teacher.set_password('password123')
    teacher.first_name = 'অধ্যাপক ড. রফিকুল'
    teacher.last_name = 'ইসলাম'
    teacher.save()

    TenantMembership.objects.update_or_create(
        tenant=tenant,
        user=teacher,
        defaults={'role': TenantMembership.Role.INSTRUCTOR, 'is_active': True}
    )

    print(f"Target student: {student.email} in tenant: {tenant.name}")

    # Ensure course exists
    c_enrolled, _ = Course.objects.get_or_create(
        tenant=tenant,
        slug="hsc-physics-1st-paper",
        defaults={
            'instructor': teacher,
            'title': "HSC '26 পদার্থবিজ্ঞান ১ম পত্র সম্পূর্ণ কোর্স",
            'description': "ভেক্টর থেকে শুরু করে আদর্শ গ্যাস পর্যন্ত সকল অধ্যায়ের বিস্তারিত ব্যাখ্যা ও গাণিতিক সমাধান।",
            'price': Decimal("2500.00"),
            'status': Course.Status.PUBLISHED,
        }
    )
    Enrollment.objects.get_or_create(tenant=tenant, user=student, course=c_enrolled)

    # 1. Feed Posts & Comments & Likes
    FeedPost.objects.filter(tenant=tenant).delete()
    p1 = FeedPost.objects.create(
        tenant=tenant,
        author=teacher,
        title="আগামী শুক্রবারের পদার্থবিজ্ঞান ১ম পত্র স্পেশাল লাইভ ক্লাস",
        content="প্রিয় শিক্ষার্থীবৃন্দ, ভেক্টর ও গতিবিদ্যা অধ্যায়ের বিগত ১০ বছরের বোর্ড প্রশ্ন ও বুয়েট ভর্তি পরীক্ষার জটিল গাণিতিক সমস্যার সমাধান নিয়ে আগামী শুক্রবার সন্ধ্যা ৭টায় স্পেশাল লাইভ ক্লাস অনুষ্ঠিত হবে। ক্লাস লিংক রুটিন ট্যাবে ও নোটিফিকেশনে যুক্ত করা হয়েছে। সবাই খাতা-কলম ও ক্যালকুলেটর নিয়ে প্রস্তুত থেকো!",
        category=FeedPost.Category.GENERAL,
    )
    FeedLike.objects.get_or_create(tenant=tenant, post=p1, user=student)
    FeedComment.objects.create(tenant=tenant, post=p1, author=student, content="স্যার, ডট ও ক্রস গুণনের ব্যবহারিক প্রয়োগগুলো একটু বুঝিয়ে দিলে ভালো হতো।")
    FeedComment.objects.create(tenant=tenant, post=p1, author=teacher, content="নিশ্চয়ই, ক্লাসে এই সংক্রান্ত ৩টি রিয়েল-লাইফ এক্সপেরিমেন্ট দেখানো হবে।")

    p2 = FeedPost.objects.create(
        tenant=tenant,
        author=student,
        title="রসায়ন ২য় পত্র: জৈব যৌগের রূপান্তর চার্ট কীভাবে সহজে মনে রাখা যায়?",
        content="আমি অ্যালিফ্যাটিক থেকে অ্যারোমেটিক হাইড্রোকার্বনের রূপান্তরের একটি কালার কোডেড চার্ট তৈরি করেছি। বন্ধুদের উপকারে আসলে খুব খুশি হব! তোমাদের কোনো সহজ ট্রিকস জানা থাকলে কমেন্টে শেয়ার করতে পারো।",
        category=FeedPost.Category.STUDY_TIPS,
    )
    FeedLike.objects.get_or_create(tenant=tenant, post=p2, user=teacher)
    FeedComment.objects.create(tenant=tenant, post=p2, author=teacher, content="দারুণ উদ্যোগ অ্যালেক্স! এভাবে ভিজ্যুয়াল চার্ট বানিয়ে পড়লে বিক্রিয়াগুলো সহজে আয়ত্তে থাকে।")

    # 2. Class Routine
    ClassRoutine.objects.filter(tenant=tenant).delete()
    ClassRoutine.objects.create(
        tenant=tenant,
        course=c_enrolled,
        day=ClassRoutine.DayOfWeek.SUNDAY,
        start_time="06:30 PM",
        end_time="08:00 PM",
        subject="উচ্চতর গণিত: কণিক ও স্থানাঙ্ক জ্যামিতি",
        mentor_name="প্রকৌশলী তামিম আহমেদ",
        live_url="https://zoom.us/j/123456789",
        is_active=True
    )
    ClassRoutine.objects.create(
        tenant=tenant,
        course=c_enrolled,
        day=ClassRoutine.DayOfWeek.MONDAY,
        start_time="07:00 PM",
        end_time="08:30 PM",
        subject="পদার্থবিজ্ঞান ১ম পত্র: নিউটনিয়ান বলবিদ্যা",
        mentor_name="অধ্যাপক ড. রফিকুল ইসলাম",
        live_url="https://meet.google.com/abc-defg-hij",
        is_active=True
    )
    ClassRoutine.objects.create(
        tenant=tenant,
        course=c_enrolled,
        day=ClassRoutine.DayOfWeek.WEDNESDAY,
        start_time="08:00 PM",
        end_time="09:15 PM",
        subject="রসায়ন ১ম পত্র: গুণগত রসায়ন ও দ্রাব্যতা নীতি",
        mentor_name="ডা. সালমা বেগম",
        live_url="https://zoom.us/j/987654321",
        is_active=True
    )
    ClassRoutine.objects.create(
        tenant=tenant,
        course=c_enrolled,
        day=ClassRoutine.DayOfWeek.FRIDAY,
        start_time="04:00 PM",
        end_time="05:30 PM",
        subject="আইসিটি: সি প্রোগ্রামিং ও লজিক গেইট সিমুলেশন",
        mentor_name="তানভীর মাহতাব",
        live_url="https://meet.google.com/ict-live-class",
        is_active=True
    )

    # 3. Student Results / Scorecards
    StudentResult.objects.filter(student=student, tenant=tenant).delete()
    StudentResult.objects.create(
        student=student,
        tenant=tenant,
        exam_title="সাপ্তাহিক মডেল টেস্ট ০১: পদার্থবিজ্ঞান ১ম পত্র (ভেক্টর)",
        course_name="HSC '26 পদার্থবিজ্ঞান",
        subject="পদার্থবিজ্ঞান",
        total_marks=Decimal("50.00"),
        obtained_marks=Decimal("47.50"),
        grade="A+",
        merit_position=3,
        total_participants=245,
        remarks="অসাধারণ পারফরম্যান্স! গাণিতিক অংশে নিখুঁত সমাধান হয়েছে।"
    )
    StudentResult.objects.create(
        student=student,
        tenant=tenant,
        exam_title="মাসিক মূল্যায়ন পরীক্ষা: রসায়ন গুণগত রসায়ন ও আয়ন শনাক্তকরণ",
        course_name="HSC '26 রসায়ন",
        subject="রসায়ন",
        total_marks=Decimal("100.00"),
        obtained_marks=Decimal("89.00"),
        grade="A+",
        merit_position=8,
        total_participants=420,
        remarks="খুব ভালো হয়েছে। দ্রাব্যতার গুণফল সম্পর্কিত সমাধানে সামান্য সতর্কতা প্রয়োজন।"
    )
    StudentResult.objects.create(
        student=student,
        tenant=tenant,
        exam_title="উচ্চতর গণিত কুইজ টেস্ট: ত্রিকোণমিতি",
        course_name="HSC '26 উচ্চতর গণিত",
        subject="গণিত",
        total_marks=Decimal("30.00"),
        obtained_marks=Decimal("28.00"),
        grade="A+",
        merit_position=5,
        total_participants=180,
        remarks="দারুণ গতি ও নির্ভুল হিসাব। চালিয়ে যাও!"
    )

    # 4. Support Thread & Messages
    SupportThread.objects.filter(student=student, tenant=tenant).delete()
    t1 = SupportThread.objects.create(
        student=student,
        tenant=tenant,
        subject="লাইভ ক্লাসের রেকর্ডেড ভিডিও প্লেয়ার লোডিং সমস্যা",
        category="ক্লাস ও ভিডিও প্লেয়ার",
        status=SupportThread.Status.OPEN
    )
    SupportChatMessage.objects.create(
        tenant=tenant,
        thread=t1,
        sender=student,
        message="আসসালামু আলাইকুম স্যার, গতকালের পদার্থবিজ্ঞান ক্লাসের রেকর্ডিং ১০৮০পি রেজুলিউশনে প্লে হতে গিয়ে বাফারিং হচ্ছে। একটু সাহায্য করবেন কি?",
        is_staff_reply=False
    )
    SupportChatMessage.objects.create(
        tenant=tenant,
        thread=t1,
        sender=teacher,
        message="ওয়ালাইকুম আসসালাম। ধন্যবাদ বিষয়টি জানানোর জন্য। আমাদের সিডিএন সার্ভার ক্যাশ রিফ্রেশ করা হয়েছে। আপনি এখন ৭২০পি অথবা ১০৮০পি তে স্মুথলি দেখতে পারবেন। একবার পেজটি রিলোড দিয়ে দেখুন।",
        is_staff_reply=True
    )

    # 5. Invoices
    StudentInvoice.objects.filter(student=student, tenant=tenant).delete()
    StudentInvoice.objects.create(
        student=student,
        tenant=tenant,
        invoice_no="INV-2026-0841",
        item_title="HSC '26 বিজ্ঞান সম্পূর্ণ মাস্টারকোর্স (ফিজিক্স + কেমিস্ট্রি + ম্যাথ)",
        amount=Decimal("4500.00"),
        status="PAID",
        payment_method="bKash Online Gateway",
        transaction_id="BKASH9X281LA0"
    )
    StudentInvoice.objects.create(
        student=student,
        tenant=tenant,
        invoice_no="INV-2026-0912",
        item_title="বোর্ড প্রশ্নব্যাংক ও ইঞ্জিনিয়ারিং প্রস্তুতি সহায়িকা - হার্ডকপি বই সেট",
        amount=Decimal("1250.00"),
        status="PAID",
        payment_method="Nagad Gateway",
        transaction_id="NAGAD71029KL8"
    )

    # 6. Book Orders
    BookOrder.objects.filter(student=student, tenant=tenant).delete()
    book1 = Book.objects.filter(tenant=tenant).first()
    if not book1:
        book1 = Book.objects.create(
            tenant=tenant,
            title="পদার্থবিজ্ঞান ১ম ও ২য় পত্র ফাইনাল রিভিশন গাইড",
            author="প্রকৌশলী তামিম আহমেদ",
            price=Decimal("450.00"),
            stock=150,
            is_active=True
        )
    BookOrder.objects.create(
        student=student,
        tenant=tenant,
        book=book1,
        quantity=1,
        total_amount=book1.price or Decimal("450.00"),
        shipping_address="হাউস ১২, রোড ৪, ধানমন্ডি, ঢাকা",
        phone_number="01712345678",
        courier_name="Steadfast Courier (স্টেডফাস্ট কুরিয়ার)",
        tracking_number="STF-99281726",
        status=BookOrder.Status.SHIPPED
    )

    # 7. Clubs, Memberships, Posts
    StudentClub.objects.filter(tenant=tenant).delete()
    c1 = StudentClub.objects.create(
        tenant=tenant,
        title="বুয়েট ও ইঞ্জিনিয়ারিং ভর্তি প্রস্তুতি ক্লাব",
        slug="buet-engineering-club",
        description="বুয়েট, কুয়েট, রুয়েট ও চুয়েট স্বপ্নবাজ শিক্ষার্থীদের জন্য বিশেষ আলোচনা ও গণিত সমাধান হাব।",
        icon="🚀",
        category="ইঞ্জিনিয়ারিং ভর্তি"
    )
    c2 = StudentClub.objects.create(
        tenant=tenant,
        title="HSC '26 বিজ্ঞান পরিবার",
        slug="hsc-26-science-family",
        description="এইচএসসি বিজ্ঞান বিভাগের সকল বিষয়ের নোট শেয়ারিং ও লাইভ প্রবলেম সলভিং কমিউনিটি।",
        icon="🔬",
        category="এইচএসসি বিজ্ঞান"
    )
    c3 = StudentClub.objects.create(
        tenant=tenant,
        title="মেডিকেল ড্রিমার্স ও বায়োলজি ক্লাব",
        slug="medical-dreamers-club",
        description="ডিএমসি ও সরকারি মেডিকেল কলেজের স্বপ্নপূরণে বায়োলজি ও জিকে স্টাডি গ্রুপ।",
        icon="🩺",
        category="মেডিকেল ভর্তি"
    )

    ClubMembership.objects.get_or_create(tenant=tenant, club=c1, user=student)
    ClubMembership.objects.get_or_create(tenant=tenant, club=c2, user=student)

    cp1 = ClubPost.objects.create(
        tenant=tenant,
        club=c1,
        author=student,
        title="ইন্ট্রিগ্রেশন বাই পার্টস শর্টকাট মেথড",
        content="ইন্ট্রিগ্রেশন বাই পার্টস (Integration by Parts) এর একটি জটিল অঙ্ক নিয়ে আটকে গেছি। কেউ কি সহজ শর্টকাট মেথডটা বুঝিয়ে দিতে পারবেন?"
    )
    ClubLike.objects.get_or_create(tenant=tenant, post=cp1, user=teacher)
    ClubComment.objects.create(
        tenant=tenant,
        post=cp1,
        author=teacher,
        content="LIATE রুল ব্যবহার করে প্রথমে u ও v সিলেক্ট করো। DI (Tabular) মেথড ব্যবহার করলে মাত্র ২০ সেকেন্ডেই সমাধান করা সম্ভব!"
    )

    print("Successfully seeded full Student Dashboard demo data!")

if __name__ == '__main__':
    seed()
