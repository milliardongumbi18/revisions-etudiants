from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Chapter, Course
from quizzes.models import Question, Quiz

from .models import ClassSlot, Exam, PlanCheck

User = get_user_model()


class PlanningViewsTests(TestCase):
    def setUp(self):
        self.awa = User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        self.bob = User.objects.create_user("bob", email="bob@exemple.cd", password="x")
        self.course_awa = Course.objects.create(owner=self.awa, title="Droit civil")
        self.course_bob = Course.objects.create(owner=self.bob, title="Chimie")
        self.client.force_login(self.awa)

    def creneau(self, **donnees):
        data = {"label": "", "weekday": 0, "start_time": "08:00", "end_time": "10:00"}
        data.update(donnees)
        return self.client.post(reverse("planning:slot_create"), data)

    def test_planning_exige_une_connexion(self):
        self.client.logout()
        url = reverse("planning:home")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_creneau_avec_le_cours_d_un_autre_refuse(self):
        response = self.creneau(course=self.course_bob.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("course", response.context["form"].errors)
        self.assertFalse(ClassSlot.objects.exists())

    def test_creneaux_qui_se_chevauchent_refuses(self):
        ClassSlot.objects.create(owner=self.awa, label="Maths", weekday=0, start_time=time(8), end_time=time(10))
        response = self.creneau(label="Physique", start_time="09:00", end_time="11:00")
        self.assertIn("start_time", response.context["form"].errors)
        self.assertEqual(ClassSlot.objects.count(), 1)

    def test_fin_avant_debut_refusee(self):
        response = self.creneau(label="Physique", start_time="10:00", end_time="08:00")
        self.assertIn("end_time", response.context["form"].errors)

    def test_creneau_d_un_autre_introuvable(self):
        creneau_bob = ClassSlot.objects.create(owner=self.bob, label="Labo", weekday=1, start_time=time(8), end_time=time(9))
        response = self.client.get(reverse("planning:slot_update", args=[creneau_bob.pk]))
        self.assertEqual(response.status_code, 404)

    def test_examen_visible_dans_le_planning(self):
        jour_examen = timezone.localdate() + timedelta(days=3)
        self.client.post(
            reverse("planning:exam_create"),
            {"kind": "examen", "course": self.course_awa.pk, "date": jour_examen.isoformat(), "title": "Partiel"},
        )
        response = self.client.get(reverse("planning:home"))
        self.assertEqual(response.context["plan"][3].blocks[0].kind, "examen")
        self.assertContains(response, "J-3")

    def test_cocher_puis_decocher_un_bloc(self):
        url = reverse("planning:toggle_done", args=[self.course_awa.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(PlanCheck.objects.filter(owner=self.awa, course=self.course_awa).exists())
        self.client.post(url)
        self.assertFalse(PlanCheck.objects.exists())

    def test_cocher_le_cours_d_un_autre_impossible(self):
        response = self.client.post(reverse("planning:toggle_done", args=[self.course_bob.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PlanCheck.objects.exists())

    def test_bloc_coche_affiche_comme_fait(self):
        PlanCheck.objects.create(owner=self.awa, course=self.course_awa, date=timezone.localdate())
        response = self.client.get(reverse("planning:home"))
        bloc = next(b for b in response.context["today"].blocks if b.kind == "cours")
        self.assertTrue(bloc.done)
        self.assertEqual(response.context["progress"]["faits"], 1)
        self.assertContains(response, "✓ Fait")

    def test_interro_enregistree_avec_son_type(self):
        jour = timezone.localdate() + timedelta(days=2)
        self.client.post(
            reverse("planning:exam_create"),
            {"kind": "interro", "course": self.course_awa.pk, "date": jour.isoformat(), "title": ""},
        )
        self.assertEqual(Exam.objects.get().kind, "interro")
        self.assertContains(self.client.get(reverse("planning:home")), "Interrogation")

    def test_intitule_ignore_si_un_cours_est_choisi(self):
        self.creneau(course=self.course_awa.pk, label="Texte inutile")
        self.assertEqual(ClassSlot.objects.get().label, "")

    # ---------- Étape 13h : chapitres concernés par une épreuve ----------

    def chapitre(self, cours, titre, ordre):
        chapitre = Chapter.objects.create(course=cours, title=titre, notes="Notes", order=ordre)
        quiz = Quiz.objects.create(chapter=chapitre)
        Question.objects.create(quiz=quiz, kind="courte", text=f"{titre} ?", expected_answer="R", order=1)
        return chapitre

    def epreuve(self, **donnees):
        data = {
            "kind": "interro", "course": self.course_awa.pk, "title": "",
            "date": (timezone.localdate() + timedelta(days=2)).isoformat(),
        }
        data.update(donnees)
        return self.client.post(reverse("planning:exam_create"), data)

    def test_chapitre_d_un_autre_cours_refuse(self):
        chimie = Course.objects.create(owner=self.awa, title="Chimie")
        response = self.epreuve(chapters=[self.chapitre(chimie, "Les atomes", 1).pk])
        self.assertIn("chapters", response.context["form"].errors)
        self.assertFalse(Exam.objects.exists())

    def test_chapitre_d_un_autre_etudiant_refuse(self):
        response = self.epreuve(chapters=[self.chapitre(self.course_bob, "Le labo", 1).pk])
        self.assertIn("chapters", response.context["form"].errors)
        self.assertFalse(Exam.objects.exists())

    def test_seance_ciblee_sur_les_chapitres_de_l_epreuve(self):
        sources = self.chapitre(self.course_awa, "Les sources", 1)
        self.chapitre(self.course_awa, "Les personnes", 2)
        self.epreuve(chapters=[sources.pk])
        response = self.client.post(reverse("reviews:start_exam", args=[Exam.objects.get().pk]))
        self.assertRedirects(response, reverse("reviews:session"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["revision"]["total"], 1)   # seulement la question du chapitre 1

    def test_seance_pour_l_epreuve_d_un_autre_impossible(self):
        examen_bob = Exam.objects.create(owner=self.bob, course=self.course_bob, date=timezone.localdate())
        self.assertEqual(self.client.post(reverse("reviews:start_exam", args=[examen_bob.pk])).status_code, 404)

    def test_bloc_du_planning_mene_au_chapitre_de_l_epreuve(self):
        self.chapitre(self.course_awa, "Les sources", 1)
        personnes = self.chapitre(self.course_awa, "Les personnes", 2)
        self.epreuve(chapters=[personnes.pk])
        response = self.client.get(reverse("planning:home"))
        bloc = next(b for b in response.context["today"].blocks if b.kind == "cours")
        self.assertEqual(bloc.chapter_id, personnes.pk)
        self.assertEqual(bloc.detail, "ch. 2")