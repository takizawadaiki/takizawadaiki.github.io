# Shots, offence or defence: what wins in the NHL?

Live page: https://takizawadaiki.github.io/nhl-wins/

Two questions: does getting more shots on goal than the other team win games, and do high-scoring teams or low-scoring-against teams win the Stanley Cup?

## Findings

**Shots**

- In one game, more shots says little. The team that outshot its opponent won 51.9% of 18,448 games from 2010–11 to 2025–26. The home team won 54.1%.
- The reason is the score. Teams take 32.3 shots per 60 minutes when trailing and 27.2 when leading, so the losing side's shot total is inflated.
- In games that were scoreless after one period, where the score could not have shaped the shot count, the team that outshot its opponent in that period won 51.7%. Each extra shot is worth about 0.4 points of win probability.
- Over a season shots matter. Shot share correlates 0.62 with points, and one extra point of shot share is worth about 3.5 standings points. Shot share also carries over from the first half of a season to the second (0.71) much better than points do (0.50).

**Offence or defence**

- The 46 champions since 1980 ranked 6.7th in goals scored and 6.6th in goals allowed on average. 26 had a top-five offence and 23 a top-five defence.
- Among playoff teams, one standard deviation of offence multiplies the odds of winning the Cup by 2.5, and one of defence also by 2.5.
- Defence has a small edge in playoff wins and in the salary cap era, and offence before it. None of those gaps is outside the margin of error.

## What is here

| Path | What it is |
| --- | --- |
| `pipeline/season.py` | Downloads one season of play-by-play and reduces each game to shot and goal counts |
| `pipeline/teams.py` | Downloads every team season with its playoff record |
| `data/` | The game and team-season files (see `data/SOURCES.md`) |
| `analysis.py` | All the calculations; writes `results/results.json` |
| `tests/test_analysis.py` | Nine tests |
| `index.html` | The page, which reads `results/results.json` |

## Limits

- A shot on goal is not a scoring chance; shot quality is not measured.
- The scoreless-first-period test covers about a fifth of games and one period of shots, so it is noisy.
- There are only 46 champions, so only a large gap between offence and defence would show up clearly.
- Goals allowed mixes team defence with goaltending.

## Run it

```
pip install numpy pytest requests
python analysis.py
python -m pytest tests
```

The data is refreshed by the workflow in `.github/workflows/nhl-wins-data.yml`.
