from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.signup, name="signup"),
    path("connexion/", views.SignInView.as_view(), name="login"),
    path("deconnexion/", views.SignOutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
    path("profil/modifier/", views.profile_edit, name="profile_edit"),
    path("supprimer/", views.delete_account, name="delete_account"),
        path("photo/", views.avatar_update, name="avatar_update"),
    path("photo/retirer/", views.avatar_delete, name="avatar_delete"),
    path("rappels/desactiver/<str:jeton>/", views.reminders_unsubscribe, name="reminders_unsubscribe"),
    path("mot-de-passe/", views.ChangePasswordView.as_view(), name="password_change"),
    # Mot de passe oublié
    path("mot-de-passe-oublie/", views.ResetPasswordView.as_view(), name="password_reset"),
    path("mot-de-passe-oublie/envoye/", views.ResetPasswordDoneView.as_view(), name="password_reset_done"),
    path("reinitialiser/<uidb64>/<token>/", views.ResetPasswordConfirmView.as_view(), name="password_reset_confirm"),
    path("reinitialiser/termine/", views.ResetPasswordCompleteView.as_view(), name="password_reset_complete"),
]