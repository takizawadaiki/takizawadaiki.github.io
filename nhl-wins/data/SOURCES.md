# Data sources

Both come from the NHL's public APIs and are built by the workflow in `.github/workflows/nhl-wins-data.yml`. Retrieved 13 November 2026.

| File | Source | What it holds |
| --- | --- | --- |
| `games_{year}.csv` | `api-web.nhle.com/v1/gamecenter/{game}/play-by-play`, reduced by `pipeline/season.py` | One row per regular-season game, 2010–11 to 2025–26 (19,152 games). Named by the year the season started |
| `team_seasons.csv` | `api.nhle.com/stats/rest/en/team/summary`, regular season and playoffs, joined by `pipeline/teams.py` | One row per team and season since 1917–18: record, goals and shots per game, and playoff games, wins and losses |

Columns in the game files, each for `home_` and `away_`:

- `goals`, `sog`: goals and shots on goal in regulation and overtime. Shootouts are left out.
- `sog_p1`, `sog_p2`, `sog_p3`, `sog_ot`: shots on goal by period.
- `sog_tied`, `sog_lead`, `sog_trail`: shots on goal by the score at the moment of the shot, from the shooting team's side. A goal counts as a shot at the score before it.
- `goals_p1`, `goals_p2`, `goals_p3`: goals by period.

`winner` is the team that won the game, including shootouts. `decided_in` is REG, OT or SO. `secs_tied`, `secs_home_lead` and `secs_away_lead` are seconds of play in each score state.
