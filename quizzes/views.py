from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DeleteView, DetailView

from courses.models import Chapter
from services.ai_provider import AIError
from services.quiz_generator import generate_quiz

from .models import Question, Quiz
from reviews.session import create_missing_cards

MIN_NOTES_CHARS = 200
DELAI_ENTRE_GENERATIONS = timedelta(seconds=30)   # protège le quota gratuit contre les clics répétés


class OwnedQuizMixin(LoginRequiredMixin):
    """Un étudiant ne voit QUE les quiz de ses propres chapitres (sinon 404)."""

    model = Quiz

    def get_queryset(self):
        return Quiz.objects.filter(chapter__course__owner=self.request.user).select_related("chapter__course")


class GenerateQuizView(LoginRequiredMixin, View):
    """Génère un quiz pour un chapitre. POST uniquement : c'est une action qui crée des données."""

    http_method_names = ["post"]

    def post(self, request, chapter_pk):
        chapter = get_object_or_404(
            Chapter.objects.select_related("course"), pk=chapter_pk, course__owner=request.user
        )

        if len(chapter.notes.strip()) < MIN_NOTES_CHARS:
            messages.error(request, "Ce chapitre est trop court pour un quiz utile (200 caractères minimum).")
            return redirect(chapter)

        recent = Quiz.objects.filter(
            chapter__course__owner=request.user,
            created_at__gte=timezone.now() - DELAI_ENTRE_GENERATIONS,
        )
        if recent.exists():
            messages.error(request, "Patiente quelques secondes avant de générer un nouveau quiz.")
            return redirect(chapter)

        try:
            deja_posees = list(Question.objects.filter(quiz__chapter=chapter).values_list("text", flat=True)[:40])
            questions, fournisseur = generate_quiz(chapter.title, chapter.notes, deja_posees=deja_posees)
        except AIError as error:
            messages.error(request, str(error))
            return redirect(chapter)

        with transaction.atomic():   # quiz + questions : tout ou rien
            quiz = Quiz.objects.create(chapter=chapter, generated_by=fournisseur[:100])
            Question.objects.bulk_create(
                [Question(quiz=quiz, order=position, **question) for position, question in enumerate(questions, start=1)]
            )

        messages.success(request, f"Quiz de {len(questions)} questions généré !")
        create_missing_cards(request.user, quiz=quiz)   # les questions entrent tout de suite dans les révisions
        return redirect(quiz)


class QuizDetailView(OwnedQuizMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["questions"] = self.object.questions.all()
        return context


class QuizDeleteView(OwnedQuizMixin, SuccessMessageMixin, DeleteView):
    template_name = "courses/confirm_delete.html"

    def get_success_url(self):
        return self.object.chapter.get_absolute_url()

    def get_success_message(self, cleaned_data):
        return "Quiz supprimé."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning"] = "Toutes ses questions seront supprimées. Cette action est irréversible."
        context["cancel_url"] = self.object.get_absolute_url()
        return context