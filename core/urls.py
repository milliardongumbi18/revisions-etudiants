from django.urls import path

from . import views

app_name = "core"  # espace de noms : on écrit {% url 'core:home' %}

urlpatterns = [
    path("", views.home, name="home"),
]