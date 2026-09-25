import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from django.test import Client
from apps.tenants.models import Tenant
from apps.users.models import User
from apps.courses.models import (
    Course, Module, Lesson, Exam, ExamQuestion, ExamAttempt, StudentResult
)
from decimal import Decimal

def run_tests():
    tenant = Tenant.objects.filter(slug='alpha').first()
    instructor = User.objects.get(email='teacher@alpha.com')
    student = User.objects.get(email='alex@student.com')

    inst_client = Client(HTTP_HOST='alpha.localhost:8001')
    inst_client.force_login(instructor)

    stud_client = Client(HTTP_HOST='alpha.localhost:8001')
    stud_client.force_login(student)

    print("=== 1. Testing Course Management CRUD (Studio) ===")
    
    # 1.1 Create Course
    res = inst_client.post('/dashboard/', {
        'action': 'create_course',
        'title': 'টেস্ট উচ্চতর গণিত ২য় পত্র কোর্স',
        'description': 'ক্যালকুলাস ও গতিবিদ্যা মাস্টারক্লাস',
        'price': '3000',
        'status': 'PUBLISHED',
    }, follow=True)
    assert res.status_code == 200
    created_course = Course.objects.filter(title='টেস্ট উচ্চতর গণিত ২য় পত্র কোর্স').first()
    assert created_course is not None, "Course creation failed!"
    print(f" [PASS] Course created successfully: {created_course.title} (ID: {created_course.id})")

    # 1.2 Update Course
    res = inst_client.post('/dashboard/', {
        'action': 'update_course',
        'course_id': created_course.id,
        'title': 'টেস্ট উচ্চতর গণিত ২য় পত্র (আপডেটেড)',
        'description': 'সম্পূর্ণ নতুন সিলেবাস',
        'price': '3200',
        'status': 'PUBLISHED',
    }, follow=True)
    assert res.status_code == 200
    created_course.refresh_from_db()
    assert created_course.title == 'টেস্ট উচ্চতর গণিত ২য় পত্র (আপডেটেড)'
    print(" [PASS] Course updated successfully")

    print("\n=== 2. Testing Curriculum & Lesson Builder ===")
    
    # 2.1 Add Module
    res = inst_client.post(f'/courses/manage/courses/{created_course.id}/curriculum/', {
        'action': 'create_module',
        'title': 'মডিউল ০২: অন্তরীকরণ ও স্পর্শক',
        'description': 'লিমিট ও ডিফারেনশিয়েশনের নিয়মাবলী',
        'order': 2,
    }, follow=True)
    assert res.status_code == 200
    created_mod = Module.objects.filter(course=created_course, title='মডিউল ০২: অন্তরীকরণ ও স্পর্শক').first()
    assert created_mod is not None, "Module creation failed!"
    print(f" [PASS] Module created: {created_mod.title} (ID: {created_mod.id})")

    # 2.2 Add Lesson
    res = inst_client.post(f'/courses/manage/courses/{created_course.id}/curriculum/', {
        'action': 'create_lesson',
        'module_id': created_mod.id,
        'title': 'লেকচার ০১: লিমিটের প্রাথমিক সূত্রাবলি',
        'content_type': 'VIDEO',
        'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'duration_minutes': 30,
        'is_preview': 'on',
        'order': 1,
    }, follow=True)
    assert res.status_code == 200
    created_lesson = Lesson.objects.filter(module=created_mod, title='লেকচার ০১: লিমিটের প্রাথমিক সূত্রাবলি').first()
    assert created_lesson is not None, "Lesson creation failed!"
    print(f" [PASS] Lesson created: {created_lesson.title} (ID: {created_lesson.id})")

    # 2.3 Edit Lesson
    res = inst_client.post(f'/courses/manage/courses/{created_course.id}/curriculum/', {
        'action': 'update_lesson',
        'lesson_id': created_lesson.id,
        'title': 'লেকচার ০১: লিমিটের বেসিক ও প্রমাণ (এডিটেড)',
        'content_type': 'VIDEO',
        'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'duration_minutes': 45,
        'is_preview': 'on',
        'order': 1,
    }, follow=True)
    assert res.status_code == 200
    created_lesson.refresh_from_db()
    assert created_lesson.title == 'লেকচার ০১: লিমিটের বেসিক ও প্রমাণ (এডিটেড)'
    print(" [PASS] Lesson updated successfully")

    # 2.4 Delete Lesson
    res = inst_client.post(f'/courses/manage/courses/{created_course.id}/curriculum/', {
        'action': 'delete_lesson',
        'lesson_id': created_lesson.id,
    }, follow=True)
    assert res.status_code == 200
    assert not Lesson.objects.filter(id=created_lesson.id).exists()
    print(" [PASS] Lesson deleted successfully")

    # Clean up test course
    res = inst_client.post('/dashboard/', {
        'action': 'delete_course',
        'course_id': created_course.id,
    }, follow=True)
    assert res.status_code == 200
    assert not Course.objects.filter(id=created_course.id).exists()
    print(" [PASS] Course deleted successfully")

    print("\n=== 3. Testing MCQ Exam Studio & Question Bank Builder ===")
    
    # 3.1 Create Exam
    res = inst_client.post('/courses/manage/exams/', {
        'action': 'create_exam',
        'title': 'উচ্চতর গণিত ত্রিকোণমিতি উইকলি টেস্ট',
        'duration_minutes': 25,
        'pass_mark': 40,
        'negative_mark_per_question': 0.25,
        'is_published': 'on',
    }, follow=True)
    assert res.status_code == 200
    test_exam = Exam.objects.filter(title='উচ্চতর গণিত ত্রিকোণমিতি উইকলি টেস্ট').first()
    assert test_exam is not None, "Exam creation failed!"
    print(f" [PASS] Exam created: {test_exam.title} (ID: {test_exam.id})")

    # 3.2 Add Question to Exam
    res = inst_client.post(f'/courses/manage/exams/{test_exam.id}/builder/', {
        'action': 'create_question',
        'question_text': 'sin(90° - θ) এর মান কত?',
        'option_a': 'sin θ',
        'option_b': 'cos θ',
        'option_c': 'tan θ',
        'option_d': '-cos θ',
        'correct_option': 'B',
        'explanation': 'প্রথম চতুর্ভাগে 90° - θ অবস্থিত, ফলে sin পরিবর্তন হয়ে cos হয় এবং চিহ্ন ধনাত্মক থাকে।',
        'marks': 1.0,
        'order': 1,
    }, follow=True)
    assert res.status_code == 200
    test_q = ExamQuestion.objects.filter(exam=test_exam, correct_option='B').first()
    assert test_q is not None, "Question creation failed!"
    print(f" [PASS] Exam Question created: {test_q.question_text[:30]}... (ID: {test_q.id})")

    # 3.3 Edit Question
    res = inst_client.post(f'/courses/manage/exams/{test_exam.id}/builder/', {
        'action': 'update_question',
        'question_id': test_q.id,
        'question_text': 'sin(90° - θ) এর সরলীকৃত মান কত?',
        'option_a': 'sin θ',
        'option_b': 'cos θ',
        'option_c': 'tan θ',
        'option_d': '-cos θ',
        'correct_option': 'B',
        'explanation': 'সহজ কো-রেশিও সূত্রানুসারে sin(90° - θ) = cos θ।',
        'marks': 1.0,
        'order': 1,
    }, follow=True)
    assert res.status_code == 200
    test_q.refresh_from_db()
    assert test_q.question_text == 'sin(90° - θ) এর সরলীকৃত মান কত?'
    print(" [PASS] Exam Question updated successfully")

    # 3.4 Delete Exam
    res = inst_client.post('/courses/manage/exams/', {
        'action': 'delete_exam',
        'exam_id': test_exam.id,
    }, follow=True)
    assert res.status_code == 200
    assert not Exam.objects.filter(id=test_exam.id).exists()
    print(" [PASS] Exam deleted successfully")

    print("\n=== 4. Testing Student Live Exam Taking & Automated Scorecard ===")
    
    physics_exam = Exam.objects.filter(slug='physics-vector-mcq-model-test').first()
    assert physics_exam is not None, "Physics model test exam not found!"

    # 4.1 Student opens live exam take screen
    res = stud_client.get(f'/courses/exams/{physics_exam.slug}/take/')
    assert res.status_code == 200, f"Exam take page failed with {res.status_code}"
    print(f" [PASS] Student live exam page loaded (HTTP 200): {physics_exam.title}")

    # 4.2 Student submits answers:
    # Q1 (ans=C): C (Correct +1)
    # Q2 (ans=B): B (Correct +1)
    # Q3 (ans=B): B (Correct +1)
    # Q4 (ans=B): C (Wrong -0.25)
    # Q5 (ans=B): None (Skipped 0)
    # Expected Score = 1 + 1 + 1 - 0.25 = 2.75 / 5.0 (55.0% Pass)
    q_list = list(physics_exam.questions.all().order_by('order'))
    post_data = {
        'time_taken_seconds': 180,
        f'q_{q_list[0].id}': 'C',
        f'q_{q_list[1].id}': 'B',
        f'q_{q_list[2].id}': 'B',
        f'q_{q_list[3].id}': 'C', # Wrong option intentionally
        # Q5 omitted (skipped)
    }

    res = stud_client.post(f'/courses/exams/{physics_exam.slug}/submit/', post_data, follow=True)
    assert res.status_code == 200
    
    attempt = ExamAttempt.objects.filter(exam=physics_exam, student=student).first()
    assert attempt is not None, "ExamAttempt was not recorded!"
    assert float(attempt.score) == 2.75, f"Expected score 2.75 but got {attempt.score}"
    assert attempt.correct_count == 3, f"Expected 3 correct but got {attempt.correct_count}"
    assert attempt.wrong_count == 1, f"Expected 1 wrong but got {attempt.wrong_count}"
    assert attempt.skipped_count == 1, f"Expected 1 skipped but got {attempt.skipped_count}"
    assert attempt.is_passed is True, "Expected is_passed to be True (55% >= 40%)"
    print(f" [PASS] Exam submitted & evaluated: Score {attempt.score}/{attempt.total_marks} (Passed: {attempt.is_passed})")

    # 4.3 Verify sync to StudentResult
    s_result = StudentResult.objects.filter(student=student, exam_title=physics_exam.title).first()
    assert s_result is not None, "StudentResult was not synced!"
    assert float(s_result.obtained_marks) == 2.75
    print(f" [PASS] Automatically synced to Student Dashboard Result: Grade {s_result.grade}, Score {s_result.obtained_marks}")

    # 4.4 Result scorecard page renders with HTTP 200
    res = stud_client.get(f'/courses/exams/{physics_exam.slug}/result/{attempt.id}/')
    assert res.status_code == 200
    print(f" [PASS] Scorecard & Explanation review page loaded (HTTP 200)")

    print("\n🎉 ALL COURSE CRUD AND MCQ EXAM ENGINE TESTS PASSED!")

if __name__ == '__main__':
    run_tests()

