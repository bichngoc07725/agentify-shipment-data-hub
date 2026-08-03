# GĐ6 — Brief tự chứa: Smart Reconciliation — Đối soát chi phí (Bước 6 nghiệp vụ)

> Brief tự chứa — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo) để nắm pattern & RBAC. Đọc `plan/master_roadmap.md` mục GĐ6 để biết checkpoint. Giai đoạn này PHỤ THUỘC GĐ4 (Quote đã xong — dùng làm baseline giá).

## 1. Mục tiêu & vì sao làm
So khớp **chi phí thực tế** (từ Debit Note / Invoice của hãng tàu, đối tác) với **giá đã báo cho khách** (Quote ở GĐ4), làm nổi bật khoản chênh lệch, khoản thiếu, khoản phát sinh ngoài báo giá. Đây là tính năng giá trị cốt lõi nhất theo quy trình (chống "thất thoát doanh thu" do bỏ sót phí). Chủ sở hữu nghiệp vụ: `accountant`; chênh lệch lớn cần `admin`/`manager` duyệt.

## 2. Bối cảnh nghiệp vụ (đủ để code)
Cuối lô hàng, Kế toán tổng hợp mọi chi phí thực đã phát sinh (cước tàu, thuế, phí lấy lệnh, phí xe, phí lưu container...) rồi **đối chiếu với bảng báo giá ban đầu** đã gửi khách. Nếu lệch phải giải trình. Rủi ro thực tế: bỏ sót phí nhỏ lẻ (phí kiểm hóa, sửa vận đơn) → quên đưa vào giấy báo nợ → mất doanh thu. Hệ thống cần tự động:
- Ghép từng khoản phí thực với khoản tương ứng trong báo giá (theo `charge_code`/mô tả).
- Đánh dấu: **khớp** (bằng/chênh trong ngưỡng), **lệch** (chênh vượt ngưỡng), **thiếu** (có trong báo giá nhưng chưa có chi phí thực), **phát sinh** (có chi phí thực nhưng không có trong báo giá).
- Cảnh báo phí lưu container (demurrage/storage) khi vượt free time.

## 3. Hạ tầng đã có sẵn (TÁI SỬ DỤNG)
- **Quote + QuoteCharge** (`db/models.py`): baseline giá. `QuoteCharge` có `charge_group` (`ocean_freight`/`surcharge`/`local`), `charge_code`, `description`, `unit_price`, `currency`, `quantity`, `amount`. Đây là vế "giá đã báo".
- **Charges đã extract**: `gmail_service/field_extract.py` LLM schema đã trích mảng `charges` từ debit note/invoice với `{description, currency, amount, vat_rate, ...}`. Đây là vế "chi phí thực" — nhưng hiện chỉ nằm trong `extracted_record`/facts, CHƯA gom thành bảng đối soát.
- **Phân loại document**: `deterministic_extract.py` đã nhận diện `debit_note`, `invoice` → biết attachment nào là nguồn chi phí thực.
- **Permission `debit_note`** đã có trong `config/permissions.py`: view {admin,manager,docs,ops,accountant}, create/edit {accountant}, approve {admin,manager,accountant}. Field group finance đã map `debit_note_no`, `invoice_amount`, `charge_amount`.
- **Free time**: `services/exception_service.py` có `compute_free_time_deadline(container)` + container có `free_time_days`. Dùng để tính phí lưu.

## 4. Data model cần thêm (`db/models.py` + migration `YYYYMMDD_0010_add_reconciliation.py`)

### Bảng `debit_notes` (chi phí thực gom theo lô)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| container_id | UUID FK→containers.id | lô hàng |
| source_attachment_id | UUID FK→attachments.id nullable | nguồn (file debit note/invoice) |
| partner_name | String nullable | bên phát hành (hãng tàu/đối tác) |
| doc_no | String nullable | số debit note/invoice |
| currency | String default USD | |
| issued_date | Date nullable | |
| created_by | UUID FK→users.id | |
| created_at | DateTime | |

### Bảng `debit_note_charges` (từng dòng chi phí thực)
Cấu trúc song song `quote_charges` để so khớp dễ: `id, debit_note_id FK, charge_code, description, amount, currency, quantity`.

### Bảng `reconciliations` + `reconciliation_lines`
- `reconciliations`: id, container_id FK, quote_id FK (baseline), status Enum(`draft`,`reviewed`,`approved`,`escalated`), total_quoted Numeric, total_actual Numeric, total_variance Numeric, needs_approval Boolean, created_by, approved_by nullable, created_at.
- `reconciliation_lines`: id, reconciliation_id FK, charge_code, quoted_amount Numeric nullable, actual_amount Numeric nullable, variance Numeric, match_status Enum(`matched`,`variance`,`missing_actual`,`extra_actual`), note Text nullable.

## 5. Logic đối soát (`services/reconciliation_service.py`)
- Hàm `build_reconciliation(container_id, quote_id) -> Reconciliation`:
  1. Lấy `quote_charges` của quote (vế báo giá) + tất cả `debit_note_charges` của container (vế thực).
  2. Ghép theo `charge_code` (chuẩn hóa hoa/thường; nếu không có code thì match gần đúng theo description — có thể để đơn giản: exact code trước, phần còn lại là extra/missing).
  3. Mỗi cặp tính `variance = actual - quoted`; gán `match_status`:
     - cả 2 có, |variance| ≤ ngưỡng (VD 1% hoặc số tuyệt đối nhỏ cấu hình được) → `matched`.
     - cả 2 có, vượt ngưỡng → `variance`.
     - chỉ báo giá có → `missing_actual`.
     - chỉ thực có → `extra_actual` (khoản phát sinh ngoài báo giá — đúng loại dễ thất thoát).
  4. `needs_approval = True` nếu tổng variance vượt ngưỡng lớn (cấu hình) → chuyển status `escalated`, chỉ admin/manager approve được.
- Hàm `add_demurrage_estimate(container)`: nếu quá `free_time` (dùng `compute_free_time_deadline`) → thêm 1 dòng `extra_actual` ước tính phí lưu (số ngày trễ × đơn giá cấu hình).

## 6. RBAC — thêm resource `reconciliation` vào `config/permissions.py`
```
"reconciliation": {
    "view": {ADMIN, MANAGER, DOCS, OPS, ACCOUNTANT},
    "create": {ACCOUNTANT},
    "edit": {ACCOUNTANT},
    "approve": {ADMIN, MANAGER},   # chênh lệch lớn: chỉ quản lý duyệt
},
```
`debit_note` đã có sẵn — tái dùng cho API nạp chi phí thực.

## 7. API (`api/routes/reconciliation.py`, prefix `/api/v1/reconciliation`; và bổ sung route debit_note nếu chưa có)
- `POST /api/v1/debit-notes` tạo debit note + charges (từ file đã extract hoặc nhập tay) — quyền `debit_note.create` (accountant).
- `POST /reconciliation` chạy đối soát cho (container_id, quote_id) → tạo Reconciliation + lines — quyền `reconciliation.create`.
- `GET /reconciliation/{id}` xem bảng đối soát (lines tô trạng thái) — quyền `view`.
- `GET /containers/{no}/reconciliation` đối soát của 1 lô.
- `POST /reconciliation/{id}/approve` duyệt chênh lệch lớn — quyền `reconciliation.approve` (admin/manager). Ghi `approved_by`.
- Schema trong `api/models.py`.

## 8. Frontend (`frontend_v2/`)
- Trang `src/pages/ReconciliationPage.tsx`: bảng so sánh 2 cột (giá báo | giá thực) + cột chênh lệch, **tô đỏ** dòng `variance`/`extra_actual`, tô xám `missing_actual`. Route trong `router.tsx`.
- Nút "Chạy đối soát"/"Nạp debit note" chỉ hiện role `accountant`; nút "Duyệt" chỉ `admin`/`manager`.
- `ContainerDetailPage.tsx`: thêm tab/khu "Đối soát chi phí".

## 9. Test bắt buộc (`tests/test_reconciliation_service.py`, `test_reconciliation_routes.py`)
- Quote vs debit note khớp hoàn toàn → mọi line `matched`, `needs_approval=False`, không cảnh báo.
- Debit note lệch 1 khoản vượt ngưỡng → đúng line đó `variance`, `total_variance` đúng số tiền.
- Khoản có trong báo giá thiếu chi phí thực → `missing_actual`; khoản phát sinh ngoài báo giá → `extra_actual`.
- Tổng chênh lớn → `needs_approval=True`, status `escalated`; `accountant` gọi approve → 403; `manager` approve → 200.
- RBAC: `accountant` tạo/chạy được; `sales`/`docs` chỉ view (hoặc 403 tùy ma trận); `driver` không thấy.
- Demurrage: container quá free time → sinh dòng phí lưu ước tính đúng số ngày.

## 10. Checkpoint nghiệm thu (khớp master_roadmap GĐ6)
- [ ] Tạo quote + nạp debit note khớp → không cảnh báo lệch.
- [ ] Nạp debit note lệch giá → hệ thống chỉ đúng khoản lệch + số tiền.
- [ ] `ketoan` thao tác đối soát được; `sales` chỉ xem.
- [ ] Chênh lệch vượt ngưỡng → yêu cầu admin/manager duyệt.
- [ ] `pytest backend/` PASS toàn bộ.

## 11. KHÔNG làm giai đoạn này
- Không xuất ERP MISA/Fast thật (chỉ chuẩn bị dữ liệu; export để giai đoạn sau nếu cần).
- Không tự gửi giấy báo nợ qua email cho khách.
- Không đụng Kanban/shipment (GĐ7) hay hải quan (GĐ7A).
