"""
Documents envoyés par les étudiants : vérification puis extraction du texte.

Aucune dépendance à Django ici : facile à tester et réutilisable
(import de cours complet, génération de quiz).
"""
import re
from pathlib import Path

from pypdf import PdfReader

MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 Mo
MAX_PDF_PAGES = 300
MAX_TEXT_CHARS = 100_000
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class DocumentError(Exception):
    """Erreur compréhensible par l'étudiant (affichée sous le champ fichier)."""


def extract_text_from_upload(uploaded_file):
    """Vérifie le fichier envoyé et renvoie son texte nettoyé. Lève DocumentError sinon."""
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentError("Format non accepté : envoie un fichier PDF ou .txt.")
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise DocumentError("Fichier trop lourd : 10 Mo maximum.")

    uploaded_file.seek(0)
    text = _extract_pdf(uploaded_file) if extension == ".pdf" else _extract_txt(uploaded_file)
    uploaded_file.seek(0)   # on rembobine : le fichier sera ensuite enregistré en entier

    text = _clean(text)
    if not text:
        raise DocumentError(
            "Aucun texte lisible dans ce fichier. S'il s'agit d'un PDF scanné "
            "(des photos de pages), son texte ne peut pas être extrait."
        )
    if len(text) > MAX_TEXT_CHARS:
        raise DocumentError(
            f"Texte trop long ({len(text):,} caractères, maximum {MAX_TEXT_CHARS:,}). "
            "Découpe le fichier en plusieurs chapitres.".replace(",", " ")
        )
    return text


def _extract_pdf(file):
    # On ne fait pas confiance à l'extension : un vrai PDF commence toujours par « %PDF- ».
    if file.read(5) != b"%PDF-":
        raise DocumentError("Ce fichier n'est pas un vrai PDF.")
    file.seek(0)
    try:
        reader = PdfReader(file)
        if reader.is_encrypted:
            raise DocumentError("Ce PDF est protégé par un mot de passe : retire la protection puis réessaie.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentError(f"PDF trop long : {MAX_PDF_PAGES} pages maximum.")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except DocumentError:
        raise
    except Exception as exc:   # pypdf lève des erreurs variées sur un fichier abîmé
        raise DocumentError("PDF illisible ou endommagé.") from exc


def _extract_txt(file):
    raw = file.read()
    if b"\x00" in raw:
        raise DocumentError(
            "Ce fichier .txt n'est pas un texte simple (ou il est enregistré en UTF-16) : "
            "réenregistre-le en UTF-8."
        )
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentError("Encodage du texte non reconnu : réenregistre-le en UTF-8.")


def _clean(text):
    """Normalise les fins de ligne et supprime les espaces / lignes vides en trop."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()