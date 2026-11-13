"""Download one NHL regular season of play-by-play and keep every faceoff.

    python faceoffs/pipeline/season.py 2025 out/      # the 2025-26 season

Writes out/faceoffs_2025.csv.gz (one row per faceoff), out/players_2025.csv (everyone who dressed)
and out/bios_2025.csv (height, weight, shooting hand and birth date). Source: the NHL's public web API.
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

PBP = 'https://api-web.nhle.com/v1/gamecenter/{game}/play-by-play'
BIOS = 'https://api.nhle.com/stats/rest/en/skater/bios?limit=-1&cayenneExp=seasonId={season}%20and%20gameTypeId=2'
MAX_GAME = 1312                   # 32 teams x 82 games / 2; earlier seasons simply have fewer
WINDOW = 30                       # seconds after a faceoff in which shots and goals are credited to it
HEADERS = {'User-Agent': 'faceoff-research (github.com/takizawadaiki)'}
COLUMNS = ['season', 'game', 'period', 'period_type', 'seconds', 'x', 'y', 'home_defends', 'home_team', 'away_team', 'winner_team',
           'winner', 'loser', 'situation', 'sog_w', 'sog_l', 'goals_w', 'goals_l']


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


def game_rows(game, season):
    """Faceoffs in one finished game, each with the shots on goal and goals of the next WINDOW seconds
    (or until the next faceoff, whichever comes first), split by the team that won the draw."""
    if not game or game.get('gameState') not in ('OFF', 'FINAL') or game.get('gameType') != 2:
        return [], []
    plays = sorted(game['plays'], key=lambda p: p['sortOrder'])
    home, away = game['homeTeam']['id'], game['awayTeam']['id']
    rows = []
    for i, p in enumerate(plays):
        if p['typeDescKey'] != 'faceoff':
            continue
        d = p.get('details', {})
        if 'winningPlayerId' not in d or 'losingPlayerId' not in d:
            continue
        t0, win_team = clock(p), d['eventOwnerTeamId']
        sog = {True: 0, False: 0}
        goals = {True: 0, False: 0}
        for q in plays[i + 1:]:
            if q['typeDescKey'] == 'faceoff' or q['periodDescriptor']['number'] != p['periodDescriptor']['number'] or clock(q) - t0 > WINDOW:
                break
            owner = q.get('details', {}).get('eventOwnerTeamId')
            if q['typeDescKey'] in ('shot-on-goal', 'goal'):
                sog[owner == win_team] += 1
            if q['typeDescKey'] == 'goal':
                goals[owner == win_team] += 1
        rows.append([season, game['id'], p['periodDescriptor']['number'], p['periodDescriptor'].get('periodType', ''), t0,
                     d.get('xCoord', ''), d.get('yCoord', ''), p.get('homeTeamDefendingSide', ''), home, away, win_team,
                     d['winningPlayerId'], d['losingPlayerId'], p.get('situationCode', ''), sog[True], sog[False], goals[True], goals[False]])
    roster = [(r['playerId'], f"{r['firstName']['default']} {r['lastName']['default']}", r['positionCode'], r['teamId']) for r in game.get('rosterSpots', [])]
    return rows, roster


def main(year, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    season = int(f'{year}{year + 1}')
    ids = [f'{year}02{n:04d}' for n in range(1, MAX_GAME + 1)]
    with ThreadPoolExecutor(6) as pool:
        games = list(pool.map(lambda g: fetch(PBP.format(game=g)), ids))
    rows, players, played = [], {}, 0
    for g in games:
        r, roster = game_rows(g, year)
        if r:
            played += 1
        rows += r
        for pid, name, pos, team in roster:
            seen = players.setdefault(pid, [name, {}])[1]
            seen[pos] = seen.get(pos, 0) + 1
    if played < 800:
        raise SystemExit(f'Only {played} games found for {season}')
    with gzip.open(out / f'faceoffs_{year}.csv.gz', 'wt', newline='') as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)
    with open(out / f'players_{year}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['season', 'player', 'name', 'position', 'games'])
        for pid, (name, pos) in sorted(players.items()):
            w.writerow([year, pid, name, max(pos, key=pos.get), sum(pos.values())])
    bios = fetch(BIOS.format(season=season))['data']
    print('bio fields:', sorted(bios[0]))
    keep = ['playerId', 'skaterFullName', 'birthDate', 'height', 'weight', 'shootsCatches', 'positionCode', 'draftOverall', 'draftYear',
            'nationalityCode', 'gamesPlayed']
    with open(out / f'bios_{year}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['season'] + keep)
        for b in bios:
            w.writerow([year] + [b.get(k, '') for k in keep])
    print(f'{season}: {played} games, {len(rows):,} faceoffs, {len(players)} players, {len(bios)} bios')


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2])
