# Đánh giá khả thi tích hợp Zalo thật (GĐ8C)

> Tài liệu nghiên cứu — KHÔNG có code tích hợp Zalo nào đi kèm. Mục tiêu: trả lời rõ có nên đầu tư tích hợp Zalo cho luồng điều xe/hải quan hay không, và nếu có thì theo con đường nào, trước khi viết bất kỳ dòng code tích hợp nào.

## 1. Vì sao câu hỏi này quan trọng

Zalo là kênh liên lạc thực tế của tài xế, đại lý hải quan và một phần khách hàng nội địa — nhưng **Zalo không cung cấp API chính thức cho tài khoản cá nhân và group chat**. Đây vừa là USP (nếu làm được, đối thủ khó copy) vừa là rủi ro kỹ thuật/pháp lý lớn nhất của cả sản phẩm. Chiến lược hiện tại (email-first + paste tay, đã code ở GĐ1–5) là điểm khởi đầu phòng thủ: không phụ thuộc API không chính thức, nhưng cũng không tự động hoá được việc đọc tin nhắn Zalo.

## 2. Bốn con đường

### (a) Zalo OA (Official Account) API

**Là gì:** Zalo Official Account — kênh chat 1-chiều/2-chiều giữa doanh nghiệp và người dùng đã follow OA, có API chính thức (Zalo OA API) để gửi/nhận tin nhắn, webhook nhận sự kiện.

**Làm được gì cho luồng điều xe:**
- Nhận tin nhắn văn bản + ảnh từ tài xế **nếu tài xế nhắn trực tiếp cho OA** (không phải group chat, không phải Zalo cá nhân của điều phối viên).
- Webhook đẩy tin nhắn về server theo thời gian thực → có thể tự động hoá việc đọc ảnh/text thay vì paste tay.
- Gửi thông báo chủ động cho tài xế (lệnh điều xe, nhắc hạn) qua OA — có giới hạn số tin/tháng theo gói (miễn phí có quota thấp).

**Giới hạn với luồng nội bộ hiện tại:**
- Nghiệp vụ hiện nay diễn ra trong **group chat Zalo cá nhân** giữa điều phối viên, tài xế, đại lý hải quan — không phải chat 1-1 với một OA. Zalo OA API **không đọc được nội dung group chat cá nhân**. Muốn dùng OA, toàn bộ quy trình phải đổi thói quen: mọi bên (tài xế, đại lý) phải nhắn trực tiếp cho OA thay vì group hiện tại.
- Cần đăng ký doanh nghiệp (giấy phép kinh doanh, xác minh), duyệt nội dung, và trả phí theo tier khi vượt quota tin nhắn.
- Zalo có thể thay đổi chính sách/API bất kỳ lúc nào (đã từng siết nhiều lần với OA của bên thứ ba) — rủi ro phụ thuộc nền tảng đóng.

**Chi phí:** phí đăng ký OA + phí theo lượng tin nhắn vượt quota (ước tính vài triệu–vài chục triệu VNĐ/tháng tuỳ volume, tham khảo bảng giá Zalo).
**Rủi ro:** trung bình-cao (đổi thói quen người dùng, phụ thuộc chính sách Zalo).
**Công sức:** trung bình (tích hợp webhook + OA setup, không cần code phức tạp nhưng cần thời gian phê duyệt tài khoản doanh nghiệp).
**Đáp ứng "điều xe realtime":** cao — NẾU chuyển được thói quen liên lạc sang OA. Nếu không, gần như vô dụng vì dữ liệu vẫn nằm trong group chat cũ.

### (b) Zalo Business / ZNS (Zalo Notification Service)

**Là gì:** ZNS là kênh gửi thông báo giao dịch một chiều (business → user đã có SĐT), thường dùng cho OTP, xác nhận đơn hàng, nhắc lịch — không phải kênh chat 2 chiều.

**Làm được gì:** gửi thông báo chủ động có định dạng chuẩn (mẫu đã duyệt) tới tài xế/khách hàng — ví dụ "Container X đã tới cảng, vui lòng xác nhận". Không nhận được phản hồi có cấu trúc, không đọc được ảnh/tin nhắn đến.

**Giới hạn:** một chiều, không giải quyết được nhu cầu chính là **đọc dữ liệu điều xe/hải quan từ Zalo vào hệ thống** — chỉ hữu ích cho việc đẩy thông báo ra ngoài, không phải ingest.

**Chi phí:** theo số tin nhắn ZNS gửi đi (rẻ hơn OA nhắn tự do, nhưng vẫn trả phí, và cần duyệt mẫu tin trước).
**Rủi ro:** thấp (không đụng tới group chat), nhưng giá trị thấp vì không giải quyết bài toán ingest.
**Công sức:** thấp-trung bình.
**Đáp ứng "điều xe realtime":** thấp — chỉ là kênh thông báo, không phải kênh thu thập dữ liệu.

### (c) Giữ nguyên paste tay + mở rộng upload ảnh (đã làm ở GĐ1 & GĐ5)

**Là gì:** đúng như hiện tại — nhân viên/điều phối viên copy nội dung Zalo (text hoặc ảnh chụp màn hình/ảnh hiện trường) và paste/upload thủ công vào Agentify qua `ZaloIngestCard` + field-image OCR (GĐ5).

**Làm được gì:** giữ nguyên toàn bộ workflow group chat hiện tại của người dùng — không cần đổi thói quen liên lạc, không phụ thuộc API không ổn định của Zalo. Có thể cải thiện thêm: paste nhanh hơn (extension trình duyệt/keyboard shortcut), OCR ảnh tốt hơn (đã có ở GĐ5), hoặc thêm hàng loạt paste (nhiều tin nhắn một lúc).

**Giới hạn:** vẫn cần một người thực hiện thao tác copy/paste hoặc chụp ảnh — không có "webhook tự động" thật sự. Có độ trễ vài phút–vài chục phút tuỳ khi nhân viên rảnh tay thao tác, không phải "realtime" theo nghĩa tức thời.

**Chi phí:** gần như bằng 0 — không có phí nền tảng, không có phí tích hợp mới.
**Rủi ro:** thấp nhất trong 4 lựa chọn — không phụ thuộc thay đổi chính sách của Zalo, không rủi ro pháp lý (không truy cập trái phép API cá nhân).
**Công sức:** thấp (mở rộng nhỏ, ví dụ paste hàng loạt) hoặc bằng 0 (giữ nguyên).
**Đáp ứng "điều xe realtime":** trung bình — đủ nhanh cho phần lớn nghiệp vụ hiện tại (free time tính theo ngày, không theo giây), nhưng không phải tự động 100%.

### (d) Không làm gì thêm (giữ nguyên scope hiện tại)

**Là gì:** dừng đầu tư vào Zalo, tập trung nguồn lực vào các nghiệp vụ khác (Kanban, đối soát, audit — đã xong GĐ1-8) và để paste tay là điểm dừng.

**Chi phí:** 0. **Rủi ro:** 0 (không thay đổi gì). **Công sức:** 0.
**Đáp ứng "điều xe realtime":** không cải thiện so với hiện tại, nhưng hiện tại đã đủ dùng cho MVP.

## 3. Bảng so sánh nhanh

| Con đường | Chi phí | Rủi ro pháp lý/kỹ thuật | Công sức | Đáp ứng điều xe realtime |
|---|---|---|---|---|
| (a) Zalo OA API | Trung bình-cao (phí quota) | Trung bình-cao (đổi thói quen, phụ thuộc chính sách) | Trung bình | Cao — nếu đổi được thói quen |
| (b) Zalo Business/ZNS | Thấp-trung bình | Thấp | Thấp-trung bình | Thấp (chỉ 1 chiều) |
| (c) Paste tay + mở rộng ảnh | ~0 | Thấp nhất | Thấp | Trung bình — đủ dùng |
| (d) Không làm | 0 | 0 | 0 | Không đổi |

## 4. Khuyến nghị

**Chọn (c): giữ paste tay + mở rộng upload ảnh, KHÔNG đầu tư Zalo OA/ZNS ở giai đoạn này.**

Lý do:
1. **USP thật của Zalo (group chat cá nhân) không có API chính thức** — Zalo OA chỉ đọc được chat 1-1 với chính OA đó, không phải group hiện tại nơi nghiệp vụ đang diễn ra. Muốn dùng OA phải bắt toàn bộ tài xế/đại lý đổi kênh liên lạc — chi phí đổi thói quen (adoption cost) cao hơn chi phí kỹ thuật, và không chắc thành công vì ngoài tầm kiểm soát của Agentify.
2. **Paste tay + OCR ảnh (đã code ở GĐ1, GĐ5) đã giải quyết phần lớn giá trị**: dữ liệu vào được hệ thống, giữ provenance, không bịa dữ liệu — đúng nguyên tắc cốt lõi của dự án. Độ trễ vài phút là chấp nhận được cho nghiệp vụ tính theo ngày (free time, phân luồng hải quan), không phải giao dịch tài chính cần tức thời.
3. **Rủi ro thấp nhất, chi phí thấp nhất** — phù hợp giai đoạn hiện tại (prototype/early sản phẩm) khi chưa có volume đủ lớn để biện minh cho chi phí OA + rủi ro phụ thuộc chính sách một nền tảng đóng.

**Khi nào nên xem lại quyết định này:** nếu volume tin nhắn Zalo tăng đến mức thao tác paste tay trở thành nút thắt cổ chai thực sự (đo bằng: nhân viên báo mất >X giờ/ngày để paste), hoặc nếu khách hàng lớn yêu cầu tích hợp Zalo OA như điều kiện hợp đồng — khi đó nên thử nghiệm (a) ở quy mô nhỏ (1 nhóm khách hàng/tuyến) trước khi mở rộng toàn bộ, không đổi luồng chính ngay lập tức.

**Quyết định cuối do anh Đạt/leader chốt** — tài liệu này chỉ dừng ở mức khuyến nghị, không có code tích hợp Zalo nào được viết ở GĐ8.
