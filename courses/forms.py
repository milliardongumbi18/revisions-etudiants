from pathlib import Path

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import MaxLengthValidator

from core.forms import StyledFormMixin
from services.documents import MAX_TEXT_CHARS, DocumentError, extract_text_from_upload

from .models import Chapter, Course


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
            "color": forms.RadioSelect(attrs={"class": "sr-only"}),
        }


class ChapterForm(StyledFormMixin, forms.ModelForm):
    """Un chapitre se remplit en écrivant ses notes OU en important un fichier."""

    class Meta:
        model = Chapter
        fields = ("title", "source_file", "notes")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ex. Chapitre 1 — Introduction"}),
            "source_file": forms.FileInput(
                attrs={"class": "sr-only", "accept": ".pdf,.txt,application/pdf,text/plain"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 16, "placeholder": "Colle ou écris ici tes notes de cours…"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        notes = self.fields["notes"]
        notes.required = False   # notes OU fichier : vérifié dans clean()
        notes.validators.append(MaxLengthValidator(MAX_TEXT_CHARS))
        notes.widget.attrs["maxlength"] = MAX_TEXT_CHARS
        notes.help_text = "Si tu importes un fichier, son texte remplacera ce qui est écrit ici (tu pourras le corriger)."

    def clean(self):
        cleaned = super().clean()
        fichier = cleaned.get("source_file")

        # UploadedFile = un NOUVEAU fichier vient d'être envoyé (pas l'ancien déjà enregistré)
        if isinstance(fichier, UploadedFile):
            try:
                cleaned["notes"] = extract_text_from_upload(fichier)
            except DocumentError as error:
                self.add_error("source_file", str(error))
                return cleaned
            self.instance.original_filename = Path(fichier.name).name[:255]

        if not cleaned.get("notes"):
            self.add_error("notes", "Écris tes notes ou importe un fichier.")
        return cleaned