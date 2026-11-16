"""Statistiques de révision (fonctions pures, sans Django)."""
from datetime import timedelta

UN_JOUR = timedelta(days=1)


def compute_streak(jours, aujourd_hui):
    """
    jours : ensemble des dates où l'étudiant a révisé au moins une fois.
    Renvoie (série actuelle, meilleure série).
    La série reste « vivante » si l'on a révisé hier mais pas encore aujourd'hui.
    """
    if not jours:
        return 0, 0

    curseur = aujourd_hui if aujourd_hui in jours else aujourd_hui - UN_JOUR
    actuelle = 0
    while curseur in jours:
        actuelle += 1
        curseur -= UN_JOUR

    meilleure, courante, precedent = 0, 0, None
    for jour in sorted(jours):
        courante = courante + 1 if precedent and jour - precedent == UN_JOUR else 1
        meilleure = max(meilleure, courante)
        precedent = jour
    return actuelle, meilleure