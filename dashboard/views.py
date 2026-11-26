from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from courses.models import Chapter, Course
from planning.models import ClassSlot
from planning.utils import user_plan
from quizzes.models import Quiz
from reviews.models import ReviewCard, ReviewLog
from reviews.session import create_missing_cards
from reviews.stats import points_acquis, pourcentage_acquis
from services.stats import compute_streak

MAITRISE_JOURS = 21    # une question programmée à 21 jours ou plus est « maîtrisée »
JOURS_ACTIVITE = 30


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        aujourd_hui = timezone.localdate()
        create_missing_cards(user)

        cartes = ReviewCard.objects.filter(owner=user)
        logs = ReviewLog.objects.filter(owner=user).order_by()   # order_by() : sans tri, pour grouper / dédoublonner

        # --- Série de jours révisés (dates en heure de Kinshasa grâce à TruncDate) ---
        jours_revises = set(logs.annotate(jour=TruncDate("reviewed_at")).values_list("jour", flat=True).distinct())
        serie, meilleure = compute_streak(jours_revises, aujourd_hui)

        # --- Activité des 30 derniers jours ---
        debut = aujourd_hui - timedelta(days=JOURS_ACTIVITE - 1)
        recents = logs.filter(reviewed_at__date__gte=debut)
        par_jour = dict(
            recents.annotate(jour=TruncDate("reviewed_at")).values("jour").annotate(n=Count("id")).values_list("jour", "n")
        )
        maximum = max(par_jour.values(), default=0) or 1
        activite = []
        for decalage in range(JOURS_ACTIVITE):
            jour = debut + timedelta(days=decalage)
            nombre = par_jour.get(jour, 0)
            activite.append({"date": jour, "n": nombre, "hauteur": max(6, round(100 * nombre / maximum)) if nombre else 0})

        stats_30j = recents.aggregate(total=Count("id"), justes=Count("id", filter=Q(correct=True)))
        taux = round(100 * stats_30j["justes"] / stats_30j["total"]) if stats_30j["total"] else None

        # --- Progression par cours (une seule requête groupée) ---
        par_cours = {
            ligne["course_id"]: ligne
            for ligne in cartes.order_by()
            .values(course_id=F("question__quiz__chapter__course_id"))
            .annotate(
                total=Count("id"),
                points=points_acquis(),
                revues=Sum("review_count"),
                justes=Sum("correct_count"),
            )
        }
        progression = []
        for cours in Course.objects.filter(owner=user).annotate(nb_chapitres=Count("chapters")):
            ligne = par_cours.get(cours.pk, {})
            total = ligne.get("total", 0)
            revues, justes = ligne.get("revues") or 0, ligne.get("justes") or 0
            progression.append({
                "course": cours,
                "total": total,
                "pourcentage": pourcentage_acquis(ligne.get("points"), total),
                "reussite": round(100 * justes / revues) if revues else None,
            })

        # --- « Bien démarrer » ---
        etapes = [
            ("Créer un cours", Course.objects.filter(owner=user).exists(), reverse("courses:create")),
            ("Ajouter un chapitre", Chapter.objects.filter(course__owner=user).exists(), reverse("courses:list")),
            ("Générer un quiz", Quiz.objects.filter(chapter__course__owner=user).exists(), reverse("courses:list")),
            ("Saisir ton emploi du temps", ClassSlot.objects.filter(owner=user).exists(), reverse("planning:slot_create")),
        ]

        planning = user_plan(user, jours=1)
        context.update({
            "aujourd_hui": aujourd_hui,
            "due_count": cartes.filter(due_date__lte=aujourd_hui).count(),
            "total_cartes": cartes.count(),
            "maitrisees": cartes.filter(interval__gte=MAITRISE_JOURS).count(),
            "serie": serie,
            "meilleure_serie": meilleure,
            "a_revise_aujourdhui": aujourd_hui in jours_revises,
            "taux_reussite": taux,
            "revisions_30j": stats_30j["total"],
            "activite": activite,
            "progression": progression,
            "plan_du_jour": planning["plan"][0],
            "prochain_examen": planning["exams"][0] if planning["exams"] else None,
            "epreuves_suivantes": planning["exams"][1:3],   # les 2 suivantes, affichées en petit
            "etapes": etapes,
            "onboarding_fini": all(fait for _, fait, _ in etapes),
        })
        return context