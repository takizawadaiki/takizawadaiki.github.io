"""Rebuild chart-values.json from the NBA Stats API, using the method the article describes.

Method (from bench-research.html, "What we actually measure"):
  - nba_api LeagueDashPlayerStats with starter_bench_nullable='Bench', per-game averages
  - x ("reg")     = mean over a team's bench players of regular-season minutes per game
  - y ("playoff") = mean over a team's bench players of playoff points per game
  - one record per team per season, for the 16 teams that played in the playoffs proper
    (the 'Playoffs' season type excludes play-in games)
  - averages are unweighted means of per-player averages, as the article describes

What the article does NOT say (so these are choices, recorded in data-provenance.json):
  - which players count when a team's bench is averaged (here: every player with a Bench row for
    that team in that split, with no minimum-games filter)
  - how players traded mid-season are handled (the endpoint reports each player once, under the
    team he finished with)
Sensitivity checks with other reasonable choices are computed and saved next to the data, so the
conclusion can be judged against the choice.

Run (on a computer that can reach stats.nba.com, e.g. your own):
    pip install -r requirements-rebuild.txt
    python rebuild_data.py            # writes chart-values.json and data-provenance.json
    python reanalysis.py              # refreshes audit-results.json
    python rebuild_data.py --selftest # checks the aggregation logic offline
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SEASONS = ['2023-24', '2024-25', '2025-26']
DASH = '–'  # the site labels seasons with an en dash, e.g. 2023–24


def season_label(season):
    return season.replace('-', DASH)


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def aggregate(reg_rows, po_rows, min_games=0, weighted=False, playoff_roster_only=False):
    """Pure function. Rows are dicts with TEAM_ABBREVIATION, PLAYER_ID, GP, MIN, PTS (per game).

    Returns {team: {'reg': x, 'playoff': y}} for every team that has playoff bench rows.
    """
    def by_team(rows):
        out = {}
        for r in rows:
            if r['GP'] >= min_games:
                out.setdefault(r['TEAM_ABBREVIATION'], []).append(r)
        return out

    reg, po = by_team(reg_rows), by_team(po_rows)
    result = {}
    for team, po_players in po.items():
        reg_players = reg.get(team, [])
        if playoff_roster_only:
            ids = {p['PLAYER_ID'] for p in po_players}
            reg_players = [p for p in reg_players if p['PLAYER_ID'] in ids]
        if not reg_players or not po_players:
            continue
        if weighted:  # total bench minutes / total bench player-games, and the same for points
            x = sum(p['MIN'] * p['GP'] for p in reg_players) / sum(p['GP'] for p in reg_players)
            y = sum(p['PTS'] * p['GP'] for p in po_players) / sum(p['GP'] for p in po_players)
        else:
            x = mean(p['MIN'] for p in reg_players)
            y = mean(p['PTS'] for p in po_players)
        result[team] = {'reg': x, 'playoff': y}
    return result


def pearson(rows):
    n = len(rows)
    xs, ys = [r['reg'] for r in rows], [r['playoff'] for r in rows]
    mx, my = mean(xs), mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy and n > 2 else float('nan')


def fetch(season, season_type, retries=4, pause=2.0):
    from nba_api.stats.endpoints import leaguedashplayerstats
    last = None
    for attempt in range(retries):
        try:
            frame = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, season_type_all_star=season_type,
                starter_bench_nullable='Bench', per_mode_detailed='PerGame', timeout=60,
            ).get_data_frames()[0]
            time.sleep(pause)
            return frame[['TEAM_ABBREVIATION', 'PLAYER_ID', 'PLAYER_NAME', 'GP', 'MIN', 'PTS']].to_dict('records')
        except Exception as exc:  # network errors, NBA throttling
            last = exc
            time.sleep(pause * (attempt + 2))
    raise SystemExit(f'Could not fetch {season} {season_type} after {retries} tries: {last}\n'
                     'stats.nba.com often blocks cloud servers; run this on your own computer.')


def selftest():
    reg = [dict(TEAM_ABBREVIATION='AAA', PLAYER_ID=i, GP=g, MIN=m, PTS=0) for i, (g, m) in enumerate([(10, 10.0), (50, 20.0), (2, 30.0)])]
    po = [dict(TEAM_ABBREVIATION='AAA', PLAYER_ID=i + 1, GP=g, MIN=0, PTS=p) for i, (g, p) in enumerate([(5, 2.0), (5, 6.0)])]
    reg += [dict(TEAM_ABBREVIATION='BBB', PLAYER_ID=99, GP=40, MIN=15.0, PTS=0)]  # BBB missed the playoffs
    out = aggregate(reg, po)
    assert set(out) == {'AAA'}, 'teams without playoff rows must be excluded'
    assert abs(out['AAA']['reg'] - 20.0) < 1e-9 and abs(out['AAA']['playoff'] - 4.0) < 1e-9, 'unweighted means'
    w = aggregate(reg, po, weighted=True)
    assert abs(w['AAA']['reg'] - (10 * 10 + 50 * 20 + 2 * 30) / 62) < 1e-9, 'games-weighted mean'
    assert abs(aggregate(reg, po, min_games=5)['AAA']['reg'] - 15.0) < 1e-9, 'min-games filter drops the 2-game player'
    assert abs(aggregate(reg, po, playoff_roster_only=True)['AAA']['reg'] - 25.0) < 1e-9, 'playoff-roster filter'
    pts = [dict(reg=1, playoff=2), dict(reg=2, playoff=4), dict(reg=3, playoff=6)]
    assert abs(pearson(pts) - 1.0) < 1e-12
    print('selftest passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='chart-values.json')
    ap.add_argument('--provenance', default='data-provenance.json')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    import nba_api
    out_path = Path(args.out)
    previous = json.loads(out_path.read_text(encoding='utf-8')) if out_path.exists() else []
    raw, records = {}, []
    for season in SEASONS:
        print('Fetching', season, '...', flush=True)
        raw[season] = (fetch(season, 'Regular Season'), fetch(season, 'Playoffs'))
        teams = aggregate(*raw[season])
        if len(teams) != 16:
            raise SystemExit(f'{season}: expected 16 playoff teams, found {len(teams)}: {sorted(teams)}. '
                             'The season may be incomplete, or the endpoint changed.')
        for team, v in teams.items():
            records.append(dict(team=team, reg=round(v['reg'], 2), playoff=round(v['playoff'], 2), season=season_label(season)))

    # Keep the file's order stable: by season, then by the previous file's team order, then alphabetically.
    prior_order = {(r['team'], r['season']): i for i, r in enumerate(previous)}
    records.sort(key=lambda r: (SEASONS.index(r['season'].replace(DASH, '-')), prior_order.get((r['team'], r['season']), 10 ** 6), r['team']))

    # Sensitivity: the same pooled correlation under other reasonable ways to define the averages.
    variants = {
        'primary (unweighted, all bench players)': {},
        'weighted by games played': dict(weighted=True),
        'bench players with at least 10 games': dict(min_games=10),
        'bench players on the playoff roster only': dict(playoff_roster_only=True),
    }
    sensitivity = {}
    for name, kw in variants.items():
        rows = [dict(r) for s in SEASONS for r in aggregate(*raw[s], **kw).values()]
        sensitivity[name] = dict(n=len(rows), pooled_r=round(pearson(rows), 4))

    changes = []
    old = {(r['team'], r['season']): r for r in previous}
    new = {(r['team'], r['season']): r for r in records}
    for key in sorted(set(old) | set(new)):
        if key not in new:
            changes.append(f'removed {key[0]} {key[1]} (was in the original data)')
        elif key not in old:
            changes.append(f'added {key[0]} {key[1]}')
        else:
            d = (new[key]['reg'] - old[key]['reg'], new[key]['playoff'] - old[key]['playoff'])
            if abs(d[0]) > 0.05 or abs(d[1]) > 0.05:
                changes.append(f"{key[0]} {key[1]}: reg {old[key]['reg']} -> {new[key]['reg']}, playoff {old[key]['playoff']} -> {new[key]['playoff']}")

    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    Path(args.provenance).write_text(json.dumps(dict(
        retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        source='stats.nba.com via nba_api LeagueDashPlayerStats',
        nba_api_version=getattr(nba_api, '__version__', 'unknown'),
        parameters=dict(starter_bench_nullable='Bench', per_mode_detailed='PerGame', season_types=['Regular Season', 'Playoffs'], seasons=SEASONS),
        aggregation='unweighted mean of per-player per-game averages; playoff teams only (play-in excluded); no minimum games',
        known_limitation='the endpoint reports traded players once, under their final team',
        records=len(records),
        sensitivity_pooled_r=sensitivity,
        changes_from_previous_chart_values=changes,
    ), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'\nWrote {len(records)} records to {out_path} and provenance to {args.provenance}')
    print('Changes from the previous file:'); [print('  -', c) for c in changes or ['none']]
    print('Pooled r under different definitions:'); [print(f'  {k}: {v["pooled_r"]}') for k, v in sensitivity.items()]
    print('\nNext: python reanalysis.py   (refreshes audit-results.json)')


if __name__ == '__main__':
    sys.exit(main())
