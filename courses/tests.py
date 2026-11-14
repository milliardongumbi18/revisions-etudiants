from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Chapter, Course

User = get_user_model()


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