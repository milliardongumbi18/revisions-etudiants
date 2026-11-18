from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.demo import DEMO_EMAIL, DEMO_USERNAME
from courses.models import Chapter, Course
from quizzes.models import Question, Quiz

from .models import ReviewCard
from .rappels import lien_desinscription

User = get_user_model()


def carte(user, dans_jours=0, titre="Algorithmique"):
    """Une carte de révision due dans `dans_jours` jours (0 = aujourd'hui)."""
    cours = Course.objects.create(owner=user, title=titre)
    chapitre = Chapter.objects.create(course=cours, title="Chapitre 1", notes="Notes")
    quiz = Quiz.objects.create(chapter=chapitre)
    question = Question.objects.create(quiz=quiz, kind=Question.Kind.SHORT, text="Question ?", expected_answer="Réponse")
    return ReviewCard.objects.create(owner=user, question=question,
                                     due_date=timezone.localdate() + timedelta(days=dans_jours))


@override_settings(SITE_URL="https://revisions.exemple.cd")
class RappelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password="x",
                                             first_name="Awa", daily_reminder=True)

    def lancer(self):
        call_command("envoyer_rappels", stdout=StringIO())

    def test_envoie_un_rappel_quand_des_revisions_sont_dues(self):
        carte(self.user)
        self.lancer()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["awa@exemple.cd"])
        self.assertIn("1 révision", email.subject)
        self.assertIn("Algorithmique", email.body)
        self.assertIn("https://revisions.exemple.cd/compte/rappels/desactiver/", email.body)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_reminder_sent, timezone.localdate())

    def test_rien_a_reviser_aucun_email(self):
        carte(self.user, dans_jours=1)
        self.lancer()
        self.assertEqual(len(mail.outbox), 0)

    def test_sans_consentement_aucun_email(self):
        User.objects.filter(pk=self.user.pk).update(daily_reminder=False)
        carte(self.user)
        self.lancer()
        self.assertEqual(len(mail.outbox), 0)

    def test_un_seul_rappel_par_jour(self):
        carte(self.user)
        self.lancer()
        self.lancer()
        self.assertEqual(len(mail.outbox), 1)

    def test_compte_demo_exclu(self):
        demo = User.objects.create_user(DEMO_USERNAME, email=DEMO_EMAIL, password="x", daily_reminder=True)
        carte(demo)
        self.lancer()
        self.assertEqual(len(mail.outbox), 0)

    def test_lien_de_desinscription_demande_confirmation_puis_desactive(self):
        url = lien_desinscription(self.user).removeprefix("https://revisions.exemple.cd")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.daily_reminder)   # un simple GET ne change rien
        self.client.post(url)
        self.user.refresh_from_db()
        self.assertFalse(self.user.daily_reminder)

    def test_jeton_falsifie_donne_404(self):
        response = self.client.get(reverse("accounts:reminders_unsubscribe", args=["faux:jeton"]))
        self.assertEqual(response.status_code, 404)

    def test_activation_depuis_le_profil(self):
        User.objects.filter(pk=self.user.pk).update(daily_reminder=False)
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Awa", "last_name": "", "email": "awa@exemple.cd",
            "university": "", "program": "", "daily_reminder": "on",
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.daily_reminder)