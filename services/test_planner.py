from collections import defaultdict
from datetime import date

from django.test import SimpleTestCase

from datetime import time

from .planner import Block, CourseInfo, DayPlan, ExamInfo, build_plan, charge_du_jour, placer_horaires, poids

LUNDI = date(2026, 11, 16)   # un lundi


class PlannerTests(SimpleTestCase):
    def test_temps_disponible_selon_les_heures_de_cours(self):
        self.assertEqual(charge_du_jour(0), (120, "libre"))
        self.assertEqual(charge_du_jour(300), (30, "très chargé"))

    def test_jour_libre_reparti_equitablement(self):
        cours = [CourseInfo(1, "Droit"), CourseInfo(2, "Chimie")]
        jour = build_plan(LUNDI, cours, {}, [], jours=1)[0]
        self.assertEqual({b.course_id: b.minutes for b in jour.blocks}, {1: 60, 2: 60})

    def test_examen_proche_prioritaire(self):
        cours = [CourseInfo(1, "Droit"), CourseInfo(2, "Chimie")]
        plan = build_plan(LUNDI, cours, {}, [ExamInfo(2, date(2026, 11, 19))], jours=3)
        total = defaultdict(int)
        for jour in plan:
            for bloc in jour.blocks:
                if bloc.kind == "cours":
                    total[bloc.course_id] += bloc.minutes
        self.assertGreater(total[2], total[1])

    def test_jour_d_examen_sans_revision_de_ce_cours(self):
        jour = build_plan(LUNDI, [CourseInfo(1, "Droit")], {}, [ExamInfo(1, LUNDI, "Examen final")], jours=1)[0]
        self.assertEqual(jour.blocks[0].kind, "examen")
        self.assertFalse([b for b in jour.blocks if b.kind == "cours"])

    def test_repetition_espacee_en_premier_un_jour_tres_charge(self):
        jour = build_plan(LUNDI, [CourseInfo(1, "Droit")], {0: 300}, [], revisions_par_date={LUNDI: 12}, jours=1)[0]
        self.assertEqual((jour.budget, jour.load), (30, "très chargé"))
        self.assertEqual((jour.blocks[0].kind, jour.blocks[0].minutes), ("revisions", 12))

    def test_jour_libre_commence_le_matin_avec_des_pauses(self):
        jour = DayPlan(date(2026, 1, 5), 0, 120, "libre", [Block("revisions", "SRS", 20), Block("cours", "Droit", 60)])
        placer_horaires(jour, [])
        self.assertEqual(jour.blocks[0].start, time(9, 0))
        self.assertEqual(jour.blocks[1].start, time(9, 30))   # 20 min + 10 min de pause
        self.assertEqual(jour.blocks[1].end, time(10, 30))

    def test_jour_de_cours_revisions_apres_le_dernier_cours(self):
        soir = DayPlan(date(2026, 1, 5), 240, 60, "chargé", [Block("cours", "Droit", 30)])
        placer_horaires(soir, [time(10, 0), time(16, 30)])
        self.assertEqual(soir.blocks[0].start, time(17, 30))    # 1 h après le dernier cours

        matin = DayPlan(date(2026, 1, 5), 120, 90, "léger", [Block("cours", "Droit", 30)])
        placer_horaires(matin, [time(10, 0)])
        self.assertEqual(matin.blocks[0].start, time(15, 0))    # jamais avant 15 h un jour de cours

    def test_interro_preparee_sur_7_jours_seulement(self):
        interro = [ExamInfo(1, date(2026, 11, 26), "Interrogation", "interro")]
        self.assertEqual(poids(1, date(2026, 11, 16), interro), 1.0)    # J-10 : pas encore
        self.assertGreater(poids(1, date(2026, 11, 23), interro), 1.0)  # J-3 : le cours prend du poids

    def test_examen_pese_plus_qu_une_interro(self):
        veille = date(2026, 11, 25)
        examen = [ExamInfo(1, date(2026, 11, 26), "Examen", "examen")]
        interro = [ExamInfo(1, date(2026, 11, 26), "Interrogation", "interro")]
        self.assertGreater(poids(1, veille, examen), poids(1, veille, interro))