import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A


def test_categories_put_awkward_names_in_the_right_place():
    assert A.category('Peanut butter, 1 kilogram') == 'Oils and sauces'
    assert A.category('Soy milk, 1.89 litres') == 'Drinks'
    assert A.category('Milk, 2 litres') == 'Dairy and eggs'
    assert A.category('Canned tuna, 170 grams') == 'Canned'
    assert A.category('Frozen green beans, 750 grams') == 'Frozen'
    assert A.category('Pasta sauce, 650 millilitres') == 'Oils and sauces'
    assert A.category('Dry or fresh pasta, 500 grams') == 'Bread, grains and dry goods'
    assert A.category('Beef top sirloin cuts, per kilogram') == 'Meat and fish'


def test_last_twelve_takes_the_latest_year_of_months():
    months = [f'{y}-{m:02d}' for y in (2024, 2025) for m in range(1, 13)] + ['2026-01']
    out = A.last_twelve(months)
    assert out[0] == '2025-02' and out[-1] == '2026-01' and len(out) == 12


def test_average_needs_nearly_a_full_year():
    months = [f'2019-{m:02d}' for m in range(1, 13)]
    assert A.average({m: 2.0 for m in months}, months) == 2.0
    assert A.average({m: 2.0 for m in months[:10]}, months) == 2.0          # two missing months are allowed
    assert A.average({m: 2.0 for m in months[:9]}, months) is None


def test_change_and_minutes_of_work():
    assert abs(A.change(13.0, 10.0) - 0.3) < 1e-9
    assert A.change(None, 10.0) is None
    assert abs(A.minutes_of_work(10.0, 30.0) - 20.0) < 1e-9                 # a $10 item at $30 an hour


def test_basket_cost_multiplies_quantities_and_refuses_missing_prices():
    assert A.basket_cost({'a': 2, 'b': 1}, {'a': 3.0, 'b': 4.0}) == 10.0
    assert A.basket_cost({'a': 2, 'b': 1}, {'a': 3.0, 'b': None}) is None


def test_every_product_has_a_category_and_the_default_basket_exists_everywhere():
    import json
    A.main()
    R = json.loads((Path(A.HERE) / 'results' / 'results.json').read_text())
    assert all(p['category'] != 'Other' for p in R['products'])
    ids = {p['id']: p for p in R['products']}
    for name in R['default_basket']:
        assert name in ids and all(v is not None for v in ids[name]['provinces'].values())
