import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from services.exception_service import (
    ContainerRiskProfile,
    ShipmentException,
)


def make_exception(**overrides) -> ShipmentException:
    defaults = {
        "container_no": "CSQU3054383",
        "code": "free_time_expiring",
        "severity": "critical",
        "title": "Sắp hết free time",
        "detail": "Hết free time ngày 2026-07-23.",
        "evidence": ["ATA: 2026-07-18", "Free time: 5 ngày"],
        "due_date": date(2026, 7, 23),
        "days_remaining": 3,
    }
    return ShipmentException(**{**defaults, **overrides})


class ExceptionRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_list_exceptions_returns_items_and_severity_counts(self) -> None:
        exceptions = [
            make_exception(),
            make_exception(code="missing_documents", severity="warning", days_remaining=None),
            make_exception(container_no="MSCU1234567", code="stale_no_update", severity="warning"),
        ]

        with patch(
            "api.routes.exceptions.list_shipment_exceptions", return_value=exceptions
        ):
            response = self.client.get("/api/v1/exceptions")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["counts_by_severity"], {"critical": 1, "warning": 2})
        self.assertEqual(body["items"][0]["container_no"], "CSQU3054383")
        self.assertEqual(body["items"][0]["due_date"], "2026-07-23")
        self.assertEqual(body["items"][0]["evidence"], ["ATA: 2026-07-18", "Free time: 5 ngày"])

    def test_list_exceptions_passes_filters_through(self) -> None:
        with patch(
            "api.routes.exceptions.list_shipment_exceptions", return_value=[]
        ) as mocked:
            response = self.client.get(
                "/api/v1/exceptions?severity=critical&code=arrived_no_do&limit=25"
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = mocked.call_args
        self.assertEqual(kwargs["severity"], "critical")
        self.assertEqual(kwargs["code"], "arrived_no_do")
        self.assertEqual(kwargs["limit"], 25)

    def test_limit_is_bounded(self) -> None:
        response = self.client.get("/api/v1/exceptions?limit=9999")

        self.assertEqual(response.status_code, 422)

    def test_container_risk_profile_is_returned(self) -> None:
        profile = ContainerRiskProfile(
            container_no="CSQU3054383",
            direction="import",
            exceptions=[make_exception()],
            documents_present=["arrival_notice"],
            documents_mentioned=["delivery_order"],
            documents_missing=["bill_of_lading", "delivery_order", "invoice"],
            completeness=0.25,
            free_time_expires_on=date(2026, 7, 23),
            free_time_is_assumed=False,
        )

        with patch(
            "api.routes.exceptions.get_container_by_no", return_value=object()
        ), patch(
            "api.routes.exceptions.get_container_risk_profile", return_value=profile
        ):
            response = self.client.get("/api/v1/containers/CSQU3054383/exceptions")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["direction"], "import")
        self.assertEqual(body["completeness"], 0.25)
        self.assertEqual(body["documents_missing"], ["bill_of_lading", "delivery_order", "invoice"])
        self.assertEqual(body["documents_mentioned"], ["delivery_order"])
        self.assertEqual(body["free_time_expires_on"], "2026-07-23")
        self.assertEqual(len(body["exceptions"]), 1)

    def test_unknown_container_returns_404(self) -> None:
        with patch("api.routes.exceptions.get_container_by_no", return_value=None):
            response = self.client.get("/api/v1/containers/NOSUCH0000000/exceptions")

        self.assertEqual(response.status_code, 404)

    def test_container_detail_route_still_matches_its_own_path(self) -> None:
        """The exceptions router must not shadow `/containers/{no}`."""
        with patch("api.routes.containers.get_container_by_no", return_value=None):
            response = self.client.get("/api/v1/containers/CSQU3054383")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Container not found")


if __name__ == "__main__":
    unittest.main()
