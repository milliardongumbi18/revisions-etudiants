"""
Génération du planning de révisions (fonction pure, sans Django : facile à tester).

Pour chaque jour :
1. Temps disponible selon la charge de cours du jour (jour libre → plus de révision).
2. D'abord la répétition espacée (les questions SM-2 dues ce jour-là).
3. Le reste est réparti en blocs de 30 min entre les cours. Le poids d'un cours
   augmente à l'approche de son examen ; un équilibrage sur toute la période
   évite d'oublier un cours.
4. placer_horaires() donne une heure à chaque bloc (agenda).
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

BLOC = 30                 # minutes
HORIZON_JOURS = 14
# Type d'épreuve → (jours de préparation, poids ajouté la veille)
PREPARATION = {"examen": (21, 7), "interro": (7, 3)}

DEBUT_JOUR_LIBRE = time(9, 0)     # jour sans cours : on révise le matin
DEBUT_APRES_COURS = time(15, 0)   # jour de cours : jamais avant 15 h
APRES_COURS = 60                  # minutes pour rentrer et souffler après le dernier cours
PAUSE = 10                        # minutes entre deux blocs


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
    kind: str = "examen"    # "examen" ou "interro"


@dataclass
class Block:
    kind: str               # "examen", "revisions" (SM-2) ou "cours"
    title: str
    minutes: int = 0
    color: str = "indigo"
    course_id: int | None = None
    start: time | None = None   # heure de début (agenda)
    done: bool = False          # coché « Fait » par l'étudiant
    chapter_id: int | None = None   # chapitre à ouvrir (épreuve proche sur des chapitres précis)
    detail: str = ""                # ex. « ch. 2 et 3 »

    @property
    def duree(self):
        return format_duree(self.minutes)

    @property
    def end(self):
        if self.start is None:
            return None
        return (datetime.combine(date.min, self.start) + timedelta(minutes=self.minutes)).time()


@dataclass
class DayPlan:
    date: date
    class_minutes: int
    budget: int
    load: str
    blocks: list = field(default_factory=list)
    classes: list = field(default_factory=list)   # créneaux de cours à l'université ce jour-là

    @property
    def class_duree(self):
        return format_duree(self.class_minutes)

    @property
    def revision_duree(self):
        return format_duree(sum(b.minutes for b in self.blocks))

    @property
    def has_exam(self):
        return any(b.kind == "examen" for b in self.blocks)


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
    """
    1 par défaut ; monte à l'approche d'une épreuve de ce cours :
    jusqu'à 8 la veille d'un examen (sur 21 jours), jusqu'à 4 la veille d'une interro (sur 7 jours).
    """
    meilleur = 1.0
    for examen in exams:
        if examen.course_id != course_id or examen.date <= jour:
            continue
        fenetre, pic = PREPARATION.get(examen.kind, PREPARATION["examen"])
        ecart = (examen.date - jour).days
        meilleur = max(meilleur, 1.0 + pic * max(0, fenetre + 1 - ecart) / fenetre)
    return meilleur


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


def placer_horaires(journee, fins_de_cours):
    """
    Donne une heure de début à chaque bloc de révision (les examens n'en ont pas).
    fins_de_cours : heures de fin des cours à l'université ce jour-là.
    """
    if fins_de_cours:
        apres = datetime.combine(journee.date, max(fins_de_cours)) + timedelta(minutes=APRES_COURS)
        debut = max(apres, datetime.combine(journee.date, DEBUT_APRES_COURS))
    else:
        debut = datetime.combine(journee.date, DEBUT_JOUR_LIBRE)

    for bloc in journee.blocks:
        if bloc.kind == "examen":
            continue
        if debut.date() != journee.date:   # on ne déborde jamais sur le lendemain
            break
        bloc.start = debut.time()
        debut += timedelta(minutes=bloc.minutes + PAUSE)