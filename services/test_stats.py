from datetime import date, timedelta

from django.test import SimpleTestCase

from .stats import compute_streak

J = date(2026, 11, 16)
D = timedelta(days=1)


class StreakTests(SimpleTestCase):
    def test_serie_qui_inclut_aujourd_hui(self):
        self.assertEqual(compute_streak({J, J - D, J - 2 * D}, J), (3, 3))

    def test_serie_encore_vivante_si_revise_hier(self):
        self.assertEqual(compute_streak({J - D, J - 2 * D}, J), (2, 2))

    def test_serie_cassee_mais_record_conserve(self):
        self.assertEqual(compute_streak({J - 3 * D, J - 5 * D, J - 6 * D, J - 7 * D}, J), (0, 3))

    def test_aucune_revision(self):
        self.assertEqual(compute_streak(set(), J), (0, 0))