import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from apps.tenants.models import Tenant
from apps.courses.models import Course, Exam, ExamQuestion
from decimal import Decimal

def seed_exams():
    tenant = Tenant.objects.filter(slug='alpha').first()
    if not tenant:
        tenant = Tenant.objects.first()
    if not tenant:
        print("No tenant found!")
        return

    course = Course.objects.filter(tenant=tenant).first()

    # Exam 1: Physics Model Test
    Exam.objects.filter(tenant=tenant, slug="physics-vector-mcq-model-test").delete()
    exam1 = Exam.objects.create(
        tenant=tenant,
        course=course,
        title="এইচএসসি '২৬ পদার্থবিজ্ঞান ১ম পত্র: ভেক্টর ও গতিবিদ্যা মডেল টেস্ট",
        slug="physics-vector-mcq-model-test",
        description="ভেক্টর রাশির গুণন, নদী-নৌকা প্রবলেম, প্রক্ষেপক ও একমাত্রিক গতির বিগত বছরের বোর্ড ও বিশ্ববিদ্যালয় ভর্তি পরীক্ষার নির্বাচিত প্রশ্নাবলি।",
        duration_minutes=20,
        pass_mark=Decimal("40.00"),
        negative_mark_per_question=Decimal("0.25"),
        total_marks=Decimal("5.00"),
        is_published=True
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam1,
        question_text="দুটি সমমানের ভেক্টরের লব্ধির মান এদের যেকোনো একটির মানের সমান হলে ভেক্টরদ্বয়ের মধ্যবর্তী কোণ কত ডিগ্রি?",
        option_a="০°",
        option_b="৬০°",
        option_c="১২০°",
        option_d="১৮০°",
        correct_option="C",
        explanation="লব্ধি R = √(P² + Q² + 2PQ cos θ)। যেহেতু R = P = Q, সুতরাং P² = P² + P² + 2P² cos θ => cos θ = -1/2 => θ = 120°।",
        marks=Decimal("1.00"),
        order=1
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam1,
        question_text="A = 2i + 3j - k এবং B = -4i - 6j + 2k ভেক্টর দুটি পরস্পরের কেমন?",
        option_a="পরস্পর লম্ব",
        option_b="পরস্পর সমান্তরাল ও বিপরীতমুখী",
        option_c="পরস্পর সমান",
        option_d="কোনো সম্পর্ক নেই",
        correct_option="B",
        explanation="B = -2(2i + 3j - k) = -2A। অর্থাৎ ভেক্টর দুটি সমান্তরাল এবং ঋণাত্মক চিহ্নের কারণে দিক বিপরীতমুখী।",
        marks=Decimal("1.00"),
        order=2
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam1,
        question_text="নদীর প্রস্থ 500m এবং স্রোতের বেগ 3 km/h হলে, 5 km/h বেগে চলা নৌকা নদীটি ন্যূনতম কত সময়ে সোজাসোজি পাড় হতে পারবে?",
        option_a="৫ মিনিট",
        option_b="৭.৫ মিনিট",
        option_c="১০ মিনিট",
        option_d="১৫ মিনিট",
        correct_option="B",
        explanation="সোজাসোজি পাড় হতে কার্যকর বেগ v' = √(v² - u²) = √(25 - 9) = 4 km/h = 4000/60 m/min। সময় t = d / v' = 500 / (4000/60) = 7.5 মিনিট।",
        marks=Decimal("1.00"),
        order=3
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam1,
        question_text="কোনো প্রক্ষেপকের অনুভূমিক পাল্লা (R) সর্বাধিক হবে যদি নিক্ষেপণ কোণ কত হয়?",
        option_a="৩০°",
        option_b="৪৫°",
        option_c="৬০°",
        option_d="৯০°",
        correct_option="B",
        explanation="অনুভূমিক পাল্লা R = (v₀² sin 2θ) / g। sin 2θ এর সর্বোচ্চ মান ১ যখন 2θ = 90° বা θ = 45°।",
        marks=Decimal("1.00"),
        order=4
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam1,
        question_text="একটি স্কেলার ক্ষেত্রের গ্রেডিয়েন্ট (Gradient) সর্বদা কী নির্দেশ করে?",
        option_a="একটি স্কেলার রাশি",
        option_b="ক্ষেত্রটির সর্বাধিক বৃদ্ধির হার ও অভিমুখ নির্দেশকারী ভেক্টর",
        option_c="ক্ষেত্রটির আবর্তন",
        option_d="কোনোটিই নয়",
        correct_option="B",
        explanation="Grad(φ) = ∇φ একটি ভেক্টর রাশি যা ওই স্কেলার ক্ষেত্রের সর্বোচ্চ বৃদ্ধির দিক ও মান প্রকাশ করে।",
        marks=Decimal("1.00"),
        order=5
    )

    # Exam 2: Chemistry Quiz
    Exam.objects.filter(tenant=tenant, slug="chemistry-qualitative-mcq-test").delete()
    exam2 = Exam.objects.create(
        tenant=tenant,
        course=course,
        title="রসায়ন ১ম পত্র: গুণগত রসায়ন ও কোয়ান্টাম সংখ্যা কুইজ",
        slug="chemistry-qualitative-mcq-test",
        description="হুন্ডের নীতি, পাউলির বর্জন নীতি ও ইলেকট্রন বিন্যাস সম্পর্কিত বাছাইকৃত প্রশ্ন।",
        duration_minutes=15,
        pass_mark=Decimal("40.00"),
        negative_mark_per_question=Decimal("0.25"),
        total_marks=Decimal("3.00"),
        is_published=True
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam2,
        question_text="প্রধান কোয়ান্টাম সংখ্যা n = 3 হলে সর্বোচ্চ কয়টি ইলেকট্রন থাকতে পারে?",
        option_a="৮টি",
        option_b="১৮টি",
        option_c="৩২টি",
        option_d="২টি",
        correct_option="B",
        explanation="সর্বোচ্চ ইলেকট্রন সংখ্যা = 2n² = 2(3)² = 18টি।",
        marks=Decimal("1.00"),
        order=1
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam2,
        question_text="d-উপস্তরে অরবিটাল সংখ্যা কয়টি?",
        option_a="৩টি",
        option_b="৫টি",
        option_c="৭টি",
        option_d="১টি",
        correct_option="B",
        explanation="d সাবশেলের জন্য সহকারী কোয়ান্টাম সংখ্যা l = 2। অরবিটাল সংখ্যা = (2l + 1) = 2(2) + 1 = 5টি।",
        marks=Decimal("1.00"),
        order=2
    )

    ExamQuestion.objects.create(
        tenant=tenant,
        exam=exam2,
        question_text="কোন পরমাণু বা আয়নে কোনো নিউট্রন নেই?",
        option_a="প্রোটিয়াম (¹H)",
        option_b="ডিউটেরিয়াম (²H)",
        option_c="ট্রিটিয়াম (³H)",
        option_d="হিলিয়াম (⁴He)",
        correct_option="A",
        explanation="সাধারণ হাইড্রোজেন বা প্রোটিয়ামে ভরসংখ্যা ১ এবং প্রোটন সংখ্যা ১, ফলে নিউট্রন সংখ্যা = ১ - ১ = ০।",
        marks=Decimal("1.00"),
        order=3
    )

    print("Successfully seeded demo MCQ Exams and Questions for Alpha Academy!")

if __name__ == '__main__':
    seed_exams()

