import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as a


class Helpers(unittest.TestCase):
    def test_payment_matches_a_known_mortgage(self):
        # $100,000 at 5% over 25 years, compounded semi-annually, is $581.60 a month
        self.assertAlmostEqual(100000 * a.monthly_payment_per_dollar(5.0), 581.60, places=1)

    def test_payment_rises_with_the_rate(self):
        self.assertGreater(a.monthly_payment_per_dollar(18), 2 * a.monthly_payment_per_dollar(4))

    def test_dollar_conversion(self):
        cpi = {2000: 50.0, a.BASE_YEAR: 100.0}
        self.assertEqual(a.to_base(10, 2000, cpi), 20)
        self.assertEqual(a.to_base(10, 1990, cpi, from_year=2000), 20)

    def test_verdict_directions_and_band(self):
        self.assertEqual(a.verdict(110, 100, 1), 'better')
        self.assertEqual(a.verdict(110, 100, -1), 'worse')
        self.assertEqual(a.verdict(102, 100, -1), 'same')
        self.assertIsNone(a.verdict(None, 100, 1))


class Data(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.early = a.build()

    def test_every_year_is_present(self):
        self.assertEqual(sorted(self.rows), list(range(1976, 2026)))

    def test_indexes_start_at_100(self):
        for key in ('house_real', 'house_to_income', 'payment_to_income'):
            self.assertAlmostEqual(self.rows[1976][key], 100)

    def test_income_is_converted_from_2024_to_2025_dollars(self):
        s = a.load_series('statcan_series.txt')
        expected = 49600 * s['cpi_all'][2025] / s['cpi_all'][2024]
        self.assertAlmostEqual(self.rows[2024]['income'], expected)
        self.assertIsNone(self.rows[2025]['income'])

    def test_latest_tuition_is_unchanged_by_inflation_adjustment(self):
        self.assertAlmostEqual(self.rows[2025]['tuition'], self.rows[2025]['tuition_nominal'])

    def test_rents_start_in_1987_for_all_eight_cities(self):
        self.assertEqual(len(self.rows[2025]['rent']), 8)
        self.assertEqual(self.rows[1986]['rent'], {})
        self.assertAlmostEqual(self.rows[2025]['rent']['Toronto'], 1761)

    def test_tuition_series_join(self):
        s = a.load_series('statcan_series.txt')
        self.assertEqual(s['tu_old'][2005], 4211)
        self.assertEqual({**s['tu_old'], **s['tu_new']}[2006], 4400)

    def test_scorecard_example(self):
        c = a.compare(self.rows, self.early, 2000, 1970)
        self.assertEqual(c['compared'], 6)
        self.assertEqual(c['worse'] + c['better'] + sum(v == 'same' for v in c['verdicts'].values()), 6)
        self.assertEqual(c['verdicts']['tuition'], 'worse')

    def test_someone_not_yet_25_uses_the_latest_year(self):
        young = a.compare(self.rows, self.early, 2004, 1970)
        self.assertEqual(young['me']['unemployment'], self.rows[2025]['unemployment'])

    def test_oldest_cohort_has_tuition(self):
        self.assertIsNotNone(a.compare(self.rows, self.early, 2000, 1952)['parent']['tuition'])


if __name__ == '__main__':
    unittest.main()
