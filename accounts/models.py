from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """
    Utilisateur du site.

    On hérite d'AbstractUser pour garder tout le système d'authentification
    de Django (mots de passe hachés, permissions, admin) et on ajoute nos champs.
    """

    email = models.EmailField("adresse e-mail")  # obligatoire (blank=False par défaut)
    university = models.CharField("université", max_length=150, blank=True)
    program = models.CharField("filière / promotion", max_length=150, blank=True)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        constraints = [
            # Unicité de l'e-mail SANS tenir compte des majuscules, garantie par la base :
            # même deux inscriptions simultanées ne peuvent pas créer de doublon.
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message="Un compte utilise déjà cette adresse e-mail.",
            ),
        ]

    def save(self, *args, **kwargs):
        # On stocke toujours l'e-mail en minuscules, sans espaces autour.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username