from functools import cached_property

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Count, Max
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from .forms import ChapterForm, CourseForm, CourseImportForm
from .models import Chapter, Course
from reviews.stats import progression_chapitre, progression_cours
from services.ai_provider import AIError
from services.text_formatter import MAX_CHARS, MIN_CHARS, mettre_en_forme


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


def prochaine_position(course):
    """Position du prochain chapitre (à la suite des existants)."""
    return (course.chapters.aggregate(dernier=Max("order"))["dernier"] or 0) + 1


# ------------------------------- Cours -------------------------------------

class CourseListView(OwnedCourseMixin, ListView):
    context_object_name = "courses"

    def get_queryset(self):
        return super().get_queryset().annotate(chapter_count=Count("chapters"))


class CourseCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Course
    form_class = CourseForm
    success_message = "Cours « %(title)s » créé."

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CourseDetailView(OwnedCourseMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapters"] = self.object.chapters.all()
        context["progression"] = progression_cours(self.request.user, self.object)
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
        context["warning"] = "Tous ses chapitres (et leurs fichiers) seront supprimés avec lui. Cette action est irréversible."
        context["cancel_url"] = self.object.get_absolute_url()
        return context


class CourseImportView(LoginRequiredMixin, FormView):
    """Importe un cours complet : un fichier → plusieurs chapitres d'un coup."""

    form_class = CourseImportForm
    template_name = "courses/course_import.html"

    @cached_property
    def course(self):
        return get_object_or_404(Course, pk=self.kwargs["pk"], owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.course
        return context

    def form_valid(self, form):
        debut = prochaine_position(self.course)
        chapitres = [
            Chapter(course=self.course, title=titre[:200], notes=texte, order=debut + index)
            for index, (titre, texte) in enumerate(form.sections)
        ]
        # Tout ou rien : si une insertion échoue, aucun chapitre n'est créé
        with transaction.atomic():
            Chapter.objects.bulk_create(chapitres)
            self.course.save(update_fields=["updated_at"])

        nombre = len(chapitres)
        messages.success(
            self.request,
            f"{nombre} chapitre{'s' if nombre > 1 else ''} importé{'s' if nombre > 1 else ''} "
            f"depuis « {form.cleaned_data['fichier'].name} ».",
        )
        return redirect(self.course.get_absolute_url())


# ------------------------------ Chapitres ----------------------------------

class ChapterCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Chapter
    form_class = ChapterForm
    success_message = "Chapitre « %(title)s » ajouté."

    @cached_property
    def course(self):
        return get_object_or_404(Course, pk=self.kwargs["course_pk"], owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.course
        return context

    def form_valid(self, form):
        form.instance.course = self.course   # AVANT l'enregistrement : utilisé pour le chemin du fichier
        form.instance.order = prochaine_position(self.course)
        response = super().form_valid(form)
        self.course.save(update_fields=["updated_at"])
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
        context["progression"] = progression_chapitre(self.request.user, self.object)
        return context


class ChapterUpdateView(OwnedChapterMixin, SuccessMessageMixin, UpdateView):
    form_class = ChapterForm
    success_message = "Chapitre mis à jour."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.object.course
        return context

    def form_valid(self, form):
        ancien = Chapter.objects.filter(pk=self.object.pk).values_list("source_file", flat=True).first()
        response = super().form_valid(form)
        if ancien and ancien != self.object.source_file.name:
            self.object.source_file.storage.delete(ancien)
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


class ChapterFileView(OwnedChapterMixin, DetailView):
    """Fichier source : propriétaire uniquement, puis lien SIGNÉ valable 10 minutes."""

    def get(self, request, *args, **kwargs):
        chapter = self.get_object()
        if not chapter.source_file:
            raise Http404("Ce chapitre n'a pas de fichier.")
        return redirect(chapter.source_file.url)


DELAI_MISE_EN_FORME = 10   # secondes entre deux mises en forme (protège le quota d'IA)


class FormatNotesView(LoginRequiredMixin, View):
    """Met en forme des notes dictées ou tapées. Appelée en JavaScript : répond en JSON."""

    http_method_names = ["post"]

    def post(self, request):
        texte = request.POST.get("texte", "").strip()
        if len(texte) < MIN_CHARS:
            return JsonResponse({"erreur": "Écris ou dicte d'abord quelques phrases."}, status=400)
        if len(texte) > MAX_CHARS:
            return JsonResponse({"erreur": "Texte trop long pour une mise en forme (20 000 caractères maximum)."}, status=400)
        if not cache.add(f"mise-en-forme:{request.user.pk}", 1, DELAI_MISE_EN_FORME):
            return JsonResponse({"erreur": "Patiente quelques secondes avant une nouvelle mise en forme."}, status=429)

        try:
            return JsonResponse({"texte": mettre_en_forme(texte)})
        except AIError as erreur:
            return JsonResponse({"erreur": str(erreur)}, status=503)