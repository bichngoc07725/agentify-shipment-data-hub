import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

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



class AttachContainerRefreshTest(unittest.IsolatedAsyncioTestCase):
    async def test_attaching_a_container_updates_the_loaded_relationship(self) -> None:
        # Session đặt `expire_on_commit=False`: chỉ gán khoá ngoại thì quan hệ
        # `container` đã nạp là None ở nguyên None, và phản hồi trả về báo chưa
        # có container dù DB đã đúng.
        from unittest.mock import AsyncMock, patch

        from api.models import BookingUpdateRequest
        from services import booking_service

        booking = SimpleNamespace(
            id=uuid4(), container_id=None, container=None, quote_id=None,
            status=BookingStatus.REQUESTED,
        )
        container = SimpleNamespace(id=uuid4(), container_no="ONEU7041287")

        with patch.object(
            booking_service, "get_booking", new=AsyncMock(return_value=booking)
        ), patch.object(
            booking_service, "get_container_by_no", new=AsyncMock(return_value=container)
        ), patch.object(booking_service, "_apply"):
            db = AsyncMock()
            await booking_service.update_booking(
                db, booking.id, BookingUpdateRequest(container_no="ONEU7041287")
            )

        self.assertEqual(booking.container_id, container.id)
        self.assertIs(booking.container, container)

class LinkQuoteToContainerTest(unittest.IsolatedAsyncioTestCase):
    """Chỗ đặt là bản ghi DUY NHẤT cầm cả `quote_id` lẫn `container_id`.

    Không truyền quan hệ đó sang báo giá thì `quotes.container_id` mãi rỗng, và
    Bước 6 — vốn tra báo giá THEO CONTAINER — báo "container chưa có báo giá
    nào" dù báo giá nằm ngay đó. Đối soát mất mốc để so.
    """

    async def _run(self, quote_container_id, booking_quote_id=None):
        from unittest.mock import AsyncMock, MagicMock

        from services import booking_service

        quote = SimpleNamespace(id=uuid4(), container_id=quote_container_id)
        booking = SimpleNamespace(
            quote_id=booking_quote_id if booking_quote_id is not None else quote.id,
            container_id=uuid4(),
        )
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = quote
        db.execute.return_value = result

        await booking_service._link_quote_to_container(db, booking)
        return quote, booking

    async def test_an_unlinked_quote_gets_the_container(self) -> None:
        quote, booking = await self._run(quote_container_id=None)

        self.assertEqual(quote.container_id, booking.container_id)

    async def test_a_quote_already_pointing_elsewhere_is_left_alone(self) -> None:
        # Trỏ sang container khác là chuyện người dùng cố ý; đè lên là âm thầm
        # đổi hồ sơ mà không ai yêu cầu.
        existing = uuid4()
        quote, _ = await self._run(quote_container_id=existing)

        self.assertEqual(quote.container_id, existing)

    async def test_a_booking_without_a_quote_touches_nothing(self) -> None:
        from unittest.mock import AsyncMock

        from services import booking_service

        db = AsyncMock()
        await booking_service._link_quote_to_container(
            db, SimpleNamespace(quote_id=None, container_id=uuid4())
        )

        db.execute.assert_not_awaited()

    async def test_a_booking_without_a_container_touches_nothing(self) -> None:
        # Đúng trạng thái 2.1: đã gửi yêu cầu, hãng tàu chưa cấp container.
        from unittest.mock import AsyncMock

        from services import booking_service

        db = AsyncMock()
        await booking_service._link_quote_to_container(
            db, SimpleNamespace(quote_id=uuid4(), container_id=None)
        )

        db.execute.assert_not_awaited()


CONFIRMATION_BODY = """Dear Agentify,

We are pleased to confirm your booking as follows.

Booking No       : ONE-BKG-260805
Container No     : ONEU7041287
Vessel / Voyage  : ONE COMMITMENT 145E
Port of loading  : Hai Phong
Port of discharge: Yokohama
ETD              : 2026-08-20
ETA              : 2026-08-29

CUT-OFF TIMES:
  SI cut-off       : 2026-08-18 16:00 (GMT+7)
  VGM cut-off      : 2026-08-18 10:00 (GMT+7)
  Gate-in cut-off  : 2026-08-19 15:00 (GMT+7)

Empty pick-up depot: Nam Hai Dinh Vu depot, Hai Phong
"""


class PrefillFromEmailTest(unittest.IsolatedAsyncioTestCase):
    """Bước 2.4. Chỗ đặt lúc này chưa gắn container (2.1 cố ý để trống vì hãng
    tàu chưa cấp), nên `container_facts` không tra được và báo giá thì không
    bao giờ biết số booking lẫn ba mốc cut-off."""

    async def _prefill(self, body: str, subject: str = "BOOKING CONFIRMATION"):
        from unittest.mock import AsyncMock, MagicMock

        from services import booking_service

        email = SimpleNamespace(
            id=uuid4(), subject=subject, body_text=body,
            from_email="booking@one-line.com", attachments=[],
        )
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = email
        db.execute.return_value = result
        return await booking_service.get_booking_prefill_from_email(db, email.id)

    async def test_reads_every_field_the_update_form_asks_for(self) -> None:
        prefill = await self._prefill(CONFIRMATION_BODY)

        self.assertEqual(prefill["booking_no"], "ONE-BKG-260805")
        self.assertEqual(prefill["container_no"], "ONEU7041287")
        self.assertEqual(prefill["vessel"], "ONE COMMITMENT")
        self.assertEqual(prefill["voyage"], "145E")
        self.assertEqual(prefill["si_cutoff_at"], "2026-08-18T16:00")
        self.assertEqual(prefill["vgm_cutoff_at"], "2026-08-18T10:00")
        self.assertEqual(prefill["gate_in_cutoff_at"], "2026-08-19T15:00")
        self.assertEqual(prefill["empty_pickup_depot"], "Nam Hai Dinh Vu depot, Hai Phong")

    async def test_freight_rate_is_never_guessed(self) -> None:
        # Giá cước là giá MUA, thư xác nhận không nói, và chênh giữa nó với giá
        # bán chính là biên lợi nhuận lô hàng — đoán một con số ở đây làm hỏng
        # đối soát Bước 6.
        self.assertNotIn("freight_rate", await self._prefill(CONFIRMATION_BODY))

    async def test_a_mail_naming_two_containers_fills_neither(self) -> None:
        # Không có căn cứ chọn cái nào, và gắn nhầm số container vào chỗ đặt là
        # loại lỗi phải lần ngược từ cảng mới phát hiện.
        prefill = await self._prefill(
            "Rolled containers: ONEU7041287 and TCLU1234563 both moved to 146E."
        )

        self.assertNotIn("container_no", prefill)

    async def test_missing_email_is_distinguished_from_an_empty_read(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from services import booking_service

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        self.assertIsNone(
            await booking_service.get_booking_prefill_from_email(db, uuid4())
        )

    async def test_an_unrelated_mail_yields_nothing_rather_than_noise(self) -> None:
        prefill = await self._prefill("Chào bạn, tuần sau mình gửi chứng từ nhé.", "Hỏi thăm")

        self.assertEqual(prefill, {})


if __name__ == "__main__":
    unittest.main()
