from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from courses.models import Course
from reviews.models import ReviewCard
from services.planner import HORIZON_JOURS, CourseInfo, ExamInfo, build_plan

from .forms import ClassSlotForm, ExamForm
from .models import ClassSlot, Exam, Weekday


class PlanningView(LoginRequiredMixin, TemplateView):
    """Emploi du temps, examens à venir et planning des 14 prochains jours (recalculé à chaque visite)."""

    template_name = "planning/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
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
            ReviewCard.objects.filter(owner=user, due_date__lt=aujourd_hui + timedelta(days=HORIZON_JOURS))
            .values("due_date").annotate(n=Count("id")).values_list("due_date", "n")
        )
        for jour, nombre in dues:
            revisions[max(jour, aujourd_hui)] += nombre

        for examen in examens:
            examen.days_left = (examen.date - aujourd_hui).days

        context.update({
            "plan": build_plan(
                aujourd_hui,
                [CourseInfo(c.pk, c.title, c.color) for c in cours],
                dict(minutes_par_jour),
                [ExamInfo(e.course_id, e.date, e.title or "Examen") for e in examens],
                dict(revisions),
            ),
            "week": [(libelle, [c for c in creneaux if c.weekday == numero]) for numero, libelle in Weekday.choices],
            "exams": examens,
            "has_courses": bool(cours),
        })
        return context


class OwnedMixin(LoginRequiredMixin):
    """Créneaux et examens : uniquement ceux de l'utilisateur (sinon 404)."""

    success_url = reverse_lazy("planning:home")

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)


class OwnedFormMixin(OwnedMixin, SuccessMessageMixin):
    template_name = "planning/form.html"
    titre = ""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user   # le formulaire filtre les cours proposés
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = self.titre
        context["delete_url"] = self.get_delete_url()
        return context

    def get_delete_url(self):
        return None


class SlotCreateView(OwnedFormMixin, CreateView):
    model = ClassSlot
    form_class = ClassSlotForm
    titre = "Ajouter un créneau de cours"
    success_message = "Créneau ajouté à ton emploi du temps."


class SlotUpdateView(OwnedFormMixin, UpdateView):
    model = ClassSlot
    form_class = ClassSlotForm
    titre = "Modifier le créneau"
    success_message = "Créneau mis à jour."

    def get_delete_url(self):
        return reverse("planning:slot_delete", args=[self.object.pk])


class SlotDeleteView(OwnedMixin, SuccessMessageMixin, DeleteView):
    model = ClassSlot
    template_name = "courses/confirm_delete.html"
    success_message = "Créneau supprimé."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning"] = "Ce créneau sera retiré de ton emploi du temps."
        context["cancel_url"] = reverse("planning:slot_update", args=[self.object.pk])
        return context


class ExamCreateView(OwnedFormMixin, CreateView):
    model = Exam
    form_class = ExamForm
    titre = "Ajouter un examen"
    success_message = "Examen ajouté : le planning en tient compte."


class ExamUpdateView(OwnedFormMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    titre = "Modifier l'examen"
    success_message = "Examen mis à jour."

    def get_delete_url(self):
        return reverse("planning:exam_delete", args=[self.object.pk])


class ExamDeleteView(OwnedMixin, SuccessMessageMixin, DeleteView):
    model = Exam
    template_name = "courses/confirm_delete.html"
    success_message = "Examen supprimé."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning"] = "Le planning ne tiendra plus compte de cet examen."
        context["cancel_url"] = reverse("planning:exam_update", args=[self.object.pk])
        return context