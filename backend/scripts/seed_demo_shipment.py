"""Dựng sẵn trọn một lô hàng để demo — một lệnh, không phải bấm gì.

    python -m scripts.seed_demo_shipment              # dọn cũ + nạp tới hết Bước 4
    python -m scripts.seed_demo_shipment --stage quote   # chỉ tới hết Bước 1
    python -m scripts.seed_demo_shipment --no-reset      # nạp thêm, giữ dữ liệu cũ

Khác `scripts.load_demo_thread` ở chỗ: script kia chỉ nạp THƯ rồi để người dùng
tự bấm qua từng bước. Script này nạp thư xong đi tiếp, tạo luôn báo giá, chỗ
đặt tàu và tờ khai — dùng khi cần mở máy ra là có sẵn một lô đầy đủ để chỉ cho
người khác xem, không phải ngồi thao tác lại từ đầu.

Mọi giá trị nằm trong `scripts/demo_data/*.json`, không rải trong code, để sửa
kịch bản demo không phải đụng vào Python.

Script đi qua đúng API công khai và đăng nhập đúng vai trò cho từng bước
(`sales` lập báo giá, `ops` đặt chỗ và khai hải quan), nên nếu ma trận phân
quyền hỏng thì seeder gãy — đó là chủ đích, một lô demo dựng bằng quyền admin
sẽ che mất lỗi RBAC.

KHÔNG cần LLM: thư đi qua bộ đọc regex, còn báo giá/booking/tờ khai là dữ liệu
soạn sẵn trong file JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._path import ensure_backend_root_on_path

ensure_backend_root_on_path(__file__)

from scripts.load_demo_thread import (  # noqa: E402
    discover,
    existing_subjects,
    read_meta,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT / "demo_email"
DATA_DIR = Path(__file__).resolve().parent / "demo_data"
DEFAULT_API = "http://127.0.0.1:8766"

# Mật khẩu demo, trùng với `plan/huong_dan_kiem_thu_buoc_1_4.md`.
PASSWORDS = {
    "sales": "sales@123",
    "ops": "ops@123",
    "docs": "docs@123",
    "admin": "admin@123",
}

# Các chặng, theo đúng thứ tự nghiệp vụ. Dừng ở chặng nào thì demo bắt đầu từ
# bước ngay sau đó — muốn diễn cảnh "Ops đặt chỗ" thì seed tới `quote` rồi tự
# bấm tiếp.
STAGES = ("emails", "quote", "booking", "customs")

# Đánh dấu trên báo giá để `--reset` biết cái nào của seeder mà xoá, không đụng
# vào báo giá người dùng tự tạo.
SEED_MARKER = "Nạp sẵn cho demo"


class ApiError(RuntimeError):
    pass


def request(
    api: str, path: str, payload: dict | None = None, token: str | None = None
) -> Any:
    req = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise ApiError(f"{exc.code} {path} — {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(
            f"Không gọi được API tại {api}: {exc}. Backend đã chạy chưa?"
        ) from exc


def login(api: str, role: str) -> str:
    return request(
        api, "/api/v1/auth/login", {"username": role, "password": PASSWORDS[role]}
    )["access_token"]


# Thứ tự xoá theo khoá ngoại: con trước, cha sau. Không đụng `users`,
# `gmail_connections`, `sync_jobs`, `audit_logs` — đó là cấu hình và nhật ký
# thao tác, không phải dữ liệu lô hàng.
WIPE_ORDER = (
    "reconciliation_lines",
    "reconciliations",
    "debit_note_charges",
    "debit_notes",
    "customs_channel_history",
    "customs_declarations",
    "bookings",
    "exception_actions",
    "container_facts",
    "attachments",
    "containers",
    "shipments",
    "quote_charges",
    "quotes",
    "emails",
)


async def wipe_all() -> None:
    """Xoá TOÀN BỘ dữ liệu lô hàng, không riêng lô demo.

    Dùng khi nhiều lần chạy thử đã chồng lên nhau: container của kịch bản này
    lẫn với kịch bản khác, báo giá mồ côi, cảnh báo của lô đã xoá. Lúc đó đọc
    màn hình không còn kết luận được gì, vì không biết con số đang thấy đến từ
    lần chạy nào.
    """
    from sqlalchemy import text

    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # Khoá ngoại tạo thành vòng: containers → shipments → quotes →
        # containers. Không có thứ tự xoá nào thoát được, nên gỡ hai liên kết
        # yếu (đều nullable) trước rồi mới xoá theo thứ tự thường.
        await session.execute(text("update quotes set container_id = null"))
        await session.execute(text("update containers set shipment_id = null"))

        removed: list[str] = []
        for table in WIPE_ORDER:
            result = await session.execute(text(f"delete from {table}"))
            if result.rowcount:
                removed.append(f"{table} {result.rowcount}")
        await session.commit()
    print("  đã xoá sạch: " + (", ".join(removed) if removed else "(vốn đã trống)"))


async def reset(container_no: str, subject_marker: str) -> None:
    """Xoá sạch lô cũ để chạy lại cho ra đúng một bản.

    Chỉ đụng vào lô demo: container theo số, thư theo dấu chủ đề, báo giá theo
    dấu trong ghi chú. Báo giá người dùng tự tạo không nằm trong diện xoá.
    """
    from sqlalchemy import text

    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        container_id = (
            await session.execute(
                text("select id from containers where container_no = :no"),
                {"no": container_no},
            )
        ).scalar()

        quote_ids = [
            row[0]
            for row in (
                await session.execute(
                    text("select id from quotes where note like :marker"),
                    {"marker": f"%{SEED_MARKER}%"},
                )
            ).all()
        ]

        if quote_ids:
            await session.execute(
                text("delete from bookings where quote_id = any(:ids)"), {"ids": quote_ids}
            )
            await session.execute(
                text("delete from quote_charges where quote_id = any(:ids)"),
                {"ids": quote_ids},
            )

        if container_id:
            await session.execute(
                text(
                    "delete from customs_channel_history where declaration_id in "
                    "(select id from customs_declarations where container_id = :c)"
                ),
                {"c": container_id},
            )
            for table in (
                "container_facts",
                "customs_declarations",
                "bookings",
                "exception_actions",
            ):
                await session.execute(
                    text(f"delete from {table} where container_id = :c"),
                    {"c": container_id},
                )
            await session.execute(
                text("update quotes set container_id = null where container_id = :c"),
                {"c": container_id},
            )
            await session.execute(
                text("delete from containers where id = :c"), {"c": container_id}
            )

        if quote_ids:
            await session.execute(
                text("delete from quotes where id = any(:ids)"), {"ids": quote_ids}
            )

        await session.execute(
            text("delete from emails where subject like :marker"),
            {"marker": f"%{subject_marker}%"},
        )
        await session.commit()

    print(f"  đã dọn lô {container_no}, thư '{subject_marker}', "
          f"{len(quote_ids)} báo giá do seeder tạo")


def delivery_timestamps(count: int, now: datetime | None = None) -> list[datetime]:
    """Dấu thời gian cho một đợt thư, tăng dần từng giây kể từ bây giờ.

    CỘNG TIẾN chứ không trừ lùi khỏi `now`: trừ lùi thì thư đầu của đợt sau rơi
    vào trước thư của đợt trước — Invoice hiện ra cũ hơn cả thư hỏi giá. Thứ tự
    này không chỉ để nhìn cho thuận: `container_facts` chọn giá trị mới nhất
    theo `source_sent_at`, mà Invoice và Packing List khai lệch nhau về số kiện.
    """
    base = now or datetime.now().astimezone()
    return [base + timedelta(seconds=index) for index in range(count)]


def build_date_shift(spec: dict, today: date | None = None) -> dict[str, str]:
    """Bảng đổi ngày cũ -> ngày mới, neo theo hôm nay.

    Corpus ghi ngày tuyệt đối, nên ba mốc cut-off và ETD/ETA cứ trôi dần vào
    quá khứ: đến đúng ngày cut-off thì băng đếm ngược hiện "ĐÃ QUÁ HẠN" và cả
    lô trông như đã rớt chuyến. Dời theo ngày thả thư thì khoảng cách giữa các
    mốc giữ nguyên, chỉ có gốc toạ độ chạy theo hôm nay.

    Ngày quá khứ (hoá đơn, ngày đăng ký tờ khai) KHÔNG dời: đọc "hoá đơn phát
    hành mấy hôm trước" vẫn tự nhiên, và số hoá đơn `INV-TL-260815` đã mã hoá
    sẵn ngày bên trong — dời ngày mà không dời số thì hai thứ đá nhau.
    """
    config = spec.get("date_shift")
    if not config:
        return {}

    anchor = date.fromisoformat(config["anchor"])
    new_anchor = (today or date.today()) + timedelta(days=config["anchor_days_from_today"])
    delta = new_anchor - anchor
    return {
        original: (date.fromisoformat(original) + delta).isoformat()
        for original in config["dates"]
    }


_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def apply_date_shift(text: str, shift: dict[str, str]) -> str:
    """Thay MỘT LƯỢT, không thay tuần tự.

    Thay tuần tự thì ngày vừa ghi ra lại trúng luật sau: `08-18 -> 08-20` rồi
    `08-20 -> 08-22` biến SI cut-off thành 22/08, đẩy nó ra sau cả gate-in. Thứ
    tự ba mốc chốt đảo lộn là hỏng đúng thứ Bước 2 cần thể hiện.
    """
    if not shift:
        return text
    return _ISO_DATE_RE.sub(lambda m: shift.get(m.group(0), m.group(0)), text)


def waves_upto(spec: dict, wave_name: str) -> list[dict]:
    """Các đợt thư tính tới `wave_name`, hoặc tất cả khi `all`."""
    waves = spec.get("email_waves") or []
    if wave_name == "all" or not waves:
        return waves
    names = [w["name"] for w in waves]
    if wave_name not in names:
        raise SystemExit(f"Không có đợt thư {wave_name!r}. Đang có: {', '.join(names)}")
    return waves[: names.index(wave_name) + 1]


def seed_emails(api: str, spec: dict, source_dir: Path, wave_name: str = "all") -> int:
    """Thả thư vào hộp thư theo ĐỢT, không đổ hết một lượt.

    Đổ hết cùng lúc thì ở Bước 2.1 — lúc còn đang soạn yêu cầu đặt chỗ — thư
    xác nhận của hãng tàu đã nằm sẵn trong hộp thư. Người kiểm thử không phân
    biệt được cái gì hệ thống suy ra và cái gì vốn đã có, và câu hỏi quan trọng
    nhất của Bước 2 ("ghi nhận được trạng thái đã hỏi mà chưa được trả lời
    không?") không kiểm được nữa.
    """
    token = login(api, "ops")
    already = existing_subjects(api, token)
    folders = discover(source_dir, spec["email_filter"])
    if not folders:
        raise SystemExit(
            f"Không thấy thư nào trong {source_dir} khớp {spec['email_filter']!r}"
        )

    shift = build_date_shift(spec)
    waves = waves_upto(spec, wave_name)
    if waves:
        wanted = tuple(part for wave in waves for part in wave["folders"])
        folders = [f for f in folders if any(part in f.name for part in wanted)]

    pending: list[tuple[Path, dict, str, str]] = []
    for folder in folders:
        meta = read_meta(folder)
        # Thư đi là thứ Agentify soạn cho người dùng tự gửi; nạp ngược vào hồ
        # sơ sẽ tạo ra dữ liệu mà ngoài đời không có.
        if meta.get("Direction") == "outbound":
            continue
        subject = (folder / "title.txt").read_text(encoding="utf-8").strip()
        if subject in already:
            continue
        body = (folder / "body.txt").read_text(encoding="utf-8")
        pending.append((folder, meta, apply_date_shift(subject, shift),
                        apply_date_shift(body, shift)))

    # Đóng dấu thời gian theo LÚC NHẬN, không theo ngày cứng trong `meta.txt`.
    #
    # Corpus ghi ngày tuyệt đối (03–07/08/2026), nên càng để lâu thư càng cũ
    # đi so với hôm nay. Kết quả: người dùng vừa bấm gửi thư đặt chỗ xong, thư
    # trả lời hiện ra "12 ngày trước" — câu trả lời có trước câu hỏi, đúng thứ
    # mà cơ chế thả theo đợt sinh ra để tránh.
    #
    # Giữ đúng THỨ TỰ trong một đợt bằng cách CỘNG TIẾN từng giây, không trừ
    # lùi khỏi `now`: trừ lùi thì thư đầu của đợt sau rơi vào trước thư của đợt
    # trước, và Invoice hiện ra cũ hơn cả thư hỏi giá. Thứ tự này không chỉ để
    # nhìn — `container_facts` chọn giá trị mới nhất theo `source_sent_at`, mà
    # Invoice và Packing List khai lệch nhau về số kiện.
    stamps = delivery_timestamps(len(pending))
    for (_folder, meta, subject, body), occurred_at in zip(pending, stamps):
        request(
            api,
            "/api/v1/manual-ingest",
            {
                "channel": "note",
                "content": f"{subject}\n{body}",
                "source_label": subject[:120],
                "sender": meta.get("From", ""),
                "occurred_at": occurred_at.isoformat(),
            },
            token,
        )
    return len(pending)


def _shift_values(payload: dict, shift: dict[str, str]) -> dict:
    """Dời ngày trong dữ liệu soạn sẵn y như dời ngày trong thân thư.

    Bỏ sót chỗ này thì chế độ demo đầy đủ (`--wipe` không kèm `--deliver`) dựng
    ra một chỗ đặt có cut-off đã quá hạn, trong khi thư lại ghi ngày tương lai —
    hai nguồn nói ngược nhau ngay trên cùng một màn hình.
    """
    return {
        key: apply_date_shift(value, shift) if isinstance(value, str) else value
        for key, value in payload.items()
    }


def seed_quote(api: str, spec: dict) -> dict:
    quote_spec = _shift_values(dict(spec["quote"]), build_date_shift(spec))
    role = quote_spec.pop("role")
    expected_total = quote_spec.pop("expected_total", None)
    token = login(api, role)

    quote = request(api, "/api/v1/quotes", quote_spec, token)

    if expected_total is not None:
        total = sum(
            Decimal(c["unit_price"]) * Decimal(c["quantity"])
            for c in quote_spec["charges"]
        )
        # Bảng phí là con số gửi cho khách. Seed ra một tổng sai thì cả buổi
        # demo đứng trên một báo giá sai, nên thà gãy ngay tại đây.
        if total != Decimal(expected_total):
            raise SystemExit(
                f"Tổng phí trong file JSON là {total}, kỳ vọng {expected_total}"
            )
    return quote


def seed_booking(api: str, spec: dict, quote_id: str | None) -> dict:
    booking_spec = _shift_values(dict(spec["booking"]), build_date_shift(spec))
    token = login(api, booking_spec.pop("role"))
    booking_spec["container_no"] = spec["container_no"]
    booking_spec["quote_id"] = quote_id
    return request(api, "/api/v1/bookings", booking_spec, token)


def seed_customs(api: str, spec: dict) -> dict:
    customs_spec = _shift_values(dict(spec["customs"]), build_date_shift(spec))
    token = login(api, customs_spec.pop("role"))
    customs_spec["container_no"] = spec["container_no"]
    return request(api, "/api/v1/customs/declarations", customs_spec, token)


def load_spec(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in DATA_DIR.glob("*.json"))) or "(trống)"
        raise SystemExit(f"Không có kịch bản {name!r}. Đang có: {available}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="roundtrip_rfq_hpn", help="tên file trong scripts/demo_data")
    parser.add_argument("--stage", choices=STAGES, default="customs",
                        help="dừng sau chặng này (mặc định: customs — đầy đủ Bước 1-4)")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--no-reset", dest="reset", action="store_false",
                        help="giữ dữ liệu cũ thay vì dọn trước khi nạp")
    parser.add_argument("--deliver", default="all",
                        help="chỉ thả thư tới đợt này: rfq | rate | booking | docs | customs | all")
    parser.add_argument("--wipe", action="store_true",
                        help="XOÁ SẠCH mọi dữ liệu lô hàng (tất cả container, báo giá, thư) "
                             "trước khi nạp — dùng khi nhiều lần chạy đã chồng lên nhau")
    parser.add_argument("--yes", action="store_true", help="không hỏi xác nhận khi --wipe")
    args = parser.parse_args()

    spec = load_spec(args.scenario)
    # `--deliver` là chế độ KIỂM THỬ TAY: chỉ thả thư, không dựng hộ báo giá /
    # chỗ đặt / tờ khai, vì đó chính là phần người dùng đang tự bấm.
    wanted = () if args.deliver != "all" else STAGES[: STAGES.index(args.stage) + 1]

    print(f"Kịch bản: {spec['title']}")

    if args.wipe:
        # Xoá hết là thao tác không lùi được, và nó cuốn theo cả thư Gmail đã
        # sync về lẫn container của kịch bản khác — hỏi trước.
        if not args.yes:
            try:
                answer = input(
                    "  XOÁ SẠCH mọi container, báo giá, chỗ đặt, tờ khai và thư "
                    "trong DB. Tài khoản và kết nối Gmail giữ nguyên.\n"
                    "  Gõ 'xoa' (hoặc 'y') để xác nhận: "
                )
            except (KeyboardInterrupt, EOFError):
                # Ctrl+C hoặc chạy không có bàn phím (CI, terminal của IDE tự
                # chèn lệnh activate venv vào đúng lúc đang chờ nhập). Thoát
                # gọn thay vì đổ traceback làm người dùng tưởng script hỏng.
                raise SystemExit("\n  Đã huỷ, không xoá gì. Muốn bỏ qua câu hỏi: thêm --yes.")
            if answer.strip().lower() not in {"xoa", "xoá", "y", "yes"}:
                raise SystemExit("  Đã huỷ, không xoá gì.")
        asyncio.run(wipe_all())
    elif args.deliver != "all":
        # Thả một đợt thư là thao tác GIỮA CHỪNG buổi kiểm thử: lúc đó chỗ đặt
        # ở 2.1 và báo giá ở Bước 1 đã do người dùng tự tạo. Dọn ở đây sẽ xoá
        # đúng phần việc họ vừa làm. Thư trùng đã được lọc theo tiêu đề nên nạp
        # thêm là an toàn.
        print("  (thả thêm thư, giữ nguyên dữ liệu đang có)")
    elif args.reset:
        asyncio.run(reset(spec["container_no"], spec["email_subject_marker"]))

    try:
        loaded = seed_emails(args.api, spec, args.source_dir, args.deliver)
        delivered = waves_upto(spec, args.deliver)
        print(f"  [thư]     nạp {loaded} thư đến"
              + (f" — đợt: {', '.join(w['name'] for w in delivered)}" if delivered else ""))
        if args.deliver != "all":
            remaining = [
                w for w in (spec.get("email_waves") or []) if w not in delivered
            ]
            for wave in remaining:
                print(f"            chưa tới: {wave['name']:8} ({wave['label']})"
                      f" — chạy --deliver {wave['name']} khi tới {wave['arrives_before']}")

        quote = None
        if "quote" in wanted:
            quote = seed_quote(args.api, spec)
            print(f"  [báo giá] {quote['quote_no']} · {len(spec['quote']['charges'])} dòng phí"
                  f" · tổng {spec['quote']['expected_total']} USD · {quote['status']}")

        if "booking" in wanted:
            booking = seed_booking(args.api, spec, quote["id"] if quote else None)
            print(f"  [đặt chỗ] {booking['booking_no']} · {booking['status']}"
                  f" · {booking['vessel']} {booking['voyage']}")

        if "customs" in wanted:
            declaration = seed_customs(args.api, spec)
            print(f"  [tờ khai] {declaration['declaration_no']} · luồng {declaration['channel']}"
                  f" · thuế {spec['customs']['tax_amount']} VND")
    except ApiError as exc:
        raise SystemExit(f"\nGãy ở API: {exc}") from exc

    if args.deliver == "all":
        print(
            f"\nXong tới chặng '{args.stage}'. Mở {spec['container_no']} ở trang Containers,"
            f" hoặc báo giá ở trang Quotes."
        )
    else:
        print("\nXong. Tải lại trang Emails để thấy thư mới.")


if __name__ == "__main__":
    main()
