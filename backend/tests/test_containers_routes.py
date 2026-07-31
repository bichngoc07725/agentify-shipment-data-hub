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


def make_shipment(**overrides):
    defaults = dict(
        id=uuid4(),
        stage=ShipmentStage.CUSTOMS,
        sla_due_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_container(**overrides):
    defaults = dict(
        id=uuid4(),
        container_no="MSCU1234567",
        booking_no="BKG-1",
        bl_no=None,
        po_no=None,
        do_no=None,
        vessel=None,
        voyage=None,
        pol=None,
        pod=None,
        etd=None,
        eta=None,
        ata=None,
        free_time_days=None,
        status_text=None,
        source_count=1,
        attachment_count=0,
        updated_at=datetime.now(UTC),
        shipment=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class ContainerDetailShipmentSummaryTest(BaseRouteTest):
    def test_container_with_a_shipment_returns_its_stage(self) -> None:
        container = make_container(shipment=make_shipment(stage=ShipmentStage.CUSTOMS))
        with (
            patch(
                "api.routes.containers.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "api.routes.containers.get_container_related_emails",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.containers.get_container_related_attachments",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = self.client.get("/api/v1/containers/MSCU1234567", headers=bearer_header(UserRole.OPS))

        self.assertEqual(response.status_code, 200)
        shipment = response.json()["container"]["shipment"]
        self.assertIsNotNone(shipment)
        self.assertEqual(shipment["stage"], "customs")
        self.assertFalse(shipment["sla_breached"])

    def test_container_without_a_shipment_returns_null_not_500(self) -> None:
        container = make_container(shipment=None)
        with (
            patch(
                "api.routes.containers.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "api.routes.containers.get_container_related_emails",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.containers.get_container_related_attachments",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = self.client.get("/api/v1/containers/MSCU1234567", headers=bearer_header(UserRole.OPS))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["container"]["shipment"])

    def test_a_breached_sla_is_reflected_in_the_summary(self) -> None:
        container = make_container(
            shipment=make_shipment(
                stage=ShipmentStage.DOCUMENTS,
                sla_due_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
        )
        with (
            patch(
                "api.routes.containers.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "api.routes.containers.get_container_related_emails",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.containers.get_container_related_attachments",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = self.client.get("/api/v1/containers/MSCU1234567", headers=bearer_header(UserRole.OPS))

        self.assertTrue(response.json()["container"]["shipment"]["sla_breached"])


class ContainerListShipmentSummaryTest(BaseRouteTest):
    def test_list_endpoint_also_carries_the_shipment_summary(self) -> None:
        containers = [
            make_container(container_no="MSCU1234567", shipment=make_shipment()),
            make_container(container_no="TGHU7654321", shipment=None),
        ]
        with patch(
            "api.routes.containers.list_containers",
            new=AsyncMock(return_value=(containers, 2)),
        ):
            response = self.client.get("/api/v1/containers", headers=bearer_header(UserRole.OPS))

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(items[0]["shipment"]["stage"], "customs")
        self.assertIsNone(items[1]["shipment"])


if __name__ == "__main__":
    unittest.main()
