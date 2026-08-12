# Gmail Body-Only Email Scenarios

Muc tieu cua file nay la tao bo email mau de gui den `nguyendinhtung20072000@gmail.com` nham test:

- Gmail connection da connect duoc chua
- Sync job co keo email moi ve duoc chua
- Subject va `body_text` co luu vao backend duoc chua
- Man hinh `/setup` va `email detail` co hien dung noi dung email duoc chua

## Luu y quan trong

Voi code hien tai, pipeline ingest dang uu tien trich xuat thong tin tu `PDF attachment`.

Neu ban chi gui email co `title + body text` ma khong co PDF:

- email van co the sync vao bang `emails`
- van co the xem duoc `subject`, `snippet`, `body_text`
- nhung co the chua tao duoc `container facts`
- vi vay search theo `container / booking / B/L / PO` co the chua ra ket qua

Noi cach khac, bo email nay phu hop de test `email sync` truoc, khong phai de xac nhan `container search` da hoat dong day du.

## Cach dung

Voi moi email ben duoi:

1. Gui email toi `nguyendinhtung20072000@gmail.com`
2. Co the gui tu Gmail khac hoac dung chinh mailbox khac trong ban
3. Sau khi gui xong, vao `/setup`
4. Tao `sync job` moi va chay sync
5. Kiem tra danh sach email va man hinh chi tiet email

## Ky vong toi thieu

Sau khi sync:

- thay email moi trong danh sach `emails`
- thay dung `from`, `subject`, `sent_at`
- thay `snippet`
- thay `body_text` tren man hinh chi tiet email

## 12 email mau de gui test

### 1. Booking request

Subject:
`Booking request for container TGHU9834210 / PO 45012891`

Body:

```text
Dear Agentify Team,

Please support booking for shipment under PO 45012891.

Container number: TGHU9834210
Booking request no: BKG-REQ-260610-01
Commodity: frozen pangasius fillet
POL: Cat Lai, Ho Chi Minh
POD: Singapore
Requested ETD: 2026-06-12

Please confirm vessel and voyage once booked.

Best regards,
Lan Nguyen
Export Coordinator
```

### 2. Booking confirmation follow-up

Subject:
`Booking confirmed for TGHU9834210 - booking BKG-SIN-77821`

Body:

```text
Hello team,

Booking has been confirmed.

Container: TGHU9834210
Booking no: BKG-SIN-77821
PO no: 45012891
Carrier: ONE
Vessel: ONE HANOI
Voyage: 022S
ETD: 2026-06-12
ETA: 2026-06-15

Please proceed with cargo cut-off arrangement.

Regards,
Booking Desk
```

### 3. Shipping instruction

Subject:
`Shipping instruction for B/L draft - TGHU9834210`

Body:

```text
Dear documentation team,

Please prepare draft B/L with below details:

Container no: TGHU9834210
Seal no: SEAL99871
Booking no: BKG-SIN-77821
Shipper: Minh Phat Seafood Co., Ltd.
Consignee: Lion City Foods Pte. Ltd.
POL: Cat Lai
POD: Singapore
Cargo: Frozen pangasius fillet

Kindly send draft back for checking today.

Best regards,
Lan Nguyen
```

### 4. Draft B/L approval

Subject:
`Approved draft BL OOLU260610998 for TGHU9834210`

Body:

```text
Hi team,

We have checked and approved the draft.

Container: TGHU9834210
Booking: BKG-SIN-77821
MBL: OOLU260610998
Seal: SEAL99871

Please issue final B/L accordingly.

Thanks,
Docs Team
```

### 5. Arrival notice style body

Subject:
`Arrival notice - FSCU6623418 ETA 2026-06-18`

Body:

```text
Dear consignee,

Your shipment is arriving as follows:

Container no: FSCU6623418
B/L no: EGLV2366102345
Booking no: BKG-HPH-99217
Vessel: EVER LUCENT
Voyage: 118W
ETA Hai Phong: 2026-06-18
Free time: 5 days

Please prepare import clearance documents in advance.

Regards,
Import Customer Service
```

### 6. Delivery order pickup notice

Subject:
`DO pickup instruction for FSCU6623418 / B/L EGLV2366102345`

Body:

```text
Dear customer,

Please arrange DO pick-up for below shipment:

Container: FSCU6623418
B/L no: EGLV2366102345
Arrival date: 2026-06-18
DO office: Hai Phong branch
DO release time: 08:30 - 17:00

Required items:
- original ID
- payment slip
- arrival notice copy

Best regards,
Import Desk
```

### 7. Invoice email

Subject:
`Invoice INV-260610-115 for container FSCU6623418`

Body:

```text
Dear accounting team,

Please find billing details below:

Invoice no: INV-260610-115
Container no: FSCU6623418
Booking no: BKG-HPH-99217
B/L no: EGLV2366102345
Charge item: local handling
Currency: USD
Amount: 125.00
VAT: 10%

Please settle before cargo release.

Regards,
Finance Desk
```

### 8. Container delay update

Subject:
`Delay update for TEMU5544332 - ETA revised`

Body:

```text
Dear all,

Please note the schedule change below:

Container no: TEMU5544332
Booking no: BKG-TSL-77110
B/L no: TSLHPH26061588
Original ETA: 2026-06-16
Revised ETA: 2026-06-19
Reason: port congestion at transshipment port

Please update customer accordingly.

Thanks,
Carrier CS
```

### 9. Empty pickup arrangement

Subject:
`Empty pickup plan for TCNU3141592 / booking BKG-USL-5512`

Body:

```text
Dear trucking team,

Please arrange empty pickup:

Container no: TCNU3141592
Booking no: BKG-USL-5512
Pickup depot: Tan Cang depot
Pickup date: 2026-06-11
Cargo: furniture
POL: Ho Chi Minh
POD: Los Angeles

Driver information will be shared separately.

Regards,
Ops Team
```

### 10. Customs document reminder

Subject:
`Need SI and customs data for container TCNU3141592`

Body:

```text
Hi docs team,

We are still missing shipping instruction and customs declaration details.

Container no: TCNU3141592
Booking no: BKG-USL-5512
PO no: PO-US-772901
Commodity: wooden furniture
Requested ETD: 2026-06-13

Please send final info before 15:00 today.

Thanks,
Operations
```

### 11. Multi-identifier customer inquiry

Subject:
`Customer asking status of MSCU7812456 / booking BKGMYC8821`

Body:

```text
Dear CS team,

Customer is asking for latest status.

Container no: MSCU7812456
Booking no: BKGMYC8821
B/L no: MAEU260619771
PO no: 45099112
Shipper: An Binh Garment
Consignee: Metro Fashion Malaysia
POL: Cat Lai
POD: Port Klang

Please revert ETA and customs readiness.

Best regards,
Sales Support
```

### 12. Final delivery confirmation

Subject:
`Delivered - container MSCU7812456 completed on 2026-06-20`

Body:

```text
Dear team,

Final delivery has been completed.

Container no: MSCU7812456
Booking no: BKGMYC8821
B/L no: MAEU260619771
Delivery date: 2026-06-20
Delivery point: Shah Alam DC
Receiver: Metro Fashion Malaysia

Please mark shipment as completed in your tracking sheet.

Regards,
Last Mile Team
```

## Goi y thu tu gui de test

Neu muon nhin ro tung nhom email lien quan den cung mot shipment, ban co the gui theo 3 cum:

- Cum 1: email `1 -> 4` cho `TGHU9834210`
- Cum 2: email `5 -> 8` cho `FSCU6623418` va `TEMU5544332`
- Cum 3: email `9 -> 12` cho `TCNU3141592` va `MSCU7812456`

## Goi y kiem tra sau khi sync

Sau khi chay sync job, kiem tra:

- email moi co vao danh sach `emails` khong
- `subject` co giong email goc khong
- `body_text` co day du khong
- `snippet` co hop ly khong
- `from_email` va `sent_at` co dung khong

Neu muon test tiep `container search`, buoc sau nen chuyen sang bo email co `PDF attachment` chua `container_no`, `booking_no`, `bl_no`, `ETA/ETD`.
