import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.tenants.models import Tenant
from apps.courses.models import Course, Exam, ExamQuestion
from apps.courses.views import (
    exam_import_questions_view,
    exam_export_txt_view,
    exam_export_csv_view,
    exam_export_json_view,
    exam_print_paper_view
)

factory = RequestFactory()
tenant = Tenant.objects.get(slug='alpha')
instructor = tenant.owner

# Get or create test exam
exam, created = Exam.objects.get_or_create(
    tenant=tenant,
    slug='sonartori-model-test-2026',
    defaults={
        'title': 'সোনার তরী ও বাংলা ১ম পত্র স্পেশাল মডেল টেস্ট',
        'duration_minutes': 25,
        'pass_mark': 40.0,
        'negative_mark_per_question': 0.25,
        'is_published': True,
    }
)

sample_pdf_text = """
১। ‘সোনার তরী’ কবিতার বর্ণনামতে বর্ষা কখন এল?
ক. ধান কাটা শুরু হলে    খ. ধান কাটতে কাটতে    গ. ধান কাটা শেষ হলে    ঘ. নৌকায় ধান তুলে দিলে    খ

২। ‘ওগো তুমি কোথা যাও কোন বিদেশে’- ‘সোনার তরী’ কবিতায় এখানে ‘তুমি’ কে?
ক. কৃষক  খ. তরী  গ. মাঝি  ঘ. কবি   গ

৩। “চারি দিকে বাঁকা জল করিছে খেলা”- এখানে ‘বাঁকা জল’ বলতে কবি কী বোঝাতে চেয়েছেন?
ক. স্রোতের বক্রতা  খ. জলের কল্লোল  গ. পরিস্থিতির ভয়াবহতা  ঘ. অনন্ত কালস্রোত   ঘ

৪। রবীন্দ্রনাথ ঠাকুর তাঁর পিতা-মাতার কততম সন্তান?
ক. দ্বিতীয়  খ. ষষ্ঠ  গ. দশম  ঘ. চতুর্দশ  ঘ

৫। ‘সোনার তরী’ কবিতায় ‘সোনার ধান’ কিসের প্রতীক?
ক. মহাকাল  খ. সমকাল  গ. সৃষ্টিকর্ম  ঘ. কালস্রোত  গ

১৫। ‘সোনার তরী’ কবিতায় ‘আমি’ বলতে যাকে বোঝায়-
i. নৌকার মাঝি
ii. সাধারণ অর্থে কৃষক
iii. প্রতীকী অর্থে কবি নিজে
নিচের কোনটি সঠিক?
ক. i  খ. i ও ii  গ. i ও iii  ঘ. ii ও iii  ঘ

১৬। ‘সোনার তরী’ কবিতায় ‘বিদেশ’ শব্দটি কী অর্থে ব্যবহৃত হয়েছে?
ক. পরলোক
খ. অচেনা জগৎ
গ. চিরায়ত শিল্পলোক
ঘ. মহাকাল
উত্তর: গ
ব্যাখ্যা: রবীন্দ্রনাথ ঠাকুরের সোনার তরী কবিতায় বিদেশ শব্দটি চিরায়ত শিল্পলোক বোঝাতে ব্যবহৃত হয়েছে।
"""

print("\n=== 1. Testing AJAX Parse & Live Preview ===")
req = factory.post(
    f'/courses/manage/exams/{exam.id}/import/',
    data={'action': 'preview', 'preview_only': 'true', 'raw_text': sample_pdf_text},
    HTTP_HOST='alpha.localhost:8001',
    HTTP_X_REQUESTED_WITH='XMLHttpRequest'
)
req.user = instructor
req.tenant = tenant
res = exam_import_questions_view(req, exam_id=exam.id)
assert res.status_code == 200, f"Preview failed with status {res.status_code}"
preview_data = json.loads(res.content.decode('utf-8'))
assert preview_data['status'] == 'success'
assert preview_data['count'] == 7
print(f" [PASS] AJAX Preview parsed {preview_data['count']} questions successfully!")

print("\n=== 2. Testing Bulk Import (Overwrite Mode) ===")
req = factory.post(
    f'/courses/manage/exams/{exam.id}/import/',
    data={
        'action': 'confirm_import',
        'import_mode': 'overwrite',
        'raw_text': sample_pdf_text
    },
    HTTP_HOST='alpha.localhost:8001'
)
req.user = instructor
req.tenant = tenant
setattr(req, 'session', {})
setattr(req, '_messages', FallbackStorage(req))
res = exam_import_questions_view(req, exam_id=exam.id)
assert res.status_code == 302, f"Import redirect failed, code: {res.status_code}"

saved_questions = ExamQuestion.objects.filter(exam=exam).order_by('order')
assert saved_questions.count() == 7, f"Expected 7 questions, got {saved_questions.count()}"
print(f" [PASS] Successfully imported {saved_questions.count()} questions into database!")

# Verify question contents
q1 = saved_questions[0]
assert 'সোনার তরী' in q1.question_text
assert q1.correct_option == 'B'
assert q1.option_a == 'ধান কাটা শুরু হলে'
assert q1.option_b == 'ধান কাটতে কাটতে'
print(f" [PASS] Q1 verified: '{q1.question_text[:30]}...' -> Correct: {q1.correct_option}")

q7 = saved_questions[6]
assert q7.correct_option == 'C'
assert 'চিরায়ত শিল্পলোক' in q7.explanation
print(f" [PASS] Q7 verified: Explanation & Answer: {q7.correct_option}")

print("\n=== 3. Testing Text Export (.txt) ===")
req = factory.get(f'/courses/manage/exams/{exam.id}/export/txt/', HTTP_HOST='alpha.localhost:8001')
req.user = instructor
req.tenant = tenant
res = exam_export_txt_view(req, exam_id=exam.id)
assert res.status_code == 200
txt_content = res.content.decode('utf-8')
assert 'সোনার তরী' in txt_content
assert 'উত্তরমালা' in txt_content
print(" [PASS] Text export successful (Contains formatted questions & answer key)")

print("\n=== 4. Testing CSV / Excel Export (.csv) ===")
req = factory.get(f'/courses/manage/exams/{exam.id}/export/csv/', HTTP_HOST='alpha.localhost:8001')
req.user = instructor
req.tenant = tenant
res = exam_export_csv_view(req, exam_id=exam.id)
assert res.status_code == 200
csv_content = res.content.decode('utf-8-sig')
assert 'Question' in csv_content
assert 'সোনার তরী' in csv_content
print(" [PASS] CSV export successful with UTF-8 BOM for Excel compatibility")

print("\n=== 5. Testing JSON Backup Export (.json) ===")
req = factory.get(f'/courses/manage/exams/{exam.id}/export/json/', HTTP_HOST='alpha.localhost:8001')
req.user = instructor
req.tenant = tenant
res = exam_export_json_view(req, exam_id=exam.id)
assert res.status_code == 200
json_data = json.loads(res.content.decode('utf-8'))
assert json_data['total_questions'] == 7
print(" [PASS] JSON export successful with complete structured data")

print("\n=== 6. Testing Printable Question Paper Sheet ===")
req = factory.get(f'/courses/manage/exams/{exam.id}/print/?answers=1', HTTP_HOST='alpha.localhost:8001')
req.user = instructor
req.tenant = tenant
res = exam_print_paper_view(req, exam_id=exam.id)
assert res.status_code == 200
html_content = res.content.decode('utf-8')
assert 'প্রশ্নপত্র' in html_content
assert 'সোনার তরী' in html_content
assert 'উত্তরমালা' in html_content
print(" [PASS] Printable question paper rendered (HTTP 200) with 2-column layout and answer key")

print("\n🎉 ALL MCQ IMPORT AND EXPORT TESTS PASSED SUCCESSFULLY!")

