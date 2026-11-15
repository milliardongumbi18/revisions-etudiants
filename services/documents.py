"""
Documents envoyés par les étudiants : vérification, extraction et découpage du texte.

Aucune dépendance à Django ici : facile à tester et réutilisable
(import d'un chapitre, import d'un cours complet, génération de quiz).
"""
import re
from pathlib import Path

from pypdf import PdfReader

MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 Mo
MAX_PDF_PAGES = 300
MAX_TEXT_CHARS = 100_000             # taille maximale d'UN chapitre
MAX_CHAPTERS = 100                   # nombre maximal de chapitres créés par un import
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

TEXTE_VIDE = (
    "Aucun texte lisible dans ce fichier. S'il s'agit d'un PDF scanné "
    "(des photos de pages), son texte ne peut pas être extrait."
)


class DocumentError(Exception):
    """Erreur compréhensible par l'étudiant (affichée sous le champ fichier)."""


# ============================== API publique ===============================

def extract_text_from_upload(uploaded_file):
    """Import d'UN chapitre : vérifie le fichier et renvoie tout son texte nettoyé."""
    extension = _check_upload(uploaded_file)
    if extension == ".pdf":
        text = "\n\n".join(_page_texts(_open_pdf(uploaded_file)))
    else:
        text = _read_txt(uploaded_file)
    uploaded_file.seek(0)   # on rembobine : le fichier sera ensuite enregistré en entier

    text = _clean(text)
    if not text:
        raise DocumentError(TEXTE_VIDE)
    if len(text) > MAX_TEXT_CHARS:
        raise DocumentError(
            f"Texte trop long ({len(text):,} caractères, maximum {MAX_TEXT_CHARS:,}). "
            "Utilise plutôt « Importer un cours complet », qui découpe automatiquement.".replace(",", " ")
        )
    return text


def split_document(uploaded_file):
    """
    Import d'un COURS COMPLET : renvoie une liste de (titre, texte), un élément par chapitre.
    - PDF avec signets : un chapitre par signet de premier niveau.
    - Sinon : un chapitre « Cours complet ».
    - Tout chapitre trop long est découpé en « … — partie 1, 2, 3 ».
    """
    extension = _check_upload(uploaded_file)
    if extension == ".pdf":
        reader = _open_pdf(uploaded_file)
        pages = [_clean(texte) for texte in _page_texts(reader)]
        sections = _sections_from_bookmarks(reader, pages) or [("Cours complet", pages)]
    else:
        texte = _clean(_read_txt(uploaded_file))
        sections = [("Cours complet", texte.split("\n\n"))]   # blocs = paragraphes
    uploaded_file.seek(0)

    chapitres = []
    for titre, blocs in sections:
        chapitres.extend(_pack(titre, blocs))

    if not chapitres:
        raise DocumentError(TEXTE_VIDE)
    if len(chapitres) > MAX_CHAPTERS:
        raise DocumentError(f"Ce fichier donnerait plus de {MAX_CHAPTERS} chapitres : découpe-le d'abord.")
    return chapitres


# ============================ Vérifications ================================

def _check_upload(uploaded_file):
    """Extension autorisée + taille raisonnable. Renvoie l'extension."""
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentError("Format non accepté : envoie un fichier PDF ou .txt.")
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise DocumentError("Fichier trop lourd : 10 Mo maximum.")
    uploaded_file.seek(0)
    return extension


def _open_pdf(file):
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
        return reader
    except DocumentError:
        raise
    except Exception as exc:   # pypdf lève des erreurs variées sur un fichier abîmé
        raise DocumentError("PDF illisible ou endommagé.") from exc


def _page_texts(reader):
    """Texte de chaque page (liste, dans l'ordre)."""
    try:
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise DocumentError("PDF illisible ou endommagé.") from exc


def _read_txt(file):
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


# =============================== Découpage =================================

def _sections_from_bookmarks(reader, pages):
    """
    Signets de premier niveau → [(titre, [textes des pages])].
    Renvoie une liste vide s'il n'y a pas au moins 2 signets exploitables.
    """
    try:
        outline = reader.outline
    except Exception:
        return []

    debuts = []   # [(titre, numéro de la première page)]
    for item in outline:
        if isinstance(item, list):   # sous-signets : on garde seulement le 1er niveau
            continue
        try:
            page = reader.get_destination_page_number(item)
        except Exception:
            continue
        titre = (getattr(item, "title", "") or "").strip()
        if page is None or page < 0 or not titre:
            continue
        if debuts and page <= debuts[-1][1]:   # même page que le précédent (ou désordre) : ignoré
            continue
        debuts.append((titre[:200], page))

    if len(debuts) < 2:   # un seul signet ne permet pas de découper
        return []

    sections = []
    if debuts[0][1] > 0:   # pages avant le 1er signet (page de garde, sommaire…)
        sections.append(("Introduction", pages[: debuts[0][1]]))
    for index, (titre, debut) in enumerate(debuts):
        fin = debuts[index + 1][1] if index + 1 < len(debuts) else len(pages)
        sections.append((titre, pages[debut:fin]))
    return sections


def _pack(titre, blocs):
    """
    Regroupe des blocs (pages ou paragraphes) en chapitres de MAX_TEXT_CHARS au plus.
    Un seul morceau → [(titre, texte)] ; plusieurs → « titre — partie N ».
    """
    parties, courant = [], ""
    for bloc in blocs:
        bloc = bloc.strip()
        if not bloc:
            continue
        while len(bloc) > MAX_TEXT_CHARS:   # bloc géant (rare) : coupé net
            if courant:
                parties.append(courant)
                courant = ""
            parties.append(bloc[:MAX_TEXT_CHARS])
            bloc = bloc[MAX_TEXT_CHARS:]
        if courant and len(courant) + 2 + len(bloc) > MAX_TEXT_CHARS:
            parties.append(courant)
            courant = bloc
        else:
            courant = f"{courant}\n\n{bloc}" if courant else bloc
    if courant:
        parties.append(courant)

    if len(parties) <= 1:
        return [(titre, partie) for partie in parties]
    return [(f"{titre} — partie {numero}", partie) for numero, partie in enumerate(parties, start=1)]


def _clean(text):
    """Normalise les fins de ligne et supprime les espaces / lignes vides en trop."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()