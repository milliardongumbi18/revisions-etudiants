from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.CourseListView.as_view(), name="list"),
    path("nouveau/", views.CourseCreateView.as_view(), name="create"),
    path("<int:pk>/", views.CourseDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.CourseUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.CourseDeleteView.as_view(), name="delete"),
    path("<int:pk>/importer/", views.CourseImportView.as_view(), name="import"),
    path("<int:course_pk>/chapitres/nouveau/", views.ChapterCreateView.as_view(), name="chapter_create"),
    path("chapitres/<int:pk>/", views.ChapterDetailView.as_view(), name="chapter_detail"),
    path("chapitres/<int:pk>/modifier/", views.ChapterUpdateView.as_view(), name="chapter_update"),
    path("chapitres/<int:pk>/supprimer/", views.ChapterDeleteView.as_view(), name="chapter_delete"),
    path("chapitres/<int:pk>/fichier/", views.ChapterFileView.as_view(), name="chapter_file"),
]