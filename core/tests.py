from django.test import TestCase
from django.urls import reverse
import re
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import User
from core.demo import DEMO_USERNAME
from courses.models import Course
from quizzes.models import Question
from reviews.models import ReviewCard, ReviewLog


class HomePageTests(TestCase):
    def test_accueil_repond_avec_le_bon_template(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_accueil_charge_le_design_et_le_bouton_de_theme(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, "css/app.css")
    
    def test_page_404_personnalisee(self):
        response = self.client.get("/cette-page-n-existe-pas/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_favicon_redirige_vers_le_svg(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("favicon.svg"))
        
    def test_en_tete_csp_avec_nonce_sur_le_script_inline(self):
        response = self.client.get("/")
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
        self.assertContains(response, f'nonce="{nonce}"')   # le même nonce est dans la page

    def test_tailwind_compile_au_lieu_du_cdn(self):
        response = self.client.get("/")
        self.assertNotContains(response, "@tailwindcss/browser")
        self.assertContains(response, "css/tailwind.css")


class DemoAccountTests(TestCase):
    MDP = "Demo-Test-2026"

    def creer(self):
        call_command("creer_demo", mot_de_passe=self.MDP, stdout=StringIO(), stderr=StringIO())
        return User.objects.get(username=DEMO_USERNAME)

    def test_cree_un_compte_complet_et_coherent(self):
        user = self.creer()
        aujourd_hui = timezone.localdate()
        self.assertEqual(Course.objects.filter(owner=user).count(), 3)
        nb_questions = Question.objects.filter(quiz__chapter__course__owner=user).count()
        self.assertEqual(nb_questions, 30)
        self.assertEqual(ReviewCard.objects.filter(owner=user).count(), nb_questions)   # une carte par question
        self.assertTrue(ReviewLog.objects.filter(owner=user).exists())
        self.assertFalse(ReviewLog.objects.filter(owner=user, reviewed_at__date__gte=aujourd_hui).exists())
        self.assertTrue(ReviewCard.objects.filter(owner=user, due_date__lte=aujourd_hui).exists())   # révisions du jour

    def test_relancer_reinitialise_sans_doublon(self):
        self.creer()
        user = self.creer()
        self.assertEqual(User.objects.filter(username=DEMO_USERNAME).count(), 1)
        self.assertEqual(Course.objects.filter(owner=user).count(), 3)

    def test_les_pages_principales_s_affichent(self):
        self.creer()
        self.assertTrue(self.client.login(username=DEMO_USERNAME, password=self.MDP))
        for nom in ("dashboard:home", "courses:list", "reviews:home", "planning:home"):
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(nom)).status_code, 200)

    def test_ne_supprime_jamais_un_vrai_compte_nomme_demo(self):
        User.objects.create_user(DEMO_USERNAME, email="vrai@exemple.cd", password="x")
        erreurs = StringIO()
        call_command("creer_demo", mot_de_passe=self.MDP, stdout=StringIO(), stderr=erreurs)
        self.assertTrue(User.objects.filter(email="vrai@exemple.cd").exists())
        self.assertIn("vrai compte", erreurs.getvalue())

    def test_mot_de_passe_obligatoire(self):
        with self.settings(DEMO_PASSWORD=""):
            with self.assertRaises(CommandError):
                call_command("creer_demo", stdout=StringIO())

    def test_mot_de_passe_et_profil_proteges(self):
        user = self.creer()
        self.client.login(username=DEMO_USERNAME, password=self.MDP)
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": self.MDP, "new_password1": "Pirate-Mdp-2026", "new_password2": "Pirate-Mdp-2026",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Pirate", "last_name": "X", "email": "pirate@exemple.cd", "university": "", "program": "",
        })
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.MDP))
        self.assertEqual(user.first_name, "Awa")