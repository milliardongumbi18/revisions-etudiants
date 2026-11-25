from datetime import date, datetime

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from courses.models import Course


class Weekday(models.IntegerChoices):
    LUNDI = 0, "Lundi"
    MARDI = 1, "Mardi"
    MERCREDI = 2, "Mercredi"
    JEUDI = 3, "Jeudi"
    VENDREDI = 4, "Vendredi"
    SAMEDI = 5, "Samedi"
    DIMANCHE = 6, "Dimanche"


class ClassSlot(models.Model):
    """Un créneau de cours à l'université, répété chaque semaine."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="class_slots", verbose_name="propriétaire"
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="class_slots", verbose_name="cours lié"
    )
    label = models.CharField(
        "intitulé", max_length=150, blank=True, help_text="Seulement si ce cours n'existe pas dans l'application."
    )
    weekday = models.PositiveSmallIntegerField("jour", choices=Weekday.choices)
    start_time = models.TimeField("début")
    end_time = models.TimeField("fin")

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            # Garantie en base, en plus du formulaire
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="planning_creneau_fin_apres_debut"),
        ]
        verbose_name = "créneau de cours"
        verbose_name_plural = "créneaux de cours"

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M} · {self.name}"

    @property
    def name(self):
        return self.course.title if self.course else self.label

    @property
    def minutes(self):
        debut = datetime.combine(date.min, self.start_time)
        fin = datetime.combine(date.min, self.end_time)
        return int((fin - debut).total_seconds() // 60)


class Exam(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exams", verbose_name="propriétaire"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="exams", verbose_name="cours")
    date = models.DateField("date de l'examen")
    title = models.CharField("intitulé", max_length=150, blank=True, help_text="Ex. Examen final, Interrogation…")

    class Meta:
        ordering = ["date"]
        verbose_name = "examen"
        verbose_name_plural = "examens"

    def __str__(self):
        return f"{self.title or 'Examen'} · {self.course} ({self.date:%d/%m/%Y})"


class PlanCheck(models.Model):
    """Un bloc de révision du jour coché « Fait » (un par cours et par jour)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan_checks", verbose_name="propriétaire"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="plan_checks", verbose_name="cours")
    date = models.DateField("jour")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "course", "date"], name="planning_bloc_fait_unique"),
        ]
        verbose_name = "bloc fait"
        verbose_name_plural = "blocs faits"

    def __str__(self):
        return f"{self.course} · {self.date:%d/%m/%Y}"