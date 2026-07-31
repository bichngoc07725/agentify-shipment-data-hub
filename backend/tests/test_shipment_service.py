import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.models import ShipmentCreateRequest
from db.models import Shipment, ShipmentStage, UserRole
from services.shipment_service import (
    STAGE_ORDER,
    StageAdvanceError,
    StageOwnerError,
    advance_stage,
    build_shipment_no,
    can_advance,
    create_shipment,
    is_sla_breached,
    move_to_stage,
    next_stage,
    owner_role_for,
    sla_due_at_for,
)


class ShipmentNoTest(unittest.TestCase):
    def test_first_job_of_the_year_is_sequence_one(self) -> None:
        self.assertEqual(build_shipment_no(2026, 1), "JOB-2026-0001")

    def test_sequence_is_zero_padded_to_four_digits(self) -> None:
        self.assertEqual(build_shipment_no(2026, 42), "JOB-2026-0042")


class NextStageTest(unittest.TestCase):
    def test_walks_every_stage_in_order(self) -> None:
        for current, expected in zip(STAGE_ORDER, STAGE_ORDER[1:]):
            with self.subTest(current=current):
                self.assertEqual(next_stage(current), expected)

    def test_closed_has_no_next_stage(self) -> None:
        self.assertIsNone(next_stage(ShipmentStage.CLOSED))


class OwnerAndSlaConfigTest(unittest.TestCase):
    def test_documents_stage_is_owned_by_docs_with_a_48h_sla(self) -> None:
        """The brief's own worked example: documents → docs → 48h."""
        self.assertEqual(owner_role_for(ShipmentStage.DOCUMENTS), UserRole.DOCS)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(
            sla_due_at_for(ShipmentStage.DOCUMENTS, now), now + timedelta(hours=48)
        )

    def test_closed_stage_has_no_owner_or_sla(self) -> None:
        self.assertIsNone(owner_role_for(ShipmentStage.CLOSED))
        self.assertIsNone(sla_due_at_for(ShipmentStage.CLOSED, datetime.now(UTC)))


class SlaBreachedTest(unittest.TestCase):
    def test_past_due_open_stage_is_breached(self) -> None:
        shipment = Shipment(
            stage=ShipmentStage.DOCUMENTS,
            sla_due_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        self.assertTrue(is_sla_breached(shipment, now=datetime(2026, 1, 1, tzinfo=UTC)))

    def test_not_yet_due_is_not_breached(self) -> None:
        shipment = Shipment(
            stage=ShipmentStage.DOCUMENTS,
            sla_due_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        self.assertFalse(is_sla_breached(shipment, now=datetime(2026, 1, 1, tzinfo=UTC)))

    def test_closed_job_is_never_breached_even_past_its_old_due_date(self) -> None:
        shipment = Shipment(
            stage=ShipmentStage.CLOSED, sla_due_at=datetime(2020, 1, 1, tzinfo=UTC)
        )
        self.assertFalse(is_sla_breached(shipment, now=datetime(2026, 1, 1, tzinfo=UTC)))

    def test_no_due_date_is_not_breached(self) -> None:
        shipment = Shipment(stage=ShipmentStage.DOCUMENTS, sla_due_at=None)
        self.assertFalse(is_sla_breached(shipment))


class CanAdvanceTest(unittest.TestCase):
    def test_the_stage_owner_can_advance(self) -> None:
        shipment = Shipment(owner_role=UserRole.DOCS)
        self.assertTrue(can_advance(shipment, UserRole.DOCS))

    def test_a_different_role_cannot_advance(self) -> None:
        shipment = Shipment(owner_role=UserRole.DOCS)
        self.assertFalse(can_advance(shipment, UserRole.SALES_CS))

    def test_admin_and_manager_can_always_advance(self) -> None:
        shipment = Shipment(owner_role=UserRole.DOCS)
        self.assertTrue(can_advance(shipment, UserRole.ADMIN))
        self.assertTrue(can_advance(shipment, UserRole.MANAGER))


class CreateShipmentTest(unittest.IsolatedAsyncioTestCase):
    async def test_new_shipment_starts_at_rfq_owned_by_sales_cs(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one=MagicMock(return_value=0))
        )
        sentinel = object()
        payload = ShipmentCreateRequest(customer_name="ACME")

        with patch(
            "services.shipment_service.get_shipment",
            new=AsyncMock(return_value=sentinel),
        ):
            result = await create_shipment(db, payload)

        self.assertIs(result, sentinel)
        shipment = db.add.call_args.args[0]
        self.assertEqual(shipment.stage, ShipmentStage.RFQ)
        self.assertEqual(shipment.owner_role, UserRole.SALES_CS)
        self.assertIsNotNone(shipment.sla_due_at)
        self.assertTrue(shipment.shipment_no.startswith("JOB-"))


class AdvanceStageTest(unittest.IsolatedAsyncioTestCase):
    async def test_owner_advances_to_the_next_stage_and_gets_new_sla(self) -> None:
        db = AsyncMock()
        shipment = Shipment(
            id=uuid4(),
            stage=ShipmentStage.RFQ,
            owner_role=UserRole.SALES_CS,
            sla_due_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        sentinel = object()

        with patch(
            "services.shipment_service.get_shipment",
            new=AsyncMock(return_value=sentinel),
        ):
            result = await advance_stage(db, shipment, UserRole.SALES_CS)

        self.assertIs(result, sentinel)
        self.assertEqual(shipment.stage, ShipmentStage.BOOKING)
        self.assertEqual(shipment.owner_role, UserRole.OPS)
        self.assertGreater(shipment.sla_due_at, datetime.now(UTC))

    async def test_non_owner_role_is_rejected(self) -> None:
        db = AsyncMock()
        shipment = Shipment(
            id=uuid4(), stage=ShipmentStage.RFQ, owner_role=UserRole.SALES_CS
        )

        with self.assertRaises(StageOwnerError):
            await advance_stage(db, shipment, UserRole.DOCS)

    async def test_a_closed_shipment_cannot_advance_further(self) -> None:
        db = AsyncMock()
        shipment = Shipment(
            id=uuid4(), stage=ShipmentStage.CLOSED, owner_role=None
        )

        with self.assertRaises(StageAdvanceError):
            await advance_stage(db, shipment, UserRole.ADMIN)


if __name__ == "__main__":
    unittest.main()



class MoveToStageTest(unittest.IsolatedAsyncioTestCase):
    """`move_to_stage` backs the Kanban drag: any column, either direction,
    gated by the same stage-owner rule as `advance_stage`."""

    @staticmethod
    def _shipment(stage: ShipmentStage) -> Shipment:
        return Shipment(
            id=uuid4(),
            stage=stage,
            owner_role=owner_role_for(stage),
            sla_due_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

    async def test_owner_can_drag_a_job_backwards(self) -> None:
        db = AsyncMock()
        shipment = self._shipment(ShipmentStage.CUSTOMS)

        with patch(
            "services.shipment_service.get_shipment",
            new=AsyncMock(return_value=shipment),
        ):
            await move_to_stage(db, shipment, ShipmentStage.DOCUMENTS, UserRole.OPS)

        self.assertEqual(shipment.stage, ShipmentStage.DOCUMENTS)
        # Ownership and SLA follow the column the card landed in.
        self.assertEqual(shipment.owner_role, UserRole.DOCS)
        self.assertNotEqual(shipment.sla_due_at, datetime(2020, 1, 1, tzinfo=UTC))

    async def test_owner_can_drag_across_several_columns(self) -> None:
        db = AsyncMock()
        shipment = self._shipment(ShipmentStage.RFQ)

        with patch(
            "services.shipment_service.get_shipment",
            new=AsyncMock(return_value=shipment),
        ):
            await move_to_stage(db, shipment, ShipmentStage.DELIVERY, UserRole.SALES_CS)

        self.assertEqual(shipment.stage, ShipmentStage.DELIVERY)

    async def test_a_role_that_does_not_own_the_stage_is_refused(self) -> None:
        db = AsyncMock()
        shipment = self._shipment(ShipmentStage.CUSTOMS)

        with self.assertRaises(StageOwnerError):
            await move_to_stage(
                db, shipment, ShipmentStage.DELIVERY, UserRole.ACCOUNTANT
            )

        self.assertEqual(shipment.stage, ShipmentStage.CUSTOMS)

    async def test_dropping_a_card_back_on_its_own_column_changes_nothing(self) -> None:
        db = AsyncMock()
        shipment = self._shipment(ShipmentStage.BOOKING)
        original_sla = shipment.sla_due_at

        with patch(
            "services.shipment_service.get_shipment",
            new=AsyncMock(return_value=shipment),
        ):
            await move_to_stage(db, shipment, ShipmentStage.BOOKING, UserRole.OPS)

        self.assertEqual(shipment.stage, ShipmentStage.BOOKING)
        self.assertEqual(shipment.sla_due_at, original_sla)
