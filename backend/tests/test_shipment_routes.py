import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import ShipmentStage, UserRole
from tests.auth_helpers import bearer_header
from services.shipment_service import STAGE_ORDER, StageAdvanceError, StageOwnerError




def make_shipment(**overrides):
    defaults = dict(
        id=uuid4(),
        shipment_no="JOB-2026-0001",
        customer_name="ACME",
        direction=None,
        stage=ShipmentStage.RFQ,
        quote_id=None,
        quote=None,
        owner_role=UserRole.SALES_CS,
        sla_due_at=None,
        containers=[],
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


class CreateShipmentPermissionTest(BaseRouteTest):
    def _create(self, headers: dict[str, str]):
        with patch(
            "api.routes.shipments.create_shipment",
            new=AsyncMock(return_value=make_shipment()),
        ):
            return self.client.post(
                "/api/v1/shipments", json={"customer_name": "ACME"}, headers=headers
            )

    def test_sales_cs_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "rfq")

    def test_ops_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 403)


class BoardPermissionTest(BaseRouteTest):
    def test_every_column_is_returned_in_stage_order(self) -> None:
        board = SimpleNamespace(columns={stage: [] for stage in STAGE_ORDER})
        board.columns[ShipmentStage.RFQ] = [make_shipment()]
        with patch(
            "api.routes.shipments.get_board", new=AsyncMock(return_value=board)
        ):
            response = self.client.get(
                "/api/v1/shipments/board", headers=bearer_header(UserRole.MANAGER)
            )
        self.assertEqual(response.status_code, 200)
        columns = response.json()["columns"]
        self.assertEqual([c["stage"] for c in columns], [s.value for s in STAGE_ORDER])
        self.assertEqual(len(columns[0]["jobs"]), 1)

    def test_driver_cannot_view_board(self) -> None:
        response = self.client.get(
            "/api/v1/shipments/board", headers=bearer_header(UserRole.DRIVER)
        )
        self.assertEqual(response.status_code, 403)


class AdvanceShipmentPermissionTest(BaseRouteTest):
    def _advance(self, headers: dict[str, str], side_effect=None, return_value=None):
        shipment = make_shipment()
        patches = [
            patch(
                "api.routes.shipments.get_shipment",
                new=AsyncMock(return_value=shipment),
            )
        ]
        advance_mock = AsyncMock(side_effect=side_effect, return_value=return_value)
        patches.append(patch("api.routes.shipments.advance_stage", new=advance_mock))
        with patches[0], patches[1]:
            return self.client.post(
                f"/api/v1/shipments/{shipment.id}/advance", json={}, headers=headers
            )

    def test_stage_owner_can_advance(self) -> None:
        response = self._advance(
            bearer_header(UserRole.SALES_CS),
            return_value=make_shipment(stage=ShipmentStage.BOOKING),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "booking")

    def test_non_owner_role_is_rejected_by_service_check(self) -> None:
        response = self._advance(
            bearer_header(UserRole.DOCS), side_effect=StageOwnerError("nope")
        )
        self.assertEqual(response.status_code, 403)

    def test_role_without_edit_permission_never_reaches_the_service(self) -> None:
        response = self._advance(bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 403)

    def test_already_closed_shipment_returns_400(self) -> None:
        response = self._advance(
            bearer_header(UserRole.ADMIN), side_effect=StageAdvanceError("closed")
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_shipment_is_404(self) -> None:
        with patch(
            "api.routes.shipments.get_shipment", new=AsyncMock(return_value=None)
        ):
            response = self.client.post(
                f"/api/v1/shipments/{uuid4()}/advance",
                json={},
                headers=bearer_header(UserRole.ADMIN),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
