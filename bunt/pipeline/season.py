"""Download one season of Statcast and reduce it to one row per plate appearance.

    python bunt/pipeline/season.py 2025 out/

Writes out/pa_2025.parquet. Source: Baseball Savant, through the pybaseball package.
Only the regular season is kept.
"""
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

MONTHS = [(3, 15, 3, 31), (4, 1, 4, 30), (5, 1, 5, 31), (6, 1, 6, 30), (7, 1, 7, 31), (8, 1, 8, 31), (9, 1, 9, 30), (10, 1, 10, 10)]
BUNT_PITCHES = {'foul_bunt', 'missed_bunt', 'bunt_foul_tip'}
NEEDED = ['game_pk', 'game_date', 'game_type', 'at_bat_number', 'pitch_number', 'inning', 'inning_topbot', 'outs_when_up',
          'on_1b', 'on_2b', 'on_3b', 'bat_score', 'post_bat_score', 'fld_score', 'post_home_score', 'post_away_score',
          'home_team', 'away_team', 'events', 'description', 'des', 'batter', 'pitcher', 'woba_value', 'woba_denom']
TWO_WAY = {660271}            # Shohei Ohtani bats as a regular hitter
PITCHER_MIN_PITCHES = 300      # thrown in the season; keeps position players who mop up an inning out of the pitcher group


def download(season: int, pause: float = 2.0) -> pd.DataFrame:
    from pybaseball import statcast
    frames = []
    for m1, d1, m2, d2 in MONTHS:
        start, end = date(season, m1, d1), min(date(season, m2, d2), date.today())
        if start > date.today():
            continue
        print(f'  {start} to {end} ...', flush=True)
        f = None
        for attempt in range(4):
            try:
                f = statcast(start_dt=start.isoformat(), end_dt=end.isoformat(), verbose=False)
                break
            except Exception as exc:  # Savant sometimes drops a request
                print('    retry after', exc, flush=True)
                time.sleep(20 * (attempt + 1))
        if f is None or f.empty:      # no games that month (March or October in most years, April to June in 2020)
            print('    no games')
            continue
        missing = [c for c in NEEDED if c not in f.columns]
        if missing:
            raise SystemExit(f'Statcast no longer returns: {missing}')
        frames.append(f.loc[f['game_type'] == 'R', NEEDED])
        time.sleep(pause)
    if not frames:
        raise SystemExit(f'No data returned for {season}')
    out = pd.concat(frames, ignore_index=True)
    least = 200_000 if season == 2020 else 600_000      # a full season has about 700,000 pitches
    if season < date.today().year and len(out) < least:
        raise SystemExit(f'Only {len(out):,} pitches for {season}; a month is probably missing')
    return out


def to_plate_appearances(p: pd.DataFrame, season: int) -> pd.DataFrame:
    """One row per completed plate appearance, with the state it started in and what followed."""
    p = p.drop_duplicates(['game_pk', 'at_bat_number', 'pitch_number']).sort_values(['game_pk', 'at_bat_number', 'pitch_number'])
    p['top'] = p['inning_topbot'].eq('Top')
    half = ['game_pk', 'inning', 'top']
    for c in ('bat_score', 'post_bat_score', 'fld_score', 'post_home_score', 'post_away_score'):
        p[c] = pd.to_numeric(p[c], errors='coerce')
    p['half_end_score'] = p.groupby(half)['post_bat_score'].transform('max')
    p['final_home'] = p.groupby('game_pk')['post_home_score'].transform('max')
    p['final_away'] = p.groupby('game_pk')['post_away_score'].transform('max')
    p['bunt_pitch'] = p['description'].isin(BUNT_PITCHES)
    for b in ('1b', '2b', '3b'):          # groupby.first() skips missing values, so turn the runner columns into flags first
        p['has_' + b] = p['on_' + b].notna()

    g = p.groupby(['game_pk', 'at_bat_number'], sort=False)
    first, last = g.first(), g.last()
    pa = pd.DataFrame({
        'season': season,
        'inning': first['inning'].astype(int), 'top': first['top'].astype(bool), 'outs': first['outs_when_up'].astype(int),
        'b1': g['has_1b'].first(), 'b2': g['has_2b'].first(), 'b3': g['has_3b'].first(),
        'score_diff': (first['bat_score'] - first['fld_score']).astype(int),
        'events': last['events'], 'des': last['des'].fillna(''), 'last_description': last['description'],
        'any_bunt_pitch': g['bunt_pitch'].any(),
        'runs_on_play': (last['post_bat_score'] - first['bat_score']).astype(int),
        'runs_rest': (first['half_end_score'] - first['bat_score']).astype(int),
        'batter': first['batter'].astype(int), 'bat_team': np.where(first['top'], first['away_team'], first['home_team']),
        'woba_value': pd.to_numeric(last['woba_value'], errors='coerce'), 'woba_denom': pd.to_numeric(last['woba_denom'], errors='coerce'),
        'final_home': first['final_home'], 'final_away': first['final_away'],
    }).reset_index()
    pa = pa[pa['events'].notna() & ~pa['events'].isin(['truncated_pa', ''])].copy()

    pa['bunt_in_play'] = pa['des'].str.contains('bunt', case=False) & ~pa['events'].isin(['strikeout', 'strikeout_double_play', 'walk', 'hit_by_pitch'])
    pa['bunt_strikeout'] = pa['events'].isin(['strikeout', 'strikeout_double_play']) & pa['last_description'].isin(BUNT_PITCHES)
    pa['bunt'] = pa['bunt_in_play'] | pa['bunt_strikeout']
    pa['bat_won'] = np.where(pa['top'], pa['final_away'] > pa['final_home'], pa['final_home'] > pa['final_away'])
    # a home half-inning in the 9th or later that ends the game is cut short, so its run total is not a full inning
    last_half = pa.groupby('game_pk')[['inning', 'top']].transform('last')
    pa['walkoff_half'] = (~pa['top']) & (pa['inning'] >= 9) & (pa['inning'] == last_half['inning']) & (~last_half['top']) & (pa['final_home'] > pa['final_away'])

    # the state the next batter of the same half-inning found (3 outs if the inning ended)
    pa = pa.sort_values(['game_pk', 'at_bat_number'])
    nxt = pa.groupby(['game_pk', 'inning', 'top'])[['outs', 'b1', 'b2', 'b3']].shift(-1)
    pa['after_outs'] = nxt['outs'].fillna(3).astype(int)
    for b in ('b1', 'b2', 'b3'):
        pa['after_' + b] = nxt[b].fillna(False).astype(bool)

    # who is batting: a pitcher, or a hitter in the weak, middle or strong third by season wOBA
    thrown = p.groupby('pitcher').size()
    pitchers = set(thrown[thrown >= PITCHER_MIN_PITCHES].index) - TWO_WAY
    w = pa.groupby('batter').agg(v=('woba_value', 'sum'), d=('woba_denom', 'sum'))
    w['woba'] = w['v'] / w['d'].where(w['d'] > 0)
    hitters = w[~w.index.isin(pitchers) & w['woba'].notna()].sort_values('woba')
    share = hitters['d'].cumsum() / hitters['d'].sum()          # thirds of plate appearances, not of players
    cls = pd.Series(np.where(share <= 1 / 3, 'weak', np.where(share <= 2 / 3, 'middle', 'strong')), index=hitters.index)
    pa['batter_class'] = pa['batter'].map(cls).fillna('middle')
    pa.loc[pa['batter'].isin(pitchers), 'batter_class'] = 'pitcher'
    pa['batter_woba'] = pa['batter'].map(w['woba'])
    keep = ['season', 'game_pk', 'at_bat_number', 'inning', 'top', 'outs', 'b1', 'b2', 'b3', 'score_diff', 'events', 'des', 'any_bunt_pitch',
            'bunt_in_play', 'bunt_strikeout', 'bunt', 'runs_on_play', 'runs_rest', 'bat_won', 'walkoff_half', 'after_outs', 'after_b1',
            'after_b2', 'after_b3', 'batter', 'bat_team', 'batter_class', 'batter_woba']
    return pa[keep].reset_index(drop=True)


if __name__ == '__main__':
    season, out = int(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    pitches = download(season)
    print(f'{len(pitches):,} regular-season pitches')
    pa = to_plate_appearances(pitches, season)
    print(f'{len(pa):,} plate appearances, {int(pa["bunt"].sum()):,} bunts')
    pa.to_parquet(out / f'pa_{season}.parquet', index=False)
