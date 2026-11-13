"""Needs numpy and scipy."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A


class Geometry(unittest.TestCase):
    def test_zone_from_each_side(self):
        # home defends the left end, so it attacks toward positive x
        self.assertEqual(A.zone_and_side(69, 22, 'left', True)[0], 'O')
        self.assertEqual(A.zone_and_side(69, 22, 'left', False)[0], 'D')
        self.assertEqual(A.zone_and_side(-69, 22, 'left', True)[0], 'D')
        self.assertEqual(A.zone_and_side(0, 0, 'left', True), ('N', ''))
        self.assertEqual(A.zone_and_side(69, 22, 'right', True)[0], 'D')

    def test_side_is_mirrored_for_the_two_players(self):
        home = A.zone_and_side(69, 22, 'left', True)[1]
        away = A.zone_and_side(69, 22, 'left', False)[1]
        self.assertEqual((home, away), ('L', 'R'))

    def test_skater_edge(self):
        self.assertEqual(A.skater_edge('1551', True), 0)
        self.assertEqual(A.skater_edge('1451', True), 1)     # away has four skaters
        self.assertEqual(A.skater_edge('1451', False), -1)
        self.assertEqual(A.skater_edge('', True), 0)

    def test_strong_side_feature(self):
        row = dict(x='69', y='22', home_defends='left', situation='1551')
        self.assertEqual(A.player_features(row, True, 'L')[0]['strong_side'], 1.0)
        self.assertEqual(A.player_features(row, True, 'R')[0]['strong_side'], -1.0)
        self.assertEqual(A.player_features(row, False, 'R')[0]['strong_side'], 1.0)


class Model(unittest.TestCase):
    def test_recovers_planted_skill_and_home_edge(self):
        rng = np.random.default_rng(3)
        n_players, n = 40, 60000
        true = rng.normal(0, 0.25, n_players)
        a, b = rng.integers(0, n_players, n), rng.integers(0, n_players, n)
        keep = a != b
        a, b = a[keep], b[keep]
        home = rng.integers(0, 2, len(a)) * 2 - 1.0          # +1 if a is at home
        p = 1 / (1 + np.exp(-(true[a] - true[b] + 0.10 * home)))
        a_wins = rng.random(len(a)) < p
        w, l = np.where(a_wins, a, b), np.where(a_wins, b, a)
        X = np.where(a_wins, home, -home)[:, None]
        skill, beta = A.fit(w, l, X, n_players, 0.25)
        self.assertGreater(np.corrcoef(skill, true)[0, 1], 0.95)
        self.assertAlmostEqual(beta[0], 0.10, delta=0.03)

    def test_shrinks_players_with_few_draws(self):
        # player 2 wins his only three draws; he must not be rated above a proven 60% player
        w = np.array([0] * 600 + [1] * 400 + [2] * 3)
        l = np.array([1] * 600 + [0] * 400 + [0] * 3)
        skill, _ = A.fit(w, l, np.zeros((len(w), 1)), 3, 0.2)
        self.assertGreater(skill[0], skill[2])
        self.assertGreater(skill[0], skill[1])

    def test_rating_scale(self):
        self.assertAlmostEqual(float(A.to_pct(0.0)), 50.0)
        self.assertAlmostEqual(float(A.to_pct(0.2)), 54.98, places=1)


class Value(unittest.TestCase):
    def test_win_value_by_zone(self):
        mk = lambda sw, sl, gw, gl: dict(sog_w=sw, sog_l=sl, goals_w=gw, goals_l=gl)
        rows = [mk(1, 0, 1, 0), mk(1, 0, 0, 0), mk(0, 1, 0, 0), mk(0, 1, 0, 1)]
        zones = np.array(['O', 'O', 'D', 'D'])
        with self.assertRaises(ZeroDivisionError):
            A.win_value(rows[:2], np.array(['O', 'O']))       # no neutral or defensive draws
        rows += [mk(0, 0, 0, 0)]
        zones = np.append(zones, 'N')
        v, sh = A.win_value(rows, zones)
        self.assertAlmostEqual(sh, 0.5)
        # winning in the offensive zone: +1 shot; losing there means the opponent won in his defensive zone and still took -1
        self.assertAlmostEqual(v['O']['shot_swing'], 1 + (-1))
        self.assertAlmostEqual(v['D']['shot_swing'], -1 + 1)


if __name__ == '__main__':
    unittest.main()


def test_specialist_value_counts_only_draws_won_above_average():
    value = {'O': {'goal_swing': 0.02}, 'N': {'goal_swing': 0.01}}
    assert A.specialist_value(50, 20, 1.0, value)['goals'] == 0
    out = A.specialist_value(60, 10, 1.0, value, games=82)
    assert out['extra_wins'] == 82.0                      # 82 games x 10 draws x 10 points
    assert out['goals'] == round(82 * 0.02, 2)
    half = A.specialist_value(60, 10, 0.5, value, games=82)
    assert half['goals'] == round(82 * 0.015, 2)
    assert out['wins'] == round(out['goals'] / A.GOALS_PER_WIN, 2)


def test_usage_ranks_player_seasons():
    rows = [dict(season='2024', winner=str(i % 60), loser=str(60 + i % 3)) for i in range(600)]
    u = A.usage(rows)[0]
    assert u['busiest'] == 200 and u['tenth'] == 10 and u['fiftieth'] == 10
