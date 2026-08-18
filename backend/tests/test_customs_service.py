import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.models import CustomsDeclarationCreateRequest, CustomsDeclarationUpdateRequest
from db.models import CustomsChannel, CustomsDeclaration
from services.customs_service import (
    create_declaration,
    numeric_amount,
    update_declaration,
)


class NumericAmountTest(unittest.TestCase):
    """Ô Tiền thuế trên form là `input type="number"`. Đưa vào chuỗi có chữ thì
    trình duyệt bỏ trắng ô mà không báo gì, nên tờ khai lưu xuống thiếu thuế."""

    def test_strips_currency_and_thousand_separators(self) -> None:
        self.assertEqual(numeric_amount("VND 42,150,000"), "42150000")

    def test_reads_vietnamese_grouping(self) -> None:
        self.assertEqual(numeric_amount("42.150.000 VND"), "42150000")

    def test_keeps_decimals(self) -> None:
        self.assertEqual(numeric_amount("USD 1,240.50"), "1240.50")

    def test_keeps_decimals_written_the_vietnamese_way(self) -> None:
        self.assertEqual(numeric_amount("1.240,50"), "1240.50")

    def test_text_without_a_number_yields_nothing(self) -> None:
        self.assertIsNone(numeric_amount("chưa có thông báo thuế"))

    def test_empty_yields_nothing(self) -> None:
        self.assertIsNone(numeric_amount(None))


class CreateDeclarationTest(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_container_raises_without_touching_db(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        payload = CustomsDeclarationCreateRequest(container_no="NOSUCH0000000")

        with patch(
            "services.customs_service.get_container_by_no",
            new=AsyncMock(return_value=None),
        ):
            with self.assertRaises(ValueError):
                await create_declaration(db, payload, uuid4())

        db.add.assert_not_called()

    async def test_setting_a_channel_on_create_writes_an_initial_history_row(self) -> None:
        """A declaration created straight into "Đỏ" still needs a channel
        history row so the audit trail always starts from a known baseline
        (from_channel=None), not just the first re-assignment."""
        db = AsyncMock()
        db.add = MagicMock()
        container = type("C", (), {"id": uuid4()})()
        payload = CustomsDeclarationCreateRequest(
            container_no="MSCU1234567", channel="red"
        )
        sentinel = object()

        with (
            patch(
                "services.customs_service.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "services.customs_service._prefill_hs_code",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.customs_service.get_declaration",
                new=AsyncMock(return_value=sentinel),
            ),
        ):
            result = await create_declaration(db, payload, uuid4())

        self.assertIs(result, sentinel)
        self.assertEqual(db.add.call_count, 2)
        declaration = db.add.call_args_list[0].args[0]
        history = db.add.call_args_list[1].args[0]
        self.assertEqual(declaration.channel, CustomsChannel.RED)
        self.assertIsNone(history.from_channel)
        self.assertEqual(history.to_channel, CustomsChannel.RED)
        self.assertEqual(history.reason, "Khởi tạo tờ khai")

    async def test_no_channel_on_create_writes_no_history_row(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        container = type("C", (), {"id": uuid4()})()
        payload = CustomsDeclarationCreateRequest(container_no="MSCU1234567")

        with (
            patch(
                "services.customs_service.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "services.customs_service._prefill_hs_code",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.customs_service.get_declaration",
                new=AsyncMock(return_value=object()),
            ),
        ):
            await create_declaration(db, payload, uuid4())

        self.assertEqual(db.add.call_count, 1)

    async def test_manual_hs_code_wins_over_prefill(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        container = type("C", (), {"id": uuid4()})()
        payload = CustomsDeclarationCreateRequest(
            container_no="MSCU1234567", hs_code="8471.30.90"
        )

        with (
            patch(
                "services.customs_service.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "services.customs_service._prefill_hs_code",
                new=AsyncMock(return_value="9999.99.99"),
            ) as prefill,
            patch(
                "services.customs_service.get_declaration",
                new=AsyncMock(return_value=object()),
            ),
        ):
            await create_declaration(db, payload, uuid4())

        prefill.assert_not_called()
        declaration = db.add.call_args_list[0].args[0]
        self.assertEqual(declaration.hs_code, "8471.30.90")


class UpdateDeclarationTest(unittest.IsolatedAsyncioTestCase):
    def _payload(self, **overrides) -> CustomsDeclarationUpdateRequest:
        defaults = dict(declaration_no="TK-001", declaration_type="import")
        defaults.update(overrides)
        return CustomsDeclarationUpdateRequest(**defaults)

    async def test_changing_channel_writes_a_history_row_with_correct_from_to(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        declaration = CustomsDeclaration(
            id=uuid4(), channel=CustomsChannel.GREEN
        )
        sentinel = object()

        with patch(
            "services.customs_service.get_declaration",
            new=AsyncMock(return_value=sentinel),
        ):
            result = await update_declaration(
                db, declaration, self._payload(channel="red", channel_change_reason="Bẻ luồng"), uuid4()
            )

        self.assertIs(result, sentinel)
        db.add.assert_called_once()
        history = db.add.call_args.args[0]
        self.assertEqual(history.from_channel, CustomsChannel.GREEN)
        self.assertEqual(history.to_channel, CustomsChannel.RED)
        self.assertEqual(history.reason, "Bẻ luồng")

    async def test_unchanged_channel_writes_no_history_row(self) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        declaration = CustomsDeclaration(id=uuid4(), channel=CustomsChannel.GREEN)

        with patch(
            "services.customs_service.get_declaration",
            new=AsyncMock(return_value=object()),
        ):
            await update_declaration(db, declaration, self._payload(channel="green"), uuid4())

        db.add.assert_not_called()

    async def test_clearing_channel_to_unknown_writes_no_history_row(self) -> None:
        """`to_channel` is NOT NULL in the schema, so a declaration whose
        channel is cleared back to unset must not attempt a history row."""
        db = AsyncMock()
        db.add = MagicMock()
        declaration = CustomsDeclaration(id=uuid4(), channel=CustomsChannel.GREEN)

        with patch(
            "services.customs_service.get_declaration",
            new=AsyncMock(return_value=object()),
        ):
            await update_declaration(db, declaration, self._payload(channel=None), uuid4())

        db.add.assert_not_called()
        self.assertIsNone(declaration.channel)


if __name__ == "__main__":
    unittest.main()
