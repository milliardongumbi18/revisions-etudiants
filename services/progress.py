"""
Évolution de la réussite semaine par semaine, et tracé de la courbe en SVG.
Fonctions pures (sans Django) : faciles à tester.
"""
from datetime import timedelta

SEMAINES = 8
LARGEUR, HAUTEUR = 560, 180       # repère du dessin SVG (viewBox), pas des pixels réels
MARGE_X, MARGE_Y = 52, 16


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


def _y(taux):
    """0 % en bas, 100 % en haut."""
    return round(MARGE_Y + (100 - taux) * (HAUTEUR - 2 * MARGE_Y) / 100, 1)


def tracer(serie):
    """Ajoute les coordonnées SVG à chaque semaine et prépare la ligne de la courbe."""
    pas = (LARGEUR - MARGE_X - 16) / max(1, len(serie) - 1)
    semaines = []
    for index, semaine in enumerate(serie):
        point = dict(semaine)
        point["x"] = round(MARGE_X + index * pas, 1)
        point["y"] = None if semaine["taux"] is None else _y(semaine["taux"])
        semaines.append(point)
    avec_donnees = [p for p in semaines if p["y"] is not None]
    return {
        "semaines": semaines,
        "trace": " ".join(f"{p['x']},{p['y']}" for p in avec_donnees),
        "a_des_donnees": bool(avec_donnees),
        "largeur": LARGEUR,
        "hauteur": HAUTEUR,
        "grille": [{"y": _y(valeur), "valeur": valeur} for valeur in (100, 50, 0)],
    }