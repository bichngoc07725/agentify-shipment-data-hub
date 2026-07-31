# GĐ5 — Brief tự chứa: OCR/Vision cho ảnh hiện trường (Bước 5 nghiệp vụ)

> Brief tự chứa — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo) để nắm pattern & RBAC. Đọc `plan/master_roadmap.md` mục GĐ5 để biết checkpoint.

## 1. Mục tiêu & vì sao làm
Cho phép **upload ảnh chụp từ hiện trường** (ảnh container/seal, EIR — phiếu giao nhận container rỗng, POD — bằng chứng giao hàng) và dùng model **vision** để bóc tách số container, số seal, biển số xe, trạng thái; lưu thành `container_facts` có provenance `source_type="image"` như các fact khác, gắn đúng container. Đây là ưu tiên "Cao nhất" theo quy trình Bước 5 (điều xe → tài xế chụp ảnh gửi về). Chủ sở hữu nghiệp vụ: `ops` và `driver`.

## 2. Bối cảnh nghiệp vụ (đủ để code)
Tại cảng, tài xế lấy container xong **chụp ảnh container + số niêm phong (seal)** gửi vào nhóm Zalo làm bằng chứng. Rủi ro thực tế: Zalo tự xóa file cũ → mất ảnh; ảnh không kèm số booking/Job nên khó gắn đúng lô. Vì vậy hệ thống cần: (a) nhận ảnh + lưu file gốc vĩnh viễn, (b) tự đọc số container/seal từ ảnh, (c) gắn vào đúng container (tự động nếu đọc được số, hoặc để người dùng chọn khi ảnh mờ), (d) luôn cho sửa tay khi OCR sai.

Các loại ảnh cần hỗ trợ ở giai đoạn này:
- **Ảnh container**: số container (11 ký tự ISO 6346, VD `MSKU1234567`), có thể thấy loại cont (40HC...).
- **Ảnh seal**: số niêm phong (chuỗi số/chữ trên kẹp chì).
- **EIR / phiếu giao nhận**: số container, số seal, tình trạng vỏ, ngày giờ, depot.
- **POD**: xác nhận đã giao (tên người nhận, ngày, chữ ký — chỉ cần đọc text rõ, không bắt buộc chữ ký viết tay).

## 3. Hạ tầng đã có sẵn (TÁI SỬ DỤNG, không viết lại)
- Model `Attachment` (`db/models.py`) đã có: `mime_type`, `storage_path`, `document_type`, `extracted_record` (JSONB), `text_extract_status`, `extracted_text`. Dùng lại cho ảnh — không cần bảng mới cho file.
- Model `ContainerFact` đã có đủ trường provenance: `source_type`, `source_label`, `confidence`, `attachment_id`, `document_type`. Ảnh → tạo fact với `source_type="image"`.
- Lưu file: pattern `ATTACHMENT_STORAGE_DIR = BACKEND_ROOT / "storage" / "gmail_attachments"` trong `gmail_service/adapter.py`. Tạo thư mục song song `storage/field_images/` theo cùng kiểu.
- LLM client: `gmail_service/llm_client.py` có `call_azure_openai(prompt, schema, schema_name)` dùng Azure Responses API với structured output (json_schema strict). **Cần mở rộng** để gửi kèm ảnh (input dạng image) — xem mục 5.
- Luồng ingest tay + gắn container đã có: `services/manual_ingest_service.py` (`container_numbers_in`, `split_known_containers`, `build_facts`) và route `api/routes/manual_ingest.py`. Bám luồng preview→confirm này.
- Validate số container ISO 6346 (checksum) đã có trong `gmail_service/deterministic_extract.py` — tái dùng để verify số container vision đọc được.

## 4. Data model — thay đổi tối thiểu
Không cần bảng mới. Chỉ:
- Cho phép `Attachment` không gắn `email_id` (ảnh field không tới từ email). Kiểm tra cột `email_id` hiện `nullable=False` → tạo migration `YYYYMMDD_0009_field_image_attachment.py` đổi `email_id` thành `nullable=True`, và thêm cột `channel`/`source` nếu cần phân biệt ảnh hiện trường (VD thêm `source_channel String default 'gmail'`, set `'field_upload'` cho ảnh). Nếu ràng buộc unique `(email_id, filename)` cản trở ảnh không-email → nới constraint cho phù hợp.
- (Tùy chọn) thêm giá trị `"image"` vào tập `source_type` hợp lệ khi tạo fact — hiện `source_type` là String tự do nên chỉ cần truyền đúng chuỗi.

## 5. Vision extraction (module mới `gmail_service/image_extract.py`)
- Hàm `extract_from_image(image_bytes, mime_type) -> dict`: mã hóa base64, gọi Azure Responses API với `content` gồm block `input_text` (prompt) + block `input_image` (data URL base64). Mở rộng `call_azure_openai` (hoặc thêm `call_azure_openai_vision`) để nhận thêm tham số ảnh — giữ nguyên cơ chế json_schema strict.
- Schema output đề xuất: `{container_no, seal_no, license_plate, doc_kind (container_photo|seal_photo|eir|pod), depot, datetime_text, raw_text, confidence}`.
- Sau khi có kết quả: chạy checksum ISO 6346 trên `container_no` (dùng hàm có sẵn ở `deterministic_extract.py`); nếu hợp lệ → gắn container tự động, nếu không → trả về cho user chọn/nhập.
- Nếu Azure chưa cấu hình (`azure_is_configured()` False) → không crash: vẫn lưu ảnh, đặt `text_extract_status="skipped"`, để user nhập tay.

## 6. API (mở rộng `api/routes/manual_ingest.py` hoặc route mới `api/routes/field_images.py`, prefix `/api/v1/field-images`)
- `POST /preview` (multipart, `UploadFile`): nhận ảnh → lưu tạm/đọc bytes → gọi `extract_from_image` → trả về gợi ý {container_no, seal_no, doc_kind, matched_container?, confidence, image_id} để user xác nhận/sửa. Quyền: `require_permission("field_image","create")`.
- `POST /` (confirm): nhận image_id + các field đã user chỉnh + container_no đích → lưu `Attachment` (mime ảnh, storage_path, document_type) + tạo `ContainerFact` `source_type="image"` gắn container. Quyền như trên.
- `GET /containers/{container_no}/images`: liệt kê ảnh của 1 container (cho container detail). Quyền `view`.
- Dùng `python-multipart` cho UploadFile (kiểm tra đã có trong deps chưa, nếu chưa thêm vào `pyproject.toml`).

## 7. RBAC — thêm resource `field_image` vào `config/permissions.py`
```
"field_image": {
    "view": ALL_STAFF,            # mọi nhân viên xem được ảnh
    "create": {OPS, DRIVER},      # chỉ Ops và Tài xế upload
},
```
Lưu ý row-level cho `driver`: giai đoạn này driver chưa có "lệnh của mình" (dispatch_order làm ở GĐ7) → tạm cho driver upload ảnh gắn container bất kỳ; ghi TODO siết row-level khi có dispatch_order.

## 8. Frontend (`frontend_v2/`)
- Mở rộng `src/components/sources/ZaloIngestCard.tsx`: thêm ô upload ảnh (kèm text tùy chọn). Sau upload → hiện preview kết quả vision (số container/seal đọc được, ảnh thu nhỏ), cho sửa trước khi xác nhận.
- Nút upload chỉ hiện với role `ops`/`driver` (đọc role từ auth context như trang khác).
- `ContainerDetailPage.tsx`: thêm khu "Ảnh hiện trường" hiển thị ảnh + fact nguồn image.

## 9. Test bắt buộc (`backend/tests/test_image_extract.py`, `test_field_image_routes.py`)
- Mock vision trả số container hợp lệ → tạo fact `source_type="image"` gắn đúng container; checksum pass.
- Ảnh mờ / vision trả số sai checksum → KHÔNG tự gắn, vẫn lưu ảnh + trạng thái chờ nhập tay (không crash).
- Azure chưa cấu hình → lưu ảnh, `text_extract_status="skipped"`, không lỗi.
- RBAC: token `ops`/`driver` upload được (200); token `sales`/`docs`/`accountant` → 403; mọi role view được.
- Ảnh không gắn email vẫn lưu được (migration nullable email_id hoạt động).

## 10. Checkpoint nghiệm thu (khớp master_roadmap GĐ5)
- [ ] Upload 1 ảnh container rõ → hệ thống đọc đúng số container/seal, gắn vào đúng container.
- [ ] Upload ảnh mờ → không crash, vẫn lưu ảnh + cho nhập tay.
- [ ] Fact sinh từ ảnh hiển thị nguồn "image" trong provenance ở container detail.
- [ ] Chỉ `ops`/`driver` upload được; role khác bị 403.
- [ ] `pytest backend/` PASS toàn bộ (mới + cũ).

## 11. KHÔNG làm giai đoạn này (tránh scope creep)
- Không tích hợp Zalo API thật (GĐ8 mới đánh giá).
- Không OCR chữ ký viết tay/biên bản giấy phức tạp (chỉ đọc text rõ).
- Không làm dispatch_order/điều xe có cấu trúc (GĐ7).
- Không đối soát chi phí (GĐ6).
