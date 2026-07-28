# Agentify Logistics

Agentify Logistics là prototype cho `Agentify Shipment Data Hub`, một lớp dữ liệu nằm phía trên các kênh vận hành logistics rời rạc như `Gmail`, `Excel`, `PDF`, ảnh chụp và các file đính kèm. Mục tiêu không phải thay thế `TMS`, `WMS`, `ERP` hay phần mềm forwarding, mà là gom dữ liệu của một shipment/container về một hồ sơ có thể tra cứu nhanh.

Prototype `v0.1` chứng minh một điều:

- Người dùng logistics có thể nhập `container`, `booking`, `B/L` hoặc `PO`.
- Hệ thống trả về các email liên quan, PDF liên quan, dữ liệu đã trích xuất, timeline và trạng thái tổng hợp.
- Mỗi thông tin đều giữ nguồn gốc rõ ràng để người dùng kiểm tra lại được.

## Prototype Này Làm Gì

Luồng dữ liệu cốt lõi hiện tại:

1. Kết nối `Gmail` bằng quyền chỉ đọc.
2. Đồng bộ email theo query và khoảng thời gian giới hạn.
3. Đọc body email và ingest attachment.
4. Trích text từ PDF (text-based) cho file nằm trong attachments.
5. Extract các field logistics như `container_no`, `booking_no`, `bl_no`, `pol`, `pod`, `etd`, `eta`, `vessel`, `voyage`.
6. Match dữ liệu vào shipment/container profile với confidence và provenance.
7. Cho phép tra cứu theo mã nghiệp vụ hoặc câu hỏi ngôn ngữ tự nhiên trên dữ liệu đã lưu.
8. Hiển thị kết quả kèm nguồn tham chiếu cụ thể, không tự bịa khi thiếu dữ liệu.

## Phạm Vi Hiện Tại

Trong prototype này, backend và frontend tập trung vào các phần sau:

- `Gmail API` với `gmail.readonly`
- Sync email có kiểm soát
- Ingest attachment và PDF text extraction
- Trích xuất field logistics có cấu trúc
- Shipment/container matching
- Shipment profile page
- Timeline và nguồn dữ liệu
- Search + tra cứu theo container/booking/B/L/PO


## Mô Hình Sản Phẩm

Agentify đóng vai trò là operational data hub:

- nguồn vào là email, PDF, ảnh, file đính kèm và dữ liệu đã sync
- đầu ra là một shipment/container profile dễ tra cứu
- mọi kết luận phải truy ngược được về email, attachment và timestamp

Nguyên tắc quan trọng:

- nếu không thấy dữ liệu, hệ thống phải nói `Not found in Agentify data`
- dữ liệu trích xuất phải giữ provenance
- match cần có confidence threshold và đường review cho case mơ hồ
- không được overwrite dữ liệu tin cậy một cách mù quáng

## Thị Trường Nhắm Tới

Nhóm khách hàng đầu tiên: **forwarder/NVOCC vừa và nhỏ thiên hàng nhập đường biển, 20-100 nhân sự, 100-500 shipment/tháng**.

Lý do chọn nhóm này thay vì "toàn ngành logistics": họ là nhóm duy nhất vừa có pain hằng ngày, vừa có pain quy đổi thành tiền mặt (phí `DEM`/`DET` tính theo ngày), vừa có dữ liệu gây pain nằm sẵn trong email và PDF - đúng thứ Agentify đọc được mà không cần tích hợp gì thêm.

Chi tiết khung chấm điểm, xếp hạng 10 nhóm khách hàng, ICP, mô hình ROI và TAM/SAM/SOM: [`docs/market/agentify_market_research_v3.md`](docs/market/agentify_market_research_v3.md).

## Nguồn Dữ Liệu

Agentify gom dữ liệu lô hàng từ nhiều kênh. Mỗi kênh có trạng thái thật, không hứa cái chưa làm được:

| Nguồn | Trạng thái | Ghi chú |
|---|---|---|
| `Gmail` | Đang chạy | OAuth chỉ đọc. Email + PDF đính kèm là nguồn chính |
| `Zalo` | Thủ công, có kiểm duyệt | Người dùng dán tin nhắn, xem Agentify đọc ra gì, rồi mới xác nhận lưu |
| Upload chứng từ | Roadmap | Cần OCR/vision cho ảnh `POD`/`EIR` và PDF scan |
| `Excel`/`Google Sheet` | Roadmap | Import file tracking để seed dữ liệu ngày đầu |
| `ECUS`/`VNACCS`, ePort, `TMS` | Ngoài phạm vi | Hệ thống lõi - Agentify nằm cạnh, không thay thế |

### Vì sao Zalo là thủ công

Đọc Zalo tự động cần quyền truy cập toàn bộ hội thoại cá nhân - một thứ sản phẩm không nên xin, và bản market research nêu rõ hứa điều đó là sai lầm. Thay vào đó người dùng giữ vai trò gác cổng: dán tin cần lưu, review kết quả trích xuất, rồi mới ghi vào hồ sơ.

Tin nhắn Zalo được lưu **ngang hàng với email** trong cùng bảng, phân biệt bằng cột `channel`. Nhờ vậy container profile, provenance và exception engine xử lý chúng y hệt nhau.

### Nhắc tới chứng từ ≠ có chứng từ

Đây là ranh giới quan trọng. Một tin nhắn Zalo báo "đã có `D/O` số DO-2026-4471" là **bằng chứng D/O tồn tại**, nhưng **không phải là file D/O**. Agentify tách hai thứ đó:

| | Nguồn | Tác động |
|---|---|---|
| Có file | Attachment được phân loại là `delivery_order` | Tính vào checklist chứng từ, tăng completeness |
| Chỉ được nhắc tới | Tin nhắn/email được phân loại là `delivery_order` | **Không** tính vào checklist; hiển thị `Có thông tin, chưa có file` |

Vì sao tách: `Ops` cần biết "D/O có chưa" để khỏi mất phí lưu container - nên một `do_no` trích được từ Zalo là đủ tắt cảnh báo `free_time_expiring`. Nhưng `Docs` vẫn phải đi lấy file thật, nên checklist không được nói dối rằng chứng từ đã có.

Quy tắc áp dụng cho mọi kênh, không riêng Zalo: một email body nói về `D/O` mà không đính kèm file cũng chỉ được tính là "có thông tin".

```text
POST /api/v1/manual-ingest/preview   → xem Agentify đọc được gì, không ghi gì
POST /api/v1/manual-ingest           → xác nhận và lưu vào hồ sơ
```

## Giao Diện Demo

Frontend hiện có 6 màn chính:

- `/` - `Tra cứu`
- `/exceptions` - `Ngoại lệ cần xử lý`
- `/setup` - `Nguồn dữ liệu`
- `/containers` - `Danh mục container`
- `/containers/:containerNo` - `Chi tiết container`
- `/emails/:id` - `Chi tiết email nguồn`

### 1. Trang Tra Cứu

Đây là màn demo chính cho CS/Ops. Người dùng nhập mã `container`, `booking`, `B/L` hoặc `PO` vào ô tra cứu để xem danh sách kết quả hoặc đi thẳng sang chi tiết nếu chỉ có một match rõ ràng.

Màn này hiển thị:

- số container hiện có
- mailbox đang kết nối
- đường dẫn sang toàn bộ danh mục container
- danh sách container gần đây hoặc kết quả tra cứu

Đây là màn phù hợp nhất để demo giá trị cốt lõi của prototype: tìm một mã và mở ra ngay dữ liệu liên quan.

### 2. Trang Nguồn Dữ Liệu

Màn này liệt kê toàn bộ kênh dữ liệu kèm trạng thái thật của từng kênh.

Với `Gmail`, người dùng có thể:

- kết nối qua OAuth chỉ đọc
- tạo và chạy sync job với query giới hạn
- xem lịch sử sync, số attachment, số PDF đã extract, số container đã upsert

Với `Zalo`, người dùng có thể:

- dán tin nhắn cần lưu, kèm tên nhóm chat và người gửi
- bấm `Xem Agentify đọc được gì` để xem trước container, `D/O`, free time trích xuất được - **chưa ghi gì vào hồ sơ**
- thấy rõ container nào đã có, container nào sẽ được tạo mới
- bấm `Xác nhận lưu vào hồ sơ` để commit

Màn này nên được dùng trước khi demo nếu cần nạp dữ liệu mới hoặc kiểm tra pipeline.

### 3. Danh Mục Container

Trang này cho phép quét nhanh toàn bộ container đã có trong hệ thống.

Người dùng có thể:

- tìm theo mã container, booking, B/L, PO, cảng hoặc trạng thái
- lọc theo trạng thái nghiệp vụ
- xem mức độ đầy đủ của dữ liệu
- mở chi tiết từng container

Màn này hữu ích khi người dùng muốn rà soát nhanh nhiều shipment thay vì tra một mã duy nhất.

### 4. Chi Tiết Container

Trang chi tiết là nơi thể hiện rõ nhất giá trị của Agentify.

Nó hiển thị:

- container number
- status text tổng hợp
- `ETA` / `ETD`
- `POL` / `POD`
- booking, B/L, PO, vessel, voyage
- số lượng source data và attachment
- danh sách email liên quan
- danh sách attachment liên quan
- provenance của từng field đã trích xuất

Từ đây người dùng có thể đi ngược về email nguồn hoặc mở trực tiếp PDF.

### 5. Chi Tiết Email Nguồn

Màn này dùng để kiểm tra bản gốc của dữ liệu.

Người dùng có thể:

- xem người gửi, tiêu đề, thời điểm gửi, người nhận
- đọc body email
- xem attachment
- mở preview PDF ngay trong giao diện
- xem các extracted facts được ghi nhận từ email đó
- nhảy sang container liên kết nếu có

Màn này quan trọng khi cần audit hoặc xác minh một field cụ thể đến từ đâu.

### 6. Ngoại Lệ Cần Xử Lý

Đây là màn chuyển Agentify từ công cụ tra cứu bị động sang hệ thống cảnh báo chủ động: thay vì người dùng phải biết cần tìm mã nào, Agentify chỉ ra lô nào cần xử lý hôm nay.

Sáu loại ngoại lệ, tất cả tính từ dữ liệu email/PDF đã có:

| Mã | Ngoại lệ | Mức |
|---|---|---|
| `free_time_expiring` | Sắp hoặc đã quá hạn free time mà chưa thấy `D/O` | Nguy cấp |
| `arrived_no_do` | Đã có `ATA` nhưng chưa thấy `Delivery Order` | Nguy cấp |
| `eta_changed` | Hai bản `ETA` mới nhất khác nhau - cần kiểm tra đã báo khách chưa | Cảnh báo |
| `missing_documents` | Thiếu chứng từ so với bộ chuẩn theo chiều hàng nhập/xuất | Cảnh báo |
| `stale_no_update` | Lô không có nguồn dữ liệu mới quá 7 ngày | Cảnh báo |
| `unlinked_charges` | Có debit note/invoice nhưng chưa đối soát | Thông tin |

Mỗi cảnh báo đều kèm **căn cứ** (`ATA`, số ngày free time, tên file nguồn). Khi số ngày free time chưa có trong chứng từ, hệ thống tạm tính và **nói rõ là đang tạm tính** thay vì im lặng đoán.

## Kiến Trúc & Luồng Hoạt Động

```
Gmail (OAuth readonly)  ─┐
Zalo (dán tin nhắn)     ─┼─► backend (FastAPI) ─► Postgres
Upload thủ công         ─┘        │
                                   ├─ regex trích xuất field logistics (luôn chạy trước)
                                   └─ LLM (Azure OpenAI / Gemini, tuỳ config) bổ sung/chính xác hoá
                                          nếu LLM lỗi hoặc không cấu hình → giữ nguyên kết quả regex
                                          (extraction_status=partial, không mất dữ liệu)
                                   │
                                   ▼
                        container/shipment profile (có provenance)
                                   │
                                   ▼
                    frontend (React + Vite) ──proxy /api,/health──► backend
```

- Backend và frontend là 2 tiến trình độc lập, không phụ thuộc runtime lẫn nhau ngoài HTTP. Khi chạy `npm run dev`, Vite tự proxy `/api` và `/health` sang backend (xem `frontend_v2/vite.config.ts`, biến `VITE_PROXY_TARGET`, mặc định `http://127.0.0.1:8766`).
- Khi deploy bằng Docker (cả hai đều có Dockerfile riêng), frontend và backend nên join chung một Docker network để container frontend gọi được backend qua tên service thay vì `127.0.0.1` — xem phần Frontend bên dưới.
- Đồng bộ Gmail chạy theo 2 chế độ: lần đầu dùng `query` người dùng nhập (vd. `newer_than:30d`); các lần sau dùng Gmail History API (bỏ qua `query`) để chỉ lấy email mới kể từ lần sync trước. Một email không đọc được (đã bị xoá, quyền truy cập lỗi...) sẽ bị bỏ qua và ghi nhận trong `error_message` của sync job, không làm hỏng cả job.

## Cách Chạy

### Backend

1. Vào thư mục backend và cài dependency:

```bash
cd backend
uv sync
```

2. Tạo file cấu hình ở `backend/.env` và `backend/app-config.yaml`.

- `backend/.env` chứa các biến môi trường runtime, ví dụ `DATABASE_URL`, `INTERNAL_API_KEY`, `GMAIL_*`, `AZURE_OPENAI_*`, `GEMINI_*`.
- `backend/app-config.yaml` là file cấu hình mà backend đọc trực tiếp lúc khởi động. Bạn có thể dùng `backend/app-config-template.yaml` làm mẫu.

Cả hai file đều nằm trong `.gitignore` nên API key không bị commit.

> **Lưu ý khi deploy trên VPS chỉ có IP (không có domain):** Google chặn OAuth 2.0 redirect URI là địa chỉ IP trần và bắt buộc HTTPS (trừ `localhost`). Nếu server chỉ có IP, `GMAIL_REDIRECT_URI` trỏ thẳng vào IP sẽ báo lỗi `Access blocked: ... doesn't comply with Google's OAuth 2.0 policy`. Cách khắc phục nhanh không cần domain riêng: dùng [ngrok](https://ngrok.com) tạo một static domain HTTPS miễn phí trỏ vào backend (`ngrok http --url=<your-domain>.ngrok-free.app 8766`), rồi dùng domain đó cho `GMAIL_REDIRECT_URI` và trong Google Cloud Console (APIs & Services → Credentials → OAuth client → Authorized redirect URIs). Frontend vẫn truy cập bình thường qua IP:port, chỉ riêng bước callback OAuth cần domain HTTPS này.

#### Cấu hình trích xuất

`EXTRACTION_PROVIDER` chọn backend đọc chứng từ:

| Giá trị | Hành vi |
|---|---|
| `auto` (mặc định) | Dùng Azure nếu đã cấu hình đủ, không thì Gemini, không nữa thì chỉ chạy regex |
| `azure_openai` | Azure AI Foundry Responses API với JSON schema chặt |
| `gemini` | Google Gemini |
| `none` | Chỉ chạy deterministic regex - không gọi LLM nào |

Với Azure, `AZURE_OPENAI_ENDPOINT` là **URL Responses API đầy đủ** và `AZURE_OPENAI_DEPLOYMENT` là **tên deployment**, không phải tên model:

```bash
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.services.ai.azure.com/openai/v1/responses
AZURE_OPENAI_DEPLOYMENT=gpt-5-nano-file
```

Liệt kê deployment thật của resource:

```bash
curl -s "https://YOUR-RESOURCE.services.ai.azure.com/openai/deployments?api-version=2023-03-15-preview" -H "api-key: $AZURE_OPENAI_API_KEY"
```

Extraction luôn chạy regex trước rồi mới gọi LLM. Nếu LLM lỗi hoặc không cấu hình, pipeline vẫn tạo được hồ sơ container từ regex và đánh dấu `extraction_status=partial` - email không bị mất.

3. Chạy PostgreSQL bằng Docker:

```bash
docker compose -f compose_db.yaml up -d postgres
```

4. Khởi tạo schema:

- **Lần đầu / môi trường dev, chưa có dữ liệu cần giữ:** tạo lại toàn bộ schema từ model (drop + create, **xoá sạch dữ liệu hiện có**):

  ```bash
  ./.venv/bin/python -m scripts.reset_database
  ```

- **Đã có dữ liệu thật cần giữ (vd. email/container đã sync trên server đang chạy):** dùng Alembic để chỉ áp dụng phần schema còn thiếu, không đụng vào dữ liệu cũ:

  ```bash
  ./.venv/bin/python -m alembic upgrade head
  ```

5. Chạy backend bằng Docker:

```bash
docker compose up -d --build
```

### Frontend

Có 2 cách chạy, tuỳ mục đích.

#### Cách 1: Chạy dev cục bộ (`npm run dev`)

```bash
cd frontend_v2
npm install
npm run dev
```

Vite chạy ở `http://localhost:5174`, tự proxy `/api` và `/health` sang backend ở `http://127.0.0.1:8766` (đổi bằng biến môi trường `VITE_PROXY_TARGET` nếu backend chạy ở host/port khác — xem `frontend_v2/vite.config.ts`).

#### Cách 2: Chạy bằng Docker (dùng khi deploy lên server)

Repo có sẵn `frontend_v2/Dockerfile` và `frontend_v2/docker-compose.yml`. Cách này hữu ích khi deploy lên VPS: container tự bind ra ngoài qua Docker, không bị chặn bởi firewall cấp OS như khi chạy `npm run dev` trần (`ufw`/iptables thường không lọc port mà Docker publish ra).

```bash
cd frontend_v2
docker compose up -d --build
```

Mặc định, compose file join vào network `agentify-logistics-app-net` (được tạo khi chạy `docker compose up` ở `backend/`) và trỏ `VITE_PROXY_TARGET` vào tên service backend (`http://agentify-logistics-api:8766`) thay vì `127.0.0.1` — bắt buộc phải chạy backend bằng Docker trước để network này tồn tại. Đổi `VITE_PROXY_TARGET` trong `frontend_v2/docker-compose.yml` nếu cấu trúc network khác.

Dù chạy theo cách nào, frontend và backend đều đã có sẵn code trong repo, không cần build gì thêm ngoài các bước trên. Điểm quan trọng: DB không tự reset khi app khởi động; muốn tạo lại schema thì chạy script/migration riêng ở backend (xem mục Backend ở trên).

### Chạy test

```bash
cd backend && uv sync && cd .. && PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests
```

Test phải chạy từ thư mục gốc của repo vì `test_gmail_adapter.py` giải đường dẫn storage theo `backend/` tính từ cwd.

### Migration

Schema có thêm ba cột phục vụ exception engine (`containers.do_no`, `containers.ata`, `containers.free_time_days`):

```bash
cd backend && ./.venv/bin/python -m alembic upgrade head
```

Nếu bạn dùng `scripts.reset_database` (tạo lại schema từ model) thì không cần chạy migration.
