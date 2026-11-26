from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.ReviewHomeView.as_view(), name="home"),
    path("commencer/", views.StartDueReviewView.as_view(), name="start_due"),
    path("quiz/<int:quiz_pk>/commencer/", views.StartQuizReviewView.as_view(), name="start_quiz"),
    path("epreuve/<int:exam_pk>/commencer/", views.StartExamReviewView.as_view(), name="start_exam"),
    path("session/", views.ReviewSessionView.as_view(), name="session"),
    path("session/repondre/", views.AnswerView.as_view(), name="answer"),
    path("session/noter/", views.GradeView.as_view(), name="grade"),
]