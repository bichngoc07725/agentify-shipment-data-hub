# Agentify — Master Roadmap (Code + Phân quyền)

Tài liệu này gộp 2 hướng song song: **phân quyền (RBAC)** và **chức năng nghiệp vụ 6 bước**, chia thành các giai đoạn tuần tự.
Cách dùng: mỗi giai đoạn có phần **"Giao cho Claude Code"** (mô tả việc để AI code thực thi) và phần **"Checkpoint nghiệm thu"** (checklist để bạn kiểm tra đạt/chưa — không cần đọc code, chỉ chạy lệnh/bấm thử theo mô tả).

Nguyên tắc xuyên suốt:
- RBAC nền dựng trước, sau đó **mỗi entity nghiệp vụ mới code tới đâu gắn quyền tới đó** (không dồn RBAC thành 1 đợt cuối).
- Mỗi giai đoạn phải có test tự động chạy xanh + checkpoint thủ công đạt thì mới sang giai đoạn sau.
- Bám data model hiện tại (container-centric + provenance `container_facts`), chỉ nâng cấp lên `shipment/job` ở Giai đoạn 7.

Bảng chuẩn trạng thái checkpoint: ✅ đạt / ❌ chưa đạt / ⏭️ bỏ qua (ngoài scope).

---

## Tổng quan 8 giai đoạn

| GĐ | Tên | Phụ thuộc | Kết quả chính |
|---|---|---|---|
| 0 | Chuẩn bị nền & test harness | — | Chạy được test, seed data, biết baseline |
| 1 | RBAC nền (users/login/role) | GĐ0 | Đăng nhập theo vai trò, có JWT + roles |
| 2 | Permission engine + áp vào endpoint đã có | GĐ1 | Quyền được enforce ở backend cho tính năng hiện tại |
| 3 | Frontend login + ẩn/hiện theo quyền | GĐ2 | UI phản ánh đúng vai trò |
| 4 | Entity RFQ/Quote (Bước 1) + quyền Sales | GĐ2 | Có baseline giá để đối soát |
| 5 | OCR/Vision ảnh (Bước 5) | GĐ2 (song song GĐ4) | Bóc tách ảnh container/seal/POD/EIR |
| 6 | Smart Reconciliation (Bước 6) + quyền Kế toán | GĐ4 | So khớp chi phí thực vs báo giá |
| 7 | Module hải quan (Bước 4) + Kanban/shipment | GĐ4,6 | Phân luồng, thuế, board 6 bước |
| 8 | Audit log + Zalo thật (đánh giá) | GĐ2 | Nhật ký thao tác nhạy cảm + kết luận Zalo |

---

## Giai đoạn 0 — Chuẩn bị nền & test harness

**Mục tiêu:** đảm bảo môi trường chạy được, có dữ liệu demo, biết trạng thái test hiện tại trước khi thêm gì.

**Giao cho Claude Code:**
- Chạy toàn bộ test backend hiện có (`backend/tests/`), báo cáo test nào xanh/đỏ.
- Chạy seed demo data (`test_seed_demo_data.py` / script seed tương ứng) và xác nhận DB có dữ liệu container/email mẫu.
- Khởi động backend + frontend_v2, chụp lại các route hiện có hoạt động (overview, containers, exceptions, emails).
- Ghi ra file `plan/baseline_status.md`: số test pass, các route chạy được, để làm mốc so sánh.

**Checkpoint nghiệm thu (bạn kiểm tra):**
- [ ] Chạy `pytest` trong `backend/` → tất cả test hiện có PASS (hoặc liệt kê rõ test nào fail và lý do).
- [ ] Mở được frontend_v2 trên trình duyệt, thấy danh sách container demo.
- [ ] File `plan/baseline_status.md` tồn tại và ghi rõ con số baseline.

---

## Giai đoạn 1 — RBAC nền (users / login / role / seed)

**Mục tiêu:** có tài khoản theo vai trò, đăng nhập ra JWT chứa roles. Chưa cần enforce quyền ở đây.

**Mô hình vai trò (đã chốt lại): 1 tài khoản = đúng 1 vai trò, quyền tách bạch hoàn toàn, không cộng dồn.**

**Giao cho Claude Code:**
- Thêm bảng `users` (id, username unique, password_hash, display_name, **role** — 1 cột enum duy nhất, is_active, created_at) vào `backend/db/models.py` + tạo migration alembic mới. **Không tạo bảng `user_roles`** (mỗi user chỉ 1 vai trò).
- `role` là enum cố định: `admin, manager, sales_cs, docs, ops, accountant, driver`.
- Endpoint `POST /auth/login` (route mới `backend/api/routes/auth.py`): nhận username/password, trả JWT chứa `user_id` + `role` (số ít). Hash bằng bcrypt/passlib.
- Seed 7 tài khoản demo mật khẩu mặc định: `admin/admin@123`, `manager/manager@123`, `sales/sales@123`, `docs/docs@123`, `ops/ops@123`, `ketoan/ketoan@123`, `taixe/taixe@123`.
- Giữ nguyên API key cũ cho job nội bộ (sync Gmail), chỉ thêm JWT cho endpoint user-facing.
- Viết test: login đúng mật khẩu trả token có đúng 1 role; sai mật khẩu trả 401.

**Checkpoint nghiệm thu:**
- [ ] Gọi `POST /auth/login` với `sales/sales@123` → nhận về token, trong token có `role: "sales_cs"` (đúng 1 vai trò).
- [ ] Login sai mật khẩu → trả lỗi 401.
- [ ] Mỗi tài khoản demo chỉ mang đúng 1 vai trò (không có user nào 2 role).
- [ ] `pytest` phần auth PASS.
- [ ] Tất cả test cũ vẫn PASS (không phá vỡ gì).

---

## Giai đoạn 2 — Permission engine + áp vào endpoint đã có

**Mục tiêu:** quyền được enforce thật ở backend cho những tính năng đang tồn tại.

**Giao cho Claude Code:**
- Tạo `backend/config/permissions.py`: dict tĩnh `{resource: {action: {roles}}}` đúng theo bảng mục 4 của `rbac_permission_design.md`.
- Tạo dependency `require_permission(resource, action)` (trong `backend/api/deps/permissions.py`): đọc JWT → lấy **role (1)** → cho qua nếu role nằm trong tập cho phép, ngược lại trả 403.
- **Bảng ánh xạ field → nhóm** (`document` / `operation` / `finance`) cho `container_facts`, dùng khi kiểm tra quyền sửa tay. Docs chỉ sửa nhóm `document`, Ops nhóm `operation`, Kế toán nhóm `finance` — không vai trò nào đụng field của vai trò khác.
- Áp vào endpoint đã có:
  - `manual_ingest.py` (paste Zalo) → action Create, cho phép: Ops, Docs.
  - Endpoint sửa `container_facts` thủ công (nếu chưa có thì tạo) → Edit, **kiểm tra 2 lớp**: (1) role có quyền Edit, (2) field thuộc đúng nhóm của role đó.
  - Resolve/approve exception → thêm cột `severity` phân biệt "thường" vs "nghiêm trọng" (vượt công nợ / chênh lệch chi phí lớn); loại nghiêm trọng chỉ Admin/Manager approve.
- Nguyên tắc tách bạch: mỗi role chỉ đúng quyền của mình, KHÔNG cộng dồn, quyền hệ thống chỉ Admin có.
- Viết test cho từng cặp (role, resource, action) quan trọng: đúng quyền → 200, sai quyền → 403.

**Checkpoint nghiệm thu:**
- [ ] Dùng token `ketoan` sửa field nhóm `document` (chứng từ) → bị chặn 403.
- [ ] Dùng token `docs` sửa field nhóm `document` → thành công; nhưng `docs` sửa field nhóm `finance` (chi phí) → bị chặn 403.
- [ ] Dùng token `ketoan` sửa field nhóm `finance` → thành công.
- [ ] Dùng token `sales` approve exception nghiêm trọng → bị chặn; token `admin` → thành công.
- [ ] Tài khoản Kế toán KHÔNG truy cập được endpoint cấu hình hệ thống/quản lý user.
- [ ] `pytest` phần permission PASS + toàn bộ test cũ PASS.

---

## Giai đoạn 3 — Frontend login + ẩn/hiện theo quyền

**Mục tiêu:** UI phản ánh đúng vai trò; backend vẫn là nơi chặn thật.

**Giao cho Claude Code:**
- Trang `frontend_v2/src/pages/LoginPage.tsx` gọi `/auth/login`, lưu JWT + role (số ít) vào auth context (`frontend_v2/src/lib/`).
- Route guard trong `router.tsx`: chưa login → về Login; vào trang không đủ quyền → chặn/ẩn.
- Ẩn/hiện nút Edit/Approve theo role trong `ExceptionsPage.tsx`, `ContainerDetailPage.tsx`, `ZaloIngestCard.tsx`.
- Hiển thị tên vai trò đang đăng nhập ở header.

**Checkpoint nghiệm thu:**
- [ ] Đăng nhập bằng `sales` → không thấy nút "Duyệt ngoại lệ nghiêm trọng".
- [ ] Đăng nhập bằng `admin` → thấy đủ nút cấu hình + duyệt.
- [ ] Đăng nhập bằng `taixe` → chỉ thấy phần liên quan tới mình, không vào được trang cấu hình.
- [ ] Bấm nút bị ẩn qua gọi API trực tiếp (nếu cố tình) vẫn bị backend chặn 403 (chứng minh không chỉ ẩn ở UI).

---

## Giai đoạn 4 — Entity RFQ/Quote (Bước 1) + quyền Sales

**Mục tiêu:** có baseline giá — điều kiện bắt buộc cho đối soát ở GĐ6.

**Giao cho Claude Code:**
- Bảng `quotes` (rfq): id, customer, pol, pod, commodity, container_type/qty, cargo_ready_date, incoterms; và các dòng phí báo giá `quote_charges` (loại phí, mô tả, đơn giá, currency) — bám cấu trúc phí ở BA Spec Bước 1 Luồng C (Ocean Freight, surcharges THC/CIC/FSC/DO/Doc, local charges).
- Liên kết quote ↔ container (một quote có thể ứng với 1 lô/nhiều container).
- CRUD API + UI trang Quote trong frontend_v2.
- Gắn quyền: Sales/CS = Create/Edit; các vai trò khác = View; công nợ/credit limit chỉ Kế toán quyết (chuẩn bị field, quyền theo ma trận).
- Test CRUD + test quyền (chỉ Sales sửa được).

**Checkpoint nghiệm thu:**
- [ ] Đăng nhập `sales` → tạo được 1 báo giá với đầy đủ các dòng phí, lưu thành công.
- [ ] Đăng nhập `docs`/`ops` → chỉ xem, không sửa được báo giá (403 khi thử).
- [ ] Mở 1 container có gắn quote → thấy báo giá liên quan.
- [ ] Test PASS.

---

## Giai đoạn 5 — OCR/Vision ảnh (Bước 5)  *(có thể chạy song song GĐ4)*

**Mục tiêu:** bóc tách dữ liệu từ ảnh container/seal/POD/EIR gửi từ hiện trường.

**Giao cho Claude Code:**
- Mở rộng `ZaloIngestCard` cho phép upload ảnh kèm text.
- Thêm nhánh vision trong pipeline (`gmail_service/field_extract.py` hoặc module mới): gọi model vision đọc số container, số seal, biển số xe, trạng thái từ ảnh; lưu kèm provenance (source=image) như các fact khác.
- Gắn ảnh vào đúng container (dựa số container nhận diện được / xác nhận thủ công khi mờ).
- Lưu file gốc + cho phép sửa tay khi OCR sai.
- Test: đưa ảnh mẫu → trích đúng số container/seal; ảnh mờ → vẫn lưu file + cho sửa tay.

**Checkpoint nghiệm thu:**
- [ ] Upload 1 ảnh container rõ → hệ thống nhận đúng số container/seal và gắn vào container tương ứng.
- [ ] Upload ảnh mờ → không crash, vẫn lưu ảnh và cho nhập tay.
- [ ] Fact từ ảnh hiển thị nguồn "image" trong provenance.
- [ ] Chỉ Ops/Tài xế được upload (theo quyền); vai trò khác bị chặn.

---

## Giai đoạn 6 — Smart Reconciliation engine (Bước 6) + quyền Kế toán

**Mục tiêu:** so khớp chi phí thực (debit note/charges đã extract) với báo giá gốc, làm nổi chênh lệch.

**Giao cho Claude Code:**
- Bảng `reconciliation_log`: container/quote ref, khoản phí, giá báo, giá thực, chênh lệch, trạng thái (khớp/lệch/đã giải trình).
- Logic so khớp: lấy `charges` đã extract từ debit note/invoice (đã có ở `field_extract.py`) đối chiếu với `quote_charges` (GĐ4) theo loại phí; đánh dấu khoản lệch, khoản thiếu, khoản phát sinh.
- Cảnh báo phí lưu container (demurrage/storage) tính từ `free_time_days` đã có + ngày thực tế.
- UI trang đối soát: bảng so sánh, tô đỏ chênh lệch, nút "duyệt/giải trình".
- Gắn quyền: Kế toán = Create/Edit/Approve; chênh lệch lớn → cần Admin/Manager duyệt (tái dùng cơ chế severity GĐ2).
- Test: quote vs debit note khớp → không cảnh báo; lệch → sinh dòng chênh lệch đúng số tiền.

**Checkpoint nghiệm thu:**
- [ ] Tạo quote + nạp debit note khớp → không có cảnh báo lệch.
- [ ] Nạp debit note lệch giá → hệ thống chỉ ra đúng khoản nào lệch, lệch bao nhiêu.
- [ ] Đăng nhập `ketoan` → thao tác đối soát được; `sales` → chỉ xem.
- [ ] Chênh lệch vượt ngưỡng → yêu cầu Admin/Manager duyệt.
- [ ] Test PASS.

---

## Giai đoạn 7 — Module hải quan (Bước 4) + Kanban/shipment

**Mục tiêu:** phân luồng hải quan + nâng data model lên `shipment/job` để có board 6 bước.

**Giao cho Claude Code (7A — hải quan):**
- Bảng `customs_declarations`: số tờ khai, ngày, mã phân luồng (Xanh/Vàng/Đỏ), mức kiểm hóa, các ô thuế cơ bản, lịch sử "bẻ luồng".
- Extract/nhập tay số tờ khai + phân luồng; gắn cảnh báo khi Luồng Đỏ/Vàng.
- Gắn quyền: Ops nhập; Docs/Kế toán xem.

**Giao cho Claude Code (7B — Kanban):**
- Thêm entity `shipments/jobs` bao trùm nhiều container + tham chiếu quote/booking/customs/reconciliation.
- Trang Kanban 6 cột (RFQ→báo giá, đặt chỗ, chứng từ, hải quan, giao nhận, đối soát); job di chuyển theo trạng thái.
- SLA/deadline gắn theo từng bước + vai trò phụ trách.

**Checkpoint nghiệm thu:**
- [ ] Nhập 1 tờ khai Luồng Đỏ → sinh cảnh báo, hiển thị đúng trạng thái.
- [ ] Đổi luồng (bẻ luồng) → lịch sử ghi lại thay đổi.
- [ ] Board Kanban hiển thị 1 job đi qua đủ 6 cột, kéo/chuyển trạng thái được.
- [ ] Mỗi cột hiển thị đúng dữ liệu từ entity liên quan (quote ở cột 1, booking cột 2...).
- [ ] Quyền theo vai trò đúng ở từng cột.

---

## Giai đoạn 8 — Audit log + đánh giá Zalo thật

**Mục tiêu:** nhật ký thao tác nhạy cảm + kết luận có làm Zalo API hay không.

**Giao cho Claude Code (8A — audit):**
- Bảng `audit_log`: user_id, role_used, action, resource_type, resource_id, detail JSON, created_at.
- Ghi log tại: approve exception nghiêm trọng, sửa container_facts tay, xác nhận credit limit, duyệt đối soát.
- Trang xem audit cho Admin.

**Giao cho Claude Code (8B — Zalo, chỉ nghiên cứu trước):**
- Đánh giá khả thi Zalo OA API cho luồng điều xe (không phải account cá nhân). Ghi kết luận vào `plan/zalo_feasibility.md`: khả thi/không, chi phí, rủi ro. **Chưa code tích hợp** cho tới khi có kết luận rõ.

**Checkpoint nghiệm thu:**
- [ ] Duyệt 1 exception nghiêm trọng → audit_log ghi đúng ai/lúc nào/làm gì.
- [ ] Admin xem được nhật ký; vai trò khác không xem được.
- [ ] File `plan/zalo_feasibility.md` có kết luận rõ ràng để bạn quyết định đầu tư hay không.

---

## Cách bạn kiểm tra nhanh sau mỗi giai đoạn (không cần đọc code)

1. Yêu cầu Claude Code chạy `pytest` trong `backend/` và dán kết quả → phải xanh.
2. Đăng nhập lần lượt vài vai trò và làm theo đúng checklist "Checkpoint nghiệm thu" của giai đoạn đó.
3. Với mỗi ô checklist: đánh ✅ nếu đúng như mô tả, ❌ nếu sai — chỉ khi tất cả ✅ (hoặc ⏭️ có lý do) mới sang giai đoạn sau.
4. Nếu ❌: yêu cầu Claude Code sửa đúng ô đó, không sang giai đoạn mới khi còn ❌.
