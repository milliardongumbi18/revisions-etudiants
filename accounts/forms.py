import hashlib

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.cache import cache

from core.forms import StyledFormMixin

from .models import User

EMAIL_DEJA_UTILISE = "Un compte utilise déjà cette adresse e-mail."
MAX_ECHECS_CONNEXION = 5
DUREE_BLOCAGE = 15 * 60   # secondes


def email_normalise_et_libre(email, exclude_pk=None):
    """
    Met l'e-mail en minuscules et vérifie qu'aucun AUTRE compte ne l'utilise.
    La contrainte en base reste la garantie finale ; ici on donne un message clair.
    """
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exclude(pk=exclude_pk).exists():
        raise forms.ValidationError(EMAIL_DEJA_UTILISE)
    return email


class SignUpForm(StyledFormMixin, UserCreationForm):
    """Inscription : UserCreationForm gère les 2 mots de passe et leur validation."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "university", "program")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Lettres, chiffres et @ . + - _ uniquement."
        self.fields["email"].widget.attrs["placeholder"] = "toi@exemple.cd"
        self.fields["university"].widget.attrs["placeholder"] = "Ex. Université de Kinshasa (UNIKIN)"
        self.fields["program"].widget.attrs["placeholder"] = "Ex. L2 Informatique"

    def clean_email(self):
        return email_normalise_et_libre(self.cleaned_data["email"])


class LoginForm(StyledFormMixin, AuthenticationForm):
    """
    Connexion avec protection contre la force brute :
    après 5 échecs sur un même nom d'utilisateur, blocage de 15 minutes.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        # Volontairement vague : on ne dit pas si c'est le nom OU le mot de passe qui est faux
        "invalid_login": "Nom d'utilisateur ou mot de passe incorrect. Attention aux majuscules.",
        "trop_de_tentatives": "Trop de tentatives de connexion. Réessaie dans 15 minutes.",
    }

    def clean(self):
        nom = (self.cleaned_data.get("username") or "").strip().lower()
        # Clé de cache hachée : jamais le nom en clair, et aucun caractère problématique
        cle = "echecs-connexion:" + hashlib.sha256(nom.encode("utf-8")).hexdigest()

        if nom and cache.get(cle, 0) >= MAX_ECHECS_CONNEXION:
            raise forms.ValidationError(self.error_messages["trop_de_tentatives"], code="trop_de_tentatives")

        try:
            cleaned = super().clean()
        except forms.ValidationError:
            if nom:
                cache.add(cle, 0, DUREE_BLOCAGE)   # crée le compteur (expire après 15 min) s'il n'existe pas
                try:
                    cache.incr(cle)
                except ValueError:                 # expiré entre-temps : on repart à 1
                    cache.set(cle, 1, DUREE_BLOCAGE)
            raise

        cache.delete(cle)   # connexion réussie : compteur remis à zéro
        return cleaned


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    """Changement de mot de passe : logique de Django (vérifie l'ancien, valide le nouveau)."""


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Modification du profil de l'utilisateur connecté."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "university", "program")

    def clean_email(self):
        # On exclut l'utilisateur lui-même : garder son propre e-mail est permis.
        return email_normalise_et_libre(self.cleaned_data["email"], exclude_pk=self.instance.pk)