# The Bench Dividend — revised research draft

This is a local revision of the public page, not a deployed update. Open `bench-research.html` in a browser, or serve this directory with `python3 -m http.server 8765`. Chart.js 4.4.0 is included locally; its license header is retained. Google Fonts needs an internet connection; system fonts provide fallbacks.

## What changed

- Explained starters, substitutes, regular season, playoffs and bench scoring for readers without basketball knowledge.
- Distinguished usage, quality, star dependence and team success.
- Recalculated the embedded chart values and added uncertainty, within-season adjustment, rank correlation, leave-one-season-out and leave-one-record-out checks.
- Corrected the displayed season correlations and Minnesota card; removed untested causal explanations.
- Added a specified follow-up analysis connecting supporting-unit quality to playoff team net rating, plus a larger-sample study of star concentration and roster continuity.
- Added a management conclusion, cross-industry measurement examples and a practical development pilot. Corporate implications are explicitly hypotheses rather than findings from corporate data.

## Data status — resolve before presenting this as validated research

The numerical input is copied from the public page retrieved on September 16, 2026:
https://takizawadaiki.github.io/bench-research.html

The public repository listing contained three HTML files and no source dataset or notebook. The chart arrays contain 48 rounded team-season records. The extraction and aggregation described in the original article could not be reproduced from raw NBA records.

1. The pooled chart correlation is 0.328728, p = 0.022533, instead of the original headline 0.300, p = 0.038.
2. Seasonal correlations are 0.014712, 0.314695 and 0.294510, not the original bars 0.285, 0.316 and 0.156.
3. The 2023–24 chart includes Golden State and omits Phoenix. Golden State was eliminated in the play-in; Phoenix participated in the playoffs. Source: https://cdn-uat.nba.com/news/2024-nba-playoffs-schedule
4. Minnesota 2025–26 has 13.80 regular-season minutes in the array, not the 10.6 in the original card.
5. Complete season coverage, including 2025–26, has not been verified. An extraction timestamp is needed.

The revised page retains all original chart records for an auditable provisional reanalysis. It does not silently replace Golden State with Phoenix or claim the remaining records have been verified. Do not turn these calculations into a finalized basketball result without reconciling the input.

## Reproduce

With Python 3.9 or later:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python reanalysis.py
```

Inputs: `chart-values.json`. Output: `audit-results.json`.

`reg` and `playoff` preserve the website's reported per-player minutes and points; `season` and `team` identify the displayed record. These are website chart values, not an NBA raw-data export.

Pearson p-values use SciPy's conventional two-sided test. Confidence intervals use the default Fisher transformation. Spearman p-values are the conventional approximation. The partial correlation removes season means from both variables; its t-test uses 44 degrees of freedom. The reproduction script independently verifies this p-value against OLS with season indicators. None of these calculations accounts for repeated-team dependence, resolves sample validity, establishes causal effects or measures team success. All robustness analyses are post hoc exploratory checks.

## Data needed for the next empirical analysis

Provide the original notebook and raw export first, including query parameters, retrieval dates, season type, player/team IDs, traded-player handling, games played, weighting and missing-value rules. Rebuild the verified playoff sample before attaching new predictors.

For the proposed team-success analysis, collect regular-season and playoff possessions, points for/against, regular-season team strength, and regular-season lineup possessions with game-specific starting status. For extensions, collect individual scoring shares, roster membership across seasons, and payroll. Define exclusion thresholds and model choices before inspecting outcome associations. Use more seasons if possible and an inference method that addresses repeated teams; adding many predictors to 48 records is not justified.

## Delivery

The HTML preserves the existing editorial design. For a future site update, place the HTML and companion downloads in the same directory. The live GitHub Pages site has not been changed. The revised page explicitly labels numerical results as provisional; it is ready for review, not for a claim of validated NBA research.
