# The Bench Dividend — research page and data

`bench-research.html` is the article, `dashboard.html` the interactive view, and the homepage card and charts read the same JSON files. To view locally, serve this directory with `python3 -m http.server 8765`. Chart.js 4.4.0 is included locally; its license header is retained.

## What changed

- Explained starters, substitutes, regular season, playoffs and bench scoring for readers without basketball knowledge.
- Distinguished usage, quality, star dependence and team success.
- Rebuilt the team values from NBA Stats and added uncertainty, within-season adjustment, rank correlation, leave-one-season-out and leave-one-record-out checks.
- Corrected the displayed season correlations and Minnesota card; removed untested causal explanations.
- Added a specified follow-up analysis connecting supporting-unit quality to playoff team net rating, plus a larger-sample study of star concentration and roster continuity.
- Added a management conclusion, cross-industry measurement examples and a practical development pilot. Corporate implications are explicitly hypotheses rather than findings from corporate data.

## Data status — rebuilt from NBA Stats on 11 November 2026

The 48 team-season values in `chart-values.json` come from the NBA Stats `leaguedashplayerstats` endpoint (bench split, per-game averages, regular season and playoffs, 2023–24 to 2025–26). `data-provenance.json` records the retrieval time, parameters, how the values were computed and every change from the previous file. `bench-team-values.json` holds the team averages under all four definitions tested.

What the rebuild showed:

1. The pooled correlation is 0.300, p = 0.038, 95% interval 0.017 to 0.538. That reproduces the headline the original article reported (0.300, p = 0.038).
2. The chart values the page displayed before the rebuild did not match the source: they gave r = 0.329, included Golden State in place of Phoenix for 2023–24, and differed by more than 0.05 for 21 other team-seasons, mostly in regular-season minutes.
3. Seasonal correlations are 0.434, 0.316 and -0.078. The association is not stable across seasons, and the season-adjusted correlation is 0.225 (p = 0.132).
4. The size depends on how the bench is averaged: primary (unweighted, all bench players) 0.300; weighted by games played 0.408; bench players with at least 10 regular-season games 0.310; bench players on the playoff roster only 0.288.

Limits that remain: a player with one bench appearance counts as much as a regular reserve under the primary definition; traded players appear once, under their final team; repeated teams are treated as independent; three seasons is a small sample.

## Rebuilding the data from NBA Stats

`rebuild_data.py` reproduces the article's described method (nba_api `LeagueDashPlayerStats`, `starter_bench_nullable='Bench'`, per-player averages, the 16 playoff teams per season) and rewrites `chart-values.json`. It also writes `data-provenance.json` with the retrieval time, parameters, a list of what changed from the previous file, and the pooled correlation under other reasonable definitions of "bench average".

NBA Stats refuses connections from cloud servers. On 11 November 2026 a run on GitHub's servers timed out, and a run in Google Colab produced no data either. The rebuild that is published was made by sending the same requests through the NBA.com stats site in a desktop browser and computing the team averages there with a direct port of `aggregate()`; `data-provenance.json` describes the checks. From a home connection the script itself should work:

```sh
pip install -r requirements-rebuild.txt
python rebuild_data.py            # chart-values.json + data-provenance.json
python reanalysis.py              # audit-results.json
git add chart-values.json data-provenance.json audit-results.json && git commit -m "Rebuild data from NBA Stats" && git push
```

`python rebuild_data.py --selftest` checks the aggregation logic offline. After a rebuild, `dashboard.html` and the homepage card and charts update themselves from the JSON files. `bench-research.html` contains typed-in numbers and embedded chart data, so it needs a manual pass. `notebooks/rebuild_bench_data.ipynb` runs the same steps in Colab for when NBA Stats is reachable from there.

## Reproduce

With Python 3.9 or later:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python reanalysis.py
```

Inputs: `chart-values.json`. Output: `audit-results.json`.

`reg` is the average regular-season minutes per bench player and `playoff` the average playoff points per bench player, both to four decimals; `season` and `team` identify the record.

Pearson p-values use SciPy's conventional two-sided test. Confidence intervals use the default Fisher transformation. Spearman p-values are the conventional approximation. The partial correlation removes season means from both variables; its t-test uses 44 degrees of freedom. The reproduction script independently verifies this p-value against OLS with season indicators. None of these calculations accounts for repeated-team dependence, establishes causal effects or measures team success. All robustness analyses are post hoc exploratory checks.

## Data needed for the next empirical analysis

For the proposed team-success analysis, collect regular-season and playoff possessions, points for/against, regular-season team strength, and regular-season lineup possessions with game-specific starting status. For extensions, collect individual scoring shares, roster membership across seasons, and payroll. Define exclusion thresholds and model choices before inspecting outcome associations. Use more seasons if possible and an inference method that addresses repeated teams; adding many predictors to 48 records is not justified.
