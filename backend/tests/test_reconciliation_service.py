import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from services.reconciliation_service import (
    build_reconciliation_lines,
    compute_demurrage_estimate,
    needs_approval_for,
    totals_for,
)


def charge(code: str, amount: str) -> SimpleNamespace:
    return SimpleNamespace(charge_code=code, amount=Decimal(amount))


class MatchedTest(unittest.TestCase):
    def test_identical_charges_match_on_every_line(self) -> None:
        quote_charges = [charge("OF", "1200.00"), charge("THC", "80.00")]
        debit_charges = [charge("OF", "1200.00"), charge("THC", "80.00")]

        lines = build_reconciliation_lines(quote_charges, debit_charges)

        self.assertEqual(len(lines), 2)
        self.assertTrue(all(line.match_status == "matched" for line in lines))

        total_quoted, total_actual, total_variance = totals_for(lines)
        self.assertEqual(total_variance, Decimal("0"))
        self.assertFalse(needs_approval_for(total_quoted, total_variance))

    def test_charge_codes_are_case_and_space_insensitive(self) -> None:
        lines = build_reconciliation_lines([charge(" of ", "100")], [charge("OF", "100")])

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].match_status, "matched")

    def test_a_tiny_rounding_difference_still_counts_as_matched(self) -> None:
        lines = build_reconciliation_lines([charge("OF", "1200.00")], [charge("OF", "1200.50")])

        self.assertEqual(lines[0].match_status, "matched")


class VarianceTest(unittest.TestCase):
    def test_a_charge_over_the_threshold_is_flagged_with_the_right_amount(self) -> None:
        quote_charges = [charge("OF", "1200.00"), charge("THC", "80.00")]
        debit_charges = [charge("OF", "1250.00"), charge("THC", "80.00")]

        lines = build_reconciliation_lines(quote_charges, debit_charges)
        by_code = {line.charge_code: line for line in lines}

        self.assertEqual(by_code["OF"].match_status, "variance")
        self.assertEqual(by_code["OF"].variance, Decimal("50.00"))
        self.assertEqual(by_code["THC"].match_status, "matched")

        total_quoted, total_actual, total_variance = totals_for(lines)
        self.assertEqual(total_variance, Decimal("50.00"))


class MissingAndExtraTest(unittest.TestCase):
    def test_a_quoted_charge_never_invoiced_is_missing_actual(self) -> None:
        lines = build_reconciliation_lines([charge("DOC", "30.00")], [])

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].match_status, "missing_actual")
        self.assertEqual(lines[0].actual_amount, None)
        self.assertEqual(lines[0].variance, Decimal("-30.00"))

    def test_a_real_charge_never_quoted_is_extra_actual(self) -> None:
        """The exact case that loses money: a fee on the invoice that never
        made it into the customer's quote."""
        lines = build_reconciliation_lines([], [charge("CIC", "45.00")])

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].match_status, "extra_actual")
        self.assertEqual(lines[0].quoted_amount, None)
        self.assertEqual(lines[0].variance, Decimal("45.00"))


class NeedsApprovalTest(unittest.TestCase):
    def test_a_large_total_variance_requires_approval(self) -> None:
        quote_charges = [charge("OF", "1000.00")]
        debit_charges = [charge("OF", "1200.00")]  # +200, well past both thresholds

        lines = build_reconciliation_lines(quote_charges, debit_charges)
        total_quoted, total_actual, total_variance = totals_for(lines)

        self.assertTrue(needs_approval_for(total_quoted, total_variance))

    def test_a_small_variance_does_not_require_approval(self) -> None:
        quote_charges = [charge("OF", "1000.00")]
        debit_charges = [charge("OF", "1005.00")]

        lines = build_reconciliation_lines(quote_charges, debit_charges)
        total_quoted, total_actual, total_variance = totals_for(lines)

        self.assertFalse(needs_approval_for(total_quoted, total_variance))


class DemurrageTest(unittest.TestCase):
    def test_no_arrival_data_means_no_estimate(self) -> None:
        container = SimpleNamespace(ata=None, eta=None, free_time_days=None)

        self.assertIsNone(compute_demurrage_estimate(container, today=date(2026, 7, 1)))

    def test_still_within_free_time_means_no_estimate(self) -> None:
        container = SimpleNamespace(ata=date(2026, 7, 1), eta=None, free_time_days=5)

        self.assertIsNone(compute_demurrage_estimate(container, today=date(2026, 7, 3)))

    def test_overdue_days_are_billed_at_the_daily_rate(self) -> None:
        container = SimpleNamespace(ata=date(2026, 7, 1), eta=None, free_time_days=5)
        # Deadline is 2026-07-06; 4 days overdue by 2026-07-10.
        today = date(2026, 7, 10)

        line = compute_demurrage_estimate(container, today=today, daily_rate=Decimal("50"))

        self.assertIsNotNone(line)
        self.assertEqual(line.match_status, "extra_actual")
        self.assertEqual(line.actual_amount, Decimal("200"))
        self.assertIsNone(line.quoted_amount)

    def test_assumed_free_time_says_so_in_the_note(self) -> None:
        container = SimpleNamespace(ata=date(2026, 7, 1), eta=None, free_time_days=None)

        line = compute_demurrage_estimate(container, today=date(2026, 7, 20))

        self.assertIsNotNone(line)
        self.assertIn("tạm tính", line.note)


if __name__ == "__main__":
    unittest.main()
