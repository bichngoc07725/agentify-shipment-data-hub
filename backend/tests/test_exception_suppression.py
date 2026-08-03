"""A resolved exception must actually leave the worklist.

`exception_actions` rows used to be write-only: the UI reported "đã xử lý"
but the exception was recomputed and reappeared on the next load. These tests
pin the rule that closes that gap — and the deliberate limit on it: an action
silences an exception only until fresher source data arrives.
"""

import unittest
from datetime import UTC, datetime, timedelta

from services.exception_service import (
    ShipmentException,
    _drop_actioned,
    _is_suppressed,
)

NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


def make_exception(code: str) -> ShipmentException:
    return ShipmentException(
        container_no="MSCU1234567",
        code=code,
        severity="warning",
        title="Sắp hết free time",
        detail="Còn 2 ngày",
        evidence=["Free time: 5 ngày"],
    )


class SuppressionRuleTest(unittest.TestCase):
    def test_no_action_means_the_exception_stays(self) -> None:
        self.assertFalse(_is_suppressed(None, NOW))

    def test_action_hides_it_when_nothing_newer_arrived(self) -> None:
        self.assertTrue(_is_suppressed(NOW, NOW - timedelta(days=1)))

    def test_action_hides_it_when_the_container_has_no_source_time(self) -> None:
        self.assertTrue(_is_suppressed(NOW, None))

    def test_fresher_source_data_brings_the_exception_back(self) -> None:
        acted_at = NOW - timedelta(days=2)
        newer_email = NOW
        self.assertFalse(_is_suppressed(acted_at, newer_email))


class DropActionedTest(unittest.TestCase):
    def test_only_the_actioned_code_is_dropped(self) -> None:
        exceptions = [make_exception("free_time_expiring"), make_exception("eta_changed")]

        remaining = _drop_actioned(
            exceptions,
            {"free_time_expiring": NOW},
            NOW - timedelta(days=1),
        )

        self.assertEqual([item.code for item in remaining], ["eta_changed"])

    def test_nothing_is_dropped_without_actions(self) -> None:
        exceptions = [make_exception("free_time_expiring")]

        remaining = _drop_actioned(exceptions, {}, NOW)

        self.assertEqual(len(remaining), 1)

    def test_an_action_on_an_unrelated_code_changes_nothing(self) -> None:
        exceptions = [make_exception("free_time_expiring")]

        remaining = _drop_actioned(exceptions, {"customs_red_channel": NOW}, None)

        self.assertEqual(len(remaining), 1)


if __name__ == "__main__":
    unittest.main()
