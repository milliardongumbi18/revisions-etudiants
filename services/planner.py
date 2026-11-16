"""
Génération du planning de révisions (fonction pure, sans Django : facile à tester).

Pour chaque jour :
1. Temps disponible selon la charge de cours du jour (jour libre → plus de révision).
2. D'abord la répétition espacée (les questions SM-2 dues ce jour-là).
3. Le reste est réparti en blocs de 30 min entre les cours. Le poids d'un cours
   augmente à l'approche de son examen ; un équilibrage sur toute la période
   évite d'oublier un cours.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

BLOC = 30                 # minutes
HORIZON_JOURS = 14
FENETRE_EXAMEN = 21       # un examen commence à peser 21 jours avant


def format_duree(minutes):
    heures, reste = divmod(minutes, 60)
    if heures and reste:
        return f"{heures} h {reste:02d}"
    if heures:
        return f"{heures} h"
    return f"{reste} min"


@dataclass(frozen=True)
class CourseInfo:
    id: int
    title: str
    color: str = "indigo"


@dataclass(frozen=True)
class ExamInfo:
    course_id: int
    date: date
    title: str = "Examen"


@dataclass
class Block:
    kind: str               # "examen", "revisions" (SM-2) ou "cours"
    title: str
    minutes: int = 0
    color: str = "indigo"
    course_id: int | None = None

    @property
    def duree(self):
        return format_duree(self.minutes)


@dataclass
class DayPlan:
    date: date
    class_minutes: int
    budget: int
    load: str
    blocks: list = field(default_factory=list)

    @property
    def class_duree(self):
        return format_duree(self.class_minutes)


def charge_du_jour(minutes_de_cours):
    """(minutes de révision disponibles, étiquette de charge) selon le temps passé en cours."""
    if minutes_de_cours == 0:
        return 120, "libre"
    if minutes_de_cours <= 120:
        return 90, "léger"
    if minutes_de_cours <= 240:
        return 60, "chargé"
    return 30, "très chargé"


def poids(course_id, jour, exams):
    """1 par défaut ; jusqu'à ~8 la veille de l'examen (montée progressive sur 21 jours)."""
    prochains = [e.date for e in exams if e.course_id == course_id and e.date > jour]
    if not prochains:
        return 1.0
    ecart = (min(prochains) - jour).days
    return 1.0 + max(0, FENETRE_EXAMEN + 1 - ecart) / 3


def build_plan(debut, courses, minutes_par_jour_semaine, exams, revisions_par_date=None, jours=HORIZON_JOURS):
    """
    debut : date du premier jour ; courses : [CourseInfo] ;
    minutes_par_jour_semaine : {0 (lundi) … 6 (dimanche): minutes de cours} ;
    exams : [ExamInfo] ; revisions_par_date : {date: nombre de questions SM-2 dues}.
    """
    revisions_par_date = revisions_par_date or {}
    par_id = {c.id: c for c in courses}
    alloue = {c.id: 0 for c in courses}   # minutes déjà données à chaque cours (équilibrage global)
    planning = []

    for decalage in range(jours):
        jour = debut + timedelta(days=decalage)
        minutes_cours = minutes_par_jour_semaine.get(jour.weekday(), 0)
        budget, charge = charge_du_jour(minutes_cours)
        journee = DayPlan(jour, minutes_cours, budget, charge)

        # 1. Examens du jour : affichés, et le cours n'est plus révisé ce jour-là
        en_examen = set()
        for examen in exams:
            if examen.date == jour:
                cours = par_id.get(examen.course_id)
                titre = f"{examen.title} · {cours.title}" if cours else examen.title
                journee.blocks.append(Block("examen", titre, 0, cours.color if cours else "indigo", examen.course_id))
                en_examen.add(examen.course_id)

        # 2. Répétition espacée : ~1 min par question due (entre 10 et 30 min)
        restant = budget
        nb = revisions_par_date.get(jour, 0)
        if nb:
            minutes = min(restant, min(30, max(10, nb)))
            journee.blocks.append(Block("revisions", f"Répétition espacée · {nb} question{'s' if nb > 1 else ''}", minutes))
            restant -= minutes

        # 3. Blocs de 30 min : au cours dont le besoin (poids / temps déjà reçu) est le plus fort
        candidats = [c for c in courses if c.id not in en_examen]
        du_jour = {}
        while restant >= BLOC and candidats:
            choisi = max(candidats, key=lambda c: (poids(c.id, jour, exams) / (alloue[c.id] + BLOC), -c.id))
            alloue[choisi.id] += BLOC
            du_jour[choisi.id] = du_jour.get(choisi.id, 0) + BLOC
            restant -= BLOC
        for course_id, minutes in du_jour.items():
            cours = par_id[course_id]
            journee.blocks.append(Block("cours", cours.title, minutes, cours.color, course_id))

        planning.append(journee)
    return planning