"""
Outils des révisions :
- création des cartes manquantes (une par question) ;
- file de questions de la séance, gardée dans la session Django (côté serveur).
"""
from django.utils import timezone

from quizzes.models import Question

from .models import ReviewCard

SESSION_KEY = "revision"
MAX_QUESTIONS = 50   # une séance raisonnable


def create_missing_cards(user, quiz=None):
    """Crée la carte de révision des questions de l'utilisateur qui n'en ont pas encore."""
    questions = Question.objects.filter(quiz__chapter__course__owner=user, review_card__isnull=True)
    if quiz is not None:
        questions = questions.filter(quiz=quiz)
    ReviewCard.objects.bulk_create(
        [ReviewCard(owner=user, question=question) for question in questions],
        ignore_conflicts=True,   # deux onglets en même temps : pas de doublon, pas d'erreur
    )


def due_cards(user):
    return ReviewCard.objects.filter(owner=user, due_date__lte=timezone.localdate())


def start_session(request, card_ids, return_url):
    ids = list(card_ids)[:MAX_QUESTIONS]
    request.session[SESSION_KEY] = {
        "queue": ids, "total": len(ids), "done": 0, "correct": 0,
        "pending": None,          # réponse donnée mais pas encore notée
        "return_url": return_url,  # URL construite par NOUS (reverse), jamais par l'utilisateur
    }


def get_session(request):
    return request.session.get(SESSION_KEY)


def save_session(request, data):
    request.session[SESSION_KEY] = data   # réaffecter = Django sait que la session a changé


def end_session(request):
    request.session.pop(SESSION_KEY, None)


def current_card(request, data):
    """Première carte de la file, en vérifiant qu'elle appartient bien à l'utilisateur."""
    while data["queue"]:
        card = (
            ReviewCard.objects.select_related("question__quiz__chapter__course")
            .filter(pk=data["queue"][0], owner=request.user)
            .first()
        )
        if card:
            return card
        # Carte supprimée entre-temps (ou étrangère) : on l'ignore
        data["queue"].pop(0)
        data["pending"] = None
        data["total"] = max(0, data["total"] - 1)
        save_session(request, data)
    return None