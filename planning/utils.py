"""Calcul du planning d'un utilisateur : partagé par la page Planning et le tableau de bord."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from courses.models import Course
from reviews.models import ReviewCard
from services.planner import HORIZON_JOURS, CourseInfo, ExamInfo, build_plan

from .models import ClassSlot, Exam


def user_plan(user, jours=HORIZON_JOURS):
    """Renvoie {"plan", "exams", "slots", "has_courses"} pour l'utilisateur."""
    aujourd_hui = timezone.localdate()
    creneaux = list(ClassSlot.objects.filter(owner=user).select_related("course"))
    examens = list(Exam.objects.filter(owner=user, date__gte=aujourd_hui).select_related("course"))
    cours = list(Course.objects.filter(owner=user))

    minutes_par_jour = defaultdict(int)
    for creneau in creneaux:
        minutes_par_jour[creneau.weekday] += creneau.minutes

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
        [ExamInfo(e.course_id, e.date, e.title or "Examen") for e in examens],
        dict(revisions),
        jours=jours,
    )
    return {"plan": plan, "exams": examens, "slots": creneaux, "has_courses": bool(cours)}