"""What is a sacrifice bunt worth, and is Japan right to bunt four times as often as MLB?

Reads the tables in data/ and writes results/results.json, which the page loads. Standard library only:

    python analysis.py
    python -m unittest tests.test_model

Three kinds of evidence are combined:
  1. League totals for MLB and NPB (2005-2026): how often each league bunts.
  2. Every MLB plate appearance from 2015 to 2026 (Statcast): what happened after real bunts,
     compared with what happened when similar hitters swung away in the same situation.
  3. A run-scoring model built from league totals (model.py), needed because NPB publishes no
     play-by-play data. It is checked against the MLB play-by-play before it is applied to Japan.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import model as M

HERE = Path(__file__).parent
DATA = HERE / 'data'
SEED = 7
RECENT = (2024, 2025, 2026)             # seasons used for today's run environment
BATTER_FACTORS = [round(0.40 + 0.05 * i, 2) for i in range(19)]   # 0.40 ... 1.30 of the league-average hitter
BATTER_TYPES = dict(pitcher=0.45, weak=0.88, middle=1.00, strong=1.12)   # how often each reaches base, relative to average
KINDS = ('sacrifice', 'fail', 'lead_out', 'safe', 'double')
SAC_STATES = [(o, b) for o in (0, 1) for b in M.BASES if b != '000']
STATE_NAMES = {'100': 'Runner on first', '010': 'Runner on second', '001': 'Runner on third', '110': 'Runners on first and second',
               '101': 'Runners on first and third', '011': 'Runners on second and third', '111': 'Bases loaded'}


def read(name):
    with open(DATA / name, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def totals(rows, years=None, leagues=None):
    out = defaultdict(int)
    for r in rows:
        if (years is None or int(r['year']) in years) and (leagues is None or r['league'] in leagues):
            for k, v in r.items():
                if k not in ('year', 'league'):
                    out[k] += int(v)
    return dict(out)


def classify(events, outs, after_outs):
    """Turn a bunt's recorded result into one of the five outcomes the model uses."""
    made = after_outs - outs
    if made >= 2 or events in ('double_play', 'grounded_into_double_play', 'sac_bunt_double_play', 'strikeout_double_play'):
        return 'double'
    if events == 'sac_bunt':
        return 'sacrifice'
    if events in ('single', 'double', 'triple', 'field_error', 'fielders_choice', 'catcher_interf'):
        return 'safe'
    if events in ('force_out', 'fielders_choice_out'):
        return 'lead_out'
    return 'fail'


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def trend(mlb, npb):
    out = []
    for y in range(2005, 2027):
        m = totals(mlb, {y})
        c, p = totals(npb, {y}, {'C'}), totals(npb, {y}, {'P'})
        both = totals(npb, {y})
        innings = lambda t: (t['AB'] - t['H'] + t['GDP'] + t['SF'] + t['SH'] + t['CS']) / 3
        out.append(dict(year=y, mlb=round(m['SH'] / m['G'], 3), npb=round(both['SH'] / both['G'], 3),
                        npb_central=round(c['SH'] / c['G'], 3), npb_pacific=round(p['SH'] / p['G'], 3),
                        mlb_total=m['SH'], npb_total=both['SH'],
                        mlb_runs=round(m['R'] / m['G'], 2), npb_runs=round(both['R'] / both['G'], 2),
                        mlb_runs_inning=round(m['R'] / innings(m), 3), npb_runs_inning=round(both['R'] / innings(both), 3)))
    return out


def empirical_re(re_rows):
    """Run expectancy from MLB play-by-play, innings 1 to 8, all seasons pooled."""
    out = {}
    for r in re_rows:
        if r['scope'] == 'innings 1-8' and r['season'] == 'all':
            n = int(r['n'])
            out[(int(r['outs']), r['bases'].zfill(3))] = dict(n=n, runs=int(r['runs']) / n, p_score=int(r['scored']) / n)
    return out


def bunt_evidence(bunts, baseline):
    """Real MLB bunts against real swings in the same situation by the same class of hitter."""
    rng = random.Random(SEED)
    by = defaultdict(list)
    for b in bunts:
        by[(int(b['outs']), b['bases'].zfill(3), b['batter_class'])].append(b)
    swing = defaultdict(lambda: defaultdict(float))
    for r in baseline:
        if r['ghost'] == 'True':
            continue
        k = (int(r['outs']), r['bases'].zfill(3), r['batter_class'])
        for c in ('n', 'runs', 'scored', 'won', 'n_full', 'runs_full'):
            swing[k][c] += float(r[c])
    rows = []
    for (outs, bases, cls), bl in sorted(by.items()):
        bl = [b for b in bl if b['ghost'] != 'True']
        sw = swing[(outs, bases, cls)]
        if len(bl) < 40 or sw['n'] < 200:
            continue
        full = [int(b['runs_rest']) for b in bl if b['walkoff_half'] != 'True']
        scored = sum(int(b['runs_rest']) > 0 for b in bl)
        mean = sum(full) / len(full)
        boots = sorted(sum(rng.choice(full) for _ in full) / len(full) for _ in range(1000))
        sw_runs = sw['runs_full'] / sw['n_full']
        rows.append(dict(outs=outs, bases=bases, batter=cls, bunts=len(bl), swings=int(sw['n']),
                         bunt_runs=round(mean, 3), swing_runs=round(sw_runs, 3), runs_diff=round(mean - sw_runs, 3),
                         runs_diff_ci=[round(boots[25] - sw_runs, 3), round(boots[974] - sw_runs, 3)],
                         bunt_score=round(scored / len(bl), 4), bunt_score_ci=wilson(scored, len(bl)),
                         swing_score=round(sw['scored'] / sw['n'], 4), score_diff=round(scored / len(bl) - sw['scored'] / sw['n'], 4)))
    return rows


def outcome_mix(bunts):
    """How real MLB bunts turned out, by starting state, for pitchers and for everyone else."""
    count = defaultdict(lambda: defaultdict(int))
    for b in bunts:
        who = 'pitcher' if b['batter_class'] == 'pitcher' else 'hitter'
        kind = classify(b['events'], int(b['outs']), int(b['after_outs']))
        for key in ((who, int(b['outs']), b['bases'].zfill(3)), (who, 'all', 'all')):
            count[key][kind] += 1
    out = {}
    for (who, outs, bases), c in count.items():
        n = sum(c.values())
        out[f'{who}|{outs}|{bases}'] = dict(n=n, **{k: round(c[k] / n, 4) for k in KINDS})
    return out


def ghost_runner(bunts, baseline):
    """Extra innings since 2020: automatic runner on second, nobody out, first batter of the half-inning.
    Split by who is batting, because the home team in a tie needs exactly one run to win."""
    groups = dict(visitors=lambda top, diff: top, home_tied=lambda top, diff: (not top) and diff == 0,
                  home_behind=lambda top, diff: (not top) and diff < 0)
    diff_value = {'-2': -2, '-1': -1, '0': 0, '+1': 1, '+2': 2}
    out = {}
    for name, test in list(groups.items()) + [('all', lambda top, diff: True)]:
        b = [x for x in bunts if x['ghost'] == 'True' and test(x['top'] == 'True', int(x['score_diff']))]
        sw = defaultdict(float)
        for r in baseline:
            if r['ghost'] == 'True' and test(r['top'] == 'True', diff_value[r['diff_bucket']]):
                for c in ('n', 'runs', 'scored', 'won'):
                    sw[c] += float(r[c])
        n = len(b)
        if n < 20 or sw['n'] < 50:
            continue
        scored, won = sum(int(x['runs_rest']) > 0 for x in b), sum(x['bat_won'] == 'True' for x in b)
        out[name] = dict(bunts=n, swings=int(sw['n']), bunt_share=round(n / (n + sw['n']), 4),
                         bunt_score=round(scored / n, 4), bunt_score_ci=wilson(scored, n), swing_score=round(sw['scored'] / sw['n'], 4),
                         swing_score_ci=wilson(int(sw['scored']), int(sw['n'])),
                         bunt_runs=round(sum(int(x['runs_rest']) for x in b) / n, 3), swing_runs=round(sw['runs'] / sw['n'], 3),
                         bunt_win=round(won / n, 4), bunt_win_ci=wilson(won, n), swing_win=round(sw['won'] / sw['n'], 4),
                         swing_win_ci=wilson(int(sw['won']), int(sw['n'])))
    return out


def league_model(tot, mix):
    """Everything the page needs to compare bunting and swinging in one league."""
    cal = M.calibrate(tot)
    states = {}
    for outs, bases in SAC_STATES:
        swing = [[round(v, 4) for v in M.batter_then_league(outs, bases, M.scale_batter(cal['rates'], f), cal)] for f in BATTER_FACTORS]
        kinds = {k: [round(v, 4) for v in M.bunt_value(outs, bases, {k: 1.0}, cal)] for k in KINDS}
        states[f'{outs}|{bases}'] = dict(swing=swing, bunt=kinds)
    return dict(rates={k: round(v, 4) for k, v in cal['rates'].items()}, dp=round(cal['dp'], 4), sf=round(cal['sf'], 4),
                model_runs_per_inning=round(cal['model_runs_per_inning'], 4), actual_runs_per_inning=round(cal['actual_runs_per_inning'], 4),
                matrix={f'{o}|{b}': [round(cal['runs'][(o, b)], 3), round(cal['p_score'][(o, b)], 3)] for o, b in M.STATES},
                states=states, _cal=cal)


def decide(league, mix, outs, bases, who, factor):
    """Bunt against swing for one situation, using the real MLB outcome mix for that kind of bunter."""
    cal = league['_cal']
    key = f"{'pitcher' if who == 'pitcher' else 'hitter'}|{outs}|{bases}"
    m = mix.get(key) or mix[f"{'pitcher' if who == 'pitcher' else 'hitter'}|all|all"]
    outcome = {k: m[k] for k in KINDS}
    br, bp = M.bunt_value(outs, bases, outcome, cal)
    sr, sp = M.batter_then_league(outs, bases, M.scale_batter(cal['rates'], factor), cal)
    return dict(bunt_runs=round(br, 3), swing_runs=round(sr, 3), bunt_score=round(bp, 4), swing_score=round(sp, 4),
                runs_diff=round(br - sr, 3), score_diff=round(bp - sp, 4))


def breakeven_factor(league, mix, outs, bases, goal):
    """The weakest hitter for whom swinging is still at least as good as bunting (as a share of league average)."""
    idx = 0 if goal == 'runs' else 1
    lo, hi = 0.05, 1.6
    for _ in range(40):
        mid = (lo + hi) / 2
        d = decide(league, mix, outs, bases, 'hitter', mid)
        if (d['bunt_runs'], d['bunt_score'])[idx] > (d['swing_runs'], d['swing_score'])[idx]:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def main():
    mlb, npb = read('raw/mlb_league_batting.csv'), read('raw/npb_league_batting.csv')
    bunts, baseline, seasons = read('bunts.csv'), read('baseline.csv'), read('seasons.csv')
    emp = empirical_re(read('re_matrix.csv'))
    mix = outcome_mix(bunts)

    # check the model against MLB play-by-play before trusting it for Japan
    check_tot = totals(mlb, set(range(2015, 2027)))
    check = M.calibrate(check_tot)
    fit = [dict(outs=o, bases=b, n=emp[(o, b)]['n'], actual_runs=round(emp[(o, b)]['runs'], 3), model_runs=round(check['runs'][(o, b)], 3),
                actual_score=round(emp[(o, b)]['p_score'], 3), model_score=round(check['p_score'][(o, b)], 3)) for o, b in M.STATES]
    w = sum(f['n'] for f in fit)
    fit_summary = dict(
        mean_abs_runs=round(sum(abs(f['actual_runs'] - f['model_runs']) * f['n'] for f in fit) / w, 3),
        mean_abs_score=round(sum(abs(f['actual_score'] - f['model_score']) * f['n'] for f in fit) / w, 3),
        max_abs_runs=round(max(abs(f['actual_runs'] - f['model_runs']) for f in fit), 3),
        max_abs_score=round(max(abs(f['actual_score'] - f['model_score']) for f in fit), 3))

    leagues = dict(MLB=league_model(totals(mlb, set(RECENT)), mix), NPB=league_model(totals(npb, set(RECENT)), mix),
                   NPB_2011=league_model(totals(npb, {2011, 2012}), mix))
    key_states = [(0, '100'), (0, '010'), (0, '110'), (1, '100'), (1, '010')]
    verdicts = {}
    for name, lg in leagues.items():
        verdicts[name] = dict(
            cases=[dict(outs=o, bases=b, who=who, **decide(lg, mix, o, b, who, f)) for o, b in key_states for who, f in BATTER_TYPES.items()],
            breakeven={f'{o}|{b}': dict(runs=breakeven_factor(lg, mix, o, b, 'runs'), score=breakeven_factor(lg, mix, o, b, 'score')) for o, b in key_states})

    # a rough price for Japan's extra bunting: sacrifices by non-pitchers, valued at the average hitter's cost with a runner on first
    npb_recent = totals(npb, set(RECENT))
    cost = -decide(leagues['NPB'], mix, 0, '100', 'middle', 1.0)['runs_diff']
    per_team = npb_recent['SH'] / (12 * len(RECENT))

    tr = trend(mlb, npb)
    last = tr[-1]
    for lg in leagues.values():
        del lg['_cal']
    results = dict(
        trend=tr, seasons=[{k: int(v) for k, v in s.items()} for s in seasons],
        headline=dict(year=last['year'], mlb_per_game=last['mlb'], npb_per_game=last['npb'], ratio=round(last['npb'] / last['mlb'], 1),
                      npb_peak=max(tr, key=lambda t: t['npb']), mlb_low=min(tr, key=lambda t: t['mlb']),
                      plate_appearances=sum(int(s['pa']) for s in seasons), bunts=len(bunts)),
        fit=fit, fit_summary=fit_summary, outcome_mix=mix, evidence=bunt_evidence(bunts, baseline), ghost=ghost_runner(bunts, baseline),
        leagues=leagues, verdicts=verdicts, batter_factors=BATTER_FACTORS, batter_types=BATTER_TYPES, kinds=KINDS,
        state_names=STATE_NAMES, recent=list(RECENT),
        npb_cost=dict(sacrifices_per_team=round(per_team, 1), runs_per_sacrifice=round(cost, 3), runs_per_team=round(per_team * cost, 1)))
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(results, separators=(',', ':')) + '\n')
    return results


if __name__ == '__main__':
    r = main()
    print('headline', {k: v for k, v in r['headline'].items() if k not in ('npb_peak', 'mlb_low')})
    print('fit', r['fit_summary'])
    for k in ('hitter|all|all', 'pitcher|all|all', 'hitter|0|100', 'hitter|0|010', 'hitter|0|110'):
        print('mix', k, r['outcome_mix'][k])
    for e in r['evidence']:
        if e['outs'] == 0 and e['bases'] in ('100', '010', '110'):
            print('evidence', e['bases'], e['batter'], e['bunts'], 'runs', e['bunt_runs'], e['swing_runs'], e['runs_diff_ci'], 'score', e['bunt_score'], e['swing_score'], e['bunt_score_ci'])
    for k, v in r['ghost'].items():
        print('ghost', k, v)
    for lg in ('MLB', 'NPB', 'NPB_2011'):
        L = r['leagues'][lg]
        print(lg, 'R/inn model', L['model_runs_per_inning'], 'actual', L['actual_runs_per_inning'])
        for c in r['verdicts'][lg]['cases']:
            if c['outs'] == 0 and c['bases'] in ('100', '010'):
                print('   ', c['bases'], c['who'], 'runs', c['bunt_runs'], c['swing_runs'], 'score', c['bunt_score'], c['swing_score'])
        print('    breakeven', r['verdicts'][lg]['breakeven'])
    print('cost', r['npb_cost'])
