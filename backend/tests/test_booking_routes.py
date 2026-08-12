import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import BookingStatus, UserRole
from tests.auth_helpers import bearer_header


def make_booking(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        container=SimpleNamespace(container_no="MSCU1234567"),
        quote_id=None,
        quote=None,
        booking_no="MSK-BKG-260615",
        status=BookingStatus.CONFIRMED,
        carrier="Maersk",
        vessel="MAERSK SAIGON",
        voyage="214N",
        pol="Cat Lai",
        pod="Yokohama",
        etd=None,
        eta=None,
        si_cutoff_at=None,
        vgm_cutoff_at=None,
        gate_in_cutoff_at=None,
        container_type="40HC",
        container_qty=1,
        empty_pickup_depot=None,
        freight_rate=None,
        currency="USD",
        note=None,
        created_by=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class CreateBookingPermissionTest(BaseRouteTest):
    def _create(self, headers: dict[str, str]):
        with patch(
            "api.routes.bookings.create_booking",
            new=AsyncMock(return_value=make_booking()),
        ):
            return self.client.post(
                "/api/v1/bookings",
                json={"container_no": "MSCU1234567", "carrier": "Maersk"},
                headers=headers,
            )

    def test_ops_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["booking_no"], "MSK-BKG-260615")

    def test_docs_cannot_create(self) -> None:
        self.assertEqual(self._create(bearer_header(UserRole.DOCS)).status_code, 403)

    def test_sales_cannot_create(self) -> None:
        self.assertEqual(
            self._create(bearer_header(UserRole.SALES_CS)).status_code, 403
        )

    def test_admin_cannot_create(self) -> None:
        # Đặt chỗ là việc khai thác, không phải việc quản trị — admin xem được
        # nhưng không đứng tên đặt chỗ hộ Ops.
        self.assertEqual(self._create(bearer_header(UserRole.ADMIN)).status_code, 403)

    def test_no_token_is_rejected(self) -> None:
        self.assertEqual(self._create({}).status_code, 401)


class ViewBookingPermissionTest(BaseRouteTest):
    def _list(self, headers: dict[str, str]):
        with patch(
            "api.routes.bookings.list_bookings_for_container",
            new=AsyncMock(return_value=[make_booking()]),
        ):
            return self.client.get(
                "/api/v1/containers/MSCU1234567/bookings", headers=headers
            )

    def test_sales_can_view(self) -> None:
        response = self._list(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_accountant_cannot_view(self) -> None:
        # Kế toán không nằm trong tập `booking.view` của config/permissions.py.
        self.assertEqual(
            self._list(bearer_header(UserRole.ACCOUNTANT)).status_code, 403
        )

    def test_driver_cannot_view(self) -> None:
        self.assertEqual(self._list(bearer_header(UserRole.DRIVER)).status_code, 403)


class BookingResponseShapeTest(BaseRouteTest):
    def test_next_cutoff_is_computed_on_the_response(self) -> None:
        soon = datetime.now(UTC) + timedelta(hours=6)
        booking = make_booking(si_cutoff_at=soon, vgm_cutoff_at=soon + timedelta(days=1))

        with patch(
            "api.routes.bookings.create_booking", new=AsyncMock(return_value=booking)
        ):
            response = self.client.post(
                "/api/v1/bookings",
                json={"container_no": "MSCU1234567"},
                headers=bearer_header(UserRole.OPS),
            )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["next_cutoff_label"], "SI cut-off")
        self.assertAlmostEqual(body["hours_to_next_cutoff"], 6, delta=0.1)

    def test_unknown_status_is_rejected_as_422(self) -> None:
        response = self.client.post(
            "/api/v1/bookings",
            json={"container_no": "MSCU1234567", "status": "on_the_way"},
            headers=bearer_header(UserRole.OPS),
        )
        self.assertEqual(response.status_code, 422)


class BookingWithoutContainerTest(BaseRouteTest):
    def test_ops_can_open_a_booking_before_the_carrier_assigns_a_container(self) -> None:
        # Đây là toàn bộ lý do `container_no` không còn bắt buộc: lúc gửi yêu
        # cầu đặt chỗ, hãng tàu chưa cấp container. Bắt buộc phải có nghĩa là
        # không ghi nhận được trạng thái `requested`.
        booking = make_booking(
            container_id=None, container=None, booking_no=None,
            status=BookingStatus.REQUESTED,
        )
        with patch(
            "api.routes.bookings.create_booking", new=AsyncMock(return_value=booking)
        ):
            response = self.client.post(
                "/api/v1/bookings",
                json={"carrier": "Ocean Network Express", "status": "requested"},
                headers=bearer_header(UserRole.OPS),
            )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(body["container_no"])
        self.assertEqual(body["status"], "requested")

    def test_prefill_from_quote_returns_the_shipment_particulars(self) -> None:
        quote_id = uuid4()
        with patch(
            "api.routes.bookings.get_booking_prefill_from_quote",
            new=AsyncMock(
                return_value={"pol": "Hai Phong", "pod": "Yokohama", "container_type": "40HC"}
            ),
        ):
            response = self.client.get(
                f"/api/v1/quotes/{quote_id}/booking-prefill",
                headers=bearer_header(UserRole.OPS),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pod"], "Yokohama")

    def test_prefill_from_an_unknown_quote_is_404(self) -> None:
        with patch(
            "api.routes.bookings.get_booking_prefill_from_quote",
            new=AsyncMock(return_value=None),
        ):
            response = self.client.get(
                f"/api/v1/quotes/{uuid4()}/booking-prefill",
                headers=bearer_header(UserRole.OPS),
            )

        self.assertEqual(response.status_code, 404)

    def test_sales_cannot_read_the_quote_prefill(self) -> None:
        with patch(
            "api.routes.bookings.get_booking_prefill_from_quote",
            new=AsyncMock(return_value={}),
        ):
            response = self.client.get(
                f"/api/v1/quotes/{uuid4()}/booking-prefill",
                headers=bearer_header(UserRole.SALES_CS),
            )

        self.assertEqual(response.status_code, 403)


class BookingPrefillTest(BaseRouteTest):
    def test_prefill_returns_what_extraction_already_read(self) -> None:
        with patch(
            "api.routes.bookings.get_booking_prefill",
            new=AsyncMock(return_value={"booking_no": "MSK-BKG-260615"}),
        ):
            response = self.client.get(
                "/api/v1/containers/MSCU1234567/booking-prefill",
                headers=bearer_header(UserRole.OPS),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"booking_no": "MSK-BKG-260615"})

    def test_unknown_container_is_404(self) -> None:
        with patch(
            "api.routes.bookings.get_booking_prefill",
            new=AsyncMock(side_effect=ValueError("Container 'NOPE' not found")),
        ):
            response = self.client.get(
                "/api/v1/containers/NOPE/booking-prefill",
                headers=bearer_header(UserRole.OPS),
            )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
