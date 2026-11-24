"""Statistiques de progression d'un cours ou d'un chapitre, pour l'étudiant connecté."""
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from services.progress import SEMAINES, debut_semaine, evolution, tracer

from .models import ReviewCard, ReviewLog

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


def _evolution(logs):
    aujourd_hui = timezone.localdate()
    debut = debut_semaine(aujourd_hui) - timedelta(weeks=SEMAINES - 1)
    reponses = [
        (timezone.localtime(moment).date(), correct)   # date en heure de Kinshasa
        for moment, correct in logs.filter(reviewed_at__date__gte=debut).values_list("reviewed_at", "correct")
    ]
    return tracer(evolution(reponses, aujourd_hui))


def progression_cours(user, course):
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter__course=course)
    par_chapitre = {
        ligne["chapter_id"]: ligne
        for ligne in cartes.order_by()
        .values(chapter_id=F("question__quiz__chapter_id"))
        .annotate(
            questions=Count("id"),
            maitrisees=Count("id", filter=Q(interval__gte=MAITRISE_JOURS)),
            reponses=Sum("review_count"),
            justes=Sum("correct_count"),
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
                "reussite": _pourcentage(ligne["justes"] or 0, ligne["reponses"] or 0),
            })
        else:
            chapitres.append({"chapter": chapitre, "questions": 0, "maitrise": 0, "reussite": None})

    logs = ReviewLog.objects.filter(owner=user, card__question__quiz__chapter__course=course)
    return {"resume": _resume(cartes), "evolution": _evolution(logs), "chapitres": chapitres}


def progression_chapitre(user, chapter):
    cartes = ReviewCard.objects.filter(owner=user, question__quiz__chapter=chapter)
    logs = ReviewLog.objects.filter(owner=user, card__question__quiz__chapter=chapter)
    return {"resume": _resume(cartes), "evolution": _evolution(logs)}