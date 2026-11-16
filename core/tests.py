from django.test import TestCase
from django.urls import reverse


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