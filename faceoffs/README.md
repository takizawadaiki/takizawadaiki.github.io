# What makes an NHL player elite at faceoffs?

Live page: https://takizawadaiki.github.io/faceoffs/

The question: what separates the best faceoff men from the rest, and could a very small player with great hands and timing hold a roster spot as a designated faceoff man?

## Findings

- **Faceoff skill is real.** Ratings run from about 35% to 60% against an average opponent. Ratings from odd-numbered games correlate 0.87 with ratings from even-numbered games, and one season predicts the next at about 0.72.
- **Size explains about a tenth of it.** Height alone has no clear link with skill. Among centres each extra 10 lb goes with about 1 more point, and at the same weight a taller centre is slightly worse. Height and weight together explain 11% of the differences among centres.
- **Situation matters.** A player on the side of the ice that matches his shooting hand gains 2.5 points. A power play adds 2.4, home ice 1.0, and the zone almost nothing.
- **Players improve into their thirties.** The same player wins about 6 points fewer draws at 22 than at his best, which points to a learned skill more than raw reflexes.
- **A win is worth little.** Winning an end-zone draw instead of losing it is worth about 0.021 goals in the next 30 seconds, and a neutral-zone draw about 0.006. A 58% specialist taking 10 draws a game adds about 1.2 goals a season, a fifth of one win.

So a small player could be an elite faceoff man, but the job alone is not worth a roster spot.

## What is here

| Path | What it is |
| --- | --- |
| `pipeline/season.py` | Downloads one season of NHL play-by-play and keeps the faceoffs, with shots and goals in the following 30 seconds |
| `data/` | The faceoffs, player names and player records for nine seasons (see `data/SOURCES.md`) |
| `analysis.py` | The rating model, the size and age analysis and the value of a win; writes `results/results.json` |
| `tests/test_analysis.py` | Ten tests of the geometry, the model and the value calculation |
| `index.html` | The page, which reads `results/results.json` |

## Method

Each faceoff is treated as a contest between two players. A Bradley–Terry model (logistic regression on the winner's terms minus the loser's) estimates a skill for each of 1,255 players together with the effects of home ice, zone, side of the ice, man advantage and age. Player skills are shrunk toward the average, with the strength of the shrinkage chosen by predicting a held-out fifth of the games. Ratings are reported for the 348 players with at least 500 draws.

The size analysis regresses each player's age-adjusted rating on height and weight, weighted by faceoffs taken. The value of a win compares shots on goal and goals in the 30 seconds after draws won and lost in the same zone.

## Limits

- Reaction time and hand speed are not measured anywhere public. The analysis shows how much skill is left unexplained by size, age and handedness; it cannot say how much of that is reflexes.
- Coaches choose who takes faceoffs, so the sample is players who were good enough to keep the job. The lightest has a listed weight of 165 lb.
- The 30-second window misses slower effects of possession, and every draw in a zone is treated alike whatever the score.
- A faceoff is credited to one player although wingers often win the loose puck.

## Run it

```
pip install numpy scipy pytest
python analysis.py
python -m pytest tests
```

The data is refreshed by the workflow in `.github/workflows/faceoff-data.yml`.
