from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from courses.models import Course

from .forms import ClassSlotForm, ExamForm
from .models import ClassSlot, Exam, PlanCheck, Weekday
from .utils import user_plan


class PlanningView(LoginRequiredMixin, TemplateView):
    """Emploi du temps, examens à venir et planning des 14 prochains jours (recalculé à chaque visite)."""

    template_name = "planning/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        donnees = user_plan(self.request.user)
        context.update({
            "plan": donnees["plan"],
            "today": donnees["plan"][0],
            "next_days": donnees["plan"][1:],
            "progress": donnees["progress"],
            "exams": donnees["exams"],
            "has_courses": donnees["has_courses"],
            "week": [
                (libelle, [c for c in donnees["slots"] if c.weekday == numero])
                for numero, libelle in Weekday.choices
            ],
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
    

class PlanCheckToggleView(LoginRequiredMixin, View):
    """Coche ou décoche « Fait » sur un bloc de cours d'aujourd'hui."""

    http_method_names = ["post"]   # une modification ne passe jamais par un simple lien (GET)

    def post(self, request, course_pk):
        cours = get_object_or_404(Course, pk=course_pk, owner=request.user)   # 404 si ce n'est pas mon cours
        coche, creee = PlanCheck.objects.get_or_create(owner=request.user, course=cours, date=timezone.localdate())
        if not creee:
            coche.delete()   # 2e clic : on décoche
        return redirect(f"{reverse('planning:home')}#aujourdhui")