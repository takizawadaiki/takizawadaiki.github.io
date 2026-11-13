# Data sources

Everything here comes from the NHL's public web API and is built by the workflow in `.github/workflows/faceoff-data.yml`, which runs `pipeline/season.py` once per season. Retrieved 12 November 2026: 633,472 faceoffs in 11,052 regular-season games, 2017–18 to 2025–26. Files are named by the year a season started.

| File | Source | What it holds |
| --- | --- | --- |
| `faceoffs_{year}.csv.gz` | `api-web.nhle.com/v1/gamecenter/{game}/play-by-play` | One row per faceoff: game, period, time, location on the ice, which end the home team defends, the teams, the winning and losing player, the skaters on the ice, and each team's shots on goal and goals in the next 30 seconds or until the next faceoff |
| `players_{year}.csv` | The same play-by-play files | Names and positions of the players who took faceoffs |
| `bios_{year}.csv` | `api.nhle.com/stats/rest/en/skater/bios` | Listed height, weight, birth date, shooting hand, position and draft details |

`situation` is the league's four-digit code: away goalie, away skaters, home skaters, home goalie. Coordinates are in feet from centre ice. `sog_w` and `goals_w` belong to the team that won the faceoff, `sog_l` and `goals_l` to the team that lost it.

Heights and weights are the league's listed figures and are taken from each player's most recent season.
