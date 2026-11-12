# What is a sacrifice bunt worth?

Japanese teams bunt a runner over several times as often as MLB teams. This project measures what the play is worth and asks whether Japan's lower-scoring game justifies the difference.

**Live page:** https://takizawadaiki.github.io/bunt/

## Three kinds of evidence

1. **League totals, 2005 to 2026.** How often each league bunts.
2. **Every MLB plate appearance, 2015 to 2026.** 2,088,742 plate appearances from Statcast, including 13,436 bunts with a runner on and fewer than two outs. What happened after real bunts is compared with what happened when the same class of hitter swung away in the same situation.
3. **A run-scoring model.** NPB publishes no play-by-play data, so `model.py` builds the value of all 24 base and out situations from league totals alone: an inning is a chain of plate appearances with the league's own rates of walks, hits, strikeouts and outs. It also gives the full distribution of runs, which turns into win probability by inning and score.

The model is checked against the MLB play-by-play before it is used for Japan. Weighted by how often each situation occurs, it is off by 0.024 runs and 1.3 percentage points on the chance of scoring.

## Findings

- In 2026 NPB teams laid down 0.51 sacrifice bunts a game and MLB teams 0.14, a ratio of 3.6.
- With a runner on first and nobody out, a bunt by an average hitter costs about 0.08 runs in MLB and raises the chance of scoring at least once by about one percentage point.
- A bunt is not a guaranteed out. One bunt in five by a position player ends with everyone safe.
- Real results agree. Weak hitters who bunted scored as many runs as weak hitters who swung (0.81 against 0.82) and scored at least once more often (42% against 39%). Middle hitters lost 0.08 runs.
- The value is in late, tied games. In the bottom of the ninth of a tie game, a bunt with a runner on second adds about 2.8 points of win probability. In the first inning it costs 0.7, and trailing by a run in the ninth it costs 1.9.
- Japan's lower scoring (0.38 runs an inning against 0.50) cuts the cost of the same bunt to about 0.05 runs. All of a team's sacrifices come to roughly 4 runs a season, under half a win.
- The run environment explains a small part of the gap between the leagues. Most of it looks like style.

## Limits

- Teams choose when to bunt, so real bunts happened in conditions the team liked.
- Japan's results are modelled, and assume Japanese bunters get the same results as MLB bunters and that runners advance on hits at MLB rates. The page lets the reader change the sacrifice success rate.
- The win-probability figures assume league-average scoring in later innings and treat a tie after nine innings as a coin flip.
- A hitter is described by one number. Speed, bunting skill, the pitcher and the defence are not modelled.

## Run it

```
python analysis.py                       # standard library only; writes results/results.json
python -m unittest tests.test_model      # 15 checks on the model
python -m unittest tests.test_pipeline   # 7 checks on the data reduction (needs pandas and pyarrow)
```

To rebuild the play-by-play tables, run the "Bunt data" workflow from the Actions tab. Sources are in [data/SOURCES.md](data/SOURCES.md).
