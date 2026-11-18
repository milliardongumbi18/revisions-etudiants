from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from core.demo import MESSAGE_DEMO, est_compte_demo

from .forms import LoginForm, ProfileForm, SignUpForm, StyledPasswordChangeForm
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


@login_required
def profile(request):
    """Profil de l'utilisateur connecté, toujours via request.user (pas d'id dans l'URL)."""
    # Copie fraîche : si le formulaire est invalide, les valeurs refusées
    # ne s'affichent pas dans l'en-tête ni dans la carte de profil.
    instance = User.objects.get(pk=request.user.pk)

    if request.method == "POST":
        if est_compte_demo(request.user):
            messages.info(request, MESSAGE_DEMO)
            return redirect("accounts:profile")
        form = ProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("accounts:profile")   # redirection après POST : pas de double envoi
    else:
        form = ProfileForm(instance=instance)

    return render(request, "accounts/profile.html", {"form": form})