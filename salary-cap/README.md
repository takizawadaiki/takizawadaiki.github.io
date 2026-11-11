# Should MLB have a salary cap?

An interactive test of the cap-and-floor offer MLB made to its players in November 2026, before the labour deal expires on 1 December.

**Live page:** https://takizawadaiki.github.io/salary-cap/

## The question

The league offered a hard cap of $258.2 million and a floor of $180.2 million from 2028. The players' union opposes any cap. Each side makes claims that can be checked with public data:

1. **Owners:** teams that spend more win more, so small markets cannot compete.
2. **Players:** a cap would not fix competitive balance.

## What the page does

- **Simulator.** Set any cap and floor and see which teams must cut, which must spend more, and what happens to total player pay. At the league's own numbers it flags the same 8 and 12 teams the Associated Press reported.
- **Money and wins.** Payroll against wins for every team season since 2000 (810 in total).
- **Other leagues.** Two balance measures for MLB next to the NBA, NFL and NHL, which all limit payrolls, plus a before-and-after look at the NHL's 2005 cap.
- **Verdict.** What the evidence supports for each side, and what it cannot settle.

## Findings

- Payroll and winning are linked (correlation 0.41), and payroll lines up with about 17% of the differences in team records. The five biggest spenders average 89 wins and the five smallest 76.
- No team in the bottom ten in payroll has won the World Series since 2000. The 2026 title went to Milwaukee, ranked 19th.
- The link is no stronger now than in the 2000s, and the gap between the top five and bottom five payrolls (3.5 times in 2026) matches 2000, though it has grown since 2018.
- The NBA has a cap and is the least even of the four leagues on both measures. MLB's year-to-year carryover (0.55) is close to the capped NHL's (0.53). The NFL is the most even.
- The NHL became slightly more even after its 2005 cap, but the intervals overlap and other rules changed at the same time.
- On 2026 payrolls, the November offer would force 12 teams up to the floor ($661 million) and 8 down to the cap ($511 million), a net gain for players of $150 million if nothing else changed. The May offer would have been a net cut of $73 million.

## Limits

- The simulator is static. It does not model how teams would react.
- Payroll and wins move together, but winning also raises revenue and then payroll. The estimated win changes are what the historical link implies, not forecasts.
- Leagues differ in more than their cap rules.
- The revenue split, which decides whether players gain or lose overall, cannot be tested because team revenues are not public.

## Run it

Python 3.9 or later, standard library only.

```
python analysis.py                    # writes data/mlb_team_seasons.csv and results/results.json
python -m unittest discover tests     # 15 checks
```

Sources are listed in [data/SOURCES.md](data/SOURCES.md).
