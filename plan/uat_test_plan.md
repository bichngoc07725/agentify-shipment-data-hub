# Agentify — Kế hoạch test thực tế (UAT) theo vai trò

> Tài liệu tự chứa để chuẩn bị test end-to-end trên code thật. Đối tượng: người chạy test thủ công (UAT) + người viết test tự động. Bám đúng endpoint/quyền/luồng hiện có trong repo (đã đối chiếu `backend/api/routes/*`, `backend/config/permissions.py`, `backend/services/shipment_service.py`, `scripts/seed_users.py`, `scripts/seed_demo_data.py`). Xem thêm `plan/master_roadmap.md` (checkpoint từng giai đoạn) và `CLAUDE.md` (nguyên tắc).

---

## 0. Chuẩn bị môi trường test

### 0.1 Khởi động hệ thống
1. PostgreSQL: `docker compose -f compose_db.yaml up -d postgres` (trong `backend/`).
2. Tạo schema sạch (môi trường test, xoá dữ liệu cũ): `./.venv/bin/python -m scripts.reset_database`.
3. Seed 7 tài khoản demo: `./.venv/bin/python -m scripts.seed_users`.
4. Seed dữ liệu logistics mẫu (email/PDF/container): `./.venv/bin/python -m scripts.seed_demo_data`.
5. Chạy backend (Docker): `docker compose up -d --build` — API ở `http://127.0.0.1:8766`.
6. Chạy frontend: `cd frontend_v2 && npm install && npm run dev` — UI ở `http://localhost:5174`, tự proxy `/api` sang backend.

### 0.2 Tài khoản demo (nguồn: `scripts/seed_users.py`)

| Username | Mật khẩu | Role (enum) | Vai trò |
|---|---|---|---|
| `admin` | `admin@123` | `admin` | Quản trị hệ thống |
| `manager` | `manager@123` | `manager` | Quản lý |
| `sales` | `sales@123` | `sales_cs` | Sales / CS |
| `docs` | `docs@123` | `docs` | Chứng từ |
| `ops` | `ops@123` | `ops` | Vận hành |
| `ketoan` | `ketoan@123` | `accountant` | Kế toán |
| `taixe` | `taixe@123` | `driver` | Tài xế |

### 0.3 Container mẫu (nguồn: `scripts/seed_demo_data.py`)
`MSCU1234567`, `TGHU7654321`, `OOLU9988776`, `WHLU4455667`, `CAIU7788990`, `SEGU5566778`, `TRHU3344556`, `FSCU2211334`, `CMAU6677889`, `TEMU5544332`. Tài khoản Gmail demo: `demo-logistics@agentify.vn`.

### 0.4 Lấy token để test API trực tiếp (curl)
```bash
curl -s -X POST http://127.0.0.1:8766/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ops","password":"ops@123"}'
# → { "access_token": "<JWT>", "token_type": "bearer", "role": "ops", ... }
```
Dùng lại: `-H "Authorization: Bearer <JWT>"`. Token chứa **đúng 1 role** — nguyên tắc "1 tài khoản = 1 vai trò".

### 0.5 Nguyên tắc kiểm thử xuyên suốt (từ `CLAUDE.md`)
- **Provenance:** mọi field hiển thị phải có nguồn (source_type/source_label/confidence/source_sent_at). Nếu thiếu dữ liệu → hệ thống trả "không tìm thấy trong Agentify", KHÔNG bịa.
- **Backend là nơi chặn thật:** UI ẩn nút chỉ là lớp 1. Mỗi test quyền phải kiểm tra thêm bằng gọi API trực tiếp → phải nhận `403` (chứng minh không chỉ ẩn ở UI).
- **Không cộng dồn quyền:** mỗi role chỉ đúng tập quyền của mình.

---

## 1. Ma trận quyền tổng hợp (kỳ vọng test RBAC)

Nguồn sự thật: `backend/config/permissions.py`. Bảng dưới là kỳ vọng để tick khi test. `V`=view, `C`=create, `E`=edit, `A`=approve, `X`=export, `R`=resolve. Ô trống = 403.

| Resource | admin | manager | sales_cs | docs | ops | accountant | driver |
|---|---|---|---|---|---|---|---|
| system_config (user, Gmail, ma trận quyền) | V C E A X | V | | | | | |
| quote (RFQ/báo giá) | V | V | V C E + delete | V | V | V | |
| credit_limit | V E C A | V | V | | | V E C A | |
| booking | V | V | V | V | V C E | | |
| shipping_document | V | V | V | V C E | V | V | |
| customs_declaration | V | V | | V | V C, E(+admin) | V | |
| shipment (Kanban) | V C E | V C E | V C | V E | V C E | V E | |
| container_facts (view) | V | V | V | V | V | V | |
| container_facts (edit — theo nhóm field) | | | | E: nhóm `document` | E: nhóm `operation` | E: nhóm `finance` | |
| manual_ingest (paste Zalo) | | | | C | C | | |
| exception (view) | V | V | V | V | V | V | |
| exception thường (resolve/approve) | A | A | | R | R | | |
| exception nghiêm trọng (`critical`) | A | A | | | | | |
| dispatch_order | V | V | | | V C E | | V (của mình) |
| pod_photo | V | V | | V | V | | C |
| field_image (ảnh hiện trường) | V | V | V | V | V C | V | C |
| debit_note | V | V | | V | V | V C E A | |
| reconciliation | V | V | | V | V | V C E, A(admin/mgr) | |
| erp_export (MISA/Fast) | V | V | | | | V C X | |
| audit log | V | V | | | | | |

Ghi chú field-group của `container_facts` (2 lớp quyền, `permissions.py::CONTAINER_FACT_FIELD_GROUPS`):
- Nhóm `operation` (Ops): container_no, booking_no, seal_no, vessel, voyage, pol, pod, etd, eta, ata, do_no, free_time_days.
- Nhóm `document` (Docs): bl_no, po_no.
- Nhóm `finance` (Kế toán): debit_note_no, invoice_no, invoice_amount, charge_amount.
- Sửa field ngoài nhóm của mình → 403 dù role có quyền edit container_facts nói chung.

---

## 2. Kịch bản E2E "đường hạnh phúc" — 1 lô đi hết 6 bước

Kịch bản chính: một lô hàng nhập đường biển đi qua đủ 6 bước trên Kanban (`rfq → booking → documents → customs → delivery → reconciliation → closed`). Chủ sở hữu mỗi bước và SLA lấy từ `services/shipment_service.py::STAGE_CONFIG`:

| Bước (stage) | Role sở hữu (được "Chuyển bước") | SLA |
|---|---|---|
| rfq | sales_cs | 24h |
| booking | ops | 24h |
| documents | docs | 48h |
| customs | ops | 48h |
| delivery | ops | 24h |
| reconciliation | accountant | 72h |
| closed | — (kết thúc) | — |

Quy tắc "Chuyển bước" (`can_advance`): chỉ **role đang sở hữu bước hiện tại** hoặc **admin/manager** mới đẩy job sang bước sau; role khác gọi `POST /api/v1/shipments/{id}/advance` → lỗi quyền.

### TC-E2E-01 — Vòng đời đầy đủ
| # | Actor | Thao tác | Kỳ vọng |
|---|---|---|---|
| 1 | sales | Tạo báo giá (`POST /api/v1/quotes`) với các dòng phí (Ocean Freight, THC, CIC, DO, Doc) | Lưu thành công, có quote_no |
| 2 | sales/ops | Tạo job Kanban (`POST /api/v1/shipments`) gắn container `MSCU1234567` + quote vừa tạo | Job hiện ở cột RFQ, owner = sales_cs, SLA +24h |
| 3 | sales | Chuyển bước RFQ→Booking | Job sang cột Booking, owner đổi thành ops |
| 4 | ops | Nhập booking facts (booking_no, vessel, etd) qua `PATCH container_facts` | Lưu OK, provenance = manual |
| 5 | ops | Chuyển bước Booking→Documents | Sang cột Documents, owner = docs |
| 6 | docs | Nhập bl_no (nhóm document) | Lưu OK |
| 7 | docs | Chuyển Documents→Customs | Sang Customs, owner = ops |
| 8 | ops | Tạo tờ khai hải quan Luồng Đỏ (`POST /api/v1/customs/declarations`) | Tạo OK + sinh exception `customs_red` |
| 9 | ops | Chuyển Customs→Delivery | Sang Delivery, owner = ops |
| 10 | taixe/ops | Upload ảnh POD/EIR hiện trường (`POST /api/v1/field-images`) | Ảnh gắn đúng container, fact có source=image |
| 11 | ops | Chuyển Delivery→Reconciliation | Sang Reconciliation, owner = accountant |
| 12 | ketoan | Tạo debit note + chạy đối soát (`POST /api/v1/reconciliation`) | Sinh dòng chênh lệch đúng số tiền |
| 13 | admin/manager | Duyệt đối soát nếu chênh lệch vượt ngưỡng | Trạng thái approved |
| 14 | ketoan | Chuyển Reconciliation→Closed | Job vào cột Hoàn tất |
| 15 | ketoan | Xuất ERP (`GET /api/v1/erp-export/reconciliation/{id}`) | File/định dạng xuất OK |
| — | any (trừ driver) | Mở container `MSCU1234567` | Timeline/tiến độ hiển thị đúng bước đang ở, mọi field có nguồn |

---

## 3. Kịch bản test theo từng vai trò

Mỗi vai trò gồm: (a) việc **được phép** (happy path) và (b) việc **bị chặn** (kiểm tra 403 qua API trực tiếp, không chỉ ẩn nút).

### 3.1 admin
Được: đăng nhập → thấy đủ menu gồm nhóm "Hệ thống"; quản lý user (`GET/POST/PATCH /api/v1/users`); xem ma trận quyền (`GET /api/v1/admin/permissions`); cấu hình Gmail; duyệt exception nghiêm trọng; xem audit log (`GET /api/v1/audit`); chuyển bước bất kỳ job nào.
- TC-ADM-01: Tạo user mới role `ops` → user đó login được, token trả `role: "ops"`.
- TC-ADM-02: `POST /users` với role = chuỗi ngoài enum → `422`.
- TC-ADM-03: Ma trận quyền trả về khớp `permissions.py` (đối chiếu tay 3–4 dòng).
- TC-ADM-04: Duyệt 1 exception `critical` → thành công.

### 3.2 manager
Được: xem báo cáo/mọi resource ở mức view; duyệt exception (thường + nghiêm trọng); duyệt đối soát; xem audit; chuyển bước job.
Bị chặn: tạo/sửa user (`POST /users` → 403 — chỉ admin create/edit `system_config`); cấu hình Gmail (`POST /gmail-connections` → 403).
- TC-MGR-01: `GET /api/v1/users` → 200 (manager có view system_config), nhưng `POST /api/v1/users` → 403.
- TC-MGR-02: Approve exception nghiêm trọng → 200.

### 3.3 sales_cs (Sales/CS) — Bước 1 RFQ/Báo giá
Được: CRUD báo giá (`POST/PUT/DELETE /api/v1/quotes`); tạo job Kanban; xem container/exception.
Bị chặn: sửa báo giá KHÔNG phải của resource mình? (mọi sales sửa được quote — quote create/edit/delete chỉ sales_cs); sửa container_facts (403); duyệt exception nghiêm trọng (403); xem reconciliation/debit_note (403 — margin nội bộ, sales bị loại khỏi cost data).
- TC-SAL-01: Tạo báo giá đầy đủ dòng phí → lưu OK.
- TC-SAL-02: `PATCH /api/v1/containers/{no}/facts` sửa bl_no → 403.
- TC-SAL-03: `GET /api/v1/reconciliation/{id}` → 403.
- TC-SAL-04: UI không hiện nút "Duyệt ngoại lệ nghiêm trọng".

### 3.4 docs (Chứng từ) — Bước 3
Được: xem/tạo/sửa shipping_document; sửa container_facts **nhóm document** (bl_no, po_no); paste Zalo (`manual_ingest`); resolve exception thường.
Bị chặn: sửa container_facts nhóm operation/finance (403); tạo booking (403 — booking create chỉ ops); duyệt exception nghiêm trọng (403).
- TC-DOC-01: `PATCH facts` sửa `bl_no` → 200; sửa `eta` (nhóm operation) → 403; sửa `invoice_amount` (finance) → 403.
- TC-DOC-02: Paste nội dung Zalo qua `POST /api/v1/manual-ingest` → tạo/cập nhật fact có provenance source=zalo/manual.
- TC-DOC-03: Resolve exception `missing_documents` (thường) → 200.

### 3.5 ops (Vận hành) — Bước 2,4,5
Được: tạo/sửa booking; sửa container_facts **nhóm operation**; tạo/sửa tờ khai hải quan; tạo dispatch order; upload field_image; paste Zalo; resolve exception thường; chuyển bước các cột ops sở hữu (booking/customs/delivery).
Bị chặn: sửa container_facts nhóm document/finance (403); tạo báo giá (403); duyệt reconciliation nghiêm trọng (403).
- TC-OPS-01: Sửa `booking_no`/`vessel`/`eta` (operation) → 200; sửa `bl_no` (document) → 403.
- TC-OPS-02: Tạo tờ khai Luồng Đỏ → 200 + sinh exception `customs_red`; đổi Xanh→Đỏ ghi `customs_channel_history`.
- TC-OPS-03: Upload ảnh container rõ → nhận đúng số container/seal, gắn đúng container; ảnh mờ → không crash, vẫn lưu, cho nhập tay.
- TC-OPS-04: Chuyển bước job đang ở cột Booking (owner ops) → 200; chuyển bước job đang ở cột Documents (owner docs) → lỗi quyền (StageOwnerError).

### 3.6 accountant (Kế toán) — Bước 6
Được: tạo/sửa/duyệt debit_note; tạo/sửa reconciliation; sửa container_facts **nhóm finance**; xuất ERP; xem credit_limit.
Bị chặn: sửa container_facts nhóm document/operation (403); duyệt reconciliation nghiêm trọng cần admin/manager (403 khi ketoan tự approve khoản vượt ngưỡng); cấu hình hệ thống/quản lý user (403).
- TC-ACC-01: Sửa `invoice_amount` (finance) → 200; sửa `eta` (operation) → 403.
- TC-ACC-02: Quote khớp debit note → không cảnh báo lệch; debit note lệch giá → sinh đúng dòng chênh lệch + số tiền.
- TC-ACC-03: `GET /api/v1/users` → 403 (kế toán không đụng system_config).
- TC-ACC-04: `GET /api/v1/erp-export/reconciliation/{id}` → 200.

### 3.7 driver (Tài xế)
Được: chỉ phần liên quan tới mình — lệnh điều xe của mình (row-level) + upload ảnh POD/field_image.
Bị chặn: mọi trang cấu hình; xem quote (403 — driver bị loại khỏi quote view); xem cost data/reconciliation (403); Kanban (`shipment` view không gồm driver → 403); container_facts view? (driver KHÔNG trong ALL_STAFF nên không xem được facts qua quyền chung).
- TC-DRV-01: Login `taixe` → sidebar chỉ thấy phần của mình, không vào được `/setup`, `/admin/*`, `/quotes`, `/kanban`.
- TC-DRV-02: `POST /api/v1/field-images` (upload POD) → 200.
- TC-DRV-03: `GET /api/v1/quotes` → 403; `GET /api/v1/shipments/board` → 403.
- TC-DRV-04: Truy cập lệnh điều xe của tài xế khác → bị chặn (row-level, service layer).

---

## 4. Test exception engine (cảnh báo tự động)

Các exception sinh tự động khi extract/nhập liệu (mã từ `services/exception_service.py`). Test bằng cách seed/nhập dữ liệu tương ứng rồi kiểm tra xuất hiện trong `GET /api/v1/exceptions` và trang Exceptions:

| Mã exception | Điều kiện kích hoạt | Mức | Ai resolve |
|---|---|---|---|
| `free_time_expiring` | Sắp hết free time (free_time_days + ngày về) | warning | docs/ops |
| `arrived_no_do` | Đã cập bến (ata) nhưng chưa có D/O (do_no) | warning | docs/ops |
| `eta_changed` | ETA thay đổi so với lần trước | info/warning | docs/ops |
| `missing_documents` | Thiếu chứng từ theo checklist chiều hàng | warning | docs/ops |
| `stale_no_update` | Lô im lặng quá lâu không cập nhật | info | docs/ops |
| `customs_yellow` | Tờ khai Luồng Vàng | warning | docs/ops |
| `customs_red` | Tờ khai Luồng Đỏ | critical? kiểm tra | admin/manager nếu critical |
| `unlinked_charges` | Có charge chưa gắn được vào quote | warning | docs/ops |

- TC-EXC-01: Exception mức `critical` → chỉ admin/manager approve được; docs/ops resolve → bị chặn (theo `EXCEPTION_ACTIONS_BY_SEVERITY`).
- TC-EXC-02: Exception thường → docs/ops resolve được; sales/driver → 403.
- TC-EXC-03: Overview hiển thị đúng số "lô cần xử lý" và tách riêng số `critical`.

---

## 5. Test provenance & tra cứu (giá trị cốt lõi sản phẩm)

- TC-PRV-01: Mở 1 container seed → mỗi field hiển thị nguồn (email/pdf/zalo/image + label + thời điểm). Không field nào "trần" không nguồn.
- TC-PRV-02: Tra cứu field mà dữ liệu không tồn tại → hệ thống nói rõ "không tìm thấy trong Agentify", KHÔNG bịa giá trị.
- TC-PRV-03: Search global (container/booking/B/L/PO) từ thanh tìm kiếm → ra đúng container + email liên quan.
- TC-PRV-04: Fact từ ảnh (OCR/vision) hiển thị source = `image`; fact từ paste Zalo hiển thị source tương ứng.
- TC-PRV-05: Matching có confidence — fact confidence thấp có đường review, không tự động ghi đè.

---

## 6. Test theme & UI (nếu GĐ9 theme đã triển khai)

- TC-UI-01: Toggle sáng/tối → toàn bộ nền/chữ/card/badge đổi; không phần tử nào mất chữ (badge danger/success/warning đọc được ở cả 2 mode).
- TC-UI-02: Reload trang → theme đã chọn được giữ (localStorage).
- TC-UI-03: ContainerProgressTimeline hiển thị đúng bước hiện tại, khớp cột Kanban; container chưa có job → "Chưa có job" không vỡ layout.
- TC-UI-04: sla_breached = true → chấm bước hiện tại đổi màu cảnh báo, khớp badge "Quá SLA" trên card Kanban.

---

## 7. Regression & test tự động

- Chạy `pytest` trong `backend/` → toàn bộ PASS trước khi coi UAT là đạt (quy tắc `CLAUDE.md`).
- File test hiện có để tham chiếu: `test_auth_routes.py`, `test_permission_routes.py`, `test_customs_service.py`, `test_customs_routes.py`, `test_shipment_service.py`, `test_reconciliation*`, `test_users_routes.py`, `test_admin_routes.py`, `test_seed_demo_data.py`.
- Với mỗi TC quyền ở mục 3, nên có 1 test tự động dạng: token role X gọi endpoint Y → assert status (200/403/422).

---

## 8. Bảng theo dõi kết quả (điền khi chạy)

| Test case | Role | Kỳ vọng | Kết quả | Ghi chú |
|---|---|---|---|---|
| TC-E2E-01 | multi | Đi hết 6 bước | | |
| TC-ADM-01..04 | admin | | | |
| TC-MGR-01..02 | manager | | | |
| TC-SAL-01..04 | sales_cs | | | |
| TC-DOC-01..03 | docs | | | |
| TC-OPS-01..04 | ops | | | |
| TC-ACC-01..04 | accountant | | | |
| TC-DRV-01..04 | driver | | | |
| TC-EXC-01..03 | — | | | |
| TC-PRV-01..05 | — | | | |
| TC-UI-01..04 | — | | | |

Quy ước: ✅ đạt / ❌ chưa đạt / ⏭️ bỏ qua (ngoài scope). Với mỗi ❌ ghi rõ endpoint + status thực nhận + kỳ vọng để lần theo.
