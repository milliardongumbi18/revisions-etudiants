from django import forms
from django.utils import timezone

from core.forms import StyledFormMixin
from courses.models import Course

from .models import ClassSlot, Exam


class ClassSlotForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ClassSlot
        fields = ("course", "label", "weekday", "start_time", "end_time")
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ex. Anglais (si le cours n'est pas dans l'application)"}),
            "data-off-when": "id_course",   # grisé par app.js dès qu'un cours est choisi
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Sécurité : seuls MES cours sont proposés (et acceptés) dans la liste
        self.fields["course"].queryset = Course.objects.filter(owner=user)
        self.fields["course"].empty_label = "— Aucun (saisir un intitulé) —"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("course"):
            cleaned["label"] = ""   # un cours est choisi : l'intitulé ne sert à rien
        if not cleaned.get("course") and not (cleaned.get("label") or "").strip():
            self.add_error("label", "Choisis un cours ou saisis un intitulé.")

        debut, fin, jour = cleaned.get("start_time"), cleaned.get("end_time"), cleaned.get("weekday")
        if debut and fin:
            if fin <= debut:
                self.add_error("end_time", "L'heure de fin doit être après l'heure de début.")
            elif jour is not None:
                # Deux créneaux se chevauchent si l'un commence avant que l'autre ne finisse
                chevauchement = ClassSlot.objects.filter(
                    owner=self.user, weekday=jour, start_time__lt=fin, end_time__gt=debut
                ).exclude(pk=self.instance.pk)
                if chevauchement.exists():
                    self.add_error("start_time", "Ce créneau chevauche un autre cours le même jour.")
        return cleaned


class ExamForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Exam
        fields = ("kind", "course", "date", "title")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "title": forms.TextInput(attrs={"placeholder": "Ex. Interro du chapitre 2 (facultatif)"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.filter(owner=user)

    def clean_date(self):
        jour = self.cleaned_data["date"]
        if jour < timezone.localdate() and not self.instance.pk:
            raise forms.ValidationError("Cette date est déjà passée.")
        return jour