"""Statistiques de progression d'un cours ou d'un chapitre, pour l'étudiant connecté."""
from django.db.models import Count, F, Q, Sum

from .models import ReviewCard

MAITRISE_JOURS = 21   # même seuil que le tableau de bord : revue dans 21 jours ou plus = maîtrisée


def _pourcentage(part, total):
    return round(100 * part / total) if total else None


def _resume(cartes):
    agg = cartes.aggregate(
        questions=Count("id"),
        maitrisees=Count("id", filter=Q(interval__gte=MAITRISE_JOURS)),
        reponses=Sum("review_count"),
        justes=Sum("correct_count"),
    )
    reponses = agg["reponses"] or 0
    return {
        "questions": agg["questions"],
        "maitrise": _pourcentage(agg["maitrisees"], agg["questions"]) or 0,
        "reussite": _pourcentage(agg["justes"] or 0, reponses),
        "reponses": reponses,
    }


def progression_cours(user, course):
    """Barre du cours + une barre par chapitre (dans l'ordre des chapitres)."""
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter__course=course)
    par_chapitre = {
        ligne["chapter_id"]: ligne
        for ligne in cartes.order_by()
        .values(chapter_id=F("question__quiz__chapter_id"))
        .annotate(
            questions=Count("id"),
            maitrisees=Count("id", filter=Q(interval__gte=MAITRISE_JOURS)),
        )
    }
    chapitres = []
    for chapitre in course.chapters.all():
        ligne = par_chapitre.get(chapitre.pk)
        if ligne:
            chapitres.append({
                "chapter": chapitre,
                "questions": ligne["questions"],
                "maitrise": _pourcentage(ligne["maitrisees"], ligne["questions"]) or 0,
            })
        else:
            chapitres.append({"chapter": chapitre, "questions": 0, "maitrise": 0})
    return {"resume": _resume(cartes), "chapitres": chapitres}


def progression_chapitre(user, chapter):
    """Pour un chapitre : seulement le résumé."""
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter=chapter)
    return {"resume": _resume(cartes)}