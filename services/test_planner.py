from collections import defaultdict
from datetime import date

from django.test import SimpleTestCase

from .planner import CourseInfo, ExamInfo, build_plan, charge_du_jour

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