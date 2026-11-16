from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    path("chapitres/<int:chapter_pk>/generer/", views.GenerateQuizView.as_view(), name="generate"),
    path("<int:pk>/", views.QuizDetailView.as_view(), name="detail"),
    path("<int:pk>/supprimer/", views.QuizDeleteView.as_view(), name="delete"),
]