"""Fetch a file (PDF or image) from a link a user pasted, e.g. a vendor
sharing an invoice URL in a Zalo chat.

This downloads content from a URL a user typed into a chat message — a
different trust level than a Gmail attachment or a file the user picked
themselves. It is hardened against SSRF: only public http(s) hosts are
allowed, every redirect hop is re-validated (not just the first request), and
size/time are capped so a hostile or broken link cannot be used to reach
internal services or exhaust the server.

Known gap: hostnames are validated by resolving them once before connecting.
A DNS-rebinding attacker (resolve public at check time, private at connect
time) could still slip through, since `urlopen` re-resolves the hostname
itself. Full protection needs connecting to a pinned IP while keeping the
original Host/SNI, which is a meaningfully bigger change — acceptable for now
given this is an internal ops tool, not a public-facing endpoint.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_FETCH_BYTES = 10 * 1024 * 1024  # stays well under the 14MB base64 cap used for pasted images
FETCH_TIMEOUT_SECONDS = 15
MAX_REDIRECTS = 5

_ALLOWED_CONTENT_TYPES = {
    "application/pdf": "application/pdf",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}

_EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_REDIRECT_CODES = (301, 302, 303, 307, 308)

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


class UrlFetchError(Exception):
    """The link could not be fetched or is not a supported file type."""


def find_first_url(text: str) -> str | None:
    match = URL_PATTERN.search(text or "")
    return match.group(0) if match else None


@dataclass
class FetchedFile:
    content: bytes
    mime_type: str
    filename: str


class _NoRedirect(HTTPRedirectHandler):
    # Returning None makes urlopen raise HTTPError for the redirect status
    # instead of silently following it, so each hop can be re-validated.
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N803
        return None


_opener = build_opener(_NoRedirect)


def _guess_content_type_from_path(path: str) -> str | None:
    lowered = path.lower()
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return None


def _assert_public_host(hostname: str) -> None:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UrlFetchError(f"Không phân giải được địa chỉ: {hostname}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UrlFetchError(f"Link trỏ tới địa chỉ nội bộ, không được phép: {hostname}")


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlFetchError("Chỉ hỗ trợ link http/https")
    if not parsed.hostname:
        raise UrlFetchError("Link không hợp lệ")
    _assert_public_host(parsed.hostname)
    return url


def _filename_from(headers, url: str, mime_type: str) -> str:
    disposition = headers.get("Content-Disposition") or ""
    match = re.search(r'filename="?([^";]+)"?', disposition)
    if match:
        return match.group(1).strip()
    path_name = urlparse(url).path.rsplit("/", 1)[-1]
    if path_name and "." in path_name:
        return path_name
    return f"linked-file{_EXTENSION_BY_MIME.get(mime_type, '')}"


def fetch_file_from_url(url: str) -> FetchedFile:
    """Download a PDF/image from `url` for the extraction pipeline to read.

    Raises `UrlFetchError` for anything that isn't a clean, supported-type
    download — callers are expected to degrade to text-only extraction rather
    than fail the whole ingest over a bad or unsupported link.
    """
    current_url = _validate_url(url)

    for _ in range(MAX_REDIRECTS + 1):
        request = Request(current_url, headers={"User-Agent": "Agentify-LinkFetcher/1.0"})
        try:
            with _opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                content_type = (
                    (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                )
                mime_type = _ALLOWED_CONTENT_TYPES.get(
                    content_type
                ) or _guess_content_type_from_path(urlparse(current_url).path)
                if mime_type is None:
                    raise UrlFetchError(
                        "Định dạng file không hỗ trợ "
                        f"(Content-Type: {content_type or 'không xác định'}). "
                        "Chỉ hỗ trợ PDF hoặc ảnh."
                    )

                raw = response.read(MAX_FETCH_BYTES + 1)
                if len(raw) > MAX_FETCH_BYTES:
                    raise UrlFetchError("File vượt quá giới hạn 10MB")

                filename = _filename_from(response.headers, current_url, mime_type)
                return FetchedFile(content=raw, mime_type=mime_type, filename=filename)
        except HTTPError as exc:
            if exc.code in _REDIRECT_CODES:
                location = exc.headers.get("Location") if exc.headers else None
                if not location:
                    raise UrlFetchError("Link chuyển hướng nhưng không có địa chỉ đích") from exc
                current_url = _validate_url(location)
                continue
            raise UrlFetchError(f"Không tải được file (HTTP {exc.code})") from exc
        except URLError as exc:
            raise UrlFetchError(f"Không tải được file: {exc.reason}") from exc
        except TimeoutError as exc:
            raise UrlFetchError("Hết thời gian chờ tải file") from exc

    raise UrlFetchError("Link chuyển hướng quá nhiều lần")
