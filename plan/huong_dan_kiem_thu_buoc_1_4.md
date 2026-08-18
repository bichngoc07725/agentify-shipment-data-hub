# Hướng dẫn kiểm thử tay — Bước 1 đến Bước 6

Đi trọn một lô hàng: khách hỏi giá → báo giá → đặt chỗ → chứng từ → hải quan
→ ảnh hiện trường → đối soát chi phí.

Bước 1–4 dùng `sales` · `ops` · `docs`. Bước 5 là của `taixe`, Bước 6 của
`ketoan` — hai bước này **cần LLM vision** (Bước 5) và một giấy báo nợ gõ tay
(Bước 6), nên tách riêng ở cuối.

**Bạn không phải gõ hay dán dữ liệu.** Một lệnh nạp sẵn toàn bộ email vào hệ
thống, phần còn lại chỉ là bấm nút trên web.

Mỗi bước ghi rõ: **ai làm · nhận gì · bấm gì · phải thấy gì · bàn giao cho ai**.

---

## Lô hàng dùng xuyên suốt

| | |
|---|---|
| Khách hàng | Cong ty CP Det May Thanh Long — MST `0201234567` |
| Tuyến | Hai Phong → Yokohama |
| Hàng | Áo sơ mi cotton, 2 x 40HC, HS `6205.20.00` |
| Hãng tàu | Ocean Network Express — tàu `ONE COMMITMENT 145E` |
| Container | `ONEU7041287` — **chưa tồn tại lúc bắt đầu**, ra đời ở Bước 2 |
| Ngày tháng | ba mốc cut-off và ETD/ETA **dời theo ngày bạn thả thư**, nên đếm ngược luôn có nghĩa. Ngày quá khứ (hoá đơn, đăng ký tờ khai) giữ nguyên |
| Hoá đơn | `INV-TL-260815` · trị giá `USD 128,400` |
| Tờ khai | `305892374611` · **Luồng Đỏ** · thuế `VND 42,150,000` |

Điểm mấu chốt cần hiểu trước: **Bước 1 và nửa đầu Bước 2 diễn ra khi chưa có
container**. Hãng tàu chỉ cấp số container khi xác nhận đặt chỗ. Vì vậy hai bước
đó làm việc trên **báo giá**, không phải trên trang container.

---

## Bước 0 — Chuẩn bị (2 phút)

**0.1** Kiểm hệ thống đang chạy:

```bash
curl -s http://127.0.0.1:8766/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5174/
```

Kỳ vọng `{"status":"ok","database":"ok"}` và `200`. Nếu không, khởi động lại:

```bash
cd backend && ./.venv/bin/uvicorn api.routes.api_main:app --reload --port 8766
cd frontend_v2 && npm run dev
```

**0.2 Làm sạch và bắt đầu — một lệnh:**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --wipe --yes --deliver rfq
```

Lệnh này **xoá sạch mọi container, báo giá, chỗ đặt, tờ khai và thư** trong DB,
rồi thả vào hộp thư đúng **một** thư: thư khách hỏi giá.

> Bỏ `--yes` thì script hỏi lại trước khi xoá. Terminal của VS Code hay tự chèn
> lệnh `source .venv/bin/activate` vào giữa lúc đang chờ nhập và làm hỏng câu
> hỏi — nên trong IDE cứ dùng `--yes`.

Tài khoản và kết nối Gmail giữ nguyên — không phải nối lại OAuth.

> Vì sao phải xoá sạch chứ không chỉ xoá lô này: chạy thử nhiều lần để lại
> container của kịch bản khác, báo giá mồ côi, cảnh báo của lô đã xoá. Khi đó
> nhìn màn hình không kết luận được gì, vì không biết con số đang thấy đến từ
> lần chạy nào.

**0.3 Thư đến theo đợt, không đổ hết một lượt.**

Hộp thư lúc này chỉ có thư hỏi giá — đúng như ngoài đời. Mỗi khi bạn "gửi" một
thư đi, chạy lệnh tương ứng để **nhận thư trả lời**:

| Chạy khi tới | Lệnh | Thư nhận được |
|---|---|---|
| **Bước 1.4** (sau khi gửi thư hỏi cước ở 1.3) | `--deliver rate` | hãng tàu báo bảng cước |
| **Bước 2.3** (sau khi gửi thư đặt chỗ ở 2.2) | `--deliver booking` | hãng tàu xác nhận + số container |
| **Bước 3.1** | `--deliver docs` | khách gửi Invoice + Packing List |
| **Bước 4.2** (sau khi truyền tờ khai ở 4.1) | `--deliver customs` | hải quan thông báo phân luồng |

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --deliver <tên đợt>
```

`--deliver` **không xoá gì** — báo giá và chỗ đặt bạn vừa tạo còn nguyên. Chạy
lại một đợt đã nhận cũng không nhân bản thư.

> Đây là chỗ đáng giá nhất của cách làm này. Nếu thư xác nhận nằm sẵn trong hộp
> thư từ đầu, thì ở Bước 2.1 — lúc bạn còn đang soạn yêu cầu đặt chỗ — câu trả
> lời đã có trước câu hỏi. Không phân biệt được cái gì hệ thống suy ra và cái
> gì vốn đã có, và câu hỏi trung tâm của Bước 2 (*ghi nhận được trạng thái "đã
> hỏi mà chưa được trả lời" không?*) không kiểm được nữa.

> Ba thư đi không bao giờ được nạp: đó là thư Agentify soạn cho bạn tự gửi, nạp
> ngược vào hồ sơ sẽ tạo ra dữ liệu mà ngoài đời không có.

**0.4** Tài khoản: `sales/sales@123` · `ops/ops@123` · `docs/docs@123` ·
`ketoan/ketoan@123` · `taixe/taixe@123` · `admin/admin@123`

**0.5 Chỉ muốn CHIẾU cho người khác xem, không muốn bấm lại từ đầu?**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --wipe
```

Một lệnh, thay cho cả 0.2 + 0.3 và toàn bộ thao tác Bước 1→4: dọn lô cũ, nạp 6
thư, rồi dựng luôn báo giá `3103.00 USD` đã duyệt, chỗ đặt tàu đã xác nhận kèm
ba mốc cut-off, và tờ khai Luồng Đỏ. Dữ liệu nằm trong
`backend/scripts/demo_data/roundtrip_rfq_hpn.json` — sửa kịch bản không cần đụng
code.

Muốn dừng giữa chừng để tự diễn tiếp từ đó:

| Lệnh | Dựng sẵn tới | Bạn diễn tiếp từ |
|---|---|---|
| `--stage emails` | chỉ 6 thư | Bước 1.1 |
| `--stage quote` | + báo giá đã duyệt | Bước 2.1 |
| `--stage booking` | + chỗ đặt đã xác nhận | Bước 3.1 |
| *(mặc định)* | + tờ khai Luồng Đỏ | xem kết quả |

Thêm `--no-reset` nếu muốn giữ dữ liệu đang có. **Để kiểm thử thật thì đừng
dùng seeder** — nó ghi thẳng dữ liệu vào, bỏ qua đúng những nút mà bạn cần
kiểm.

> **Không cần LLM.** Toàn bộ hướng dẫn này chạy được bằng bộ đọc regex, kể cả
> bảng phí. Nếu có hạn mức LLM thì kết quả trích xuất đầy đủ hơn, nhưng mọi
> bước dưới đây vẫn đúng khi nhà cung cấp hết quota.

---

## BƯỚC 1 — Hỏi giá & báo giá · **Sales/CS**

> Rủi ro gốc: *báo giá miệng qua Zalo không lưu vết, tranh chấp không đối chiếu được.*

### 1.1 Xem thư khách hỏi giá

Đăng nhập **`sales`** → sidebar **Emails** → mở thư
**`[AGENTIFY-DEMO][KHACH>AGENTIFY] Cần báo giá Hai Phong - Yokohama…`**

**Phải thấy:** nội dung thư, và mục *Extracted facts* **trống hoặc rất ít**.

**Điều này đúng, không phải lỗi:** thư hỏi giá chưa có số container nên hệ thống
không gắn được fact vào đâu. Đó chính là lỗ hổng mà nút ở bước sau vá lại.

### 1.2 Tạo báo giá từ chính thư đó

Vẫn ở trang thư → bấm **"Tạo báo giá từ email này"**

**Phải thấy:** nhảy sang form báo giá, băng xanh *"Đã điền N trường từ email…"*,
và **8 ô** đã có sẵn:

| Ô | Giá trị |
|---|---|
| Khách hàng | `Cong ty CP Det May Thanh Long` |
| POL / POD | `Hai Phong` / `Yokohama` |
| Mặt hàng | `Áo sơ mi cotton` |
| Loại / số cont | `40HC` / `2` |
| Ngày hàng sẵn | **hôm nay + 4 ngày** (xem đúng thư) |
| Incoterm | `FOB` |

> Thư này viết tuyến bằng câu tiếng Việt — *"Lấy hàng tại Hai Phong, giao
> Yokohama"* — chứ không có nhãn `POL:` nào. Ô POL/POD trống là lỗi bộ đọc,
> không phải giới hạn của dữ liệu.

**Điền thêm bằng tay:** ô **Hiệu lực đến** — chọn ngày nào cũng được, miễn ở
tương lai (VD hai tuần nữa).

Bấm **Lưu báo giá** → **ghi lại mã `Q-2026-00xx`**.

### 1.3 Soạn thư hỏi cước hãng tàu

Cuộn tới mục **TRAO ĐỔI THƯ** → bấm **"Soạn thư hỏi cước hãng tàu"**

**Phải thấy:** thư tiếng Anh, tiêu đề `Rate request Hai Phong - Yokohama / 2 x
40HC / ref Q-2026-00xx`, thân thư hỏi đủ 3 thứ: free time, transit time, rate
validity.

Bấm **Chép tiêu đề + nội dung** hoặc **Mở trong Gmail** → tự gửi.

> Agentify không gửi thay bạn. Quyền Gmail là chỉ-đọc.

### 1.4 Nạp phí từ thư hãng tàu trả lời

**Nhận thư trả lời của hãng tàu trước:**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --deliver rate
```

Bấm **"Nạp phí từ thư hãng tàu trả lời"** → chọn thư
**`RE: Rate request Hai Phong - Yokohama…`**

**Phải thấy 6 dòng phí, chia đúng 3 nhóm:**

| Nhóm | Mã | Đơn giá | SL | Thành tiền |
|---|---|---|---|---|
| Cước biển | OF | 1240.00 | 2 | 2480.00 |
| Phụ phí | BAF | 130.00 | 1 | 130.00 |
| Phụ phí | LSS | 88.00 | 1 | 88.00 |
| Phí local | THC | 170.00 | 2 | 340.00 |
| Phí local | DOC | 35.00 | 1 | 35.00 |
| Phí local | TELEX | 30.00 | 1 | 30.00 |

**TỔNG PHẢI LÀ `USD 3103.00`.**

> Phép kiểm quan trọng nhất Bước 1. Thư ghi *"Ocean Freight 40HC x2 USD
> 2,480.00"* — con số 2 480 là **thành tiền cả dòng**, hệ thống chia cho số
> lượng để ra đơn giá 1 240. Ra **6206** là nhánh chia hỏng (nhân đôi); ra
> **1723** là đọc thiếu số lượng.

Bấm **Lưu báo giá**.

### 1.5 Gửi báo giá cho khách

Bấm **"Soạn thư báo giá gửi khách"**

**Phải thấy:** thư tiếng Việt, bảng phí 3 khối, dòng số lượng khác 1 hiện `(x2)`,
kết bằng `TỔNG CỘNG: 3103.00 USD`. Chép và gửi.

### 1.6 Khách duyệt giá

Bấm **Sửa** → ô **Trạng thái** chọn **Khách chấp nhận** → **Lưu báo giá**.

### ✅ Kết thúc Bước 1

Báo giá có mã số, 6 dòng phí, trạng thái đã duyệt. Đây sẽ là **mốc đối soát ở
Bước 6**.

**Bàn giao:** Ops mở chính báo giá này.

---

## BƯỚC 2 — Đặt chỗ trên tàu · **Operations**

> Rủi ro gốc: *trễ giờ chốt hạ container → rớt chuyến, phát sinh phí lưu kho.*

### 2.1 Mở yêu cầu đặt chỗ

Đăng nhập **`ops`** → **Quotes** → mở `Q-2026-00xx` → mục **ĐẶT CHỖ TRÊN TÀU** →
**"+ Đặt chỗ mới"** → **"Điền từ báo giá đã chốt"**

**Phải thấy tự điền:** POL `Hai Phong`, POD `Yokohama`, `40HC`, `2`, ETD
**hôm nay + 4 ngày** (lấy từ ngày hàng sẵn trong báo giá).

**Điền thêm:** Hãng tàu `Ocean Network Express` · Trạng thái **Đã gửi yêu cầu**

**Để trống ô Số container** — hãng tàu chưa cấp. Bấm **Lưu chỗ đặt**.

**Phải thấy:** thẻ ghi *"Chưa có số booking"*, huy hiệu xám **Đã gửi yêu cầu**.

> Đây là lý do `container_id` được phép rỗng. Bắt buộc phải có container ở bước
> này đồng nghĩa không ghi nhận được trạng thái "đã hỏi mà chưa được trả lời" —
> đúng khoảnh khắc bước này cần theo dõi nhất.

### 2.2 Gửi thư đặt chỗ

Bấm **"Soạn thư đặt chỗ gửi hãng tàu"**

**Phải thấy:** thư **chốt chỗ** (`firm booking`), hỏi đúng 4 thứ: số booking,
tàu/chuyến + ETD-ETA, ba mốc cut-off, depot lấy rỗng.

> Khác thư Bước 1: bước 1 hỏi giá, bước 2 chốt chỗ. Gửi nhầm thư hỏi giá ở đây
> khiến hãng tàu tưởng ta còn so giá và không giữ chỗ.

### 2.3 Xem thư xác nhận của hãng tàu

**Nhận thư xác nhận:**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --deliver booking
```

**Emails** → gõ `BOOKING CONFIRMATION` vào ô tìm → mở
**`[AGENTIFY-DEMO][HANGTAU>AGENTIFY] BOOKING CONFIRMATION ONE-BKG-260805 / ONEU7041287`**

> Thư demo mang ngày thật của kịch bản (`2026-08-05`), không phải ngày bạn nạp,
> nên nó nằm giữa danh sách chứ không ở trên cùng. Danh sách chỉ tải 100 thư
> mỗi lần và ô tìm chỉ lọc trong số đã tải — còn thư chưa tải thì có dòng
> *"Đang hiển thị x/y thư"* kèm nút **Tải thêm**.

**Phải thấy:** thư có đủ số booking, container, tàu/chuyến, 3 mốc cut-off, depot.

**Containers** → **`ONEU7041287`** đã xuất hiện trong danh sách. Đây là khoảnh
khắc container ra đời.

### 2.4 Cập nhật chỗ đặt theo xác nhận

Quay lại **Quotes** → `Q-2026-00xx` → thẻ chỗ đặt →
**"Cập nhật sau khi hãng tàu xác nhận"**

Bấm **"Điền từ thư xác nhận của hãng tàu"** → chọn thư
**`BOOKING CONFIRMATION ONE-BKG-260805 / ONEU7041287`**

**Phải thấy tự điền đủ 11 ô:**

| Ô | Giá trị |
|---|---|
| Số booking | `ONE-BKG-260805` |
| Tên tàu / Số chuyến | `ONE COMMITMENT` / `145E` |
| **Số container** | `ONEU7041287` |
| Cảng đi / đến | `Hai Phong` / `Yokohama` |
| ETD / ETA | **hôm nay + 4** / **+13 ngày** |
| SI cut-off | **hôm nay + 2 ngày** `16:00` |
| VGM cut-off | **hôm nay + 2 ngày** `10:00` |
| Gate-in cut-off | **hôm nay + 3 ngày** `15:00` |
| Depot lấy rỗng | `Nam Hai Dinh Vu depot, Hai Phong` |

**Chỉ còn hai ô gõ tay:** Trạng thái = **Hãng tàu đã xác nhận** · Giá cước hãng
tàu = `1240` USD.

> Giá cước phải gõ tay có lý do: thư xác nhận **không ghi giá**. Hệ thống điền
> hộ một con số nó không đọc được ở đâu là chuyện tệ nhất có thể làm ở bước
> này, vì `1240` sẽ đi thẳng vào đối soát Bước 6.

> Kiểm giờ cut-off: thư ghi `16:00 (GMT+7)` thì ô phải hiện **16:00**. Hiện
> `09:00` nghĩa là có ai đó quy đổi múi giờ — mốc cut-off là giờ tại cảng xếp,
> quy đổi ở đây là đường thẳng tới rớt chuyến.

Bấm **Lưu thay đổi**.

**Phải thấy:** huy hiệu xanh **Hãng tàu đã xác nhận**, và **băng đếm ngược**
*"VGM cut-off còn … ngày"*. Dưới 72 giờ chuyển cam, dưới 24 giờ đỏ, quá hạn đổi
thành **"ĐÃ QUÁ HẠN x giờ"**.

> Giá cước `1240` là **giá mua từ hãng tàu**, khác giá bán `2480` trong báo giá.
> Chênh lệch chính là biên lợi nhuận của lô.

### ✅ Kết thúc Bước 2

Container có hồ sơ, ba mốc cut-off được đếm ngược tự động.

**Bàn giao:** Docs mở trang container.

---

## BƯỚC 3 — Chuẩn bị chứng từ · **Documentation**

> Rủi ro gốc: *Invoice/Packing List sai lệch không phát hiện sớm → lỗi kéo dài đến khâu hải quan.*

### 3.1 Mở hồ sơ container

**Nhận chứng từ khách gửi:**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --deliver docs
```

Đăng nhập **`docs`** → **Containers** → **`ONEU7041287`**

**Phải thấy:** ô đếm *"Chứng từ x/5"*, mục **ĐẶT CHỖ TRÊN TÀU** (chỉ xem, không
có nút sửa — đó là việc của Ops).

### 3.2 Cảnh báo vênh chứng từ

Ở mục **Cần xử lý** đầu trang:

> ⚠️ **Chứng từ vênh nhau: Số kiện**
> Số kiện — Invoice: 940 CTNS ≠ Packing List: 904 CTNS. Hai chứng từ khai khác
> nhau về cùng một số liệu — đối chiếu và sửa trước khi khai hải quan.

**Không được có cảnh báo về trọng lượng** — hai chứng từ cùng ghi 18 500 KGS.

> Hệ thống **không tự chọn bên nào đúng**. Cả hai đều là chứng từ do đối tác
> phát hành, máy không có căn cứ phân xử. Việc của nó là bắt bạn nhìn thấy chỗ
> vênh — trước khi khai, không phải sau.

### 3.3 Xem lịch sử trường dữ liệu

Cuộn tới bảng *Fact history*.

**Phải thấy:** mỗi trường ghi rõ **nguồn** (Invoice / Packing List / Booking
confirmation / Thông báo hải quan) và thời điểm. Đây là nguyên tắc provenance:
mọi giá trị truy được về chứng từ gốc.

### 3.4 Phiếu nhập liệu tờ khai

Cuộn tới **PHIẾU NHẬP LIỆU TỜ KHAI (ECUS/VNACCS)**

**Phải thấy:** *"24/32 ô đã có dữ liệu · 8 ô phải tự bổ sung"*

> Con số này phụ thuộc bước đã làm. Chưa cập nhật chỗ đặt ở 2.4 thì tàu/chuyến
> còn trống → **20/32**. Sau Bước 4 (có tờ khai và thư phân luồng) sẽ lên
> **27/32**: số tờ khai, loại hình và chi cục hải quan tự đầy.

**Phiếu này CHỈ ĐỌC — không sửa, không thêm ô được.** Nó là bản dựng lại từ dữ
liệu đã có, không phải một biểu mẫu để điền. Muốn đổi một ô đang hiện sai thì
sửa ở **Fact history** (mục 3.3), phiếu tự đổi theo.

Bấm **Xem chi tiết** → 5 mục A–E. Kiểm vài ô đáng chú ý:

| Ô | Giá trị |
|---|---|
| Người xuất khẩu — tên | Cong ty CP Det May Thanh Long |
| Người xuất khẩu — mã số thuế | `0201234567` |
| Người nhập khẩu | Sakura Apparel Trading K.K |
| Tên tàu / Số chuyến | `ONE COMMITMENT` / `145E` |
| Số hoá đơn / Ngày | `INV-TL-260815` / `2026-08-15` |
| Số kiện · Trọng lượng · Số khối | `904 CTNS` · `18,500 KGS` · `62.5 CBM` |

Ô thiếu hiện **nền hồng, chữ đỏ nghiêng**, ghi rõ *"KHÔNG CÓ TRONG AGENTIFY —
cần lấy từ …"*.

Bấm **Tải file .docx** → mở bằng Word, nội dung giống hệt bản trên web.

> Ô **Tổng trị giá hoá đơn** cố ý để trống dù hệ thống có tổng báo giá 3 103
> USD. Tổng báo giá là tiền **cước dịch vụ**, không phải **trị giá lô hàng**.
> Điền nhầm vào tờ khai là khai sai trị giá hải quan.

### ✅ Kết thúc Bước 3

Sai lệch Invoice ↔ Packing List lộ ra **trước** khi khai; có một tờ phiếu để gõ
sang ECUS.

**Bàn giao:** Ops cầm phiếu đi khai.

---

## BƯỚC 4 — Khai hải quan · **Operations**

> Rủi ro gốc: *rơi Luồng Đỏ → chậm 1–2 ngày → phát sinh phí lưu container.*

### 4.1 Gõ tờ khai sang ECUS

Mở phiếu (web hoặc file .docx) cạnh màn hình ECUS/VNACCS và gõ theo.

> **Agentify không nối vào ECUS.** Đó là phần mềm ngoài, có quy trình chữ ký số
> riêng. Ô đỏ trên phiếu là ô bạn phải tự tra theo nguồn ghi kèm.

### 4.2 Ghi nhận phân luồng

**Nhận thông báo phân luồng của hải quan:**

```bash
backend/.venv/bin/python backend/scripts/seed_demo_shipment.py --deliver customs
```

Đăng nhập **`ops`** → **Containers** → `ONEU7041287` → mục **Hải quan** →
**"+ Nhập tờ khai"**

Bấm **"Điền từ thông báo hải quan đã đọc"** trước.

**Phải thấy tự điền đủ 5 ô:**

| Ô | Giá trị |
|---|---|
| Số tờ khai | `305892374611` |
| Mã HS | `6205.20.00` |
| Luồng | **Luồng Đỏ** |
| Ngày đăng ký | `2026-08-16` |
| Tiền thuế (VND) | `42150000` |

> Ô **Tiền thuế** đáng nhìn kỹ: thư ghi *"VND 42,150,000"*, còn ô trên form là
> ô số. Ô này trống sau khi bấm điền nghĩa là chuỗi có ký hiệu tiền tệ đã bị
> trình duyệt bỏ lặng — tờ khai lưu xuống thiếu thuế mà không ai được báo.

**Để trống ô Ngày thông quan** — sẽ điền ở 4.4. Bấm **Lưu tờ khai**.

**Phải thấy:** huy hiệu **đỏ**, và cảnh báo nghiêm trọng **"Tờ khai Luồng Đỏ"**
ở mục *Cần xử lý*.

### 4.3 Luồng Đỏ đẩy sớm cảnh báo phí lưu container

Đây là mối nối đáng kiểm nhất của Bước 4: cùng một hạn free time, cảnh báo
*"Sắp hết free time"* nổi lên **sớm hơn 2 ngày** khi lô đang ở Luồng Đỏ chưa
thông quan.

```bash
cd backend && ./.venv/bin/python -c "
from datetime import date
from types import SimpleNamespace
from services.exception_service import detect_exceptions
c = SimpleNamespace(container_no='X', ata=None, eta=date(2026,8,7), free_time_days=8,
    do_no=None, pod='Hai Phong', pol='Busan', etd=None, vessel=None, voyage=None,
    bl_no=None, booking_no=None)
common = dict(document_types=set(), eta_history=[], last_source_at=None, today=date(2026,8,10))
for lane, cleared in [('green',False),('red',False),('red',True)]:
    ex = detect_exceptions(c, customs_channel=lane, customs_cleared=cleared, **common)
    ft = next((e for e in ex if e.code=='free_time_expiring'), None)
    print(f'  {lane:6} đã thông quan={cleared}: ' + ('CẢNH BÁO' if ft else 'chưa cảnh báo'))"
```

Kỳ vọng: `green` chưa · `red` chưa thông quan **CẢNH BÁO** · `red` đã thông quan
chưa.

### 4.4 Thông quan xong

**"+ Nhập tờ khai"** lần nữa, điền y hệt nhưng thêm **Ngày thông quan** =
**hôm nay** → **Lưu tờ khai** → tải lại trang.

**Phải thấy:** cảnh báo **"Tờ khai Luồng Đỏ" biến mất**. Thông quan xong thì
luồng chỉ còn là lịch sử, không còn là việc phải làm.

### 4.5 Bẻ luồng (tuỳ chọn)

Trên thẻ tờ khai bấm **"Đổi sang Luồng Vàng"** → hiện dòng lịch sử ghi thời điểm
và người đổi. Đây là quyết định có thể thêm ngày và tiền cho lô hàng nên phải
lưu vết.

### ✅ Kết thúc Bước 4

Tờ khai có số, luồng, thuế, hai mốc thời gian. Thuế **tự thành một dòng chi phí**
trong đối soát Bước 6 (mã `CUSTOMS_TAX`, dạng phát sinh ngoài báo giá — vì báo
giá là tiền cước dịch vụ, không bao giờ chứa thuế).

---

## BƯỚC 5 — Ảnh hiện trường · **Tài xế**

> Rủi ro gốc: *ảnh chụp ở bãi gửi qua Zalo, Zalo tự xoá ảnh gốc, đến lúc tranh
> chấp không còn bằng chứng container đã hạ hay chưa.*

**Khác mọi bước trên: bước này BẮT BUỘC có LLM vision.** Ảnh không có lớp văn
bản nào để regex bám vào. `VISION_PROVIDER=none` hoặc hết quota thì ảnh vẫn
được lưu, nhưng mọi ô đọc ra đều trống và `extraction_status` báo `skipped`.

### 5.1 Tài xế gửi ảnh

Đăng nhập **`taixe`** / `taixe@123` → sidebar **Ảnh hiện trường**

**Phải thấy:** đúng **một** mục — trang tải ảnh. Không có Containers, không có
Quotes, không có Emails.

Chọn một ảnh container hoặc phiếu EIR bất kỳ (ảnh chụp điện thoại là được).

**Phải thấy sau khi Agentify đọc xong:**

| Ô | Ý nghĩa |
|---|---|
| Loại ảnh | `container_photo` · `seal_photo` · `eir` · `pod` |
| Số container | đọc từ ảnh, kèm dấu **hợp lệ/không hợp lệ** theo checksum ISO 6346 |
| Số seal · Biển số xe · Depot | nếu ảnh có |
| Khớp container nào | lô đã có trong Agentify, hoặc "chưa có" |

> Ảnh được **lưu ngay khi tải lên**, trước cả khi vision đọc. Zalo tự xoá ảnh
> gốc, nên bản của Agentify là bản bền duy nhất — lưu trước, đọc sau, đọc sai
> cũng không mất ảnh.

### 5.2 Gắn ảnh vào lô hàng

Sửa lại số container thành `ONEU7041287` nếu đọc sai → bấm **Xác nhận gắn vào lô**.

> Đây cố ý là **hai thao tác tách rời**. Ảnh chụp ở bãi thường mờ, ngược sáng,
> số container bị che một nửa. Tự động gắn theo kết quả đọc nghĩa là một ảnh
> đọc nhầm sẽ chui vào hồ sơ lô khác — và không ai biết cho tới lúc tranh chấp.

### 5.3 Kiểm ảnh đã vào hồ sơ

Đăng xuất → đăng nhập **`ops`** → **Containers** → `ONEU7041287`

**Phải thấy:** mục **Ảnh hiện trường** có ảnh vừa gửi. Nếu vision đọc được số
seal, ô *Số seal* trên phiếu nhập liệu tờ khai (mục 3.4) hết đỏ.

### ⚠️ Lỗi đã biết ở bước này

Đăng nhập lại bằng **`taixe`** và thử xem lại ảnh vừa gửi: **không xem được**.

```
taixe  tải ảnh lên: qua  |  xem ảnh: 403
```

`field_image` cấp `create` cho `driver` nhưng **không cấp `view`**. Tài xế gửi
ảnh xong không kiểm được mình đã gửi chưa, gửi nhầm ảnh chưa. Trái với thiết kế
trong `CLAUDE.md` (*"driver: chỉ lệnh của mình + ảnh"*). Chưa sửa — cần chốt là
cho xem mọi ảnh hay chỉ ảnh do chính mình tải lên.

---

## BƯỚC 6 — Đối soát chi phí · **Kế toán**

> Rủi ro gốc: *phí hãng tàu thu thêm mà không ai đối chiếu với báo giá đã gửi
> khách → lô hàng lỗ mà tới lúc quyết toán mới biết.*

Đây là nơi báo giá `3103.00 USD` ở Bước 1 quay lại làm **mốc đối chiếu**.

### 6.1 Nạp giấy báo nợ của hãng tàu

Đăng nhập **`ketoan`** / `ketoan@123` → **Reconciliation** → nhập `ONEU7041287`

**Phải thấy:** báo giá `Q-2026-00xx` · `3103.00 USD`, và **chưa có giấy báo nợ nào**.

Ở mục **Nạp debit note**, nhập đúng 6 dòng sau — cố ý lệch so với báo giá để
kiểm cả bốn trạng thái so khớp:

| Mã phí | Số tiền | Sẽ ra trạng thái |
|---|---|---|
| `OF` | `2480.00` | khớp |
| `BAF` | `130.00` | khớp |
| `LSS` | `110.00` | **lệch** — hãng tàu thu thêm 22 |
| `THC` | `340.00` | khớp |
| `DOC` | `35.00` | khớp |
| `CLEANING` | `45.00` | **phát sinh** — không có trong báo giá |

**Cố ý KHÔNG nhập `TELEX`** (báo giá có `30.00`) để tạo trạng thái *thiếu*.

### 6.2 Chạy đối soát

Bấm **Chạy đối soát**.

**Phải thấy đủ bốn trạng thái:**

| Mã | Báo giá | Thực tế | Lệch | Trạng thái |
|---|---|---|---|---|
| `OF` `BAF` `THC` `DOC` | = | = | `0.00` | khớp |
| `LSS` | 88.00 | 110.00 | **+22.00** | lệch |
| `TELEX` | 30.00 | — | **−30.00** | thiếu chứng từ thực |
| `CLEANING` | — | 45.00 | **+45.00** | phát sinh ngoài báo giá |
| `CUSTOMS_TAX` | — | 42.150.000 | +42.150.000 | phát sinh ngoài báo giá |

> Vì sao `LSS` lệch 22 bị bắt còn chênh vài xu thì không: ngưỡng là
> `max(1.00, 1% số báo giá)`. Hãng tàu làm tròn khác nhau giữa báo giá và hoá
> đơn, bắt lỗi từng `$0.10` sẽ chôn mất những dòng đáng để ý.

> `CUSTOMS_TAX` tự xuất hiện từ tờ khai Bước 4, không phải gõ tay. Nó **luôn**
> là phát sinh, vì báo giá là tiền cước dịch vụ — không bao giờ chứa thuế.

### ⚠️ Lỗi đã biết: cộng lẫn USD với VND

Nhìn dòng **TỔNG**:

```
Tổng báo giá : 3103.00          (USD)
Tổng thực tế : 42153140.00      ← 3103 USD + 42.150.000 VND cộng thẳng
Lệch         : 42150037.00      → bật cờ "cần duyệt"
```

Bảng `reconciliations` **không có cột đơn vị tiền**, và hàm tính tổng cộng
thẳng các số thập phân. Con số tổng vì vậy không mang đơn vị nào có nghĩa, và
mọi lô có thuế đều bị đẩy sang trạng thái cần duyệt vì lệch hàng chục triệu.

Từng dòng riêng lẻ vẫn đúng — chỉ phần tổng là hỏng. Chưa sửa.

### 6.3 Duyệt và xuất ERP

Lệch vượt `max(100.00, 5% số báo giá)` thì phải có người duyệt, không phải kế
toán tự chốt. Bấm **Duyệt**, rồi **Xuất ERP** → tải file về.

**Phải thấy:** file có đủ các dòng phí kèm trạng thái so khớp.

### ✅ Kết thúc Bước 6

Chi phí thực đã đối chiếu với báo giá đã gửi khách, mỗi khoản lệch có tên và
con số, và hồ sơ xuất được sang phần mềm kế toán.

---

## PHỤ LỤC — Dán tin nhắn Zalo · **Ops / Docs**

> Rủi ro gốc: *thông tin quan trọng nhất của lô nằm trong group chat — số seal,
> biển số xe, giờ hạ bãi — và Zalo tự xoá ảnh sau một thời gian. Đến lúc tranh
> chấp thì không còn gì.*

**Agentify KHÔNG đọc Zalo tự động.** Làm vậy phải xin quyền truy cập hộp thoại
cá nhân — thứ sản phẩm này cố ý không đòi. Người dùng tự dán tin cần lưu, xem
máy đọc được gì, rồi mới quyết định ghi vào hồ sơ.

Vào **Data Sources** (`/setup`) → mục **Dán tin nhắn Zalo**. Chỉ `ops` và
`docs` thấy mục này.

Mỗi lần dán đều đi hai nhịp: **Xem trước** (không ghi gì) → **Lưu vào hồ sơ**.

### Z.1 Tin điều xe của lô đang test

| Ô | Điền |
|---|---|
| Nhóm chat / nguồn | `Group Điều xe Hai Phong` |
| Người gửi | `Ops - Nguyen Van A` |

Nội dung:

```
Xe đã lấy rỗng xong nhé anh.
Container: ONEU7041287
Seal: ONE1234567
Số xe: 15C-234.56
Depot: Nam Hai Dinh Vu
Hạ bãi lúc 14h chiều nay.
```

Bấm **Xem trước**. **Phải thấy:**

| | |
|---|---|
| Số container | `ONEU7041287` — nhãn **đã có trong Agentify** |
| Seal | `ONE1234567` |
| Depot lấy rỗng | `Nam Hai Dinh Vu` |

Bấm **Lưu vào hồ sơ** → mở **Containers** → `ONEU7041287` → bảng *Fact history*.

**Phải thấy:** `seal_no` và `empty_pickup_depot` có nguồn là **`Group Điều xe
Hai Phong`**, không phải email. Đây là điểm đáng quay nhất: một tin nhắn chat
giờ có provenance ngang hàng với chứng từ.

> Ô **Số seal** trên phiếu nhập liệu tờ khai (mục 3.4) hết đỏ sau bước này.

> `Số xe: 15C-234.56` **không** được đọc. Biển số chỉ bóc được từ ảnh, không
> có trong bộ đọc văn bản — đừng chờ nó xuất hiện.

### Z.2 Một tin nhắc hai container

Đây là phép kiểm tinh nhất của tính năng.

```
Sáng nay chạy 2 cont nhé:
ONEU7041287 - seal ONE1234567, xe 15C-234.56, hạ Nam Hai Dinh Vu
TCLU1234563 - seal TCL9876543, xe 15C-999.99, hạ Tan Vu
```

**Phải thấy ở Xem trước:** hai container, `ONEU7041287` **đã có**,
`TCLU1234563` **sẽ tạo mới**.

Lưu lại, rồi mở *Fact history* của **từng** container:

| Container | seal phải là |
|---|---|
| `ONEU7041287` | `ONE1234567` |
| `TCLU1234563` | `TCL9876543` |

**Seal không được lẫn sang nhau.** Hệ thống cắt tin nhắn thành từng cụm theo
dòng có số container, và mỗi container chỉ nhận thuộc tính rút ra từ cụm của
chính nó. Gán nhầm seal sang container khác là loại lỗi phải lần ngược từ cảng
mới phát hiện.

> **Lệch đã biết ở màn Xem trước:** với tin nhiều container, Xem trước chỉ hiện
> **một** seal (`ONE1234567`), trong khi lưu xuống thì cả hai đều đúng. Xem
> trước đang hiện bảng phẳng của cả đoạn, chưa tách theo container. Không phải
> dữ liệu sai — chỉ là màn xem trước nói ít hơn thực tế.

### Z.3 Tin không có số container

```
Anh ơi lô hàng đi Nhật tuần này chốt chưa? Khách giục rồi.
```

**Phải thấy:** không container nào, không trường nào đọc được.

Đây là hành vi đúng, không phải lỗi: fact không gắn được vào container nào thì
không có chỗ nào để lưu. Thà nói thẳng "không đọc được gì" còn hơn đoán bừa một
lô hàng.

### Z.4 Dán ảnh — chỉ chạy khi còn quota LLM

Khung dán nhận cả ảnh (chụp màn hình Zalo, ảnh POD/EIR). Ảnh không có lớp văn
bản nào để regex bám vào nên **bắt buộc có LLM vision**.

Kiểm nhanh còn quota hay không: dán một tin văn bản rồi bấm **Xem trước**, nhìn
nhãn *cách đọc*.

| Nhãn | Nghĩa |
|---|---|
| `hybrid` | LLM còn chạy — dán ảnh sẽ đọc được |
| `deterministic` + trạng thái `partial` | **LLM đã hết quota**, đang chạy bằng regex. Dán ảnh sẽ ra rỗng |

> Regex đủ cho toàn bộ Z.1–Z.3. Chỉ riêng ảnh là không thay thế được.

### ✅ Kết thúc phụ lục

Tin nhắn chat vào được hồ sơ lô hàng, giữ nguyên nguồn gốc, và người dùng vẫn
là người quyết định cái gì được ghi.

---

## Bảng đánh dấu

| # | Việc | Vai trò | Đạt? |
|---|---|---|---|
| 0.2 | Dọn sạch, hộp thư chỉ còn **1 thư** hỏi giá | — | ☐ |
| 1.2 | Tạo báo giá tự điền **8 ô** từ email | sales | ☐ |
| 1.3 | Thư hỏi cước có đủ 3 câu hỏi | sales | ☐ |
| 1.4 | Nạp 6 dòng phí, **tổng 3103.00** | sales | ☐ |
| 1.5 | Thư gửi khách có `(x2)` và tổng đúng | sales | ☐ |
| 2.1 | Đặt chỗ mở được khi **chưa có container** | ops | ☐ |
| 2.2 | Thư đặt chỗ là `firm booking` | ops | ☐ |
| 2.4 | Điền **11 ô** từ thư xác nhận, thấy đếm ngược | ops | ☐ |
| 3.2 | Cảnh báo **vênh số kiện**, không cảnh báo trọng lượng | docs | ☐ |
| 3.3 | Mỗi trường có nguồn gốc rõ | docs | ☐ |
| 3.4 | Phiếu **24/32 ô**, chỉ đọc, tải được .docx | docs | ☐ |
| 4.2 | Tờ khai tự điền **5 ô**, Luồng Đỏ + thuế `42150000` | ops | ☐ |
| 4.3 | Luồng Đỏ đẩy sớm cảnh báo free time | — | ☐ |
| 4.4 | Điền ngày thông quan → cảnh báo luồng tắt | ops | ☐ |
| 5.1 | `taixe` chỉ thấy trang Ảnh hiện trường | taixe | ☐ |
| 5.2 | Đọc số container, tự sửa rồi mới gắn vào lô | taixe | ☐ |
| 6.2 | Đối soát ra đủ **4 trạng thái** khớp/lệch/thiếu/phát sinh | ketoan | ☐ |
| 6.3 | Duyệt được và xuất được file ERP | ketoan | ☐ |
| Z.1 | Tin Zalo vào hồ sơ, nguồn ghi tên nhóm chat | ops | ☐ |
| Z.2 | Hai container **không lẫn seal của nhau** | ops | ☐ |
| Z.3 | Tin không có container → không đoán bừa | ops | ☐ |

## Kiểm phân quyền

| Đăng nhập | Thử | Kỳ vọng |
|---|---|---|
| `sales` | mở container | thấy Đặt chỗ, **không có nút** tạo/sửa; mục Hải quan **403** |
| `docs` | mở báo giá | sửa được báo giá, **không có** mục Trao đổi thư |
| `ketoan` | mở container | xem được Hải quan và Đối soát, **không thấy** mục Đặt chỗ |
| `taixe` | mở container | **403 — không mở được container**, kể cả để xem |

> Dòng `taixe` hay bị hiểu nhầm là "mở được nhưng ẩn bớt mục". Không phải:
> `driver` không nằm trong `container_facts:view` nên chặn ngay ở API. Tài xế
> chỉ có `field_image:create`.

Kiểm lớp thật, không chỉ ẩn nút:

```bash
T=$(curl -s -X POST http://127.0.0.1:8766/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"docs","password":"docs@123"}' \
  | ./.venv/bin/python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8766/api/v1/bookings \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"carrier":"X"}'
```

Phải ra **403**.

---

## Muốn chạy qua Gmail thật thay vì nạp sẵn

```bash
export GMAIL_APP_PASSWORD='<16 ký tự từ myaccount.google.com/apppasswords>'
./.venv/bin/python -m scripts.send_demo_emails --only roundtrip-rfq-hpn
```

Rồi vào `/setup` bằng `admin`, tạo sync job với query
`subject:AGENTIFY-DEMO newer_than:1d`.

Lưu ý: token OAuth ở chế độ Testing chỉ sống 7 ngày. Trang Setup báo đỏ *"Hết
hạn kết nối"* thì bấm **Kết nối lại**.

---

## Những chỗ chưa có, đừng mất công tìm

- **Agentify không gửi thư.** Quyền Gmail là chỉ-đọc; mọi nút "Soạn thư" chỉ
  dựng sẵn nội dung để bạn tự gửi.
- **Không nối vào ECUS/VNACCS.** Phiếu nhập liệu là để gõ tay sang.
- **Chưa có thực thể chứng từ.** Không ghi nhận được "đã nộp SI ngày X",
  "draft HBL bản 2", "telex release rồi".
- **Bước 5 chưa có lệnh điều xe.** Tài xế gửi được ảnh, nhưng không có thực thể
  "lệnh giao hàng của tôi" để gắn ảnh vào.
- **Giấy báo nợ phải gõ tay ở Bước 6.** Kịch bản này không có thư hoá đơn của
  hãng tàu, và chưa có đường bóc giấy báo nợ từ email.

Hai lỗi đã biết, sẽ gặp khi làm Bước 5 và 6 — không phải bạn thao tác sai:

- **Tài xế không xem được ảnh của chính mình** (`field_image` thiếu `view` cho
  `driver`).
- **Đối soát cộng lẫn USD với VND**, nên dòng TỔNG vô nghĩa khi lô có thuế hải
  quan. Từng dòng riêng lẻ vẫn đúng.
