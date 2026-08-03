import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.quote_service import (
    build_quote_no,
    compute_charge_amount,
    list_quotes,
    total_amount,
)


class ChargeAmountTest(unittest.TestCase):
    def test_amount_is_unit_price_times_quantity(self) -> None:
        amount = compute_charge_amount(Decimal("120.50"), Decimal("2"))

        self.assertEqual(amount, Decimal("241.00"))

    def test_default_quantity_of_one_keeps_amount_equal_to_unit_price(self) -> None:
        amount = compute_charge_amount(Decimal("85"), Decimal("1"))

        self.assertEqual(amount, Decimal("85"))


class QuoteNoTest(unittest.TestCase):
    def test_first_quote_of_the_year_is_sequence_one(self) -> None:
        self.assertEqual(build_quote_no(2026, 1), "Q-2026-0001")

    def test_sequence_is_zero_padded_to_four_digits(self) -> None:
        self.assertEqual(build_quote_no(2026, 42), "Q-2026-0042")


class TotalAmountTest(unittest.TestCase):
    def test_sums_every_charge_line(self) -> None:
        quote = SimpleNamespace(
            charges=[
                SimpleNamespace(amount=Decimal("100")),
                SimpleNamespace(amount=Decimal("50.25")),
                SimpleNamespace(amount=Decimal("10")),
            ]
        )

        self.assertEqual(total_amount(quote), Decimal("160.25"))

    def test_no_charges_totals_to_zero(self) -> None:
        quote = SimpleNamespace(charges=[])

        self.assertEqual(total_amount(quote), Decimal("0"))


class ListQuotesContainerFilterTest(unittest.IsolatedAsyncioTestCase):
    async def test_an_unknown_container_no_returns_nothing_not_unassigned_quotes(self) -> None:
        """Regression test: `Quote.container_id == None` compiles to `IS NULL`
        in SQLAlchemy, which used to match every quote with no container at
        all — the opposite of "no quotes for this (nonexistent) container".
        A container_no that matches nothing must short-circuit before any
        such comparison is built, which we assert here by checking `db`
        never even runs a query.
        """
        db = AsyncMock()

        with patch(
            "services.quote_service.get_container_by_no",
            new=AsyncMock(return_value=None),
        ):
            items, total = await list_quotes(db, container_no="NOSUCH0000000")

        self.assertEqual(items, [])
        self.assertEqual(total, 0)
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
