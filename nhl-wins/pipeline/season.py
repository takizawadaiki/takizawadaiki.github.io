"""Download one NHL regular season of play-by-play and reduce each game to one row of shots and goals.

    python nhl-wins/pipeline/season.py 2025 out/      # the 2025-26 season

Writes out/games_2025.csv. Shots on goal are counted by period and by the score at the moment of the shot
(shooting team tied, leading or trailing). The shootout is left out of every count. Source: the NHL's public web API.
"""
from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

PBP = 'https://api-web.nhle.com/v1/gamecenter/{game}/play-by-play'
MAX_GAME = 1312
HEADERS = {'User-Agent': 'nhl-research (github.com/takizawadaiki)'}
SIDE_COLS = ['goals', 'sog', 'sog_p1', 'sog_p2', 'sog_p3', 'sog_ot', 'sog_tied', 'sog_lead', 'sog_trail', 'goals_p1', 'goals_p2', 'goals_p3']
COLUMNS = (['season', 'game', 'date', 'home', 'away', 'winner', 'decided_in', 'first_goal', 'secs_tied', 'secs_home_lead', 'secs_away_lead']
           + ['home_' + c for c in SIDE_COLS] + ['away_' + c for c in SIDE_COLS])


def fetch(url, tries=4):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'Could not fetch {url}')


def clock(play):
    m, s = play['timeInPeriod'].split(':')
    return (play['periodDescriptor']['number'] - 1) * 1200 + int(m) * 60 + int(s)


def game_row(game, season):
    """One finished regular-season game as a dict, or None."""
    if not game or game.get('gameState') not in ('OFF', 'FINAL') or game.get('gameType') != 2:
        return None
    home, away = game['homeTeam'], game['awayTeam']
    plays = sorted(game.get('plays', []), key=lambda p: p['sortOrder'])
    side = {home['id']: 'home', away['id']: 'away'}
    n = {s + '_' + c: 0 for s in ('home', 'away') for c in SIDE_COLS}
    score = {'home': 0, 'away': 0}
    secs = {'tied': 0, 'home': 0, 'away': 0}
    last_t, first_goal, end = 0, '', 0
    state = lambda: 'tied' if score['home'] == score['away'] else 'home' if score['home'] > score['away'] else 'away'
    for p in plays:
        pd = p['periodDescriptor']
        if pd.get('periodType') == 'SO':
            continue
        t = clock(p)
        end = max(end, t)
        kind = p['typeDescKey']
        if kind not in ('shot-on-goal', 'goal'):
            continue
        s = side.get(p.get('details', {}).get('eventOwnerTeamId'))
        if s is None:
            continue
        other = 'away' if s == 'home' else 'home'
        per = pd['number']
        n[f'{s}_sog'] += 1
        n[f"{s}_sog_{'p' + str(per) if per <= 3 else 'ot'}"] += 1
        n[f"{s}_sog_{'tied' if score[s] == score[other] else 'lead' if score[s] > score[other] else 'trail'}"] += 1
        if kind == 'goal':
            secs[state()] += t - last_t
            last_t = t
            score[s] += 1
            n[f'{s}_goals'] += 1
            if per <= 3:
                n[f'{s}_goals_p{per}'] += 1
            first_goal = first_goal or s
    secs[state()] += max(0, end - last_t)
    if n['home_sog'] + n['away_sog'] < 20:
        return None                       # play-by-play missing or broken for this game
    hs, as_ = home.get('score'), away.get('score')
    if hs is None or as_ is None or hs == as_:
        return None
    decided = (game.get('gameOutcome') or {}).get('lastPeriodType') or ('REG' if score['home'] != score['away'] else 'SO')
    row = dict(season=season, game=game['id'], date=game.get('gameDate', ''), home=home['abbrev'], away=away['abbrev'],
               winner='home' if hs > as_ else 'away', decided_in=decided, first_goal=first_goal,
               secs_tied=secs['tied'], secs_home_lead=secs['home'], secs_away_lead=secs['away'])
    row.update(n)
    return row


def main(year, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ids = [f'{year}02{i:04d}' for i in range(1, MAX_GAME + 1)]
    with ThreadPoolExecutor(6) as pool:
        games = list(pool.map(lambda g: fetch(PBP.format(game=g)), ids))
    found = sum(1 for g in games if g)
    rows = [r for r in (game_row(g, year) for g in games) if r]
    if len(rows) < 600:
        raise SystemExit(f'Only {len(rows)} usable games of {found} found for {year}')
    with open(out / f'games_{year}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f'{year}: {len(rows)} games kept of {found} found')


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2])
