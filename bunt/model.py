"""A run-scoring model built from league batting totals.

Play-by-play data is public for MLB but not for Japan's NPB, so the comparison between the two
leagues needs a model that only uses the totals both leagues publish: hits, walks, strikeouts and so on.

An inning is treated as a chain of plate appearances. Each one ends in a walk, single, double, triple,
home run, strikeout or other out, with the league's own frequencies, and runners move by fixed rules.
From that the model gives, for each of the 24 base-out states:

    runs      the average number of runs scored from that state to the end of the inning
    p_score   the chance that at least one run scores

The double-play and sacrifice-fly rates are set so the model reproduces each league's own totals.
The other running rules are fixed assumptions (ADVANCE below), the same for both leagues.

Standard library only.
"""
from __future__ import annotations

from itertools import product

BASES = [''.join(b) for b in product('01', repeat=3)]       # '100' = runner on first only
STATES = [(o, b) for o in range(3) for b in BASES]
EVENTS = ('bb', '1b', '2b', '3b', 'hr', 'k', 'out')

# Share of the time a runner takes the extra base. Typical MLB values; assumed equal in NPB.
ADVANCE = dict(
    single_second_scores=0.60,    # runner on second scores on a single
    single_first_to_third=0.28,   # runner on first reaches third on a single
    double_first_scores=0.42,     # runner on first scores on a double
    out_second_to_third=0.22,     # runner on second moves up on an out in play (fewer than two outs)
    out_first_to_second=0.12,     # runner on first moves up on an out in play that is not a double play
    reach_on_error=0.012,         # share of plate appearances where the batter reaches on an error
)


def league_rates(t: dict) -> dict:
    """Per-plate-appearance outcome rates from season totals. Bunts and intentional walks are left out."""
    pa = t['AB'] + t['BB'] - t['IBB'] + t['HBP'] + t['SF']
    r = {'bb': (t['BB'] - t['IBB'] + t['HBP']) / pa, '1b': (t['H'] - t['2B'] - t['3B'] - t['HR']) / pa, '2b': t['2B'] / pa,
         '3b': t['3B'] / pa, 'hr': t['HR'] / pa, 'k': t['SO'] / pa}
    r['out'] = 1 - sum(r.values())
    return r


def scale_batter(rates: dict, factor: float) -> dict:
    """A weaker or stronger hitter: every way of reaching base is scaled by `factor`, and the difference
    goes to strikeouts and other outs in their existing proportion."""
    r = dict(rates)
    reach = ('bb', '1b', '2b', '3b', 'hr')
    for k in reach:
        r[k] = rates[k] * factor
    left = 1 - sum(r[k] for k in reach)
    outs = rates['k'] + rates['out']
    r['k'], r['out'] = left * rates['k'] / outs, left * rates['out'] / outs
    return r


def transitions(outs: int, bases: str, rates: dict, dp: float, sf: float, adv: dict = ADVANCE):
    """Every way one plate appearance can turn out: a list of (probability, runs, new outs, new bases)."""
    b1, b2, b3 = (c == '1' for c in bases)
    res = []

    def add(p, runs, o, nb):
        if p > 0:
            res.append((p, runs, o, ''.join('1' if x else '0' for x in nb)))

    # walk or hit by pitch: only forced runners move
    add(rates['bb'], int(b1 and b2 and b3), outs, (True, b1 or b2, b3 or (b1 and b2)))

    def single(p):
        for p2, second_scores in ((adv['single_second_scores'], True), (1 - adv['single_second_scores'], False)) if b2 else ((1, False),):
            for p1, first_to_third in ((adv['single_first_to_third'], True), (1 - adv['single_first_to_third'], False)) if b1 else ((1, False),):
                runs = int(b3) + int(b2 and second_scores)
                third = (b2 and not second_scores) or (b1 and first_to_third and not (b2 and not second_scores))
                second = b1 and not (first_to_third and not (b2 and not second_scores))
                add(p * p2 * p1, runs, outs, (True, second, third))
    roe = adv['reach_on_error']
    single(rates['1b'] + roe)                     # an error is treated like a single

    for p1, first_scores in ((adv['double_first_scores'], True), (1 - adv['double_first_scores'], False)) if b1 else ((1, False),):
        add(rates['2b'] * p1, int(b3) + int(b2) + int(b1 and first_scores), outs, (False, True, b1 and not first_scores))
    add(rates['3b'], int(b1) + int(b2) + int(b3), outs, (False, False, True))
    add(rates['hr'], 1 + int(b1) + int(b2) + int(b3), outs, (False, False, False))
    add(rates['k'], 0, outs + 1, (b1, b2, b3))

    p_out = rates['out'] - roe
    if outs == 2:
        add(p_out, 0, 3, (False, False, False))
    else:
        p_dp = dp if b1 else 0.0
        # double play: batter and the runner from first are out; other runners move up one base if the inning continues
        if p_dp:
            if outs == 1:
                add(p_out * p_dp, 0, 3, (False, False, False))
            else:
                add(p_out * p_dp, int(b3), 2, (False, False, b2))
        rest = p_out * (1 - p_dp)
        p_sf = sf if b3 else 0.0
        # sacrifice fly: runner on third scores, the others hold
        if p_sf:
            add(rest * p_sf, 1, outs + 1, (b1, b2, False))
        rest *= (1 - p_sf)
        for p2, up2 in ((adv['out_second_to_third'], True), (1 - adv['out_second_to_third'], False)) if (b2 and not b3) else ((1, False),):
            for p1, up1 in ((adv['out_first_to_second'], True), (1 - adv['out_first_to_second'], False)) if (b1 and not b2) else ((1, False),):
                add(rest * p2 * p1, 0, outs + 1, (b1 and not up1, (b2 and not up2) or (b1 and up1), b3 or (b2 and up2)))
    return res


def solve(rates: dict, dp: float, sf: float, adv: dict = ADVANCE):
    """Expected runs and chance of scoring from each state, plus expected visits to each state per inning."""
    runs = {s: 0.0 for s in STATES}
    p0 = {s: 1.0 for s in STATES}            # chance of NOT scoring
    trans = {s: transitions(s[0], s[1], rates, dp, sf, adv) for s in STATES}
    for _ in range(400):                       # the chain always moves toward three outs, so this converges fast
        new_runs, new_p0 = {}, {}
        for s in STATES:
            er, ez = 0.0, 0.0
            for p, r, o, b in trans[s]:
                er += p * (r + (runs[(o, b)] if o < 3 else 0.0))
                ez += p * (0.0 if r > 0 else (p0[(o, b)] if o < 3 else 1.0))
            new_runs[s], new_p0[s] = er, ez
        if max(abs(new_runs[s] - runs[s]) for s in STATES) < 1e-12:
            runs, p0 = new_runs, new_p0
            break
        runs, p0 = new_runs, new_p0
    visits = {s: 0.0 for s in STATES}
    visits[(0, '000')] = 1.0
    for _ in range(60):
        nxt = {s: 0.0 for s in STATES}
        nxt[(0, '000')] = 1.0
        for s in STATES:
            for p, r, o, b in trans[s]:
                if o < 3:
                    nxt[(o, b)] += visits[s] * p
        visits = nxt
    return runs, {s: 1 - p0[s] for s in STATES}, visits, trans


def calibrate(totals: dict, adv: dict = ADVANCE):
    """Find the double-play and sacrifice-fly rates that reproduce the league's own totals."""
    rates = league_rates(totals)
    innings = (totals['AB'] - totals['H'] + totals['GDP'] + totals['SF'] + totals['SH'] + totals['CS']) / 3
    target_dp, target_sf = totals['GDP'] / innings, totals['SF'] / innings
    dp, sf = 0.12, 0.20
    for _ in range(40):
        _, _, visits, _ = solve(rates, dp, sf, adv)
        p_out = rates['out'] - adv['reach_on_error']
        dp_opp = sum(v for (o, b), v in visits.items() if o < 2 and b[0] == '1') * p_out
        sf_opp = sum(v * (1 - (dp if b[0] == '1' else 0)) for (o, b), v in visits.items() if o < 2 and b[2] == '1') * p_out
        dp, sf = min(0.6, target_dp / dp_opp), min(0.9, target_sf / sf_opp)
    runs, score, visits, _ = solve(rates, dp, sf, adv)
    return dict(rates=rates, dp=dp, sf=sf, runs=runs, p_score=score, innings=innings,
                model_runs_per_inning=runs[(0, '000')], actual_runs_per_inning=totals['R'] / innings)


def batter_then_league(outs: int, bases: str, batter_rates: dict, league: dict, adv: dict = ADVANCE):
    """Swing away: this batter hits with his own rates, and everyone after him is a league-average hitter."""
    er, pz = 0.0, 0.0
    for p, r, o, b in transitions(outs, bases, batter_rates, league['dp'], league['sf'], adv):
        er += p * (r + (league['runs'][(o, b)] if o < 3 else 0.0))
        pz += p * (0.0 if r > 0 else ((1 - league['p_score'][(o, b)]) if o < 3 else 1.0))
    return er, 1 - pz


def bunt_value(outs: int, bases: str, outcome: dict, league: dict):
    """Bunt: `outcome` gives the chance of each result. Returns (expected runs, chance of scoring).

        sacrifice  batter out, every runner moves up one base
        fail       batter out, runners stay
        lead_out   the lead runner is thrown out, batter safe at first, other runners move up
        safe       batter safe at first and every runner moves up (bunt hit or error)
        double     two outs: the batter and the lead runner
    """
    er, pz = 0.0, 0.0
    for kind, p in outcome.items():
        if p <= 0:
            continue
        r, o, nb = bunt_after(outs, bases, kind)
        key = (o, nb)
        er += p * (r + (league['runs'][key] if o < 3 else 0.0))
        pz += p * (0.0 if r > 0 else ((1 - league['p_score'][key]) if o < 3 else 1.0))
    return er, 1 - pz


def bunt_after(outs: int, bases: str, kind: str):
    """Where one bunt result leaves the inning: (runs scored, outs, bases)."""
    b1, b2, b3 = (c == '1' for c in bases)
    lead = 3 if b3 else 2 if b2 else 1
    if kind == 'sacrifice':
        r, o, nb = int(b3), outs + 1, (False, b1, b2)
    elif kind == 'fail':
        r, o, nb = 0, outs + 1, (b1, b2, b3)
    elif kind == 'safe':
        r, o, nb = int(b3), outs, (True, b1, b2)
    elif kind == 'lead_out':     # the lead runner is erased, the batter takes first, trailing runners move up
        r, o, nb = 0, outs + 1, (True, b1 and lead != 1, b2 and lead != 2)
    elif kind == 'double':
        r, o, nb = 0, outs + 2, (False, b1 and lead != 1, b2 and lead != 2)
    else:
        raise KeyError(kind)
    return r, o, ''.join('1' if x else '0' for x in nb)


# ---------- win probability ----------

MAX_RUNS = 10     # runs in one half-inning; anything above is counted as 10
MAX_LEAD = 12     # leads beyond this are treated as decided


def shift(dist, runs):
    """The same distribution with `runs` already scored."""
    out = [0.0] * (MAX_RUNS + 1)
    for k, p in enumerate(dist):
        out[min(MAX_RUNS, k + runs)] += p
    return out


def run_distributions(rates: dict, dp: float, sf: float, adv: dict = ADVANCE):
    """For each state, the chance of scoring exactly 0, 1, 2 ... more runs before the inning ends."""
    zero = [1.0] + [0.0] * MAX_RUNS
    dist = {s: list(zero) for s in STATES}
    trans = {s: transitions(s[0], s[1], rates, dp, sf, adv) for s in STATES}
    for _ in range(400):
        new = {}
        for s in STATES:
            acc = [0.0] * (MAX_RUNS + 1)
            for p, r, o, b in trans[s]:
                d = shift(dist[(o, b)] if o < 3 else zero, r)
                for k in range(MAX_RUNS + 1):
                    acc[k] += p * d[k]
            new[s] = acc
        done = max(abs(a - b) for s in STATES for a, b in zip(new[s], dist[s])) < 1e-12
        dist = new
        if done:
            break
    return dist


def win_table(inning_dist, innings: int = 9, tie_value: float = 0.5):
    """W[(inning, half, lead)]: the chance that the team about to bat wins, at the start of that half-inning.
    half 0 is the top (visitors bat), half 1 the bottom. A game tied after nine innings is a coin flip."""
    W = {}

    def after_half(i, half, lead):
        """Chance the team that just batted wins, given its lead once the half-inning is over."""
        if half == 0:
            return 1 - at_start(i, 1, -lead)
        if i >= innings:
            return 1.0 if lead > 0 else tie_value if lead == 0 else 0.0
        return 1 - at_start(i + 1, 0, -lead)

    def at_start(i, half, lead):
        if lead > MAX_LEAD:
            return 1.0
        if lead < -MAX_LEAD:
            return 0.0
        key = (i, half, lead)
        if key not in W:
            if half == 1 and i >= innings and lead > 0:
                W[key] = 1.0          # the home team is ahead and does not bat
            else:
                W[key] = sum(p * after_half(i, half, lead + k) for k, p in enumerate(inning_dist))
        return W[key]

    for i in range(innings, 0, -1):
        for half in (1, 0):
            for lead in range(-MAX_LEAD, MAX_LEAD + 1):
                at_start(i, half, lead)
    return W, after_half


def win_probability(dist, after_half, inning: int, half: int, lead: int):
    """Chance of winning for the batting team, given the distribution of runs it will add in this half-inning."""
    return sum(p * after_half(inning, half, lead + k) for k, p in enumerate(dist))


def swing_distribution(outs, bases, batter_rates, league, dists, adv: dict = ADVANCE):
    zero = [1.0] + [0.0] * MAX_RUNS
    acc = [0.0] * (MAX_RUNS + 1)
    for p, r, o, b in transitions(outs, bases, batter_rates, league['dp'], league['sf'], adv):
        d = shift(dists[(o, b)] if o < 3 else zero, r)
        for k in range(MAX_RUNS + 1):
            acc[k] += p * d[k]
    return acc


def bunt_distribution(outs, bases, kind, dists):
    r, o, nb = bunt_after(outs, bases, kind)
    return shift(dists[(o, nb)] if o < 3 else [1.0] + [0.0] * MAX_RUNS, r)
