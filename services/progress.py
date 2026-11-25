"""
Évolution de la réussite semaine par semaine, et coordonnées de la courbe.
Fonctions pures (sans Django) : faciles à tester.
"""
from datetime import timedelta

SEMAINES = 8


def debut_semaine(jour):
    """Le lundi de la semaine de `jour`."""
    return jour - timedelta(days=jour.weekday())


def evolution(reponses, aujourd_hui, semaines=SEMAINES):
    """
    reponses : liste de (date, correcte).
    Renvoie une entrée par semaine, de la plus ancienne à la plus récente :
    {"debut": lundi, "total": n, "justes": n, "taux": % ou None si aucune réponse}.
    """
    debuts = [debut_semaine(aujourd_hui) - timedelta(weeks=k) for k in range(semaines - 1, -1, -1)]
    compte = {debut: [0, 0] for debut in debuts}
    for jour, correcte in reponses:
        debut = debut_semaine(jour)
        if debut in compte:
            compte[debut][0] += 1
            compte[debut][1] += int(bool(correcte))
    return [
        {"debut": debut, "total": total, "justes": justes, "taux": round(100 * justes / total) if total else None}
        for debut, (total, justes) in compte.items()
    ]


def _pct(valeur):
    """
    Nombre → texte avec un POINT décimal (« 14.29 »).
    Indispensable : en français, le gabarit écrirait « 14,29 », que le CSS et le SVG ne comprennent pas.
    """
    return f"{valeur:.2f}".rstrip("0").rstrip(".")


def tracer(serie):
    """
    Coordonnées en pourcentage (0 à 100) : le graphique s'adapte à toutes les largeurs d'écran.
    x : 0 = semaine la plus ancienne, 100 = cette semaine ; y : 0 = 100 % (en haut), 100 = 0 % (en bas).
    """
    pas = 100 / max(1, len(serie) - 1)
    semaines = []
    for index, semaine in enumerate(serie):
        point = dict(semaine)
        point["x"] = _pct(index * pas)
        point["y"] = None if semaine["taux"] is None else _pct(100 - semaine["taux"])
        semaines.append(point)
    avec_donnees = [p for p in semaines if p["y"] is not None]
    return {
        "semaines": semaines,
        "trace": " ".join(f"{p['x']},{p['y']}" for p in avec_donnees),
        "a_des_donnees": bool(avec_donnees),
        "grille": [{"y": _pct(100 - valeur), "valeur": valeur} for valeur in (100, 50, 0)],
    }