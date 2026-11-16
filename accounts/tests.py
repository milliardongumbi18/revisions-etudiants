from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Kinshasa-Revise-2026!"
NEW_PASSWORD = "Nouveau-Mdp-Lubumbashi-2027!"


class UserModelTests(TestCase):
    def test_email_normalise_en_minuscules(self):
        user = User.objects.create_user("awa", email="  Awa@Exemple.CD ", password="x")
        self.assertEqual(user.email, "awa@exemple.cd")

    def test_validation_signale_un_doublon_avec_une_casse_differente(self):
        User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        doublon = User(username="awa2", email="AWA@exemple.cd")
        with self.assertRaisesMessage(ValidationError, "Un compte utilise déjà cette adresse e-mail."):
            doublon.validate_constraints()

    def test_la_base_bloque_un_doublon_meme_sans_passer_par_save(self):
        User.objects.create_user("awa", email="awa@exemple.cd", password="x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(username="awa2", email="AWA@Exemple.cd")])


class SignupTests(TestCase):
    def donnees(self, **modifs):
        data = {
            "username": "awa",
            "email": "Awa@Exemple.cd",
            "university": "UNIKIN",
            "program": "L2 Informatique",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(modifs)
        return data

    def test_page_inscription_s_affiche(self):
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")

    def test_inscription_cree_le_compte_connecte_et_mene_aux_cours(self):
        response = self.client.post(reverse("accounts:signup"), self.donnees())
        self.assertRedirects(response, reverse("courses:list"))

        user = User.objects.get(username="awa")
        self.assertEqual(user.email, "awa@exemple.cd")
        self.assertNotEqual(user.password, PASSWORD)      # jamais en clair
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_email_deja_utilise_refuse_quelle_que_soit_la_casse(self):
        User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        response = self.client.post(
            reverse("accounts:signup"), self.donnees(username="awa2", email="AWA@EXEMPLE.CD")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Un compte utilise déjà cette adresse e-mail.")
        self.assertEqual(User.objects.count(), 1)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)

    def test_connexion_mene_aux_cours(self):
        response = self.client.post(reverse("accounts:login"), {"username": "awa", "password": PASSWORD})
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_mauvais_mot_de_passe_refuse_avec_un_message(self):
        response = self.client.post(reverse("accounts:login"), {"username": "awa", "password": "faux"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "Nom d&#x27;utilisateur ou mot de passe incorrect.")

    def test_deconnexion_refuse_get(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)   # méthode non autorisée

    def test_deconnexion_en_post(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        User.objects.create_user("bob", email="bob@exemple.cd", password=PASSWORD)

    def donnees(self, **modifs):
        data = {
            "first_name": "Awa",
            "last_name": "Mbuyi",
            "email": "awa@exemple.cd",
            "university": "UCC",
            "program": "L3 Informatique",
        }
        data.update(modifs)
        return data

    def test_profil_exige_une_connexion(self):
        url = reverse("accounts:profile")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_modification_du_profil(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.donnees())
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.university, "UCC")

    def test_email_d_un_autre_compte_refuse(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.donnees(email="BOB@exemple.cd"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Un compte utilise déjà cette adresse e-mail.")


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        self.url = reverse("accounts:password_change")

    def test_exige_une_connexion(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_changement_reussi_et_session_conservee(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            "old_password": PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertIn("_auth_user_id", self.client.session)   # toujours connecté

    def test_ancien_mot_de_passe_faux_refuse(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            "old_password": "pas-le-bon",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))   # inchangé