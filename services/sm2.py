"""
Algorithme SM-2 (SuperMemo 2, Piotr Woźniak, 1987) : calcule quand revoir une question.

Après chaque réponse, une note de 0 à 5 :
  - note < 3  : raté   → la série repart de zéro, la question revient demain ;
  - note ≥ 3  : réussi → l'intervalle grandit : 1 jour, puis 6 jours, puis × facilité.
La « facilité » (2,5 au départ, jamais sous 1,3) baisse quand on peine, monte quand c'est facile.
Fonction pure (aucune dépendance à Django) : facile à tester et à expliquer.
"""
from dataclasses import dataclass

EASINESS_DEFAULT = 2.5
EASINESS_MIN = 1.3


@dataclass(frozen=True)
class SM2State:
    easiness: float = EASINESS_DEFAULT
    interval: int = 0       # jours avant la prochaine révision
    repetitions: int = 0    # réussites d'affilée


def review(state, grade):
    """Renvoie le NOUVEL état après une réponse notée `grade` (0 à 5)."""
    if not 0 <= grade <= 5:
        raise ValueError("La note doit être comprise entre 0 et 5.")

    if grade < 3:
        repetitions, interval = 0, 1
    else:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = max(1, round(state.interval * state.easiness))
        repetitions = state.repetitions + 1

    # Formule originale de SM-2 : +0,1 pour « parfait », jusqu'à −0,8 pour « blackout total »
    easiness = state.easiness + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    return SM2State(easiness=max(EASINESS_MIN, round(easiness, 2)), interval=interval, repetitions=repetitions)