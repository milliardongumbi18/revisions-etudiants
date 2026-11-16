"""
Couche d'abstraction pour l'IA.

Le reste de l'application appelle seulement :
    get_provider().generate_json(consigne, schema)
Changer de fournisseur (Gemini → Groq…) = ajouter une classe ici et changer
la variable d'environnement AI_PROVIDER. Aucune vue à modifier.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Erreur compréhensible par l'étudiant (affichée dans un message)."""


class AIProvider:
    """Contrat commun à tous les fournisseurs."""

    label = "IA"

    def generate_json(self, prompt, schema):
        """Envoie `prompt`, renvoie un dict Python qui respecte `schema`. Lève AIError en cas d'échec."""
        raise NotImplementedError


class GeminiProvider(AIProvider):
    """Gemini via l'API REST generateContent, avec sortie JSON imposée par un schéma."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key, model, timeout):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.label = f"Gemini · {model}"

    def generate_json(self, prompt, schema):
        if not self.api_key:
            raise AIError("La génération de quiz n'est pas encore configurée (clé API manquante).")

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",   # réponse en JSON...
                "responseSchema": schema,                 # ...qui respecte NOTRE structure
                "temperature": 0.4,                        # peu de fantaisie : on veut du fiable
            },
        }
        request = urllib.request.Request(
            self.URL.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            logger.warning("Gemini HTTP %s : %s", exc.code, detail)   # la clé n'est jamais journalisée
            raise AIError(self._message_http(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("Gemini injoignable : %s", exc)
            raise AIError("Impossible de joindre le service d'IA (connexion coupée ou délai dépassé). Réessaie.") from exc

        try:
            parts = payload["candidates"][0]["content"]["parts"]
            texte = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            return json.loads(texte)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Réponse Gemini inattendue : %s", str(payload)[:500])
            raise AIError("La réponse de l'IA était incomplète. Réessaie.") from exc

    def _message_http(self, code):
        if code == 429:
            return "Limite de l'offre gratuite atteinte (trop de demandes rapprochées). Réessaie dans une minute."
        if code in (401, 403):
            return "Clé API refusée : vérifie GEMINI_API_KEY."
        if code == 404:
            return f"Modèle « {self.model} » introuvable : vérifie GEMINI_MODEL."
        if code == 400:
            return "Demande refusée par l'IA : vérifie la clé API, ou le chapitre est peut-être trop long."
        return "Le service d'IA est momentanément indisponible. Réessaie plus tard."


class FakeProvider(AIProvider):
    """Fournisseur de démonstration : aucune requête réseau (tests, CI, travail hors connexion)."""

    label = "Démo (sans IA)"

    def generate_json(self, prompt, schema):
        qcm = [
            {
                "type": "qcm",
                "question": f"Question de démonstration n°{numero} ?",
                "choix": ["Réponse A", "Réponse B", "Réponse C", "Réponse D"],
                "bonne_reponse": 1,
                "explication": "Explication de démonstration.",
            }
            for numero in range(1, 4)
        ]
        courtes = [
            {
                "type": "courte",
                "question": f"Question courte de démonstration n°{numero} ?",
                "reponse_attendue": "Réponse attendue de démonstration.",
                "explication": "Explication de démonstration.",
            }
            for numero in range(1, 3)
        ]
        return {"questions": qcm + courtes}


def get_provider():
    """Renvoie le fournisseur choisi par la configuration (AI_PROVIDER)."""
    nom = getattr(settings, "AI_PROVIDER", "gemini")
    if nom == "fake":
        return FakeProvider()
    if nom == "gemini":
        return GeminiProvider(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.AI_TIMEOUT)
    raise AIError(f"Fournisseur d'IA inconnu : {nom}")