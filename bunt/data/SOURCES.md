# Data sources

## MLB play by play

`bunts.csv`, `baseline.csv`, `re_matrix.csv`, `seasons.csv`, `league_events.csv` and `manifest.json` are built by the workflow in `.github/workflows/bunt-data.yml`. It downloads every regular-season pitch from 2015 to 2026 from Baseball Savant (Statcast) through the `pybaseball` package, reduces it to one row per plate appearance (`pipeline/season.py`), and writes these tables (`pipeline/aggregate.py`). Retrieved 12 November 2026: 2,088,742 plate appearances in 27,622 games.

| File | What it holds |
| --- | --- |
| `bunts.csv` | Every bunt with a runner on and fewer than two outs: the situation, the result, the runs scored in the rest of the inning and whether the batting team won |
| `baseline.csv` | Every plate appearance in the same situations where the batter did not bunt or show bunt, grouped by season, inning, score, outs, bases, class of hitter and half-inning |
| `re_matrix.csv` | Plate appearances, runs and scoring innings for each of the 24 base and out states, by season |
| `seasons.csv` | Season totals, used to check the download against official counts |

The season plate-appearance and sacrifice-bunt counts match MLB's official totals exactly (for example 183,849 and 682 in 2026).

A hitter's class is his third of that season's hitters by wOBA, weighted by plate appearances. A batter counts as a pitcher if he threw at least 300 pitches that season.

## League totals

| File | Source |
| --- | --- |
| `raw/mlb_league_batting.csv` | MLB Stats API, team hitting totals summed to the league, 2005 to 2026 |
| `raw/npb_league_batting.csv` | npb.jp team batting tables (チーム打撃成績), summed to each league, 2005 to 2026 |
| `raw/npb_team_batting.csv` | npb.jp team batting tables, 2025 and 2026 |

`G` is team games, so a league's games played is half of it. `SH` is sacrifice bunts (犠打). Retrieved 12 November 2026 and checked against checksums computed at the source.
