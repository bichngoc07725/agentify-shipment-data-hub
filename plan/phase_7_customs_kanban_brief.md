# GĐ7 — Brief tự chứa: Module Hải quan (Bước 4) + Kanban/Shipment 6 bước

> Brief tự chứa — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo). Đọc `plan/master_roadmap.md` mục GĐ7 để biết checkpoint. Giai đoạn này gồm 2 phần độc lập: **7A Hải quan** và **7B Kanban/Shipment**. Có thể làm 7A trước, 7B sau.

Ghi chú: `config/permissions.py` ĐÃ khai sẵn quyền cho `customs_declaration` (view: admin/manager/docs/ops/accountant; create: ops; edit: admin/ops). Chỉ cần gắn `require_permission` vào route, KHÔNG sửa ma trận.

---

# PHẦN 7A — Module Hải quan (Bước 4 nghiệp vụ)

## 1. Mục tiêu & vì sao
Lưu tờ khai hải quan + **kết quả phân luồng** (Xanh/Vàng/Đỏ) cho mỗi lô, cảnh báo khi Luồng Vàng/Đỏ (phát sinh phí lưu, chậm tiến độ), giữ lịch sử "bẻ luồng". Chủ sở hữu: `ops` nhập liệu; `docs`/`accountant` xem.

## 2. Bối cảnh nghiệp vụ (đủ để code)
Sau khi có bộ chứng từ, nhân viên/đại lý hải quan nhập số liệu vào phần mềm khai báo → hệ thống VNACCS trả về **số tờ khai chính thức** + **mã phân luồng**:
- **Luồng Xanh** (mã 1): thông quan ngay.
- **Luồng Vàng** (mã 2): kiểm tra hồ sơ giấy.
- **Luồng Đỏ** (mã 3): kiểm tra thực tế hàng — chậm 1-2 ngày, dễ phát sinh phí lưu.
Tờ khai có thể bị "bẻ luồng" (đổi từ Xanh sang Vàng/Đỏ) → cần lưu lịch sử thay đổi. Mã HS (mã số hàng hóa) đã được LLM extract sẵn (`gmail_service/field_extract.py` có field `hs_code`) — tái dùng, không tự xây bảng biểu thuế ở giai đoạn này.

## 3. Data model (`db/models.py` + migration `YYYYMMDD_0011_add_customs.py`)

### Bảng `customs_declarations`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| container_id | UUID FK→containers.id | |
| declaration_no | String nullable | số tờ khai VNACCS |
| declaration_type | Enum(`import`,`export`) | NK/XK |
| channel | Enum(`green`,`yellow`,`red`) nullable | phân luồng hiện tại |
| hs_code | String nullable | lấy từ fact đã extract |
| registered_at | DateTime nullable | ngày giờ đăng ký |
| cleared_at | DateTime nullable | ngày thông quan |
| tax_amount | Numeric nullable | tổng thuế (nếu có) |
| note | Text nullable | |
| created_by | UUID FK→users.id | |
| created_at, updated_at | DateTime | |

### Bảng `customs_channel_history` (lịch sử bẻ luồng)
`id, declaration_id FK, from_channel nullable, to_channel, changed_at, changed_by, reason Text nullable`.

## 4. Logic (`services/customs_service.py`)
- CRUD tờ khai. Khi `channel` đổi → tự ghi 1 dòng `customs_channel_history`.
- Khi tạo/đổi sang `yellow`/`red` → sinh exception (tái dùng `services/exception_service.py`): code `customs_yellow`/`customs_red`, mức cảnh báo tương ứng, gắn container.
- Prefill `hs_code` từ container_fact đã extract nếu có.

## 5. API (`api/routes/customs.py`, prefix `/api/v1/customs`)
- `POST /declarations` tạo (quyền `customs_declaration.create` → ops).
- `PUT /declarations/{id}` sửa/đổi luồng (quyền `edit` → admin/ops).
- `GET /declarations/{id}` + `GET /containers/{no}/customs` xem (quyền `view`).
- Route trả kèm `channel_history`.

## 6. Frontend
- Trong `ContainerDetailPage.tsx`: khu "Hải quan" — hiển thị số tờ khai, badge màu phân luồng (xanh/vàng/đỏ), lịch sử bẻ luồng. Form nhập chỉ hiện role `ops`.
- Cảnh báo Luồng Đỏ/Vàng xuất hiện trong `ExceptionsPage.tsx` (tự động qua exception engine).

## 7. Test (`tests/test_customs_service.py`, `test_customs_routes.py`)
- Tạo tờ khai Luồng Đỏ → sinh exception `customs_red`.
- Đổi Xanh→Đỏ → `customs_channel_history` ghi đúng from/to.
- RBAC: `ops` tạo được; `docs`/`accountant` chỉ view; `sales`/`driver` không.

## 8. Checkpoint 7A (khớp master_roadmap)
- [ ] Nhập tờ khai Luồng Đỏ → sinh cảnh báo, hiển thị đúng trạng thái.
- [ ] Bẻ luồng → lịch sử ghi lại thay đổi.
- [ ] Quyền theo vai trò đúng.

---

# PHẦN 7B — Kanban Job Board + entity Shipment

## 1. Mục tiêu & vì sao
Hiện tại dữ liệu xoay quanh `container`. Để hiển thị 1 lô hàng đi qua **đủ 6 bước** (RFQ→báo giá, đặt chỗ, chứng từ, hải quan, giao nhận, đối soát) cần entity cấp cao hơn `shipment/job` gom nhiều container + tham chiếu quote/booking/customs/reconciliation. Kanban giúp Sales/Ops/Manager thấy tiến độ, phát hiện job kẹt.

## 2. Data model (`db/models.py` + migration `YYYYMMDD_0012_add_shipments.py`)

### Bảng `shipments` (= job)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| shipment_no | String unique | mã job (VD `JOB-2026-0001`) |
| customer_name | String nullable | |
| direction | Enum(`import`,`export`) nullable | |
| stage | Enum(`rfq`,`booking`,`documents`,`customs`,`delivery`,`reconciliation`,`closed`) | cột Kanban hiện tại |
| quote_id | UUID FK→quotes.id nullable | |
| owner_role | Enum(UserRole) nullable | vai trò đang phụ trách stage hiện tại |
| sla_due_at | DateTime nullable | hạn của stage hiện tại |
| created_at, updated_at | DateTime | |

### Liên kết shipment ↔ container
Thêm cột `shipment_id` (UUID FK→shipments.id, nullable) vào bảng `containers` (một shipment gom nhiều container). Migration alter table.

## 3. Logic (`services/shipment_service.py`)
- CRUD shipment; API chuyển `stage` (kéo thả Kanban).
- Hàm tổng hợp trạng thái: từ shipment suy ra dữ liệu mỗi bước — quote (GĐ4), booking/free_time (đã có ở container), customs (7A), reconciliation (GĐ6) — để mỗi cột Kanban hiển thị tóm tắt đúng.
- Khi chuyển stage → cập nhật `owner_role` + `sla_due_at` theo bảng cấu hình bước→vai trò→SLA (VD documents→docs→48h).
- Job quá `sla_due_at` chưa chuyển bước → sinh exception SLA.

## 4. RBAC — thêm resource `shipment` vào `config/permissions.py`
```
"shipment": {
    "view": {ADMIN, MANAGER, SALES_CS, DOCS, OPS, ACCOUNTANT},
    "create": {ADMIN, MANAGER, SALES_CS, OPS},
    "edit": {ADMIN, MANAGER, SALES_CS, DOCS, OPS, ACCOUNTANT},  # đổi stage: ai phụ trách bước đó
},
```
Có thể siết: chỉ role đang là `owner_role` của stage mới được đẩy job sang bước sau (row-level, kiểm tra trong service).

## 5. API (`api/routes/shipments.py`, prefix `/api/v1/shipments`)
- `GET /shipments/board` trả dữ liệu Kanban gom theo `stage` (mỗi cột 1 mảng job kèm tóm tắt).
- CRUD + `POST /shipments/{id}/advance` chuyển stage.

## 6. Frontend
- Trang `src/pages/KanbanPage.tsx`: 6-7 cột theo `stage`, mỗi card = 1 job (mã, khách, container count, cảnh báo SLA). Kéo/nút chuyển stage (chỉ role phụ trách). Route trong `router.tsx`.
- Card link tới `ContainerDetailPage`/shipment detail.

## 7. Test (`tests/test_shipment_service.py`, `test_shipment_routes.py`)
- Tạo shipment gom 2 container → truy được cả 2.
- `advance` chuyển stage đúng thứ tự + cập nhật owner_role/SLA.
- Board trả đúng job theo từng cột.
- Job quá SLA → sinh exception.
- RBAC: role phụ trách bước mới đẩy được job; role khác 403.

## 8. Checkpoint 7B (khớp master_roadmap)
- [ ] Board Kanban hiển thị 1 job đi qua đủ 6 cột, chuyển stage được.
- [ ] Mỗi cột hiển thị đúng dữ liệu entity liên quan (quote cột 1, booking cột 2, customs cột 4, đối soát cột 6).
- [ ] Quyền theo vai trò đúng ở từng cột.
- [ ] `pytest backend/` PASS toàn bộ.

## 9. KHÔNG làm giai đoạn này
- Không xây bảng biểu thuế XNK / tính thuế tự động (chỉ lưu tax_amount nhập tay + hs_code đã extract).
- Không tích hợp VNACCS/ECUS thật (chỉ nhập tay kết quả phân luồng).
- Không làm audit log (GĐ8) hay Zalo (GĐ8).
