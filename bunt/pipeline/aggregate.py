"""Combine the season files into the small tables the analysis reads.

    python bunt/pipeline/aggregate.py out/ bunt/data/

Writes re_matrix.csv, bunts.csv, baseline.csv, seasons.csv, league_rates.csv and manifest.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def inning_bucket(i):
    return np.select([i <= 6, i <= 8, i == 9], ['1-6', '7-8', '9'], '10+')


def diff_bucket(d):
    return np.select([d <= -2, d == -1, d == 0, d == 1], ['-2', '-1', '0', '+1'], '+2')


def bases(df, prefix=''):
    return df[prefix + 'b1'].astype(int).astype(str) + df[prefix + 'b2'].astype(int).astype(str) + df[prefix + 'b3'].astype(int).astype(str)


def main(src, dst):
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    pa = pd.concat([pd.read_parquet(f) for f in sorted(src.glob('pa_*.parquet'))], ignore_index=True)
    pa['bases'] = bases(pa)
    pa['after_bases'] = bases(pa, 'after_')
    pa['scored'] = pa['runs_rest'] > 0
    pa['inning_bucket'] = inning_bucket(pa['inning'])
    pa['diff_bucket'] = diff_bucket(pa['score_diff'])
    # the automatic runner: first batter of an extra half-inning, runner on second only, nobody out (2020 on)
    first_of_half = pa.groupby(['game_pk', 'inning', 'top'])['at_bat_number'].transform('min') == pa['at_bat_number']
    pa['ghost'] = (pa['season'] >= 2020) & (pa['inning'] >= 10) & first_of_half & (pa['bases'] == '010') & (pa['outs'] == 0)

    # 1. run expectancy by base-out state. Full innings only: walk-off halves are cut short.
    full = pa[~pa['walkoff_half']]
    rows = []
    for label, sel in (('all', full), ('innings 1-8', full[full['inning'] <= 8]), ('extra innings', pa[pa['inning'] >= 10])):
        for season, grp in list(sel.groupby('season')) + [('all', sel)]:
            t = grp.groupby(['outs', 'bases']).agg(n=('runs_rest', 'size'), runs=('runs_rest', 'sum'), scored=('scored', 'sum')).reset_index()
            t.insert(0, 'season', season); t.insert(0, 'scope', label)
            rows.append(t)
    pd.concat(rows).to_csv(dst / 're_matrix.csv', index=False)

    # 2. every bunt with a runner on and fewer than two outs
    sit = pa[(pa['bases'] != '000') & (pa['outs'] < 2)]
    cols = ['season', 'game_pk', 'inning', 'top', 'outs', 'bases', 'score_diff', 'events', 'bunt_in_play', 'bunt_strikeout', 'runs_on_play',
            'runs_rest', 'bat_won', 'walkoff_half', 'after_outs', 'after_bases', 'batter', 'bat_team', 'batter_class', 'batter_woba', 'ghost']
    sit[sit['bunt']][cols].to_csv(dst / 'bunts.csv', index=False)

    # 3. everyone who did not bunt (and never showed bunt) in the same situations, in groups
    keys = ['season', 'inning_bucket', 'diff_bucket', 'outs', 'bases', 'batter_class', 'ghost', 'top']
    swing = sit[~sit['bunt'] & ~sit['any_bunt_pitch']]
    base = swing.groupby(keys).agg(n=('runs_rest', 'size'), runs=('runs_rest', 'sum'), scored=('scored', 'sum'), won=('bat_won', 'sum')).reset_index()
    fullsw = swing[~swing['walkoff_half']].groupby(keys).agg(n_full=('runs_rest', 'size'), runs_full=('runs_rest', 'sum')).reset_index()
    base.merge(fullsw, on=keys, how='left').fillna({'n_full': 0, 'runs_full': 0}).to_csv(dst / 'baseline.csv', index=False)

    # 4. season totals
    pa['sac_situation'] = (pa['bases'] != '000') & (pa['outs'] < 2)
    games = pa.groupby('season')['game_pk'].nunique()
    s = pa.groupby('season').agg(pa=('events', 'size'), sac_situations=('sac_situation', 'sum'), bunts=('bunt', 'sum'),
                                 sac_bunts=('events', lambda e: int(e.isin(['sac_bunt', 'sac_bunt_double_play']).sum())),
                                 bunts_in_sac_situations=('bunt', lambda b: 0), runs=('runs_on_play', 'sum'))
    s['bunts_in_sac_situations'] = pa[pa['sac_situation']].groupby('season')['bunt'].sum()
    s['pitcher_bunts'] = pa[pa['sac_situation'] & pa['bunt'] & (pa['batter_class'] == 'pitcher')].groupby('season').size()
    s['pitcher_pa'] = pa[pa['batter_class'] == 'pitcher'].groupby('season').size()
    s['games'] = games
    s.fillna(0).astype(int).reset_index().to_csv(dst / 'seasons.csv', index=False)

    # 5. league event rates per season, for the run-scoring model
    ev = pa.groupby(['season', 'events']).size().unstack(fill_value=0)
    ev.reset_index().to_csv(dst / 'league_events.csv', index=False)

    (dst / 'manifest.json').write_text(json.dumps(dict(
        source='Baseball Savant Statcast search, via pybaseball.statcast',
        retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        seasons=sorted(int(x) for x in pa['season'].unique()), plate_appearances=int(len(pa)),
        bunts=int(pa['bunt'].sum()), games=int(pa['game_pk'].nunique())), indent=2) + '\n')
    print(pa.groupby('season').agg(pa=('events', 'size'), bunts=('bunt', 'sum')))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
