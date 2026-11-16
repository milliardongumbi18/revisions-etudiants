from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.models import Chapter, Course

from .models import Quiz
from reviews.models import ReviewCard

User = get_user_model()
NOTES = "Le droit civil régit les relations entre les personnes privées. " * 10   # > 200 caractères


@override_settings(AI_PROVIDER="fake")   # aucun appel réseau pendant les tests
class GenerateQuizTests(TestCase):
    def setUp(self):
        self.awa = User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        self.bob = User.objects.create_user("bob", email="bob@exemple.cd", password="x")
        course_awa = Course.objects.create(owner=self.awa, title="Droit civil")
        course_bob = Course.objects.create(owner=self.bob, title="Chimie")
        self.chapter_awa = Chapter.objects.create(course=course_awa, title="Introduction", notes=NOTES, order=1)
        self.chapter_bob = Chapter.objects.create(course=course_bob, title="Alcanes", notes=NOTES, order=1)
        self.client.force_login(self.awa)

    def url(self, chapter):
        return reverse("quizzes:generate", args=[chapter.pk])

    def test_generation_cree_le_quiz_et_ses_questions(self):
        response = self.client.post(self.url(self.chapter_awa))
        quiz = Quiz.objects.get(chapter=self.chapter_awa)
        self.assertRedirects(response, quiz.get_absolute_url())
        self.assertEqual(quiz.questions.count(), 5)
        self.assertEqual(quiz.questions.filter(kind="qcm").count(), 3)

    def test_generation_refuse_get(self):
        response = self.client.get(self.url(self.chapter_awa))
        self.assertEqual(response.status_code, 405)

    def test_chapitre_d_un_autre_introuvable(self):
        response = self.client.post(self.url(self.chapter_bob))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Quiz.objects.exists())

    def test_chapitre_trop_court_refuse(self):
        court = Chapter.objects.create(course=self.chapter_awa.course, title="Court", notes="Trop court.", order=2)
        response = self.client.post(self.url(court))
        self.assertRedirects(response, court.get_absolute_url())
        self.assertFalse(Quiz.objects.exists())

    def test_deux_generations_rapprochees_refusees(self):
        self.client.post(self.url(self.chapter_awa))
        self.client.post(self.url(self.chapter_awa))
        self.assertEqual(Quiz.objects.count(), 1)

    def test_quiz_d_un_autre_introuvable(self):
        quiz_bob = Quiz.objects.create(chapter=self.chapter_bob)
        response = self.client.get(reverse("quizzes:detail", args=[quiz_bob.pk]))
        self.assertEqual(response.status_code, 404)

    @override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="")
    def test_erreur_ia_affiche_un_message_sans_creer_de_quiz(self):
        response = self.client.post(self.url(self.chapter_awa), follow=True)
        self.assertContains(response, "clé API manquante")
        self.assertFalse(Quiz.objects.exists())


    def test_generation_cree_les_cartes_de_revision(self):
        self.client.post(self.url(self.chapter_awa))
        self.assertEqual(ReviewCard.objects.filter(owner=self.awa).count(), 5)