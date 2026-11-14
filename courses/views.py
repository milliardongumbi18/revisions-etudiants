from functools import cached_property

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ChapterForm, CourseForm
from .models import Chapter, Course


# ---------------------------------------------------------------------------
# Sécurité : chaque vue ne cherche QUE parmi les données de l'utilisateur connecté.
# Un objet d'un autre étudiant donne une 404 (on ne révèle même pas qu'il existe).
# ---------------------------------------------------------------------------

class OwnedCourseMixin(LoginRequiredMixin):
    model = Course

    def get_queryset(self):
        return Course.objects.filter(owner=self.request.user)


class OwnedChapterMixin(LoginRequiredMixin):
    model = Chapter

    def get_queryset(self):
        return Chapter.objects.filter(course__owner=self.request.user).select_related("course")


# ------------------------------- Cours -------------------------------------

class CourseListView(OwnedCourseMixin, ListView):
    context_object_name = "courses"

    def get_queryset(self):
        # Le nombre de chapitres est calculé en UNE requête (pas une par cours)
        return super().get_queryset().annotate(chapter_count=Count("chapters"))


class CourseCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Course
    form_class = CourseForm
    success_message = "Cours « %(title)s » créé."

    def form_valid(self, form):
        form.instance.owner = self.request.user   # le propriétaire vient de la session, jamais du formulaire
        return super().form_valid(form)


class CourseDetailView(OwnedCourseMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapters"] = self.object.chapters.all()
        return context


class CourseUpdateView(OwnedCourseMixin, SuccessMessageMixin, UpdateView):
    form_class = CourseForm
    success_message = "Cours mis à jour."


class CourseDeleteView(OwnedCourseMixin, SuccessMessageMixin, DeleteView):
    template_name = "courses/confirm_delete.html"
    success_url = reverse_lazy("courses:list")

    def get_success_message(self, cleaned_data):
        return f"Cours « {self.object.title} » supprimé."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning"] = "Tous ses chapitres seront supprimés avec lui. Cette action est irréversible."
        context["cancel_url"] = self.object.get_absolute_url()
        return context


# ------------------------------ Chapitres ----------------------------------

class ChapterCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Chapter
    form_class = ChapterForm
    success_message = "Chapitre « %(title)s » ajouté."

    @cached_property
    def course(self):
        # Lu APRÈS la vérification de connexion (pas dans dispatch).
        # 404 si le cours n'existe pas OU appartient à quelqu'un d'autre.
        return get_object_or_404(Course, pk=self.kwargs["course_pk"], owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.course
        return context

    def form_valid(self, form):
        form.instance.course = self.course
        dernier = self.course.chapters.aggregate(dernier=Max("order"))["dernier"] or 0
        form.instance.order = dernier + 1
        response = super().form_valid(form)
        self.course.save(update_fields=["updated_at"])   # le cours remonte en tête de liste
        return response

    def get_success_url(self):
        return self.course.get_absolute_url()


class ChapterDetailView(OwnedChapterMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapitres = list(self.object.course.chapters.only("pk", "title"))
        index = next(i for i, c in enumerate(chapitres) if c.pk == self.object.pk)
        context["position"] = index + 1
        context["total"] = len(chapitres)
        context["previous"] = chapitres[index - 1] if index > 0 else None
        context["next"] = chapitres[index + 1] if index < len(chapitres) - 1 else None
        return context


class ChapterUpdateView(OwnedChapterMixin, SuccessMessageMixin, UpdateView):
    form_class = ChapterForm
    success_message = "Chapitre mis à jour."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.object.course
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.course.save(update_fields=["updated_at"])
        return response


class ChapterDeleteView(OwnedChapterMixin, SuccessMessageMixin, DeleteView):
    template_name = "courses/confirm_delete.html"

    def get_success_url(self):
        return self.object.course.get_absolute_url()

    def get_success_message(self, cleaned_data):
        return f"Chapitre « {self.object.title} » supprimé."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning"] = "Cette action est irréversible."
        context["cancel_url"] = self.object.get_absolute_url()
        return context