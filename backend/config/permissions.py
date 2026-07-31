"""Static permission matrix — the single place RBAC rules live.

Mirrors `plan/rbac_permission_design.md` section 4 (resource x action x role)
so anyone auditing "who can do what" reads this file instead of grepping for
scattered `if role == "admin"` checks across routes.

A role's permissions are NOT additive: a user has exactly one role
(`db.models.UserRole`), and that role's entry here is the entire set of
things they may do. There is no union across roles.
"""

from __future__ import annotations

from db.models import UserRole

ADMIN = UserRole.ADMIN
MANAGER = UserRole.MANAGER
SALES_CS = UserRole.SALES_CS
DOCS = UserRole.DOCS
OPS = UserRole.OPS
ACCOUNTANT = UserRole.ACCOUNTANT
DRIVER = UserRole.DRIVER

# Every role except Driver, who only ever sees rows scoped to themselves
# (row-level, enforced in the service layer — not expressible in this table).
ALL_STAFF = {ADMIN, MANAGER, SALES_CS, DOCS, OPS, ACCOUNTANT}

# {resource: {action: {roles allowed}}}. Actions match the design doc:
# view, create, edit, approve, export.
PERMISSIONS: dict[str, dict[str, set[UserRole]]] = {
    # Row: "Cấu hình hệ thống, user, kết nối Gmail"
    "system_config": {
        "view": {ADMIN, MANAGER},
        "create": {ADMIN},
        "edit": {ADMIN},
        "approve": {ADMIN},
        "export": {ADMIN},
    },
    # Row: "Quote/RFQ". Admin/Manager are view-only here too — quoting is
    # Sales/CS's call, not a management override.
    "quote": {
        "view": ALL_STAFF,
        "create": {SALES_CS},
        "edit": {SALES_CS},
        "delete": {SALES_CS},
    },
    # Row: "Credit limit / công nợ khách hàng"
    "credit_limit": {
        "view": {ADMIN, MANAGER, SALES_CS, ACCOUNTANT},
        "edit": {ADMIN, ACCOUNTANT},
        "create": {ACCOUNTANT},
        "approve": {ACCOUNTANT},
    },
    # Row: "Booking (đặt chỗ tàu)"
    "booking": {
        "view": {ADMIN, MANAGER, SALES_CS, DOCS, OPS},
        "create": {OPS},
        "edit": {OPS},
    },
    # Row: "Chứng từ (Invoice/Packing List/SI/Draft B/L)"
    "shipping_document": {
        "view": ALL_STAFF,
        "create": {DOCS},
        "edit": {DOCS},
    },
    # Row: "Tờ khai hải quan / phân luồng"
    "customs_declaration": {
        "view": {ADMIN, MANAGER, DOCS, OPS, ACCOUNTANT},
        "create": {OPS},
        "edit": {ADMIN, OPS},
    },
    # Row: "Job board / Kanban lô hàng"
    "shipment": {
        "view": {ADMIN, MANAGER, SALES_CS, DOCS, OPS, ACCOUNTANT},
        "create": {ADMIN, MANAGER, SALES_CS, OPS},
        "edit": {ADMIN, MANAGER, SALES_CS, DOCS, OPS, ACCOUNTANT},
    },
    # Rows: "Container facts — nhóm CHỨNG TỪ / VẬN HÀNH / CHI PHÍ".
    # This entry is layer 1 only — *whether the role may edit container_facts
    # at all* (the union of every group-owning role). Layer 2 — *which group*
    # (document/operation/finance) — is `CONTAINER_FACT_FIELD_GROUPS` +
    # `ROLE_FIELD_GROUP` below, checked in the route handler per field.
    "container_facts": {
        "view": ALL_STAFF,
        "edit": {DOCS, OPS, ACCOUNTANT},
    },
    # Not a design-doc row by itself — paste-and-preview ingestion (Zalo) can
    # touch fields across every group, so it gets its own coarse Create gate
    # rather than being folded into `container_facts`.
    "manual_ingest": {
        "create": {OPS, DOCS},
    },
    # Row: "Exception thường" / "Exception nghiêm trọng". `view` is the same
    # for both tiers, so it lives here; `resolve`/`approve` differ by
    # severity tier and live in `EXCEPTION_ACTIONS_BY_SEVERITY` below.
    "exception": {
        "view": ALL_STAFF,
    },
    # Row: "Lệnh điều xe (dispatch order)". Driver's "confirm my own
    # assignment" is row-level (assigned_driver_id == current user) and is
    # enforced in the service layer, not here.
    "dispatch_order": {
        "view": {ADMIN, MANAGER, OPS, DRIVER},
        "create": {OPS},
        "edit": {OPS},
    },
    # Row: "Ảnh/POD gửi từ hiện trường"
    "pod_photo": {
        "view": {ADMIN, MANAGER, DOCS, OPS},
        "create": {DRIVER},
    },
    # Field photos (container/seal/EIR/POD) read by vision — GĐ5. Broader
    # than `pod_photo` above (every staff role may view, not just
    # Admin/Manager/Docs/Ops) because these become container_facts everyone
    # doing the lookup needs to see, not just an ops-only artifact.
    # TODO(GĐ7 dispatch_order): once a photo is tied to a specific dispatch
    # assignment, restrict Driver's `create` to their own assignment
    # (row-level, like `dispatch_order`) instead of any container.
    "field_image": {
        "view": ALL_STAFF,
        "create": {OPS, DRIVER},
    },
    # Row: "Debit note / đối soát chi phí"
    "debit_note": {
        "view": {ADMIN, MANAGER, DOCS, OPS, ACCOUNTANT},
        "create": {ACCOUNTANT},
        "edit": {ACCOUNTANT},
        "approve": {ADMIN, MANAGER, ACCOUNTANT},
    },
    # GĐ6 — Smart Reconciliation. Not a direct BA Spec row, but follows the
    # same shape as `debit_note` above (its cost data source): Sales/CS and
    # Driver are excluded from `view` on purpose — a variance report shows
    # real cost vs. quoted price, i.e. margin, which is internal-only.
    "reconciliation": {
        "view": {ADMIN, MANAGER, DOCS, OPS, ACCOUNTANT},
        "create": {ACCOUNTANT},
        "edit": {ACCOUNTANT},
        "approve": {ADMIN, MANAGER},
    },
    # Row: "Xuất dữ liệu sang ERP (MISA/Fast)"
    "erp_export": {
        "view": {ADMIN, MANAGER, ACCOUNTANT},
        "create": {ACCOUNTANT},
        "export": {ACCOUNTANT},
    },
    # Row: "Nhật ký audit" — evidence for a cost/data dispute, admin-only.
    "audit": {
        "view": {ADMIN},
    },
}

# Exception resolve/approve depend on the SEVERITY TIER, not just the
# resource/action pair, so they are looked up separately from `PERMISSIONS`.
#
# "normal"   -> everyday exceptions (free time, missing docs, stale shipment).
# "critical" -> exceeds a credit limit or a large cost variance. Only
#               Admin/Manager may act on these at all — there is no
#               "resolve" step for anyone else, per design doc §4 note.
EXCEPTION_ACTIONS_BY_SEVERITY: dict[str, dict[str, set[UserRole]]] = {
    "normal": {
        "resolve": {DOCS, OPS},
        "approve": {ADMIN, MANAGER},
    },
    "critical": {
        "approve": {ADMIN, MANAGER},
    },
}


def exception_severity_tier(severity: str) -> str:
    """Collapse the 3-level UI severity (critical/warning/info) into the
    2-tier approval model the design doc calls for. Only `critical` requires
    Admin/Manager sign-off; everything else is resolvable by Docs/Ops."""

    return "critical" if severity == "critical" else "normal"


# Field-name -> group for manual edits to `container_facts`. A field missing
# from this map is deliberately *unclassified*: the edit endpoint denies
# rather than guessing a group for it. Add new fields here (not in the route)
# as extraction grows to cover more of them.
CONTAINER_FACT_FIELD_GROUPS: dict[str, str] = {
    # operation: schedule/movement fields — Ops owns these.
    "container_no": "operation",
    "booking_no": "operation",
    "seal_no": "operation",
    "vessel": "operation",
    "voyage": "operation",
    "pol": "operation",
    "pod": "operation",
    "etd": "operation",
    "eta": "operation",
    "ata": "operation",
    "do_no": "operation",
    "free_time_days": "operation",
    # document: commercial/paper trail fields — Docs owns these.
    "bl_no": "document",
    "po_no": "document",
    # finance: cost fields — Accountant owns these. Not yet produced by the
    # extraction pipeline (no charge/debit-note parser exists today), but
    # container_facts.field_name is free text, so a fact with one of these
    # names can already be created (e.g. by manual ingest) and must resolve
    # to the right group here.
    "debit_note_no": "finance",
    "invoice_no": "finance",
    "invoice_amount": "finance",
    "charge_amount": "finance",
}

# Which group each role may edit within `container_facts`. Docs/Ops/Accountant
# each own exactly one group — no overlap, per design doc §4 closing note.
ROLE_FIELD_GROUP: dict[UserRole, str] = {
    DOCS: "document",
    OPS: "operation",
    ACCOUNTANT: "finance",
}


def field_group_for(field_name: str) -> str | None:
    return CONTAINER_FACT_FIELD_GROUPS.get(field_name)
