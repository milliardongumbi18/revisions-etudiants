from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course

from .models import ClassSlot

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
            {"course": self.course_awa.pk, "date": jour_examen.isoformat(), "title": "Partiel"},
        )
        response = self.client.get(reverse("planning:home"))
        self.assertEqual(response.context["plan"][3].blocks[0].kind, "examen")
        self.assertContains(response, "J-3")