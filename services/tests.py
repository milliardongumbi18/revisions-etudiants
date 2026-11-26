import zipfile
from io import BytesIO
from unittest.mock import patch
from xml.sax.saxutils import escape
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from pypdf import PdfReader, PdfWriter

from .documents import MAX_UPLOAD_SIZE, DocumentError, extract_text_from_upload, split_document


def make_pdf(text):
    """Fabrique un vrai petit PDF d'une page contenant `text` (ASCII), pour les tests."""
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_position = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_position)
    return bytes(out)


def make_pdf_with_bookmarks(chapitres):
    """PDF d'une page par chapitre, avec un signet par page. chapitres = [(titre, texte)]."""
    writer = PdfWriter()
    for numero, (titre, texte) in enumerate(chapitres):
        writer.add_page(PdfReader(BytesIO(make_pdf(texte))).pages[0])
        writer.add_outline_item(titre, numero)
    sortie = BytesIO()
    writer.write(sortie)
    return sortie.getvalue()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _zip(fichiers):
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in fichiers.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


def make_docx(paragraphes):
    """Petit .docx pour les tests. paragraphes = [(style ou None, texte)], ex. ("Titre1", "Chapitre 1")."""
    def paragraphe(style, texte):
        proprietes = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{proprietes}<w:r><w:t>{escape(texte)}</w:t></w:r></w:p>"

    corps = "".join(paragraphe(style, texte) for style, texte in paragraphes)
    document = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W_NS}"><w:body>{corps}</w:body></w:document>'
    return _zip({"[Content_Types].xml": "<Types/>", "word/document.xml": document})


def make_pptx(diapos, sections=None):
    """Petit .pptx pour les tests. diapos = [(titre, texte)] ; sections = [(nom, [numéros des diapos])]."""
    ids = "".join(f'<p:sldId id="{256 + n}" r:id="rId{n + 1}"/>' for n in range(len(diapos)))
    liste_sections = ""
    if sections:
        liste_sections = "<p:extLst><p:ext><p14:sectionLst>" + "".join(
            f'<p14:section name="{escape(nom)}"><p14:sldIdLst>'
            + "".join(f'<p14:sldId id="{256 + n}"/>' for n in numeros)
            + "</p14:sldIdLst></p14:section>"
            for nom, numeros in sections
        ) + "</p14:sectionLst></p:ext></p:extLst>"
    fichiers = {
        "ppt/presentation.xml": (
            f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}" xmlns:p14="{P14_NS}">'
            f"<p:sldIdLst>{ids}</p:sldIdLst>{liste_sections}</p:presentation>"
        ),
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{REL_NS}">' + "".join(
            f'<Relationship Id="rId{n + 1}" Target="slides/slide{n + 1}.xml"/>' for n in range(len(diapos))
        ) + "</Relationships>",
    }
    for n, (titre, texte) in enumerate(diapos):
        fichiers[f"ppt/slides/slide{n + 1}.xml"] = (
            f'<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}"><p:cSld><p:spTree>'
            f'<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            f"<p:txBody><a:p><a:r><a:t>{escape(titre)}</a:t></a:r></a:p></p:txBody></p:sp>"
            f"<p:sp><p:txBody><a:p><a:r><a:t>{escape(texte)}</a:t></a:r></a:p></p:txBody></p:sp>"
            "</p:spTree></p:cSld></p:sld>"
        )
    return _zip(fichiers)
class ExtractTextTests(SimpleTestCase):
    def test_pdf_valide_texte_extrait(self):
        fichier = SimpleUploadedFile("cours.pdf", make_pdf("Bonjour Kinshasa"))
        self.assertIn("Bonjour Kinshasa", extract_text_from_upload(fichier))

    def test_txt_utf8_avec_accents(self):
        fichier = SimpleUploadedFile("notes.txt", "Révision : l'économie".encode("utf-8"))
        self.assertEqual(extract_text_from_upload(fichier), "Révision : l'économie")

    def test_extension_refusee(self):
        fichier = SimpleUploadedFile("cours.exe", b"MZ")
        with self.assertRaisesMessage(DocumentError, "Format non accepté"):
            extract_text_from_upload(fichier)

    def test_faux_pdf_refuse(self):
        fichier = SimpleUploadedFile("virus.pdf", b"MZ\x90\x00 ceci n'est pas un pdf")
        with self.assertRaisesMessage(DocumentError, "pas un vrai PDF"):
            extract_text_from_upload(fichier)

    def test_fichier_trop_lourd(self):
        fichier = SimpleUploadedFile("gros.pdf", b"%PDF-" + b"0" * MAX_UPLOAD_SIZE)
        with self.assertRaisesMessage(DocumentError, "trop lourd"):
            extract_text_from_upload(fichier)

    def test_pdf_sans_texte(self):
        fichier = SimpleUploadedFile("scan.pdf", make_pdf(""))
        with self.assertRaisesMessage(DocumentError, "Aucun texte lisible"):
            extract_text_from_upload(fichier)


class SplitDocumentTests(SimpleTestCase):
    def test_un_chapitre_par_signet(self):
        pdf = make_pdf_with_bookmarks([("Introduction au droit", "Texte un"), ("Les contrats", "Texte deux")])
        chapitres = split_document(SimpleUploadedFile("cours.pdf", pdf))
        self.assertEqual([titre for titre, _ in chapitres], ["Introduction au droit", "Les contrats"])
        self.assertIn("Texte un", chapitres[0][1])
        self.assertIn("Texte deux", chapitres[1][1])

    def test_sans_signets_un_seul_chapitre(self):
        chapitres = split_document(SimpleUploadedFile("cours.pdf", make_pdf("Tout le cours")))
        self.assertEqual(len(chapitres), 1)
        self.assertEqual(chapitres[0][0], "Cours complet")
        self.assertIn("Tout le cours", chapitres[0][1])

    def test_texte_trop_long_decoupe_en_parties(self):
        texte = "\n\n".join(["a" * 60_000, "b" * 60_000, "c" * 60_000])
        chapitres = split_document(SimpleUploadedFile("cours.txt", texte.encode("utf-8")))
        self.assertEqual(
            [titre for titre, _ in chapitres],
            ["Cours complet — partie 1", "Cours complet — partie 2", "Cours complet — partie 3"],
        )


class OfficeDocumentsTests(SimpleTestCase):
    def test_word_texte_extrait(self):
        docx = make_docx([(None, "Bonjour Kinshasa"), (None, "L'économie & le droit")])
        texte = extract_text_from_upload(SimpleUploadedFile("cours.docx", docx))
        self.assertIn("Bonjour Kinshasa", texte)
        self.assertIn("L'économie & le droit", texte)

    def test_word_un_chapitre_par_titre(self):
        docx = make_docx([
            (None, "Page de garde"),                       # trop court : ignoré
            ("Heading1", "Chapitre 1 — Les sources"), (None, "La loi"),
            ("Titre1", "Chapitre 2 — Les personnes"), ("Titre2", "Section 1"), (None, "La capacité"),
        ])
        chapitres = split_document(SimpleUploadedFile("cours.docx", docx))
        self.assertEqual([titre for titre, _ in chapitres], ["Chapitre 1 — Les sources", "Chapitre 2 — Les personnes"])
        self.assertIn("La capacité", chapitres[1][1])

    def test_powerpoint_texte_dans_l_ordre(self):
        pptx = make_pptx([("Les sources du droit", "La loi"), ("Diapo 2", "La jurisprudence")])
        texte = extract_text_from_upload(SimpleUploadedFile("cours.pptx", pptx))
        self.assertLess(texte.index("La loi"), texte.index("La jurisprudence"))

    def test_powerpoint_un_chapitre_par_section(self):
        pptx = make_pptx([("A", "a"), ("B", "b"), ("C", "c")], sections=[("Partie 1", [0, 1]), ("Partie 2", [2])])
        chapitres = split_document(SimpleUploadedFile("cours.pptx", pptx))
        self.assertEqual([titre for titre, _ in chapitres], ["Partie 1", "Partie 2"])

    def test_faux_document_word_refuse(self):
        with self.assertRaisesMessage(DocumentError, "pas un vrai document Word"):
            extract_text_from_upload(SimpleUploadedFile("virus.docx", b"MZ\x90\x00"))

    def test_xml_piege_refuse(self):
        piege = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><w:document xmlns:w="x">&a;</w:document>'
        docx = _zip({"word/document.xml": piege})
        with self.assertRaisesMessage(DocumentError, "XML suspect"):
            extract_text_from_upload(SimpleUploadedFile("piege.docx", docx))

    def test_bombe_zip_refusee(self):
        docx = make_docx([(None, "x" * 500)])
        with patch("services.documents.MAX_UNZIPPED_SIZE", 100):   # limite abaissée pour le test
            with self.assertRaisesMessage(DocumentError, "trop volumineux"):
                extract_text_from_upload(SimpleUploadedFile("bombe.docx", docx))

    def test_ancien_format_explique(self):
        with self.assertRaisesMessage(DocumentError, "enregistre ton fichier en .docx"):
            extract_text_from_upload(SimpleUploadedFile("cours.doc", b"\xd0\xcf\x11\xe0"))


def cours_txt(*lignes):
    return SimpleUploadedFile("cours.txt", "\n".join(lignes).encode("utf-8"))


PARAGRAPHE = "Texte du cours sur ce point précis. " * 15   # environ 540 caractères


class DecoupageTexteTests(SimpleTestCase):
    PLAN = "Chapitre 1 : Les sources du droit\n  1.1 La loi\nChapitre 2 : Les personnes"

    def test_decoupe_selon_le_plan_en_ignorant_le_sommaire(self):
        fichier = cours_txt(
            "SOMMAIRE", "Chapitre 1 : Les sources du droit", "Chapitre 2 : Les personnes",   # le sommaire
            "CHAPITRE I. LES SOURCES DU DROIT", PARAGRAPHE,
            "CHAPITRE II. LES PERSONNES", PARAGRAPHE,
        )
        chapitres = split_document(fichier, plan=self.PLAN)
        self.assertEqual([t for t, _ in chapitres], ["Chapitre 1 : Les sources du droit", "Chapitre 2 : Les personnes"])
        self.assertIn("Texte du cours", chapitres[0][1])

    def test_sans_plan_titres_chapitre_detectes(self):
        fichier = cours_txt("Chapitre 1", "Les sources", PARAGRAPHE, "Chapitre 2", "Les personnes", PARAGRAPHE)
        self.assertEqual(
            [t for t, _ in split_document(fichier)], ["Chapitre 1 — Les sources", "Chapitre 2 — Les personnes"]
        )

    def test_ia_en_dernier_recours_sans_inventer_de_titre(self):
        long_texte = PARAGRAPHE * 20
        fichier = cours_txt("Notes de cours", "Les obligations", long_texte, "La responsabilité", long_texte)
        ia = lambda candidats: [1, 3, 999]   # 999 n'existe pas : ignoré
        self.assertEqual([t for t, _ in split_document(fichier, ia=ia)], ["Les obligations", "La responsabilité"])

    def test_ia_en_panne_le_cours_est_importe_quand_meme(self):
        def ia_en_panne(candidats):
            raise RuntimeError("quota dépassé")

        long_texte = PARAGRAPHE * 20
        fichier = cours_txt("Les obligations", long_texte, "La responsabilité", long_texte)
        self.assertEqual([t for t, _ in split_document(fichier, ia=ia_en_panne)], ["Cours complet"])