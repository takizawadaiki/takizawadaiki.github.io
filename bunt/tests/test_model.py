import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A
import model as M

TOTALS = dict(G=4860, PA=182926, AB=163664, R=21614, H=40138, **{'2B': 7745, '3B': 628}, HR=5650, SB=3440, CS=989, SH=560, SF=1307,
              BB=15379, IBB=556, HBP=1928, SO=40645, GDP=3122)   # MLB 2025


class Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = M.calibrate(TOTALS)

    def test_rates_sum_to_one(self):
        self.assertAlmostEqual(sum(M.league_rates(TOTALS).values()), 1.0)
        self.assertAlmostEqual(sum(M.scale_batter(M.league_rates(TOTALS), 0.5).values()), 1.0)

    def test_every_state_has_probabilities_that_sum_to_one(self):
        for outs, bases in M.STATES:
            total = sum(p for p, *_ in M.transitions(outs, bases, self.cal['rates'], self.cal['dp'], self.cal['sf']))
            self.assertAlmostEqual(total, 1.0, places=9, msg=f'{outs} {bases}')

    def test_runner_and_out_count_is_conserved(self):
        # runners before + batter = runners after + runs + outs made
        for outs, bases in M.STATES:
            for p, runs, o, nb in M.transitions(outs, bases, self.cal['rates'], self.cal['dp'], self.cal['sf']):
                if o < 3:
                    self.assertEqual(bases.count('1') + 1, nb.count('1') + runs + (o - outs), msg=f'{outs} {bases} -> {o} {nb}')

    def test_model_reproduces_league_scoring(self):
        self.assertAlmostEqual(self.cal['model_runs_per_inning'], self.cal['actual_runs_per_inning'], delta=0.03)

    def test_more_runners_and_fewer_outs_are_worth_more(self):
        r = self.cal['runs']
        self.assertGreater(r[(0, '100')], r[(0, '000')])
        self.assertGreater(r[(0, '000')], r[(1, '000')])
        self.assertGreater(r[(1, '000')], r[(2, '000')])
        self.assertGreater(r[(0, '111')], r[(0, '110')])

    def test_perfect_sacrifice_lands_on_the_next_state(self):
        runs, score = M.bunt_value(0, '100', {'sacrifice': 1.0}, self.cal)
        self.assertAlmostEqual(runs, self.cal['runs'][(1, '010')])
        self.assertAlmostEqual(score, self.cal['p_score'][(1, '010')])

    def test_sacrifice_with_runner_on_third_scores_him(self):
        runs, score = M.bunt_value(0, '001', {'sacrifice': 1.0}, self.cal)
        self.assertAlmostEqual(score, 1.0)
        self.assertAlmostEqual(runs, 1 + self.cal['runs'][(1, '000')])

    def test_a_weaker_hitter_is_worth_less_swinging(self):
        weak = M.batter_then_league(0, '100', M.scale_batter(self.cal['rates'], 0.5), self.cal)[0]
        avg = M.batter_then_league(0, '100', self.cal['rates'], self.cal)[0]
        self.assertLess(weak, avg)
        self.assertAlmostEqual(avg, self.cal['runs'][(0, '100')])


class Helpers(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(A.classify('sac_bunt', 0, 1), 'sacrifice')
        self.assertEqual(A.classify('single', 0, 0), 'safe')
        self.assertEqual(A.classify('force_out', 0, 1), 'lead_out')
        self.assertEqual(A.classify('field_out', 0, 1), 'fail')
        self.assertEqual(A.classify('strikeout', 1, 2), 'fail')
        self.assertEqual(A.classify('sac_bunt_double_play', 0, 2), 'double')

    def test_wilson_interval_contains_the_estimate(self):
        lo, hi = A.wilson(30, 100)
        self.assertLess(lo, 0.30); self.assertGreater(hi, 0.30)


if __name__ == '__main__':
    unittest.main()
