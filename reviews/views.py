from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Min
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from quizzes.models import Question, Quiz
from services.sm2 import review

from .models import ReviewCard, ReviewLog
from .session import (
    create_missing_cards, current_card, due_cards, end_session, get_session, save_session, start_session,
)

NOTES_AUTORISEES = {1, 3, 4, 5}                                   # 1 = raté, 3 = difficile, 4 = bien, 5 = facile
BOUTONS_REUSSITE = [(3, "Difficile"), (4, "Bien"), (5, "Facile")]


def libelle_delai(jours):
    return "demain" if jours <= 1 else f"dans {jours} j"


class ReviewHomeView(LoginRequiredMixin, TemplateView):
    """Révisions du jour : combien de questions à revoir, et dans quels cours."""

    template_name = "reviews/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        create_missing_cards(user)   # les questions des nouveaux quiz entrent dans le cycle

        aujourd_hui = timezone.localdate()
        cartes = ReviewCard.objects.filter(owner=user)
        dues = due_cards(user)
        context.update({
            "due_count": dues.count(),
            "total_count": cartes.count(),
            "new_count": cartes.filter(review_count=0).count(),
            "next_due": cartes.filter(due_date__gt=aujourd_hui).aggregate(d=Min("due_date"))["d"],
            "by_course": (
                dues.annotate(
                    course_title=F("question__quiz__chapter__course__title"),
                    course_color=F("question__quiz__chapter__course__color"),
                )
                .values("course_title", "course_color")
                .annotate(n=Count("id"))
                .order_by("-n")
            ),
            "session_active": bool(get_session(self.request)),
        })
        return context


class StartDueReviewView(LoginRequiredMixin, View):
    """Démarre la séance avec toutes les questions dues aujourd'hui."""

    http_method_names = ["post"]

    def post(self, request):
        create_missing_cards(request.user)
        ids = list(due_cards(request.user).values_list("pk", flat=True))
        if not ids:
            messages.info(request, "Rien à réviser aujourd'hui : tout est à jour !")
            return redirect("reviews:home")
        start_session(request, ids, reverse("reviews:home"))
        return redirect("reviews:session")


class StartQuizReviewView(LoginRequiredMixin, View):
    """Démarre la séance avec toutes les questions d'un quiz (même celles qui ne sont pas dues)."""

    http_method_names = ["post"]

    def post(self, request, quiz_pk):
        quiz = get_object_or_404(Quiz, pk=quiz_pk, chapter__course__owner=request.user)
        create_missing_cards(request.user, quiz=quiz)
        ids = (
            ReviewCard.objects.filter(owner=request.user, question__quiz=quiz)
            .order_by("question__order")
            .values_list("pk", flat=True)
        )
        start_session(request, ids, quiz.get_absolute_url())
        return redirect("reviews:session")


class ReviewSessionView(LoginRequiredMixin, View):
    """Affiche la question en cours, sa correction (si répondue), ou le bilan final."""

    def get(self, request):
        data = get_session(request)
        if not data:
            return redirect("reviews:home")

        card = current_card(request, data)
        if card is None:   # file vide : bilan
            end_session(request)
            pourcentage = round(100 * data["correct"] / data["done"]) if data["done"] else 0
            return render(request, "reviews/session_done.html", {"data": data, "percent": pourcentage})

        pending = data.get("pending")
        if not pending or pending.get("card") != card.pk:
            pending = None

        boutons = [
            (note, libelle, libelle_delai(review(card.state, note).interval))
            for note, libelle in BOUTONS_REUSSITE
        ]
        return render(request, "reviews/session.html", {
            "card": card,
            "question": card.question,
            "chapter": card.question.quiz.chapter,
            "pending": pending,
            "position": data["done"] + 1,
            "total": data["total"],
            "percent": round(100 * data["done"] / data["total"]) if data["total"] else 0,
            "boutons": boutons,
        })


class AnswerView(LoginRequiredMixin, View):
    """Enregistre la réponse (sans encore noter) puis réaffiche la page avec la correction."""

    http_method_names = ["post"]

    def post(self, request):
        data = get_session(request)
        card = current_card(request, data) if data else None
        if card is None:
            return redirect("reviews:session")

        question = card.question
        if question.kind == Question.Kind.MCQ:
            try:
                choix = int(request.POST.get("choice", ""))
            except ValueError:
                choix = -1
            if not 0 <= choix < len(question.choices):
                messages.error(request, "Choisis une réponse avant de valider.")
                return redirect("reviews:session")
            data["pending"] = {"card": card.pk, "choice": choix, "correct": choix == question.correct_index, "answer": ""}
        else:
            reponse = request.POST.get("answer", "").strip()[:1000]
            data["pending"] = {"card": card.pk, "choice": None, "correct": None, "answer": reponse}

        save_session(request, data)
        return redirect("reviews:session")   # redirection après POST : F5 ne renvoie pas la réponse


class GradeView(LoginRequiredMixin, View):
    """Applique SM-2 avec la note choisie, enregistre l'historique, passe à la question suivante."""

    http_method_names = ["post"]

    def post(self, request):
        data = get_session(request)
        card = current_card(request, data) if data else None
        pending = data.get("pending") if data else None
        if card is None or not pending or pending.get("card") != card.pk:
            return redirect("reviews:session")

        try:
            note = int(request.POST.get("grade", ""))
        except ValueError:
            return HttpResponseBadRequest("Note invalide.")
        if note not in NOTES_AUTORISEES:
            return HttpResponseBadRequest("Note invalide.")

        if pending["correct"] is False:   # QCM raté : retour demain, quoi que l'on clique
            note = 1
        reussi = note >= 3

        card.apply(review(card.state, note), reussi)
        card.save()
        ReviewLog.objects.create(owner=request.user, card=card, grade=note, correct=reussi)

        data["queue"].pop(0)
        data["done"] += 1
        data["correct"] += int(reussi)
        data["pending"] = None
        save_session(request, data)
        return redirect("reviews:session")