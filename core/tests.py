from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_accueil_repond_avec_le_bon_template(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")