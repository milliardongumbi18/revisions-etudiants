from django.shortcuts import render


def home(request):
    """Page d'accueil publique."""
    return render(request, "core/home.html")