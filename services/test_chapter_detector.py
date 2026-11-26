from unittest.mock import patch

from django.test import SimpleTestCase

from .ai_provider import AIError
from .chapter_detector import detecter_titres


class FauxFournisseur:
    def __init__(self, reponse=None, erreur=None):
        self.reponse, self.erreur = reponse, erreur

    def generate_json(self, prompt, schema):
        if self.erreur:
            raise self.erreur
        return self.reponse


class DetecteurTitresTests(SimpleTestCase):
    def test_garde_seulement_des_numeros_entiers(self):
        faux = FauxFournisseur({"titres": [2, "3", True, 7]})
        with patch("services.chapter_detector.get_provider", return_value=faux):
            self.assertEqual(detecter_titres([(2, "Les sources"), (7, "Les personnes")]), [2, 7])

    def test_ia_indisponible_liste_vide(self):
        faux = FauxFournisseur(erreur=AIError("quota dépassé"))
        with patch("services.chapter_detector.get_provider", return_value=faux):
            self.assertEqual(detecter_titres([(2, "Les sources")]), [])