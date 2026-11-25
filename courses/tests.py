from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from services.tests import make_pdf, make_pdf_with_bookmarks

from .models import Chapter, Course
from quizzes.models import Question, Quiz
from reviews.models import ReviewCard, ReviewLog
from django.core.cache import cache

User = get_user_model()

# Pendant les tests, les fichiers sont gardés en mémoire (rien sur le disque, rien sur Supabase)
STOCKAGE_MEMOIRE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class CourseTestCase(TestCase):
    """Deux étudiants : Awa (connectée) et Bob, dont Awa ne doit JAMAIS voir les données."""

    def setUp(self):
        self.awa = User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        self.bob = User.objects.create_user("bob", email="bob@exemple.cd", password="x")
        self.course_awa = Course.objects.create(owner=self.awa, title="Droit civil")
        self.course_bob = Course.objects.create(owner=self.bob, title="Chimie organique")
        self.client.force_login(self.awa)


class CourseViewsTests(CourseTestCase):
    def test_liste_exige_une_connexion(self):
        self.client.logout()
        url = reverse("courses:list")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_liste_ne_montre_que_mes_cours(self):
        response = self.client.get(reverse("courses:list"))
        self.assertContains(response, "Droit civil")
        self.assertNotContains(response, "Chimie organique")

    def test_creation_attribue_le_cours_a_l_utilisateur_connecte(self):
        data = {"title": "Économie", "description": "", "outline": "", "color": "mangue",
                "owner": self.bob.pk}  # tentative de tricher : doit être ignorée
        response = self.client.post(reverse("courses:create"), data)
        course = Course.objects.get(title="Économie")
        self.assertEqual(course.owner, self.awa)
        self.assertRedirects(response, course.get_absolute_url())

    def test_cours_d_un_autre_introuvable(self):
        for name in ("courses:detail", "courses:update", "courses:delete"):
            with self.subTest(vue=name):
                response = self.client.get(reverse(name, args=[self.course_bob.pk]))
                self.assertEqual(response.status_code, 404)

    def test_suppression_du_cours_d_un_autre_impossible(self):
        response = self.client.post(reverse("courses:delete", args=[self.course_bob.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Course.objects.filter(pk=self.course_bob.pk).exists())

    def test_suppression_de_mon_cours(self):
        response = self.client.post(reverse("courses:delete", args=[self.course_awa.pk]))
        self.assertRedirects(response, reverse("courses:list"))
        self.assertFalse(Course.objects.filter(pk=self.course_awa.pk).exists())


class ChapterViewsTests(CourseTestCase):
    def test_chapitres_numerotes_dans_l_ordre(self):
        url = reverse("courses:chapter_create", args=[self.course_awa.pk])
        self.client.post(url, {"title": "Introduction", "notes": "Notes 1"})
        self.client.post(url, {"title": "Les contrats", "notes": "Notes 2"})
        orders = list(self.course_awa.chapters.values_list("order", flat=True))
        self.assertEqual(orders, [1, 2])

    def test_ajout_dans_le_cours_d_un_autre_impossible(self):
        url = reverse("courses:chapter_create", args=[self.course_bob.pk])
        response = self.client.post(url, {"title": "Intrus", "notes": "..."})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Chapter.objects.filter(title="Intrus").exists())

    def test_chapitre_d_un_autre_introuvable(self):
        chapter = Chapter.objects.create(course=self.course_bob, title="Alcanes", notes="...", order=1)
        for name in ("courses:chapter_detail", "courses:chapter_update", "courses:chapter_delete"):
            with self.subTest(vue=name):
                response = self.client.get(reverse(name, args=[chapter.pk]))
                self.assertEqual(response.status_code, 404)

    def test_notes_echappees_contre_le_xss(self):
        chapter = Chapter.objects.create(
            course=self.course_awa, title="Test", notes="<script>alert(1)</script>", order=1
        )
        response = self.client.get(reverse("courses:chapter_detail", args=[chapter.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
    

@override_settings(STORAGES=STOCKAGE_MEMOIRE)
class ChapterFileTests(CourseTestCase):
    def test_import_pdf_cree_le_chapitre_avec_son_texte(self):
        url = reverse("courses:chapter_create", args=[self.course_awa.pk])
        pdf = SimpleUploadedFile("Chapitre 1.pdf", make_pdf("Les sources du droit"), content_type="application/pdf")
        response = self.client.post(url, {"title": "Sources", "notes": "", "source_file": pdf})

        self.assertRedirects(response, self.course_awa.get_absolute_url())
        chapter = Chapter.objects.get(title="Sources")
        self.assertIn("Les sources du droit", chapter.notes)
        self.assertEqual(chapter.original_filename, "Chapitre 1.pdf")
        # Nom stocké généré par nous : dossier de l'étudiant + identifiant aléatoire
        self.assertTrue(chapter.source_file.name.startswith(f"chapitres/{self.awa.pk}/"))
        self.assertTrue(chapter.source_file.name.endswith(".pdf"))

    def test_ni_notes_ni_fichier_refuse(self):
        url = reverse("courses:chapter_create", args=[self.course_awa.pk])
        response = self.client.post(url, {"title": "Vide", "notes": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "notes", "Écris tes notes ou importe un fichier.")
        self.assertFalse(Chapter.objects.filter(title="Vide").exists())

    def test_fichier_d_un_autre_introuvable(self):
        chapter = Chapter.objects.create(course=self.course_bob, title="Alcanes", notes="...", order=1)
        response = self.client.get(reverse("courses:chapter_file", args=[chapter.pk]))
        self.assertEqual(response.status_code, 404)
        

class CourseImportTests(CourseTestCase):
    def test_import_cree_un_chapitre_par_signet(self):
        pdf = make_pdf_with_bookmarks([("Les sources du droit", "Texte un"), ("Les contrats", "Texte deux")])
        url = reverse("courses:import", args=[self.course_awa.pk])
        response = self.client.post(url, {"fichier": SimpleUploadedFile("cours.pdf", pdf)})

        self.assertRedirects(response, self.course_awa.get_absolute_url())
        chapitres = list(self.course_awa.chapters.values_list("title", "order"))
        self.assertEqual(chapitres, [("Les sources du droit", 1), ("Les contrats", 2)])

    def test_import_dans_le_cours_d_un_autre_impossible(self):
        url = reverse("courses:import", args=[self.course_bob.pk])
        response = self.client.post(url, {"fichier": SimpleUploadedFile("cours.pdf", make_pdf("Intrus"))})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.course_bob.chapters.exists())
    

class DictationTests(CourseTestCase):
    def test_formulaire_chapitre_propose_la_dictee_sur_les_notes(self):
        response = self.client.get(reverse("courses:chapter_create", args=[self.course_awa.pk]))
        self.assertContains(response, 'data-dictation="id_notes"')


class ProgressionTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.chapitre = Chapter.objects.create(course=self.course_awa, title="Les contrats", notes="Notes", order=1)
        quiz = Quiz.objects.create(chapter=self.chapitre)
        questions = [
            Question.objects.create(quiz=quiz, kind="courte", text=f"Question {n} ?", expected_answer="R", order=n)
            for n in (1, 2)
        ]
        # 1 carte maîtrisée sur 2 (50 %), 3 bonnes réponses sur 4 (75 %)
        carte = ReviewCard.objects.create(owner=self.awa, question=questions[0], interval=30, review_count=4, correct_count=3)
        ReviewCard.objects.create(owner=self.awa, question=questions[1])
        ReviewLog.objects.create(owner=self.awa, card=carte, grade=4, correct=True)

    def test_page_du_cours_affiche_la_progression_par_chapitre(self):
        response = self.client.get(reverse("courses:detail", args=[self.course_awa.pk]))
        self.assertContains(response, "Progression")
        self.assertContains(response, "50 % maîtrisé")
        self.assertNotContains(response, "<polyline")   # plus de courbe : seulement des barres

    def test_page_du_chapitre_affiche_une_progression_simple(self):
        response = self.client.get(reverse("courses:chapter_detail", args=[self.chapitre.pk]))
        self.assertContains(response, "50 % maîtrisé")
        self.assertContains(response, "2 questions")

    def test_chapitre_sans_quiz_l_indique(self):
        Chapter.objects.create(course=self.course_awa, title="Les successions", notes="Notes", order=2)
        response = self.client.get(reverse("courses:detail", args=[self.course_awa.pk]))
        self.assertContains(response, "Pas encore de quiz")


@override_settings(AI_PROVIDER="fake")
class FormatNotesTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()   # remet à zéro le délai entre deux mises en forme
        self.url = reverse("courses:format_notes")

    def test_met_en_forme_et_repond_en_json(self):
        response = self.client.post(self.url, {"texte": "euh je je je deviendrai médecin plus tard"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Introduction", response.json()["texte"])

    def test_texte_trop_court_refuse(self):
        response = self.client.post(self.url, {"texte": "  euh  "})
        self.assertEqual(response.status_code, 400)

    def test_une_mise_en_forme_toutes_les_10_secondes(self):
        texte = {"texte": "un texte dicté assez long pour être mis en forme"}
        self.client.post(self.url, texte)
        self.assertEqual(self.client.post(self.url, texte).status_code, 429)

@override_settings(STORAGES=STOCKAGE_MEMOIRE)
class FichierGardeTests(CourseTestCase):
    def test_titre_oublie_le_texte_du_fichier_reste_dans_les_notes(self):
        url = reverse("courses:chapter_create", args=[self.course_awa.pk])
        pdf = SimpleUploadedFile("Chapitre 1.pdf", make_pdf("Les sources du droit"), content_type="application/pdf")
        response = self.client.post(url, {"title": "", "source_file": pdf})
        self.assertEqual(response.status_code, 200)                 # la page revient avec l'erreur…
        self.assertContains(response, "Les sources du droit")       # …mais le texte du PDF est conservé
        self.assertContains(response, "a été lu")
        self.assertFalse(Chapter.objects.exists())