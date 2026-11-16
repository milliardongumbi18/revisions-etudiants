from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from quizzes.models import Question
from services.sm2 import EASINESS_DEFAULT, SM2State


class ReviewCard(models.Model):
    """État de répétition espacée d'UNE question pour son propriétaire."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_cards", verbose_name="propriétaire"
    )
    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name="review_card", verbose_name="question"
    )
    easiness = models.FloatField("facilité", default=EASINESS_DEFAULT)
    interval = models.PositiveIntegerField("intervalle (jours)", default=0)
    repetitions = models.PositiveIntegerField("réussites d'affilée", default=0)
    due_date = models.DateField("à revoir le", default=timezone.localdate)
    last_reviewed_at = models.DateTimeField("dernière révision", null=True, blank=True)
    review_count = models.PositiveIntegerField("nombre de révisions", default=0)
    correct_count = models.PositiveIntegerField("bonnes réponses", default=0)

    class Meta:
        ordering = ["due_date", "pk"]
        indexes = [models.Index(fields=["owner", "due_date"])]   # « mes cartes dues aujourd'hui » : requête rapide
        verbose_name = "carte de révision"
        verbose_name_plural = "cartes de révision"

    def __str__(self):
        return f"{self.question} (à revoir le {self.due_date:%d/%m/%Y})"

    @property
    def state(self):
        return SM2State(self.easiness, self.interval, self.repetitions)

    def apply(self, state, correct):
        """Enregistre le nouvel état SM-2 et planifie la prochaine révision."""
        self.easiness = state.easiness
        self.interval = state.interval
        self.repetitions = state.repetitions
        self.due_date = timezone.localdate() + timedelta(days=state.interval)
        self.last_reviewed_at = timezone.now()
        self.review_count += 1
        if correct:
            self.correct_count += 1


class ReviewLog(models.Model):
    """Historique : une ligne par réponse (servira au tableau de bord et aux séries de jours)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_logs", verbose_name="propriétaire"
    )
    card = models.ForeignKey(ReviewCard, on_delete=models.CASCADE, related_name="logs", verbose_name="carte")
    grade = models.PositiveSmallIntegerField("note")
    correct = models.BooleanField("réussie")
    reviewed_at = models.DateTimeField("révisée le", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reviewed_at"]
        verbose_name = "révision"
        verbose_name_plural = "historique des révisions"