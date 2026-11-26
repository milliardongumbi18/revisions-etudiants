"""
Documents envoyés par les étudiants : vérification, extraction et découpage du texte.

Formats acceptés : PDF, Word (.docx), PowerPoint (.pptx) et texte (.txt).
Aucune dépendance à Django ici : facile à tester et réutilisable
(import d'un chapitre, import d'un cours complet, génération de quiz).
"""
import posixpath
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 Mo
MAX_PDF_PAGES = 300
MAX_TEXT_CHARS = 100_000             # taille maximale d'UN chapitre
MAX_CHAPTERS = 100                   # nombre maximal de chapitres créés par un import
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".pptx"}
ANCIENS_FORMATS = {".doc", ".ppt", ".odt", ".odp", ".rtf"}

# Protection contre les « bombes ZIP » (un petit fichier qui se décompresse en plusieurs Go)
MAX_UNZIPPED_SIZE = 50 * 1024 * 1024   # 50 Mo une fois décompressé
MAX_ZIP_MEMBERS = 3000
MAX_SLIDES = 500

TEXTE_VIDE = (
    "Aucun texte lisible dans ce fichier. S'il s'agit d'un PDF scanné "
    "(des photos de pages), son texte ne peut pas être extrait."
)

# Espaces de noms XML d'Office (un .docx / .pptx est un ZIP de fichiers XML)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
P14 = "{http://schemas.microsoft.com/office/powerpoint/2010/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"

STYLE_TITRE = re.compile(r"^(?:heading|titre)\s*([1-9])$", re.IGNORECASE)   # « Heading1 », « Titre 1 »…
DIAPO = re.compile(r"^ppt/slides/slide\d+\.xml$")
MIN_INTRODUCTION = 200   # en dessous, le texte avant le 1er titre est une simple page de garde

# Découpage d'un texte sans structure (étape 13f)
MIN_SECTION = 200          # un chapitre de moins de 200 caractères = sans doute une ligne du sommaire
MIN_TEXTE_IA = 15_000      # en dessous, inutile de découper (et d'utiliser l'IA)
MAX_CANDIDATS_IA = 800     # lignes envoyées à l'IA au maximum
SOMMAIRE = re.compile(r"(\.{3,}|…|_{3,}|\s{4,}|\t)\s*\d{1,4}\s*$")   # « Les sources ........ 12 »
NUMEROTATION = re.compile(   # « chapitre 1 », « partie ii », « 3 », « b »… en tête de titre (texte déjà normalisé)
    r"^(?:(?:chapitre|chap|partie|titre|section|lecon|module|theme|unite|sequence)\s+)?"
    r"(?:\d+|(?=[ivx])x{0,3}(?:ix|iv|v?i{0,3})|premier|premiere|[a-z])\s+(?=\S)"
)
MOT_CHAPITRE = re.compile(
    r"^\s*(chapitre|partie|le[cç]on|module|th[eè]me|unit[eé]|s[eé]quence)\s+(\d+|[IVXLC]+|premi[eè]re?)\b",
    re.IGNORECASE,
)


class DocumentError(Exception):
    """Erreur compréhensible par l'étudiant (affichée sous le champ fichier)."""


# ============================== API publique ===============================

def extract_text_from_upload(uploaded_file):
    """Import d'UN chapitre : vérifie le fichier et renvoie tout son texte nettoyé."""
    extension = _check_upload(uploaded_file)
    if extension == ".pdf":
        text = "\n\n".join(_page_texts(_open_pdf(uploaded_file)))
    elif extension == ".docx":
        text = "\n\n".join(texte for _, texte in _docx_paragraphs(_open_office(uploaded_file, ".docx")))
    elif extension == ".pptx":
        _, diapos = _pptx_slides(_open_office(uploaded_file, ".pptx"))
        text = "\n\n".join(texte for _, texte in diapos)
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


def split_document(uploaded_file, plan="", ia=None):
    """
    Import d'un COURS COMPLET : renvoie une liste de (titre, texte), un élément par chapitre.

    1. La structure du fichier, si elle existe : signets du PDF, titres Word, sections PowerPoint.
    2. Sinon, le texte est découpé (voir _decouper_texte) :
       selon le PLAN du cours, puis selon les titres « Chapitre 1 », « Partie 2 »…,
       et en dernier recours avec `ia`, une fonction qui choisit les titres parmi les lignes.
    3. Rien trouvé : un chapitre « Cours complet ».
    Tout chapitre trop long est découpé en « … — partie 1, 2, 3 ».
    """
    extension = _check_upload(uploaded_file)
    if extension == ".pdf":
        reader = _open_pdf(uploaded_file)
        pages = [_clean(texte) for texte in _page_texts(reader)]
        sections = _sections_from_bookmarks(reader, pages) or _decouper_texte("\n\n".join(pages), plan, ia)
    elif extension == ".docx":
        paragraphes = _docx_paragraphs(_open_office(uploaded_file, ".docx"))
        sections = _sections_from_headings(paragraphes) or _decouper_texte(
            "\n\n".join(t for _, t in paragraphes), plan, ia
        )
    elif extension == ".pptx":
        presentation, diapos = _pptx_slides(_open_office(uploaded_file, ".pptx"))
        sections = _sections_from_pptx(presentation, diapos) or _decouper_texte(
            "\n\n".join(t for _, t in diapos), plan, ia
        )
    else:
        sections = _decouper_texte(_clean(_read_txt(uploaded_file)), plan, ia)
    uploaded_file.seek(0)

    chapitres = []
    for titre, blocs in sections:
        chapitres.extend(_pack(titre, [_clean(bloc) for bloc in blocs]))

    if not chapitres:
        raise DocumentError(TEXTE_VIDE)
    if len(chapitres) > MAX_CHAPTERS:
        raise DocumentError(f"Ce fichier donnerait plus de {MAX_CHAPTERS} chapitres : découpe-le d'abord.")
    return chapitres


# ============================ Vérifications ================================

def _check_upload(uploaded_file):
    """Extension autorisée + taille raisonnable. Renvoie l'extension."""
    extension = Path(uploaded_file.name).suffix.lower()
    if extension in ANCIENS_FORMATS:
        raise DocumentError(
            "Ce format n'est pas accepté : enregistre ton fichier en .docx (Word) ou .pptx (PowerPoint), "
            "ou exporte-le en PDF."
        )
    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentError("Format non accepté : envoie un fichier PDF, Word (.docx), PowerPoint (.pptx) ou .txt.")
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


# ======================== Word et PowerPoint (ZIP) =========================

def _open_office(file, extension):
    """Ouvre un .docx / .pptx après avoir vérifié que c'est un vrai ZIP, sans bombe."""
    nom = "Word" if extension == ".docx" else "PowerPoint"
    # Un vrai .docx / .pptx commence par « PK » (signature ZIP). Un document protégé
    # par mot de passe est enregistré autrement : il est refusé ici aussi.
    if file.read(4) != b"PK\x03\x04":
        raise DocumentError(
            f"Ce fichier n'est pas un vrai document {nom} (ou il est protégé par un mot de passe)."
        )
    file.seek(0)
    try:
        archive = zipfile.ZipFile(file)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentError(f"Document {nom} illisible ou endommagé.") from exc

    infos = archive.infolist()
    # Taille annoncée de chaque fichier interne : zipfile refuse ensuite d'en lire davantage
    if len(infos) > MAX_ZIP_MEMBERS or sum(info.file_size for info in infos) > MAX_UNZIPPED_SIZE:
        raise DocumentError(f"Document {nom} trop volumineux une fois décompressé.")

    principal = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
    if principal not in archive.namelist():
        raise DocumentError(f"Ce fichier n'est pas un vrai document {nom}.")
    return archive


def _xml(archive, nom):
    """Lit et analyse un fichier XML du document, en refusant les pièges."""
    try:
        donnees = archive.read(nom)
    except (KeyError, zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError) as exc:
        raise DocumentError("Document incomplet ou endommagé.") from exc
    # Les fichiers Office n'ont jamais de DOCTYPE : s'il y en a un, c'est une tentative
    # d'attaque XML (entités qui se multiplient, lecture de fichiers du serveur…).
    if b"<!DOCTYPE" in donnees or b"<!ENTITY" in donnees:
        raise DocumentError("Document refusé : contenu XML suspect.")
    try:
        return ElementTree.fromstring(donnees)
    except ElementTree.ParseError as exc:
        raise DocumentError("Document incomplet ou endommagé.") from exc


def _sans_variantes(element):
    """Parcourt l'arbre en sautant les « variantes de secours » (sinon certains textes seraient doublés)."""
    for enfant in element:
        if enfant.tag == MC_FALLBACK:
            continue
        yield enfant
        yield from _sans_variantes(enfant)


def _texte_paragraphe_word(paragraphe):
    morceaux = []

    def parcourir(element):
        for enfant in element:
            if enfant.tag in (f"{W}p", MC_FALLBACK):   # paragraphe imbriqué (zone de texte) : lu à part
                continue
            if enfant.tag == f"{W}t":
                morceaux.append(enfant.text or "")
            elif enfant.tag == f"{W}tab":
                morceaux.append(" ")
            elif enfant.tag in (f"{W}br", f"{W}cr"):
                morceaux.append("\n")
            parcourir(enfant)

    parcourir(paragraphe)
    return "".join(morceaux).strip()


def _niveau_titre_word(paragraphe):
    """1 pour « Titre 1 », 2 pour « Titre 2 »… 0 pour un paragraphe normal."""
    proprietes = paragraphe.find(f"{W}pPr")
    if proprietes is None:
        return 0
    style = proprietes.find(f"{W}pStyle")
    if style is not None:
        trouve = STYLE_TITRE.match((style.get(f"{W}val") or "").strip())
        if trouve:
            return int(trouve.group(1))
    plan = proprietes.find(f"{W}outlineLvl")   # niveau hiérarchique défini à la main (0 = niveau 1)
    if plan is not None and (plan.get(f"{W}val") or "").isdigit():
        niveau = int(plan.get(f"{W}val")) + 1
        return niveau if niveau <= 9 else 0
    return 0


def _docx_paragraphs(archive):
    """[(niveau de titre, texte)] pour chaque paragraphe non vide du document Word."""
    corps = _xml(archive, "word/document.xml")
    paragraphes = []
    for element in _sans_variantes(corps):
        if element.tag == f"{W}p":
            texte = _texte_paragraphe_word(element)
            if texte:
                paragraphes.append((_niveau_titre_word(element), texte))
    return paragraphes


def _pptx_slides(archive):
    """(arbre de presentation.xml, [(identifiant, texte)]) : une entrée par diapositive, dans l'ordre."""
    presentation = _xml(archive, "ppt/presentation.xml")
    liens = {
        lien.get("Id"): lien.get("Target") or ""
        for lien in _xml(archive, "ppt/_rels/presentation.xml.rels").iter(f"{REL}Relationship")
    }
    noms = set(archive.namelist())

    diapos = []
    for diapo in presentation.iter(f"{P}sldId"):
        cible = liens.get(diapo.get(f"{R}id"), "")
        chemin = cible.lstrip("/") if cible.startswith("/") else posixpath.normpath(f"ppt/{cible}")
        if not DIAPO.match(chemin) or chemin not in noms:   # chemin inattendu : ignoré
            continue
        if len(diapos) >= MAX_SLIDES:
            raise DocumentError(f"Présentation trop longue : {MAX_SLIDES} diapositives maximum.")
        texte = _texte_diapo(_xml(archive, chemin))
        if texte:
            diapos.append((diapo.get("id"), texte))
    return presentation, diapos


def _texte_diapo(diapo):
    """Titre de la diapositive sur la 1re ligne, puis le reste du texte."""
    titres, lignes, deja_lus = [], [], set()
    for forme in diapo.iter(f"{P}sp"):
        espace = forme.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
        if espace is not None and espace.get("type") in ("title", "ctrTitle"):
            for paragraphe in forme.iter(f"{A}p"):
                deja_lus.add(paragraphe)
                titres.append(_texte_paragraphe_dessin(paragraphe))
    for paragraphe in diapo.iter(f"{A}p"):   # zones de texte, tableaux…
        if paragraphe not in deja_lus:
            lignes.append(_texte_paragraphe_dessin(paragraphe))
    titre = " ".join(t for t in titres if t)
    return "\n".join(ligne for ligne in [titre, *lignes] if ligne).strip()


def _texte_paragraphe_dessin(paragraphe):
    morceaux = []
    for element in paragraphe.iter():
        if element.tag == f"{A}t":
            morceaux.append(element.text or "")
        elif element.tag == f"{A}br":
            morceaux.append("\n")
    return "".join(morceaux).strip()


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


def _sections_from_headings(paragraphes):
    """
    Word : un chapitre par titre du niveau le plus haut utilisé au moins 2 fois
    (« Titre 1 » en général). Renvoie une liste vide si le document n'a pas de titres.
    """
    niveaux = sorted({niveau for niveau, _ in paragraphes if niveau})
    niveau = next((n for n in niveaux if sum(1 for x, _ in paragraphes if x == n) >= 2), None)
    if niveau is None:
        return []

    sections, titre, blocs = [], "Introduction", []
    for niveau_paragraphe, texte in paragraphes:
        if niveau_paragraphe == niveau:
            sections.append((titre, blocs))
            titre, blocs = texte[:200], []
        else:
            blocs.append(texte)
    sections.append((titre, blocs))

    # L'introduction n'est gardée que si c'est plus qu'une page de garde
    if sections[0][0] == "Introduction" and len(" ".join(sections[0][1])) < MIN_INTRODUCTION:
        sections.pop(0)
    return [(t, b) for t, b in sections if b]


def _sections_from_pptx(presentation, diapos):
    """PowerPoint : un chapitre par section (Accueil → Sections). Liste vide s'il y en a moins de 2."""
    texte_par_id = dict(diapos)
    sections = []
    for section in presentation.iter(f"{P14}section"):
        nom = (section.get("name") or "").strip()[:200]
        blocs = [texte_par_id[d.get("id")] for d in section.iter(f"{P14}sldId") if d.get("id") in texte_par_id]
        if nom and blocs:
            sections.append((nom, blocs))
    return sections if len(sections) >= 2 else []
# ================= Découpage d'un texte sans structure (13f) ================

def _decouper_texte(texte, plan="", ia=None):
    """Plan du cours → titres « Chapitre 1 »… → IA (dernier recours) → un seul chapitre."""
    lignes = texte.split("\n")
    debuts = _debuts_selon_plan(lignes, plan) or _debuts_par_motifs(lignes)
    if not debuts and ia is not None and len(texte) >= MIN_TEXTE_IA:
        debuts = _debuts_par_ia(lignes, ia)
    if debuts:
        return _sections_par_lignes(lignes, debuts)
    return [("Cours complet", texte.split("\n\n"))]


def _normaliser(texte):
    """« CHAPITRE I. Les Sources du Droit » → « chapitre i les sources du droit » (sans accents ni ponctuation)."""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


def _cle(ligne):
    """Ce qui permet de comparer deux titres : texte normalisé, sans la numérotation de tête."""
    return NUMEROTATION.sub("", _normaliser(ligne))


def _ressemble_a_un_titre(ligne):
    """Ligne courte, qui n'est ni une ligne de sommaire ni la fin d'une phrase."""
    ligne = ligne.strip()
    return 3 <= len(ligne) <= 120 and not SOMMAIRE.search(ligne) and not ligne.endswith((".", ",", ";"))


def _taille(lignes, debuts, index):
    """Nombre de caractères du chapitre n° index (de son titre exclu jusqu'au titre suivant)."""
    fin = debuts[index + 1][0] if index + 1 < len(debuts) else len(lignes)
    return sum(len(ligne.strip()) for ligne in lignes[debuts[index][0] + 1 : fin])


def _petits(lignes, debuts):
    """Indices des chapitres presque vides (signe qu'on est tombé sur le sommaire)."""
    return [i for i in range(len(debuts)) if _taille(lignes, debuts, i) < MIN_SECTION]


def _valides(lignes, debuts):
    """Au moins 2 chapitres, et aucun presque vide (seul le dernier, une courte conclusion, est toléré)."""
    return len(debuts) >= 2 and all(i == len(debuts) - 1 for i in _petits(lignes, debuts))


def _entrees_du_plan(plan):
    """Lignes de 1er niveau du plan : on saute les sous-parties (indentées, « 1.2 », « a) »)."""
    for ligne in (plan or "").splitlines():
        if not ligne.strip() or re.match(r"^(\s{2,}|\t)", ligne) or re.match(r"^\s*(\d+\.\d+|[a-z]\))", ligne):
            continue
        yield ligne.strip()


def _debuts_selon_plan(lignes, plan):
    """[(numéro de ligne, titre du plan)] : chaque partie du plan est cherchée dans l'ordre."""
    entrees = [(entree[:200], cle) for entree in _entrees_du_plan(plan) if len(cle := _cle(entree)) >= 4]
    if len(entrees) < 2:
        return []
    cles_lignes = [_cle(ligne) if _ressemble_a_un_titre(ligne) else None for ligne in lignes]

    depart = 0
    for _ in range(3):   # 3 essais : le 1er tombe parfois sur le sommaire du début
        debuts, position = [], depart
        for titre, cle in entrees:
            for numero in range(position, len(lignes)):
                cle_ligne = cles_lignes[numero]
                if cle_ligne and (cle_ligne == cle or cle_ligne.startswith(cle + " ")):
                    debuts.append((numero, titre))
                    position = numero + 1
                    break
        if _valides(lignes, debuts):
            return debuts
        petits = _petits(lignes, debuts)
        if not petits:
            return []
        depart = debuts[petits[-1]][0] + 1   # on recommence après le sommaire
    return []


def _numero(texte):
    """« 3 » → 3, « IV » → 4, « première » → 1."""
    texte = texte.lower()
    if texte.isdigit():
        return int(texte)
    if texte.startswith("premi"):
        return 1
    valeurs, total = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}, 0
    for index, lettre in enumerate(texte):
        valeur = valeurs[lettre]
        total += -valeur if index + 1 < len(texte) and valeurs[texte[index + 1]] > valeur else valeur
    return total


def _debuts_par_motifs(lignes):
    """Titres explicites : « Chapitre 1 », « PARTIE II », « Leçon 3 »… (le mot le plus fréquent l'emporte)."""
    trouves = {}   # mot → [(numéro de ligne, numéro du chapitre)]
    for numero, ligne in enumerate(lignes):
        motif = MOT_CHAPITRE.match(ligne)
        if motif and _ressemble_a_un_titre(ligne):
            mot = _normaliser(motif.group(1))
            trouves.setdefault(mot, []).append((numero, _numero(motif.group(2))))
    if not trouves:
        return []
    lignes_trouvees = max(trouves.values(), key=len)

    # Le sommaire liste « Chapitre 1, 2, 3 » avant le vrai « Chapitre 1 » : on garde la dernière série
    premier = lignes_trouvees[0][1]
    reprises = [i for i, (_, n) in enumerate(lignes_trouvees) if n == premier]
    lignes_trouvees = lignes_trouvees[reprises[-1]:]

    debuts = []
    for numero, _ in lignes_trouvees:
        titre = lignes[numero].strip()
        suivante = next((l.strip() for l in lignes[numero + 1 : numero + 3] if l.strip()), "")
        # « Chapitre 1 » seul sur sa ligne, son nom juste en dessous → « Chapitre 1 — Les sources »
        if len(titre) <= 20 and suivante and _ressemble_a_un_titre(suivante):
            titre = f"{titre} — {suivante}"
        debuts.append((numero, titre[:200]))
    return debuts if _valides(lignes, debuts) else []


def _debuts_par_ia(lignes, ia):
    """
    Dernier recours : `ia` reçoit les lignes courtes [(numéro, ligne)] et renvoie les numéros des titres.
    On ne garde que des numéros proposés ET existants : l'IA ne peut pas inventer de titre.
    """
    candidats = [
        (numero, ligne.strip())
        for numero, ligne in enumerate(lignes)
        if _ressemble_a_un_titre(ligne) and len(ligne.strip()) <= 80 and ligne.strip()[0].isupper()
    ][:MAX_CANDIDATS_IA]
    if len(candidats) < 2:
        return []
    permis = dict(candidats)
    try:
        numeros = ia(candidats)
    except Exception:   # l'IA est un bonus : si elle échoue, on importe quand même (un seul chapitre)
        return []
    debuts = [(n, permis[n][:200]) for n in sorted({n for n in numeros if isinstance(n, int)}) if n in permis]
    return debuts if _valides(lignes, debuts) else []


def _sections_par_lignes(lignes, debuts):
    """[(numéro de ligne, titre)] → [(titre, blocs)], avec une « Introduction » s'il y a du texte avant."""
    sections = []
    avant = "\n".join(lignes[: debuts[0][0]]).strip()
    if len(avant) >= MIN_INTRODUCTION:
        sections.append(("Introduction", avant.split("\n\n")))
    for index, (numero, titre) in enumerate(debuts):
        fin = debuts[index + 1][0] if index + 1 < len(debuts) else len(lignes)
        sections.append((titre, "\n".join(lignes[numero + 1 : fin]).split("\n\n")))
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