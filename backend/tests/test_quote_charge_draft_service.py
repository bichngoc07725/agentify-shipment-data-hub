import unittest

from db.models import ChargeGroup
from services.quote_charge_draft_service import build_charge_lines, classify_charge


class ClassifyChargeTest(unittest.TestCase):
    def test_ocean_freight_goes_to_its_own_group(self) -> None:
        self.assertEqual(
            classify_charge("Ocean Freight 20GP"), ("OF", ChargeGroup.OCEAN_FREIGHT)
        )

    def test_vietnamese_wording_is_recognized(self) -> None:
        self.assertEqual(classify_charge("Cước biển"), ("OF", ChargeGroup.OCEAN_FREIGHT))

    def test_thc_is_a_local_charge_not_a_surcharge(self) -> None:
        # THC thu tại cảng đầu VN — xếp vào phụ phí sẽ làm sai cơ cấu giá khi
        # đối chiếu với debit note ở Bước 6.
        self.assertEqual(classify_charge("Terminal Handling Charge"), ("THC", ChargeGroup.LOCAL))

    def test_bunker_and_imbalance_are_surcharges(self) -> None:
        self.assertEqual(classify_charge("BAF")[1], ChargeGroup.SURCHARGE)
        self.assertEqual(classify_charge("Container Imbalance Charge")[1], ChargeGroup.SURCHARGE)

    def test_unknown_charge_lands_in_surcharge_not_ocean_freight(self) -> None:
        # Đoán nhầm vào cước biển làm hỏng phép đối soát, vì cước biển là khoản
        # đối chiếu chính; phụ phí là chỗ an toàn để người dùng sửa lại.
        code, group = classify_charge("Phí abcxyz lạ hoắc")

        self.assertEqual(code, "OTHER")
        self.assertEqual(group, ChargeGroup.SURCHARGE)

    def test_empty_description_does_not_crash(self) -> None:
        self.assertEqual(classify_charge(None), ("OTHER", ChargeGroup.SURCHARGE))


class BuildChargeLinesTest(unittest.TestCase):
    def test_maps_an_extracted_charge_onto_a_quote_line(self) -> None:
        lines = build_charge_lines(
            [{"description": "Ocean Freight", "amount": 780, "currency": "USD", "quantity": "1"}]
        )

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["charge_group"], "ocean_freight")
        self.assertEqual(lines[0]["charge_code"], "OF")
        self.assertEqual(lines[0]["unit_price"], "780")
        self.assertEqual(lines[0]["quantity"], "1")

    def test_amount_is_divided_by_quantity_to_get_unit_price(self) -> None:
        # `amount` trích ra là thành tiền cả dòng; lưu thẳng vào đơn giá sẽ
        # nhân đôi tổng báo giá khi backend tính lại amount = đơn giá x SL.
        lines = build_charge_lines(
            [{"description": "THC", "amount": 260, "currency": "USD", "quantity": "2"}]
        )

        self.assertEqual(lines[0]["unit_price"], "130")
        self.assertEqual(lines[0]["quantity"], "2")

    def test_a_charge_without_an_amount_is_dropped(self) -> None:
        # Để lại với đơn giá 0 sẽ âm thầm kéo tổng báo giá thấp hơn thực tế.
        lines = build_charge_lines(
            [
                {"description": "Ocean Freight", "amount": 780, "currency": "USD"},
                {"description": "Phí chờ xác nhận", "amount": None, "currency": "USD"},
            ]
        )

        self.assertEqual(len(lines), 1)

    def test_zero_or_missing_quantity_falls_back_to_one(self) -> None:
        lines = build_charge_lines(
            [{"description": "CIC", "amount": 60, "currency": "USD", "quantity": "0"}]
        )

        self.assertEqual(lines[0]["quantity"], "1")
        self.assertEqual(lines[0]["unit_price"], "60")

    def test_currency_defaults_to_usd_when_absent(self) -> None:
        lines = build_charge_lines([{"description": "CIC", "amount": 60}])

        self.assertEqual(lines[0]["currency"], "USD")

    def test_no_charges_returns_an_empty_list(self) -> None:
        self.assertEqual(build_charge_lines([]), [])
        self.assertEqual(build_charge_lines(None), [])


if __name__ == "__main__":
    unittest.main()
