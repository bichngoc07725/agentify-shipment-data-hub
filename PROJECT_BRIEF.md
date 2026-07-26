# Project Brief

## Agentify Logistics là gì?

Agentify Logistics đang được định hướng như một `Shipment Data Hub` cho doanh nghiệp logistics B2B/XNK, đặc biệt là forwarder và `3PL` SME tại Việt Nam.

Ý tưởng cốt lõi:

> Mỗi `shipment/container` nên có một hồ sơ duy nhất, gom dữ liệu đang nằm rải rác trong `email`, `Excel`, `PDF`, ảnh chứng từ và các nguồn thủ công khác để nhân viên tra cứu nhanh và trả lời khách chính xác hơn.

Agentify không nhằm thay thế:

- `TMS`
- `WMS`
- `ERP`
- phần mềm khai hải quan
- ePort
- forwarding software hiện có

Nó là lớp dữ liệu vận hành nằm phía trên các công cụ đó.

## Vấn đề thị trường đang có

Trong logistics B2B/XNK, dữ liệu thật thường bị phân mảnh:

- trạng thái lô nằm trong `Excel` hoặc `Google Sheet`
- booking, arrival notice, delay notice, debit note nằm trong `email`
- `POD`, `EIR`, ảnh seal/container nằm trong `Zalo` hoặc ảnh chụp
- một phần ngữ cảnh chỉ nằm trong đầu người phụ trách

Khi khách hỏi:

- container đang ở đâu
- ETA mới nhất là khi nào
- đã có `D/O` chưa
- đã giao kho chưa
- còn thiếu chứng từ gì

thì `CS/Ops/Docs/Account` thường phải mở nhiều nguồn, hỏi nhiều người, rồi tự ghép lại thành câu trả lời. Đây là pain chính mà prototype đang nhắm tới.

## Prototype hiện tại muốn chứng minh điều gì?

Prototype `v0.1` cần chứng minh một giá trị rất cụ thể:

> Người dùng logistics có thể search `container`, `booking`, `B/L` hoặc `PO` và ngay lập tức thấy email liên quan, chứng từ, timeline, dữ liệu trích xuất, trạng thái hiện tại và thông tin còn thiếu.

Luồng chính của prototype:

1. Kết nối `Gmail` với quyền `read-only`
2. Đồng bộ email logistics và attachment
3. Trích xuất dữ liệu từ email, `PDF`, ảnh, scan
4. Match dữ liệu vào đúng `shipment/container`
5. Tạo `shipment profile` và `timeline`
6. Cho phép search hoặc hỏi bằng ngôn ngữ tự nhiên, kèm nguồn tham chiếu

## Scope đang ưu tiên

Đã build xong:

- `Gmail API` integration + sync có filter
- parse email body và attachment, PDF text extraction
- deterministic extraction + `AI` extraction (Azure `gpt-5-nano`) với `JSON` schema chặt
- matching theo `container`, `booking`, `B/L`, `PO`
- `shipment profile` có provenance từng field
- exception engine: sắp hết free time, đã cập bến chưa có `D/O`, `ETA` đổi, thiếu chứng từ, lô im lặng
- document checklist theo chiều hàng nhập/xuất

Những gì nên tập trung build tiếp, theo thứ tự ưu tiên:

- `timeline` có source traceability cho từng shipment
- Q&A hoặc search có dẫn nguồn
- import file `Excel`/`Google Sheet` tracking để seed dữ liệu ngày đầu
- OCR/vision cho ảnh và `PDF` scan - cần cho `POD`/`EIR`, là mắt xích còn thiếu để đóng vòng free time
- forward/upload nội dung `Zalo` quan trọng, có consent

Những gì chưa nên làm ở giai đoạn này:

- gửi email tự động
- ingest `Zalo` tự động toàn phần
- tích hợp sâu với customs/ePort/`TMS`/`WMS`/`ERP`
- cho `LLM` query database trực tiếp
- biến Agentify thành một logistics platform quá rộng

## Nguyên tắc sản phẩm cần giữ

- Mọi dữ liệu trích xuất phải giữ `source`
- Nếu không có dữ liệu, phải trả lời rõ là chưa thấy trong Agentify
- Không đoán
- Matching phải có `confidence` và đường review khi không chắc
- Ưu tiên `human-in-the-loop`
- Ưu tiên prototype hẹp nhưng chạy được hơn là scope rộng nhưng mơ hồ

## Nhóm khách hàng nhắm tới

Nhóm đầu tiên là `forwarder`/`NVOCC` vừa và nhỏ **thiên hàng nhập đường biển**, 20-100 nhân sự, 100-500 shipment/tháng, tại TP.HCM - Bình Dương - Đồng Nai và Hà Nội - Hải Phòng.

Lý do không nhắm rộng hơn: nhóm này là nhóm duy nhất hội đủ ba điều kiện cùng lúc.

1. Pain xảy ra hằng ngày - `CS` trả lời hàng chục câu hỏi trạng thái mỗi ngày.
2. Pain có hóa đơn - phí `DEM`/`DET` tính theo ngày, theo container.
3. Dữ liệu gây pain nằm trong `email` và `PDF` - đúng thứ Agentify đọc được hôm nay.

Nhiều nhóm có pain lớn hơn về quy mô (nhà phân phối `B2B`, bán lẻ đa kênh, trucking) nhưng dữ liệu của họ nằm trong `Zalo`, điện thoại và `OMS`, nên bán cho họ đồng nghĩa với phải xây một sản phẩm khác trước.

Phân tích đầy đủ: `docs/market/agentify_market_research_v3.md`.

## Nên đọc gì trước khi làm việc?

Thứ tự khuyến nghị:

1. `docs/market/agentify_market_research_v3.md`
2. `docs/context-logistics/de_xuat_agentify_v3.md`
3. `plan/prototype_implementation_plan.md`
4. `docs/context-logistics/README_CONTEXT.md`
5. `docs/context-logistics/cum_8_cs_ops_account_tra_loi_khach.md`
6. `docs/context-logistics/cum_9_excel_email_zalo_file_thu_cong.md`

## Ưu tiên build ngắn hạn

Thứ tự ưu tiên hiện tại (1-5 đã xong):

1. kết nối và sync `Gmail`
2. ingest email + attachment
3. extraction + classification
4. shipment matching
5. shipment profile + exception/checklist
6. timeline có source traceability
7. search/Q&A có source

## Một câu mô tả dự án

> Agentify giúp mỗi `shipment/container` có một hồ sơ duy nhất để team logistics tra cứu nhanh trạng thái, chứng từ và bằng chứng vận hành từ dữ liệu đang bị rơi giữa email, file và chat - và cảnh báo trước những lô sắp phát sinh chi phí.
