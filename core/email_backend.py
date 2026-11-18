"""
Envoi des e-mails par l'API HTTPS de Brevo.
Render (offre gratuite) bloque les ports SMTP 25, 465 et 587 : on passe donc par HTTPS (port 443).
Django appelle ce moteur via EMAIL_BACKEND ; le reste du code utilise send_mail() normalement.
"""
import json
import logging
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

URL_BREVO = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        envoyes = 0
        for message in email_messages:
            try:
                self._envoyer(message)
                envoyes += 1
            except Exception:
                logger.exception("Échec d'envoi d'un e-mail via Brevo")   # visible dans Render → Logs
                if not self.fail_silently:
                    raise
        return envoyes

    def _envoyer(self, message):
        nom, adresse = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        corps = {
            "sender": {"name": nom or "Révisions Étudiants", "email": adresse},
            "to": [{"email": parseaddr(destinataire)[1]} for destinataire in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        for contenu, type_mime in getattr(message, "alternatives", []):
            if type_mime == "text/html":
                corps["htmlContent"] = contenu

        requete = urllib.request.Request(
            URL_BREVO,
            data=json.dumps(corps).encode("utf-8"),
            headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(requete, timeout=15) as reponse:
            reponse.read()