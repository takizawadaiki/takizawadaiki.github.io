"""Two NHL questions: do shots on goal win games, and do offences or defences win the Stanley Cup?

    python analysis.py            # reads data/, writes results/results.json

Part one uses one row per regular-season game (shots by period and by the score when they were taken).
Part two uses one row per team season (goals for and against, and playoff wins).
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIRST_CUP_SEASON = 1979          # 1979-80: the first season with 16 playoff teams
CAP_SEASON = 2005                # 2005-06: the first season under the salary cap
MARGIN_BUCKETS = [(1, 3), (4, 7), (8, 12), (13, 19), (20, 99)]


# ---------- loading ----------

def load_games(folder=None):
    folder = folder or HERE / 'data'
    rows = []
    for path in sorted(Path(folder).glob('games_*.csv')):
        with open(path, newline='') as f:
            for r in csv.DictReader(f):
                rows.append({k: (int(v) if v.lstrip('-').isdigit() else v) for k, v in r.items()})
    return rows


def load_team_seasons(path=None):
    path = path or HERE / 'data' / 'team_seasons.csv'
    out = []
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            num = lambda k: float(r[k]) if r.get(k) not in (None, '') else None
            out.append(dict(season=int(r['season']), team=r['team'], team_id=int(r['team_id']), games=int(r['gamesPlayed']),
                            point_pct=num('pointPct'), gf=num('goalsForPerGame'), ga=num('goalsAgainstPerGame'),
                            sf=num('shotsForPerGame'), sa=num('shotsAgainstPerGame'),
                            playoff_games=int(r['playoff_games']), playoff_wins=int(r['playoff_wins']), playoff_losses=int(r['playoff_losses'])))
    return out


# ---------- small tools ----------

def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(np.corrcoef(x, y)[0, 1])


def logistic(X, y, steps=60):
    """Plain logistic regression by Newton's method. X has no intercept column; one is added.
    Returns coefficients (intercept first) and their standard errors."""
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    y = np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(steps):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = 1 / (1 + np.exp(-X @ b))
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]) + 1e-9 * np.eye(X.shape[1]))
    return b, np.sqrt(np.diag(cov))


def ols(X, y):
    """Least squares with an intercept. Returns coefficients, standard errors and R squared."""
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    y = np.asarray(y, float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    dof = max(1, len(y) - X.shape[1])
    cov = resid @ resid / dof * np.linalg.inv(X.T @ X)
    r2 = 1 - resid @ resid / np.sum((y - y.mean()) ** 2)
    return b, np.sqrt(np.diag(cov)), float(r2)


def zscores(values):
    v = np.asarray(values, float)
    sd = v.std()
    return (v - v.mean()) / sd if sd > 0 else np.zeros(len(v))


# ---------- part one: shots and wins ----------

def outshooting(games, key='sog'):
    """How often the team with more shots (of the kind named by key) wins, overall and by the size of the gap."""
    wins = n = even = 0
    buckets = {b: [0, 0] for b in MARGIN_BUCKETS}
    for g in games:
        d = g[f'home_{key}'] - g[f'away_{key}']
        if d == 0:
            even += 1
            continue
        won = (g['winner'] == 'home') == (d > 0)
        n += 1
        wins += won
        for lo, hi in MARGIN_BUCKETS:
            if lo <= abs(d) <= hi:
                buckets[(lo, hi)][0] += won
                buckets[(lo, hi)][1] += 1
    return dict(games=n, even=even, win_pct=wins / n if n else None,
                by_margin=[dict(low=lo, high=hi, games=c[1], win_pct=c[0] / c[1] if c[1] else None) for (lo, hi), c in buckets.items()])


def scoreless_first(games):
    """Games that were 0-0 after one period. Every first-period shot was taken with the score tied and none went in,
    so the shot count cannot have been shaped by the score or by the goals that decided the game."""
    return [g for g in games if g['home_goals_p1'] == 0 and g['away_goals_p1'] == 0]


def score_effects(games):
    """Shots on goal per 60 minutes by a team that is tied, leading or trailing."""
    shots = dict(tied=0, lead=0, trail=0)
    secs = dict(tied=0, lead=0, trail=0)
    for g in games:
        shots['tied'] += g['home_sog_tied'] + g['away_sog_tied']
        secs['tied'] += 2 * g['secs_tied']                     # both teams are tied at once
        shots['lead'] += g['home_sog_lead'] + g['away_sog_lead']
        shots['trail'] += g['home_sog_trail'] + g['away_sog_trail']
        secs['lead'] += g['secs_home_lead'] + g['secs_away_lead']
        secs['trail'] += g['secs_home_lead'] + g['secs_away_lead']
    return {k: dict(shots=shots[k], hours=secs[k] / 3600, per60=shots[k] / secs[k] * 3600 if secs[k] else None) for k in shots}


def outshot_winners(games):
    """Games the winner was outshot in, and all games with unequal shots."""
    uneven = [g for g in games if g['home_sog'] != g['away_sog']]
    return sum((g['home_sog'] < g['away_sog']) == (g['winner'] == 'home') for g in uneven), len(uneven)


def win_curve(games, key='sog'):
    """Logistic fit of the home team winning on its shot margin. Returns the fit and a function for any margin."""
    d = np.array([g[f'home_{key}'] - g[f'away_{key}'] for g in games], float)
    y = np.array([g['winner'] == 'home' for g in games], float)
    b, se = logistic(d[:, None], y)
    return dict(intercept=float(b[0]), slope=float(b[1]), slope_se=float(se[1]), home_win_pct=float(y.mean()))


def team_seasons_from_games(games):
    """Each team's season, and its first and second halves, built from the game rows."""
    by = defaultdict(list)
    for g in sorted(games, key=lambda g: (g['season'], g['date'], g['game'])):
        for me, other in (('home', 'away'), ('away', 'home')):
            won = g['winner'] == me
            by[(g['season'], g[me])].append(dict(
                win=1.0 if won else 0.0, points=2 if won else (1 if g['decided_in'] != 'REG' else 0),
                gf=g[f'{me}_goals'], ga=g[f'{other}_goals'], sf=g[f'{me}_sog'], sa=g[f'{other}_sog'],
                tsf=g[f'{me}_sog_tied'], tsa=g[f'{other}_sog_tied']))
    def summarise(rows):
        t = {k: sum(r[k] for r in rows) for k in rows[0]}
        n = len(rows)
        return dict(games=n, win_pct=t['win'] / n, point_pct=t['points'] / (2 * n),
                    goal_share=t['gf'] / max(1, t['gf'] + t['ga']), shot_share=t['sf'] / (t['sf'] + t['sa']),
                    tied_shot_share=t['tsf'] / max(1, t['tsf'] + t['tsa']),
                    shooting_pct=t['gf'] / t['sf'], save_pct=1 - t['ga'] / t['sa'],
                    shots_for=t['sf'] / n, shots_against=t['sa'] / n)
    out = []
    for (season, team), rows in by.items():
        if len(rows) < 40:
            continue
        half = len(rows) // 2
        out.append(dict(season=season, team=team, full=summarise(rows), first=summarise(rows[:half]), second=summarise(rows[half:])))
    return out


def persistence(teams):
    """Which first-half number best predicts a team's second-half points percentage?"""
    target = [t['second']['point_pct'] for t in teams]
    out = {}
    for k in ('point_pct', 'goal_share', 'shot_share', 'tied_shot_share', 'shooting_pct', 'save_pct'):
        out[k] = dict(predicts_second_half_points=corr([t['first'][k] for t in teams], target),
                      repeats_itself=corr([t['first'][k] for t in teams], [t['second'][k] for t in teams]))
    return out


def shots_part(games):
    teams = team_seasons_from_games(games)
    full = lambda k: [t['full'][k] for t in teams]
    b, se, r2_shots = ols(np.array(full('shot_share'))[:, None], full('point_pct'))
    _, _, r2_pct = ols(np.column_stack([full('shooting_pct'), full('save_pct')]), full('point_pct'))
    _, _, r2_all = ols(np.column_stack([full('shot_share'), full('shooting_pct'), full('save_pct')]), full('point_pct'))
    seasons = sorted({g['season'] for g in games})
    reg = [g for g in games if g['decided_in'] == 'REG']
    clean = scoreless_first(games)
    first_goal = [g for g in games if g['first_goal'] in ('home', 'away')]
    lead2 = [(g, 'home' if g['home_goals_p1'] + g['home_goals_p2'] > g['away_goals_p1'] + g['away_goals_p2'] else 'away')
             for g in games if g['home_goals_p1'] + g['home_goals_p2'] != g['away_goals_p1'] + g['away_goals_p2']]
    return dict(
        games=len(games), seasons=[seasons[0], seasons[-1]],
        shots_per_team_game=sum(g['home_sog'] + g['away_sog'] for g in games) / (2 * len(games)),
        all_shots=outshooting(games, 'sog'), tied_shots=outshooting(games, 'sog_tied'), first_period=outshooting(games, 'sog_p1'),
        regulation_only=outshooting(reg, 'sog'),
        scoreless_first=outshooting(clean, 'sog_p1'), curve_scoreless=win_curve(clean, 'sog_p1'), scoreless_games=len(clean),
        outshot_and_won=dict(zip(('wins', 'games'), outshot_winners(games))),
        by_season=[dict(season=s, **{k: v for k, v in outshooting([g for g in games if g['season'] == s]).items() if k != 'by_margin'}) for s in seasons],
        score_effects=score_effects(games),
        curve_all=win_curve(games, 'sog'), curve_tied=win_curve(games, 'sog_tied'), curve_first=win_curve(games, 'sog_p1'),
        first_goal_win_pct=sum(g['winner'] == g['first_goal'] for g in first_goal) / len(first_goal),
        lead_after_two_win_pct=sum(g['winner'] == who for g, who in lead2) / len(lead2),
        team_seasons=len(teams),
        season_level=dict(
            shot_share_vs_points=corr(full('shot_share'), full('point_pct')),
            tied_shot_share_vs_points=corr(full('tied_shot_share'), full('point_pct')),
            goal_share_vs_points=corr(full('goal_share'), full('point_pct')),
            points_line=dict(intercept=float(b[0]), slope=float(b[1]), slope_se=float(se[1]),
                             residual_sd=float(np.std(np.array(full('point_pct')) - (b[0] + b[1] * np.array(full('shot_share')))))),
            points_per_shot_share_point=float(b[1]) / 100 * 164,      # standings points over 82 games for one point of shot share
            r2_shot_share=r2_shots, r2_shooting_and_saves=r2_pct, r2_all_three=r2_all),
        persistence=persistence(teams),
        teams=[dict(season=t['season'], team=t['team'], **{k: round(v, 4) for k, v in t['full'].items()}) for t in teams],
    )


# ---------- part two: offence or defence ----------

def prepare_cup(rows, first=FIRST_CUP_SEASON):
    """Add offence and defence scores (standard deviations better than the league that season), ranks and the champion flag."""
    out = []
    for season in sorted({r['season'] for r in rows if r['season'] >= first}):
        league = [r for r in rows if r['season'] == season and r['gf'] is not None and r['ga'] is not None]
        if not league or max(r['playoff_wins'] for r in league) == 0:
            continue                                            # a season with no playoffs
        off, deff = zscores([r['gf'] for r in league]), -zscores([r['ga'] for r in league])
        shot = None
        if all(r['sf'] and r['sa'] for r in league):
            shot = zscores([r['sf'] / (r['sf'] + r['sa']) for r in league])
        best = max(r['playoff_wins'] for r in league)
        top = [r for r in league if r['playoff_wins'] == best]
        for i, r in enumerate(league):
            out.append(dict(r, offence=float(off[i]), defence=float(deff[i]),
                            offence_rank=int(sum(o > off[i] for o in off)) + 1, defence_rank=int(sum(d > deff[i] for d in deff)) + 1,
                            shot_share=float(shot[i]) if shot is not None else None,
                            teams=len(league), made_playoffs=r['playoff_games'] > 0,
                            champion=len(top) == 1 and r is top[0]))
    return out


def style(t, gap=0.5):
    d = t['offence'] - t['defence']
    return 'offence' if d > gap else 'defence' if d < -gap else 'balanced'


def cup_part(rows):
    T = prepare_cup(rows)
    playoff = [t for t in T if t['made_playoffs']]
    champs = [t for t in T if t['champion']]
    def block(sel_playoff, sel_champs):
        if len(sel_champs) < 5:
            return None
        X = np.array([[t['offence'], t['defence']] for t in sel_playoff])
        b, se = logistic(X, [t['champion'] for t in sel_playoff])
        bw, sew, r2 = ols(X, [t['playoff_wins'] for t in sel_playoff])
        styles = {}
        for s in ('offence', 'balanced', 'defence'):
            grp = [t for t in sel_playoff if style(t) == s]
            styles[s] = dict(playoff_teams=len(grp), champions=sum(t['champion'] for t in grp),
                             cup_rate=sum(t['champion'] for t in grp) / len(grp) if grp else None,
                             playoff_wins=float(np.mean([t['playoff_wins'] for t in grp])) if grp else None)
        n = len(sel_champs)
        return dict(
            champions=n, playoff_teams=len(sel_playoff),
            champion_offence=float(np.mean([t['offence'] for t in sel_champs])), champion_defence=float(np.mean([t['defence'] for t in sel_champs])),
            champion_offence_rank=float(np.mean([t['offence_rank'] for t in sel_champs])), champion_defence_rank=float(np.mean([t['defence_rank'] for t in sel_champs])),
            top5_offence=sum(t['offence_rank'] <= 5 for t in sel_champs), top5_defence=sum(t['defence_rank'] <= 5 for t in sel_champs),
            top5_both=sum(t['offence_rank'] <= 5 and t['defence_rank'] <= 5 for t in sel_champs),
            top5_neither=sum(t['offence_rank'] > 5 and t['defence_rank'] > 5 for t in sel_champs),
            better_offence=sum(t['offence'] > t['defence'] for t in sel_champs), better_defence=sum(t['defence'] > t['offence'] for t in sel_champs),
            cup_odds=dict(offence=float(b[1]), offence_se=float(se[1]), defence=float(b[2]), defence_se=float(se[2])),
            playoff_wins=dict(offence=float(bw[1]), offence_se=float(sew[1]), defence=float(bw[2]), defence_se=float(sew[2]), r2=r2),
            styles=styles)
    eras = dict(all=(FIRST_CUP_SEASON, 9999), before_cap=(FIRST_CUP_SEASON, CAP_SEASON - 1), cap=(CAP_SEASON, 9999))
    blocks = {name: block([t for t in playoff if lo <= t['season'] <= hi], [t for t in champs if lo <= t['season'] <= hi]) for name, (lo, hi) in eras.items()}
    # the regular season, for comparison: what a standard deviation of each is worth in points percentage
    reg = [t for t in T if t['point_pct'] is not None]
    br, ser, r2r = ols(np.array([[t['offence'], t['defence']] for t in reg]), [t['point_pct'] for t in reg])
    # the model's Cup chance for any pair of scores, as a share of the average playoff team's chance
    b_all, _ = logistic(np.array([[t['offence'], t['defence']] for t in playoff]), [t['champion'] for t in playoff])
    keep = ('season', 'team', 'offence', 'defence', 'offence_rank', 'defence_rank', 'teams', 'gf', 'ga', 'point_pct', 'playoff_wins', 'champion', 'shot_share')
    seasons = sorted({t['season'] for t in T})
    return dict(
        seasons=[seasons[0], seasons[-1]], season_count=len(seasons), eras=blocks,
        regular_season=dict(offence=float(br[1]), defence=float(br[2]), offence_se=float(ser[1]), defence_se=float(ser[2]), r2=r2r),
        cup_model=dict(intercept=float(b_all[0]), offence=float(b_all[1]), defence=float(b_all[2])),
        champions=[dict({k: (round(t[k], 3) if isinstance(t[k], float) else t[k]) for k in keep}, style=style(t)) for t in champs],
        playoff_teams=[dict(season=t['season'], team=t['team'], offence=round(t['offence'], 2), defence=round(t['defence'], 2),
                            wins=t['playoff_wins'], champion=t['champion']) for t in playoff],
    )


def main():
    games, seasons = load_games(), load_team_seasons()
    results = dict(shots=shots_part(games), cup=cup_part(seasons))
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (float, np.floating)):
            return None if math.isnan(o) else round(float(o), 5)
        if isinstance(o, (np.integer, np.bool_)):
            return o.item()
        return o
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(clean(results), separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    S, C = results['shots'], results['cup']
    print({k: v for k, v in S.items() if k not in ('teams', 'by_season')})
    print(S['by_season'])
    print({k: v for k, v in C.items() if k not in ('champions', 'playoff_teams')})
    for c in C['champions']:
        print(c['season'], c['team'], c['offence_rank'], c['defence_rank'], c['style'], c['playoff_wins'])


if __name__ == '__main__':
    main()
