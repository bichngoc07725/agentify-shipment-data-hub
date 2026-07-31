# Baseline Status — Local Dev Run

Ngày chạy: 2026-07-29 (giờ VN), branch `feat/exception-engine-and-multi-channel-sources`.

Mục đích: mốc so sánh trước khi bắt đầu code tiếp — xác nhận toàn bộ stack chạy được local từ trạng thái sạch (chưa có `.env`/`app-config.yaml`/DB trước đó).

## 1. Môi trường đã dựng

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| Docker daemon | OK | Khởi động qua `open -a Docker`, mất ~1 phút |
| Postgres (`backend/compose_db.yaml`) | OK | Container `agentify-logistics-postgres`, port host `5443` |
| `backend/.env` | Đã tạo mới | `DATABASE_URL` trỏ `127.0.0.1:5443`, `EXTRACTION_PROVIDER=none` (chưa có Azure/Gemini key), Gmail OAuth chưa cấu hình |
| `backend/app-config.yaml` | Đã tạo mới | Copy nguyên từ `app-config-template.yaml`, đọc biến từ `.env` |
| Backend deps (`uv sync`) | OK | Python 3.12, không lỗi |
| DB schema | OK | `python -m scripts.reset_database` — drop + create từ model |
| Frontend deps (`npm install` trong `frontend_v2`) | OK | 72 package, 5 vulnerability npm audit (chưa xử lý, không chặn dev) |

**Lưu ý quan trọng**: `Gmail sync` và `AI extraction (Azure/Gemini)` **chưa được cấu hình** ở máy này — cần thêm `GMAIL_CREDENTIALS_FILE` thật + set lại `EXTRACTION_PROVIDER` và key tương ứng nếu muốn test luồng đó. Toàn bộ kết quả bên dưới chạy với dữ liệu seed thủ công, không qua Gmail thật.

## 2. Kết quả test suite backend

```bash
cd agentify-shipment-data-hub
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests
```

**129 passed, 0 failed** (0.59s). Toàn bộ 19 file test xanh, bao gồm:
`test_app_home_service`, `test_attachment_routes`, `test_database_config`, `test_db_init`, `test_db_models`, `test_deterministic_extract`, `test_exception_routes`, `test_exception_service`, `test_field_extract`, `test_generate_demo_email_corpus`, `test_gmail_adapter`, `test_gmail_fetcher`, `test_gmail_pipeline`, `test_gmail_sync_service`, `test_manual_ingest_service`, `test_script_path_setup`, `test_seed_demo_data`, `test_send_demo_emails`, `test_sync_job_service`.

Không có test nào bị skip hoặc xfail.

## 3. Seed demo data

```bash
./.venv/bin/python -m scripts.seed_demo_data
```

Kết quả ghi vào DB (qua `services.ingestion_service.ingest_processed_email`, không phải insert thẳng SQL):

| Bảng | Số dòng |
|---|---|
| gmail_connections | 1 |
| sync_jobs | 2 |
| emails | 15 |
| attachments | 14 |
| containers | 10 |
| container_facts | 85 |

Xác nhận bằng `psql` — container có đủ `booking_no`, `bl_no`, `pol`, `pod`, `status_text` thực tế (tiếng Việt), không rỗng.

## 4. Backend chạy local

```bash
uvicorn api.routes.api_main:app --host 127.0.0.1 --port 8766
```

- `GET /health` → `{"status":"ok","database":"ok"}`
- `GET /api/v1/containers?limit=3` → trả 10 container thật, đầy đủ field
- `GET /api/v1/exceptions?limit=2` → trả exception thật (`free_time_expiring`, severity `critical`, có `evidence`)
- `GET /api/v1/app-home` → `has_data: true`, `container_count: 10`, mailbox demo connected
- `GET /api/v1/emails?limit=1` → trả email thật

Entry point đúng là **`api.routes.api_main:app`** (không phải `endpoints:app` — file `endpoints.py` chỉ chứa enum route path nội bộ, không phải ASGI app).

## 5. Frontend chạy local

```bash
cd frontend_v2 && npm run dev
```

Vite chạy ở `http://localhost:5174`, tự proxy `/api` và `/health` sang backend `127.0.0.1:8766` (đúng như README mô tả).

Route đã kiểm tra bằng Playwright (điều hướng thật + snapshot DOM, không dùng dữ liệu giả lập):

| Route | Trạng thái | Console errors |
|---|---|---|
| `/` (Overview) | OK | 0 |
| `/containers` | OK | 0 |
| `/containers/MSCU1234567` (detail) | OK | 0 |
| `/exceptions` | OK — hiển thị đúng 26 exception thật (5 nguy cấp, 21 cảnh báo), khớp số liệu API | 0 |
| `/emails` | OK | 0 |
| `/setup` | OK | 0 |

Cảnh báo console duy nhất trên mọi trang: React Router v7 future-flag warning (không phải lỗi, không ảnh hưởng chức năng).

## 6. Việc chưa làm / cần quyết định tiếp

- Chưa cấu hình Gmail OAuth thật → chưa test được luồng `Connect Gmail` → `Sync now` end-to-end qua UI (mới test qua seed script trực tiếp).
- Chưa cấu hình Azure OpenAI/Gemini → extraction hiện tại chỉ chạy regex (`EXTRACTION_PROVIDER=none`), chưa kiểm chứng nhánh AI extraction trên máy này (dù đã có unit test riêng cho nhánh đó, xanh).
- `frontend/` (bản cũ) không được khởi động lại — `frontend_v2` là bản đang dùng theo README.
- Processes đang chạy nền cho phiên này: `uvicorn` (port 8766), `vite dev` (port 5174), Postgres container `agentify-logistics-postgres`. Cần dừng thủ công (`Ctrl+C` / `docker compose -f backend/compose_db.yaml down`) khi không dùng nữa.

---

## 7. Audit đối chiếu roadmap vs code — 2026-07-31

Rà lại toàn bộ dự án để tìm phần chưa xong và phần "báo xong nhưng không đúng sự thật". Con số ở mục 2 (129 passed) đã cũ — baseline hiện tại là **444 passed**.

### Đã sửa trong đợt này

| # | Vấn đề | Bằng chứng gốc | Xử lý |
|---|---|---|---|
| 1 | `pytest` fail khi chạy đúng cách CLAUDE.md mô tả (`cd backend && pytest`) — test neo vào `Path("backend")` nên phụ thuộc cwd, còn tạo rác `backend/backend/storage`. Checkpoint GĐ0 "tất cả test PASS" vì vậy không đúng. | `tests/test_gmail_adapter.py` | Neo vào `gmail_service.adapter.BACKEND_ROOT`; xanh từ cả hai cwd |
| 2 | Nút "Đánh dấu đã xử lý"/"Duyệt" ngoại lệ **không có tác dụng thật**: bảng `exception_actions` chỉ ghi, không nơi nào đọc; exception tính động nên F5 là hiện lại. | `services/exception_action_service.py`, `services/exception_service.py` | `load_exception_suppressions()` đọc action và loại ngoại lệ khỏi worklist; UI refetch sau khi thao tác |
| 3 | Toàn bộ API đọc **không cần đăng nhập** (containers, emails, exceptions, app-home, tải file đính kèm), và `POST /sync-jobs/{id}/run` kích hoạt sync Gmail vô danh. Các entry `view` trong `config/permissions.py` là code chết. | `api/routes/{containers,emails,attachments,exceptions,app_home,sync_jobs}.py` | Gắn `require_permission(..., "view")`; sync-jobs → `system_config`; thêm `tests/test_read_endpoints_require_auth.py` |

Quy tắc đã chốt cho #2: một action **ẩn ngoại lệ cho tới khi có dữ liệu nguồn mới hơn thời điểm xử lý**. Đánh dấu xong không ẩn vĩnh viễn — nếu email mới về làm ngoại lệ tái phát thì worklist phải nói lại.

### Còn tồn — chưa xử lý, cần quyết định

- **Kanban không kéo-thả.** Checkpoint GĐ7 ghi "kéo/chuyển trạng thái được"; `KanbanPage.tsx` chỉ có nút `advance` một chiều, không lùi được stage. Hoặc code drag-and-drop, hoặc sửa lại checkpoint cho đúng thứ đã làm.
- **Mâu thuẫn trong ma trận quyền với vai trò `driver`.** `field_image.create` cho phép Driver upload ảnh, nhưng `container_facts.view` (`ALL_STAFF`) lại loại Driver — nên Driver không mở được trang container để upload. Sau khi vá #3, Driver đăng nhập sẽ gặp 403 ở Overview/Containers/Exceptions/Emails. Cần thiết kế màn hình riêng cho Driver ở GĐ7 (`dispatch_order`, row-level scoping — đã có TODO sẵn trong `config/permissions.py`).
