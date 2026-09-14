from django.urls import path
from apps.courses import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("manage/dashboard/", views.instructor_course_dashboard, name="manage_dashboard"),
    path("<slug:slug>/", views.course_detail, name="detail"),
    path("<slug:course_slug>/player/<slug:lesson_slug>/", views.lesson_player_view, name="player"),
    path("lessons/<int:lesson_id>/complete-and-next/", views.complete_and_next_lesson, name="complete_and_next"),
    path("lessons/<int:lesson_id>/toggle-progress/", views.toggle_lesson_progress, name="toggle_progress"),
]
