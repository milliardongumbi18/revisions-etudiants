from django.shortcuts import redirect, render
from django.templatetags.static import static


def home(request):
    """Page d'accueil publique."""
    return render(request, "core/home.html")


def favicon(request):
    """Les navigateurs demandent /favicon.ico : on les renvoie vers notre icône SVG."""
    return redirect(static("img/favicon.svg"), permanent=True)