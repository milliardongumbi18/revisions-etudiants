from datetime import date

from django.test import SimpleTestCase

from .progress import evolution, tracer


class EvolutionTests(SimpleTestCase):
    def test_regroupe_les_reponses_par_semaine(self):
        aujourd_hui = date(2026, 11, 25)   # un mercredi
        reponses = [(date(2026, 11, 24), True), (date(2026, 11, 23), False), (date(2026, 11, 17), True)]
        serie = evolution(reponses, aujourd_hui, semaines=3)
        self.assertEqual([s["debut"] for s in serie], [date(2026, 11, 9), date(2026, 11, 16), date(2026, 11, 23)])
        self.assertEqual([s["taux"] for s in serie], [None, 100, 50])

    def test_tracer_place_100_en_haut_et_0_en_bas(self):
        serie = [{"debut": date(2026, 11, 2), "total": 1, "justes": 1, "taux": 100},
                 {"debut": date(2026, 11, 9), "total": 0, "justes": 0, "taux": None},
                 {"debut": date(2026, 11, 16), "total": 1, "justes": 0, "taux": 0}]
        courbe = tracer(serie)
        self.assertEqual(courbe["semaines"][0]["y"], "0")       # 100 % → tout en haut
        self.assertEqual(courbe["semaines"][2]["y"], "100")     # 0 % → tout en bas
        self.assertEqual(courbe["semaines"][2]["x"], "100")     # dernière semaine → tout à droite
        self.assertIsNone(courbe["semaines"][1]["y"])
        self.assertEqual(len(courbe["trace"].split()), 2)   # la semaine vide n'est pas tracée

    def test_coordonnees_avec_un_point_decimal(self):
        serie = [{"debut": date(2026, 11, 2), "total": 3, "justes": 1, "taux": 33}] * 8
        courbe = tracer(serie)
        self.assertEqual(courbe["semaines"][1]["x"], "14.29")   # jamais « 14,29 »
        self.assertNotIn(",", courbe["semaines"][1]["x"])