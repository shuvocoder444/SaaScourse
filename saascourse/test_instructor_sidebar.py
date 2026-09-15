import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.tenants.models import Tenant
from apps.courses.models import Course, Exam
from apps.courses.views import (
    instructor_course_dashboard, 
    manage_exams_view, 
    exam_builder_view, 
    course_curriculum_builder,
    manage_books_view,
    manage_resources_view,
    manage_blog_view
)
from apps.tenants.views import tenant_branding_settings_view

User = get_user_model()
tenant = Tenant.objects.get(slug='alpha')
instructor = tenant.owner

factory = RequestFactory()

def test_view(view_func, url, name, **kwargs):
    request = factory.get(url, HTTP_HOST='alpha.localhost:8001')
    request.user = instructor
    request.tenant = tenant
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)
    
    response = view_func(request, **kwargs)
    assert response.status_code == 200, f"Failed for {name}, status: {response.status_code}"
    content = response.content.decode('utf-8')
    # Assert sidebar presence
    assert "Studio Navigation" in content or "ওভারভিউ ড্যাশবোর্ড" in content, f"Sidebar missing in {name}"
    assert "MCQ ও অনলাইন এক্সাম" in content, f"Exams link missing in sidebar for {name}"
    assert "বই ও প্রকাশনা" in content, f"Books link missing in sidebar for {name}"
    assert "৩টি ল্যান্ডিং টেমপ্লেট" in content, f"Templates link missing in sidebar for {name}"
    print(f"[OK] {name}: Sidebar present & verified")

print("\n--- TESTING INSTRUCTOR STUDIO SIDEBAR ON ALL PAGES ---")
test_view(instructor_course_dashboard, '/dashboard/?tab=overview', "Dashboard (Overview)")
test_view(instructor_course_dashboard, '/dashboard/?tab=courses', "Dashboard (Courses)")
test_view(manage_exams_view, '/courses/manage/exams/', "Manage Exams")

exam = Exam.objects.filter(tenant=tenant).first()
if exam:
    test_view(exam_builder_view, f'/courses/manage/exams/{exam.id}/builder/', "Exam Builder", exam_id=exam.id)

course = Course.objects.filter(tenant=tenant).first()
if course:
    test_view(course_curriculum_builder, f'/courses/manage/courses/{course.id}/curriculum/', "Curriculum Builder", course_id=course.id)

test_view(manage_books_view, '/courses/manage/books/', "Manage Books")
test_view(manage_resources_view, '/courses/manage/resources/', "Manage Resources")
test_view(manage_blog_view, '/courses/manage/blog/', "Manage Blog")
test_view(tenant_branding_settings_view, '/tenants/settings/?tab=template', "Settings (Templates)")
test_view(tenant_branding_settings_view, '/tenants/settings/?tab=navigation', "Settings (Navigation)")
test_view(tenant_branding_settings_view, '/tenants/settings/?tab=header_footer', "Settings (Header/Footer)")

print("\nALL INSTRUCTOR STUDIO PAGES HAVE 100% PERSISTENT SIDEBAR MENU!")
