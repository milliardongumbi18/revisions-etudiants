from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


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
        # bulk_create n'appelle pas save() : c'est donc la contrainte en base qui doit bloquer.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(username="awa2", email="AWA@Exemple.cd")])