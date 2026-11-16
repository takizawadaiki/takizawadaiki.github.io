"""Grocery prices in Canada against wages, 2019 to now.

    python analysis.py        # reads data/, writes results/results.json

Prices are Statistics Canada's monthly average retail prices for 110 products. Every comparison is between
two twelve-month averages (calendar 2019 and the latest twelve months), because fresh food prices move with the seasons.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_YEAR = 2019
PROVINCES = ['British Columbia', 'Alberta', 'Saskatchewan', 'Manitoba', 'Ontario', 'Quebec', 'New Brunswick', 'Nova Scotia', 'Prince Edward Island', 'Newfoundland and Labrador']

# first match wins
CATEGORIES = [
    ('Household', ['deodorant', 'toothpaste', 'shampoo', 'laundry']),
    ('Baby', ['baby food', 'infant formula']),
    ('Frozen', ['frozen']),
    ('Canned', ['canned']),
    ('Meat and fish', ['beef', 'pork', 'chicken', 'bacon', 'wieners', 'salmon', 'shrimp', 'tuna']),
    ('Drinks', ['juice', 'coffee', 'tea ', 'soy milk', 'nut milk']),
    ('Oils and sauces', ['oil', 'ketchup', 'mayonnaise', 'salsa', 'pasta sauce', 'salad dressing', 'margarine', 'peanut butter', 'hummus']),
    ('Dairy and eggs', ['milk, ', 'butter', 'cheese', 'yogurt', 'cream', 'eggs']),
    ('Fruit', ['apples', 'bananas', 'grapes', 'oranges', 'pears', 'lemons', 'limes', 'strawberries', 'cantaloupe', 'avocado']),
    ('Vegetables', ['broccoli', 'cabbage', 'carrots', 'celery', 'cucumber', 'lettuce', 'mushrooms', 'onions', 'peppers', 'potatoes', 'squash', 'tomatoes', 'salad greens', 'sweet potatoes']),
    ('Bread, grains and dry goods', ['bread', 'rice', 'pasta', 'flour', 'cereal', 'cookies', 'crackers', 'flatbread', 'sugar', 'lentils', 'beans', 'almonds', 'peanuts', 'sunflower', 'tofu', 'meatless']),
]

# a week of ordinary shopping for one household; the page lets the reader change it
DEFAULT_BASKET = {
    'Milk, 2 litres': 2, 'Eggs, 1 dozen': 1, 'Butter, 454 grams': 1, 'Block cheese, 500 grams': 1, 'Yogurt, 500 grams': 1,
    'White bread, 675 grams': 2, 'Dry or fresh pasta, 500 grams': 1, 'White rice, 2 kilograms': 1, 'Cereal, 400 grams': 1, 'Pasta sauce, 650 millilitres': 1,
    'Chicken breasts, per kilogram': 1, 'Ground beef, per kilogram': 1, 'Bacon, 500 grams': 1, 'Canned tuna, 170 grams': 2,
    'Apples, per kilogram': 1, 'Bananas, per kilogram': 1, 'Oranges, per kilogram': 1, 'Potatoes, per kilogram': 2, 'Onions, per kilogram': 1, 'Carrots, 1.36 kilograms': 1,
    'Tomatoes, per kilogram': 1, 'Romaine lettuce, unit': 1, 'Broccoli, unit': 1, 'Roasted or ground coffee, 340 grams': 1, 'Orange juice, 2 litres': 1,
    'Peanut butter, 1 kilogram': 1, 'Vegetable oil, 3 litres': 1,
}


def category(product):
    p = product.lower()
    for name, words in CATEGORIES:
        if any(w in p for w in words):
            return name
    return 'Other'


def read(name):
    with open(HERE / 'data' / name, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def table(rows, key, value):
    """{geo: {key: {month: value}}} from long rows."""
    out = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        out[r['geo']][r[key].strip() if key else '']['%s' % r['month']] = float(r[value])
    return out


def last_twelve(months):
    """The latest twelve months in a sorted list of 'YYYY-MM' strings."""
    months = sorted(months)
    return months[-12:]


def average(series, months):
    vals = [series[m] for m in months if m in series]
    return sum(vals) / len(vals) if len(vals) >= max(1, len(months) - 2) else None       # allow two missing months


def change(now, base):
    return now / base - 1 if now is not None and base else None


def minutes_of_work(price, hourly_wage):
    return price / hourly_wage * 60


def basket_cost(basket, prices):
    """Cost of a basket {product: quantity} at given prices; None if any priced item is missing."""
    total = 0.0
    for product, qty in basket.items():
        if prices.get(product) is None:
            return None
        total += qty * prices[product]
    return total


def main():
    prices = table(read('prices.csv'), 'product', 'price')
    cpi = table(read('cpi.csv'), 'item', 'index')
    wages = {g: t[''] for g, t in table(read('wages.csv'), None, 'hourly_wage').items()}
    base = [f'{BASE_YEAR}-{m:02d}' for m in range(1, 13)]
    now = last_twelve(next(iter(prices['Canada'].values())).keys())
    wage = {g: dict(base=average(wages[g], base), now=average(wages[g], now)) for g in wages}
    for g in wage:
        wage[g]['change'] = change(wage[g]['now'], wage[g]['base'])
    months = sorted(next(iter(prices['Canada'].values())).keys())
    months = [m for m in months if m >= f'{BASE_YEAR}-01']

    products = []
    for name, series in sorted(prices['Canada'].items()):
        b, n = average(series, base), average(series, now)
        item, _, size = name.partition(',')
        products.append(dict(
            id=name, name=item.strip(), size=size.strip() or 'each', category=category(name),
            base=round(b, 3), now=round(n, 3), change=round(change(n, b), 4),
            minutes_base=round(minutes_of_work(b, wage['Canada']['base']), 2), minutes_now=round(minutes_of_work(n, wage['Canada']['now']), 2),
            series=[round(series[m], 2) if m in series else None for m in months],
            provinces={p: (round(v, 2) if (v := average(prices[p].get(name, {}), now)) is not None else None) for p in PROVINCES},
            provinces_base={p: (round(v, 2) if (v := average(prices[p].get(name, {}), base)) is not None else None) for p in PROVINCES}))
    products.sort(key=lambda p: -p['change'])

    ch = [p['change'] for p in products]
    wg = wage['Canada']['change']
    cats = defaultdict(list)
    for p in products:
        cats[p['category']].append(p['change'])
    cpi_ca = cpi['Canada']
    cpi_change = {item: round(change(average(s, now), average(s, base)), 4) for item, s in cpi_ca.items() if average(s, base)}
    idx = lambda s: [round(s[m] / average(s, base) * 100, 1) if m in s else None for m in months]
    provinces = []
    for p in PROVINCES:
        pn = {x['id']: x['provinces'][p] for x in products}
        pb = {x['id']: x['provinces_base'][p] for x in products}
        cn, cb = basket_cost(DEFAULT_BASKET, pn), basket_cost(DEFAULT_BASKET, pb)
        food = cpi[p]['Food purchased from stores']
        provinces.append(dict(name=p, wage=round(wage[p]['now'], 2), wage_change=round(wage[p]['change'], 4),
                              food_change=round(change(average(food, now), average(food, base)), 4),
                              basket=round(cn, 2), basket_base=round(cb, 2), basket_change=round(change(cn, cb), 4),
                              basket_minutes=round(minutes_of_work(cn, wage[p]['now']), 1), basket_minutes_base=round(minutes_of_work(cb, wage[p]['base']), 1)))
    ca_now, ca_base = {x['id']: x['now'] for x in products}, {x['id']: x['base'] for x in products}
    bn, bb = basket_cost(DEFAULT_BASKET, ca_now), basket_cost(DEFAULT_BASKET, ca_base)
    out = dict(
        base_year=BASE_YEAR, now=[now[0], now[-1]], months=months, provinces_order=PROVINCES,
        summary=dict(products=len(products), median_change=round(statistics.median(ch), 4), faster_than_wages=sum(c > wg for c in ch), cheaper=sum(c < 0 for c in ch),
                     over_50=sum(c >= 0.5 for c in ch), wage_change=round(wg, 4), wage_base=round(wage['Canada']['base'], 2), wage_now=round(wage['Canada']['now'], 2),
                     food_cpi=cpi_change['Food purchased from stores'], all_cpi=cpi_change['All-items'], restaurant_cpi=cpi_change['Food purchased from restaurants'],
                     basket=round(bn, 2), basket_base=round(bb, 2), basket_change=round(change(bn, bb), 4),
                     basket_minutes=round(minutes_of_work(bn, wage['Canada']['now']), 1), basket_minutes_base=round(minutes_of_work(bb, wage['Canada']['base']), 1)),
        categories=sorted([dict(name=k, products=len(v), median=round(statistics.median(v), 4), low=round(min(v), 4), high=round(max(v), 4)) for k, v in cats.items()], key=lambda c: -c['median']),
        cpi=cpi_change,
        index=dict(food=idx(cpi_ca['Food purchased from stores']), all=idx(cpi_ca['All-items']), wage=idx(wages['Canada'])),
        provinces=provinces, default_basket=DEFAULT_BASKET, products=products)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'results.json').write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    print(out['now'], out['summary']); print(out['categories']); print(cpi_change)
    for p in provinces: print(p)
    for p in products[:8] + products[-6:]: print(p['id'], p['category'], p['base'], p['now'], p['change'], p['minutes_base'], p['minutes_now'])
    print([p['id'] for p in products if p['category'] == 'Other'])


if __name__ == '__main__':
    main()
