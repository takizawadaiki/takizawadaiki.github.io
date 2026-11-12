"""Should MLB have a salary cap? The numbers behind the page.

Reads the raw files in data/raw, writes tidy CSVs to data/ and every figure the page shows to
results/results.json. Standard library only, so it runs anywhere:

    python analysis.py
    python -m unittest discover tests

Sources and retrieval dates are in data/SOURCES.md.
"""
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / 'data' / 'raw'
SEED = 7
BOOT = 2000

# The league's offer of 4 November 2026 (Associated Press), for a system starting in 2028.
PROPOSAL = dict(cap=258.2, floor=180.2, reported_cut=528, reported_add=636,
                reported_over=['BOS', 'CHC', 'LAD', 'NYM', 'NYY', 'PHI', 'SD', 'TOR'],
                reported_under=['ATH', 'CWS', 'CIN', 'CLE', 'COL', 'MIA', 'MIL', 'MIN', 'PIT', 'STL', 'TB', 'WSH'])

SLUG_TO_ABBR = {
    'baltimore-orioles': 'BAL', 'boston-red-sox': 'BOS', 'new-york-yankees': 'NYY', 'tampa-bay-rays': 'TB',
    'toronto-blue-jays': 'TOR', 'chicago-white-sox': 'CWS', 'cleveland-guardians': 'CLE', 'detroit-tigers': 'DET',
    'kansas-city-royals': 'KC', 'minnesota-twins': 'MIN', 'athletics': 'ATH', 'houston-astros': 'HOU',
    'los-angeles-angels': 'LAA', 'seattle-mariners': 'SEA', 'texas-rangers': 'TEX', 'atlanta-braves': 'ATL',
    'miami-marlins': 'MIA', 'new-york-mets': 'NYM', 'philadelphia-phillies': 'PHI', 'washington-nationals': 'WSH',
    'chicago-cubs': 'CHC', 'cincinnati-reds': 'CIN', 'milwaukee-brewers': 'MIL', 'pittsburgh-pirates': 'PIT',
    'st-louis-cardinals': 'STL', 'arizona-diamondbacks': 'AZ', 'colorado-rockies': 'COL',
    'los-angeles-dodgers': 'LAD', 'san-diego-padres': 'SD', 'san-francisco-giants': 'SF',
}
TEAM_NAMES = {v: ' '.join(w.capitalize() for w in k.split('-')).replace('St Louis', 'St. Louis') for k, v in SLUG_TO_ABBR.items()}

# Franchises that moved keep one identity, so year-to-year comparisons follow the club.
NHL_FRANCHISE = {11: 52, 33: 53, 27: 53, 59: 53, 68: 53, 34: 12}   # Atlanta>Winnipeg, Winnipeg(1979)>Phoenix>Arizona>Utah, Hartford>Carolina
NFL_FRANCHISE = {'STL': 'LA', 'SD': 'LAC', 'OAK': 'LV'}
NHL_CAP_FIRST_SEASON = 2005  # the 2005-06 season, after the cancelled 2004-05 season


# ---------- small statistics helpers ----------

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def pstdev(xs):
    xs = list(xs)
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def pearson(xs, ys):
    mx, my = mean(xs), mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return sxy / math.sqrt(sxx * syy)


def slope_intercept(xs, ys):
    mx, my = mean(xs), mean(ys)
    b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    return b, my - b * mx


def ranks(xs, descending=True):
    """Average ranks, 1 = largest when descending."""
    order = sorted(range(len(xs)), key=lambda i: -xs[i] if descending else xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def bootstrap_ci(pairs, stat, reps=BOOT, seed=SEED):
    rng = random.Random(seed)
    n = len(pairs)
    vals = []
    for _ in range(reps):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(stat([p[0] for p in sample], [p[1] for p in sample]))
    vals.sort()
    return vals[int(.025 * reps)], vals[int(.975 * reps) - 1]


def noll_scully(win_pcts, games):
    """Spread of winning percentages relative to a league where every game is a coin flip.
    1.0 means as balanced as chance allows; higher means less balanced."""
    return pstdev(win_pcts) / (0.5 / math.sqrt(games))


# ---------- the cap and floor simulator (the page runs the same arithmetic) ----------

def apply_cap_floor(payrolls, cap, floor):
    """payrolls: {team: $M}. Teams above the cap are cut to it, teams below the floor are raised to it.
    Static: no team changes behaviour beyond what the rule forces."""
    new = {t: min(max(p, floor), cap) for t, p in payrolls.items()}
    over = {t: p - cap for t, p in payrolls.items() if p > cap}
    under = {t: floor - p for t, p in payrolls.items() if p < floor}
    return dict(new=new, over=over, under=under, cut=sum(over.values()), add=sum(under.values()),
                net=sum(under.values()) - sum(over.values()))


def apply_revenue_band(payrolls, revenues, min_share, max_share, anchor=None):
    """A Premier League style rule: each team's payroll must sit between two shares of its own revenue.
    anchor, if given, also stops any team spending more than that multiple of the lowest team revenue."""
    ceiling = anchor * min(revenues.values()) if anchor else float('inf')
    new = {t: min(max(p, min_share * revenues[t]), max_share * revenues[t], ceiling) for t, p in payrolls.items()}
    # changes under $0.5 million are rounding, not a team the rule moves
    over = {t: p - new[t] for t, p in payrolls.items() if p - new[t] > .5}
    under = {t: new[t] - p for t, p in payrolls.items() if new[t] - p > .5}
    return dict(new=new, over=over, under=under, cut=sum(over.values()), add=sum(under.values()),
                net=sum(under.values()) - sum(over.values()))


def top_bottom_ratio(values, k=5):
    v = sorted(values, reverse=True)
    return mean(v[:k]) / mean(v[-k:])


# ---------- loading ----------

def load_payrolls():
    out = {}
    for line in (RAW / 'cots_payrolls.txt').read_text().splitlines():
        slug, body = line.split('=')
        team = SLUG_TO_ABBR[slug]
        for cell in body.split(';'):
            y, od, ye, cbt = cell.split(',')
            out[(team, int(y))] = dict(opening_day=float(od), year_end=float(ye), cbt=float(cbt) if cbt else None)
    return out


def load_revenue():
    with open(RAW / 'forbes_revenue_2025.csv') as f:
        return {r['team']: float(r['revenue_m']) for r in csv.DictReader(f)}


def revenue_rule(pay, teams):
    rev = load_revenue()
    base = {t: pay[(t, 2026)]['cbt'] for t in teams}
    shares = {t: base[t] / rev[t] for t in teams}

    def summary(lo, hi, anchor=None):
        r = apply_revenue_band(base, rev, lo, hi, anchor)
        return dict(min_share=lo, max_share=hi, anchor=anchor, ceiling=round(anchor * min(rev.values()), 1) if anchor else None,
                    dodgers=round(r['new']['LAD'], 1), over=sorted(r['over']), under=sorted(r['under']), cut=round(r['cut'], 1),
                    add=round(r['add'], 1), net=round(r['net'], 1), ratio_after=round(top_bottom_ratio(r['new'].values()), 2))

    top = max(shares, key=shares.get)
    return dict(revenue={t: rev[t] for t in teams}, league_share=round(sum(base.values()) / sum(rev.values()), 4),
                highest=dict(team=top, share=round(shares[top], 4)),
                rank_of=dict(LAD=sorted(shares, key=shares.get, reverse=True).index('LAD') + 1,
                             NYY=sorted(shares, key=shares.get, reverse=True).index('NYY') + 1),
                premier_league_85=summary(0, .85), default_band=summary(.45, .60),
                proposal=summary(.50, 9, 1.2), lowest=dict(team=min(rev, key=rev.get), revenue=min(rev.values())),
                # what the league's flat numbers mean as a share of each team's revenue
                league_floor_share={t: round(PROPOSAL['floor'] / rev[t], 4) for t in teams},
                league_cap_share={t: round(PROPOSAL['cap'] / rev[t], 4) for t in teams})


def load_mlb():
    lines = (RAW / 'mlb_standings.txt').read_text().splitlines()
    ids = {int(a.split(':')[0]): a.split(':')[1] for a in lines[0].split(' ')[1].split(',')}
    out = {}
    for line in lines[1:]:
        y, body = line.split(' ')
        for cell in body.split(','):
            i, w, l, po, ch = map(int, cell.split('-'))
            out[(ids[i], int(y))] = dict(w=w, l=l, playoffs=po, champion=ch)
    return out


def load_simple(name, franchise=None):
    """{league-season: {team: (win_pct, games)}} for the NBA and NHL files."""
    out = defaultdict(dict)
    for line in (RAW / name).read_text().splitlines():
        y, body = line.split(' ')
        for cell in body.split(','):
            p = list(map(int, cell.split('.')))
            team = (franchise or {}).get(p[0], p[0])
            if name.startswith('nhl'):
                _, w, gp, pts = p
                out[int(y)][team] = (pts / (2 * gp), gp)   # points percentage
            else:
                _, w, l = p
                out[int(y)][team] = (w / (w + l), w + l)
    return dict(out)


def load_nfl():
    rec = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    with open(RAW / 'nfl_games.csv') as f:
        for r in csv.DictReader(f):
            a, h = int(r['away_score']), int(r['home_score'])
            for team, mine, theirs in ((r['away_team'], a, h), (r['home_team'], h, a)):
                team = NFL_FRANCHISE.get(team, team)
                cell = rec[int(r['season'])][team]
                cell[0] += 1 if mine > theirs else .5 if mine == theirs else 0
                cell[1] += 1
    return {y: {t: (w / g, g) for t, (w, g) in teams.items()} for y, teams in rec.items()}


def mlb_as_league(mlb):
    out = defaultdict(dict)
    for (team, y), r in mlb.items():
        out[y][team] = (r['w'] / (r['w'] + r['l']), r['w'] + r['l'])
    return dict(out)


# ---------- analysis ----------

def money_and_wins(pay, mlb, measure='year_end'):
    seasons = sorted({y for _, y in mlb})
    teams = sorted({t for t, _ in mlb})
    rows, by_year = [], []
    for y in seasons:
        vals = {t: pay[(t, y)][measure] for t in teams}
        avg = mean(vals.values())
        rk = dict(zip(teams, ranks([vals[t] for t in teams])))
        year_rows = []
        for t in teams:
            m = mlb[(t, y)]
            year_rows.append(dict(team=t, season=y, payroll=vals[t], rel=vals[t] / avg, rank=rk[t],
                                  win_pct=m['w'] / (m['w'] + m['l']), w=m['w'], l=m['l'],
                                  playoffs=m['playoffs'], champion=m['champion']))
        rows += year_rows
        xs, ys = [r['rel'] for r in year_rows], [r['win_pct'] for r in year_rows]
        v = sorted(vals.values(), reverse=True)
        by_year.append(dict(season=y, r=round(pearson(xs, ys), 3),
                            spearman=round(pearson(ranks(xs), ranks(ys)), 3),
                            top5_bottom5=round(top_bottom_ratio(v), 2), max_min=round(v[0] / v[-1], 2),
                            cv=round(pstdev(v) / mean(v), 3), league_avg=round(avg, 1),
                            highest=round(v[0], 1), lowest=round(v[-1], 1)))
    return rows, by_year


def summarise_money(rows):
    xs, ys = [r['rel'] for r in rows], [r['win_pct'] for r in rows]
    r = pearson(xs, ys)
    lo, hi = bootstrap_ci(list(zip(xs, ys)), pearson)
    b, a = slope_intercept(xs, ys)
    groups = []
    for g in range(6):
        sel = [x for x in rows if g * 5 < x['rank'] <= g * 5 + 5]
        groups.append(dict(label=f'{g * 5 + 1}-{g * 5 + 5}', wins_per_162=round(mean(x['win_pct'] for x in sel) * 162, 1),
                           playoff_rate=round(mean(x['playoffs'] for x in sel), 3),
                           titles=sum(x['champion'] for x in sel), n=len(sel)))
    champs = [dict(season=x['season'], team=x['team'], rank=int(round(x['rank'])), rel=round(x['rel'], 2))
              for x in rows if x['champion']]
    eras = []
    for label, a0, a1 in (('2000-2011', 2000, 2011), ('2012-2021', 2012, 2021), ('2022-2026', 2022, 2026)):
        sel = [x for x in rows if a0 <= x['season'] <= a1]
        ex, ey = [x['rel'] for x in sel], [x['win_pct'] for x in sel]
        elo, ehi = bootstrap_ci(list(zip(ex, ey)), pearson)
        eras.append(dict(era=label, r=round(pearson(ex, ey), 3), ci=[round(elo, 3), round(ehi, 3)],
                         top10_playoff_rate=round(mean(x['playoffs'] for x in sel if x['rank'] <= 10), 3),
                         bottom10_playoff_rate=round(mean(x['playoffs'] for x in sel if x['rank'] > 20), 3)))
    return dict(n=len(rows), pooled_r=round(r, 3), pooled_r_ci=[round(lo, 3), round(hi, 3)], r_squared=round(r * r, 3),
                slope_win_pct_per_unit_rel=round(b, 4), intercept=round(a, 4),
                wins_per_50pct_above_average=round(b * .5 * 162, 1),
                rank_groups=groups, champions=champs,
                champions_top10=sum(c['rank'] <= 10 for c in champs),
                champions_bottom15=sum(c['rank'] > 15 for c in champs), eras=eras)


def league_balance(league, first=2000, last=2025):
    seasons = sorted(y for y in league if first <= y <= last)
    per_season = []
    for y in seasons:
        teams = league[y]
        per_season.append(dict(season=y, noll_scully=round(noll_scully([v[0] for v in teams.values()],
                                                                       mean(v[1] for v in teams.values())), 3)))

    def pairs(gap):
        out = []
        for y in seasons:
            if y + gap in league and y + gap <= last:
                out += [(league[y][t][0], league[y + gap][t][0]) for t in league[y] if t in league[y + gap]]
        return out

    res = dict(seasons=[seasons[0], seasons[-1]], noll_scully=round(mean(s['noll_scully'] for s in per_season), 2),
               per_season=per_season)
    for gap, key in ((1, 'next_season_r'), (5, 'five_season_r')):
        p = pairs(gap)
        if len(p) < 30:
            continue
        lo, hi = bootstrap_ci(p, pearson)
        res[key] = round(pearson(*zip(*p)), 3)
        res[key + '_ci'] = [round(lo, 3), round(hi, 3)]
        res[key + '_n'] = len(p)
    return res


def simulator_baseline(pay, mlb, slope):
    teams = sorted({t for t, _ in mlb})
    base = {t: pay[(t, 2026)]['cbt'] for t in teams}
    sim = apply_cap_floor(base, PROPOSAL['cap'], PROPOSAL['floor'])
    return dict(
        season=2026, measure='Competitive balance tax payroll (projected year end, Cot\'s Contracts, as of 1 November 2026)',
        teams=[dict(team=t, name=TEAM_NAMES[t], payroll=base[t], wins=mlb[(t, 2026)]['w'], losses=mlb[(t, 2026)]['l'],
                    playoffs=mlb[(t, 2026)]['playoffs']) for t in teams],
        slope=round(slope, 4), proposal=PROPOSAL,
        may_offer=dict(cap=245.3, floor=171.2, net=round(apply_cap_floor(base, 245.3, 171.2)['net'], 1)),
        check=dict(over=sorted(sim['over']), under=sorted(sim['under']), cut=round(sim['cut'], 1), add=round(sim['add'], 1),
                   net=round(sim['net'], 1), same_over=sorted(sim['over']) == sorted(PROPOSAL['reported_over']),
                   same_under=sorted(sim['under']) == sorted(PROPOSAL['reported_under']),
                   ratio_before=round(top_bottom_ratio(base.values()), 2),
                   ratio_after=round(top_bottom_ratio(sim['new'].values()), 2)))


def write_csvs(pay, mlb, rows):
    with open(HERE / 'data' / 'mlb_team_seasons.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['season', 'team', 'wins', 'losses', 'playoffs', 'champion', 'opening_day_payroll_m',
                    'year_end_payroll_m', 'cbt_payroll_m', 'year_end_vs_league_avg', 'year_end_rank'])
        for r in sorted(rows, key=lambda r: (r['season'], r['team'])):
            p = pay[(r['team'], r['season'])]
            w.writerow([r['season'], r['team'], r['w'], r['l'], r['playoffs'], r['champion'], p['opening_day'],
                        p['year_end'], '' if p['cbt'] is None else p['cbt'], round(r['rel'], 4), r['rank']])


def main():
    pay, mlb = load_payrolls(), load_mlb()
    rows, by_year = money_and_wins(pay, mlb)
    money = summarise_money(rows)
    leagues = dict(MLB=mlb_as_league(mlb), NBA=load_simple('nba_standings.txt'),
                   NHL=load_simple('nhl_standings.txt', NHL_FRANCHISE), NFL=load_nfl())
    balance = {name: league_balance(lg) for name, lg in leagues.items()}
    nhl = leagues['NHL']
    balance['NHL']['before_cap'] = league_balance(nhl, 1995, NHL_CAP_FIRST_SEASON - 2)
    balance['NHL']['after_cap'] = league_balance(nhl, NHL_CAP_FIRST_SEASON, 2025)
    balance['MLB']['recent'] = league_balance(leagues['MLB'], 2022, 2026)
    balance['MLB']['through_2026'] = league_balance(leagues['MLB'], 2000, 2026)
    cbt_rows, cbt_by_year = money_and_wins({k: v for k, v in pay.items()}, {k: v for k, v in mlb.items() if k[1] >= 2012}, 'cbt')
    cx, cy = [r['rel'] for r in cbt_rows], [r['win_pct'] for r in cbt_rows]
    cbt_slope = slope_intercept(cx, cy)[0]
    money['cbt_2012_2026'] = dict(n=len(cbt_rows), r=round(pearson(cx, cy), 3), slope=round(cbt_slope, 4),
                                  wins_per_50pct_above_average=round(cbt_slope * .5 * 162, 1))
    results = dict(
        money=money, by_year=by_year, cbt_by_year=cbt_by_year,
        scatter=[dict(t=r['team'], s=r['season'], x=round(r['rel'], 3), y=round(r['win_pct'], 3), p=r['playoffs'], c=r['champion'])
                 for r in rows],
        balance=balance, simulator=simulator_baseline(pay, mlb, cbt_slope))
    results['revenue_rule'] = revenue_rule(pay, sorted({t for t, _ in mlb}))
    # Tampa Bay lost the 2026 World Series to Milwaukee (NBC Sports, 28 October 2026)
    results['simulator']['finalist_rank'] = int(next(r['rank'] for r in rows if r['team'] == 'TB' and r['season'] == 2026))
    write_csvs(pay, mlb, rows)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(results, separators=(',', ':')) + '\n')
    return results


if __name__ == '__main__':
    r = main()
    m, s = r['money'], r['simulator']['check']
    print('pooled r', m['pooled_r'], m['pooled_r_ci'], 'r2', m['r_squared'], 'wins per +50%', m['wins_per_50pct_above_average'])
    print('eras', m['eras'])
    print('cbt', m['cbt_2012_2026'])
    print('groups', [(g['label'], g['wins_per_162'], g['playoff_rate'], g['titles']) for g in m['rank_groups']])
    print('champs top10', m['champions_top10'], 'bottom15', m['champions_bottom15'], 'of', len(m['champions']))
    print('disparity', [(y['season'], y['top5_bottom5'], y['r']) for y in r['by_year']])
    print('proposal check', s)
    for k, v in r['balance'].items():
        print(k, v['seasons'], 'NS', v['noll_scully'], 'next', v['next_season_r'], v['next_season_r_ci'], '5yr', v['five_season_r'], v['five_season_r_ci'])
    b = r['balance']['NHL']
    for k in ('before_cap', 'after_cap'):
        print('NHL', k, b[k]['seasons'], b[k]['noll_scully'], b[k]['next_season_r'], b[k]['next_season_r_ci'], b[k]['five_season_r'])
    print('MLB recent', r['balance']['MLB']['recent']['noll_scully'], r['balance']['MLB']['recent']['next_season_r'])
    print('MLB through 2026', r['balance']['MLB']['through_2026']['noll_scully'], r['balance']['MLB']['through_2026']['next_season_r'])
