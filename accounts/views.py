from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from core.demo import MESSAGE_DEMO, est_compte_demo

from .forms import (
    AvatarForm,
    DeleteAccountForm,
    LoginForm,
    ProfileForm,
    SignUpForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .models import User


def signup(request):
    """Inscription, puis connexion automatique et arrivée sur « Mes cours »."""
    if request.user.is_authenticated:
        return redirect("courses:list")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()          # le mot de passe est haché par UserCreationForm
            login(request, user)
            messages.success(request, f"Bienvenue {user.username} ! Crée ton premier cours pour commencer.")
            return redirect("courses:list")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


class SignInView(SuccessMessageMixin, LoginView):
    """
    Connexion. LoginView vérifie que le paramètre ?next= pointe vers NOTRE site
    (protection contre les redirections ouvertes).
    """

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    success_message = "Bon retour, %(username)s !"


class SignOutView(LogoutView):
    """Déconnexion : uniquement en POST (protégé par le jeton CSRF)."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "Tu es déconnecté. À bientôt !")
        return response


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    """
    Changement de mot de passe. PasswordChangeView :
    - exige d'être connecté ;
    - vérifie l'ancien mot de passe ;
    - garde la session ouverte après le changement (update_session_auth_hash).
    """

    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")
    success_message = "Mot de passe modifié avec succès."

    def dispatch(self, request, *args, **kwargs):
        # Compte de démo : mot de passe public, il ne doit pas pouvoir être changé
        if est_compte_demo(request.user):
            messages.info(request, MESSAGE_DEMO)
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)


# --- Mot de passe oublié : 4 écrans fournis par Django, à nos couleurs ---------------------

class ResetPasswordView(PasswordResetView):
    """1. Saisie de l'e-mail → envoi d'un lien signé, valable PASSWORD_RESET_TIMEOUT."""

    form_class = StyledPasswordResetForm
    template_name = "accounts/password_reset_form.html"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    email_template_name = "accounts/emails/password_reset.txt"
    html_email_template_name = "accounts/emails/password_reset.html"
    success_url = reverse_lazy("accounts:password_reset_done")


class ResetPasswordDoneView(PasswordResetDoneView):
    """2. « Si un compte existe, un e-mail a été envoyé » (même message dans tous les cas)."""

    template_name = "accounts/password_reset_done.html"


class ResetPasswordConfirmView(PasswordResetConfirmView):
    """3. Lien de l'e-mail : vérifie le jeton, puis demande le nouveau mot de passe."""

    form_class = StyledSetPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class ResetPasswordCompleteView(PasswordResetCompleteView):
    """4. Confirmation finale, avec un lien vers la connexion."""

    template_name = "accounts/password_reset_complete.html"


@login_required
def profile(request):
    """Profil en lecture seule : les informations, et un bouton pour les modifier."""
    return render(request, "accounts/profile.html")


@login_required
def profile_edit(request):
    """Modification du profil, toujours via request.user (pas d'id dans l'URL)."""
    if est_compte_demo(request.user):
        messages.info(request, MESSAGE_DEMO)
        return redirect("accounts:profile")

    # Copie fraîche : si le formulaire est invalide, les valeurs refusées
    # n'apparaissent pas ailleurs dans la page (en-tête, menu).
    instance = User.objects.get(pk=request.user.pk)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("accounts:profile")   # redirection après POST : pas de double envoi
    else:
        form = ProfileForm(instance=instance)

    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
def delete_account(request):
    """Suppression définitive du compte et de TOUTES ses données, après confirmation du mot de passe."""
    if est_compte_demo(request.user):
        messages.info(request, MESSAGE_DEMO)
        return redirect("accounts:profile")

    if request.method == "POST":
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            logout(request)   # d'abord fermer la session...
            user.delete()     # ...puis tout supprimer en cascade (cours, quiz, révisions, planning, fichiers)
            messages.success(request, "Ton compte et toutes tes données ont été supprimés. À bientôt !")
            return redirect("core:home")
    else:
        form = DeleteAccountForm(request.user)

    return render(request, "accounts/delete_account.html", {"form": form})


@login_required
@require_POST
def avatar_update(request):
    """Nouvelle photo : vérifiée et nettoyée, puis l'ancienne est supprimée du stockage."""
    if est_compte_demo(request.user):
        messages.info(request, MESSAGE_DEMO)
        return redirect("accounts:profile")

    form = AvatarForm(request.POST, request.FILES)
    if form.is_valid():
        user = User.objects.get(pk=request.user.pk)
        ancienne = user.avatar.name
        user.avatar.save("avatar.webp", ContentFile(form.contenu), save=True)
        if ancienne:
            user.avatar.storage.delete(ancienne)
        messages.success(request, "Photo de profil mise à jour.")
    else:
        messages.error(request, form.errors["avatar"][0])
    return redirect("accounts:profile")


@login_required
@require_POST
def avatar_delete(request):
    """Retire la photo : le fichier est supprimé du stockage, puis le champ est vidé."""
    if est_compte_demo(request.user):
        messages.info(request, MESSAGE_DEMO)
        return redirect("accounts:profile")

    user = User.objects.get(pk=request.user.pk)
    if user.avatar:
        user.avatar.delete(save=True)
        messages.success(request, "Photo de profil retirée.")
    return redirect("accounts:profile")