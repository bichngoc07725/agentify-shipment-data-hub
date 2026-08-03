import ipaddress
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from services import url_fetcher
from services.url_fetcher import UrlFetchError, fetch_file_from_url, find_first_url


class FindFirstUrlTest(unittest.TestCase):
    def test_finds_a_url_inside_surrounding_text(self) -> None:
        text = "Anh oi hoa don day nhe: https://vendor.example.com/invoice.pdf cam on anh"

        self.assertEqual(find_first_url(text), "https://vendor.example.com/invoice.pdf")

    def test_returns_none_when_there_is_no_link(self) -> None:
        self.assertIsNone(find_first_url("Container MSCU1234567 da ve cang"))


class ValidateUrlSsrfGuardTest(unittest.TestCase):
    """These use literal IPs so they need no DNS and exercise the real guard."""

    def test_rejects_non_http_scheme(self) -> None:
        with self.assertRaises(UrlFetchError):
            url_fetcher._validate_url("ftp://example.com/file.pdf")

    def test_rejects_a_url_with_no_hostname(self) -> None:
        with self.assertRaises(UrlFetchError):
            url_fetcher._validate_url("http:///file.pdf")

    def test_rejects_loopback_address(self) -> None:
        with self.assertRaises(UrlFetchError):
            url_fetcher._validate_url("http://127.0.0.1/file.pdf")

    def test_rejects_cloud_metadata_link_local_address(self) -> None:
        with self.assertRaises(UrlFetchError):
            url_fetcher._validate_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_private_rfc1918_address(self) -> None:
        with self.assertRaises(UrlFetchError):
            url_fetcher._validate_url("http://10.1.2.3/file.pdf")

    def test_accepts_a_public_address(self) -> None:
        url = "http://93.184.216.34/file.pdf"

        self.assertEqual(url_fetcher._validate_url(url), url)


def _fake_getaddrinfo(host, *_args, **_kwargs):
    # Literal IPs resolve to themselves (matches real getaddrinfo, so the
    # SSRF checks below still see the real address); hostnames resolve to a
    # fixed public IP so these tests need no real DNS.
    try:
        ipaddress.ip_address(host)
        resolved = host
    except ValueError:
        resolved = "93.184.216.34"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (resolved, 0))]


class _FakeHeaders:
    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = {k.lower(): v for k, v in headers.items()}

    def get(self, key: str, default=None):
        return self._headers.get(key.lower(), default)


class _FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        self._content = content
        self.headers = _FakeHeaders(headers)

    def read(self, n: int = -1) -> bytes:
        return self._content[:n] if n and n > 0 else self._content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> bool:
        return False


class FetchFileFromUrlTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch("services.url_fetcher.socket.getaddrinfo", side_effect=_fake_getaddrinfo)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_downloads_a_pdf_and_reports_its_mime_type(self) -> None:
        response = _FakeResponse(b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
        with patch.object(url_fetcher._opener, "open", return_value=response):
            fetched = fetch_file_from_url("https://vendor.example.com/invoice.pdf")

        self.assertEqual(fetched.mime_type, "application/pdf")
        self.assertEqual(fetched.content, b"%PDF-1.4 fake")
        self.assertEqual(fetched.filename, "invoice.pdf")

    def test_falls_back_to_the_url_extension_when_content_type_is_generic(self) -> None:
        response = _FakeResponse(b"\xff\xd8\xff fake jpeg", {"Content-Type": "application/octet-stream"})
        with patch.object(url_fetcher._opener, "open", return_value=response):
            fetched = fetch_file_from_url("https://vendor.example.com/photo.jpg")

        self.assertEqual(fetched.mime_type, "image/jpeg")

    def test_rejects_an_unsupported_content_type(self) -> None:
        response = _FakeResponse(b"<html>not a file</html>", {"Content-Type": "text/html"})
        with patch.object(url_fetcher._opener, "open", return_value=response):
            with self.assertRaises(UrlFetchError):
                fetch_file_from_url("https://vendor.example.com/page")

    def test_rejects_a_file_over_the_size_cap(self) -> None:
        oversized = b"x" * (url_fetcher.MAX_FETCH_BYTES + 1)
        response = _FakeResponse(oversized, {"Content-Type": "application/pdf"})
        with patch.object(url_fetcher._opener, "open", return_value=response):
            with self.assertRaises(UrlFetchError):
                fetch_file_from_url("https://vendor.example.com/huge.pdf")

    def test_uses_the_content_disposition_filename_when_present(self) -> None:
        response = _FakeResponse(
            b"fake",
            {
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="ToKhai.pdf"',
            },
        )
        with patch.object(url_fetcher._opener, "open", return_value=response):
            fetched = fetch_file_from_url("https://vendor.example.com/download?id=1")

        self.assertEqual(fetched.filename, "ToKhai.pdf")

    def test_follows_a_redirect_and_re_validates_the_new_host(self) -> None:
        redirect = HTTPError(
            "https://vendor.example.com/redirect",
            302,
            "Found",
            {"Location": "https://cdn.example.com/invoice.pdf"},
            None,
        )
        final_response = _FakeResponse(b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
        with patch.object(url_fetcher._opener, "open", side_effect=[redirect, final_response]):
            fetched = fetch_file_from_url("https://vendor.example.com/redirect")

        self.assertEqual(fetched.content, b"%PDF-1.4 fake")

    def test_a_redirect_to_a_private_address_is_rejected(self) -> None:
        # A malicious or compromised link must not be able to use a redirect
        # to reach an internal address after the first hop passes the guard.
        redirect = HTTPError(
            "https://vendor.example.com/redirect",
            302,
            "Found",
            {"Location": "http://169.254.169.254/latest/meta-data/"},
            None,
        )
        with patch.object(url_fetcher._opener, "open", side_effect=[redirect]):
            with self.assertRaises(UrlFetchError):
                fetch_file_from_url("https://vendor.example.com/redirect")

    def test_a_non_redirect_http_error_is_reported(self) -> None:
        not_found = HTTPError("https://vendor.example.com/missing.pdf", 404, "Not Found", {}, None)
        with patch.object(url_fetcher._opener, "open", side_effect=[not_found]):
            with self.assertRaises(UrlFetchError):
                fetch_file_from_url("https://vendor.example.com/missing.pdf")


if __name__ == "__main__":
    unittest.main()
