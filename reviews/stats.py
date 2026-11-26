"""Statistiques de progression d'un cours ou d'un chapitre, pour l'étudiant connecté."""
from django.db.models import Count, F, Sum, Value
from django.db.models.functions import Least

from .models import ReviewCard

ETAPES_ACQUIS = 3   # 3 bonnes réponses d'affilée, espacées (1 j, 6 j, ~2 semaines) = question acquise


def points_acquis():
    """
    Expression SQL : chaque question rapporte de 0 à 3 points, ses bonnes réponses d'affilée
    (champ SM-2 « repetitions », remis à 0 après une erreur). Least = le plus petit des deux.
    """
    return Sum(Least("repetitions", Value(ETAPES_ACQUIS)))


def pourcentage_acquis(points, questions):
    """Points obtenus / points possibles, en %. 0 s'il n'y a pas encore de question."""
    return round(100 * (points or 0) / (ETAPES_ACQUIS * questions)) if questions else 0


def _resume(cartes):
    agg = cartes.aggregate(questions=Count("id"), points=points_acquis())
    return {"questions": agg["questions"], "acquis": pourcentage_acquis(agg["points"], agg["questions"])}


def progression_cours(user, course):
    """Barre du cours + une barre par chapitre (dans l'ordre des chapitres)."""
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter__course=course)
    par_chapitre = {
        ligne["chapter_id"]: ligne
        for ligne in cartes.order_by()
        .values(chapter_id=F("question__quiz__chapter_id"))
        .annotate(questions=Count("id"), points=points_acquis())
    }
    chapitres = []
    for chapitre in course.chapters.all():
        ligne = par_chapitre.get(chapitre.pk, {})
        questions = ligne.get("questions", 0)
        chapitres.append({
            "chapter": chapitre,
            "questions": questions,
            "acquis": pourcentage_acquis(ligne.get("points"), questions),
        })
    return {"resume": _resume(cartes), "chapitres": chapitres}


def progression_chapitre(user, chapter):
    """Pour un chapitre : seulement le résumé."""
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter=chapter)
    return {"resume": _resume(cartes)}