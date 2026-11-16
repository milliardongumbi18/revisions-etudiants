import io
import json
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from .ai_provider import AIError, GeminiProvider


def reponse_ok(data):
    """Simule une réponse HTTP 200 de Gemini contenant `data` en JSON."""
    reponse = mock.MagicMock()
    corps = {"candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}]}
    reponse.__enter__.return_value.read.return_value = json.dumps(corps).encode("utf-8")
    return reponse


def erreur_http(code):
    return urllib.error.HTTPError("https://exemple", code, "Erreur", {}, io.BytesIO(b'{"error": "surcharge"}'))


@mock.patch("services.ai_provider.time.sleep")   # aucune vraie attente pendant les tests
class GeminiRetryTests(SimpleTestCase):
    def setUp(self):
        self.fournisseur = GeminiProvider("cle-de-test", "modele-test", timeout=5)

    def test_reessaie_apres_une_surcharge_503(self, _sleep):
        with mock.patch("services.ai_provider.urllib.request.urlopen",
                        side_effect=[erreur_http(503), reponse_ok({"ok": True})]):
            with self.assertLogs("services.ai_provider", "WARNING"):
                self.assertEqual(self.fournisseur.generate_json("consigne", {}), {"ok": True})

    def test_abandonne_apres_trois_surcharges(self, _sleep):
        with mock.patch("services.ai_provider.urllib.request.urlopen", side_effect=[erreur_http(503)] * 3):
            with self.assertLogs("services.ai_provider", "WARNING"):
                with self.assertRaisesMessage(AIError, "surchargé"):
                    self.fournisseur.generate_json("consigne", {})