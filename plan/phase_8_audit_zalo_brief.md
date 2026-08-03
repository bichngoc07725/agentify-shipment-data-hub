# GĐ8 — Brief tự chứa: Audit Log + Đánh giá Zalo + Export ERP

> Brief tự chứa — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo). Đọc `plan/master_roadmap.md` mục GĐ8 để biết checkpoint. Giai đoạn này gồm 3 phần: **8A Audit Log**, **8B Export ERP (MISA/Fast)**, **8C Đánh giá Zalo (chỉ nghiên cứu, chưa code)**.

---

# PHẦN 8A — Audit Log

## 1. Mục tiêu & vì sao
Ghi lại **ai làm gì, lúc nào** trên các thao tác nhạy cảm (duyệt ngoại lệ nghiêm trọng, sửa dữ liệu tay, xác nhận công nợ, duyệt đối soát). Đây chính là "bằng chứng" mà Kế toán cần khi có tranh chấp giá/chi phí — đúng pain point nghiệp vụ. Chỉ `admin` xem được nhật ký.

## 2. Hạ tầng đã có (TÁI SỬ DỤNG / TỔNG QUÁT HÓA)
- Đã có model `ExceptionAction` (migration `20260730_0007_add_exception_actions.py`) + `services/exception_action_service.py` (`record_exception_action` lưu `acted_by`, `acted_by_role`, action). Đây là audit chuyên biệt cho exception.
- GĐ8A = **tổng quát hóa** pattern này thành 1 bảng audit dùng chung cho mọi resource nhạy cảm, KHÔNG viết lại từ đầu — bám đúng cách `exception_action_service` ghi log.

## 3. Data model (`db/models.py` + migration `YYYYMMDD_0013_add_audit_log.py`)

### Bảng `audit_logs`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id | ai làm |
| role_used | Enum(UserRole) | vai trò lúc thao tác |
| action | String | VD `approve`,`edit`,`export`,`confirm` |
| resource_type | String | VD `reconciliation`,`container_fact`,`credit_limit` |
| resource_id | UUID nullable | id bản ghi bị tác động |
| detail | JSONB nullable | trước/sau, số tiền, lý do... |
| created_at | DateTime server_default now | |

Index trên `(resource_type, resource_id)` và `created_at`.

## 4. Logic (`services/audit_service.py`)
- Hàm `record_audit(session, user, action, resource_type, resource_id=None, detail=None)` — gọi tại đúng các điểm nhạy cảm:
  - Duyệt exception nghiêm trọng (hook vào `exception_action_service`).
  - Sửa `container_facts` tay (hook vào `container_service.update_container_fact`).
  - Duyệt đối soát chênh lệch lớn (GĐ6 `reconciliation approve`).
  - Xác nhận credit limit (khi entity này được code).
  - Export ERP (8B).
- Không chặn nghiệp vụ nếu ghi log lỗi (log là phụ trợ) nhưng phải log lỗi ra để dev biết.

## 5. API (`api/routes/audit.py`, prefix `/api/v1/audit`)
- `GET /audit` liệt kê log (filter theo resource_type/user/khoảng ngày) — quyền: chỉ `admin`. Thêm resource `audit` vào `config/permissions.py`:
```
"audit": { "view": {ADMIN} },
```

## 6. Frontend
- Trang `src/pages/AuditLogPage.tsx` (chỉ admin thấy trong menu): bảng thời gian / người / vai trò / hành động / resource / chi tiết. Route trong `router.tsx` có guard admin.

## 7. Test (`tests/test_audit_service.py`, `test_audit_routes.py`)
- Duyệt 1 exception nghiêm trọng → `audit_logs` có đúng 1 dòng ghi user/role/action/resource.
- `admin` GET /audit → 200; mọi role khác → 403.
- Sửa container_fact tay → sinh audit đúng.

## 8. Checkpoint 8A
- [ ] Duyệt exception nghiêm trọng → audit ghi đúng ai/lúc nào/làm gì.
- [ ] Admin xem được nhật ký; vai trò khác không.

---

# PHẦN 8B — Export ERP (MISA/Fast)

## 1. Mục tiêu
Xuất dữ liệu đối soát/giấy báo nợ (GĐ6) ra **file định dạng chuẩn** để import vào MISA/Fast — KHÔNG tích hợp API ERP thật, chỉ xuất file (CSV/Excel theo template). Quyền `erp_export` đã có sẵn trong `permissions.py` (accountant).

## 2. Logic + API (`services/erp_export_service.py`, route `api/routes/erp_export.py`)
- `GET /api/v1/erp-export/reconciliation/{id}` sinh file CSV/XLSX các dòng chi phí (mã phí, mô tả, số tiền, VAT) theo cột MISA/Fast — quyền `erp_export.export` (accountant).
- Ghi audit (8A) mỗi lần export.
- Có thể tái dùng thư viện tạo xlsx nếu đã có trong deps; nếu không, xuất CSV UTF-8-BOM (MISA đọc được).

## 3. Test + Checkpoint 8B
- [ ] Accountant export được file đối soát; role khác 403.
- [ ] File có đủ dòng phí, số tiền khớp bảng đối soát.
- [ ] Mỗi lần export sinh 1 audit log.

---

# PHẦN 8C — Đánh giá Zalo thật (CHỈ NGHIÊN CỨU, CHƯA CODE)

## 1. Mục tiêu
Kết luận rõ ràng có nên đầu tư tích hợp Zalo cho luồng điều xe/hải quan hay không, trước khi viết bất kỳ dòng code tích hợp nào.

## 2. Bối cảnh rủi ro đã biết (ghi trong memory dự án)
Zalo **không cung cấp API chính thức cho tài khoản cá nhân và group chat** — đây là USP nhưng rủi ro kỹ thuật cao nhất. Chiến lược "email-first + paste tay" (đã làm ở GĐ hiện tại) được khuyến nghị làm điểm khởi đầu phòng thủ tốt hơn.

## 3. Việc cần làm (Claude Code chỉ viết tài liệu, KHÔNG code)
Tạo `plan/zalo_feasibility.md` trả lời:
- Các con đường khả thi: (a) Zalo OA (Official Account) API — làm được gì, giới hạn gì với luồng nội bộ điều xe; (b) Zalo Business/ZNS; (c) giữ nguyên paste tay + mở rộng upload ảnh (đã có ở GĐ5); (d) không làm.
- Với mỗi con đường: chi phí, rủi ro pháp lý/kỹ thuật, công sức, mức đáp ứng nhu cầu "điều xe realtime".
- **Khuyến nghị 1 lựa chọn** + lý do, để anh Đạt/leader quyết.

## 4. Checkpoint 8C
- [ ] File `plan/zalo_feasibility.md` có phân tích ≥3 con đường + khuyến nghị rõ ràng.
- [ ] KHÔNG có code tích hợp Zalo nào được viết ở giai đoạn này.

---

## Ghi chú đóng dự án (sau GĐ8)
Khi cả 8 giai đoạn đạt checkpoint: chạy `pytest backend/` toàn bộ xanh, đăng nhập thử đủ 7 vai trò theo checklist từng giai đoạn trong `plan/master_roadmap.md`, và cập nhật `PROJECT_BRIEF.md` phần trạng thái. Prototype khi đó phủ đủ 6 bước nghiệp vụ + phân quyền riêng rẽ + audit.
