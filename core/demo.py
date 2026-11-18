"""
Compte de démonstration (portfolio) : un étudiant fictif avec des cours, des quiz,
un historique de révisions réaliste et un emploi du temps.
Les dates sont calculées à partir d'aujourd'hui : la démo est toujours « fraîche ».
"""
import random
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from courses.models import Chapter, Course
from planning.models import ClassSlot, Exam
from quizzes.models import Question, Quiz
from reviews.models import ReviewCard, ReviewLog
from services import sm2

from .demo_data import COURS, CRENEAUX, EXAMENS

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@exemple.cd"
MESSAGE_DEMO = "Action désactivée sur le compte de démonstration : crée ton propre compte pour l'essayer."


class CompteDemoIndisponible(Exception):
    """Le nom ou l'e-mail de la démo appartient à un vrai compte : on n'y touche surtout pas."""


def est_compte_demo(user):
    return user.is_authenticated and user.username == DEMO_USERNAME and user.email == DEMO_EMAIL


def _question(quiz, ordre, q):
    if q["type"] == "qcm":
        return Question(quiz=quiz, kind=Question.Kind.MCQ, text=q["question"], choices=q["choix"],
                        correct_index=q["bonne"], explanation=q["explication"], order=ordre)
    return Question(quiz=quiz, kind=Question.Kind.SHORT, text=q["question"],
                    expected_answer=q["attendue"], explanation=q["explication"], order=ordre)


def _simuler_historique(rng, debut, aujourd_hui):
    """
    Rejoue l'algorithme SM-2 comme si l'étudiant avait vraiment révisé depuis `debut`.
    Renvoie (état final, [(jour, note), ...], prochaine date de révision).
    """
    difficulte = rng.uniform(0.1, 0.45)          # probabilité de rater cette question
    etat, historique, jour = sm2.SM2State(), [], debut
    while jour < aujourd_hui:
        note = rng.choice([3, 4, 4, 5]) if rng.random() > difficulte else 1
        historique.append((jour, note))
        etat = sm2.review(etat, note)
        jour += timedelta(days=etat.interval)
    return etat, historique, jour


def _moment(rng, jour):
    """Une heure réaliste dans la journée (heure de Kinshasa)."""
    return timezone.make_aware(datetime.combine(jour, time(rng.randint(7, 21), rng.randint(0, 59))))


@transaction.atomic
def creer_compte_demo(mot_de_passe, aujourd_hui=None, graine=2026):
    """Crée (ou recrée) le compte de démonstration. Tout ou rien grâce à la transaction."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    rng = random.Random(graine)   # graine fixe : la même démo à chaque fois

    existant = User.objects.filter(username=DEMO_USERNAME).first()
    if existant and existant.email != DEMO_EMAIL:
        raise CompteDemoIndisponible(f"Le nom « {DEMO_USERNAME} » appartient à un vrai compte : rien n'a été modifié.")
    if User.objects.filter(email__iexact=DEMO_EMAIL).exclude(username=DEMO_USERNAME).exists():
        raise CompteDemoIndisponible(f"L'adresse {DEMO_EMAIL} appartient à un vrai compte : rien n'a été modifié.")
    if existant:
        existant.delete()   # cascade : cours, quiz, cartes, historique, planning

    user = User.objects.create_user(
        DEMO_USERNAME, email=DEMO_EMAIL, password=mot_de_passe,
        first_name="Awa", last_name="Démo",
        university="Université de Kinshasa (UNIKIN)", program="L2 Informatique",
    )

    # Jour de la première révision de chaque question : un départ chaque jour récent,
    # sauf un « trou » pour que série actuelle et meilleure série soient différentes.
    departs = [jours for jours in range(1, 29) if jours not in (12, 13)]
    cours_crees, cartes, a_journaliser, numero = [], [], [], 0

    for donnees in COURS:
        cours = Course.objects.create(owner=user, title=donnees["titre"], description=donnees["description"],
                                      outline=donnees["plan"], color=donnees["couleur"])
        cours_crees.append(cours)
        for position, chap in enumerate(donnees["chapitres"], start=1):
            chapitre = Chapter.objects.create(course=cours, title=chap["titre"], notes=chap["notes"], order=position)
            quiz = Quiz.objects.create(chapter=chapitre, generated_by="Démo (rédigé à la main)")
            questions = Question.objects.bulk_create(
                [_question(quiz, ordre, q) for ordre, q in enumerate(chap["questions"], start=1)]
            )
            for question in questions:
                carte = ReviewCard(owner=user, question=question)   # par défaut : nouvelle, à voir aujourd'hui
                if chap.get("revise", True):
                    debut = aujourd_hui - timedelta(days=departs[numero % len(departs)])
                    numero += 1
                    etat, historique, prochaine = _simuler_historique(rng, debut, aujourd_hui)
                    moments = [_moment(rng, jour) for jour, _ in historique]
                    carte.easiness, carte.interval, carte.repetitions = etat.easiness, etat.interval, etat.repetitions
                    carte.due_date = prochaine
                    carte.last_reviewed_at = moments[-1]
                    carte.review_count = len(historique)
                    carte.correct_count = sum(1 for _, note in historique if note >= 3)
                    a_journaliser.append((carte, historique, moments))
                cartes.append(carte)

    ReviewCard.objects.bulk_create(cartes)

    logs, dates = [], []
    for carte, historique, moments in a_journaliser:
        for (_, note), moment in zip(historique, moments):
            logs.append(ReviewLog(owner=user, card=carte, grade=note, correct=note >= 3))
            dates.append(moment)
    ReviewLog.objects.bulk_create(logs)
    # reviewed_at est rempli automatiquement (auto_now_add) : on remet ensuite les vraies dates
    for log, moment in zip(logs, dates):
        log.reviewed_at = moment
    ReviewLog.objects.bulk_update(logs, ["reviewed_at"], batch_size=500)

    ClassSlot.objects.bulk_create([
        ClassSlot(owner=user, course=cours_crees[i] if i is not None else None, label=label, weekday=jour,
                  start_time=time.fromisoformat(debut), end_time=time.fromisoformat(fin))
        for i, label, jour, debut, fin in CRENEAUX
    ])
    Exam.objects.bulk_create([
        Exam(owner=user, course=cours_crees[i], date=aujourd_hui + timedelta(days=dans), title=titre)
        for i, dans, titre in EXAMENS
    ])
    return {"cours": len(cours_crees), "questions": len(cartes), "revisions": len(logs)}