"""Nạp một kịch bản email demo thẳng vào hệ thống, khỏi dán tay từng thư.

Dùng khi muốn thao tác tay trên giao diện nhưng không muốn ngồi copy-paste sáu
bảy cái email. Script đẩy từng thư qua đúng đường mà khung "dán tin nhắn" dùng
(`POST /api/v1/manual-ingest`), nên kết quả giống hệt như bạn tự dán — cùng
trích xuất, cùng fact, cùng provenance.

    python -m scripts.load_demo_thread --only roundtrip-rfq-hpn

Chỉ nạp thư ĐẾN. Thư đi là thứ Agentify soạn cho người dùng tự gửi, đưa ngược
vào hồ sơ sẽ tạo ra dữ liệu mà ngoài đời không có.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._path import ensure_backend_root_on_path

ensure_backend_root_on_path(__file__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT / "demo_email"
DEFAULT_API = "http://127.0.0.1:8766"
# Khung dán tin nhắn chỉ mở cho ops và docs; ops là vai trò đi suốt các bước.
DEFAULT_USER = "ops"
DEFAULT_PASSWORD = "ops@123"


def read_meta(folder: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in (folder / "meta.txt").read_text(encoding="utf-8").splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            meta[key.strip()] = value.strip()
    return meta


def sent_at_of(meta: dict[str, str]) -> str | None:
    """Ngày giờ thật của thư, từ `meta.txt` (`2026-08-03 08:30 +07`).

    Bỏ qua trường này thì `sent_at` rơi về thời điểm chạy script, và cả kịch
    bản — hỏi giá 03/08, xác nhận 05/08, hoá đơn 15/08, phân luồng 16/08 — bị
    nén vào vài mili giây của hôm nay. Hỏng hai chỗ: danh sách thư xếp theo
    thứ tự nạp thay vì thứ tự xảy ra, và `container_facts` chọn "giá trị mới
    nhất" theo `source_sent_at` nên khi hai chứng từ khai khác nhau thì bên
    thắng là ngẫu nhiên.
    """
    raw = meta.get("Sent At")
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M %z", "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(raw.replace("+07", "+0700"), fmt)
        except ValueError:
            continue
        return parsed.isoformat()
    return None


def _order_key(folder: Path) -> tuple:
    """Sắp theo SỐ thứ tự, không theo chữ.

    `sorted()` trên tên thư mục cho ra email_100 trước email_96 — thứ tự chuỗi.
    Corpus đánh số theo đúng trình tự nghiệp vụ, nên xếp sai số là nạp thư xác
    nhận đặt chỗ trước cả thư hỏi giá.
    """
    parts = folder.name.split("_", 2)
    return (int(parts[1]), folder.name) if len(parts) > 1 and parts[1].isdigit() else (
        10**9,
        folder.name,
    )


def discover(source_dir: Path, only: str | None) -> list[Path]:
    folders = []
    for child in source_dir.iterdir():
        if not child.is_dir() or not child.name.startswith("email_"):
            continue
        if only and only.lower() not in child.name.lower():
            continue
        if not (child / "body.txt").exists():
            continue
        folders.append(child)
    return sorted(folders, key=_order_key)


def post(api: str, path: str, payload: dict, token: str | None = None) -> dict:
    request = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read())


def get(api: str, path: str, token: str) -> dict:
    request = urllib.request.Request(
        f"{api}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def existing_subjects(api: str, token: str, pages: int = 3) -> set[str]:
    """Tiêu đề các thư đã có, để chạy lại script không nhân bản hồ sơ.

    Nạp hai lần thì mọi bước sau đều phải chọn giữa mấy thư giống hệt nhau, và
    fact bị ghi đè bởi chính nó — nhìn thì vẫn "chạy được" nhưng không còn phản
    ánh đúng cái gì đến từ đâu.
    """
    subjects: set[str] = set()
    for page in range(1, pages + 1):
        payload = get(api, f"/api/v1/emails?page={page}&page_size=100", token)
        items = payload.get("items", [])
        subjects.update(item["subject"] for item in items if item.get("subject"))
        if len(items) < 100:
            break
    return subjects


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default=None, help="Lọc theo tên thư mục, vd: roundtrip-rfq-hpn")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--username", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--include-outbound",
        action="store_true",
        help="Nạp cả thư đi (mặc định bỏ qua, vì đó là thư người dùng tự gửi)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Nạp lại cả thư đã có trong hệ thống (mặc định bỏ qua để khỏi nhân bản)",
    )
    args = parser.parse_args()

    folders = discover(args.source_dir, args.only)
    if not folders:
        raise SystemExit(
            f"Không thấy thư nào trong {args.source_dir}"
            + (f" khớp --only {args.only!r}" if args.only else "")
        )

    try:
        token = post(
            args.api,
            "/api/v1/auth/login",
            {"username": args.username, "password": args.password},
        )["access_token"]
    except urllib.error.URLError as exc:
        raise SystemExit(f"Không gọi được API tại {args.api}: {exc}") from exc

    already = set() if args.force else existing_subjects(args.api, token)

    loaded = skipped = duplicate = 0
    for folder in folders:
        meta = read_meta(folder)
        if meta.get("Direction") == "outbound" and not args.include_outbound:
            print(f"  BỎ QUA (thư đi) {folder.name}")
            skipped += 1
            continue

        subject = (folder / "title.txt").read_text(encoding="utf-8").strip()
        body = (folder / "body.txt").read_text(encoding="utf-8")
        if subject in already:
            print(f"  ĐÃ CÓ {folder.name} — bỏ qua (dùng --force để nạp lại)")
            duplicate += 1
            continue
        result = post(
            args.api,
            "/api/v1/manual-ingest",
            {
                "channel": "note",
                "content": f"{subject}\n{body}",
                "source_label": subject[:120],
                "sender": meta.get("From", ""),
                "occurred_at": sent_at_of(meta),
            },
            token,
        )
        containers = ", ".join(result["linked_containers"]) or "chưa có container"
        print(
            f"  NẠP {folder.name}\n"
            f"      {result['fact_count']} fact · {containers}"
        )
        loaded += 1

    print(
        f"\nXong: nạp {loaded} thư, bỏ qua {skipped} thư đi"
        + (f", {duplicate} thư đã có sẵn." if duplicate else ".")
    )


if __name__ == "__main__":
    main()
