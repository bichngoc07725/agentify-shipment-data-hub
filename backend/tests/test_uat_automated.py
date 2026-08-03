"""UAT automated suite — 5 test cases per feature area.

Mục đích: bộ test tự động (chạy bằng `pytest` hoặc `python -m unittest`) kiểm tra
LỚP PHÂN QUYỀN (RBAC) và các nhánh cơ bản (200 / 403 / 404 / 422) của từng phần
trong hệ thống. Bám đúng khung test sẵn có của repo (xem `tests/test_quote_routes.py`):

- Không cần DB thật: `get_db` được override thành `None`, mọi service được
  `patch` bằng `AsyncMock`. Vì `require_permission` chặn TRƯỚC khi gọi service,
  các ca 403 không cần mock gì cả — đó là phần chắc chắn nhất.
- Token JWT tạo bằng `create_access_token(FakeUser(role))`, đúng như suite gốc.
- **Chỉ mock ở ranh giới service/DB, KHÔNG mock `_to_response` của chính route.**
  Mock hàm serialize của route sẽ biến ca 200 thành "chỉ kiểm tra cổng RBAC mở"
  và giấu đi đúng loại lỗi đã thực sự xảy ra ở GĐ7 (enum trả `.name` thay vì
  `.value`, quan hệ ORM đọc phải bản cũ). Vì vậy service mock luôn trả về một
  object có hình dạng thật (enum thật, list quan hệ thật) để serializer thật chạy.

Mỗi lớp `*Test` là MỘT phần, có 5 phương thức `test_*` (5 test case).
Chạy riêng:  pytest backend/tests/test_uat_automated.py -v
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import (
    CustomsChannel,
    CustomsDeclarationType,
    ReconciliationMatchStatus,
    ReconciliationStatus,
    ShipmentStage,
    UserRole,
)
from services.auth_service import create_access_token

NOW = datetime.now(UTC)
CONTAINER_NO = "MSCU1234567"


class FakeUser:
    """Giống suite gốc: đủ thuộc tính để `create_access_token` ký token."""

    def __init__(self, role: UserRole) -> None:
        self.id = uuid4()
        self.username = "tester"
        self.display_name = "Tester"
        self.role = role


def bearer(role: UserRole) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(FakeUser(role))}"}


ALL_ROLES = [
    UserRole.ADMIN, UserRole.MANAGER, UserRole.SALES_CS,
    UserRole.DOCS, UserRole.OPS, UserRole.ACCOUNTANT, UserRole.DRIVER,
]


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 1 — Auth / Login
# ─────────────────────────────────────────────────────────────────────────────
class AuthLoginTest(BaseRouteTest):
    URL = "/api/v1/auth/login"

    def test_login_success_returns_token_and_single_role(self) -> None:
        with patch(
            "api.routes.auth.authenticate_user",
            new=AsyncMock(return_value=FakeUser(UserRole.SALES_CS)),
        ):
            r = self.client.post(self.URL, json={"username": "sales", "password": "sales@123"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["access_token"])
        self.assertEqual(body["role"], "sales_cs")

    def test_login_wrong_password_is_401(self) -> None:
        with patch("api.routes.auth.authenticate_user", new=AsyncMock(return_value=None)):
            r = self.client.post(self.URL, json={"username": "sales", "password": "wrong"})
        self.assertEqual(r.status_code, 401)

    def test_login_ops_role_in_token_payload(self) -> None:
        with patch(
            "api.routes.auth.authenticate_user",
            new=AsyncMock(return_value=FakeUser(UserRole.OPS)),
        ):
            r = self.client.post(self.URL, json={"username": "ops", "password": "ops@123"})
        self.assertEqual(r.json()["role"], "ops")

    def test_login_missing_field_is_422(self) -> None:
        r = self.client.post(self.URL, json={"username": "sales"})
        self.assertEqual(r.status_code, 422)

    def test_login_driver_role(self) -> None:
        with patch(
            "api.routes.auth.authenticate_user",
            new=AsyncMock(return_value=FakeUser(UserRole.DRIVER)),
        ):
            r = self.client.post(self.URL, json={"username": "taixe", "password": "taixe@123"})
        self.assertEqual(r.json()["role"], "driver")


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 2 — Ma trận quyền (admin)
# ─────────────────────────────────────────────────────────────────────────────
class AdminPermissionMatrixTest(BaseRouteTest):
    URL = "/api/v1/admin/permissions"

    def test_admin_can_view_matrix(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 200)
        self.assertIn("matrix", r.json())

    def test_manager_can_view_matrix(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.MANAGER))
        self.assertEqual(r.status_code, 200)

    def test_matrix_contains_known_resource(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.ADMIN))
        self.assertIn("quote", r.json()["matrix"])

    def test_sales_cannot_view_matrix(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 403)

    def test_no_token_is_401(self) -> None:
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 401)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 3 — Quote (RFQ/báo giá)
# ─────────────────────────────────────────────────────────────────────────────
QUOTE_PAYLOAD = {
    "customer_name": "Công ty TNHH Minh Phát",
    "pol": "Shanghai",
    "pod": "Ho Chi Minh City",
    "container_type": "40HC",
    "container_qty": 2,
    "charges": [
        {"charge_group": "ocean_freight", "charge_code": "OF", "unit_price": "1200", "quantity": "2"},
    ],
}


class QuotePermissionTest(BaseRouteTest):
    URL = "/api/v1/quotes"

    def test_sales_can_create(self) -> None:
        with patch(
            "api.routes.quotes.create_quote",
            new=AsyncMock(return_value=SimpleNamespace(
                id=uuid4(), quote_no="QUOTE-2026-0001", customer_name="Công ty TNHH Minh Phát",
                status=SimpleNamespace(value="draft"), pol="Shanghai", pod="Ho Chi Minh City", commodity=None,
                is_dangerous=False, is_reefer=False, container_type="40HC", container_qty=2,
                gross_weight_kg=None, cargo_ready_date=None, incoterm=None, payment_term=None,
                transit_time=None, valid_until=None, note=None, currency="USD",
                created_by=uuid4(), container_id=None, container=None, charges=[],
                created_at=NOW, updated_at=None,
            )),
        ):
            r = self.client.post(self.URL, json=QUOTE_PAYLOAD, headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 200)

    def test_docs_cannot_create(self) -> None:
        r = self.client.post(self.URL, json=QUOTE_PAYLOAD, headers=bearer(UserRole.DOCS))
        self.assertEqual(r.status_code, 403)

    def test_admin_cannot_create(self) -> None:
        r = self.client.post(self.URL, json=QUOTE_PAYLOAD, headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 403)

    def test_ops_can_view_list(self) -> None:
        with patch("api.routes.quotes.list_quotes", new=AsyncMock(return_value=([], 0))):
            r = self.client.get(self.URL, headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)

    def test_driver_cannot_view_list(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.DRIVER))
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 4 — Container facts (sửa 2 lớp quyền: role + nhóm field)
# ─────────────────────────────────────────────────────────────────────────────
def _fact(field_name: str):
    return SimpleNamespace(
        id=uuid4(), field_name=field_name, field_value="OLD", normalized_value=None,
        source_type="manual", source_label=None, document_type=None, confidence=None,
        source_sent_at=None, email_id=None, attachment_id=None,
    )


class ContainerFactEditTest(BaseRouteTest):
    def _url(self, fact_id) -> str:
        return f"/api/v1/containers/{CONTAINER_NO}/facts/{fact_id}"

    def _patch_stack(self, field_name: str):
        """Mock đủ để chạm tới bước kiểm tra nhóm field trong route."""
        fact = _fact(field_name)
        return fact, [
            patch("api.routes.containers.get_container_by_no",
                  new=AsyncMock(return_value=SimpleNamespace(id=uuid4()))),
            patch("api.routes.containers.get_container_fact_by_id",
                  new=AsyncMock(return_value=fact)),
            patch("api.routes.containers.update_container_fact",
                  new=AsyncMock(return_value=fact)),
            patch("api.routes.containers.record_audit", new=AsyncMock(return_value=None)),
        ]

    def test_docs_can_edit_document_field_bl_no(self) -> None:
        fact, mocks = self._patch_stack("bl_no")
        for m in mocks: m.start()
        try:
            r = self.client.patch(self._url(fact.id), json={"field_value": "NEWBL"},
                                  headers=bearer(UserRole.DOCS))
        finally:
            for m in mocks: m.stop()
        self.assertEqual(r.status_code, 200)

    def test_docs_cannot_edit_operation_field_eta(self) -> None:
        fact, mocks = self._patch_stack("eta")
        for m in mocks: m.start()
        try:
            r = self.client.patch(self._url(fact.id), json={"field_value": "2026-08-20"},
                                  headers=bearer(UserRole.DOCS))
        finally:
            for m in mocks: m.stop()
        self.assertEqual(r.status_code, 403)

    def test_ops_can_edit_operation_field_eta(self) -> None:
        fact, mocks = self._patch_stack("eta")
        for m in mocks: m.start()
        try:
            r = self.client.patch(self._url(fact.id), json={"field_value": "2026-08-20"},
                                  headers=bearer(UserRole.OPS))
        finally:
            for m in mocks: m.stop()
        self.assertEqual(r.status_code, 200)

    def test_accountant_can_edit_finance_field_invoice_amount(self) -> None:
        fact, mocks = self._patch_stack("invoice_amount")
        for m in mocks: m.start()
        try:
            r = self.client.patch(self._url(fact.id), json={"field_value": "1250"},
                                  headers=bearer(UserRole.ACCOUNTANT))
        finally:
            for m in mocks: m.stop()
        self.assertEqual(r.status_code, 200)

    def test_sales_cannot_edit_any_fact(self) -> None:
        # Sales không có quyền container_facts.edit → 403 ngay ở lớp 1 (không cần mock).
        r = self.client.patch(self._url(uuid4()), json={"field_value": "X"},
                              headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 5 — Customs (hải quan)
# ─────────────────────────────────────────────────────────────────────────────
CUSTOMS_PAYLOAD = {
    "container_no": CONTAINER_NO,
    "declaration_no": "103876540210",
    "declaration_type": "import",
    "channel": "red",
    "hs_code": "5407.10",
}


def _fake_declaration(channel=CustomsChannel.RED):
    """Hình dạng thật của `CustomsDeclaration` đã load quan hệ: enum thật cho
    `declaration_type`/`channel`, và `channel_history` là list object thật."""
    return SimpleNamespace(
        id=uuid4(), container_id=uuid4(),
        container=SimpleNamespace(container_no=CONTAINER_NO),
        declaration_no="103876540210",
        declaration_type=CustomsDeclarationType.IMPORT,
        channel=channel,
        hs_code="5407.10", registered_at=None, cleared_at=None,
        tax_amount=Decimal("12500000.00"), note=None, created_by=uuid4(),
        channel_history=[
            SimpleNamespace(
                id=uuid4(), from_channel=None, to_channel=CustomsChannel.GREEN,
                changed_at=NOW, changed_by=uuid4(), reason="Khởi tạo tờ khai",
            ),
            SimpleNamespace(
                id=uuid4(), from_channel=CustomsChannel.GREEN, to_channel=channel,
                changed_at=NOW, changed_by=uuid4(), reason="Bẻ luồng",
            ),
        ],
        created_at=NOW, updated_at=None,
    )


class CustomsPermissionTest(BaseRouteTest):
    URL = "/api/v1/customs/declarations"

    def test_ops_can_create(self) -> None:
        with patch(
            "api.routes.customs.create_declaration",
            new=AsyncMock(return_value=_fake_declaration()),
        ):
            r = self.client.post(self.URL, json=CUSTOMS_PAYLOAD, headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # `.value` chứ không phải `.name`: phải là "red"/"import", không phải "RED"/"IMPORT".
        self.assertEqual(body["channel"], "red")
        self.assertEqual(body["declaration_type"], "import")
        self.assertEqual(body["container_no"], CONTAINER_NO)

    def test_docs_cannot_create(self) -> None:
        r = self.client.post(self.URL, json=CUSTOMS_PAYLOAD, headers=bearer(UserRole.DOCS))
        self.assertEqual(r.status_code, 403)

    def test_driver_cannot_create(self) -> None:
        r = self.client.post(self.URL, json=CUSTOMS_PAYLOAD, headers=bearer(UserRole.DRIVER))
        self.assertEqual(r.status_code, 403)

    def test_accountant_can_view_with_channel_history(self) -> None:
        """Lịch sử bẻ luồng là bằng chứng nghiệp vụ — phải serialize đúng
        from/to, và `from_channel=None` (dòng khởi tạo) không được làm vỡ."""
        with patch(
            "api.routes.customs.get_declaration",
            new=AsyncMock(return_value=_fake_declaration()),
        ):
            r = self.client.get(f"{self.URL}/{uuid4()}", headers=bearer(UserRole.ACCOUNTANT))
        self.assertEqual(r.status_code, 200)
        history = r.json()["channel_history"]
        self.assertEqual(len(history), 2)
        self.assertIsNone(history[0]["from_channel"])
        self.assertEqual(history[0]["to_channel"], "green")
        self.assertEqual(history[1]["from_channel"], "green")
        self.assertEqual(history[1]["to_channel"], "red")

    def test_view_unknown_declaration_is_404(self) -> None:
        with patch("api.routes.customs.get_declaration", new=AsyncMock(return_value=None)):
            r = self.client.get(f"{self.URL}/{uuid4()}", headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 6 — Reconciliation (đối soát chi phí)
# ─────────────────────────────────────────────────────────────────────────────
def _fake_reconciliation(status=ReconciliationStatus.ESCALATED):
    """Hình dạng thật của `Reconciliation` đã load quan hệ container/quote/lines."""
    return SimpleNamespace(
        id=uuid4(), container_id=uuid4(),
        container=SimpleNamespace(container_no=CONTAINER_NO),
        quote_id=uuid4(), quote=SimpleNamespace(quote_no="QUOTE-2026-0001"),
        status=status,
        total_quoted=Decimal("2935.00"), total_actual=Decimal("3185.00"),
        total_variance=Decimal("250.00"), needs_approval=True,
        created_by=uuid4(), approved_by=None,
        lines=[
            SimpleNamespace(
                id=uuid4(), charge_code="OF", quoted_amount=Decimal("2400.00"),
                actual_amount=Decimal("2650.00"), variance=Decimal("250.00"),
                match_status=ReconciliationMatchStatus.VARIANCE, note=None,
            ),
            SimpleNamespace(
                id=uuid4(), charge_code="CIC", quoted_amount=None,
                actual_amount=Decimal("45.00"), variance=Decimal("45.00"),
                match_status=ReconciliationMatchStatus.EXTRA_ACTUAL, note="Phát sinh",
            ),
        ],
        created_at=NOW,
    )


class ReconciliationPermissionTest(BaseRouteTest):
    URL = "/api/v1/reconciliation"

    def test_accountant_can_create(self) -> None:
        with patch(
            "api.routes.reconciliation.build_reconciliation",
            new=AsyncMock(return_value=_fake_reconciliation()),
        ):
            r = self.client.post(self.URL, json={"container_no": CONTAINER_NO, "quote_id": str(uuid4())},
                                 headers=bearer(UserRole.ACCOUNTANT))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "escalated")
        # Khoản phát sinh ngoài báo giá — đúng thứ nghiệp vụ cần nhìn thấy.
        self.assertEqual(body["lines"][1]["match_status"], "extra_actual")
        self.assertIsNone(body["lines"][1]["quoted_amount"])

    def test_sales_cannot_create(self) -> None:
        r = self.client.post(self.URL, json={"container_no": CONTAINER_NO, "quote_id": str(uuid4())},
                             headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        r = self.client.get(f"{self.URL}/{uuid4()}", headers=bearer(UserRole.DRIVER))
        self.assertEqual(r.status_code, 403)

    def test_admin_can_approve(self) -> None:
        with (
            patch("api.routes.reconciliation.get_reconciliation",
                  new=AsyncMock(return_value=_fake_reconciliation())),
            patch("api.routes.reconciliation.approve_reconciliation",
                  new=AsyncMock(return_value=_fake_reconciliation(ReconciliationStatus.APPROVED))),
            patch("api.routes.reconciliation.record_audit", new=AsyncMock(return_value=None)),
        ):
            r = self.client.post(f"{self.URL}/{uuid4()}/approve", json={},
                                 headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "approved")

    def test_accountant_cannot_approve(self) -> None:
        # Duyệt khoản chênh lệch là quyền admin/manager, không phải người tạo.
        r = self.client.post(f"{self.URL}/{uuid4()}/approve", json={},
                             headers=bearer(UserRole.ACCOUNTANT))
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 7 — Shipment / Kanban
# ─────────────────────────────────────────────────────────────────────────────
def _fake_shipment(stage=ShipmentStage.BOOKING, sla_due_at=None, owner_role=UserRole.OPS):
    """Hình dạng thật của `Shipment`. `stage`/`owner_role` là enum thật để
    `_to_response` chạy đúng `.value`, và `sla_due_at` để hàm thật
    `is_sla_breached()` tự tính — không hardcode `sla_breached`."""
    return SimpleNamespace(
        id=uuid4(), shipment_no="JOB-2026-0001", customer_name="Công ty TNHH Minh Phát",
        direction=CustomsDeclarationType.IMPORT,  # Shipment.direction dùng lại enum này
        stage=stage, quote_id=None, quote=None, owner_role=owner_role,
        sla_due_at=sla_due_at,
        containers=[SimpleNamespace(container_no=CONTAINER_NO)],
        created_at=NOW, updated_at=None,
    )


class ShipmentPermissionTest(BaseRouteTest):
    URL = "/api/v1/shipments"

    def test_ops_can_create_job(self) -> None:
        with patch(
            "api.routes.shipments.create_shipment",
            new=AsyncMock(return_value=_fake_shipment(ShipmentStage.RFQ, owner_role=UserRole.SALES_CS)),
        ):
            r = self.client.post(self.URL, json={"customer_name": "Minh Phát", "container_nos": [CONTAINER_NO]},
                                 headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["stage"], "rfq")
        self.assertEqual(body["owner_role"], "sales_cs")
        self.assertEqual(body["container_nos"], [CONTAINER_NO])
        self.assertEqual(body["container_count"], 1)

    def test_driver_cannot_view_board(self) -> None:
        r = self.client.get(f"{self.URL}/board", headers=bearer(UserRole.DRIVER))
        self.assertEqual(r.status_code, 403)

    def test_manager_can_view_list(self) -> None:
        with patch("api.routes.shipments.list_shipments", new=AsyncMock(return_value=[])):
            r = self.client.get(self.URL, headers=bearer(UserRole.MANAGER))
        self.assertEqual(r.status_code, 200)

    def test_advance_by_non_owner_role_is_403(self) -> None:
        # Docs không sở hữu bước 'booking' → advance_stage ném StageOwnerError → 403.
        from services.shipment_service import StageOwnerError
        with (
            patch("api.routes.shipments.get_shipment", new=AsyncMock(return_value=_fake_shipment())),
            patch("api.routes.shipments.advance_stage",
                  new=AsyncMock(side_effect=StageOwnerError("not owner"))),
        ):
            r = self.client.post(f"{self.URL}/{uuid4()}/advance", json={},
                                 headers=bearer(UserRole.DOCS))
        self.assertEqual(r.status_code, 403)

    def test_owner_role_can_advance_and_sla_breach_is_computed(self) -> None:
        """Job quá hạn SLA phải tự lộ `sla_breached=true` qua hàm thật, khớp
        badge "Quá SLA" trên card Kanban."""
        overdue = datetime(2020, 1, 1, tzinfo=UTC)
        with (
            patch("api.routes.shipments.get_shipment", new=AsyncMock(return_value=_fake_shipment())),
            patch("api.routes.shipments.advance_stage",
                  new=AsyncMock(return_value=_fake_shipment(ShipmentStage.DOCUMENTS,
                                                            sla_due_at=overdue,
                                                            owner_role=UserRole.DOCS))),
        ):
            r = self.client.post(f"{self.URL}/{uuid4()}/advance", json={},
                                 headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["stage"], "documents")
        self.assertEqual(body["owner_role"], "docs")
        self.assertTrue(body["sla_breached"])


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 8 — Users (quản lý người dùng — chỉ admin)
# ─────────────────────────────────────────────────────────────────────────────
USER_PAYLOAD = {
    "username": "docs2", "display_name": "Chứng từ - Ca 2",
    "role": "docs", "password": "docs2@123",
}


def _fake_user_row(role=UserRole.DOCS):
    return SimpleNamespace(
        id=uuid4(), username="docs2", display_name="Chứng từ - Ca 2",
        role=role, is_active=True, created_at=NOW,
    )


class UsersPermissionTest(BaseRouteTest):
    URL = "/api/v1/users"

    def test_admin_can_list(self) -> None:
        with patch(
            "api.routes.users.list_users",
            new=AsyncMock(return_value=[_fake_user_row(UserRole.ADMIN), _fake_user_row()]),
        ):
            r = self.client.get(self.URL, headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["items"][0]["role"], "admin")

    def test_admin_can_create(self) -> None:
        with patch("api.routes.users.create_user", new=AsyncMock(return_value=_fake_user_row())):
            r = self.client.post(self.URL, json=USER_PAYLOAD, headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 200)
        # 1 tài khoản = đúng 1 vai trò, trả về đúng `.value`.
        self.assertEqual(r.json()["role"], "docs")

    def test_manager_can_view_but_not_create(self) -> None:
        with patch("api.routes.users.list_users", new=AsyncMock(return_value=[])):
            view = self.client.get(self.URL, headers=bearer(UserRole.MANAGER))
        create = self.client.post(self.URL, json=USER_PAYLOAD, headers=bearer(UserRole.MANAGER))
        self.assertEqual(view.status_code, 200)
        self.assertEqual(create.status_code, 403)

    def test_accountant_cannot_list(self) -> None:
        r = self.client.get(self.URL, headers=bearer(UserRole.ACCOUNTANT))
        self.assertEqual(r.status_code, 403)

    def test_create_invalid_role_is_422(self) -> None:
        bad = dict(USER_PAYLOAD, role="superuser")
        r = self.client.post(self.URL, json=bad, headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 9 — Manual ingest (dán tin nhắn Zalo)
# ─────────────────────────────────────────────────────────────────────────────
ZALO_PAYLOAD = {
    "channel": "zalo",
    "content": "Xe 51F-12345 lấy cont WHLU4455667, D/O DO-2026-4471, free time 7 ngày.",
    "source_label": "Group Điều xe Cát Lái",
    "sender": "Ops - Nguyễn Văn A",
}


def _ingest_result():
    return {
        "message_id": uuid4(), "channel": "zalo", "linked_containers": ["WHLU4455667"],
        "fact_count": 3, "extraction_method": "deterministic", "extraction_status": "ok",
    }


class ManualIngestPermissionTest(BaseRouteTest):
    URL = "/api/v1/manual-ingest"

    def test_ops_can_save(self) -> None:
        with patch("api.routes.manual_ingest.ingest_manual_content",
                   new=AsyncMock(return_value=_ingest_result())):
            r = self.client.post(self.URL, json=ZALO_PAYLOAD, headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fact_count"], 3)

    def test_docs_can_save(self) -> None:
        with patch("api.routes.manual_ingest.ingest_manual_content",
                   new=AsyncMock(return_value=_ingest_result())):
            r = self.client.post(self.URL, json=ZALO_PAYLOAD, headers=bearer(UserRole.DOCS))
        self.assertEqual(r.status_code, 200)

    def test_sales_cannot_save(self) -> None:
        r = self.client.post(self.URL, json=ZALO_PAYLOAD, headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 403)

    def test_manager_cannot_save(self) -> None:
        r = self.client.post(self.URL, json=ZALO_PAYLOAD, headers=bearer(UserRole.MANAGER))
        self.assertEqual(r.status_code, 403)

    def test_empty_content_is_422(self) -> None:
        bad = dict(ZALO_PAYLOAD, content="")
        r = self.client.post(self.URL, json=bad, headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 10 — Field image (ảnh hiện trường — chỉ ops/driver upload)
# ─────────────────────────────────────────────────────────────────────────────
def _image_file():
    return {"file": ("container.jpg", b"fake-image-bytes", "image/jpeg")}


def _preview_result():
    return {
        "attachment": SimpleNamespace(id=uuid4(), filename="container.jpg", mime_type="image/jpeg"),
        "vision": {"extraction_status": "ok", "container_no": CONTAINER_NO, "container_no_valid": True},
        "matched_container": CONTAINER_NO,
    }


class FieldImagePermissionTest(BaseRouteTest):
    URL = "/api/v1/field-images/preview"

    def test_ops_can_preview(self) -> None:
        with (
            patch("api.routes.field_images.preview_field_image",
                  new=AsyncMock(return_value=_preview_result())),
            patch("api.routes.field_images.attachment_file_url", return_value=None),
        ):
            r = self.client.post(self.URL, files=_image_file(), headers=bearer(UserRole.OPS))
        self.assertEqual(r.status_code, 200)

    def test_driver_can_preview(self) -> None:
        with (
            patch("api.routes.field_images.preview_field_image",
                  new=AsyncMock(return_value=_preview_result())),
            patch("api.routes.field_images.attachment_file_url", return_value=None),
        ):
            r = self.client.post(self.URL, files=_image_file(), headers=bearer(UserRole.DRIVER))
        self.assertEqual(r.status_code, 200)

    def test_sales_cannot_preview(self) -> None:
        r = self.client.post(self.URL, files=_image_file(), headers=bearer(UserRole.SALES_CS))
        self.assertEqual(r.status_code, 403)

    def test_accountant_cannot_preview(self) -> None:
        r = self.client.post(self.URL, files=_image_file(), headers=bearer(UserRole.ACCOUNTANT))
        self.assertEqual(r.status_code, 403)

    def test_admin_cannot_preview(self) -> None:
        r = self.client.post(self.URL, files=_image_file(), headers=bearer(UserRole.ADMIN))
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
