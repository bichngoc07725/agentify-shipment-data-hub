"""Regex-first extraction of logistics fields from email and PDF text.

This runs before the LLM so the ingestion pipeline still produces usable
container profiles when no extraction provider is configured, and so exact-format
identifiers are read by a rule with known precision rather than by a model.

Container numbers are validated against the ISO 6346 check digit. Numbers that
fail the check are still returned — real documents contain typos — but with lower
confidence so downstream matching can rank them.
"""

from __future__ import annotations

import re
from datetime import date, datetime

# ISO 6346 letter values: A=10, then increasing, skipping every multiple of 11.
_ISO6346_LETTER_VALUES = {
    "A": 10, "B": 12, "C": 13, "D": 14, "E": 15, "F": 16, "G": 17, "H": 18,
    "I": 19, "J": 20, "K": 21, "L": 23, "M": 24, "N": 25, "O": 26, "P": 27,
    "Q": 28, "R": 29, "S": 30, "T": 31, "U": 32, "V": 34, "W": 35, "X": 36,
    "Y": 37, "Z": 38,
}

CONTAINER_PATTERN = re.compile(r"\b([A-Z]{4})[\s-]?(\d{7})\b")

CONFIDENCE_CHECKSUM_OK = 0.99
CONFIDENCE_CHECKSUM_BAD = 0.60

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Separator between a label and its value. `-` is deliberately excluded: it is
# part of identifiers far more often than it separates them, and treating it as
# a separator truncates values like `DO-2026-4471` to `2026-4471`.
# `[:.#]*` rather than `?` because forms like `PO #:` stack two punctuation marks.
_LABEL_SEP = r"(?:\s*(?:no|number|ref|s[oố])\.?)?\s*[:.#]*\s*"

# An identifier must contain at least one digit, which is what stops a label
# from swallowing the following prose ("Booking confirmation attached").
_ID_VALUE = r"((?=[A-Z0-9][A-Z0-9/-]*\d)[A-Z0-9][A-Z0-9/-]{3,})"
_SEAL_VALUE = r"((?=[A-Z0-9][A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,})"
# Customs declaration numbers are pure digits (e.g. 105476302040), unlike other
# identifiers which mix letters and digits.
_DECLARATION_VALUE = r"(\d{6,14})"


def _labelled(label: str, value: str = _ID_VALUE) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{label}){_LABEL_SEP}{value}", re.IGNORECASE)


# Label -> patterns. The capture group is always the value.
_IDENTIFIER_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "booking_no": [
        _labelled(r"booking|bkg"),
        _labelled(r"s[oố]\s*booking"),
    ],
    "bl_no": [
        _labelled(r"m?b/?l|bill\s+of\s+lading|master\s+bl"),
        _labelled(r"v[aậ]n\s+đơn"),
    ],
    "po_no": [_labelled(r"p\.?o\.?|purchase\s+order")],
    "do_no": [
        _labelled(r"d/?o|delivery\s+order"),
        _labelled(r"l[eệ]nh\s+giao\s+h[aà]ng"),
    ],
    "seal_no": [_labelled(r"seal|ni[eê]m\s*phong", _SEAL_VALUE)],
    "invoice_no": [_labelled(r"invoice|inv")],
    # Anchored on the full label, not bare "tờ khai" — that phrase appears
    # constantly in the document's own title/prose ("TỜ KHAI HÀNG HÓA...").
    "declaration_no": [
        _labelled(r"s[oố]\s*t[oờ]\s*khai", _DECLARATION_VALUE),
        _labelled(r"declaration\s*(?:no|number)?", _DECLARATION_VALUE),
    ],
}

_DATE_LABELS: dict[str, str] = {
    "eta": r"eta|estimated\s+time\s+of\s+arrival|ng[aà]y\s+d[uự]\s+ki[eế]n\s+đ[eế]n",
    "etd": r"etd|estimated\s+time\s+of\s+departure|ng[aà]y\s+d[uự]\s+ki[eế]n\s+đi",
    "ata": r"ata|actual\s+time\s+of\s+arrival|arrived\s+on|ng[aà]y\s+t[aà]u\s+c[aậ]p",
}

_DATE_VALUE = (
    r"(\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
    r"|\d{1,2}[\s-][A-Z]{3}[a-z]*[\s-]\d{4}"
    r"|[A-Z]{3}[a-z]*\s+\d{1,2},?\s+\d{4})"
)

_FREE_TIME_PATTERNS = [
    re.compile(
        r"\bfree\s*time\b[^\n\d]{0,40}?(\d{1,2})\s*(?:day|days|ng[aà]y)", re.IGNORECASE
    ),
    re.compile(
        r"(\d{1,2})\s*(?:day|days|ng[aà]y)[^\n]{0,20}?\bfree\s*time\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(?:mi[eễ]n\s+ph[ií]\s+l[uư]u\s+(?:container|b[aã]i))[^\n\d]{0,30}?"
        r"(\d{1,2})\s*ng[aà]y",
        re.IGNORECASE,
    ),
]

# Carriers usually print vessel and voyage on one line, e.g.
# "Vessel / Voyage: MSC ANNA / 235W". Matching that as a unit avoids reading the
# vessel name as the voyage number.
_VESSEL_VOYAGE_PATTERN = re.compile(
    r"\b(?:vessel|ship|t[aà]u)\s*[/&]\s*(?:voyage|voy|chuy[eế]n)\s*[:.#-]\s*"
    r"([^\n,;|/]{2,40}?)\s*/\s*([A-Z0-9][A-Z0-9-]{0,15})\b",
    re.IGNORECASE,
)
_VESSEL_PATTERNS = [
    re.compile(
        r"\b(?:vessel|ship|t[aà]u)(?:\s*name)?\s*[:.#-]\s*([^\n,;|]{2,60})",
        re.IGNORECASE,
    ),
]
_VOYAGE_PATTERNS = [
    re.compile(
        r"\b(?:voyage|voy|chuy[eế]n)(?:\s*(?:no|number))?\s*[:.#-]\s*"
        r"([A-Z0-9][A-Z0-9-]{0,15})",
        re.IGNORECASE,
    ),
]
_PORT_PATTERNS = {
    "pol": [
        re.compile(
            r"\b(?:pol|port\s+of\s+loading|c[aả]ng\s+x[eế]p)\s*[:.#-]\s*([^\n,;|]{2,60})",
            re.IGNORECASE,
        )
    ],
    "pod": [
        re.compile(
            r"\b(?:pod|port\s+of\s+discharge|c[aả]ng\s+d[oỡ])\s*[:.#-]\s*([^\n,;|]{2,60})",
            re.IGNORECASE,
        )
    ],
}

# Ordered: the first keyword that matches wins, so put the specific ones first.
_DOC_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "customs_declaration",
        (
            "customs declaration",
            "tờ khai hải quan",
            "tờ khai hàng hóa",
            # ASCII fallback: some systems/scans strip Vietnamese diacritics.
            "to khai hai quan",
            "to khai hang hoa",
        ),
    ),
    ("arrival_notice", ("arrival notice", "notice of arrival", "thông báo hàng đến")),
    (
        "booking_confirmation",
        ("booking confirmation", "booking confirmed", "booking note", "xác nhận booking"),
    ),
    ("delivery_order", ("delivery order", "lệnh giao hàng")),
    ("debit_note", ("debit note", "credit note", "giấy báo nợ", "giấy báo có")),
    ("certificate_of_origin", ("certificate of origin", "giấy chứng nhận xuất xứ")),
    ("packing_list", ("packing list", "phiếu đóng gói")),
    ("bill_of_lading", ("bill of lading", "draft b/l", "draft bl", "vận đơn")),
    ("invoice", ("commercial invoice", "invoice", "hóa đơn")),
]


def iso6346_check_digit(container_no: str) -> int | None:
    """Return the expected ISO 6346 check digit, or None if the input is malformed."""
    body = container_no[:10].upper()
    if len(body) != 10 or not body[:4].isalpha() or not body[4:].isdigit():
        return None

    total = 0
    for index, char in enumerate(body):
        value = (
            _ISO6346_LETTER_VALUES.get(char)
            if char.isalpha()
            else int(char)
        )
        if value is None:
            return None
        total += value * (2**index)
    return total % 11 % 10


def is_valid_container_no(container_no: str) -> bool:
    normalized = normalize_container_no(container_no)
    if len(normalized) != 11 or not normalized[10:].isdigit():
        return False
    expected = iso6346_check_digit(normalized)
    return expected is not None and expected == int(normalized[10])


def normalize_container_no(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper().strip()


def find_container_numbers(text: str) -> list[tuple[str, float]]:
    """Return `(container_no, confidence)` in document order, deduplicated.

    Checksum-valid numbers are returned before invalid ones so that callers
    picking a single default container prefer the trustworthy one.
    """
    seen: set[str] = set()
    valid: list[tuple[str, float]] = []
    invalid: list[tuple[str, float]] = []

    for match in CONTAINER_PATTERN.finditer(text.upper()):
        container_no = f"{match.group(1)}{match.group(2)}"
        if container_no in seen:
            continue
        seen.add(container_no)
        if is_valid_container_no(container_no):
            valid.append((container_no, CONFIDENCE_CHECKSUM_OK))
        else:
            invalid.append((container_no, CONFIDENCE_CHECKSUM_BAD))

    return valid + invalid


def parse_date(value: str) -> date | None:
    raw = value.strip().replace(",", "")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    match = re.fullmatch(r"(\d{1,2})[\s-]([A-Za-z]{3})[a-z]*[\s-](\d{4})", raw)
    if match:
        month = _MONTHS.get(match.group(2).upper())
        if month:
            return _safe_date(int(match.group(3)), month, int(match.group(1)))

    match = re.fullmatch(r"([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s+(\d{4})", raw)
    if match:
        month = _MONTHS.get(match.group(1).upper())
        if month:
            return _safe_date(int(match.group(3)), month, int(match.group(2)))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _first_match(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip().rstrip(".,;:")
            if value:
                return value
    return None


def find_dates(text: str) -> dict[str, str]:
    """Return `{field: ISO date}` for ETA/ETD/ATA labels found in the text."""
    found: dict[str, str] = {}
    for field, label in _DATE_LABELS.items():
        pattern = re.compile(
            rf"\b(?:{label})\b\s*[:.#-]?\s*{_DATE_VALUE}", re.IGNORECASE
        )
        match = pattern.search(text)
        if not match:
            continue
        parsed = parse_date(match.group(1))
        if parsed:
            found[field] = parsed.isoformat()
    return found


def find_vessel_voyage(text: str) -> tuple[str | None, str | None]:
    """Return `(vessel, voyage)`, preferring the combined one-line form."""
    combined = _VESSEL_VOYAGE_PATTERN.search(text)
    if combined:
        return combined.group(1).strip(), combined.group(2).strip().upper()

    vessel = _first_match(text, _VESSEL_PATTERNS)
    voyage = _first_match(text, _VOYAGE_PATTERNS)
    return vessel, voyage.upper() if voyage else None


def find_free_time_days(text: str) -> int | None:
    for pattern in _FREE_TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            days = int(match.group(1))
            if 0 < days <= 60:
                return days
    return None


def classify_document(subject: str, text: str) -> tuple[str, float]:
    """Classify by keyword. Subject matches are more reliable than body matches."""
    subject_lower = subject.lower()
    for doc_type, keywords in _DOC_TYPE_KEYWORDS:
        if any(keyword in subject_lower for keyword in keywords):
            return doc_type, 0.85

    head = text[:4000].lower()
    for doc_type, keywords in _DOC_TYPE_KEYWORDS:
        if any(keyword in head for keyword in keywords):
            return doc_type, 0.65

    return "other", 0.0


def extract_deterministic(subject: str, sender: str, text: str) -> dict:
    """Build a partial ExtractedRecord payload using rules only."""
    content = "\n".join(part for part in (subject, text) if part)
    doc_type, doc_type_confidence = classify_document(subject or "", text or "")

    containers = find_container_numbers(content)
    identifiers: dict[str, object] = {
        "container_no": [container_no for container_no, _ in containers],
        "seal_no": [],
    }
    for field, patterns in _IDENTIFIER_PATTERNS.items():
        value = _first_match(content, patterns)
        if not value:
            continue
        if field == "seal_no":
            identifiers["seal_no"] = [value.upper()]
        else:
            identifiers[field] = value.upper()

    route: dict[str, object] = {}
    vessel, voyage = find_vessel_voyage(content)
    if vessel:
        route["vessel"] = vessel
    if voyage:
        route["voyage"] = voyage
    for field, patterns in _PORT_PATTERNS.items():
        port = _first_match(content, patterns)
        if port:
            route[field] = port
    route.update(find_dates(content))

    payload: dict[str, object] = {
        "doc_type": doc_type,
        "doc_type_confidence": doc_type_confidence,
        "identifiers": identifiers,
        "route": route,
        "container_confidences": {
            container_no: confidence for container_no, confidence in containers
        },
    }

    free_time_days = find_free_time_days(content)
    if free_time_days is not None:
        payload["free_time_days"] = free_time_days

    return payload
