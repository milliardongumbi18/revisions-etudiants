from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
import json
import re
from unittest import mock

from django.core import mail
from django.core.mail import send_mail
from django.test import override_settings
from courses.models import Course

from core.demo import DEMO_EMAIL, DEMO_USERNAME
from io import BytesIO

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

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
    
    def test_arobase_refuse_dans_le_nom_d_utilisateur(self):
        response = self.client.post(reverse("accounts:signup"), self.donnees(username="@awa"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="@awa").exists())
        self.assertFormError(response.context["form"], "username",
                             "Lettres, chiffres et . + - _ uniquement (pas de @ ni d'espace).")


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
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD, university="UNIKIN")
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

    def test_profil_affiche_les_infos_sans_formulaire(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "UNIKIN")
        self.assertContains(response, reverse("accounts:profile_edit"))
        self.assertNotContains(response, 'name="first_name"')   # aucun champ modifiable

    def test_page_de_modification_exige_une_connexion(self):
        url = reverse("accounts:profile_edit")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_modification_du_profil(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile_edit"), self.donnees())
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.university, "UCC")

    def test_email_d_un_autre_compte_refuse(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile_edit"), self.donnees(email="BOB@exemple.cd"))
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
        

class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()   # compteurs d'échecs remis à zéro entre les tests
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        self.url = reverse("accounts:login")

    def echouer(self, fois):
        for _ in range(fois):
            self.client.post(self.url, {"username": "awa", "password": "faux"})

    def test_blocage_apres_5_echecs_meme_avec_le_bon_mot_de_passe(self):
        self.echouer(5)
        response = self.client.post(self.url, {"username": "awa", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trop de tentatives")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_connexion_reussie_remet_le_compteur_a_zero(self):
        self.echouer(4)
        self.client.post(self.url, {"username": "awa", "password": PASSWORD})   # réussite
        self.client.logout()
        self.echouer(4)
        response = self.client.post(self.url, {"username": "awa", "password": PASSWORD})
        self.assertEqual(response.status_code, 302)   # toujours autorisé
    

class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()   # remet à zéro l'anti-abus (1 e-mail / 5 min)
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        self.url = reverse("accounts:password_reset")

    def demander(self, email="awa@exemple.cd"):
        return self.client.post(self.url, {"email": email})

    def test_page_mot_de_passe_oublie_s_affiche(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_envoie_un_lien_a_une_adresse_connue(self):
        response = self.demander("AWA@exemple.cd")   # majuscules : le compte est quand même retrouvé
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["awa@exemple.cd"])
        self.assertIn("/compte/reinitialiser/", mail.outbox[0].body)

    def test_adresse_inconnue_meme_page_et_aucun_email(self):
        response = self.demander("inconnu@exemple.cd")
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_parcours_complet_jusqu_au_nouveau_mot_de_passe(self):
        self.demander()
        lien = re.search(r"https?://\S+", mail.outbox[0].body).group(0)
        response = self.client.get(lien, follow=True)   # Django retire le jeton de l'URL puis redirige
        formulaire = response.redirect_chain[-1][0]
        response = self.client.post(formulaire, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.assertTrue(self.client.login(username="awa", password=NEW_PASSWORD))

    def test_un_seul_email_par_tranche_de_5_minutes(self):
        self.demander()
        self.demander()
        self.assertEqual(len(mail.outbox), 1)

    def test_jamais_d_email_pour_le_compte_demo(self):
        User.objects.create_user(DEMO_USERNAME, email=DEMO_EMAIL, password=PASSWORD)
        self.demander(DEMO_EMAIL)
        self.assertEqual(len(mail.outbox), 0)


class BrevoBackendTests(TestCase):
    @override_settings(EMAIL_BACKEND="core.email_backend.BrevoEmailBackend", BREVO_API_KEY="cle-de-test")
    def test_envoie_par_l_api_https_de_brevo(self):
        with mock.patch("core.email_backend.urllib.request.urlopen") as urlopen:
            send_mail("Sujet", "Corps du message", "Révisions Étudiants <envoi@exemple.cd>", ["awa@exemple.cd"])
        requete = urlopen.call_args.args[0]
        corps = json.loads(requete.data)
        self.assertEqual(requete.get_header("Api-key"), "cle-de-test")
        self.assertEqual(corps["sender"], {"name": "Révisions Étudiants", "email": "envoi@exemple.cd"})
        self.assertEqual(corps["to"], [{"email": "awa@exemple.cd"}])
        self.assertEqual(corps["subject"], "Sujet")


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        Course.objects.create(owner=self.user, title="Algorithmique")
        self.url = reverse("accounts:delete_account")

    def test_exige_une_connexion(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_mauvais_mot_de_passe_ne_supprime_rien(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"password": "faux"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "password", "Mot de passe incorrect.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_bon_mot_de_passe_supprime_le_compte_et_ses_donnees(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"password": PASSWORD})
        self.assertRedirects(response, reverse("core:home"))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Course.objects.filter(title="Algorithmique").exists())   # supprimé en cascade
        self.assertNotIn("_auth_user_id", self.client.session)                  # déconnecté

    def test_compte_demo_ne_peut_pas_etre_supprime(self):
        demo = User.objects.create_user(DEMO_USERNAME, email=DEMO_EMAIL, password=PASSWORD)
        self.client.force_login(demo)
        response = self.client.post(self.url, {"password": PASSWORD})
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertTrue(User.objects.filter(pk=demo.pk).exists())

    def test_bouton_visible_sur_le_profil(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("accounts:profile")), self.url)


# Fichiers gardés en mémoire pendant les tests : rien sur le disque, rien sur Supabase
STOCKAGE_MEMOIRE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def image_test(format="PNG", taille=(800, 600), exif=None):
    tampon = BytesIO()
    options = {"exif": exif} if exif else {}
    Image.new("RGB", taille, (240, 138, 46)).save(tampon, format=format, **options)
    return SimpleUploadedFile(f"photo.{format.lower()}", tampon.getvalue(), content_type=f"image/{format.lower()}")


@override_settings(STORAGES=STOCKAGE_MEMOIRE)
class AvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", email="awa@exemple.cd", password=PASSWORD)
        self.client.force_login(self.user)

    def envoyer(self, fichier):
        return self.client.post(reverse("accounts:avatar_update"), {"avatar": fichier})

    def test_photo_recadree_convertie_et_nettoyee(self):
        exif = Image.Exif()
        exif[0x010F] = "Appareil secret"   # 0x010F = marque de l'appareil photo
        response = self.envoyer(image_test("JPEG", (1200, 800), exif=exif.tobytes()))
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith(".webp"))
        with self.user.avatar.open("rb") as fichier:
            image = Image.open(fichier)
            image.load()
        self.assertEqual(image.format, "WEBP")
        self.assertEqual(image.size, (400, 400))
        self.assertNotIn(0x010F, image.getexif())   # métadonnées supprimées

    def test_fichier_qui_n_est_pas_une_image_refuse(self):
        self.envoyer(SimpleUploadedFile("photo.png", b"pas une image", content_type="image/png"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_format_non_accepte_refuse(self):
        self.envoyer(image_test("GIF"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_image_trop_lourde_refusee(self):
        self.envoyer(SimpleUploadedFile("photo.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_nouvelle_photo_remplace_et_supprime_l_ancienne(self):
        self.envoyer(image_test())
        self.user.refresh_from_db()
        ancienne = self.user.avatar.name
        self.envoyer(image_test())
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.avatar.name, ancienne)
        self.assertFalse(default_storage.exists(ancienne))

    def test_retirer_la_photo(self):
        self.envoyer(image_test())
        self.user.refresh_from_db()
        nom = self.user.avatar.name
        self.client.post(reverse("accounts:avatar_delete"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        self.assertFalse(default_storage.exists(nom))

    def test_envoi_uniquement_en_post(self):
        self.assertEqual(self.client.get(reverse("accounts:avatar_update")).status_code, 405)

    def test_compte_demo_ne_peut_pas_changer_de_photo(self):
        demo = User.objects.create_user(DEMO_USERNAME, email=DEMO_EMAIL, password=PASSWORD)
        self.client.force_login(demo)
        self.envoyer(image_test())
        demo.refresh_from_db()
        self.assertFalse(demo.avatar)