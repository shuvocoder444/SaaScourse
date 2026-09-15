from django.urls import path
from apps.courses import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("manage/dashboard/", views.instructor_course_dashboard, name="manage_dashboard"),
    path("manage/courses/<int:course_id>/curriculum/", views.course_curriculum_builder, name="course_curriculum"),
    path("manage/exams/", views.manage_exams_view, name="manage_exams"),
    path("manage/exams/<int:exam_id>/builder/", views.exam_builder_view, name="exam_builder"),
    path("manage/books/", views.manage_books_view, name="manage_books"),
    path("manage/resources/", views.manage_resources_view, name="manage_resources"),
    path("manage/blog/", views.manage_blog_view, name="manage_blog"),
    
    # MCQ Exam Student Test Engine
    path("exams/<slug:exam_slug>/take/", views.exam_take_view, name="exam_take"),
    path("exams/<slug:exam_slug>/submit/", views.exam_submit_view, name="exam_submit"),
    path("exams/<slug:exam_slug>/result/<int:attempt_id>/", views.exam_result_view, name="exam_result"),

    # Public Course Syllabus and Player
    path("<slug:slug>/", views.course_detail, name="detail"),
    path("<slug:course_slug>/player/<slug:lesson_slug>/", views.lesson_player_view, name="player"),
    path("lessons/<int:lesson_id>/complete-and-next/", views.complete_and_next_lesson, name="complete_and_next"),
    path("lessons/<int:lesson_id>/toggle-progress/", views.toggle_lesson_progress, name="toggle_progress"),
    
    # Public Books
    path("pub/books/", views.book_list, name="books_list"),
    path("pub/books/<slug:slug>/", views.book_detail, name="book_detail"),
    
    # Public Free Resources
    path("pub/resources/", views.resource_list, name="resources_list"),
    path("pub/resources/<slug:slug>/download/", views.resource_download, name="resource_download"),
    
    # Public Blog
    path("pub/blog/", views.blog_list, name="blog_list"),
    path("pub/blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
]
