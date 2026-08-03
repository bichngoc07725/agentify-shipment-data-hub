# GĐ4 — Brief tự chứa: Entity RFQ/Quote (Bước 1 nghiệp vụ)

> Brief này tự chứa đủ ngữ cảnh — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo) để nắm pattern & RBAC. Đọc thêm `plan/master_roadmap.md` mục GĐ4 để biết checkpoint nghiệm thu.

## 1. Mục tiêu & vì sao làm giai đoạn này
Tạo entity **Quote (báo giá) / RFQ (yêu cầu hỏi giá)** — nơi lưu "giá đã báo cho khách". Đây là **baseline bắt buộc** để GĐ6 (đối soát chi phí) so khớp chi phí thực với giá đã báo. Không có Quote thì không làm được đối soát. Chủ sở hữu nghiệp vụ: vai trò `sales_cs`.

## 2. Bối cảnh nghiệp vụ (trích từ quy trình thật, đủ để code)
Bước 1 quy trình forwarder VN: khách gửi RFQ (qua email/Zalo) → Sales hỏi giá hãng tàu → cộng phụ phí + phí local → lập **báo giá** gửi khách. Một báo giá gồm 4 khối:
1. **Cước biển chính (Ocean Freight)**: đơn giá theo loại container, loại giá (contract/spot), thời hạn hiệu lực báo giá.
2. **Phụ phí đi kèm cước biển (Surcharges)**: FSC (phụ phí nhiên liệu), THC (xếp dỡ tại cảng), CIC (mất cân bằng container), phí vệ sinh container, D/O fee (làm lệnh giao hàng), Doc fee (chứng từ).
3. **Phí local tại VN**: các khoản thu tại đầu VN — dễ gây hiểu lầm vì "giá cước" ≠ "tổng chi phí thực".
4. **Điều khoản kèm theo**: điều khoản thanh toán (VD trả trước 30%), transit time dự kiến, ghi chú (VD "chưa gồm phí lưu container").

RFQ đầu vào (khách hỏi) gồm: tuyến (POL→POD), loại hàng + cờ hàng nguy hiểm/hàng lạnh, số lượng + loại container + trọng lượng, ngày hàng sẵn sàng (cargo ready date), điều kiện giao hàng (Incoterms: FOB/CIF/EXW...).

## 3. Data model cần thêm (`backend/db/models.py` + migration mới)

Tạo migration `backend/alembic/versions/YYYYMMDD_0008_add_quotes.py` (nối tiếp `down_revision` của bản mới nhất hiện tại là `..._0007_add_exception_actions`).

### Bảng `quotes`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | default uuid4 |
| quote_no | String unique | mã báo giá, sinh tự động (VD `Q-2026-0001`) |
| customer_name | String | tên khách hàng |
| status | Enum(`draft`,`sent`,`accepted`,`rejected`,`expired`) | vòng đời báo giá |
| pol | String nullable | cảng đi |
| pod | String nullable | cảng đến |
| commodity | String nullable | tên hàng |
| is_dangerous | Boolean default False | hàng nguy hiểm |
| is_reefer | Boolean default False | hàng lạnh |
| container_type | String nullable | VD `40HC` |
| container_qty | Integer nullable | số lượng cont |
| gross_weight_kg | Numeric nullable | trọng lượng |
| cargo_ready_date | Date nullable | ngày hàng sẵn sàng |
| incoterm | String nullable | FOB/CIF/EXW... |
| payment_term | String nullable | điều khoản thanh toán |
| transit_time | String nullable | thời gian vận chuyển dự kiến |
| valid_until | Date nullable | hạn hiệu lực báo giá |
| note | Text nullable | ghi chú |
| currency | String default `USD` | đơn vị tiền báo giá |
| created_by | UUID FK→users.id | ai tạo (phải là sales_cs) |
| container_id | UUID FK→containers.id nullable | liên kết lô hàng (1 quote ↔ 1 container ở prototype; để nullable vì RFQ có thể chưa có container) |
| created_at, updated_at | DateTime | timestamp |

### Bảng `quote_charges` (các dòng phí trong báo giá)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| quote_id | UUID FK→quotes.id | cascade delete |
| charge_group | Enum(`ocean_freight`,`surcharge`,`local`) | khối phí (mục 2 ở trên) |
| charge_code | String | VD `FSC`,`THC`,`CIC`,`DO`,`DOC`, hoặc tự do cho local |
| description | String | mô tả khoản phí |
| unit_price | Numeric | đơn giá |
| currency | String default `USD` | |
| quantity | Numeric default 1 | VD số container |
| amount | Numeric | = unit_price × quantity (tính khi lưu) |

Nhớ thêm `relationship` 2 chiều quotes ↔ quote_charges, và index trên `quote_id`, `quote_no`, `container_id`.

## 4. RBAC — gắn quyền (tái dùng cơ chế có sẵn)
Thêm vào `backend/config/permissions.py` resource `quote`:
- `view`: tất cả vai trò trừ `driver`.
- `create`, `edit`, `delete`: chỉ `sales_cs` (và `admin` nếu ma trận cho phép — theo `plan/rbac_permission_design.md`, các vai trò khác chỉ View).
Gắn `require_permission("quote","create"|"edit"|"view")` vào từng route như các route hiện có (tham khảo `backend/api/routes/containers.py`).

## 5. API cần thêm (`backend/api/routes/quotes.py`, prefix `/api/v1/quotes`)
- `POST /` tạo quote (kèm danh sách charges) — quyền `quote.create` (sales_cs).
- `GET /` list quote (filter theo customer/status/container_no) — quyền `quote.view`.
- `GET /{id}` chi tiết quote + charges — quyền `quote.view`.
- `PUT /{id}` sửa quote + charges — quyền `quote.edit` (sales_cs).
- `DELETE /{id}` — quyền `quote.delete`.
- `GET /api/v1/containers/{container_no}/quotes` (hoặc field trong container detail) để container detail hiển thị báo giá liên quan.
Schema request/response đặt trong `backend/api/models.py`. Logic trong `backend/services/quote_service.py`.

## 6. Frontend (`frontend_v2/`)
- Trang danh sách `src/pages/QuotesPage.tsx` + chi tiết/tạo/sửa `src/pages/QuoteDetailPage.tsx` (form 4 khối phí như mục 2). Thêm route vào `src/router.tsx`.
- Nút "Tạo/Sửa báo giá" chỉ hiện với role `sales_cs` (đọc role từ auth context như các trang khác đã làm).
- Ở `ContainerDetailPage.tsx`: thêm khu vực "Báo giá liên quan".

## 7. Test bắt buộc (`backend/tests/test_quote_service.py`, `test_quote_routes.py`)
- Tạo quote với đầy đủ 4 khối charges → lưu đúng, `amount` tính đúng = unit_price×quantity.
- List/filter quote trả đúng.
- Sửa quote cập nhật cả charges.
- **RBAC**: token `sales_cs` tạo/sửa được (200); token `docs`/`ops` tạo/sửa → 403; mọi role (trừ driver) view được.
- Liên kết container: quote gắn container_id → truy được từ container detail.

## 8. Checkpoint nghiệm thu (khớp master_roadmap GĐ4)
- [ ] Đăng nhập `sales/sales@123` → tạo được 1 báo giá đầy đủ 4 khối phí, lưu thành công.
- [ ] Đăng nhập `docs`/`ops` → chỉ xem, sửa/tạo bị 403.
- [ ] Container có gắn quote → container detail hiển thị báo giá liên quan.
- [ ] `pytest backend/` PASS toàn bộ (test mới + test cũ).

## 9. KHÔNG làm trong giai đoạn này (tránh scope creep)
- Không tự động sinh báo giá bằng AI từ RFQ (chỉ nhập/sửa tay + có thể prefill từ fact đã extract nếu dễ).
- Không làm đối soát (đó là GĐ6).
- Không gửi email báo giá cho khách.
- Không đụng tới credit limit/công nợ (chỉ chuẩn bị field nếu cần, quyền thuộc accountant — làm ở giai đoạn sau).
