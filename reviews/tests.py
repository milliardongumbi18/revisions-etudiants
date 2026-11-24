from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Chapter, Course
from quizzes.models import Question, Quiz
from services.sm2 import SM2State, review

from .models import ReviewCard, ReviewLog

User = get_user_model()


class SM2Tests(SimpleTestCase):
    def test_intervalles_1_puis_6_puis_multiplies(self):
        etat = review(SM2State(), 4)
        self.assertEqual((etat.interval, etat.repetitions), (1, 1))
        etat = review(etat, 4)
        self.assertEqual(etat.interval, 6)
        etat = review(etat, 4)
        self.assertEqual(etat.interval, 15)   # 6 jours × facilité 2,5

    def test_un_echec_remet_la_serie_a_zero(self):
        etat = review(review(review(SM2State(), 5), 5), 1)
        self.assertEqual((etat.interval, etat.repetitions), (1, 0))

    def test_la_facilite_ne_descend_jamais_sous_1_3(self):
        etat = SM2State()
        for _ in range(10):
            etat = review(etat, 0)
        self.assertEqual(etat.easiness, 1.3)

    def test_note_hors_limites_refusee(self):
        with self.assertRaises(ValueError):
            review(SM2State(), 6)


class ReviewFlowTests(TestCase):
    def setUp(self):
        self.awa = User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        self.bob = User.objects.create_user("bob", email="bob@exemple.cd", password="x")

        chapitre = Chapter.objects.create(
            course=Course.objects.create(owner=self.awa, title="Géographie"), title="La RDC", notes="...", order=1
        )
        self.quiz = Quiz.objects.create(chapter=chapitre)
        self.q1 = Question.objects.create(
            quiz=self.quiz, kind="qcm", text="Quelle est la capitale ?", order=1,
            choices=["Lubumbashi", "Goma", "Kinshasa", "Kisangani"], correct_index=2,
        )
        self.q2 = Question.objects.create(
            quiz=self.quiz, kind="courte", text="Quel fleuve traverse la capitale ?", order=2,
            expected_answer="Le fleuve Congo",
        )

        chapitre_bob = Chapter.objects.create(
            course=Course.objects.create(owner=self.bob, title="Chimie"), title="Alcanes", notes="...", order=1
        )
        self.quiz_bob = Quiz.objects.create(chapter=chapitre_bob)
        self.q_bob = Question.objects.create(quiz=self.quiz_bob, kind="courte", text="?", expected_answer="!", order=1)

        self.client.force_login(self.awa)
        
    def test_qcm_reussi_passe_directement_a_la_question_suivante(self):
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 2})   # bonne réponse
        log = ReviewLog.objects.get()
        self.assertEqual((log.grade, log.correct), (4, True))
        response = self.client.get(reverse("reviews:session"))
        self.assertContains(response, "Quel fleuve traverse la capitale ?")   # déjà la question 2

    def test_explication_affichee_apres_une_erreur(self):
        self.q1.explanation = "Kinshasa est la capitale de la RDC."
        self.q1.save()
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 0})
        self.assertContains(self.client.get(reverse("reviews:session")), "Kinshasa est la capitale de la RDC.")

    def test_le_fournisseur_d_ia_n_est_pas_affiche(self):
        self.quiz.generated_by = "Gemini · modèle de test"
        self.quiz.save()
        page_quiz = self.client.get(reverse("quizzes:detail", args=[self.quiz.pk]))
        page_chapitre = self.client.get(reverse("courses:chapter_detail", args=[self.quiz.chapter.pk]))
        self.assertNotContains(page_quiz, "Gemini")
        self.assertNotContains(page_chapitre, "Gemini")

    def demarrer(self):
        return self.client.post(reverse("reviews:start_quiz", args=[self.quiz.pk]))

    def test_demarrer_cree_les_cartes_et_affiche_la_premiere_question(self):
        self.assertRedirects(self.demarrer(), reverse("reviews:session"))
        self.assertEqual(ReviewCard.objects.filter(owner=self.awa).count(), 2)
        self.assertContains(self.client.get(reverse("reviews:session")), "Quelle est la capitale ?")

    def test_qcm_rate_revient_demain_meme_si_on_clique_facile(self):
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 0})   # mauvaise réponse
        self.client.post(reverse("reviews:grade"), {"grade": 5})     # tentative de tricher
        carte = ReviewCard.objects.get(question=self.q1)
        self.assertEqual((carte.repetitions, carte.interval), (0, 1))
        self.assertEqual(carte.due_date, timezone.localdate() + timedelta(days=1))
        self.assertFalse(ReviewLog.objects.get().correct)

    def test_qcm_reussi_programme_la_prochaine_revision(self):
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 2})
        self.client.post(reverse("reviews:grade"), {"grade": 4})
        carte = ReviewCard.objects.get(question=self.q1)
        self.assertEqual((carte.repetitions, carte.interval, carte.correct_count), (1, 1, 1))

    def test_seance_terminee_affiche_le_bilan(self):
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 2})
        self.client.post(reverse("reviews:grade"), {"grade": 4})
        self.client.post(reverse("reviews:answer"), {"answer": "Le fleuve Congo"})
        self.client.post(reverse("reviews:grade"), {"grade": 5})
        self.assertContains(self.client.get(reverse("reviews:session")), "Révision terminée")

    def test_note_invalide_refusee(self):
        self.demarrer()
        self.client.post(reverse("reviews:answer"), {"choice": 0})   # mauvaise réponse : écran de correction
        response = self.client.post(reverse("reviews:grade"), {"grade": 2})
        self.assertEqual(response.status_code, 400)

    def test_quiz_d_un_autre_introuvable(self):
        response = self.client.post(reverse("reviews:start_quiz", args=[self.quiz_bob.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ReviewCard.objects.exists())

    def test_revisions_du_jour_ne_comptent_que_mes_cartes(self):
        ReviewCard.objects.create(owner=self.bob, question=self.q_bob)
        response = self.client.get(reverse("reviews:home"))
        self.assertEqual(response.context["due_count"], 2)   # les 2 questions d'Awa, pas celle de Bob