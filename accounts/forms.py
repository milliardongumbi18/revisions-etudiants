import hashlib
import logging

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.cache import cache

from core.demo import est_compte_demo
from services.images import ImageInvalide, preparer_avatar
from core.forms import StyledFormMixin

from .models import User
from django.core.validators import RegexValidator

logger = logging.getLogger(__name__)

EMAIL_DEJA_UTILISE = "Un compte utilise déjà cette adresse e-mail."
MAX_ECHECS_CONNEXION = 5
DUREE_BLOCAGE = 15 * 60          # secondes
DELAI_ENTRE_EMAILS = 5 * 60      # au plus un e-mail de réinitialisation par adresse toutes les 5 minutes

# Comme le validateur de Django, mais SANS le @ (évite « @@nom » et la confusion avec un e-mail)
NOM_UTILISATEUR_VALIDE = RegexValidator(
    r"^[\w.+-]+\Z",
    "Lettres, chiffres et . + - _ uniquement (pas de @ ni d'espace).",
)


def cle_cache(prefixe, valeur):
    """Clé de cache hachée : jamais la donnée en clair, aucun caractère problématique."""
    return prefixe + hashlib.sha256(valeur.strip().lower().encode("utf-8")).hexdigest()


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
        self.fields["username"].help_text = "Lettres, chiffres et . + - _ uniquement."
        self.fields["email"].widget.attrs["placeholder"] = "toi@exemple.cd"
        self.fields["university"].widget.attrs["placeholder"] = "Ex. Université de Kinshasa (UNIKIN)"
        self.fields["program"].widget.attrs["placeholder"] = "Ex. L2 Informatique"

    def clean_username(self):
        username = super().clean_username()   # Django vérifie déjà l'unicité (sans tenir compte des majuscules)
        NOM_UTILISATEUR_VALIDE(username)
        return username

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
        cle = cle_cache("echecs-connexion:", nom)

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


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    """
    « Mot de passe oublié » : Django retrouve le compte par e-mail et envoie un lien signé.
    Même page de confirmation que l'adresse existe ou non (aucune fuite d'information).
    """

    def get_users(self, email):
        # Jamais d'e-mail pour le compte de démonstration (adresse fictive, mot de passe public)
        return (user for user in super().get_users(email) if not est_compte_demo(user))

    def save(self, *args, **kwargs):
        # Anti-abus : au plus un e-mail par adresse toutes les 5 minutes (protège aussi le quota Brevo)
        if not cache.add(cle_cache("reinit-mdp:", self.cleaned_data["email"]), 1, DELAI_ENTRE_EMAILS):
            return
        super().save(*args, **kwargs)

    def send_mail(self, *args, **kwargs):
        # Un souci chez le fournisseur ne doit pas afficher une erreur 500 à l'étudiant
        try:
            super().send_mail(*args, **kwargs)
        except Exception:
            logger.exception("E-mail de réinitialisation non envoyé")


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    """Choix du nouveau mot de passe (validé par les règles de AUTH_PASSWORD_VALIDATORS)."""


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Modification du profil de l'utilisateur connecté."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "university", "program")

    def clean_email(self):
        # On exclut l'utilisateur lui-même : garder son propre e-mail est permis.
        return email_normalise_et_libre(self.cleaned_data["email"], exclude_pk=self.instance.pk)


class DeleteAccountForm(StyledFormMixin, forms.Form):
    """Suppression du compte : on redemande le mot de passe (une session volée ne suffit pas)."""

    password = forms.CharField(
        label="Mot de passe actuel",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Mot de passe incorrect.")
        return password


class AvatarForm(forms.Form):
    """Photo de profil : la vraie vérification est faite par services/images.py."""

    avatar = forms.FileField(
        label="Photo de profil",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_avatar(self):
        fichier = self.cleaned_data["avatar"]
        try:
            self.contenu = preparer_avatar(fichier)   # octets WebP prêts à enregistrer
        except ImageInvalide as exc:
            raise forms.ValidationError(str(exc))
        return fichier