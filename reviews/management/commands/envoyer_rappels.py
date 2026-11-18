from django.core.management.base import BaseCommand

from reviews.rappels import envoyer_rappels


class Command(BaseCommand):
    help = "Envoie le rappel quotidien aux étudiants qui l'ont activé et ont des révisions dues."

    def handle(self, *args, **options):
        envoyes = envoyer_rappels()
        self.stdout.write(self.style.SUCCESS(f"{envoyes} rappel(s) envoyé(s)."))