from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from courses.models import Chapter, Course
from quizzes.models import Question, Quiz
from reviews.models import ReviewCard, ReviewLog

User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.awa = User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        self.bob = User.objects.create_user("bob", email="bob@exemple.cd", password="x")
        cours = Course.objects.create(owner=self.awa, title="Droit civil")
        Course.objects.create(owner=self.bob, title="Chimie organique")
        quiz = Quiz.objects.create(chapter=Chapter.objects.create(course=cours, title="Intro", notes="...", order=1))
        self.question = Question.objects.create(quiz=quiz, kind="courte", text="Q ?", expected_answer="R", order=1)
        self.client.force_login(self.awa)

    def test_exige_une_connexion(self):
        self.client.logout()
        url = reverse("dashboard:home")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_ne_montre_que_mes_cours(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Droit civil")
        self.assertNotContains(response, "Chimie organique")

    def test_activite_et_serie_du_jour(self):
        carte = ReviewCard.objects.create(owner=self.awa, question=self.question)
        ReviewLog.objects.create(owner=self.awa, card=carte, grade=4, correct=True)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["serie"], 1)
        self.assertEqual(response.context["activite"][-1]["n"], 1)
        self.assertEqual(response.context["taux_reussite"], 100)

    def test_badge_des_revisions_dues_dans_l_en_tete(self):
        ReviewCard.objects.create(owner=self.awa, question=self.question)   # due aujourd'hui par défaut
        response = self.client.get(reverse("courses:list"))
        self.assertContains(response, 'class="nav-badge"')