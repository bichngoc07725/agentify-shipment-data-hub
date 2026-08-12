import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from services.booking_mail_service import build_booking_request_mail


def make_quote(**overrides):
    defaults = dict(
        quote_no="Q-2026-0007",
        customer_name="Cong ty TNHH Hat Dieu Phuong Nam",
        commodity="Hạt điều rang muối",
        incoterm="FOB",
        gross_weight_kg=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_booking(**overrides):
    defaults = dict(
        booking_no=None,
        carrier="Wan Hai Lines",
        vessel=None,
        voyage=None,
        pol="Cat Lai",
        pod="Singapore",
        etd=None,
        container_type="20GP",
        container_qty=1,
        freight_rate=None,
        currency="USD",
        note=None,
        quote=make_quote(),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BookingRequestMailTest(unittest.TestCase):
    def test_subject_carries_route_equipment_and_reference(self) -> None:
        subject = build_booking_request_mail(make_booking())["subject"]

        self.assertIn("Cat Lai", subject)
        self.assertIn("Singapore", subject)
        self.assertIn("1 x 20GP", subject)
        self.assertIn("Q-2026-0007", subject)

    def test_booking_no_is_preferred_over_the_quote_as_reference(self) -> None:
        subject = build_booking_request_mail(
            make_booking(booking_no="WHL-BKG-260710")
        )["subject"]

        self.assertIn("WHL-BKG-260710", subject)

    def test_body_asks_for_the_four_things_a_booking_needs(self) -> None:
        body = build_booking_request_mail(make_booking())["body"]

        self.assertIn("Booking number", body)
        self.assertIn("Vessel / voyage", body)
        self.assertIn("cut-off", body)
        self.assertIn("Empty pick-up depot", body)

    def test_it_places_a_firm_booking_not_another_rate_enquiry(self) -> None:
        # Bước 1 hỏi giá, bước 2 chốt chỗ. Gửi lại thư hỏi giá ở đây khiến hãng
        # tàu tưởng ta vẫn đang so giá và không giữ chỗ.
        body = build_booking_request_mail(make_booking())["body"]

        self.assertIn("firm booking", body)
        self.assertNotIn("quotation for the shipment below", body)

    def test_shipment_particulars_come_from_the_linked_quote(self) -> None:
        body = build_booking_request_mail(make_booking())["body"]

        self.assertIn("Hạt điều rang muối", body)
        self.assertIn("Cong ty TNHH Hat Dieu Phuong Nam", body)
        self.assertIn("FOB", body)

    def test_a_booking_without_a_quote_still_produces_a_usable_mail(self) -> None:
        body = build_booking_request_mail(make_booking(quote=None))["body"]

        self.assertIn("Cat Lai", body)
        self.assertNotIn("Commodity", body)

    def test_agreed_rate_is_restated_when_known(self) -> None:
        # Đây là chỗ tranh chấp hay xảy ra nhất khi debit note về ở Bước 6.
        body = build_booking_request_mail(
            make_booking(freight_rate=Decimal("690.00"))
        )["body"]

        self.assertIn("Agreed rate", body)
        self.assertIn("690.00 USD", body)

    def test_missing_route_is_stated_not_left_blank(self) -> None:
        body = build_booking_request_mail(make_booking(pod=None))["body"]

        self.assertIn("(chưa có)", body)

    def test_requested_etd_appears_only_when_set(self) -> None:
        self.assertNotIn("Requested ETD", build_booking_request_mail(make_booking())["body"])
        self.assertIn(
            "2026-07-10",
            build_booking_request_mail(make_booking(etd=date(2026, 7, 10)))["body"],
        )


if __name__ == "__main__":
    unittest.main()
