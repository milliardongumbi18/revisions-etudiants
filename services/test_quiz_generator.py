from unittest import mock

from django.test import SimpleTestCase

from .ai_provider import AIError
from .quiz_generator import generate_quiz


class FauxFournisseur:
    """Simule une réponse d'IA choisie par le test."""

    label = "Faux"

    def __init__(self, data):
        self.data = data

    def generate_json(self, prompt, schema):
        return self.data


class QuizGeneratorTests(SimpleTestCase):
    def test_les_questions_invalides_sont_ecartees(self):
        data = {"questions": [
            {"type": "qcm", "question": "Q1 ?", "choix": ["a", "b", "c", "d"], "bonne_reponse": 2, "explication": "e"},
            {"type": "qcm", "question": "Q2 ?", "choix": ["a", "b"], "bonne_reponse": 5, "explication": "e"},  # index hors limites
            {"type": "courte", "question": "Q3 ?", "reponse_attendue": "r", "explication": "e"},
            {"type": "courte", "question": "Q4 ?", "reponse_attendue": "", "explication": "e"},                # sans réponse
            {"type": "inconnu", "question": "Q5 ?"},                                                           # type inconnu
            {"type": "qcm", "question": "Q6 ?", "choix": ["a", "b", "c"], "bonne_reponse": 0, "explication": "e"},
        ]}
        with mock.patch("services.quiz_generator.get_provider", return_value=FauxFournisseur(data)):
            questions, _ = generate_quiz("Titre", "Texte du cours")
        self.assertEqual([q["text"] for q in questions], ["Q1 ?", "Q3 ?", "Q6 ?"])

    def test_trop_peu_de_questions_valides(self):
        data = {"questions": [{"type": "courte", "question": "Q ?", "reponse_attendue": "r", "explication": "e"}]}
        with mock.patch("services.quiz_generator.get_provider", return_value=FauxFournisseur(data)):
            with self.assertRaises(AIError):
                generate_quiz("Titre", "Texte du cours")