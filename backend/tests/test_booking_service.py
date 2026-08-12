import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from db.models import BookingStatus
from services.booking_service import next_cutoff

NOW = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)


def make_booking(**overrides):
    defaults = dict(
        status=BookingStatus.CONFIRMED,
        si_cutoff_at=None,
        vgm_cutoff_at=None,
        gate_in_cutoff_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class NextCutoffTest(unittest.TestCase):
    def test_no_cutoff_set_returns_nothing(self) -> None:
        self.assertEqual(next_cutoff(make_booking(), NOW), (None, None, None))

    def test_picks_the_nearest_cutoff_still_ahead(self) -> None:
        booking = make_booking(
            si_cutoff_at=NOW + timedelta(hours=5),
            vgm_cutoff_at=NOW + timedelta(hours=2),
            gate_in_cutoff_at=NOW + timedelta(days=2),
        )

        label, at, hours = next_cutoff(booking, NOW)

        self.assertEqual(label, "VGM cut-off")
        self.assertEqual(at, NOW + timedelta(hours=2))
        self.assertEqual(hours, 2.0)

    def test_a_passed_cutoff_is_skipped_while_a_later_one_remains(self) -> None:
        booking = make_booking(
            si_cutoff_at=NOW - timedelta(hours=3),
            gate_in_cutoff_at=NOW + timedelta(hours=4),
        )

        label, _, hours = next_cutoff(booking, NOW)

        self.assertEqual(label, "Hạ container (gate-in)")
        self.assertEqual(hours, 4.0)

    def test_all_cutoffs_passed_reports_the_latest_as_overdue(self) -> None:
        # Đã trễ vẫn phải hiện, và hiện số âm — im lặng ở đây đúng bằng việc
        # giấu chuyện lô hàng đã rớt chuyến.
        booking = make_booking(
            si_cutoff_at=NOW - timedelta(hours=10),
            vgm_cutoff_at=NOW - timedelta(hours=2),
        )

        label, _, hours = next_cutoff(booking, NOW)

        self.assertEqual(label, "VGM cut-off")
        self.assertEqual(hours, -2.0)

    def test_cancelled_booking_has_no_cutoff_to_chase(self) -> None:
        booking = make_booking(
            status=BookingStatus.CANCELLED, si_cutoff_at=NOW + timedelta(hours=1)
        )

        self.assertEqual(next_cutoff(booking, NOW), (None, None, None))

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        booking = make_booking(si_cutoff_at=datetime(2026, 6, 15, 12, 0))

        _, _, hours = next_cutoff(booking, NOW)

        self.assertEqual(hours, 3.0)


if __name__ == "__main__":
    unittest.main()
