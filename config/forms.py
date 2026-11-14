from django import forms


class StyledFormMixin:
    """
    Ajoute la classe CSS .input (définie dans app.css) aux champs de saisie.
    Les boutons radio et les cases à cocher gardent leur propre style.
    """

    SANS_STYLE = (forms.RadioSelect, forms.CheckboxInput, forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, self.SANS_STYLE):
                continue
            field.widget.attrs.setdefault("class", "input")