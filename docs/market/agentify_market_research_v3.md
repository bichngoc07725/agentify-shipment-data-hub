# Agentify — Market Research V3

**Mục tiêu tài liệu:** chứng minh product-market fit của Agentify bằng cách chỉ ra *chính xác* nhóm khách hàng nào có pain cao nhất **mà sản phẩm hiện tại đọc được dữ liệu của họ**, thay vì liệt kê mọi nhóm có pain.

**Điểm khác biệt so với V2:**

| Vấn đề của V2 | Cách V3 xử lý |
|---|---|
| Xếp hạng segment theo "mức độ pain" cảm tính | Thay bằng khung chấm điểm 6 tiêu chí, trong đó **data-fit** (dữ liệu gây pain có nằm trong email/file không) được nhân đôi trọng số |
| Hứa "Zalo Integration native", "Smart Reconciliation" như tính năng đã có | Tách rõ 3 trạng thái: **đang chạy được / trong roadmap / không nên hứa** |
| Trộn lẫn số liệu có nguồn và ước tính nội bộ | Mỗi con số gắn nhãn `[Nguồn]` hoặc `[Ước tính Agentify]` |
| SOM 1.500 DN trong 1–3 năm | Tách "pool có thể tiếp cận" (1.500 DN) khỏi "kế hoạch bán hàng thực tế" (150–250 DN năm 3) |
| Segment #2 là Logistics TMĐT xuyên biên giới | Bị đẩy xuống #6 vì dữ liệu pain của họ nằm trong API sàn/OMS, không nằm trong email |

---

## Mục lục

1. [Tóm tắt điều hành](#1-tóm-tắt-điều-hành)
2. [Agentify là gì — định vị chính xác](#2-agentify-là-gì--định-vị-chính-xác)
3. [Bối cảnh thị trường](#3-bối-cảnh-thị-trường)
4. [Khung chấm điểm Pain-Fit](#4-khung-chấm-điểm-pain-fit)
5. [Xếp hạng 10 nhóm khách hàng](#5-xếp-hạng-10-nhóm-khách-hàng)
6. [Beachhead: mổ xẻ nhóm pain cao nhất](#6-beachhead-mổ-xẻ-nhóm-pain-cao-nhất)
7. [Product-Market Fit: pain → tính năng → trạng thái build](#7-product-market-fit-pain--tính-năng--trạng-thái-build)
8. [Mô hình ROI định lượng](#8-mô-hình-roi-định-lượng)
9. [TAM / SAM / SOM](#9-tam--sam--som)
10. [Cạnh tranh và khoảng trống](#10-cạnh-tranh-và-khoảng-trống)
11. [Go-to-market và pricing](#11-go-to-market-và-pricing)
12. [Kế hoạch kiểm chứng PMF và tiêu chí bác bỏ](#12-kế-hoạch-kiểm-chứng-pmf-và-tiêu-chí-bác-bỏ)
13. [Lộ trình mở rộng](#13-lộ-trình-mở-rộng)
14. [Phụ lục](#14-phụ-lục)

---

## 1. Tóm tắt điều hành

### 1.1. Luận điểm một câu

> Trong logistics B2B/XNK Việt Nam, **dữ liệu vận hành thật không nằm trong phần mềm — nó nằm trong hộp thư và file đính kèm**. Agentify là lớp dữ liệu đọc chính những nguồn đó và biến chúng thành một hồ sơ shipment/container tra cứu được, có nguồn gốc.

### 1.2. Ba kết luận chính

**Kết luận 1 — Nhóm pain cao nhất không phải "toàn ngành logistics", mà là một lát cắt rất hẹp.**

Nhóm đạt điểm cao nhất (34/35) là:

> **Freight Forwarder / NVOCC vừa và nhỏ, thiên về hàng NHẬP đường biển (FCL/LCL), 20–100 nhân sự, 100–500 shipment/tháng, tại TP.HCM – Bình Dương – Đồng Nai và Hà Nội – Hải Phòng.**

Lý do nhóm này thắng không phải vì họ "đau nhất" — mà vì họ là nhóm duy nhất hội đủ **cả ba** điều kiện cùng lúc:

1. Pain xảy ra hằng ngày (CS trả lời hàng chục câu hỏi trạng thái/ngày).
2. Pain quy đổi thành **tiền mặt trực tiếp** (phí lưu container/lưu bãi — DEM/DET — tính theo ngày, theo container).
3. **Dữ liệu tạo ra pain nằm trong email + PDF đính kèm** — đúng thứ Agentify đọc được hôm nay, không cần tích hợp gì thêm.

**Kết luận 2 — Nhiều nhóm "pain rất cao" lại là bẫy đối với sản phẩm này.**

Nhà phân phối B2B, D2C bán lẻ đa kênh, trucking/điều xe đều có pain lớn và thị trường đông. Nhưng dữ liệu gây pain của họ nằm trong **Zalo, điện thoại, OMS và ảnh chụp** — không phải email. Bán cho họ hôm nay nghĩa là phải xây thêm một sản phẩm khác trước khi giao được giá trị. Đây là thay đổi lớn nhất so với bản V2.

**Kết luận 3 — Chỗ pain chuyển thành tiền nhanh nhất là "free time / DEM–DET", và đó nên là tính năng mũi nhọn.**

Tiết kiệm thời gian tra cứu là lợi ích *dễ nói* nhưng *khó ký hợp đồng*. Cảnh báo "container này còn 2 ngày free time mà chưa thấy D/O" là lợi ích *khó nói hơn* nhưng **có đơn vị tiền tệ**. Toàn bộ dữ liệu cần cho cảnh báo này (ETA/ATA, số ngày free time, D/O đã phát hành chưa) nằm trong Arrival Notice và email hãng tàu — Agentify đọc được.

### 1.3. Điều gì làm luận điểm này sai?

Tài liệu này chỉ có giá trị nếu nó có thể bị bác bỏ. Ba tín hiệu sẽ chứng minh luận điểm sai — xem chi tiết ở [mục 12.3](#123-tiêu-chí-bác-bỏ-kill-criteria):

- Nếu > 40% forwarder pilot dùng **hộp thư cá nhân** thay vì hộp thư dùng chung, Agentify không lấy được dữ liệu hợp pháp ở quy mô đội nhóm.
- Nếu tỷ lệ trích xuất đúng `container_no` trên email thật < 70%, hồ sơ shipment sẽ rỗng và sản phẩm mất niềm tin ngay tuần đầu.
- Nếu DEM/DET thực tế được hãng tàu tính cho **chủ hàng** chứ không phải forwarder ở đa số hợp đồng, thì người trả tiền và người chịu đau là hai bên khác nhau — phải đổi ICP sang chủ hàng.

---

## 2. Agentify là gì — định vị chính xác

### 2.1. Một câu mô tả

> **Agentify Shipment Data Hub** — kho dữ liệu vận hành cho shipment/container. Agentify tự đọc email và file đính kèm của team CS/Ops/Docs, trích xuất thông tin logistics, gom về **một hồ sơ duy nhất cho mỗi container**, và cảnh báo những lô đang có rủi ro phát sinh chi phí.

### 2.2. Agentify KHÔNG phải là gì

Đây là phần quan trọng nhất của định vị, vì nó quyết định Agentify không phải cạnh tranh với ai:

| Không phải | Vì sao quan trọng |
|---|---|
| TMS / WMS / ERP | Không đụng vào hệ thống lõi khách đã đầu tư → không có "rip and replace", chu kỳ bán ngắn |
| Phần mềm khai hải quan (ECUS/VNACCS) | Tránh rủi ro pháp lý; ECUS là bắt buộc và đã mạnh |
| Chatbot logistics chung chung | Không trả lời khi không có dữ liệu — nói rõ "chưa thấy trong Agentify" |
| Control tower enterprise | Không cần tích hợp EDI/API hãng tàu để có giá trị ngày đầu |

### 2.3. Ranh giới năng lực — thước đo để chấm điểm segment

Đây là bảng quyết định mọi thứ ở mục 4 và 5. Một pain chỉ được tính điểm cao nếu dữ liệu của nó nằm ở cột "Đọc được hôm nay".

| Nguồn dữ liệu | Trạng thái | Ghi chú |
|---|---|---|
| Email body (Gmail, read-only) | ✅ Đọc được hôm nay | Đã chạy trong prototype |
| PDF đính kèm có text layer | ✅ Đọc được hôm nay | Booking confirm, arrival notice, B/L, D/O, debit note, invoice |
| Ảnh chụp / PDF scan (POD, EIR, ảnh seal) | 🟡 Roadmap — cần OCR/vision | Rất nhiều bằng chứng vận hành nằm ở đây |
| Excel / Google Sheet tracking file | 🟡 Roadmap — import thủ công trước | File tracking là "source of truth" thực tế của nhiều DN |
| Zalo — forward/upload thủ công | 🟡 Roadmap — an toàn về consent | Người dùng chủ động đẩy tin quan trọng vào Agentify |
| Zalo — đọc tự động toàn bộ chat cá nhân | ❌ Không nên hứa | Rủi ro quyền riêng tư, consent và kỹ thuật |
| Zalo OA / API chính thức | 🟡 Roadmap — chỉ khi DN có kênh OA hợp lệ | |
| ECUS/VNACCS, ePort, API hãng tàu | ❌ Ngoài phạm vi giai đoạn này | |

> ⚠️ **Đính chính so với V2:** bản V2 liệt kê "Tích hợp Zalo: ✅ Native" trong bảng so sánh cạnh tranh. Đây là cam kết không nên đưa vào tài liệu gọi vốn hoặc bán hàng ở thời điểm hiện tại. V3 thay bằng "Zalo qua forward/upload có consent, Zalo OA khi doanh nghiệp có kênh chính thức".

---

## 3. Bối cảnh thị trường

### 3.1. Quy mô ngành

| Chỉ số | Giá trị | Loại |
|---|---|---|
| Quy mô thị trường logistics VN (2025) | 52 – 86 tỷ USD (tùy phạm vi thống kê) | `[Nguồn]` mordorintelligence.com, expertmarketresearch.com |
| Tốc độ tăng trưởng | 12 – 16%/năm | `[Nguồn]` logistics.gov.vn |
| CAGR dự báo đến 2030 | 6,4 – 6,7% | `[Nguồn]` mordorintelligence.com |
| Số DN logistics | 30.000 – 50.000 | `[Nguồn]` b-company.jp, marketreportsworld.com |
| DN thành lập mới (Q1–Q3/2025) | 9.343 DN (+27,7% YoY) | `[Nguồn]` b-company.jp |
| Đóng góp GDP | 4 – 5% | `[Nguồn]` logistics.gov.vn |
| Chi phí logistics/GDP (VN vs. thế giới) | 16 – 18% vs. 10 – 12% | `[Nguồn]` logistics.gov.vn |
| Tỷ lệ SME trong ngành | 88 – 95% | `[Nguồn]` tổng hợp b-company.jp |
| ~70% DN logistics tập trung tại TP.HCM | — | `[Nguồn]` tổng hợp |

### 3.2. Thực trạng công nghệ — đây mới là thị trường thật của Agentify

| Thực trạng | Số liệu | Loại |
|---|---|---|
| DN vẫn dùng Excel/Google Sheets hằng ngày | 97,8% | `[Nguồn]` udn.vn |
| DN có phần mềm quản lý kho (WMS) | ~30% | `[Nguồn]` researchgate.net |
| DN đã triển khai AI ở quy mô sản xuất | ~13,8% | `[Nguồn]` b-company.jp |
| DN ứng dụng công nghệ ở mức cơ bản | 50 – 60% | `[Nguồn]` vngcloud.vn |
| Zalo MAU | 79,6 triệu | `[Nguồn]` vietnam.vn, vietnamnet.vn |

**Diễn giải:** con số 97,8% dùng Excel không phải là "DN chưa số hóa". Nó có nghĩa là **DN đã mua phần mềm rồi vẫn phải dùng Excel song song** — vì phần mềm nào cũng chỉ quản một mảnh, còn thứ nối các mảnh lại vẫn là con người, Excel, email và Zalo.

Đây chính xác là khoảng trống Agentify nhắm tới. Agentify không bán "chuyển đổi số cho DN chưa có gì" — Agentify bán "lớp nối cho DN đã có 5–7 phần mềm mà không hệ thống nào nói chuyện với nhau".

### 3.3. Bằng chứng định tính từ khảo sát ngành

Phản hồi trực tiếp từ nhóm khảo sát ngành logistics:

> "Logistics phục vụ công nghiệp khó khăn sẽ đến từ việc là hiện chưa có 1 GP nào có thể hỗ trợ quản lý full các dịch vụ cho 3PLs, 4PLs bao gồm: cước quốc tế (phần mềm quản lý vận đơn, lệnh giao hàng, doanh thu, chi phí, eDO, eBL và các ứng dụng tra cứu track and trace), hải quan (phần mềm khai báo HQ), trucking (TMS quản lý tra cứu giao nhận nội địa), kho phân phối (phục vụ fulfillment)."

> "Hiện các bên đang phải dùng rời rạc từng hệ thống cho từng modul dịch vụ, kể cả PM kế toán là riêng → nên việc quản trị gặp rất nhiều khó khăn."

**Cách đọc phản hồi này — và một cảnh báo:** phản hồi mô tả nhu cầu về một **suite quản lý đầy đủ cho 3PL/4PL**. Đó là một sản phẩm khác Agentify, cần 3–5 năm và vốn lớn để xây, và phải cạnh tranh trực diện với CargoWise.

Giá trị đúng của phản hồi này với Agentify là ở **vế thứ hai**: nếu không bên nào sắp có suite đầy đủ, thì **tình trạng phân mảnh sẽ còn kéo dài nhiều năm nữa**. Một lớp dữ liệu đứng *trên* các hệ thống rời rạc — không thay thế chúng — có cửa sổ thị trường dài và không phải chờ ai thay đổi hành vi.

> **Rủi ro định vị cần ghi nhận:** khách hàng nói "tôi cần một hệ thống quản lý tất cả" trong khi Agentify bán "một lớp tra cứu trên tất cả". Đội sale phải xử lý được khoảng cách kỳ vọng này ngay ở cuộc gặp đầu tiên, nếu không tỷ lệ chốt sẽ thấp dù pain có thật.

---

## 4. Khung chấm điểm Pain-Fit

### 4.1. Vì sao cần khung chấm điểm

Xếp hạng "pain cao/trung bình/thấp" như bản V2 có hai vấn đề: không kiểm chứng được, và không phân biệt được **pain lớn** với **pain mà sản phẩm này giải được**. Một nhà phân phối B2B nhận đơn qua điện thoại có pain rất lớn — nhưng Agentify không nghe được điện thoại.

### 4.2. Sáu tiêu chí

Mỗi tiêu chí chấm 1–5 điểm.

| # | Tiêu chí | Câu hỏi | Trọng số |
|---|---|---|---|
| F | **Tần suất pain** | Pain xảy ra bao nhiêu lần mỗi ngày cho một người dùng? | ×1 |
| C | **Chi phí pain** | Mỗi lần pain quy đổi ra bao nhiêu tiền hoặc rủi ro mất khách? | ×1 |
| **D** | **Data-fit** | **Dữ liệu gây ra pain có nằm trong email + file đính kèm không?** | **×2** |
| P | **Khả năng chi trả** | DN có ngân sách và người quyết định mua phần mềm không? | ×1 |
| A | **Khả năng tiếp cận** | Có kênh bán, có mối quan hệ, có tập trung địa lý không? | ×1 |
| S | **Tốc độ chứng minh giá trị** | Bao lâu từ lúc connect đến lúc user thấy giá trị? | ×1 |

**Điểm tối đa: 35.** (F + C + 2D + P + A + S)

### 4.3. Vì sao Data-fit nhân đôi trọng số

Data-fit là **ranh giới sống còn** của giai đoạn này, không phải một tiêu chí ngang hàng.

- Nếu D = 5: khách connect Gmail buổi sáng, buổi chiều đã thấy hồ sơ container đầy dữ liệu. Không cần tích hợp, không cần thay đổi quy trình.
- Nếu D = 2: phải xây thêm connector Zalo/OMS/API trước khi khách thấy bất kỳ giá trị nào. Chu kỳ bán kéo dài từ tuần thành quý, và rủi ro sản phẩm tăng gấp bội.

Nói cách khác: F, C, P, A, S đo **thị trường**; D đo **khoảng cách giữa thị trường đó và sản phẩm hiện có**. Đây chính là câu hỏi product-market fit.

### 4.4. Thang điểm Data-fit

| Điểm | Nghĩa | Ví dụ |
|---|---|---|
| 5 | Gần như toàn bộ dữ liệu pain nằm trong email + PDF | Arrival notice, D/O, B/L, debit note của forwarder |
| 4 | Đa số trong email/PDF, một phần trong ảnh/scan | Đại lý hải quan (tờ khai + chứng từ) |
| 3 | Khoảng một nửa; phần còn lại trong hệ thống khác | 3PL (email + WMS/tồn kho) |
| 2 | Thiểu số; dữ liệu chính ở chat/OMS | Nhà phân phối B2B (đơn qua Zalo) |
| 1 | Hầu như không có gì trong email | Trucking (Zalo + ảnh + GPS) |

---

## 5. Xếp hạng 10 nhóm khách hàng

### 5.1. Bảng điểm tổng hợp

`[Ước tính Agentify]` — điểm số dựa trên corpus research 9 cụm nghiệp vụ trong `docs/context-logistics/` và cần hiệu chỉnh sau 10 cuộc phỏng vấn pilot.

| # | Nhóm khách hàng | F | C | **D** | P | A | S | **Tổng /35** | Quy mô ước tính |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---|
| **1** | **FF/NVOCC SME — thiên hàng NHẬP biển** | 5 | 5 | **5** | 4 | 5 | 5 | **34** | 1.500 – 2.500 DN |
| **2** | **FF/NVOCC SME — thiên hàng XUẤT biển** | 4 | 3 | **5** | 4 | 5 | 4 | **30** | 1.500 – 2.500 DN |
| 3 | 3PL đa dịch vụ (kho + vận tải + brokerage) | 5 | 4 | 3 | 4 | 4 | 3 | **26** | 2.000 – 4.000 DN |
| 4 | Chủ hàng XNK (nhà máy/thương mại nhiều PO) | 3 | 5 | 3 | 5 | 3 | 3 | **25** | 5.000 – 8.000 DN |
| 5 | Đại lý khai hải quan | 4 | 3 | 4 | 3 | 3 | 3 | **24** | 1.000 – 2.000 DN |
| 6 | Logistics TMĐT xuyên biên giới | 5 | 4 | 2 | 4 | 2 | 2 | **21** | 500 – 1.500 DN |
| 7 | Nhà phân phối B2B | 5 | 3 | 2 | 4 | 3 | 2 | **21** | 5.000+ DN |
| 8 | Trucking / điều xe container | 5 | 3 | 1 | 3 | 4 | 2 | **19** | 3.000+ DN |
| 9 | D2C / bán lẻ đa kênh | 5 | 3 | 1 | 3 | 2 | 2 | **17** | 5.000+ DN |
| 10 | Bảo hành / bảo trì hiện trường | 3 | 3 | 2 | 3 | 2 | 2 | **17** | 3.000+ DN |

### 5.2. Ba thay đổi quan trọng so với xếp hạng V2

**(a) Logistics TMĐT xuyên biên giới: từ #2 xuống #6.**
Pain của họ có thật và rất cao (F=5). Nhưng dữ liệu đơn hàng, trạng thái vận chuyển và hoàn hàng nằm trong **API sàn TMĐT và hệ thống fulfillment**, không nằm trong hộp thư (D=2). Agentify sẽ phải xây connector sàn trước khi giao được bất cứ giá trị nào. Đây là nhóm tốt cho giai đoạn 3, không phải giai đoạn 1.

**(b) Nhà phân phối B2B: từ #4 xuống #7.**
Đơn hàng đến qua Zalo và điện thoại (D=2). Đúng như bản V2 mô tả — nhưng chính mô tả đó loại họ khỏi beachhead của sản phẩm hiện tại.

**(c) Nhóm #1 được chẻ đôi theo chiều NHẬP/XUẤT.**
Bản V2 gộp chung "Freight Forwarder vừa & nhỏ". Nhưng hàng nhập và hàng xuất có cấu trúc pain khác nhau về mặt tiền bạc:

| | Hàng NHẬP | Hàng XUẤT |
|---|---|---|
| Pain đắt nhất | **DEM/DET** — phí lưu container tính theo ngày sau khi hết free time | Trễ cut-off SI/VGM → rớt tàu |
| Đồng hồ đếm ngược | Có — từ ngày tàu cập (ATA) | Có — nhưng deadline biết trước và cố định |
| Ai chịu phí | Thường forwarder ứng trước rồi đòi lại | Thường chủ hàng chịu, forwarder chịu uy tín |
| Dữ liệu quyết định | Arrival Notice (PDF), D/O (email), EIR trả rỗng | Booking confirm, SI, VGM (email) |
| **Hệ quả** | **Pain có đơn vị tiền tệ rõ ràng → dễ bán** | Pain là uy tín → khó định giá |

Hàng nhập thắng vì **có đồng hồ đếm ngược và có hóa đơn**. Đây là chỗ để cắm mũi nhọn sản phẩm.

### 5.3. Biểu đồ định vị: Pain vs. Data-fit

```text
   CAO │
  P    │   ⑧ Trucking        ⑦ NPP B2B      ③ 3PL        ①② FF/NVOCC
  A    │   ⑨ D2C             ⑥ TMĐT XBG                    ★ BEACHHEAD
  I    │                                     ⑤ ĐL Hải quan
  N    │
       │                     ⑩ Bảo hành      ④ Chủ hàng XNK
   THẤP│
       └────────────────────────────────────────────────────────────►
        THẤP (1-2)          TRUNG BÌNH (3)           CAO (4-5)
                            DATA-FIT

   ⬅ Vùng "bẫy": pain lớn nhưng     Vùng thắng: pain lớn VÀ dữ liệu ➡
     dữ liệu ngoài tầm với           nằm sẵn trong email/PDF
```

**Cách đọc:** nhóm ⑦⑧⑨ nằm ở góc trên-trái là vùng nguy hiểm — pain hấp dẫn nhưng đòi hỏi xây sản phẩm mới. Nhóm ①② ở góc trên-phải là nơi sản phẩm hiện tại giao được giá trị trong ngày đầu tiên.

---

## 6. Beachhead: mổ xẻ nhóm pain cao nhất

### 6.1. ICP — Ideal Customer Profile

| Tiêu chí | Mô tả | Vì sao |
|---|---|---|
| **Loại hình** | Freight Forwarder / NVOCC / Logistics Service Provider | Là bên phải gom thông tin từ nhiều bên nhất |
| **Chiều hàng** | **Thiên hàng nhập đường biển (FCL/LCL) ≥ 50%** | Pain có đồng hồ đếm ngược và có hóa đơn DEM/DET |
| **Quy mô nhân sự** | 20 – 100 người | Đủ lớn để có bộ phận CS/Ops/Docs riêng, đủ nhỏ để quyết định nhanh |
| **Quy mô vận hành** | **100 – 500 shipment/tháng** | Dưới 100: pain chưa đủ đau. Trên 500: thường đã có forwarding software |
| **Doanh thu** | 30 – 300 tỷ VNĐ/năm | Có ngân sách phần mềm nhưng không đủ cho CargoWise |
| **Người dùng hằng ngày** | 5 – 20 seats: CS, Ops, Docs, Account | Đây là số seat để tính giá |
| **Người quyết định mua** | Giám đốc / Head of Ops / Head of CS | Chu kỳ bán ngắn, 1–2 người quyết |
| **Điều kiện kỹ thuật bắt buộc** | **Có hộp thư dùng chung của team (Google Workspace)** | Không có điều kiện này thì Agentify không lấy được dữ liệu ở quy mô đội |
| **Phần mềm đang dùng** | Email, Excel, Zalo, ECUS/VNACCS, MISA/Fast, có thể có forwarding software rời | Agentify nằm cạnh, không thay thế |
| **Địa bàn ưu tiên** | TP.HCM – Bình Dương – Đồng Nai; Hà Nội – Hải Phòng | ~70% DN logistics ở phía Nam |

### 6.2. Persona chính và Job-To-Be-Done

| Persona | JTBD — "Khi… tôi muốn… để…" | Tần suất |
|---|---|---|
| **CS / Customer Service** | Khi khách nhắn hỏi "cont MSCU1234567 tới đâu rồi", tôi muốn trả lời trong 1 phút kèm bằng chứng, để khách không phải hỏi lại lần hai | 20 – 30 lần/ngày |
| **Docs / Documentation** | Khi chuẩn bị bộ chứng từ, tôi muốn biết ngay lô này còn thiếu chứng từ gì và bản B/L nào là mới nhất, để không phải lục lại 40 email | 10 – 15 lô/ngày |
| **Ops / Operations** | Khi tàu cập, tôi muốn biết lô nào sắp hết free time mà chưa có D/O, để không bị tính phí lưu container | Hằng ngày, đầu ca |
| **Head of Ops / CS** | Khi bắt đầu ngày làm việc, tôi muốn thấy danh sách lô đang có rủi ro, để phân công trước khi khách phàn nàn | 1 – 2 lần/ngày |
| **Account / Sales** | Khi khách lớn escalate, tôi muốn nắm toàn cảnh lô hàng trước khi gọi lại, để không trả lời sai | 2 – 5 lần/tuần |

**Người dùng đầu tiên nên là CS.** Họ chạm pain nhiều lần nhất mỗi ngày, giá trị thấy được ngay lập tức, và họ là người sẽ kéo Ops/Docs vào dùng theo.

### 6.3. Bốn cụm pain — kèm bài kiểm tra "dữ liệu nằm ở đâu"

---

#### Pain A — Trả lời trạng thái khách: mở 4 nguồn cho 1 câu hỏi

**Mức độ: CAO · Tần suất: 20–30 lần/người/ngày · Data-fit: ✅ 5/5**

Khi khách hỏi "container đang ở đâu, ETA mới nhất là khi nào, đã có D/O chưa, đã giao kho chưa, còn thiếu chứng từ gì", nhân viên CS thường phải:

1. Mở Gmail, tìm thread theo số container hoặc tên khách.
2. Mở file Excel tracking, tìm dòng tương ứng.
3. Cuộn Zalo group để xem cập nhật mới nhất từ Ops/tài xế.
4. Hỏi lại đồng nghiệp phụ trách lô đó.

**Hệ quả:**
- Trả lời chậm, hoặc trả lời rồi phải đính chính.
- Câu trả lời khác nhau tùy người phụ trách.
- Khi nhân viên nghỉ, không ai bàn giao được vì ngữ cảnh nằm trong đầu và trong hộp thư cá nhân.

**Dữ liệu nằm ở đâu:** email thread + PDF đính kèm (bước 1) là nguồn *chính thức* — bước 2, 3, 4 chỉ là bản sao thủ công của bước 1. → **Agentify đọc thẳng nguồn gốc, bỏ qua ba lớp sao chép.**

---

#### Pain B — Free time / DEM–DET: pain duy nhất có hóa đơn

**Mức độ: RẤT CAO · Tần suất: mỗi container nhập · Data-fit: 🟡 4/5**

Đây là cụm pain quan trọng nhất về mặt thương mại.

**Cơ chế:** Sau khi tàu cập cảng, hãng tàu cho một số ngày **free time** miễn phí lưu container. Hết hạn, phí **demurrage** (lưu container trong cảng) và **detention** (giữ container quá hạn sau khi rút hàng) bắt đầu tính theo ngày, theo container.

**Chuỗi điều kiện để lấy được container ra khỏi cảng:**

```text
Tàu cập (ATA)
  → Có Arrival Notice          [PDF qua email]        ✅ đọc được
  → Đã thông quan tờ khai      [ECUS / báo qua Zalo]  ❌ ngoài tầm
  → Đã thanh toán phí cảng     [email / Zalo]         🟡 một phần
  → Đã có D/O (Delivery Order) [email hãng tàu]       ✅ đọc được
  → Điều được xe               [Zalo group điều xe]   ❌ ngoài tầm
  → Rút hàng, trả rỗng đúng hạn [ảnh EIR qua Zalo]    🟡 cần OCR
```

**Chỉ một mắt xích chậm là cả chuỗi kẹt** — và đồng hồ DEM/DET vẫn chạy.

Từ khảo sát ngành (`cum_1_hai_quan_cang_depot_icd.md`, `cum_3_forwarder_booking_quoc_te_hang_tau_hang_bay.md`):

> "Sắp hết free time/lưu bãi/lưu container → Ops, chủ hàng, quản lý → Phát sinh chi phí → cần deadline monitoring."

> "Với Agentify, đây là nhóm cảnh báo rất có giá trị vì phát sinh tiền trực tiếp."

> "Phí phát sinh thường được phát hiện muộn. DEM/DET, storage, phí sửa chứng từ, phí chờ xe hoặc phí cảng có thể xuất hiện do chậm ở cụm này, nhưng kế toán hoặc account chỉ biết khi nhận hóa đơn/debit note."

**Vì sao Data-fit là 4 chứ không phải 5:** hai dữ kiện đầu chuỗi (ATA + free time từ Arrival Notice, D/O từ email hãng tàu) Agentify đọc được ngay — đủ để **cảnh báo trước**. Nhưng bằng chứng đóng vòng (EIR trả rỗng) nằm trong ảnh chụp qua Zalo, cần OCR ở giai đoạn sau.

**Đây vẫn là tính năng mũi nhọn**, vì giá trị nằm ở *cảnh báo sớm*, không phải ở *đóng sổ*. Biết trước 2 ngày là đủ để hành động.

---

#### Pain C — Chứng từ: thiếu, sai version, không biết bản nào mới nhất

**Mức độ: CAO · Tần suất: mỗi lô · Data-fit: ✅ 5/5**

Một lô hàng quốc tế đi kèm một chuỗi email dài với nhiều bản nháp của cùng một chứng từ: Draft B/L v1, v2, v3; Invoice bản sửa; Packing List cập nhật; C/O bổ sung.

**Hệ quả (theo `cum_9_excel_email_zalo_file_thu_cong.md`):**
- Sai version file → gửi nhầm bản cũ cho hãng tàu hoặc hải quan.
- Không biết nguồn nào đáng tin khi hai file mâu thuẫn.
- File chứng từ khó tìm khi cần gấp hoặc khi audit.

**Dữ liệu nằm ở đâu:** 100% trong attachment của email. Agentify đã lưu `attachments` kèm `document_type`, `extracted_text`, và mốc thời gian — đủ để dựng checklist chứng từ và đánh dấu bản mới nhất.

---

#### Pain D — Đối soát chi phí chậm, rò rỉ doanh thu

**Mức độ: TRUNG BÌNH–CAO · Tần suất: cuối tháng + mỗi lô · Data-fit: 🟡 3/5**

Chi phí một lô đến từ nhiều bên: cước hãng tàu (debit note qua email), phí hải quan (Zalo/email), phí trucking (Zalo/điện thoại), phí kho bãi (email), phí nâng hạ, phí làm D/O.

**Hệ quả:** chậm đối soát → chậm thu tiền; phí phát sinh không ghi nhận kịp → rò rỉ doanh thu; sai sót → tranh chấp.

**Data-fit 3/5:** debit note và invoice (phần lớn giá trị) nằm trong email/PDF ✅. Phí trucking báo qua Zalo/điện thoại ❌. Agentify có thể gom được phía hãng tàu và kho, nhưng chưa khép được vòng đối soát.

> ⚠️ **Đính chính so với V2:** V2 liệt kê "Smart Reconciliation — tự động gom Debit Note + phí trucking + phí HQ → so sánh với quotation → cảnh báo chênh lệch" như một tính năng ngang hàng. Với data-fit 3/5, tính năng này chỉ nên hứa ở dạng "phát hiện debit note chưa gắn shipment" trong 12 tháng đầu.

---

### 6.4. Bảng tổng kết Pain — và điều Agentify KHÔNG hứa

| Pain | Mức độ | Data-fit | Agentify giải được hôm nay? |
|---|:-:|:-:|---|
| A — Trả lời trạng thái khách | Cao | 5/5 | ✅ **Có** — search container → hồ sơ + nguồn |
| B — Free time / DEM–DET | Rất cao | 4/5 | ✅ **Cảnh báo được** — chưa đóng được vòng trả rỗng |
| C — Chứng từ thiếu/sai version | Cao | 5/5 | ✅ **Có** — checklist chứng từ theo lô |
| D — Đối soát chi phí | TB–Cao | 3/5 | 🟡 **Một phần** — gom debit note, chưa gồm phí Zalo |
| E — Handover khi nhân viên nghỉ | Cao | 4/5 | ✅ **Có** — nếu dùng hộp thư dùng chung |
| F — Điều xe, POD/EIR ảnh | Cao | 1/5 | ❌ **Không** — cần OCR + kênh Zalo, roadmap |
| G — Trạng thái tờ khai hải quan | Cao | 1/5 | ❌ **Không** — nằm trong ECUS, ngoài phạm vi |

**Nguyên tắc bán hàng rút ra:** bán A + B + C. Nhắc D như hướng phát triển. **Nói thẳng là chưa làm F và G** — vì nếu khách phát hiện sau khi ký, mất niềm tin còn đắt hơn mất hợp đồng.

---

## 7. Product-Market Fit: pain → tính năng → trạng thái build

### 7.1. Bản đồ đầy đủ

| Pain | Tính năng Agentify | Cách hoạt động | Trạng thái |
|---|---|---|---|
| A | **Shipment Data Hub** | Nhập container/booking/B/L/PO → trả về hồ sơ: trạng thái, email liên quan, chứng từ, timeline, mỗi trường kèm nguồn | ✅ **Đang chạy** |
| A | **Provenance / truy vết nguồn** | Mỗi trường trích xuất giữ email nguồn, file nguồn, thời điểm; không có dữ liệu thì nói "Chưa thấy trong dữ liệu Agentify" | ✅ **Đang chạy** |
| B | **Exception Dashboard** | Tính rủi ro theo container: sắp hết free time, đã cập bến chưa có D/O, ETA đổi chưa báo khách, lô im lặng quá N ngày | ✅ **Vừa build** (mục 7.2) |
| C | **Document Checklist** | Đối chiếu chứng từ đã có với bộ chuẩn theo loại lô (import FCL / export FCL / LCL) → hiện thiếu gì | ✅ **Vừa build** |
| A,C | **AI Document Extraction** | Đọc email + PDF, phân loại chứng từ, trích xuất ~30 trường logistics theo JSON schema chặt | ✅ **Đang chạy** (Azure `gpt-5-nano`) |
| D | **Debit note chưa gắn shipment** | Phát hiện debit note/invoice có phí nhưng chưa liên kết được vào container nào | 🟡 **Roadmap Q+1** |
| F | **OCR ảnh POD/EIR** | Đọc ảnh chụp bằng chứng giao nhận, gắn vào đúng container | 🟡 **Roadmap Q+2** |
| F | **Zalo forward/upload** | User forward tin quan trọng vào Agentify; Zalo OA khi DN có kênh chính thức | 🟡 **Roadmap Q+2** |
| — | Excel tracking import | Đọc file tracking hiện có để seed dữ liệu ngày đầu | 🟡 **Roadmap Q+1** |

### 7.2. Tính năng mũi nhọn: Exception Dashboard

Đây là tính năng chuyển research thành sản phẩm. Nó chuyển Agentify từ **công cụ tra cứu bị động** (user phải biết cần tìm gì) sang **hệ thống cảnh báo chủ động** (Agentify nói cho user biết lô nào cần xử lý hôm nay).

Sáu loại ngoại lệ, tất cả tính được từ dữ liệu email/PDF đã có:

| Mã | Ngoại lệ | Điều kiện phát hiện | Mức |
|---|---|---|---|
| `free_time_expiring` | Sắp hết free time | ATA (hoặc ETA) + số ngày free time − hôm nay ≤ 3 ngày, và chưa thấy bằng chứng đã lấy hàng | 🔴 Nguy cấp |
| `arrived_no_do` | Tàu đã cập nhưng chưa có D/O | Đã qua ATA/ETA ≥ 1 ngày mà không có chứng từ `delivery_order` | 🔴 Nguy cấp |
| `eta_changed` | ETA thay đổi | Tồn tại ≥ 2 fact `eta` khác giá trị; lấy 2 bản mới nhất | 🟡 Cảnh báo |
| `missing_documents` | Thiếu chứng từ bắt buộc | Bộ chứng từ chuẩn − chứng từ đã có ≠ ∅ | 🟡 Cảnh báo |
| `stale_no_update` | Lô im lặng quá lâu | Nguồn mới nhất cũ hơn 7 ngày, lô chưa đóng | 🟡 Cảnh báo |
| `unlinked_charges` | Debit note chưa gắn lô | Có `debit_note`/`invoice` với charges nhưng thiếu định danh container | ⚪ Thông tin |

**Vì sao đây là tính năng đáng trả tiền:** ba ngoại lệ đầu đều có **đơn vị tiền tệ**. Một cảnh báo `free_time_expiring` đúng, xử lý kịp, tiết kiệm số ngày DEM/DET × số container. Đây là con số khách hàng tự tính được — và tự thuyết phục chính họ.

### 7.3. Nguyên tắc sản phẩm phải giữ

Những nguyên tắc này là điều kiện để user tin dữ liệu — mất chúng là mất sản phẩm:

1. **Mọi dữ liệu hiển thị phải có nguồn** — email nào, file nào, ai gửi, lúc nào.
2. **Không có dữ liệu thì nói "Chưa thấy trong dữ liệu Agentify"** — tuyệt đối không đoán.
3. **Matching phải có confidence** — không chắc thì đưa 2–3 hồ sơ để người dùng chọn.
4. **Human-in-the-loop cho mọi kết luận nhạy cảm** — AI không tự cam kết ETA với khách, không tự duyệt chi phí.
5. **Không ghi đè dữ liệu tin cậy** nếu không so sánh được nguồn và thời điểm.

---

## 8. Mô hình ROI định lượng

### 8.1. Cấu phần 1 — Thời gian CS/Ops (dễ tính, dễ hoài nghi)

Công thức từ `cum_8_cs_ops_account_tra_loi_khach.md`:

```text
Số câu hỏi trạng thái/ngày × Số phút/câu × Số nhân sự × Số ngày làm việc/tháng
```

Ví dụ một DN trong ICP: **4 nhân sự CS/Ops · 25 câu hỏi/người/ngày · 8 phút/câu · 22 ngày**

```text
4 × 25 × 8 × 22 = 17.600 phút/tháng ≈ 293 giờ/tháng
```

Nếu Agentify giảm **40%** thời gian tra cứu → tiết kiệm **~117 giờ/tháng**.

`[Ước tính Agentify]` Quy đổi ở mức chi phí nhân sự CS/Ops 12 triệu VNĐ/tháng (~68.000 VNĐ/giờ):

```text
117 giờ × 68.000 VNĐ ≈ 8,0 triệu VNĐ/tháng ≈ 95 triệu VNĐ/năm
```

> ⚠️ **Cảnh báo về cách dùng con số này.** Thời gian tiết kiệm thường **không** chuyển thành cắt giảm nhân sự — nó chuyển thành xử lý được nhiều lô hơn với cùng đội. Đừng bán bằng "giảm biên chế"; bán bằng "cùng đội này xử lý được thêm 30% lô". Giám đốc điều hành hiểu ngôn ngữ đó, và nó đúng với thực tế hơn.

### 8.2. Cấu phần 2 — Tránh phí DEM/DET (khó tính hơn, nhưng thuyết phục hơn nhiều)

```text
Tiết kiệm/năm = Số container nhập/năm
              × Tỷ lệ lô từng phát sinh DEM/DET
              × Số ngày phát sinh trung bình
              × Đơn giá DEM/DET mỗi ngày mỗi container
              × Tỷ lệ ngăn chặn được nhờ cảnh báo sớm
```

`[Ước tính Agentify — TẤT CẢ tham số phải kiểm chứng ở pilot]`

| Tham số | Giả định làm ví dụ | Cách kiểm chứng ở pilot |
|---|---|---|
| Container nhập/năm | 1.800 (150/tháng) | Đếm từ dữ liệu đã sync |
| Tỷ lệ lô phát sinh DEM/DET | 5% | Lấy từ sổ kế toán 6 tháng gần nhất |
| Số ngày phát sinh TB | 2 ngày | Từ debit note hãng tàu |
| Đơn giá/ngày/container | **Phải lấy từ biểu phí thật của hãng tàu** | Không dùng số quốc tế — biểu phí VN khác theo hãng, tuyến, loại cont |
| Tỷ lệ ngăn chặn nhờ cảnh báo | 40% | Đo A/B: lô có cảnh báo vs. không |

**Vì sao không điền sẵn đơn giá:** đơn giá DEM/DET thay đổi theo hãng tàu, tuyến, loại container, và bậc thang ngày. Điền một con số bịa vào đây sẽ khiến toàn bộ mô hình bị bác bỏ ngay khi gặp người trong ngành. **Cách làm đúng ở pilot: xin 6 tháng debit note của khách, cộng thẳng số tiền DEM/DET thực tế đã trả.** Đó là con số không ai cãi được.

### 8.3. Cấu phần 3 — Giá trị không quy đổi được ra tiền

Vẫn nên nêu, nhưng không đưa vào tính ROI:

- Bàn giao được khi nhân viên nghỉ phép hoặc nghỉ việc.
- Onboarding nhân viên mới nhanh hơn (có lịch sử lô để đọc).
- Có bằng chứng khi tranh chấp với khách hoặc hãng tàu.
- Giảm rủi ro dữ liệu nằm trong hộp thư cá nhân của người đã nghỉ.

### 8.4. Payback

`[Ước tính Agentify]` Với giá giả định ở [mục 11.2](#112-giá-đề-xuất) (~28,8 triệu VNĐ/DN/năm cho 6 seats), chỉ riêng cấu phần thời gian (95 triệu VNĐ/năm) đã cho **payback dưới 4 tháng** — chưa tính DEM/DET.

Đây là biên độ an toàn tốt: kể cả khi mức giảm thời gian thực tế chỉ đạt một nửa giả định (20% thay vì 40%), payback vẫn dưới 8 tháng.

---

## 9. TAM / SAM / SOM

### 9.1. Phương pháp

Tính **bottom-up** theo số doanh nghiệp × giá trị hợp đồng năm, không dùng phương pháp "x% của thị trường logistics 52 tỷ USD" — cách đó không kiểm chứng được.

Đơn giá cơ sở: **$1.200/DN/năm** (~28,8 triệu VNĐ) — xem cách dẫn ra ở [mục 11.2](#112-giá-đề-xuất).

Agentify chủ động **loại bỏ tệp 800.000+ SME đại trà** tại Việt Nam (hộ kinh doanh nhỏ lẻ, quán ăn, dịch vụ đơn giản) vì họ không có nhu cầu kết nối hệ thống phức tạp.

### 9.2. TAM — Total Addressable Market: **96 triệu USD/năm** (~2.400 tỷ VNĐ)

Trần dài hạn, bao gồm cả các nhóm mở rộng ở giai đoạn 2–3:

| Nhóm | Số DN | Nỗi đau vận hành |
|---|---|---|
| DN logistics nội địa | ~50.000 | Phân mảnh giữa phần mềm hải quan, kế toán, TMS và dòng email chứng từ |
| Nhà phân phối B2B & bán buôn | ~20.000 | Đội sale chốt đơn, gửi ảnh đại lý, duyệt công nợ qua Zalo/Viber, không đồng bộ ERP |
| Thương hiệu bán lẻ đa kênh & D2C quy mô vừa | ~10.000 | Ngoại lệ đổi trả, khiếu nại rải rác trên Zalo OA/chat sàn, không tự cập nhật OMS/kế toán |
| **Tổng** | **80.000 DN** | **× $1.200/năm = $96.000.000/năm** |

### 9.3. SAM — Serviceable Addressable Market: **21,6 triệu USD/năm** (~540 tỷ VNĐ)

> ⚠️ **Đây là điều chỉnh giảm có chủ đích so với V2** (V2: 30.000 DN = $36M). Lý do: SAM phải chỉ gồm các nhóm có **Data-fit ≥ 3** — tức là dữ liệu gây pain thực sự nằm trong email/file mà Agentify đọc được. Nhóm nhà phân phối B2B và D2C (data-fit 2/5) thuộc TAM nhưng chưa thuộc SAM.

| Nhóm (Data-fit ≥ 3) | Số DN | Điểm Pain-Fit |
|---|---|---|
| FF/NVOCC SME (nhập + xuất) | ~5.000 | 30–34 |
| 3PL đa dịch vụ | ~4.000 | 26 |
| Chủ hàng XNK nhiều shipment/tháng | ~7.500 | 25 |
| Đại lý khai hải quan | ~1.500 | 24 |
| **Tổng** | **18.000 DN** | **× $1.200/năm = $21.600.000/năm** |

**Một SAM nhỏ hơn nhưng cứng hơn có giá trị hơn một SAM lớn mà mềm.** Nhà đầu tư có kinh nghiệm sẽ hỏi "tại sao nhóm này mua được?" — và SAM này trả lời được câu đó cho từng dòng.

### 9.4. SOM — Serviceable Obtainable Market

Cần tách hai khái niệm mà bản V2 gộp làm một:

**(a) Pool có thể tiếp cận trong 1–3 năm: 1.500 DN = $1,8 triệu/năm**

Nhóm Freight Forwarder và NVOCC vừa và nhỏ (20–100 nhân sự) tại TP.HCM, Bình Dương, Đồng Nai, Hà Nội và Hải Phòng — nơi doanh nghiệp có sẵn mối quan hệ đi sale trực tiếp và làm pilot. Đây là **kích thước cái phễu**, không phải doanh thu dự kiến.

**(b) Kế hoạch bán hàng thực tế:**

`[Ước tính Agentify]`

| | Năm 1 | Năm 2 | Năm 3 |
|---|---|---|---|
| Khách trả phí (lũy kế) | 10 – 15 | 60 – 80 | 150 – 250 |
| % của pool 1.500 DN | ~1% | ~5% | ~13% |
| ARR (USD) | $12k – $18k | $72k – $96k | **$180k – $300k** |
| ARR (VNĐ) | 0,3 – 0,4 tỷ | 1,7 – 2,3 tỷ | **4,3 – 7,2 tỷ** |

> **Vì sao phải tách hai con số này.** Nói "SOM = $1,8M" mà không nói rõ đó là pool sẽ bị hiểu là doanh thu năm 3. Chiếm 100% pool 1.500 DN trong 3 năm tương đương ~40 khách mới mỗi tháng liên tục — không khả thi với một đội bán hàng giai đoạn đầu tại Việt Nam. Trình bày cả hai con số cho thấy đội ngũ hiểu sự khác biệt giữa thị trường và kế hoạch, và đó là tín hiệu tốt với nhà đầu tư.

### 9.5. Tóm tắt ba tầng

```text
┌──────────────────────────────────────────────────────────────┐
│ TAM   80.000 DN × $1.200  =  $96.000.000/năm  (~2.400 tỷ VNĐ)│
│       Trần dài hạn, gồm cả nhóm mở rộng giai đoạn 2–3        │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ SAM  18.000 DN × $1.200 = $21.600.000/năm (~540 tỷ)   │   │
│  │      Chỉ nhóm có Data-fit ≥ 3                          │   │
│  │  ┌────────────────────────────────────────────────┐   │   │
│  │  │ SOM-pool  1.500 DN = $1.800.000/năm (~45 tỷ)   │   │   │
│  │  │  ┌──────────────────────────────────────────┐  │   │   │
│  │  │  │ Kế hoạch năm 3: 150–250 DN               │  │   │   │
│  │  │  │ = $180k–$300k ARR (4,3–7,2 tỷ VNĐ)       │  │   │   │
│  │  │  └──────────────────────────────────────────┘  │   │   │
│  │  └────────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 10. Cạnh tranh và khoảng trống

### 10.1. Bốn nhóm sản phẩm liên quan

| Nhóm | Ví dụ | Họ giải gì | Vì sao không lấp được khoảng trống |
|---|---|---|---|
| **Forwarding software / TMS quốc tế** | CargoWise, Magaya, GoFreight | Quản lý job, booking, kế toán forwarding end-to-end | Giá và độ phức tạp vượt tầm SME Việt Nam; vẫn giả định dữ liệu được **nhập vào hệ thống**, không tự đọc từ hộp thư |
| **Document AI / OCR** | Azure AI Document Intelligence, Google Document AI, ABBYY | Đọc chữ và trích trường từ tài liệu | Chỉ là **năng lực đọc**, không hiểu shipment/container; không tự tạo hồ sơ lô hàng hay cảnh báo free time |
| **Phần mềm logistics nội địa** | Các TMS/WMS/FMS Việt Nam | Quản lý mảng vận tải hoặc kho cụ thể | Mỗi sản phẩm quản một mảnh — chính chúng tạo ra sự phân mảnh cần lớp nối |
| **Công cụ tổng quát** | Email, Excel, Zalo, Drive, Copilot/Gemini | Linh hoạt, quen thuộc, miễn phí | Không hiểu nghiệp vụ logistics; không gắn dữ liệu vào shipment; không giữ provenance |

### 10.2. Khoảng trống Agentify nhắm tới

Không có sản phẩm nào hiện làm đồng thời cả bốn việc sau cho SME logistics Việt Nam:

1. **Tự đọc dữ liệu từ nơi nó thực sự nằm** (hộp thư + file đính kèm) thay vì chờ người nhập.
2. **Hiểu ngữ nghĩa logistics** — biết container, B/L, booking, D/O, free time là gì và liên quan nhau thế nào.
3. **Giữ provenance cho từng trường dữ liệu** — nói được thông tin này đến từ email nào, file nào, lúc nào.
4. **Cảnh báo theo đồng hồ tiền bạc** — free time, D/O, chứng từ thiếu.

### 10.3. Ba lợi thế cục bộ

| Lợi thế | Nội dung | Độ bền |
|---|---|---|
| **Ngôn ngữ & chứng từ Việt** | Chứng từ song ngữ Việt–Anh, tên cảng/hãng viết tắt kiểu Việt, cách ghi ngày tháng | Trung bình — LLM đa ngữ đang thu hẹp khoảng cách này |
| **Giá phù hợp SME Việt** | Mức giá dưới ngưỡng ra quyết định của giám đốc SME | Thấp — dễ bị sao chép |
| **Hiểu quy trình vận hành thật** | Biết chuỗi điều kiện lấy container khỏi cảng, biết D/O là nút thắt | **Cao** — đây là tri thức nghiệp vụ, không phải tính năng |

**Hào bảo vệ dài hạn không nằm ở ba điều trên**, mà ở **dữ liệu tích lũy**: khi Agentify đã đọc 12 tháng email của một khách, hồ sơ lịch sử shipment, các mẫu matching đã được người dùng sửa, và các bộ chứng từ chuẩn theo từng khách trở thành chi phí chuyển đổi thật.

### 10.4. Rủi ro cạnh tranh cần theo dõi

| Rủi ro | Mức | Ứng phó |
|---|---|---|
| Google/Microsoft đưa AI đọc hộp thư sâu hơn vào Workspace/365 | Cao | Họ làm lớp chung, không làm ngữ nghĩa shipment và cảnh báo free time — tập trung vào lớp nghiệp vụ |
| Một forwarding software nội địa thêm module đọc email | Trung bình | Tốc độ và độ hẹp là lợi thế; họ vướng backlog sản phẩm lõi |
| Khách tự làm bằng LLM + n8n/Zapier | Trung bình | Làm được demo, khó làm được provenance, confidence, matching và độ tin cậy vận hành |

---

## 11. Go-to-market và pricing

### 11.1. Chiến lược tiếp cận

**Giai đoạn 0 — Pilot có dữ liệu thật (tháng 1–3)**

- Mục tiêu: **5 DN pilot** trong ICP, ưu tiên nơi đã có mối quan hệ.
- Điều kiện chọn: có hộp thư dùng chung, ≥ 100 shipment/tháng, thiên hàng nhập, có 3–5 người dùng thật.
- Giá: miễn phí, đổi lại quyền dùng dữ liệu có consent và cam kết feedback hằng tuần.
- Đầu ra bắt buộc: **6 tháng debit note** của mỗi pilot để dựng mô hình DEM/DET thật.

**Giai đoạn 1 — Chuyển đổi trả phí (tháng 4–9)**

- Chuyển 3/5 pilot sang trả phí. Đây là **tín hiệu PMF quan trọng nhất** — quan trọng hơn mọi chỉ số khác trong tài liệu này.
- Kênh mở rộng: giới thiệu từ pilot, cộng đồng logistics trên Zalo/Facebook, hiệp hội (VLA), sự kiện ngành.

**Giai đoạn 2 — Nhân rộng trong beachhead (tháng 10–24)**

- Case study có số thật từ pilot.
- Bán theo địa bàn: HCM/BD/ĐN trước, rồi HN/HP.

### 11.2. Giá đề xuất

`[Ước tính Agentify — cần kiểm chứng willingness-to-pay ở pilot]`

Giá tính theo **seat**, vì giá trị tỉ lệ với số người tra cứu:

| Gói | Giá/user/tháng | Seat tối thiểu | Giá trị hợp đồng năm |
|---|---|---|---|
| **Core** (tra cứu + hồ sơ + provenance) | 400.000 VNĐ | 5 | ~24 triệu VNĐ (~$1.000) |
| **Ops** (thêm Exception Dashboard + Checklist) | 550.000 VNĐ | 5 | ~33 triệu VNĐ (~$1.375) |
| **Trung bình có trọng số (6 seats)** | — | — | **~28,8 triệu VNĐ ≈ $1.200/năm** |

Con số $1.200/DN/năm dùng cho TAM/SAM/SOM ở mục 9 được dẫn ra từ đây, không phải giả định rời.

**Kiểm tra chéo mức giá:** 28,8 triệu VNĐ/năm ≈ 2,4 triệu VNĐ/tháng — thấp hơn chi phí **1/5 nhân sự CS**, trong khi tiết kiệm ước tính ~117 giờ/tháng (≈ 0,7 FTE). Tỷ lệ giá trị/giá này đủ rộng để chịu được việc khách chiết khấu và việc giả định ROI bị cắt một nửa.

### 11.3. Vòng bán hàng cần chuẩn bị

| Bước | Nội dung | Rủi ro cần xử lý |
|---|---|---|
| 1. Tiếp cận | "Cho tôi 30 phút, tôi sẽ chỉ ra lô nào của anh/chị đang sắp hết free time" | Bị nhầm là bán TMS |
| 2. Demo | Connect hộp thư demo → hiện hồ sơ container thật → mở email nguồn | Demo bằng dữ liệu giả sẽ mất uy tín ngay |
| 3. Xử lý phản đối bảo mật | Chỉ đọc (`gmail.readonly`), không gửi/sửa/xóa email; nêu rõ dữ liệu lưu ở đâu | **Đây là phản đối số 1**, phải có câu trả lời bằng văn bản |
| 4. Pilot | 2–4 tuần, 3–5 user thật, đo 5 chỉ số ở mục 12.2 | User thử vài lần rồi bỏ |
| 5. Chốt | Trình con số DEM/DET thật từ debit note của chính họ | Người quyết định không phải người dùng |

---

## 12. Kế hoạch kiểm chứng PMF và tiêu chí bác bỏ

### 12.1. Mười câu hỏi bắt buộc trong phỏng vấn pilot

Không hỏi "anh/chị có thích ý tưởng này không". Hỏi về hành vi đã xảy ra:

1. Hôm qua anh/chị nhận bao nhiêu câu hỏi trạng thái từ khách? Câu gần nhất mất bao lâu để trả lời?
2. Để trả lời câu đó, anh/chị phải mở những nguồn nào?
3. Team đang dùng hộp thư dùng chung hay hộp thư cá nhân? (**câu quyết định**)
4. 6 tháng qua công ty trả bao nhiêu tiền DEM/DET? Cho tôi xem debit note được không?
5. Lần gần nhất mất/không tìm được chứng từ là khi nào? Hậu quả ra sao?
6. File tracking hiện có bao nhiêu cột, ai cập nhật, cập nhật mấy lần/ngày?
7. POD/EIR/ảnh giao nhận đang lưu ở đâu?
8. Khi một nhân viên nghỉ đột xuất, bàn giao lô đang chạy diễn ra thế nào?
9. Nếu chỉ được một dashboard duy nhất mỗi sáng, anh/chị muốn thấy gì?
10. Ai là người ký duyệt mua một phần mềm 2–3 triệu VNĐ/tháng?

### 12.2. Năm chỉ số đo trong pilot

| Chỉ số | Cách đo | Ngưỡng đạt |
|---|---|---|
| **Tỷ lệ trích xuất đúng `container_no`** | Đối chiếu thủ công 100 email ngẫu nhiên | **≥ 85%** |
| **Thời gian trả lời một câu hỏi trạng thái** | Bấm giờ 20 câu trước và sau | **Giảm ≥ 40%** |
| **DAU/tuần của CS** | Log đăng nhập | **≥ 4/5 ngày làm việc** |
| **Cảnh báo free time đúng** | Đối chiếu cảnh báo với kết quả thực tế | **Precision ≥ 70%** |
| **Chuyển đổi pilot → trả phí** | Hợp đồng ký | **≥ 3/5 DN** |

### 12.3. Tiêu chí bác bỏ (kill criteria)

Nếu một trong các điều sau đúng sau pilot, **định hướng phải đổi, không phải cố bán tiếp**:

| # | Tiêu chí bác bỏ | Nếu đúng thì làm gì |
|---|---|---|
| 1 | **> 40% DN pilot dùng hộp thư cá nhân**, không có hộp thư dùng chung | Không lấy được dữ liệu ở quy mô đội → phải chuyển sang mô hình upload thủ công / Excel import trước |
| 2 | **Trích xuất `container_no` < 70%** trên email thật | Hồ sơ rỗng, user mất niềm tin trong tuần đầu → phải đầu tư mạnh vào extraction trước khi bán |
| 3 | **DEM/DET được tính cho chủ hàng, không phải forwarder** ở đa số hợp đồng | Người đau và người trả tiền là hai bên khác nhau → đổi ICP sang chủ hàng XNK (nhóm #4) |
| 4 | **CS mở Agentify < 2 ngày/tuần** sau tuần thứ 3 | Sản phẩm không vào được thói quen → xem lại điểm vào, có thể phải nhúng vào chính Gmail |
| 5 | **0/5 pilot chuyển sang trả phí** dù dùng đều | Có giá trị nhưng chưa đủ đau để trả tiền → xem lại pricing hoặc đóng gói lại quanh DEM/DET |

---

## 13. Lộ trình mở rộng

### 13.1. Ba giai đoạn

```text
GIAI ĐOẠN 1 (0–12 tháng)         GIAI ĐOẠN 2 (12–24 tháng)        GIAI ĐOẠN 3 (24+ tháng)
━━━━━━━━━━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━━━━━━━━━━

🎯 FF/NVOCC hàng NHẬP biển       📦 3PL đa dịch vụ                🛒 Nhà phân phối B2B
   Pain-Fit 34/35                   Pain-Fit 26/35                   Pain-Fit 21/35
   ~1.500 DN pool                   ~4.000 DN                        ~5.000 DN
   Data-fit 5/5 — bán ngay          Cần: OCR ảnh + WMS context       Cần: kênh Zalo/OA

   ↓ mở rộng tự nhiên            📄 Chủ hàng XNK                   🌏 Logistics TMĐT XBG
                                    Pain-Fit 25/35                    Pain-Fit 21/35
🎯 FF/NVOCC hàng XUẤT               ~7.500 DN                         Cần: connector sàn
   Pain-Fit 30/35                   Cần: cổng chia sẻ cho
   Cùng khách, cùng hộp thư         forwarder/vendor
```

### 13.2. Năng lực cần mở khóa trước mỗi bước

| Bước mở rộng | Năng lực bắt buộc phải có trước |
|---|---|
| Hàng xuất | Checklist theo loại lô export; cảnh báo cut-off SI/VGM |
| 3PL | OCR ảnh POD/EIR; khái niệm order/task ngoài shipment |
| Chủ hàng XNK | Cổng để forwarder/vendor chia sẻ dữ liệu vào Agentify |
| Nhà phân phối B2B | Kênh Zalo OA + trích xuất đơn hàng từ tin nhắn tự do |
| Logistics TMĐT | Connector sàn TMĐT + xử lý luồng hoàn hàng |

**Nguyên tắc:** không mở segment mới khi chưa mở khóa năng lực tương ứng. Bản V2 xếp nhà phân phối B2B ở vị trí thứ 2 — với năng lực hiện tại, bán cho họ đồng nghĩa với hứa một sản phẩm chưa tồn tại.

---

## 14. Phụ lục

### 14.1. Nguồn dữ liệu

**Nguồn bên ngoài**

| Nguồn | Nội dung tham khảo |
|---|---|
| logistics.gov.vn | Số liệu chính thức ngành logistics VN, chi phí logistics/GDP |
| mordorintelligence.com | Quy mô thị trường, CAGR, dự báo |
| expertmarketresearch.com | Phân khúc thị trường, dự báo 2035 |
| b-company.jp | Phân tích DN logistics VN, tỷ lệ SME, AI adoption |
| udn.vn | Thống kê 97,8% DN dùng Excel |
| vngcloud.vn | Tỷ lệ ứng dụng công nghệ trong logistics |
| researchgate.net, ijeijournal.com | Rào cản chuyển đổi số SME |
| vietnam.vn, vietnamnet.vn, vng.com.vn | Số liệu Zalo MAU, Zalo OA |
| Maersk — Demurrage & Detention | Định nghĩa free time, DEM, DET |

**Nguồn nội bộ (corpus research trong repo)**

| File | Dùng cho |
|---|---|
| `docs/context-logistics/cum_1_hai_quan_cang_depot_icd.md` | Chuỗi điều kiện lấy container khỏi cảng, free time monitoring |
| `docs/context-logistics/cum_3_forwarder_booking_quoc_te_hang_tau_hang_bay.md` | DEM/DET, free time, booking, cut-off |
| `docs/context-logistics/cum_4_chung_tu_xuat_nhap_khau.md` | Bộ chứng từ XNK, phân loại tài liệu |
| `docs/context-logistics/cum_7_ke_toan_chi_phi_hoa_don_doi_soat.md` | Đối soát chi phí, debit note, revenue leakage |
| `docs/context-logistics/cum_8_cs_ops_account_tra_loi_khach.md` | Pain ranking CS/Ops, công thức ROI thời gian |
| `docs/context-logistics/cum_9_excel_email_zalo_file_thu_cong.md` | Bản đồ dữ liệu thủ công, pain version file |
| `docs/context-logistics/de_xuat_agentify_v3.md` | Định vị sản phẩm, ICP, 5 module MVP |
| Phản hồi nhóm khảo sát ngành (Zalo) | Thực trạng phần mềm rời rạc cho 3PL/4PL |

### 14.2. Ghi chú phương pháp

1. **Số liệu thị trường dao động lớn** (52–86 tỷ USD) do khác biệt định nghĩa "logistics market" giữa các nguồn (chỉ freight vs. toàn bộ supply chain services). Tài liệu này dùng khoảng, không dùng điểm.
2. **Ước tính số DN theo phân khúc** dựa trên tổng số DN logistics (30.000–50.000) và tỷ lệ phân bổ từ các nguồn khảo sát. Đây là ước tính, không phải thống kê.
3. **Điểm Pain-Fit là đánh giá nội bộ**, dựa trên corpus research 9 cụm nghiệp vụ. Cần hiệu chỉnh sau 10 phỏng vấn pilot đầu tiên.
4. **Benchmark hiệu suất** (giảm 40% thời gian tra cứu) dựa trên số liệu toàn cầu về AI document processing. Bản V2 dùng "80–90%" — V3 hạ xuống 40% vì con số 80–90% chỉ áp dụng cho *thao tác nhập liệu thuần*, không áp dụng cho *toàn bộ chu trình trả lời khách* vốn còn gồm đọc hiểu, xác nhận và soạn câu trả lời.
5. **Đơn giá DEM/DET cố tình để trống** — phải lấy từ debit note thật của khách pilot. Dùng số quốc tế sẽ sai với biểu phí Việt Nam.
6. **Mọi con số gắn nhãn `[Ước tính Agentify]` chưa được kiểm chứng** và cần cập nhật sau pilot.

### 14.3. Thuật ngữ

| Thuật ngữ | Giải thích |
|---|---|
| **NVOCC** | Non-Vessel Operating Common Carrier — hãng vận tải không sở hữu tàu, phát hành vận đơn riêng |
| **FCL / LCL** | Full / Less than Container Load — hàng nguyên container / hàng lẻ ghép container |
| **B/L** | Bill of Lading — vận đơn đường biển |
| **D/O** | Delivery Order — lệnh giao hàng, điều kiện bắt buộc để lấy container khỏi cảng |
| **Arrival Notice** | Thông báo hàng đến, chứa ETA, số container, free time |
| **SI / VGM** | Shipping Instruction / Verified Gross Mass — chỉ thị giao hàng và khai báo khối lượng, có deadline cut-off |
| **Free time** | Số ngày miễn phí lưu container sau khi tàu cập |
| **DEM / DET** | Demurrage / Detention — phí lưu container trong cảng / phí giữ container quá hạn sau khi rút hàng |
| **EIR** | Equipment Interchange Receipt — phiếu giao nhận container, bằng chứng trả rỗng |
| **POD** | Proof of Delivery — bằng chứng giao hàng |
| **ETA / ETD / ATA / ATD** | Estimated / Actual Time of Arrival / Departure |
| **Provenance** | Nguồn gốc dữ liệu — email nào, file nào, ai gửi, lúc nào |
| **Data-fit** | Mức độ dữ liệu gây pain nằm trong nguồn mà sản phẩm đọc được |
| **TAM / SAM / SOM** | Total / Serviceable Addressable / Serviceable Obtainable Market |
| **ICP** | Ideal Customer Profile — chân dung khách hàng lý tưởng |
