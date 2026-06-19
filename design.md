# Agentify Prototype v0.1 — UI/UX Design Specification

## 1. Mục đích tài liệu

Tài liệu này mô tả hướng thiết kế giao diện mới cho prototype **Agentify Shipment Data Hub v0.1**. Tài liệu được dùng làm đầu vào cho Antigravity hoặc một công cụ tạo giao diện khác.

Giao diện phải giúp người dùng thực hiện nhanh ba việc:

1. Kết nối Gmail ở chế độ chỉ đọc và đồng bộ dữ liệu.
2. Tìm container từ dữ liệu email và PDF đã xử lý.
3. Kiểm tra thông tin container cùng email, attachment và nguồn trích xuất liên quan.

Đây là prototype kiểm chứng luồng dữ liệu Gmail → email/PDF → extraction → container profile. Thiết kế không được khiến người xem hiểu nhầm rằng sản phẩm đã là một TMS, shared inbox hoặc nền tảng AI logistics hoàn chỉnh.

---

## 2. Phạm vi sản phẩm cần phản ánh

### 2.1. Có trong prototype

- Kết nối Gmail bằng OAuth với quyền `gmail.readonly`.
- Hiển thị mailbox đã kết nối.
- Tạo một lần đồng bộ thủ công theo Gmail query và giới hạn số email.
- Hiển thị trạng thái và lịch sử sync.
- Lưu và hiển thị email đã sync.
- Hiển thị PDF attachment và trạng thái đọc text.
- Chỉ xử lý PDF có text layer.
- Trích xuất các field logistics.
- Gom dữ liệu theo `container_no`.
- Danh sách container.
- Chi tiết container.
- Truy vết field về email hoặc attachment nguồn.
- Hiển thị lỗi parse/extract để người dùng hoặc developer kiểm tra.

### 2.2. Không có trong prototype

Không thiết kế các tính năng sau như thể chúng đã hoạt động:

- OCR cho ảnh hoặc scanned PDF.
- Chat hoặc Q&A bằng ngôn ngữ tự nhiên.
- Embedding và semantic search.
- Gửi, trả lời hoặc chỉnh sửa email.
- Shared inbox hoặc phân công email.
- Bình luận nội bộ.
- Workflow approval.
- Zalo ingestion.
- Excel hoặc Google Sheets import.
- Alert nghiệp vụ tự động.
- Timeline shipment thông minh.
- TMS, WMS, ERP hoặc customs workflow.
- Review queue cho matching AI phức tạp.

Nếu cần nhắc đến tính năng ngoài phạm vi, chỉ được ghi là định hướng tương lai; không đặt CTA hoặc control giả.

---

## 3. Nguồn cảm hứng

### Front — nguồn tham khảo chính

Tham khảo:

- App shell có sidebar cố định.
- Cách tổ chức list-detail để người dùng không phải chuyển trang liên tục.
- Mật độ thông tin phù hợp công việc vận hành.
- Thanh công cụ gọn, phân cấp rõ.
- Danh sách hội thoại/email dạng row thay vì card lớn.
- Inspector panel cho metadata và thông tin liên quan.

Không sao chép:

- Shared inbox.
- Assignment.
- Team comments.
- Ticketing.
- SLA và automation.

### ChatGPT

Tham khảo:

- App shell tối giản.
- Navigation ít nhiễu.
- Search hoặc hành động chính luôn dễ nhìn thấy.
- Empty state bình tĩnh, có một bước tiếp theo rõ ràng.

Không thiết kế Agentify thành chatbot trong v0.1.

### Shortwave và Superhuman Mail

Tham khảo:

- Danh sách email compact.
- Subject là nội dung nổi bật nhất.
- Sender, snippet, timestamp và attachment là metadata thứ cấp.
- Email reader tập trung vào nội dung.
- Điều hướng nhanh giữa danh sách và email detail.

### Google Workspace

Tham khảo:

- Cách diễn đạt OAuth rõ ràng.
- Hiển thị account identity.
- Giải thích phạm vi quyền.
- Trạng thái kết nối và lỗi quyền truy cập.

---

## 4. Design read

Thiết kế này là một **B2B operations workspace** cho CS/Ops logistics, có ngôn ngữ thị giác điềm tĩnh, chính xác và thiên về dữ liệu, lấy Front làm nền tảng bố cục.

Các thông số định hướng:

- Design variance: `4/10`
- Motion intensity: `2/10`
- Visual density: `7/10`

Giao diện cần tạo cảm giác:

- Tin cậy.
- Nhanh.
- Có cấu trúc.
- Dữ liệu có thể kiểm chứng.
- Đang làm việc trong một ứng dụng, không phải xem landing page.

Giao diện không được tạo cảm giác:

- AI màu tím.
- Dashboard template.
- Website marketing.
- Nhiều card trang trí nhưng ít dữ liệu.
- Enterprise software quá nặng.

---

## 5. Nguyên tắc UX

### 5.1. Search và dữ liệu là trung tâm

Người dùng mở Agentify để tìm một mã logistics hoặc kiểm tra dữ liệu đã sync. Tiêu đề marketing và đoạn mô tả dài không được chiếm phần lớn viewport.

### 5.2. Progressive disclosure

Thông tin được chia theo ba lớp:

1. List row để quét nhanh.
2. Detail panel để xem dữ liệu quan trọng.
3. Source inspector hoặc source detail để kiểm chứng.

### 5.3. Provenance luôn nhìn thấy

Mỗi fact logistics phải có đường dẫn hoặc control dẫn đến nguồn:

- Email nào.
- Attachment nào.
- Thời gian email.
- Field được trích xuất từ đâu.

Không đặt source ở một tab khó tìm.

### 5.4. Không suy đoán

Khi dữ liệu chưa tồn tại, hiển thị:

> Not found in Agentify data

Hoặc bản dịch phù hợp:

> Chưa tìm thấy trong dữ liệu Agentify

Không dùng các giá trị giả để lấp khoảng trống.

### 5.5. Trạng thái hệ thống phải cụ thể

Tránh các nhãn mơ hồ như:

- Chưa rõ trạng thái.
- Có vấn đề.
- Đang xử lý dữ liệu.

Ưu tiên:

- Chưa kết nối Gmail.
- Đang chờ đồng bộ.
- Đang tải email 24/100.
- Đã đồng bộ 86 email.
- 3 PDF không có text layer.
- Đồng bộ thất bại do Google OAuth hết hiệu lực.

### 5.6. Một hành động chính trên mỗi màn hình

- Overview: tìm dữ liệu.
- Data sources: kết nối Gmail hoặc sync.
- Containers: chọn một container.
- Emails: chọn một email.
- Email detail: kiểm tra email và nguồn trích xuất.

---

## 6. Information architecture

### 6.1. Navigation chính

Sidebar desktop:

1. **Overview**
2. **Containers**
3. **Emails**
4. **Data source**

Không tạo thêm navigation cho các module chưa có trong prototype.

`Sync history` nằm bên trong `Data source`, không cần một module cấp cao riêng trong v0.1.

### 6.2. Route mapping đề xuất

| Navigation | Route hiện tại hoặc đề xuất | Mục đích |
|---|---|---|
| Overview | `/` | Search nhanh và trạng thái dữ liệu |
| Containers | `/containers` | Danh sách và chi tiết container |
| Container detail | `/containers/:containerNo` | Deep link đến container |
| Emails | `/emails` | Danh sách email đã sync |
| Email detail | `/emails/:id` | Đọc email, attachment và extracted facts |
| Data source | `/setup` | Gmail connection, sync form và sync jobs |

Nếu backend/frontend hiện chưa có route `/emails`, Antigravity vẫn nên thiết kế màn hình này vì API và email detail đã nằm trong phạm vi prototype. Không thêm logic backend mới vào bản thiết kế.

### 6.3. Sidebar footer

Hiển thị:

- Mailbox đang kết nối hoặc `Gmail chưa kết nối`.
- Chấm trạng thái backend nếu endpoint health có dữ liệu.
- Workspace name nếu đã có.

Không cần user management phức tạp.

---

## 7. App shell

### 7.1. Desktop

```text
┌──────────────────┬──────────────────────────────────────────────────────┐
│                  │ Top toolbar                                          │
│ Sidebar          ├───────────────────────┬──────────────────────────────┤
│                  │ Primary workspace     │ Detail / inspector           │
│                  │                       │                              │
│                  │                       │                              │
│                  │                       │                              │
│ Mailbox status   │                       │                              │
└──────────────────┴───────────────────────┴──────────────────────────────┘
```

- Sidebar: `240px`.
- Sidebar có thể collapse về icon rail ở viewport trung bình.
- Toolbar: `56px`.
- Nội dung chiếm toàn bộ chiều rộng còn lại.
- Không bọc toàn ứng dụng trong `max-width: 1280px`.
- Page background và panel background khác nhau rất nhẹ.
- Dùng divider 1px để phân vùng; hạn chế shadow.

### 7.2. Tablet

- Sidebar collapse thành icon rail khoảng `64px`.
- List-detail có thể giữ hai cột.
- Inspector phụ mở bằng drawer nếu không đủ chiều rộng.

### 7.3. Mobile

- Navigation mở bằng drawer.
- Chỉ hiển thị một cấp màn hình mỗi lần.
- List → detail là navigation thông thường.
- Toolbar sticky.
- Không cố ép layout ba cột xuống màn hình nhỏ.

---

## 8. Global toolbar

Toolbar nằm trên vùng nội dung, không nằm trong sidebar.

Thành phần:

- Breadcrumb hoặc page title ngắn ở trái.
- Global search trigger ở giữa hoặc gần trái.
- Nút `Sync now` ở phải khi Gmail đã kết nối.
- Mailbox avatar hoặc Gmail identity.

Global search trigger:

- Placeholder: `Search container, booking, B/L or PO`
- Có keyboard hint `/` hoặc `⌘K`.
- Khi mở, cho phép search các mã mà backend hiện hỗ trợ.
- Không hiển thị câu hỏi gợi ý như chatbot.

Nếu global search chưa thể triển khai ngay, Overview vẫn có ô search chính; toolbar chỉ hiển thị page title.

---

## 9. Screen specification

## 9.1. Overview

### Mục tiêu

Cho người dùng biết hệ thống đã sẵn sàng chưa và bắt đầu tra cứu trong vài giây.

### Layout

Không dùng hero marketing lớn. Nội dung đầu viewport:

1. Page heading nhỏ: `Overview`.
2. Search box nổi bật.
3. Một status strip.
4. Hai danh sách ngắn: containers gần đây và email mới sync.

### Search block

- Chiều rộng tối đa khoảng `760px`.
- Input cao `52–56px`.
- Icon search bên trái.
- Nút search hoặc Enter để submit.
- Helper text ngắn: `Container, booking, B/L or PO`.
- Không bọc input trong một card lớn có nền beige.

### Status strip

Một hàng thống nhất, dùng divider thay vì bốn metric card:

- Gmail: connected/not connected.
- Last sync.
- Emails synced.
- Containers found.
- PDF extraction warning nếu có.

Khi Gmail chưa kết nối:

- Hiển thị một banner rõ ràng.
- Primary CTA: `Connect Gmail`.
- Nêu `Read-only access`.

### Recent containers

Hiển thị tối đa 5 row:

- Container number.
- Booking hoặc B/L.
- ETA nếu có.
- Latest status text.
- Updated time.

### Recent emails

Hiển thị tối đa 5 row:

- Sender.
- Subject.
- Sent time.
- PDF indicator.
- Processing status.

Không dựng các widget analytics vì prototype chưa có nhu cầu quản trị.

---

## 9.2. Containers

### Mục tiêu

Quét danh sách container và mở hồ sơ mà không mất ngữ cảnh.

### Desktop layout

```text
┌────────────────────────────────┬───────────────────────────────────────┐
│ Container list                 │ Container detail                      │
│ Search                         │ Header + facts                        │
│ Filters                        │ Related emails                        │
│ Rows                           │ Source references                     │
└────────────────────────────────┴───────────────────────────────────────┘
```

- List pane: `380–430px`.
- Detail pane: phần còn lại.
- Có resizable divider nếu thuận tiện; không bắt buộc cho prototype.

### List header

- Title: `Containers`.
- Total count.
- Search input.
- Filter đơn giản, chỉ dùng khi có dữ liệu đáng tin cậy.

Prototype ưu tiên filter:

- All.
- Complete enough.
- Missing data.

Không tạo filter nghiệp vụ như customs/trucking nếu backend chỉ suy ra bằng heuristic không chắc chắn.

### Container row

Mỗi row cao khoảng `84–104px`, gồm:

- `container_no` bằng mono font.
- Status text tối đa hai dòng.
- Booking hoặc B/L.
- ETA hoặc last updated time.
- Badge `Missing data` khi thiếu các field quan trọng.

Selected row dùng nền accent rất nhạt và indicator 2px bên trái.

Không dùng mỗi container như một card bo tròn độc lập.

### Empty state

Nếu chưa có container:

- Heading: `No containers found`.
- Nội dung: container chỉ xuất hiện khi email/PDF có `container_no` được extract.
- CTA: `Go to data source`.

### Loading

Dùng 6–8 skeleton rows có cấu trúc giống row thật.

---

## 9.3. Container detail

### Header

Hiển thị:

- Container number.
- Latest status text.
- Last seen timestamp.
- Source count nếu tính được.

Primary action không cần thiết. Có thể có `Copy container number`.

### Summary facts

Sử dụng grid thông tin phẳng, không dùng một card cho từng field.

Nhóm 1 — Identifiers:

- Booking.
- B/L.
- PO.
- Seal.

Nhóm 2 — Route:

- POL.
- POD.
- Vessel.
- Voyage.

Nhóm 3 — Schedule:

- ETD.
- ETA.

Mỗi field gồm:

- Label.
- Latest value.
- Source link.
- Missing state.

Source link có thể ghi:

- `Email · 12 Jun 2026`
- `PDF · booking_confirmation.pdf`

### Related emails

Danh sách email compact:

- Subject.
- Sender.
- Sent time.
- Attachment count.
- Số extracted facts.

Click mở email detail.

### Fact history

Hiển thị dưới dạng bảng hoặc grouped list:

- Field.
- Value.
- Source.
- Source sent time.

Nếu nhiều nguồn có cùng field, latest value được nhấn mạnh nhẹ; lịch sử cũ vẫn còn.

Không tuyên bố conflict resolution nếu backend chưa hỗ trợ đầy đủ.

---

## 9.4. Emails

### Mục tiêu

Cho người dùng và developer kiểm tra email nào đã vào hệ thống, đã xử lý đến đâu và có liên kết với container nào.

### Desktop layout

```text
┌────────────────────────────────┬───────────────────────────────────────┐
│ Email list                     │ Email detail preview                  │
│ Search + filters               │ Content / attachment / facts          │
└────────────────────────────────┴───────────────────────────────────────┘
```

- List pane: `400–460px`.
- Detail pane: phần còn lại.

### Email filters

Chỉ dùng các filter có dữ liệu hiện tại:

- All.
- Has PDF.
- Linked to container.
- Processing failed.

Có thể bổ sung date filter đơn giản nếu API hỗ trợ.

### Email row

- Sender name/email.
- Subject đậm vừa.
- Snippet một dòng.
- Sent time.
- Paperclip/PDF indicator.
- Processing badge.
- Container number nếu đã liên kết.

Badge trạng thái:

- Synced.
- Parsed.
- Extracted.
- No container found.
- Unsupported PDF.
- Failed.

Tên badge phải map đúng trạng thái backend, không tự tạo trạng thái không tồn tại.

### Empty state

- `No synced emails yet`.
- Giải thích rằng email xuất hiện sau khi Gmail được kết nối và sync hoàn tất.
- CTA: `Connect Gmail` hoặc `Run sync`.

---

## 9.5. Email detail

### Mục tiêu

Kiểm chứng email gốc, PDF và các fact được extract.

### Layout desktop

```text
┌────────────────────────────────────────────┬───────────────────────────┐
│ Email reader                              │ Source inspector           │
│ Header                                    │ Linked containers          │
│ Body                                      │ Extracted facts            │
│ Attachment viewer                         │ Processing status/errors   │
└────────────────────────────────────────────┴───────────────────────────┘
```

- Reader chiếm khoảng `65–70%`.
- Inspector chiếm `30–35%`.
- Inspector có thể sticky trong viewport.

### Email header

- Subject là heading chính.
- From.
- To và CC trong disclosure.
- Sent time.
- Gmail message/thread ID chỉ nằm trong phần technical details.

### Email body

- Ưu tiên plain text hoặc HTML đã sanitize.
- Chiều rộng đọc khoảng `70–80ch`.
- Không đặt body trong nhiều lớp card.

### Attachment section

- Tabs hoặc list attachment ở trên viewer.
- Filename.
- File type và size.
- Text extraction status.
- PDF preview nếu endpoint file hoạt động.
- Extracted text có thể ở tab riêng.

Nếu PDF không có text layer:

- Hiển thị trạng thái `Unsupported in prototype`.
- Giải thích: `This prototype only processes text-based PDFs.`
- Không hiển thị CTA OCR.

### Source inspector

Nhóm:

1. Linked containers.
2. Extracted facts.
3. Processing details.
4. Errors.

Fact item:

- Field label.
- Extracted value.
- Source: body hoặc attachment.

Click một fact nên highlight attachment hoặc khu vực nguồn khi khả thi. Nếu chưa thể triển khai, source link vẫn phải mở đúng attachment.

---

## 9.6. Data source

### Mục tiêu

Kết nối Gmail, cấu hình phạm vi sync và kiểm tra các sync job.

Đây là màn quản trị dữ liệu, không phải dashboard tổng quan.

### Trạng thái chưa kết nối

Hiển thị một connection panel duy nhất:

- Gmail logo.
- Heading: `Connect Gmail`.
- Mô tả một câu.
- Quyền: `Read email and attachments only`.
- Nêu rõ Agentify không gửi, sửa hoặc xóa email.
- Primary CTA: `Continue with Google`.

Không hiển thị metric cards rỗng trước khi kết nối.

### Trạng thái đã kết nối

Connection row:

- Gmail avatar hoặc initial.
- Gmail address.
- Status: Connected.
- Scope: Read-only.
- Last successful sync.
- Action: `Sync now`.
- Secondary menu: reconnect/configure nếu backend hỗ trợ.

### Sync configuration

Form gọn:

- Mailbox.
- Gmail query.
- Maximum emails.
- Submit: `Start sync`.

Label phải nằm trên input.

Gmail query có:

- Giá trị mặc định hiện tại, ví dụ `newer_than:30d`.
- Helper text ngắn.
- Không tạo visual query builder trong prototype.

### Active sync

Hiển thị progress panel:

- Job status.
- Started at.
- Processed/total nếu backend cung cấp.
- Current phase nếu backend cung cấp.
- Không giả lập phần trăm khi API không có dữ liệu.

### Sync history

Table/list gồm:

- Started time.
- Gmail query.
- Status.
- Emails fetched.
- Containers found nếu có.
- Error summary.

Click job mở phần detail ngay bên dưới hoặc drawer.

### Synced email preview

Hiển thị tối đa 5 email gần nhất và link `View all emails`.

Không nhét toàn bộ email list vào cuối một trang setup dài.

---

## 10. Component inventory

Antigravity nên xây các component có mục đích rõ:

### Layout

- `AppShell`
- `PrimarySidebar`
- `TopToolbar`
- `SplitView`
- `InspectorPanel`
- `MobileNavigationDrawer`

### Search and navigation

- `GlobalSearch`
- `PageSearch`
- `Breadcrumb`
- `FilterChips`

### Data rows

- `ContainerRow`
- `EmailRow`
- `SyncJobRow`
- `SourceReference`
- `FactRow`

### Status

- `StatusBadge`
- `ConnectionStatus`
- `ProcessingStatus`
- `InlineError`
- `WarningBanner`
- `EmptyState`
- `SkeletonRows`

### Gmail

- `GmailConnectionPanel`
- `SyncConfigurationForm`
- `ActiveSyncProgress`
- `SyncHistoryList`

### Detail

- `ContainerHeader`
- `FactGroup`
- `RelatedEmailList`
- `EmailReader`
- `AttachmentTabs`
- `AttachmentViewer`
- `SourceInspector`

Không xây một component `Card` chung rồi bọc mọi nội dung vào card.

---

## 11. Visual design system

## 11.1. Color

Sử dụng cool-neutral palette.

```css
--bg-app: #f5f6f8;
--bg-sidebar: #f0f2f5;
--bg-panel: #ffffff;
--bg-hover: #f4f6f9;
--bg-selected: #edf3ff;

--text-primary: #18202b;
--text-secondary: #556274;
--text-muted: #7b8797;

--border-subtle: #e1e5ea;
--border-strong: #cfd5dd;

--accent: #315fce;
--accent-hover: #284fae;
--accent-soft: #edf3ff;

--success: #247a52;
--warning: #9a6700;
--danger: #b33a3a;
--info: #315fce;
```

Nguyên tắc:

- Chỉ một accent chính.
- Màu semantic chỉ dùng cho trạng thái.
- Không dùng beige/cream.
- Không dùng purple gradient.
- Không dùng nền nhiều màu cho từng card.

## 11.2. Typography

Đề xuất:

- UI font: `Geist`.
- Technical identifiers: `Geist Mono`.

Fallback:

```css
font-family: Geist, "Segoe UI", sans-serif;
```

Quy tắc:

- Page title: 22–26px, semibold.
- Section title: 15–18px, semibold.
- Body: 14px.
- Metadata: 12–13px.
- Container/booking/B/L: mono, 13–15px.
- Không dùng heading 48–60px trong app.
- Không dùng uppercase eyebrow trên mọi section.

## 11.3. Spacing

Base spacing: `4px`.

Mức chính:

- `4px`
- `8px`
- `12px`
- `16px`
- `20px`
- `24px`
- `32px`

List row dùng padding dọc `12–16px`.

## 11.4. Radius

- Button/input: `8px`.
- Panel/dialog: `10–12px`.
- Badge/chip: full pill.
- List row: `0–8px`, tùy selected treatment.

Không dùng radius 24–28px trên mọi container.

## 11.5. Shadow

- App shell và panel chủ yếu dùng border.
- Dropdown/dialog có shadow nhỏ.
- Không dùng shadow blur 60–80px.

## 11.6. Icons

- Dùng một icon family duy nhất.
- Nếu giữ dependency hiện tại, dùng Lucide nhất quán.
- Icon mặc định 16–18px.
- Không dùng icon chỉ để trang trí bên cạnh mọi label.

---

## 12. Interaction and motion

Motion phải hỗ trợ định hướng, không dùng để trình diễn.

- Hover transition: `120–160ms`.
- Panel opening: `160–220ms`.
- Selected row chuyển nền nhẹ.
- Button active có thể scale `0.98`.
- Không dùng parallax.
- Không dùng entrance animation cho toàn bộ dashboard.
- Tôn trọng `prefers-reduced-motion`.

Keyboard behavior:

- `/` hoặc `⌘K`: focus global search nếu triển khai.
- `Escape`: đóng dialog/drawer.
- Arrow key navigation trong list là tùy chọn, không bắt buộc cho v0.1.

---

## 13. Loading, empty and error states

Mỗi màn hình phải có đủ bốn trạng thái:

1. Loading.
2. Empty.
3. Success.
4. Error.

### Loading

- Skeleton có cùng cấu trúc dữ liệu thật.
- Không chỉ hiển thị chữ `Loading...`.

### Empty

Empty state phải giải thích nguyên nhân và đưa ra bước tiếp theo.

Ví dụ:

- Chưa kết nối Gmail → `Connect Gmail`.
- Đã kết nối nhưng chưa sync → `Start first sync`.
- Sync xong nhưng không có container → giải thích email chưa có container number được extract.
- Không có kết quả search → đề nghị kiểm tra chính tả hoặc tìm bằng booking/B/L/PO.

### Error

Lỗi phải nằm gần phần bị lỗi:

- OAuth error trong connection panel.
- Sync error trong active job/history.
- Email load error trong email pane.
- Attachment parse error cạnh attachment.

Toast chỉ dùng cho feedback ngắn như copy thành công.

---

## 14. Accessibility

- Contrast đạt WCAG AA.
- Focus ring rõ ràng.
- Mọi icon button có accessible label.
- Không dùng màu làm tín hiệu trạng thái duy nhất.
- List row có trạng thái selected cho screen reader.
- Sidebar và toolbar dùng semantic navigation.
- Input luôn có label, không dùng placeholder thay label.
- Click target tối thiểu khoảng `40px`.
- Email HTML phải được sanitize trước khi render.

---

## 15. Content guidelines

### Ngôn ngữ

Giao diện có thể dùng tiếng Việt, nhưng thuật ngữ logistics phổ biến được giữ nguyên:

- Container.
- Booking.
- B/L.
- PO.
- ETD.
- ETA.
- PDF.
- Gmail.
- Sync.

### Voice

- Ngắn.
- Trực tiếp.
- Không quảng cáo.
- Không nhân cách hóa AI.
- Không nói hệ thống “hiểu” dữ liệu nếu chỉ dùng extraction.

### Ví dụ microcopy

Tốt:

- `Connect Gmail`
- `Read-only access`
- `Start sync`
- `86 emails synced`
- `No container number found`
- `PDF has no text layer`
- `View source email`
- `Chưa tìm thấy trong dữ liệu Agentify`

Không tốt:

- `Let Agentify work its magic`
- `AI đã hiểu email của bạn`
- `Smart logistics intelligence`
- `Everything looks great!`

---

## 16. Prototype-specific constraints for Antigravity

Antigravity phải tuân thủ:

1. Giữ nguyên các luồng API đang có; đây là redesign frontend, không phải thiết kế lại backend.
2. Không tạo fake feature hoặc fake data để che trạng thái rỗng.
3. Có thể dùng realistic demo data trong mockup, nhưng phải khớp schema hiện tại.
4. Mỗi field logistics phải support trạng thái null.
5. Một email có thể liên kết nhiều container.
6. Một container có thể có nhiều email, attachment và fact.
7. PDF scan phải hiển thị unsupported, không giả vờ đã OCR.
8. Sync có thể fail hoặc partial.
9. LLM có thể bị tắt; UI không phụ thuộc vào AI summary.
10. Search chính vẫn là tìm mã logistics, không phải chat.

---

## 17. Data examples for mockups

Antigravity có thể dùng dữ liệu mẫu:

### Container

```json
{
  "container_no": "MSCU1234567",
  "booking_no": "BK-SGN-240612",
  "bl_no": "MAEU987654321",
  "po_no": "PO-450012345",
  "vessel": "MAERSK HANOI",
  "voyage": "426W",
  "pol": "Ho Chi Minh City",
  "pod": "Los Angeles",
  "etd": "2026-06-12T08:00:00Z",
  "eta": "2026-07-02T09:00:00Z",
  "status_text": "Booking confirmed"
}
```

### Email

```json
{
  "from_email": "operations@carrier-example.com",
  "subject": "Booking Confirmation BK-SGN-240612",
  "sent_at": "2026-06-10T09:30:00Z",
  "snippet": "Please find attached the booking confirmation...",
  "has_pdf_attachments": true,
  "processing_status": "processed"
}
```

### Attachment

```json
{
  "filename": "booking_confirmation_BK-SGN-240612.pdf",
  "mime_type": "application/pdf",
  "extraction_status": "completed"
}
```

Không dùng bản đồ, GPS live tracking, customs status hoặc POD image trong mockup v0.1 nếu dữ liệu đó chưa có trong implementation.

---

## 18. Acceptance criteria cho thiết kế

Thiết kế được xem là phù hợp khi:

1. Người dùng nhận ra ngay đây là một ứng dụng làm việc, không phải landing page.
2. Kết nối Gmail là luồng rõ ràng, có giải thích read-only.
3. Sync status và sync errors dễ tìm.
4. Email đã sync có một màn hình danh sách riêng.
5. Container list có mật độ đủ cao để quét nhanh.
6. Container detail luôn hiển thị source cho dữ liệu đã extract.
7. Email detail cho phép kiểm tra body, attachment và facts trong cùng ngữ cảnh.
8. Không có tính năng ngoài phạm vi prototype được trình bày như đã hoạt động.
9. Loading, empty và error state được thiết kế đầy đủ.
10. Giao diện desktop phù hợp với người dùng CS/Ops làm việc nhiều giờ.
11. Mobile có fallback rõ nhưng desktop là ưu tiên chính.
12. Visual system nhất quán, không dùng hàng loạt card bo tròn lớn.

---

## 19. Deliverables mong muốn từ Antigravity

Antigravity nên tạo:

1. App shell responsive.
2. Sidebar và global toolbar.
3. Overview.
4. Containers list-detail.
5. Container detail.
6. Emails list-detail.
7. Email detail và source inspector.
8. Data source/Gmail connection.
9. Sync form và sync history.
10. Loading, empty, success và error states cho từng màn hình.
11. Design tokens dưới dạng CSS variables.
12. Reusable components theo component inventory.

Ưu tiên desktop ở `1440px`, sau đó kiểm tra:

- `1280px`
- `1024px`
- `768px`
- `390px`

---

## 20. Tóm tắt định hướng

Agentify v0.1 nên trông giống một **operations inbox dành cho dữ liệu shipment/container**, không phải một dashboard AI chung chung.

Front cung cấp cấu trúc app shell và list-detail. Shortwave/Superhuman cung cấp cách đọc email. ChatGPT cung cấp sự tối giản và cách đặt search làm hành động chính. Tuy nhiên, mọi màn hình và control phải phục vụ đúng prototype hiện tại:

> Connect Gmail read-only → sync email/PDF → extract logistics fields → search container → inspect source.
