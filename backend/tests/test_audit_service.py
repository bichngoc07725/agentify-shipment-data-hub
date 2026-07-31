import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from db.models import UserRole
from services.audit_service import record_audit


class RecordAuditTest(unittest.IsolatedAsyncioTestCase):
    async def test_writes_an_entry_with_the_given_fields(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        user_id = uuid4()
        resource_id = uuid4()

        entry = await record_audit(
            db,
            user_id=user_id,
            role_used=UserRole.ADMIN,
            action="approve",
            resource_type="reconciliation",
            resource_id=resource_id,
            detail={"total_variance": "500.00"},
        )

        db.add.assert_called_once()
        added = db.add.call_args.args[0]
        self.assertIs(entry, added)
        self.assertEqual(added.user_id, user_id)
        self.assertEqual(added.role_used, UserRole.ADMIN)
        self.assertEqual(added.action, "approve")
        self.assertEqual(added.resource_type, "reconciliation")
        self.assertEqual(added.resource_id, resource_id)
        self.assertEqual(added.detail, {"total_variance": "500.00"})

    async def test_a_db_failure_is_swallowed_not_raised(self) -> None:
        """Audit logging is best-effort: it must never block the business
        action it's auditing, even if the write itself fails."""
        db = AsyncMock()
        db.add = MagicMock(side_effect=RuntimeError("boom"))

        result = await record_audit(
            db,
            user_id=uuid4(),
            role_used=UserRole.OPS,
            action="edit",
            resource_type="container_fact",
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
