from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete
from django.dispatch import receiver


def avatar_upload_path(instance, filename):
    """Nom généré par NOUS : impossible à deviner, aucune collision, toujours en .webp."""
    return f"avatars/{instance.pk}/{uuid4().hex}.webp"


class User(AbstractUser):
    """
    Utilisateur du site.

    On hérite d'AbstractUser pour garder tout le système d'authentification
    de Django (mots de passe hachés, permissions, admin) et on ajoute nos champs.
    """

    email = models.EmailField("adresse e-mail")  # obligatoire (blank=False par défaut)
    university = models.CharField("université", max_length=150, blank=True)
    program = models.CharField("filière / promotion", max_length=150, blank=True)
    avatar = models.ImageField("photo de profil", upload_to=avatar_upload_path, blank=True)
    daily_reminder = models.BooleanField(
        "recevoir un rappel chaque matin quand des révisions m'attendent", default=False
    )
    last_reminder_sent = models.DateField("dernier rappel envoyé le", null=True, blank=True)
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


@receiver(post_delete, sender=User)
def supprimer_la_photo_du_compte(sender, instance, **kwargs):
    """Compte supprimé → sa photo est retirée du stockage (pas de fichier orphelin)."""
    if instance.avatar:
        instance.avatar.delete(save=False)