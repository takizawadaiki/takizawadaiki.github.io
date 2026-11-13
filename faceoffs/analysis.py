"""What makes an NHL player good at faceoffs, and what would a faceoff specialist be worth?

Reads the season files in data/ and writes results/results.json, which the page loads.

    pip install numpy scipy
    python analysis.py
    python -m unittest discover tests

Every faceoff is treated as a contest between two players. A player's rating is what is left of his
results after allowing for who he faced, home ice, the zone, the side of the ice relative to his
shooting hand, and whether his team had a man advantage. Ratings are shrunk toward average, so a
player with few draws is not rated on luck.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.optimize import minimize

HERE = Path(__file__).parent
DATA = HERE / 'data'
SEED = 7
MIN_DRAWS = 500            # faceoffs needed before a player is listed or used in the size analysis
PRIOR_SD_GRID = [0.15, 0.20, 0.30, 0.40, 0.50, 0.65, 0.80]   # candidate spreads of true skill, in logits
FEATURES = ['home', 'offensive_zone', 'strong_side', 'man_advantage', 'age', 'age_squared']
PEAK_GUESS = 28            # ages are measured from here, in units of five years
SHOOTING_PCT = None        # filled from the data: goals per shot on goal


# ---------- loading ----------

def load_faceoffs():
    rows = []
    for f in sorted(DATA.glob('faceoffs_*.csv.gz')):
        with gzip.open(f, 'rt', newline='') as fh:
            rows += list(csv.DictReader(fh))
    return rows


def load_bios():
    """Latest height, weight, hand and birth date for each player, and his name."""
    bio = {}
    for f in sorted(DATA.glob('bios_*.csv')):
        with open(f, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r['height'] and r['weight']:
                    bio[int(r['playerId'])] = dict(name=r['skaterFullName'], height=float(r['height']), weight=float(r['weight']),
                                                   shoots=r['shootsCatches'], born=r['birthDate'][:10], position=r['positionCode'])
    names = {}
    for f in sorted(DATA.glob('players_*.csv')):
        with open(f, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                names[int(r['player'])] = (r['name'], r['position'])
    return bio, names


# ---------- features ----------

def zone_and_side(x, y, home_defends, is_home):
    """Where the draw is from one player's point of view.

    Returns (zone, side): zone is 'O', 'D' or 'N'; side is 'L' or 'R' as he faces the goal he attacks,
    or '' on the centre line of the rink."""
    attacks_positive_x = (home_defends == 'left') == is_home
    forward = x if attacks_positive_x else -x
    zone = 'O' if forward > 25 else 'D' if forward < -25 else 'N'
    left = y if attacks_positive_x else -y          # facing +x, a player's left is +y
    side = 'L' if left > 0 else 'R' if left < 0 else ''
    return zone, side


def skater_edge(situation, is_home):
    """+1 if this player's team has more skaters on the ice, -1 if fewer, 0 if even.
    The situation code reads: away goalie, away skaters, home skaters, home goalie."""
    if len(situation) != 4 or not situation.isdigit():
        return 0
    away, home = int(situation[1]), int(situation[2])
    d = (home - away) if is_home else (away - home)
    return (d > 0) - (d < 0)


def player_features(row, is_home, shoots, age=None):
    x, y = float(row['x'] or 0), float(row['y'] or 0)
    zone, side = zone_and_side(x, y, row['home_defends'], is_home)
    strong = 0.0
    if side and shoots in ('L', 'R'):
        strong = 1.0 if side == shoots else -1.0     # a left shot on the left side is on his strong side
    a = 0.0 if age is None else (age - PEAK_GUESS) / 5
    return dict(home=1.0 if is_home else 0.0, offensive_zone=1.0 if zone == 'O' else -1.0 if zone == 'D' else 0.0,
                strong_side=strong, man_advantage=float(skater_edge(row['situation'], is_home)), age=a, age_squared=a * a), zone


def build(rows, bio):
    """Arrays for the model: one line per faceoff, winner minus loser."""
    ids = sorted({int(r['winner']) for r in rows} | {int(r['loser']) for r in rows})
    index = {p: i for i, p in enumerate(ids)}
    n = len(rows)
    w = np.fromiter((index[int(r['winner'])] for r in rows), dtype=np.int32, count=n)
    l = np.fromiter((index[int(r['loser'])] for r in rows), dtype=np.int32, count=n)
    X = np.zeros((n, len(FEATURES)))
    AGE = np.zeros((n, 4))        # age and age squared for the winner, then for the loser
    zones = []
    for i, r in enumerate(rows):
        win_home = r['winner_team'] == r['home_team']
        year = int(r['season'])
        bw, bl = bio.get(int(r['winner']), {}), bio.get(int(r['loser']), {})
        age = lambda b: year + 1 - int(b['born'][:4]) if b.get('born') else None     # age during the second half of the season
        fw, zone = player_features(r, win_home, bw.get('shoots', ''), age(bw))
        fl, _ = player_features(r, not win_home, bl.get('shoots', ''), age(bl))
        X[i] = [fw[k] - fl[k] for k in FEATURES]
        AGE[i] = [fw['age'], fw['age_squared'], fl['age'], fl['age_squared']]
        zones.append(zone)
    return ids, w, l, X, np.array(zones), AGE


# ---------- the model ----------

def fit(w, l, X, n_players, prior_sd, start=None):
    """Penalised logistic regression. Each line says the winner beat the loser, so the model maximises
    the probability of what happened, with a normal prior on player ratings."""
    n, k = X.shape
    rows = np.arange(n)
    D = sparse.csr_matrix((np.r_[np.ones(n), -np.ones(n)], (np.r_[rows, rows], np.r_[w, l])), shape=(n, n_players))
    lam = 1.0 / prior_sd ** 2

    def objective(theta):
        z = D @ theta[:n_players] + X @ theta[n_players:]
        loss = np.logaddexp(0, -z).sum() + 0.5 * lam * (theta[:n_players] ** 2).sum()
        g = -1.0 / (1.0 + np.exp(z))
        grad = np.r_[D.T @ g + lam * theta[:n_players], X.T @ g]
        return loss, grad

    x0 = np.zeros(n_players + k) if start is None else start
    res = minimize(objective, x0, jac=True, method='L-BFGS-B', options=dict(maxiter=500, maxfun=2000))
    return res.x[:n_players], res.x[n_players:]


def log_loss(w, l, X, skill, beta):
    z = skill[w] - skill[l] + X @ beta
    return float(np.logaddexp(0, -z).mean())


def choose_prior(w, l, X, games, n_players):
    """Pick the spread of skill that best predicts faceoffs in games the model did not see."""
    rng = np.random.default_rng(SEED)
    uniq = np.unique(games)
    held = np.isin(games, rng.choice(uniq, size=len(uniq) // 5, replace=False))
    scores = []
    for sd in PRIOR_SD_GRID:
        s, b = fit(w[~held], l[~held], X[~held], n_players, sd)
        scores.append((log_loss(w[held], l[held], X[held], s, b), sd))
    base = math.log(2)
    best = min(scores)
    return best[1], [dict(prior_sd=sd, log_loss=round(v, 5)) for v, sd in scores], round(base, 5)


def to_pct(logit):
    """Win percentage against an average opponent in a neutral situation."""
    return 100.0 / (1.0 + np.exp(-np.asarray(logit)))


# ---------- what is a win worth ----------

def win_value(rows, zones):
    """Shots and goals in the 30 seconds after a draw, for the team that won it, by the winner's zone."""
    out = {}
    tot_goals = sum(int(r['goals_w']) + int(r['goals_l']) for r in rows)
    tot_sog = sum(int(r['sog_w']) + int(r['sog_l']) for r in rows)
    sh = tot_goals / tot_sog
    for z in ('O', 'N', 'D'):
        sel = [r for r, zz in zip(rows, zones) if zz == z]
        n = len(sel)
        gw, gl = sum(int(r['goals_w']) for r in sel), sum(int(r['goals_l']) for r in sel)
        sw, sl = sum(int(r['sog_w']) for r in sel), sum(int(r['sog_l']) for r in sel)
        out[z] = dict(n=n, goals_for=gw / n, goals_against=gl / n, shots_for=sw / n, shots_against=sl / n)
    mirror = {'O': 'D', 'D': 'O', 'N': 'N'}
    res = {}
    for z in ('O', 'N', 'D'):
        a, b = out[z], out[mirror[z]]
        # winning in my zone z against losing there (the opponent wins in his mirror zone)
        shots = (a['shots_for'] - a['shots_against']) + (b['shots_for'] - b['shots_against'])
        goals = (a['goals_for'] - a['goals_against']) + (b['goals_for'] - b['goals_against'])
        res[z] = dict(n=out[z]['n'] + 0, win_shots_for=round(a['shots_for'], 4), win_shots_against=round(a['shots_against'], 4),
                      win_goals_for=round(a['goals_for'], 5), win_goals_against=round(a['goals_against'], 5),
                      shot_swing=round(shots, 4), goal_swing=round(goals, 5), goal_swing_from_shots=round(shots * sh, 5))
    return res, sh


GOALS_PER_WIN = 6.0     # the usual NHL rule of thumb: about six goals of goal difference is worth one win


def specialist_value(win_pct, draws_per_game, end_zone_share, value, games=82):
    """Goals a faceoff man adds over a season against an average one taking the same draws.

    Every draw he wins that an average player would have lost is worth the full swing between
    winning and losing it: the end-zone figure for draws at either end, the neutral-zone figure otherwise.
    """
    extra_wins = games * draws_per_game * (win_pct - 50) / 100
    per_win = end_zone_share * value['O']['goal_swing'] + (1 - end_zone_share) * value['N']['goal_swing']
    goals = extra_wins * per_win
    return dict(extra_wins=round(extra_wins, 1), goals=round(goals, 2), wins=round(goals / GOALS_PER_WIN, 2))


def usage(rows):
    """How many draws the busiest faceoff men take: the 10th busiest player-season in each full season."""
    from collections import Counter
    by = {}
    for r in rows:
        c = by.setdefault(r['season'], Counter())
        c[r['winner']] += 1
        c[r['loser']] += 1
    out = []
    for season, c in sorted(by.items()):
        top = sorted(c.values(), reverse=True)
        out.append(dict(season=int(season), busiest=top[0], tenth=top[9], fiftieth=top[49]))
    return out


# ---------- everything together ----------

def main():
    rows = load_faceoffs()
    bio, names = load_bios()
    ids, w, l, X, zones, AGE = build(rows, bio)
    n_players = len(ids)
    games = np.array([int(r['game']) for r in rows])
    seasons = np.array([int(r['season']) for r in rows])

    prior_sd, prior_scores, base_loss = choose_prior(w, l, X, games, n_players)
    skill, beta = fit(w, l, X, n_players, prior_sd)

    draws = np.bincount(w, minlength=n_players) + np.bincount(l, minlength=n_players)
    wins = np.bincount(w, minlength=n_players)
    # ratings are measured against the average opponent actually faced, weighted by how many draws each player takes
    b_age_pair = np.array([beta[FEATURES.index('age')], beta[FEATURES.index('age_squared')]])
    age_w, age_l = AGE[:, :2] @ b_age_pair, AGE[:, 2:] @ b_age_pair          # each player's age effect on each draw
    centre = float((skill[w].sum() + skill[l].sum() + age_w.sum() + age_l.sum()) / (2 * len(w)))
    # a player's average age effect over the draws he took: his rating "as played" is talent plus this
    age_avg = (np.bincount(w, weights=age_w, minlength=n_players) + np.bincount(l, weights=age_l, minlength=n_players)) / np.maximum(draws, 1)
    raw = 100 * wins / np.maximum(draws, 1)

    # is it a real skill? fit odd and even games separately and compare the two sets of ratings
    odd = games % 2 == 1
    s_odd, _ = fit(w[odd], l[odd], X[odd], n_players, prior_sd)
    s_even, _ = fit(w[~odd], l[~odd], X[~odd], n_players, prior_sd)
    regular = draws >= MIN_DRAWS
    split_half = float(np.corrcoef(s_odd[regular], s_even[regular])[0, 1])

    # year to year: ratings fitted on one season against the next
    yy = []
    for y in sorted(set(seasons))[:-1]:
        a, b = seasons == y, seasons == y + 1
        sa, _ = fit(w[a], l[a], X[a], n_players, prior_sd)
        sb, _ = fit(w[b], l[b], X[b], n_players, prior_sd)
        da = np.bincount(w[a], minlength=n_players) + np.bincount(l[a], minlength=n_players)
        db = np.bincount(w[b], minlength=n_players) + np.bincount(l[b], minlength=n_players)
        both = (da >= 300) & (db >= 300)
        if both.sum() >= 30:
            yy.append(dict(season=int(y), n=int(both.sum()), r=round(float(np.corrcoef(sa[both], sb[both])[0, 1]), 3)))

    regular_all = draws >= MIN_DRAWS
    # the players
    last_year = int(seasons.max())
    last_draws = np.bincount(w[seasons == last_year], minlength=n_players) + np.bincount(l[seasons == last_year], minlength=n_players)
    players = []
    for i, pid in enumerate(ids):
        if draws[i] < MIN_DRAWS or pid not in bio:
            continue
        b = bio[pid]
        age = last_year + 1 - int(b['born'][:4]) if b['born'] else None
        players.append(dict(id=pid, name=b['name'], height=b['height'], weight=b['weight'], shoots=b['shoots'], position=b['position'],
                            draws=int(draws[i]), raw=round(float(raw[i]), 2), rating=round(float(to_pct(skill[i] + age_avg[i] - centre)), 2),
                            talent=round(float(to_pct(skill[i] - float(np.average(skill[regular_all], weights=draws[regular_all])))), 2),
                            skill=float(skill[i]), birth_year=int(b['born'][:4]) if b['born'] else None,
                            recent_draws=int(last_draws[i])))
    players.sort(key=lambda p: -p['rating'])

    # what explains the ratings? ordinary regression of rating on size and hand, weighted by draws
    P = [p for p in players if p['shoots'] in ('L', 'R')]
    y = np.array([p['talent'] for p in P])       # age-adjusted, so that older (and heavier) players do not blur the picture
    wt = np.sqrt(np.array([p['draws'] for p in P], dtype=float))
    h = np.array([p['height'] for p in P]); wgt = np.array([p['weight'] for p in P]); right = np.array([p['shoots'] == 'R' for p in P], dtype=float)
    is_centre = np.array([p['position'] == 'C' for p in P])
    def ols(cols, names, keep=None):
        A = np.column_stack([np.ones(len(P))] + cols)
        if keep is not None:
            return ols_on(A[keep], y[keep], wt[keep], names)
        return ols_on(A, y, wt, names)
    def ols_on(A, y, wt, names):
        coef, *_ = np.linalg.lstsq(A * wt[:, None], y * wt, rcond=None)
        pred = A @ coef
        ybar = np.average(y, weights=wt ** 2)
        r2 = 1 - np.sum(wt ** 2 * (y - pred) ** 2) / np.sum(wt ** 2 * (y - ybar) ** 2)
        resid = y - pred
        dof = len(y) - A.shape[1]
        s2 = np.sum(wt ** 2 * resid ** 2) / dof
        cov = s2 * np.linalg.inv((A * wt[:, None]).T @ (A * wt[:, None]))
        return dict(r2=round(float(r2), 4), terms=[dict(name=n, coef=round(float(c), 4), se=round(float(math.sqrt(v)), 4))
                                                    for n, c, v in zip(['intercept'] + names, coef, np.diag(cov))])
    size_models = dict(
        height=ols([h - h.mean()], ['height_inch']),
        weight=ols([(wgt - wgt.mean()) / 10], ['weight_10lb']),
        all=ols([h - h.mean(), (wgt - wgt.mean()) / 10, right], ['height_inch', 'weight_10lb', 'right_shot']),
        centres=ols([h - h.mean(), (wgt - wgt.mean()) / 10], ['height_inch', 'weight_10lb'], keep=is_centre),
        centres_weight=ols([(wgt - wgt.mean()) / 10], ['weight_10lb'], keep=is_centre),
        means=dict(height=round(float(h.mean()), 2), weight=round(float(wgt.mean()), 1), n=len(P), centres=int(is_centre.sum())))
    r_height = float(np.corrcoef(h, y)[0, 1]); r_weight = float(np.corrcoef(wgt, y)[0, 1])

    # size groups
    def group(lo, hi):
        sel = [p for p in P if lo <= p['height'] < hi]
        if not sel:
            return None
        d = np.array([p['draws'] for p in sel], dtype=float)
        r = np.array([p['rating'] for p in sel])
        best = max(sel, key=lambda p: p['rating'])
        return dict(n=len(sel), mean=round(float(np.average(r, weights=d)), 2), best=best['name'], best_rating=best['rating'],
                    best_height=best['height'], best_weight=best['weight'], share_above_52=round(float(np.mean(r >= 52)), 3))
    height_groups = [dict(label=lab, **g) for lab, lo, hi in (('5\'9" and under', 0, 70), ('5\'10" to 5\'11"', 70, 72), ('6\'0" to 6\'1"', 72, 74),
                                                             ('6\'2" to 6\'3"', 74, 76), ('6\'4" and over', 76, 99)) if (g := group(lo, hi))]

    # how much of the spread in ratings size leaves unexplained
    A_all = np.column_stack([np.ones(len(P)), h - h.mean(), (wgt - wgt.mean()) / 10, right])
    coef_all, *_ = np.linalg.lstsq(A_all * wt[:, None], y * wt, rcond=None)
    resid = y - A_all @ coef_all
    for p, e, pr in zip(P, resid, A_all @ coef_all):
        p['expected_from_size'] = round(float(pr), 2)
        p['beyond_size'] = round(float(e), 2)

    # the age curve implied by the model, relative to the best age
    b_age, b_age2 = float(b_age_pair[0]), float(b_age_pair[1])
    ages = list(range(19, 41))
    curve = [b_age * (a - PEAK_GUESS) / 5 + b_age2 * ((a - PEAK_GUESS) / 5) ** 2 for a in ages]
    top = max(curve)
    age_curve = [dict(age=a, pct=round(float(to_pct(c - top) - 50), 2)) for a, c in zip(ages, curve)]
    peak_age = ages[int(np.argmax(curve))]

    value, shooting_pct = win_value(rows, zones)
    zone_share = {z: round(float(np.mean(zones == z)), 4) for z in ('O', 'N', 'D')}

    spread = float(np.std([p['rating'] for p in players]))
    pct_per_logit = 25.0      # near 50%, one logit is about 25 percentage points
    def wgroup(lo, hi, label):
        sel = [p for p in P if lo <= p['weight'] < hi]
        d = np.array([p['draws'] for p in sel], float)
        t = np.array([p['talent'] for p in sel])
        return dict(label=label, n=len(sel), mean=round(float(np.average(t, weights=d)), 2), share_above_52=round(float(np.mean(t >= 52)), 3))
    weight_groups = [wgroup(0, 185, 'Under 185 lb'), wgroup(185, 195, '185 to 194 lb'), wgroup(195, 205, '195 to 204 lb'),
                     wgroup(205, 215, '205 to 214 lb'), wgroup(215, 999, '215 lb and over')]
    use = usage(rows)
    examples = dict(
        elite_specialist=specialist_value(58, 10, 0.8, value),
        top_centre=specialist_value(57, 20, 0.69, value),
        goals_per_win=GOALS_PER_WIN)
    results = dict(
        summary=dict(faceoffs=len(rows), games=int(len(np.unique(games))), seasons=[int(seasons.min()), int(seasons.max())],
                     players=int(n_players), rated_players=len(players), min_draws=MIN_DRAWS, prior_sd=prior_sd,
                     rating_sd=round(spread, 2), split_half=round(split_half, 3), year_to_year=yy,
                     shooting_pct=round(shooting_pct, 4), prior_scores=prior_scores, coin_flip_loss=base_loss),
        effects={k: dict(logit=round(float(b), 4), pct=round(float(to_pct(b) - 50), 2)) for k, b in zip(FEATURES, beta)},
        size=dict(models=size_models, r_height=round(r_height, 3), r_weight=round(r_weight, 3), height_groups=height_groups),
        value=value, zone_share=zone_share, usage=use, examples=examples, weight_groups=weight_groups,
        talent_sd=round(float(np.std([p['talent'] for p in P])), 2), age_curve=age_curve, peak_age=peak_age,
        size_residual_sd=round(float(np.std(resid)), 2),
        players=[{k: v for k, v in p.items() if k != 'skill'} for p in players],
    )
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(results, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    return results


if __name__ == '__main__':
    r = main()
    s = r['summary']
    print({k: v for k, v in s.items() if k not in ('prior_scores', 'year_to_year')})
    print('prior', s['prior_scores'], 'coin flip', s['coin_flip_loss'])
    print('year to year', s['year_to_year'])
    print('effects', r['effects'])
    print('age', r['peak_age'], [(a['age'], a['pct']) for a in r['age_curve'][::3]], 'resid sd', r['size_residual_sd'])
    sz = r['size']
    print('size', sz['models']['height'], sz['models']['weight'], sz['models']['all'], sz['r_height'], sz['r_weight'])
    for g in sz['height_groups']:
        print('   ', g)
    print('value', r['value'], r['zone_share'])
    for p in r['players'][:15]:
        print(p['name'], p['height'], p['weight'], p['shoots'], p['draws'], p['raw'], p['rating'], p['talent'])
    print('...shortest rated:')
    for p in sorted(r['players'], key=lambda p: p['height'])[:12]:
        print(p['name'], p['height'], p['weight'], p['draws'], p['raw'], p['rating'])
