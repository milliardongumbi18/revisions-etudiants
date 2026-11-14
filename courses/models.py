from django.conf import settings
from django.db import models
from django.urls import reverse


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
        on_delete=models.CASCADE,        # compte supprimé → ses cours aussi
        related_name="courses",          # user.courses.all()
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
        ordering = ["-updated_at"]       # le plus récemment travaillé en premier
        verbose_name = "cours"
        verbose_name_plural = "cours"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.pk])


class Chapter(models.Model):
    """Un chapitre d'un cours. Pour l'instant : des notes texte (PDF à l'étape suivante)."""

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="chapters", verbose_name="cours"
    )
    title = models.CharField("titre", max_length=200)
    order = models.PositiveIntegerField("position", default=0)
    notes = models.TextField("notes de cours", blank=True)
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