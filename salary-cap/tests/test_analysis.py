import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as a


class Helpers(unittest.TestCase):
    def test_pearson_perfect_lines(self):
        self.assertAlmostEqual(a.pearson([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(a.pearson([1, 2, 3], [6, 4, 2]), -1.0)

    def test_slope(self):
        b, c = a.slope_intercept([0, 1, 2], [1, 3, 5])
        self.assertAlmostEqual(b, 2.0)
        self.assertAlmostEqual(c, 1.0)

    def test_ranks_with_ties(self):
        self.assertEqual(a.ranks([10, 30, 30, 5]), [3.0, 1.5, 1.5, 4.0])

    def test_noll_scully_coin_flip_league_is_near_one(self):
        import random
        rng = random.Random(1)
        vals = []
        for _ in range(300):
            pcts = [sum(rng.random() < .5 for _ in range(162)) / 162 for _ in range(30)]
            vals.append(a.noll_scully(pcts, 162))
        self.assertAlmostEqual(a.mean(vals), 1.0, delta=0.05)

    def test_noll_scully_known_value(self):
        # every team at .600 or .400 over 100 games: spread .1, coin-flip spread .05
        self.assertAlmostEqual(a.noll_scully([.6, .4, .6, .4], 100), 2.0)


class Simulator(unittest.TestCase):
    def test_cap_and_floor_by_hand(self):
        s = a.apply_cap_floor(dict(A=300, B=200, C=100), cap=250, floor=150)
        self.assertEqual(s['new'], dict(A=250, B=200, C=150))
        self.assertEqual((s['cut'], s['add'], s['net']), (50, 50, 0))
        self.assertEqual((list(s['over']), list(s['under'])), (['A'], ['C']))

    def test_no_change_when_limits_are_wide(self):
        s = a.apply_cap_floor(dict(A=300, B=100), cap=999, floor=0)
        self.assertEqual((s['cut'], s['add']), (0, 0))

    def test_ratio(self):
        self.assertAlmostEqual(a.top_bottom_ratio([10, 10, 5, 5], k=2), 2.0)


class Data(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pay, cls.mlb = a.load_payrolls(), a.load_mlb()

    def test_thirty_teams_every_season(self):
        for y in range(2000, 2027):
            self.assertEqual(sum(1 for (_, s) in self.mlb if s == y), 30, y)
            self.assertEqual(sum(1 for (_, s) in self.pay if s == y), 30, y)

    def test_wins_equal_losses_league_wide(self):
        for y in range(2000, 2027):
            w = sum(r['w'] for (_, s), r in self.mlb.items() if s == y)
            l = sum(r['l'] for (_, s), r in self.mlb.items() if s == y)
            self.assertEqual(w, l, y)

    def test_one_champion_every_season(self):
        for y in range(2000, 2027):
            self.assertEqual(sum(r['champion'] for (_, s), r in self.mlb.items() if s == y), 1, y)

    def test_known_values(self):
        self.assertEqual(self.mlb[('SEA', 2001)]['w'], 116)
        self.assertEqual(self.mlb[('BOS', 2004)]['champion'], 1)
        self.assertEqual(self.pay[('NYY', 2000)]['opening_day'], 107.59)
        self.assertIsNone(self.pay[('NYY', 2011)]['cbt'])

    def test_other_leagues_average_five_hundred(self):
        for name, lg in (('NBA', a.load_simple('nba_standings.txt')), ('NFL', a.load_nfl())):
            for y, teams in lg.items():
                g = sum(v[1] for v in teams.values())
                self.assertAlmostEqual(sum(v[0] * v[1] for v in teams.values()) / g, .5, places=6, msg=f'{name} {y}')

    def test_franchise_moves_keep_one_identity(self):
        nhl = a.load_simple('nhl_standings.txt', a.NHL_FRANCHISE)
        self.assertIn(53, nhl[1995]); self.assertIn(53, nhl[2025]); self.assertNotIn(68, nhl[2025])
        nfl = a.load_nfl()
        self.assertEqual(len(nfl[2001]), 31); self.assertEqual(len(nfl[2025]), 32)
        self.assertIn('LV', nfl[2005])

    def test_proposal_names_the_same_teams_as_the_league(self):
        base = {t: self.pay[(t, 2026)]['cbt'] for (t, y) in self.mlb if y == 2026}
        s = a.apply_cap_floor(base, a.PROPOSAL['cap'], a.PROPOSAL['floor'])
        self.assertEqual(sorted(s['over']), sorted(a.PROPOSAL['reported_over']))
        self.assertEqual(sorted(s['under']), sorted(a.PROPOSAL['reported_under']))
        self.assertLess(abs(s['cut'] - a.PROPOSAL['reported_cut']) / a.PROPOSAL['reported_cut'], .05)
        self.assertLess(abs(s['add'] - a.PROPOSAL['reported_add']) / a.PROPOSAL['reported_add'], .05)


if __name__ == '__main__':
    unittest.main()
