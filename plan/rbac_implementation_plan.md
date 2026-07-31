# Agentify — Plan code RBAC (dựa trên rbac_permission_design.md)

Nguyên tắc bám theo quyết định đã chốt: **1 tài khoản = đúng 1 vai trò, quyền tách bạch hoàn toàn (không cộng dồn/leo thang)**, sửa container_facts tách theo nhóm field, login theo tên vai trò + mật khẩu mặc định, tách Admin/Manager.

## Giai đoạn 1 — Data model + Auth cơ bản

**Migration mới** (thêm vào `backend/db/models.py` + alembic, theo đúng convention migration hiện có trong `backend/`):

- `users`: id (UUID), username (unique), password_hash, display_name, **role** (enum, 1 cột duy nhất — mỗi user đúng 1 vai trò), is_active, created_at.
- `role` enum cố định 7 giá trị — `admin, manager, sales_cs, docs, ops, accountant, driver` (Python `Enum` + Postgres `CHECK`). **Không tạo bảng `user_roles`** (đã chốt: 1 tài khoản = 1 vai trò, quyền tách bạch).

**Auth**:
- Endpoint `POST /auth/login` nhận username/password → trả JWT chứa `user_id` + `role` (số ít).
- Hash mật khẩu bằng `passlib`/`bcrypt`.
- Seed script (giống `test_seed_demo_data.py` đã có) tạo 7 tài khoản demo, mỗi tài khoản đúng 1 vai trò: `admin/admin@123`, `manager/manager@123`, `sales/sales@123`, `docs/docs@123`, `ops/ops@123`, `ketoan/ketoan@123`, `taixe/taixe@123`.
- Giữ API key hiện tại (`backend/config/auth.py`) song song cho các job nội bộ (sync Gmail...), không thay thế — chỉ thêm JWT cho user-facing endpoints.

**File cần đụng tới**: `backend/db/models.py`, migration mới trong thư mục alembic hiện có, `backend/config/auth.py` (mở rộng), route mới `backend/api/routes/auth.py`, service mới `backend/services/user_service.py`.

## Giai đoạn 2 — Permission engine

- File cấu hình trung tâm `backend/config/permissions.py`: dict tĩnh `{resource: {action: {roles cho phép}}}` đúng theo bảng ở mục 4 của `rbac_permission_design.md`.
- Dependency FastAPI `require_permission(resource, action)` trong `backend/config/auth.py` hoặc file mới `backend/api/deps/permissions.py`: đọc JWT → lấy roles → kiểm tra có role nào nằm trong tập cho phép không.
- Áp dụng ngay cho các endpoint **đã tồn tại**:
  - `backend/api/routes/manual_ingest.py` (paste Zalo) → action Create, role cho phép: Ops (điều xe), Docs (chứng từ) — theo ngữ cảnh nội dung paste.
  - Route sửa `container_facts` thủ công (nếu đã có endpoint correction — cần rà lại `backend/api/routes/containers.py`) → action Edit theo đúng field (Docs sửa field chứng từ, Ops sửa field vận hành, Kế toán sửa field charges).
  - Exception resolve/approve trong `backend/services/exception_service.py` + route liên quan → tách 2 mức: exception thường (Docs/Ops resolve được) vs exception nghiêm trọng — cần thêm cột `severity` phân loại "vượt công nợ/chênh lệch chi phí lớn" nếu chưa có, chỉ Admin mới Approve loại này.
- Row-level check (cho Tài xế sau này khi có `dispatch_order`): viết riêng 1 helper `check_owner(resource, user_id)`, không đưa vào bảng tĩnh vì đây là check theo dữ liệu chứ không phải theo role.

## Giai đoạn 3 — Frontend

- Thêm trang Login (`frontend_v2/src/pages/LoginPage.tsx`) gọi `/auth/login`, lưu JWT + roles vào auth context (`frontend_v2/src/lib/`).
- Route guard trong `frontend_v2/src/router.tsx`: chặn truy cập trang không đúng quyền (VD trang Exceptions nghiêm trọng chỉ Admin/Manager xem được nút Approve).
- Ẩn/hiện nút Edit/Approve theo role trong các trang đã có: `ExceptionsPage.tsx`, `ContainerDetailPage.tsx`, `sources/ZaloIngestCard.tsx`.
- Lưu ý: đây chỉ là UX, **quyền thật luôn được enforce ở backend** (Giai đoạn 2), tránh trường hợp sửa được qua gọi API trực tiếp.

## Giai đoạn 4 — Audit log (đi kèm approve/edit nhạy cảm)

- Bảng `audit_log`: user_id, role_used, action, resource_type, resource_id, detail (JSON), created_at.
- Ghi log tại đúng những action đã liệt kê "nhạy cảm" ở mục 4-5 của design doc: approve exception nghiêm trọng, sửa container_facts thủ công, xác nhận hạn mức tín dụng (khi entity credit limit được code).

## Thứ tự làm việc đề xuất

1. Giai đoạn 1 (users, roles, login, seed) — làm trước, không phụ thuộc gì, mở khóa mọi thứ sau.
2. Giai đoạn 2 áp cho các endpoint đã có sẵn hiện nay (container_facts, exception, manual_ingest) — chứng minh cơ chế hoạt động thật với dữ liệu thật.
3. Giai đoạn 3 (frontend) — làm song song hoặc ngay sau Giai đoạn 2, để có demo đầy đủ end-to-end.
4. Giai đoạn 4 (audit log) — có thể làm cuối, không chặn các phần khác, nhưng nên làm trước khi bất kỳ entity nhạy cảm mới (quote, debit note) được code, để mỗi entity mới sinh ra đã có log sẵn.
5. Khi các entity mới ở roadmap trước (quote/RFQ, booking, customs_declaration, dispatch_order, debit_note) được code, chỉ cần bổ sung dòng tương ứng vào `permissions.py` — không cần sửa kiến trúc Giai đoạn 1-2.

## Việc cần bạn xác nhận thêm (nhỏ, không chặn bắt đầu code)

- Field nào trong `container_facts` được coi là "thuộc Docs" vs "thuộc Ops" vs "thuộc Kế toán" khi cho sửa tay — cần liệt kê cụ thể danh sách field trước khi code Giai đoạn 2 (có thể làm song song lúc code Giai đoạn 1).
