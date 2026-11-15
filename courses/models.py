from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse


def chapter_upload_path(instance, filename):
    """
    Le nom du fichier stocké est généré par NOUS : on ne garde que l'extension.
    → pas de caractères dangereux, pas de collision, impossible à deviner.
    """
    extension = Path(filename).suffix.lower()
    return f"chapitres/{instance.course.owner_id}/{uuid4().hex}{extension}"


class Course(models.Model):
    """Un cours appartenant à UN étudiant."""

    class Color(models.TextChoices):
        INDIGO = "indigo", "Indigo"
        MANGUE = "mangue", "Mangue"
        TERRACOTTA = "terracotta", "Terracotta"
        FEUILLE = "feuille", "Feuille"
        TURQUOISE = "turquoise", "Turquoise"
        SAFRAN = "safran", "Safran"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses",
        verbose_name="propriétaire",
    )
    title = models.CharField("titre", max_length=150)
    description = models.TextField("description", blank=True)
    outline = models.TextField(
        "plan du cours", blank=True, help_text="Les grandes parties du cours, une par ligne."
    )
    color = models.CharField("couleur", max_length=12, choices=Color.choices, default=Color.INDIGO)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "cours"
        verbose_name_plural = "cours"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.pk])


class Chapter(models.Model):
    """Un chapitre : du texte écrit à la main OU extrait d'un fichier (PDF / .txt)."""

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="chapters", verbose_name="cours"
    )
    title = models.CharField("titre", max_length=200)
    order = models.PositiveIntegerField("position", default=0)
    notes = models.TextField("notes de cours", blank=True)
    source_file = models.FileField("fichier source", upload_to=chapter_upload_path, blank=True)
    original_filename = models.CharField("nom du fichier d'origine", max_length=255, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "chapitre"
        verbose_name_plural = "chapitres"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:chapter_detail", args=[self.pk])


@receiver(post_delete, sender=Chapter)
def supprimer_le_fichier_du_chapitre(sender, instance, **kwargs):
    """Chapitre supprimé (seul OU avec son cours) → son fichier est retiré du stockage."""
    if instance.source_file:
        instance.source_file.delete(save=False)