from django.utils import timezone

from .models import ReviewCard


def revisions_dues(request):
    """Nombre de questions à revoir aujourd'hui, pour le badge « Réviser » de l'en-tête (1 requête rapide)."""
    if not request.user.is_authenticated:
        return {}
    return {
        "nb_revisions_dues": ReviewCard.objects.filter(
            owner=request.user, due_date__lte=timezone.localdate()
        ).count()
    }