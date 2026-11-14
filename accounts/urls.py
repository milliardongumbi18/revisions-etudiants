from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.signup, name="signup"),
    path("connexion/", views.SignInView.as_view(), name="login"),
    path("deconnexion/", views.SignOutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
]