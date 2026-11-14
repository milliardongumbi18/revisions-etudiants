
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from core.forms import StyledFormMixin
from .models import User


EMAIL_DEJA_UTILISE = "Un compte utilise déjà cette adresse e-mail."


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

        self.fields["username"].help_text = (
            "Lettres, chiffres et @ . + - _ uniquement."
        )
        self.fields["email"].widget.attrs["placeholder"] = "toi@exemple.cd"
        self.fields["university"].widget.attrs["placeholder"] = (
            "Ex. Université de Kinshasa (UNIKIN)"
        )
        self.fields["program"].widget.attrs["placeholder"] = (
            "Ex. L2 Informatique"
        )

    def clean_email(self):
        return email_normalise_et_libre(self.cleaned_data["email"])


class LoginForm(StyledFormMixin, AuthenticationForm):
    """Connexion : uniquement le style, la logique est celle de Django."""


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Modification du profil de l'utilisateur connecté."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "university", "program")

    def clean_email(self):
        # On exclut l'utilisateur lui-même : garder son propre e-mail est permis.
        return email_normalise_et_libre(
            self.cleaned_data["email"],
            exclude_pk=self.instance.pk,
        )
