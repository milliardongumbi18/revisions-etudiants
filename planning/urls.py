from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("", views.PlanningView.as_view(), name="home"),
    path("creneaux/nouveau/", views.SlotCreateView.as_view(), name="slot_create"),
    path("creneaux/<int:pk>/modifier/", views.SlotUpdateView.as_view(), name="slot_update"),
    path("creneaux/<int:pk>/supprimer/", views.SlotDeleteView.as_view(), name="slot_delete"),
    path("examens/nouveau/", views.ExamCreateView.as_view(), name="exam_create"),
    path("examens/<int:pk>/modifier/", views.ExamUpdateView.as_view(), name="exam_update"),
    path("examens/<int:pk>/supprimer/", views.ExamDeleteView.as_view(), name="exam_delete"),
]