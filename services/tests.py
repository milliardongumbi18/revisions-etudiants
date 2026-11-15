from io import BytesIO

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


class ExtractTextTests(SimpleTestCase):
    def test_pdf_valide_texte_extrait(self):
        fichier = SimpleUploadedFile("cours.pdf", make_pdf("Bonjour Kinshasa"))
        self.assertIn("Bonjour Kinshasa", extract_text_from_upload(fichier))

    def test_txt_utf8_avec_accents(self):
        fichier = SimpleUploadedFile("notes.txt", "Révision : l'économie".encode("utf-8"))
        self.assertEqual(extract_text_from_upload(fichier), "Révision : l'économie")

    def test_extension_refusee(self):
        fichier = SimpleUploadedFile("cours.docx", b"PK\x03\x04")
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