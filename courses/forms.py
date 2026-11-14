from django import forms
from django.core.validators import MaxLengthValidator

from core.forms import StyledFormMixin

from .models import Chapter, Course

NOTES_MAX = 50_000  # caractères : limite raisonnable (et protège la future génération IA)


class CourseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ("title", "description", "outline", "color")   # jamais "owner" !
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ex. Droit constitutionnel"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "En quelques mots : de quoi parle ce cours ?"}
            ),
            "outline": forms.Textarea(
                attrs={"rows": 6, "placeholder": "I. Introduction\nII. Les sources du droit\nIII. ..."}
            ),
            # Boutons radio cachés visuellement : on affiche des pastilles de couleur à la place
            "color": forms.RadioSelect(attrs={"class": "sr-only"}),
        }


class ChapterForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ("title", "notes")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ex. Chapitre 1 — Introduction"}),
            "notes": forms.Textarea(
                attrs={"rows": 16, "placeholder": "Colle ou écris ici tes notes de cours…"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        notes = self.fields["notes"]
        notes.required = True  # pour l'instant, un chapitre = des notes
        notes.validators.append(MaxLengthValidator(NOTES_MAX))
        notes.widget.attrs["maxlength"] = NOTES_MAX
        notes.help_text = f"{NOTES_MAX:,} caractères maximum.".replace(",", " ")