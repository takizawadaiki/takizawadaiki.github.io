# Data sources

All files were retrieved on 11 November 2026. The raw files in `raw/` are kept exactly as collected, and `analysis.py` reads them directly.

| File | Source | What it holds |
| --- | --- | --- |
| `raw/cots_payrolls.txt` | Cot's Baseball Contracts, Baseball Prospectus (team pages, "payrolls" table) | Opening-day, year-end 40-man and competitive balance tax payrolls for all 30 MLB teams, 2000 to 2026, in $ millions. Tax payrolls start in 2012. |
| `raw/mlb_standings.txt` | MLB Stats API (`/api/v1/standings`, `/api/v1/schedule/postseason`) | Wins, losses, playoff appearance and World Series winner, 2000 to 2026. |
| `raw/nba_standings.txt` | NBA Stats (`leaguestandingsv3`) | Wins and losses, 1999-00 to 2025-26. Seasons are labelled by the year they start. |
| `raw/nhl_standings.txt` | NHL Stats API (`/stats/rest/en/team/summary`) | Wins, games and points, 1995-96 to 2025-26. There is no 2004-05 season. |
| `raw/nfl_games.csv` | nflverse `nfldata` (`games.csv`) | Regular-season scores, 1999 to 2025. |

The league's offer (cap of $258.2 million, floor of $180.2 million, the teams affected and the totals) comes from the Associated Press report of 4 November 2026.

## Notes

- Payroll figures are unofficial. Cot's compiles them from published reports, and the 2026 year-end and tax payrolls are projections as of 1 November 2026.
- 2020 payrolls in the opening-day and year-end columns are prorated for the 60-game season. The analysis divides each team's payroll by the league average for that season, so this does not affect the results.
- Each raw file was checked against a checksum computed at the source when it was collected.
- Line formats: payrolls are `team=year,opening_day,year_end,tax;...`; MLB is `season teamId-wins-losses-playoffs-champion,...`; NBA is `season teamId.wins.losses,...` (team ID minus 1610612700); NHL is `season teamId.wins.games.points,...`.
