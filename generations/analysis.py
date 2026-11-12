"""Is your generation worse off than your parents'? The numbers behind the page (Canada, 1976 to 2025).

Reads the raw series in data/raw and writes results/results.json, which the page loads, and
data/canada_by_year.csv. Standard library only:

    python analysis.py
    python -m unittest discover tests

Sources and series identifiers are listed in data/SOURCES.md.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / 'data' / 'raw'
BASE_YEAR = 2025          # every dollar figure is expressed in 2025 dollars
INCOME_DOLLAR_YEAR = 2024  # Statistics Canada publishes the income table in 2024 constant dollars
FIRST, LAST = 1976, 2025
AMORTIZATION_YEARS = 25
CITIES = {'Toronto, Ontario': 'Toronto', 'Vancouver, British Columbia': 'Vancouver', 'Montréal, Quebec': 'Montréal',
          'Calgary, Alberta': 'Calgary', 'Edmonton, Alberta': 'Edmonton',
          'Ottawa-Gatineau, Ontario part, Ontario/Quebec': 'Ottawa', 'Winnipeg, Manitoba': 'Winnipeg',
          'Halifax, Nova Scotia': 'Halifax'}
# higher is better for income; lower is better for the rest
METRICS = [('income', 1), ('house_to_income', -1), ('payment_to_income', -1), ('rent', -1), ('tuition', -1), ('unemployment', -1)]
SIMILAR_BAND = 0.03  # changes within 3% are called "about the same"


def load_series(name):
    out = {}
    for line in (RAW / name).read_text(encoding='utf-8').splitlines():
        key, _, start, values = line.split('|')
        out[key] = {int(start) + i: float(v) for i, v in enumerate(values.split(','))}
    return out


def load_rents():
    out = {}
    for line in (RAW / 'cmhc_rents.txt').read_text(encoding='utf-8').splitlines():
        name, structure, _, span, values = line.split('|')
        if structure == 's4' and name in CITIES:   # apartment buildings of six units and over, one-bedroom
            start = int(span[:4])
            out[CITIES[name]] = {start + i: float(v) for i, v in enumerate(values.split(','))}
    return out


def monthly_payment_per_dollar(annual_rate_pct, years=AMORTIZATION_YEARS):
    """Monthly payment on a $1 mortgage. Canadian fixed rates compound twice a year."""
    monthly = (1 + annual_rate_pct / 200) ** (1 / 6) - 1
    n = years * 12
    return monthly / (1 - (1 + monthly) ** -n)


def to_base(value, year, cpi, from_year=None):
    """Convert dollars of `year` (or constant dollars of `from_year`) into BASE_YEAR dollars."""
    return value * cpi[BASE_YEAR] / cpi[from_year or year]


def index_to(series, base):
    return {y: 100 * v / series[base] for y, v in series.items()}


def verdict(mine, theirs, direction, band=SIMILAR_BAND):
    """'better', 'worse' or 'same' for the first value against the second."""
    if mine is None or theirs is None:
        return None
    change = (mine - theirs) / theirs
    if abs(change) <= band:
        return 'same'
    return 'better' if change * direction > 0 else 'worse'


def build():
    s, cpi_house, rents = load_series('statcan_series.txt'), load_series('bis_house_prices.txt')['house_bis'], load_rents()
    cpi = s['cpi_all']
    years = list(range(FIRST, LAST + 1))
    tuition_nominal = {**s['tu_old'], **s['tu_new']}   # the newer survey takes over from 2006/07

    def income(key, y):   # 2024 constant dollars -> 2025 dollars
        return to_base(s[key][y], y, cpi, INCOME_DOLLAR_YEAR) if y in s[key] else None

    rows = {}
    for y in years:
        inc = income('inc_med_total_2534', y)
        inc_nominal = s['inc_med_total_2534'][y] * cpi[y] / cpi[INCOME_DOLLAR_YEAR] if y in s['inc_med_total_2534'] else None
        rows[y] = dict(
            year=y, income=inc, income_men=income('inc_med_total_2534_m', y), income_women=income('inc_med_total_2534_w', y),
            income_4554=income('inc_med_total_4554', y), income_all=income('inc_med_total_15up', y),
            house_real=cpi_house[y] / cpi[y],
            house_to_income=cpi_house[y] / inc_nominal if inc_nominal else None,
            payment_to_income=cpi_house[y] * monthly_payment_per_dollar(s['mort5'][y]) / inc_nominal if inc_nominal else None,
            mortgage_rate=s['mort5'][y], unemployment=s['ur_2529'][y], unemployment_1524=s['ur_1524'][y],
            unemployment_2554=s['ur_2554'][y], full_time=s['ft_2529'][y], employment_rate=s['er_2529'][y],
            tuition=to_base(tuition_nominal[y], y, cpi), tuition_nominal=tuition_nominal[y],
            cpi=cpi[y], rent={c: to_base(v[y], y, cpi) for c, v in rents.items() if y in v},
            rent_share={c: 12 * v[y] / inc_nominal for c, v in rents.items() if y in v and inc_nominal})
    # tuition is also needed for 1972-1975, the years the oldest cohorts were 20
    early_tuition = {y: to_base(tuition_nominal[y], y, cpi) for y in range(1972, FIRST)}
    for key in ('house_real', 'house_to_income', 'payment_to_income'):
        base = rows[FIRST][key]
        for y in years:
            if rows[y][key] is not None:
                rows[y][key] = 100 * rows[y][key] / base
    return rows, early_tuition


def summarise(rows):
    have_income = [y for y in rows if rows[y]['income'] is not None]
    last_inc = max(have_income)

    def extreme(key, fn, pool=None):
        pool = pool or [y for y in rows if rows[y][key] is not None]
        y = fn(pool, key=lambda yy: rows[yy][key])
        return dict(year=y, value=round(rows[y][key], 2))

    def change(key, a, b):
        return round(100 * (rows[b][key] / rows[a][key] - 1), 1)

    return dict(
        first=FIRST, last=LAST, last_income_year=last_inc,
        income=dict(start=round(rows[FIRST]['income']), end=round(rows[last_inc]['income']), change_pct=change('income', FIRST, last_inc),
                    low=extreme('income', min), high=extreme('income', max),
                    men_change_pct=change('income_men', FIRST, last_inc), women_change_pct=change('income_women', FIRST, last_inc),
                    age4554_change_pct=change('income_4554', FIRST, last_inc), all_change_pct=change('income_all', FIRST, last_inc)),
        housing=dict(real_price_change_pct=change('house_real', FIRST, LAST), to_income_end=round(rows[last_inc]['house_to_income']),
                     to_income_peak=extreme('house_to_income', max), payment_end=round(rows[last_inc]['payment_to_income']),
                     payment_peak=extreme('payment_to_income', max), payment_low=extreme('payment_to_income', min),
                     rate_peak=extreme('mortgage_rate', max), rate_low=extreme('mortgage_rate', min)),
        tuition=dict(start=round(rows[FIRST]['tuition']), end=round(rows[LAST]['tuition']), change_pct=change('tuition', FIRST, LAST),
                     low=extreme('tuition', min), high=extreme('tuition', max)),
        jobs=dict(peak=extreme('unemployment', max), low=extreme('unemployment', min), end=rows[LAST]['unemployment'],
                  full_time_start=rows[FIRST]['full_time'], full_time_end=rows[LAST]['full_time']),
        rent={c: dict(start_year=min(y for y in rows if c in rows[y]['rent']),
                      start=round(rows[min(y for y in rows if c in rows[y]['rent'])]['rent'][c]), end=round(rows[LAST]['rent'][c]),
                      change_pct=round(100 * (rows[LAST]['rent'][c] / rows[1987]['rent'][c] - 1), 1),
                      share_start=round(100 * rows[1987]['rent_share'][c], 1), share_end=round(100 * rows[last_inc]['rent_share'][c], 1))
              for c in rows[LAST]['rent']})


def compare(rows, early_tuition, born, parent_born, city='Toronto'):
    """The scorecard the page shows: each person's figures in the year they turned 25 (tuition at 20)."""
    def snapshot(b):
        y = min(b + 25, LAST)
        yi = min(y, max(yy for yy in rows if rows[yy]['income'] is not None))
        ty = min(b + 20, LAST)
        return dict(income=rows[yi]['income'], house_to_income=rows[yi]['house_to_income'], payment_to_income=rows[yi]['payment_to_income'],
                    rent=rows[y]['rent'].get(city), tuition=rows[ty]['tuition'] if ty >= FIRST else early_tuition.get(ty),
                    unemployment=rows[y]['unemployment'])
    me, parent = snapshot(born), snapshot(parent_born)
    out = {k: verdict(me[k], parent[k], d) for k, d in METRICS}
    return dict(me=me, parent=parent, verdicts=out, worse=sum(v == 'worse' for v in out.values()),
                better=sum(v == 'better' for v in out.values()), compared=sum(v is not None for v in out.values()))


def main():
    rows, early_tuition = build()
    summary = summarise(rows)
    r2 = lambda v: None if v is None else round(v, 2)
    table = [dict(year=y, income=r2(r['income']), income_men=r2(r['income_men']), income_women=r2(r['income_women']),
                  income_4554=r2(r['income_4554']), income_all=r2(r['income_all']), house_real=r2(r['house_real']),
                  house_to_income=r2(r['house_to_income']), payment_to_income=r2(r['payment_to_income']),
                  mortgage_rate=r['mortgage_rate'], unemployment=r['unemployment'], unemployment_1524=r['unemployment_1524'],
                  unemployment_2554=r['unemployment_2554'], full_time=r['full_time'], tuition=r2(r['tuition']),
                  rent={c: round(v) for c, v in r['rent'].items()}, rent_share={c: round(100 * v, 1) for c, v in r['rent_share'].items()})
             for y, r in rows.items()]
    examples = {f'{b}_{p}': {k: v for k, v in compare(rows, early_tuition, b, p).items() if k in ('verdicts', 'worse', 'better', 'compared')}
                for b, p in ((2000, 1970), (1990, 1960), (1975, 1952))}
    results = dict(summary=summary, years=table, early_tuition={y: round(v, 2) for y, v in early_tuition.items()},
                   cities=list(CITIES.values()), examples=examples,
                   config=dict(base_year=BASE_YEAR, similar_band=SIMILAR_BAND, amortization_years=AMORTIZATION_YEARS,
                               metrics=[dict(key=k, direction=d) for k, d in METRICS]))
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(results, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    with open(HERE / 'data' / 'canada_by_year.csv', 'w', newline='', encoding='utf-8') as f:
        cols = ['year', 'income', 'income_men', 'income_women', 'income_4554', 'income_all', 'house_real', 'house_to_income',
                'payment_to_income', 'mortgage_rate', 'unemployment', 'unemployment_1524', 'full_time', 'tuition']
        w = csv.writer(f)
        w.writerow(cols + [f'rent_{c.lower()}' for c in CITIES.values()])
        for t in table:
            w.writerow([t[c] for c in cols] + [t['rent'].get(c, '') for c in CITIES.values()])
    return results


if __name__ == '__main__':
    r = main()
    print(json.dumps(r['summary'], indent=1, ensure_ascii=False))
    print(r['examples'])
