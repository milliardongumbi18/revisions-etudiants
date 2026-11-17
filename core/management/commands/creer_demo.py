from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.demo import DEMO_USERNAME, CompteDemoIndisponible, creer_compte_demo


class Command(BaseCommand):
    help = "Crée ou réinitialise le compte de démonstration rempli d'exemples."

    def add_arguments(self, parser):
        parser.add_argument("--mot-de-passe", dest="mot_de_passe", default="",
                            help="Sinon : variable d'environnement DEMO_PASSWORD.")

    def handle(self, *args, **options):
        mot_de_passe = options["mot_de_passe"] or settings.DEMO_PASSWORD
        if not mot_de_passe:
            raise CommandError("Indique un mot de passe : --mot-de-passe \"…\" ou la variable DEMO_PASSWORD.")
        try:
            resume = creer_compte_demo(mot_de_passe)
        except CompteDemoIndisponible as exc:
            # Avertissement sans échec : un déploiement ne doit pas casser pour ça
            self.stderr.write(self.style.WARNING(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Compte « {DEMO_USERNAME} » prêt : {resume['cours']} cours, "
            f"{resume['questions']} questions, {resume['revisions']} révisions simulées."
        ))