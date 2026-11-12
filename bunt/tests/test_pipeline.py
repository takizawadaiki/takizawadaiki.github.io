"""Checks the plate-appearance reduction on a tiny hand-made game. Needs pandas and pyarrow."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
import season as S


def pitch(ab, n, inning, top, outs, on1, on2, on3, bat, post, fld, events=None, desc='ball', des='', batter=1, pitcher=9, home=0, away=0):
    return dict(game_pk=1, game_date='2025-04-01', game_type='R', at_bat_number=ab, pitch_number=n, inning=inning,
                inning_topbot='Top' if top else 'Bot', outs_when_up=outs, on_1b=on1, on_2b=on2, on_3b=on3, bat_score=bat,
                post_bat_score=post, fld_score=fld, post_home_score=home, post_away_score=away, home_team='HOM', away_team='AWY',
                events=events, description=desc, des=des, batter=batter, pitcher=pitcher, woba_value=0.0, woba_denom=1.0)


class Reduce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [
            # top 1: single, sacrifice bunt, single scores the runner, two outs
            pitch(1, 1, 1, True, 0, None, None, None, 0, 0, 0, 'single', 'hit_into_play', 'A singles.', batter=1),
            pitch(2, 1, 1, True, 0, 11.0, None, None, 0, 0, 0, None, 'foul_bunt', '', batter=2),
            pitch(2, 2, 1, True, 0, 11.0, None, None, 0, 0, 0, 'sac_bunt', 'hit_into_play', 'B out on a sacrifice bunt.', batter=2),
            pitch(3, 1, 1, True, 1, None, 11.0, None, 0, 1, 0, 'single', 'hit_into_play', 'C singles. A scores.', batter=3, away=1),
            pitch(4, 1, 1, True, 1, 13.0, None, None, 1, 1, 0, 'grounded_into_double_play', 'hit_into_play', 'D grounds into a double play.', batter=4, away=1),
            # bottom 1: strikeout on a foul bunt with a runner on, then two more outs
            pitch(5, 1, 1, False, 0, None, None, None, 0, 0, 1, 'walk', 'ball', 'E walks.', batter=5, away=1),
            pitch(6, 1, 1, False, 0, 15.0, None, None, 0, 0, 1, 'strikeout', 'foul_bunt', 'F strikes out on a foul bunt.', batter=6, away=1),
            pitch(7, 1, 1, False, 1, 15.0, None, None, 0, 0, 1, 'field_out', 'hit_into_play', 'G flies out.', batter=7, away=1),
            pitch(8, 1, 1, False, 2, 15.0, None, None, 0, 0, 1, 'field_out', 'hit_into_play', 'H flies out.', batter=8, away=1),
        ]
        cls.pa = S.to_plate_appearances(pd.DataFrame(rows), 2025).set_index('at_bat_number')

    def test_one_row_per_plate_appearance(self):
        self.assertEqual(len(self.pa), 8)

    def test_state_at_the_start_of_the_bunt(self):
        b = self.pa.loc[2]
        self.assertEqual((b.outs, b.b1, b.b2, b.b3), (0, True, False, False))
        self.assertTrue(b.bunt and b.bunt_in_play and b.any_bunt_pitch)

    def test_runs_for_the_rest_of_the_inning(self):
        self.assertEqual(self.pa.loc[2].runs_rest, 1)   # the runner later scored
        self.assertEqual(self.pa.loc[3].runs_rest, 1)
        self.assertEqual(self.pa.loc[4].runs_rest, 0)   # the run was already in
        self.assertEqual(self.pa.loc[6].runs_rest, 0)

    def test_state_the_next_batter_found(self):
        b = self.pa.loc[2]
        self.assertEqual((b.after_outs, b.after_b1, b.after_b2), (1, False, True))
        self.assertEqual(self.pa.loc[4].after_outs, 3)  # inning over

    def test_strikeout_on_a_foul_bunt_counts_as_a_bunt(self):
        self.assertTrue(self.pa.loc[6].bunt and self.pa.loc[6].bunt_strikeout and not self.pa.loc[6].bunt_in_play)

    def test_an_ordinary_single_is_not_a_bunt(self):
        self.assertFalse(self.pa.loc[1].bunt)

    def test_winner_and_team(self):
        self.assertTrue(self.pa.loc[1].bat_won)     # away team leads 1-0 at the end
        self.assertFalse(self.pa.loc[5].bat_won)
        self.assertEqual(self.pa.loc[1].bat_team, 'AWY')
        self.assertEqual(self.pa.loc[5].bat_team, 'HOM')


if __name__ == '__main__':
    unittest.main()
