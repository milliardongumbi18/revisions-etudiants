from django.db import models
from django.urls import reverse

from courses.models import Chapter


class Quiz(models.Model):
    """Un quiz généré à partir d'un chapitre (un chapitre peut en avoir plusieurs)."""

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="quizzes", verbose_name="chapitre")
    generated_by = models.CharField("généré par", max_length=100, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "quiz"
        verbose_name_plural = "quiz"

    def __str__(self):
        return f"Quiz « {self.chapter.title} »"

    def get_absolute_url(self):
        return reverse("quizzes:detail", args=[self.pk])


class Question(models.Model):
    class Kind(models.TextChoices):
        MCQ = "qcm", "QCM"
        SHORT = "courte", "Question courte"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions", verbose_name="quiz")
    kind = models.CharField("type", max_length=10, choices=Kind.choices)
    text = models.TextField("question")
    choices = models.JSONField("choix", default=list, blank=True)   # liste de textes (QCM)
    correct_index = models.PositiveSmallIntegerField("bonne réponse (position)", null=True, blank=True)
    expected_answer = models.TextField("réponse attendue", blank=True)   # question courte
    explanation = models.TextField("explication", blank=True)
    order = models.PositiveIntegerField("position", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "question"
        verbose_name_plural = "questions"

    def __str__(self):
        return self.text[:80]

    @property
    def correct_choice(self):
        """Texte de la bonne réponse d'un QCM ('' sinon)."""
        if self.kind == self.Kind.MCQ and self.correct_index is not None and self.correct_index < len(self.choices):
            return self.choices[self.correct_index]
        return ""