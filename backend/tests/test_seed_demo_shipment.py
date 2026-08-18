"""Kiểm file kịch bản demo, không gọi API.

Seeder chỉ có giá trị nếu con số trong file JSON đúng: một buổi demo dựng trên
bảng phí sai còn tệ hơn không demo, vì người xem tin vào nó.
"""

import json
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from scripts.seed_demo_shipment import (
    DATA_DIR,
    SEED_MARKER,
    STAGES,
    WIPE_ORDER,
    apply_date_shift,
    build_date_shift,
    delivery_timestamps,
    load_spec,
    waves_upto,
)


class EmailWaveTest(unittest.TestCase):
    """Thư phải đến theo đợt, không đổ hết một lượt.

    Đổ hết thì ở Bước 2.1 — lúc còn đang soạn yêu cầu đặt chỗ — thư xác nhận
    của hãng tàu đã nằm sẵn trong hộp thư, và câu hỏi trung tâm của Bước 2
    ("ghi nhận được trạng thái đã hỏi mà chưa được trả lời không?") không còn
    kiểm được.
    """

    def setUp(self) -> None:
        self.spec = load_spec("roundtrip_rfq_hpn")

    def test_waves_follow_the_order_of_the_walkthrough(self) -> None:
        self.assertEqual(
            [w["name"] for w in self.spec["email_waves"]],
            ["rfq", "rate", "booking", "docs", "customs"],
        )

    def test_asking_for_a_wave_includes_every_earlier_one(self) -> None:
        # Cộng dồn, không phải chỉ đợt đó: đến Bước 2.3 thì thư hỏi giá và thư
        # báo cước vẫn phải còn trong hộp thư.
        self.assertEqual(
            [w["name"] for w in waves_upto(self.spec, "booking")],
            ["rfq", "rate", "booking"],
        )

    def test_all_means_every_wave(self) -> None:
        self.assertEqual(len(waves_upto(self.spec, "all")), len(self.spec["email_waves"]))

    def test_an_unknown_wave_fails_loudly(self) -> None:
        with self.assertRaises(SystemExit):
            waves_upto(self.spec, "khong-co")

    def test_the_confirmation_does_not_arrive_before_the_booking_wave(self) -> None:
        # Đây là chỗ vô lý mà đợt thư sinh ra để sửa: thư trả lời không được
        # nằm sẵn trong hộp thư trước khi người dùng gửi thư đi.
        early = [f for w in waves_upto(self.spec, "rate") for f in w["folders"]]

        self.assertNotIn("-06-hang-tau-xac-nhan", early)

    def test_every_inbound_folder_belongs_to_exactly_one_wave(self) -> None:
        # Thư không thuộc đợt nào sẽ không bao giờ được nạp ở chế độ `--deliver`
        # và lặng lẽ vắng mặt khỏi hồ sơ.
        seen: list[str] = []
        for wave in self.spec["email_waves"]:
            seen.extend(wave["folders"])

        self.assertEqual(len(seen), len(set(seen)))
        # Đúng 6 thư đến của kịch bản; 3 thư đi không thuộc đợt nào vì chúng là
        # thư người dùng tự gửi, không nạp ngược vào hồ sơ.
        self.assertEqual(len(seen), 6)


class DeliveryTimestampTest(unittest.TestCase):
    """Thư phải mang dấu thời gian LÚC NHẬN, không phải ngày cứng trong corpus.

    Corpus ghi ngày tuyệt đối (03–07/08/2026) nên càng để lâu càng lệch: người
    dùng vừa bấm gửi thư đặt chỗ, thư trả lời hiện ra "12 ngày trước" — câu trả
    lời có trước câu hỏi.
    """

    def test_stamps_increase_so_order_within_a_wave_is_kept(self) -> None:
        now = datetime(2026, 8, 17, 22, 0, tzinfo=UTC)

        stamps = delivery_timestamps(3, now)

        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(len(set(stamps)), 3)

    def test_no_stamp_is_earlier_than_now(self) -> None:
        # Trừ lùi khỏi `now` thì thư đầu của đợt sau rơi vào trước thư của đợt
        # trước, và Invoice hiện ra cũ hơn cả thư hỏi giá.
        now = datetime(2026, 8, 17, 22, 0, tzinfo=UTC)

        for stamp in delivery_timestamps(5, now):
            self.assertGreaterEqual(stamp, now)

    def test_an_empty_wave_asks_for_no_stamps(self) -> None:
        self.assertEqual(delivery_timestamps(0, datetime.now(UTC)), [])

    def test_a_later_wave_lands_after_an_earlier_one(self) -> None:
        earlier = delivery_timestamps(2, datetime(2026, 8, 17, 22, 0, tzinfo=UTC))
        later = delivery_timestamps(2, datetime(2026, 8, 17, 22, 5, tzinfo=UTC))

        self.assertLess(max(earlier), min(later))


class DateShiftTest(unittest.TestCase):
    """Ba mốc cut-off và ETD/ETA phải dời theo ngày thả thư.

    Ngày trong corpus là tuyệt đối, nên đến đúng ngày cut-off thì băng đếm
    ngược hiện "ĐÃ QUÁ HẠN" và cả lô trông như đã rớt chuyến.
    """

    def setUp(self) -> None:
        self.spec = load_spec("roundtrip_rfq_hpn")
        self.shift = build_date_shift(self.spec, date(2026, 8, 18))

    def test_the_anchor_lands_the_configured_number_of_days_ahead(self) -> None:
        self.assertEqual(self.shift["2026-08-20"], "2026-08-22")

    def test_gaps_between_the_dates_are_preserved(self) -> None:
        # SI/VGM 2 ngày trước ETD, gate-in 1 ngày trước — giữ nguyên khoảng
        # cách thì thứ tự ba mốc mới còn đúng.
        shifted = [date.fromisoformat(self.shift[d]) for d in
                   ("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-29")]
        original = [date.fromisoformat(d) for d in
                    ("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-29")]
        self.assertEqual(
            [(b - a).days for a, b in zip(shifted, shifted[1:])],
            [(b - a).days for a, b in zip(original, original[1:])],
        )

    def test_replacement_happens_once_not_in_a_chain(self) -> None:
        # Thay tuần tự thì `08-18 -> 08-20` rồi `08-20 -> 08-22` biến SI
        # cut-off thành 22/08, đẩy nó ra sau cả gate-in.
        text = "SI: 2026-08-18 16:00\nGate-in: 2026-08-19 15:00\nETD: 2026-08-20"
        shifted = apply_date_shift(text, self.shift)

        self.assertIn("SI: 2026-08-20 16:00", shifted)
        self.assertIn("Gate-in: 2026-08-21 15:00", shifted)
        self.assertIn("ETD: 2026-08-22", shifted)

    def test_cutoffs_stay_before_departure(self) -> None:
        etd = date.fromisoformat(self.shift["2026-08-20"])
        for cutoff in ("2026-08-18", "2026-08-19"):
            self.assertLess(date.fromisoformat(self.shift[cutoff]), etd)

    def test_every_shifted_date_is_in_the_future(self) -> None:
        today = date(2026, 8, 18)
        for original, new in self.shift.items():
            with self.subTest(date=original):
                self.assertGreater(date.fromisoformat(new), today)

    def test_past_dates_are_left_alone(self) -> None:
        # Hoá đơn 15/08 và ngày đăng ký tờ khai 16/08 là chuyện đã xảy ra; số
        # hoá đơn INV-TL-260815 còn mã hoá sẵn ngày bên trong.
        text = "Ngày hoá đơn: 2026-08-15 · Ngày đăng ký: 2026-08-16"

        self.assertEqual(apply_date_shift(text, self.shift), text)

    def test_a_scenario_without_the_config_shifts_nothing(self) -> None:
        self.assertEqual(build_date_shift({}), {})
        self.assertEqual(apply_date_shift("ETD: 2026-08-20", {}), "ETD: 2026-08-20")


class WipeOrderTest(unittest.TestCase):
    def test_children_are_deleted_before_their_parents(self) -> None:
        # Xoá cha trước là gãy khoá ngoại giữa chừng, để lại DB nửa vời — tệ
        # hơn hẳn so với không xoá gì.
        for child, parent in (
            ("reconciliation_lines", "reconciliations"),
            ("debit_note_charges", "debit_notes"),
            ("customs_channel_history", "customs_declarations"),
            ("container_facts", "containers"),
            ("attachments", "emails"),
            ("quote_charges", "quotes"),
            ("bookings", "quotes"),
            ("containers", "shipments"),
        ):
            with self.subTest(child=child):
                self.assertLess(WIPE_ORDER.index(child), WIPE_ORDER.index(parent))

    def test_accounts_and_gmail_config_are_never_wiped(self) -> None:
        # Xoá chúng đi thì không đăng nhập lại được, và phải nối lại OAuth chỉ
        # để chạy tiếp một kịch bản demo.
        for keep in ("users", "gmail_connections", "sync_jobs", "audit_logs"):
            self.assertNotIn(keep, WIPE_ORDER)


class ScenarioFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec("roundtrip_rfq_hpn")

    def test_charge_lines_add_up_to_the_declared_total(self) -> None:
        total = sum(
            Decimal(c["unit_price"]) * Decimal(c["quantity"])
            for c in self.spec["quote"]["charges"]
        )

        self.assertEqual(total, Decimal(self.spec["quote"]["expected_total"]))

    def test_ocean_freight_unit_price_is_per_container_not_per_line(self) -> None:
        # Thư hãng tàu ghi "40HC x2 USD 2,480.00" — 2 480 là thành tiền cả
        # dòng. Để nguyên 2 480 làm đơn giá là nhân đôi cước, ra tổng 6 206.
        ocean = next(
            c for c in self.spec["quote"]["charges"] if c["charge_group"] == "ocean_freight"
        )

        self.assertEqual(Decimal(ocean["unit_price"]), Decimal("1240.00"))
        self.assertEqual(Decimal(ocean["quantity"]), Decimal("2"))

    def test_carrier_rate_is_the_buy_price_not_the_sell_price(self) -> None:
        # Chênh giữa giá mua 1 240 và giá bán 2 480 chính là biên lợi nhuận lô
        # hàng — đối soát Bước 6 đứng trên đúng hai con số này.
        self.assertEqual(Decimal(self.spec["booking"]["freight_rate"]), Decimal("1240.00"))

    def test_quote_is_marked_so_reset_can_find_it(self) -> None:
        # Không có dấu thì `--reset` hoặc không xoá được báo giá của chính nó,
        # hoặc xoá nhầm báo giá người dùng tự tạo.
        self.assertIn(SEED_MARKER, self.spec["quote"]["note"])

    def test_declaration_is_left_uncleared(self) -> None:
        # Thông quan rồi thì cảnh báo Luồng Đỏ tắt, và demo mất đúng cảnh đáng
        # xem nhất của Bước 4.
        self.assertIsNone(self.spec["customs"]["cleared_at"])
        self.assertEqual(self.spec["customs"]["channel"], "red")

    def test_route_matches_between_quote_and_booking(self) -> None:
        for field in ("pol", "pod", "container_type"):
            self.assertEqual(
                self.spec["quote"][field], self.spec["booking"][field], field
            )

    def test_every_scenario_file_declares_the_keys_the_stages_need(self) -> None:
        for path in DATA_DIR.glob("*.json"):
            with self.subTest(scenario=path.stem):
                spec = json.loads(path.read_text(encoding="utf-8"))
                for key in ("container_no", "email_filter", "email_subject_marker"):
                    self.assertIn(key, spec)
                for stage in STAGES[1:]:
                    self.assertIn(stage, spec)
                    self.assertIn("role", spec[stage])


class StageOrderTest(unittest.TestCase):
    def test_stages_run_in_business_order(self) -> None:
        # Đặt chỗ trước khi có báo giá, hay khai hải quan trước khi có
        # container, đều dựng ra một lô mà ngoài đời không tồn tại.
        self.assertEqual(STAGES, ("emails", "quote", "booking", "customs"))


class DataDirTest(unittest.TestCase):
    def test_data_dir_ships_with_the_script(self) -> None:
        self.assertTrue(DATA_DIR.is_dir())
        self.assertTrue(list(DATA_DIR.glob("*.json")))

    def test_unknown_scenario_fails_loudly(self) -> None:
        with self.assertRaises(SystemExit):
            load_spec("khong-ton-tai")


if __name__ == "__main__":
    unittest.main()
