import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
import analysis as A
import season as S

SIDE = S.SIDE_COLS


def game(home_sog, away_sog, winner, **extra):
    g = dict(season=2024, game=1, date='2024-10-01', home='AAA', away='BBB', winner=winner, decided_in='REG', first_goal=winner,
             secs_tied=1800, secs_home_lead=1800, secs_away_lead=0)
    for s in ('home', 'away'):
        for c in SIDE:
            g[f'{s}_{c}'] = 0
    g.update(home_sog=home_sog, away_sog=away_sog)
    g.update(extra)
    return g


def test_outshooting_counts_winner_with_more_shots_and_skips_even_games():
    games = [game(30, 25, 'home'), game(30, 25, 'away'), game(20, 35, 'away'), game(28, 28, 'home')]
    out = A.outshooting(games)
    assert out['games'] == 3 and out['even'] == 1
    assert abs(out['win_pct'] - 2 / 3) < 1e-9
    by = {(b['low'], b['high']): b for b in out['by_margin']}
    assert by[(4, 7)]['games'] == 2 and by[(4, 7)]['win_pct'] == 0.5
    assert by[(13, 19)]['games'] == 1 and by[(13, 19)]['win_pct'] == 1.0


def test_score_effects_rates_use_time_in_each_state():
    g = game(30, 30, 'home', home_sog_tied=10, away_sog_tied=10, home_sog_lead=5, away_sog_trail=20, secs_tied=1800, secs_home_lead=1800)
    out = A.score_effects([g])
    assert abs(out['tied']['per60'] - 20) < 1e-9          # 20 shots in two team-half-hours
    assert abs(out['lead']['per60'] - 10) < 1e-9
    assert abs(out['trail']['per60'] - 40) < 1e-9


def test_logistic_recovers_known_slope():
    rng = np.random.default_rng(1)
    x = rng.normal(size=20000)
    y = rng.random(20000) < 1 / (1 + np.exp(-(0.3 + 0.8 * x)))
    b, se = A.logistic(x[:, None], y)
    assert abs(b[0] - 0.3) < 0.06 and abs(b[1] - 0.8) < 0.06 and se[1] < 0.05


def test_ols_fits_a_line_exactly():
    x = np.arange(10.0)
    b, se, r2 = A.ols(x[:, None], 2 + 3 * x)
    assert abs(b[0] - 2) < 1e-9 and abs(b[1] - 3) < 1e-9 and r2 > 0.999999


def test_team_seasons_split_into_halves_in_date_order():
    games = []
    for i in range(60):
        first = i < 30
        games.append(game(40 if first else 20, 20 if first else 40, 'home' if first else 'away', game=i, date=f'2024-{1 + i // 28:02d}-{1 + i % 28:02d}',
                          home_goals=3 if first else 1, away_goals=1 if first else 3))
    teams = {t['team']: t for t in A.team_seasons_from_games(games)}
    a = teams['AAA']
    assert a['first']['win_pct'] == 1.0 and a['second']['win_pct'] == 0.0
    assert abs(a['first']['shot_share'] - 2 / 3) < 1e-9 and abs(a['full']['shot_share'] - 0.5) < 1e-9
    assert a['full']['point_pct'] == 0.5


def team(season, name, gf, ga, wins, games=10):
    return dict(season=season, team=name, team_id=hash(name) % 1000, games=82, point_pct=0.5, gf=gf, ga=ga, sf=30.0, sa=30.0,
                playoff_games=games if wins or games else 0, playoff_wins=wins, playoff_losses=0)


def test_prepare_cup_scores_ranks_and_picks_one_champion():
    rows = [team(1990, 'Scorers', 4.0, 3.0, 16), team(1990, 'Stoppers', 3.0, 2.0, 12), team(1990, 'Middle', 3.0, 3.0, 4), team(1990, 'Bad', 2.0, 4.0, 0, games=0)]
    T = {t['team']: t for t in A.prepare_cup(rows)}
    assert T['Scorers']['champion'] and not T['Stoppers']['champion']
    assert T['Scorers']['offence_rank'] == 1 and T['Stoppers']['defence_rank'] == 1 and T['Bad']['defence_rank'] == 4
    assert T['Stoppers']['defence'] > 0 > T['Bad']['defence']           # fewer goals against is a higher defence score
    assert not T['Bad']['made_playoffs']
    assert A.style(T['Scorers']) == 'offence' and A.style(T['Stoppers']) == 'defence' and A.style(T['Middle']) == 'balanced'


def test_prepare_cup_skips_seasons_without_playoffs_and_ties_for_most_wins():
    rows = [team(2004, 'A', 3, 2, 0, games=0), team(2004, 'B', 2, 3, 0, games=0), team(1995, 'C', 3, 2, 10), team(1995, 'D', 2, 3, 10)]
    T = A.prepare_cup(rows)
    assert {t['season'] for t in T} == {1995}
    assert not any(t['champion'] for t in T)


def test_pipeline_game_row_splits_shots_by_score():
    def P(n, t, kind, team=None, per=1, pt='REG'):
        d = {'sortOrder': n, 'timeInPeriod': t, 'periodDescriptor': {'number': per, 'periodType': pt}, 'typeDescKey': kind}
        if team:
            d['details'] = {'eventOwnerTeamId': team}
        return d
    plays = ([P(2 + i, '01:00', 'shot-on-goal', 1) for i in range(12)] + [P(20, '05:00', 'goal', 2)] + [P(21 + i, '06:00', 'shot-on-goal', 1) for i in range(10)]
             + [P(40, '10:00', 'goal', 1, 2), P(41, '19:00', 'shot-on-goal', 2, 3), P(42, '20:00', 'period-end', None, 3), P(43, '02:00', 'goal', 1, 4, 'OT'), P(44, '00:00', 'goal', 2, 5, 'SO')])
    g = {'gameState': 'OFF', 'gameType': 2, 'id': 1, 'gameDate': '2025-01-01', 'homeTeam': {'id': 1, 'abbrev': 'TOR', 'score': 2},
         'awayTeam': {'id': 2, 'abbrev': 'MTL', 'score': 1}, 'plays': plays, 'gameOutcome': {'lastPeriodType': 'OT'}}
    r = S.game_row(g, 2025)
    assert r['home_sog'] == 24 and r['home_sog_tied'] == 13 and r['home_sog_trail'] == 11
    assert r['away_sog'] == 2 and r['away_sog_tied'] == 2 and r['away_sog_lead'] == 0        # the shootout goal is not a shot
    assert r['secs_away_lead'] == 1500 and r['secs_tied'] == 2220 and r['first_goal'] == 'away' and r['winner'] == 'home'


def test_scoreless_first_keeps_only_games_with_no_first_period_goals():
    games = [game(30, 25, 'home'), game(30, 25, 'home', home_goals_p1=1), game(30, 25, 'away', away_goals_p1=2)]
    assert len(A.scoreless_first(games)) == 1
    assert A.outshot_winners(games) == (1, 3)
