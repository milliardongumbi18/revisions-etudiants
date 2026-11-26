"""Calcul du planning d'un utilisateur : partagé par la page Planning et le tableau de bord."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from courses.models import Course
from reviews.models import ReviewCard, ReviewLog
from services.planner import HORIZON_JOURS, CourseInfo, ExamInfo, build_plan, placer_horaires

from .models import ClassSlot, Exam, PlanCheck


def user_plan(user, jours=HORIZON_JOURS):
    """Renvoie {"plan", "exams", "slots", "has_courses", "progress"} pour l'utilisateur."""
    aujourd_hui = timezone.localdate()
    creneaux = list(ClassSlot.objects.filter(owner=user).select_related("course"))
    examens = list(Exam.objects.filter(owner=user, date__gte=aujourd_hui).select_related("course"))
    cours = list(Course.objects.filter(owner=user))

    minutes_par_jour = defaultdict(int)
    creneaux_par_jour = defaultdict(list)
    for creneau in creneaux:
        minutes_par_jour[creneau.weekday] += creneau.minutes
        creneaux_par_jour[creneau.weekday].append(creneau)

    # Questions SM-2 dues par date (les retards comptent pour aujourd'hui)
    revisions = defaultdict(int)
    dues = (
        ReviewCard.objects.filter(owner=user, due_date__lt=aujourd_hui + timedelta(days=jours))
        .values("due_date").annotate(n=Count("id")).values_list("due_date", "n")
    )
    for jour, nombre in dues:
        revisions[max(jour, aujourd_hui)] += nombre

    for examen in examens:
        examen.days_left = (examen.date - aujourd_hui).days

    plan = build_plan(
        aujourd_hui,
        [CourseInfo(c.pk, c.title, c.color) for c in cours],
        dict(minutes_par_jour),
        [ExamInfo(e.course_id, e.date, e.libelle, e.kind) for e in examens],
        dict(revisions),
        jours=jours,
    )

    # Agenda : les cours à l'université du jour, puis une heure pour chaque bloc de révision
    for journee in plan:
        journee.classes = sorted(creneaux_par_jour[journee.date.weekday()], key=lambda c: c.start_time)
        placer_horaires(journee, [c.end_time for c in journee.classes])

    # Aujourd'hui : blocs cochés « Fait », et répétition espacée terminée (plus aucune question due)
    du_jour = plan[0]
    coches = set(PlanCheck.objects.filter(owner=user, date=aujourd_hui).values_list("course_id", flat=True))
    for bloc in du_jour.blocks:
        bloc.done = bloc.kind == "cours" and bloc.course_id in coches

    revisees = ReviewLog.objects.filter(owner=user, reviewed_at__date=aujourd_hui).count()
    a_faire = [b for b in du_jour.blocks if b.kind in ("cours", "revisions")]
    srs_terminee = revisees > 0 and not any(b.kind == "revisions" for b in a_faire)
    progress = {
        "faits": sum(b.done for b in a_faire) + srs_terminee,
        "total": len(a_faire) + srs_terminee,
        "revisees": revisees,
        "srs_terminee": srs_terminee,
    }
    return {"plan": plan, "exams": examens, "slots": creneaux, "has_courses": bool(cours), "progress": progress}