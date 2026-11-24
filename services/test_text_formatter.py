from django.test import SimpleTestCase, override_settings

from .text_formatter import mettre_en_forme, supprimer_repetitions


class TextFormatterTests(SimpleTestCase):
    def test_supprime_les_mots_repetes(self):
        self.assertEqual(supprimer_repetitions("je je je je deviendrai médecin"), "je deviendrai médecin")
        self.assertEqual(supprimer_repetitions("Le le cours commence"), "Le cours commence")

    def test_garde_nous_nous_et_vous_vous(self):
        self.assertEqual(supprimer_repetitions("nous nous sommes levés"), "nous nous sommes levés")

    @override_settings(AI_PROVIDER="fake")
    def test_mise_en_forme_avec_le_fournisseur_de_demo(self):
        self.assertIn("Introduction", mettre_en_forme("euh donc le cours de droit commence aujourd'hui"))