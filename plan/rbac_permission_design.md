# Agentify — Thiết kế Phân quyền (RBAC) — Draft v1

## 1. Hiện trạng (đã kiểm tra trong docs/code)

- **Chưa có** hệ thống phân quyền thật. Auth hiện tại chỉ là 1 API key chung (`backend/config/auth.py`), không có user/role nào được enforce.
- `plan/prototype_implementation_plan.md` có bảng `workspace_members` với `role IN ('admin','manager','member')` — nhưng đây là role generic (SaaS thông thường), **không map** với 6 vai trò nghiệp vụ thật của forwarder.
- `plan/prototype_implementation_plan.md` dòng 1221 liệt kê rõ **"Complex role-based permission model beyond admin/member"** là thứ chủ động **không build** ở giai đoạn prototype — đây là lý do phần này còn thiếu, không phải bị quên.
- BA Spec mục 5 ("Ma trận Phân quyền") đã có 1 bảng thô: 7 dòng tính năng × 6 vai trò, chỉ có 3 mức ✅/👁️/—. Bảng này tốt để tham khảo nhưng **chưa đủ để code** vì: không map vào entity/field cụ thể trong DB, không phân biệt hành động (view/tạo/sửa/duyệt/xuất), Admin và Manager bị gộp làm một, và nhiều entity trong bảng (RFQ/quote, tờ khai hải quan, giấy báo nợ, lệnh điều xe) **hiện chưa tồn tại** trong schema.

Kết luận: cần thiết kế lại một bảng phân quyền chi tiết hơn, gắn với entity thật (kể cả entity sẽ có trong roadmap), rồi mới đưa vào code.

## 2. Vai trò (giữ nguyên 6 vai trò theo BA Spec)

| Vai trò | Ghi chú thiết kế |
| --- | --- |
| **Admin** | Toàn quyền hệ thống + duyệt các ngoại lệ nghiệp vụ (vượt công nợ, chênh lệch chi phí lớn) |
| **Manager** | Gộp với Admin trong bảng gốc, nhưng nên tách: Manager chỉ xem báo cáo/duyệt nghiệp vụ, không cấu hình hệ thống (user, tích hợp Gmail...) |
| **Sales/CS** | Tạo/sửa RFQ, báo giá; chỉ xem công nợ (do Kế toán xác nhận) |
| **Docs** | Sửa chứng từ (Invoice/Packing List/SI/B/L), đối chiếu chéo, gửi khách xác nhận Draft B/L |
| **Ops** | Đặt chỗ tàu, tạo lệnh điều xe, cập nhật trạng thái container, xử lý ngoại lệ hải quan |
| **Kế toán** | Xác nhận hạn mức tín dụng, đối soát chi phí, xuất ERP |
| **Tài xế** | Chỉ xem/xác nhận lệnh **của chính mình**, gửi ảnh — không xem dữ liệu Job khác |

## 3. Entity/resource cần phân quyền (gồm cả entity tương lai từ gap-analysis trước)

| Resource | Trạng thái |
| --- | --- |
| `container` / `container_facts` | Đã có |
| `exception` | Đã có |
| `email` / `attachment` (nguồn Gmail/Zalo-paste) | Đã có |
| `sync_job`, `gmail_connection` | Đã có |
| `quote` / `rfq` | **Chưa có** — cần thêm (đã nêu ở gap-analysis) |
| `booking` (tách riêng khỏi container_facts) | Chưa có, hiện chỉ là facts rời |
| `customs_declaration` (tờ khai, phân luồng) | Chưa có |
| `debit_note` / `reconciliation_log` | Chưa có |
| `dispatch_order` (lệnh điều xe) | Chưa có (đang là text tự do qua ZaloIngestCard) |
| `erp_export_batch` | Chưa có |
| `user` / `workspace_member` | Có schema nhưng chưa gắn 6 role nghiệp vụ |

## 4. Ma trận quyền chi tiết (resource × action × role)

Action: **V**=View, **C**=Create, **E**=Edit, **A**=Approve, **X**=Export/xuất dữ liệu

| Resource | Admin | Manager | Sales/CS | Docs | Ops | Kế toán | Tài xế |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cấu hình hệ thống, user, kết nối Gmail | VCEAX | V | — | — | — | — | — |
| Quote/RFQ | V | V | **VCE** | V | V | V | — |
| Credit limit / công nợ khách hàng | VE | V | V (chỉ xem) | — | — | **VCEA** | — |
| Booking (đặt chỗ tàu) | V | V | V | V | **VCE** | — | — |
| Chứng từ (Invoice/Packing List/SI/Draft B/L) | V | V | V | **VCE** | V | V | — |
| Tờ khai hải quan / phân luồng | VE | V | — | V | **VCE** | V | — |
| Container facts — nhóm field CHỨNG TỪ (BL/invoice/packing/parties...) | V | V | — | **VE** | V | V | — |
| Container facts — nhóm field VẬN HÀNH (container/seal/vessel/ETA/DO/cutoff...) | V | V | — | V | **VE** | — | — |
| Container facts — nhóm field CHI PHÍ (charges/debit note...) | V | V | — | V | V | **VE** | — |
| Exception thường (nhắc việc, quá hạn) | VA | VA | V | **VE** (resolve) | **VE** (resolve) | V | — |
| Exception nghiêm trọng (vượt công nợ, chênh lệch chi phí lớn) | **VA** | **VA** | V | V | V | V | — |
| Lệnh điều xe (dispatch order) | V | V | — | — | **VCE** | — | **V + xác nhận trạng thái của mình** |
| Ảnh/POD gửi từ hiện trường | V | V | — | V | V | — | **C** (upload) |
| Debit note / đối soát chi phí | VA | VA | — | V | V | **VCEA** | — |
| Xuất dữ liệu sang ERP (MISA/Fast) | V | V | — | — | — | **VCX** | — |

Ghi chú quan trọng rút ra từ BA Spec khi thiết kế bảng trên:
- Mục 1 spec ghi rõ Admin duyệt "vượt hạn mức công nợ hoặc chi phí chênh lệch lớn" → 2 loại exception này phải tách riêng, không gộp chung mức duyệt với exception thường.
- Bước 1 Luồng B: quyết định duyệt/không duyệt booking mới dựa trên công nợ là quyền của **Kế toán**, Sales chỉ được xem kết quả, không tự quyết.
- Tài xế chỉ được thao tác trên **lệnh gán cho chính mình** — đây là phân quyền theo dòng dữ liệu (row-level), không chỉ theo resource, cần lưu ý khi code (không phải chỉ check role mà còn phải check `assigned_driver_id == current_user.id`).
- **Quyền sửa container_facts tách theo NHÓM FIELD (đã chốt lại)**: mỗi field trong `container_facts` được gắn 1 nhãn nhóm (`document` / `operation` / `finance`). Docs chỉ sửa field nhóm `document`, Ops chỉ nhóm `operation`, Kế toán chỉ nhóm `finance` — không vai trò nào đụng field của vai trò khác. Cần một bảng ánh xạ `field_name → group` để engine kiểm tra khi cho sửa tay.

## 5. Kiến trúc kỹ thuật đề xuất

1. **Data model**: bảng `users` (id, username, password_hash, display_name, **role** — 1 cột enum duy nhất, is_active, created_at). Mỗi user đúng 1 vai trò. Không dùng bảng nhiều-nhiều.
2. **Permission matrix tập trung 1 chỗ**: 1 file cấu hình (vd `backend/config/permissions.py`) khai báo dict `{resource: {action: [roles allowed]}}` đúng như bảng trên — tránh rải rác `if role == "admin"` khắp nơi, dễ audit khi leader hỏi lại.
3. **FastAPI dependency**: `require_permission(resource, action)` kiểm tra role của user hiện tại (lấy từ JWT/session) trước khi vào handler; với case row-level (tài xế), thêm check riêng trong service (không đưa vào bảng tĩnh).
4. **Frontend**: role lưu trong auth context → ẩn/hiện nút theo quyền, nhưng **backend luôn là nơi enforce thật sự**, frontend chỉ để UX tốt hơn.
5. **Audit log tối thiểu**: mọi hành động Approve/Edit trên resource nhạy cảm (exception nghiêm trọng, credit limit, debit note) nên ghi lại ai làm, lúc nào — vì đây chính là bằng chứng mà Persona "Chị Lan Kế toán" cần khi có tranh chấp.

## 6. Roadmap triển khai (3 giai đoạn, không làm 1 lần)

- **Giai đoạn 1 — MVP RBAC (làm ngay, không phụ thuộc entity mới):**
  `users` + `user_roles`, đăng nhập cơ bản, `require_permission` áp dụng cho các resource **đã tồn tại**: container_facts edit, exception resolve/approve. Đủ để chứng minh khái niệm phân quyền hoạt động.

- **Giai đoạn 2 — Gắn theo entity mới khi được code (quote, booking, customs_declaration, dispatch_order, debit_note):**
  Mỗi khi 1 entity mới ra đời (theo roadmap gap-analysis trước), thêm dòng tương ứng vào bảng permission, không cần sửa kiến trúc.

- **Giai đoạn 3 — RBAC động (chỉ làm nếu thực sự cần đa khách hàng/tùy biến):**
  Chuyển từ bảng tĩnh sang `permissions` + `role_permissions` trong DB để admin tự cấu hình quyền qua UI, không cần sửa code mỗi lần đổi rule.

## 7. Quyết định (đã chốt với leader/PO)

1. **Một tài khoản = đúng một vai trò (đã chốt lại)**: mỗi user chỉ giữ **1 role duy nhất**, quyền **tách bạch hoàn toàn**, không cộng dồn/union, không leo thang. Bỏ mô hình 1-2 vai trò trước đó. Về kỹ thuật: dùng **cột `role` thẳng trong bảng `users`** (không cần bảng `user_roles` nhiều-nhiều). Quyền hệ thống (quản lý user, cấu hình Gmail/tích hợp) **chỉ Admin** có.
2. **Login đơn giản**: chưa cần email/password thật theo từng cá nhân hay SSO. Dùng tài khoản gán theo **tên vai trò** + mật khẩu mặc định (VD `sales / sales@123`, `ketoan / ketoan@123`...), có thể đổi mật khẩu sau. Đủ dùng cho giai đoạn hiện tại, không chặn roadmap nâng cấp login thật sau này.
3. **Khuyến nghị của mình (đã áp dụng): tách Admin và Manager**, vì đây chính là cách hiện thực hoá nguyên tắc "không ai được toàn quyền ngoài phạm vi" ở mục (1):
   - **Admin**: duy nhất được cấu hình hệ thống (tạo/xoá tài khoản, gán vai trò, cấu hình Gmail/tích hợp) + duyệt ngoại lệ nghiệp vụ nghiêm trọng.
   - **Manager**: chỉ xem báo cáo/dashboard tổng và duyệt nghiệp vụ (SLA, chi phí chênh lệch) — **không** đụng vào cấu hình hệ thống hay tài khoản.
   - Lý do tách: nếu gộp chung, Manager mặc nhiên có luôn quyền quản trị hệ thống → vi phạm đúng nguyên tắc "kế toán (hay bất kỳ ai) không được toàn quyền" mà leader vừa nhấn mạnh. Tách ra giúp áp nguyên tắc **least privilege** nhất quán cho mọi vai trò, không riêng gì Kế toán.
