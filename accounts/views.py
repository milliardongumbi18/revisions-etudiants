from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render

from .forms import LoginForm, ProfileForm, SignUpForm
from .models import User


def signup(request):
    """Inscription, puis connexion automatique."""
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()          # le mot de passe est haché par UserCreationForm
            login(request, user)
            messages.success(request, f"Bienvenue {user.username} ! Ton compte est prêt.")
            return redirect("accounts:profile")
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


@login_required
def profile(request):
    """Profil de l'utilisateur connecté, toujours via request.user (pas d'id dans l'URL)."""
    # Copie fraîche de l'utilisateur : si le formulaire est invalide, les valeurs
    # refusées ne s'affichent pas dans l'en-tête ni dans la carte de profil.
    instance = User.objects.get(pk=request.user.pk)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("accounts:profile")   # redirection après POST : pas de double envoi
    else:
        form = ProfileForm(instance=instance)

    return render(request, "accounts/profile.html", {"form": form})