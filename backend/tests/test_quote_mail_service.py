import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from db.models import ChargeGroup
from services.quote_mail_service import (
    build_customer_quote_mail,
    build_rate_request_mail,
)


def charge(group: ChargeGroup, description: str, amount: str, quantity: str = "1"):
    return SimpleNamespace(
        charge_group=group,
        charge_code="X",
        description=description,
        amount=Decimal(amount),
        currency="USD",
        quantity=Decimal(quantity),
    )


def make_quote(**overrides):
    defaults = dict(
        quote_no="Q-2026-0005",
        customer_name="Tay Nguyen Coffee",
        pol="Da Nang",
        pod="Singapore",
        commodity="Coffee beans",
        container_type="20GP",
        container_qty=1,
        gross_weight_kg=None,
        cargo_ready_date=None,
        incoterm=None,
        payment_term=None,
        transit_time=None,
        valid_until=None,
        currency="USD",
        is_dangerous=False,
        is_reefer=False,
        charges=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class RateRequestMailTest(unittest.TestCase):
    def test_subject_carries_route_equipment_and_reference(self) -> None:
        mail = build_rate_request_mail(make_quote())

        self.assertIn("Da Nang", mail["subject"])
        self.assertIn("Singapore", mail["subject"])
        self.assertIn("1 x 20GP", mail["subject"])
        self.assertIn("Q-2026-0005", mail["subject"])

    def test_body_asks_for_the_three_things_a_quote_needs(self) -> None:
        body = build_rate_request_mail(make_quote())["body"]

        self.assertIn("Free time", body)
        self.assertIn("Transit time", body)
        self.assertIn("validity", body)

    def test_missing_route_is_stated_not_left_blank(self) -> None:
        # Ô trống giữa thân thư khiến người đọc tưởng không quan trọng, trong
        # khi thực ra là ta chưa biết.
        body = build_rate_request_mail(make_quote(pol=None))["body"]

        self.assertIn("(chưa có)", body)

    def test_dangerous_and_reefer_cargo_add_their_own_asks(self) -> None:
        body = build_rate_request_mail(
            make_quote(is_dangerous=True, is_reefer=True)
        )["body"]

        self.assertIn("IMO class", body)
        self.assertIn("temperature", body)

    def test_optional_details_are_omitted_when_absent(self) -> None:
        body = build_rate_request_mail(make_quote())["body"]

        self.assertNotIn("Gross weight", body)
        self.assertNotIn("Cargo ready date", body)

    def test_optional_details_appear_when_present(self) -> None:
        body = build_rate_request_mail(
            make_quote(gross_weight_kg=Decimal("18500"), cargo_ready_date=date(2026, 7, 1))
        )["body"]

        self.assertIn("18500", body)
        self.assertIn("2026-07-01", body)


class CustomerQuoteMailTest(unittest.TestCase):
    def test_charges_are_grouped_and_totalled(self) -> None:
        quote = make_quote(
            charges=[
                charge(ChargeGroup.OCEAN_FREIGHT, "Ocean freight", "780"),
                charge(ChargeGroup.SURCHARGE, "CIC", "60"),
                charge(ChargeGroup.LOCAL, "THC", "130"),
            ]
        )

        body = build_customer_quote_mail(quote)["body"]

        self.assertIn("Cước biển:", body)
        self.assertIn("Phụ phí:", body)
        self.assertIn("Phí local:", body)
        self.assertIn("TỔNG CỘNG: 970 USD", body)

    def test_a_quote_with_no_charges_says_so_instead_of_showing_an_empty_table(self) -> None:
        # Gửi báo giá chưa có dòng phí nào là gửi một tờ giấy trắng.
        body = build_customer_quote_mail(make_quote())["body"]

        self.assertIn("chưa có dòng phí nào", body)
        self.assertNotIn("TỔNG CỘNG", body)

    def test_validity_and_payment_term_appear_when_set(self) -> None:
        quote = make_quote(
            valid_until=date(2026, 8, 30),
            payment_term="TT 30 days",
            charges=[charge(ChargeGroup.OCEAN_FREIGHT, "Ocean freight", "780")],
        )

        body = build_customer_quote_mail(quote)["body"]

        self.assertIn("2026-08-30", body)
        self.assertIn("TT 30 days", body)

    def test_quantity_is_shown_only_when_it_is_not_one(self) -> None:
        quote = make_quote(
            charges=[
                charge(ChargeGroup.LOCAL, "THC", "260", quantity="2"),
                charge(ChargeGroup.SURCHARGE, "CIC", "60", quantity="1"),
            ]
        )

        body = build_customer_quote_mail(quote)["body"]

        self.assertIn("(x2)", body)
        self.assertNotIn("(x1)", body)

    def test_subject_names_the_quote_and_the_route(self) -> None:
        subject = build_customer_quote_mail(make_quote())["subject"]

        self.assertIn("Q-2026-0005", subject)
        self.assertIn("Da Nang", subject)
        self.assertIn("Singapore", subject)


if __name__ == "__main__":
    unittest.main()
