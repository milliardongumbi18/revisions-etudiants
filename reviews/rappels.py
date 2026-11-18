"""
Rappels quotidiens par e-mail.
Lancés chaque matin par GitHub Actions : python manage.py envoyer_rappels
"""
from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.demo import est_compte_demo

from .models import ReviewCard

SEL_DESINSCRIPTION = "rappels-desinscription"   # « sel » propre à cet usage : un jeton ne sert qu'ici
MAX_COURS_LISTES = 5


def lien_desinscription(user):
    """Lien signé : impossible à fabriquer pour un autre compte sans la SECRET_KEY."""
    jeton = signing.dumps(user.pk, salt=SEL_DESINSCRIPTION)
    return settings.SITE_URL + reverse("accounts:reminders_unsubscribe", args=[jeton])


def envoyer_rappels(aujourd_hui=None):
    """Envoie un rappel à chaque étudiant volontaire qui a des révisions dues. Renvoie le nombre d'e-mails envoyés."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    envoyes = 0

    destinataires = (
        User.objects.filter(daily_reminder=True, is_active=True)
        .exclude(email="")
        .exclude(last_reminder_sent=aujourd_hui)   # jamais deux rappels le même jour
    )
    for user in destinataires:
        if est_compte_demo(user):
            continue

        par_cours = list(
            ReviewCard.objects.filter(owner=user, due_date__lte=aujourd_hui)
            .values(titre=F("question__quiz__chapter__course__title"))
            .annotate(n=Count("id"))
            .order_by("-n", "titre")
        )
        total = sum(ligne["n"] for ligne in par_cours)
        if not total:
            continue   # rien à réviser : on ne dérange pas

        contexte = {
            "user": user,
            "total": total,
            "par_cours": par_cours[:MAX_COURS_LISTES],
            "autres_cours": max(0, len(par_cours) - MAX_COURS_LISTES),
            "lien_revisions": settings.SITE_URL + reverse("reviews:home"),
            "lien_desinscription": lien_desinscription(user),
        }
        sujet = f"{total} révision{'s' if total > 1 else ''} t'attend{'ent' if total > 1 else ''} aujourd'hui"
        message = EmailMultiAlternatives(
            sujet, render_to_string("reviews/emails/rappel.txt", contexte), settings.DEFAULT_FROM_EMAIL, [user.email]
        )
        message.attach_alternative(render_to_string("reviews/emails/rappel.html", contexte), "text/html")

        if message.send(fail_silently=True):   # échec : enregistré dans les journaux, on passe au suivant
            User.objects.filter(pk=user.pk).update(last_reminder_sent=aujourd_hui)
            envoyes += 1
    return envoyes