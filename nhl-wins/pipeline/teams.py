"""Download every NHL team season: regular-season scoring and shots, and playoff results.

    python nhl-wins/pipeline/teams.py out/

Writes out/team_seasons.csv (one row per team and season) from the NHL's public statistics API.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import requests

URL = 'https://api.nhle.com/stats/rest/en/team/summary?limit=-1&sort=seasonId&cayenneExp=gameTypeId={kind}'
HEADERS = {'User-Agent': 'nhl-research (github.com/takizawadaiki)'}
KEEP = ['gamesPlayed', 'wins', 'losses', 'ties', 'otLosses', 'points', 'pointPct', 'goalsFor', 'goalsAgainst', 'goalsForPerGame',
        'goalsAgainstPerGame', 'shotsForPerGame', 'shotsAgainstPerGame', 'powerPlayPct', 'penaltyKillPct', 'faceoffWinPct']


def fetch(url):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()['data']
        except requests.RequestException:
            pass
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'Could not fetch {url}')


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    regular, playoffs = fetch(URL.format(kind=2)), fetch(URL.format(kind=3))
    print('fields:', sorted(regular[0]))
    post = {(r['seasonId'], r['teamId']): r for r in playoffs}
    with open(out / 'team_seasons.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['season', 'team_id', 'team'] + KEEP + ['playoff_games', 'playoff_wins', 'playoff_losses', 'playoff_goals_for', 'playoff_goals_against'])
        for r in sorted(regular, key=lambda r: (r['seasonId'], r['teamFullName'])):
            p = post.get((r['seasonId'], r['teamId']), {})
            w.writerow([r['seasonId'] // 10000, r['teamId'], r['teamFullName']] + [r.get(k, '') if r.get(k) is not None else '' for k in KEEP]
                       + [p.get('gamesPlayed', 0), p.get('wins', 0), p.get('losses', 0), p.get('goalsFor', 0), p.get('goalsAgainst', 0)])
    print(f'{len(regular)} team seasons, {len(playoffs)} playoff teams')


if __name__ == '__main__':
    main(sys.argv[1])
