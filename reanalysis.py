"""Reproduce the provisional audit. No NBA data is downloaded or validated.
Run: python reanalysis.py [chart-values.json] [audit-results.json]
Requires numpy and scipy; see requirements.txt.
"""
import json
from pathlib import Path
import sys
import numpy as np
from scipy import stats


def result(rows):
    x = np.array([r['reg'] for r in rows])
    y = np.array([r['playoff'] for r in rows])
    pearson = stats.pearsonr(x, y)
    ci = pearson.confidence_interval()
    spearman = stats.spearmanr(x, y)
    return dict(n=len(rows), r=float(pearson.statistic), p=float(pearson.pvalue),
                ci=[float(ci.low), float(ci.high)], r2=float(pearson.statistic**2),
                spearman=float(spearman.statistic), spearman_p=float(spearman.pvalue))


def analyze(rows):
    assert len(rows) == 48, 'This audit expects the original 48 website records.'
    assert len({(r['team'], r['season']) for r in rows}) == len(rows)
    assert all(np.isfinite([r['reg'], r['playoff']]).all() for r in rows)
    seasons = list(dict.fromkeys(r['season'] for r in rows))
    groups = {season: [r for r in rows if r['season'] == season] for season in seasons}
    assert len(groups) == 3 and all(len(g) == 16 for g in groups.values())
    results = {season: result(group) for season, group in groups.items()}
    results['combined'] = result(rows)
    # Remove season-specific means from both variables. Two season controls
    # plus an intercept imply df = n - 2 controls - 2 for partial correlation.
    x, y = [], []
    for group in groups.values():
        gx = np.array([r['reg'] for r in group])
        gy = np.array([r['playoff'] for r in group])
        x.extend(gx - gx.mean())
        y.extend(gy - gy.mean())
    r = float(stats.pearsonr(x, y).statistic)
    df = len(rows) - (len(groups) - 1) - 2
    results['season_adjusted'] = dict(r=r, p=float(2 * stats.t.sf(abs(r * np.sqrt(df / (1-r*r))), df)), df=df)
    results['leave_one_season_out'] = {
        season: result([r for r in rows if r['season'] != season]) for season in seasons
    }
    leave_one_out = [result(rows[:i] + rows[i+1:])['r'] for i in range(len(rows))]
    results['leave_one_row_out_r_range'] = [min(leave_one_out), max(leave_one_out)]
    # Independently check the partial-correlation test against OLS with season controls.
    xv = np.array([r['reg'] for r in rows])
    yv = np.array([r['playoff'] for r in rows])
    design = np.column_stack([np.ones(len(rows)), xv] + [
        np.array([r['season'] == season for r in rows], dtype=float) for season in seasons[1:]
    ])
    beta = np.linalg.lstsq(design, yv, rcond=None)[0]
    residual = yv - design @ beta
    se = np.sqrt((residual @ residual / df) * np.linalg.inv(design.T @ design)[1, 1])
    ols_p = float(2 * stats.t.sf(abs(beta[1] / se), df))
    assert np.isclose(ols_p, results['season_adjusted']['p'], atol=1e-10)
    return results


if __name__ == '__main__':
    base = Path(__file__).resolve().parent
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else base / 'chart-values.json'
    destination = Path(sys.argv[2]) if len(sys.argv) > 2 else base / 'audit-results.json'
    results = analyze(json.loads(source.read_text()))
    destination.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
