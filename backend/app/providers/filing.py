"""Download a user-supplied earnings filing PDF (NSE/BSE/company IR) and extract its text."""

import asyncio
import io
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

MAX_PDF_BYTES = 20 * 1024 * 1024
FILING_MAX_CHARS = 30_000  # same budget as SEC earnings releases


class FilingError(ValueError):
    """The URL can't be used; the message is safe to show the user."""


async def _check_public_https(url: str) -> None:
    """Only fetch public HTTPS hosts, so a pasted URL can't reach internal services."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise FilingError("Use an https:// link to the PDF")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise FilingError(f"Can't resolve {parsed.hostname}") from e
    # shortcut: the host is resolved again on connect (DNS rebinding); pin the IP if this ever serves untrusted users
    if not all(ipaddress.ip_address(info[4][0]).is_global for info in infos):
        raise FilingError("That host is not a public address")


async def fetch_filing_text(url: str) -> str:
    """Text of the PDF at `url`, capped at FILING_MAX_CHARS. Raises FilingError."""
    body = bytearray()
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "Quantara/1.0"}) as client:
        for _ in range(4):  # follow a few redirects, re-checking every hop
            await _check_public_https(url)
            try:
                async with client.stream("GET", url) as resp:
                    if resp.is_redirect:
                        url = str(resp.next_request.url) if resp.next_request else ""
                        continue
                    if resp.status_code != 200:
                        raise FilingError(f"The server returned HTTP {resp.status_code}")
                    async for part in resp.aiter_bytes():
                        body += part
                        if len(body) > MAX_PDF_BYTES:
                            raise FilingError("The PDF is larger than 20 MB")
                    break
            except httpx.HTTPError as e:
                raise FilingError(f"Download failed: {e}") from e
        else:
            raise FilingError("Too many redirects")

    if not body.startswith(b"%PDF"):
        raise FilingError("That link is not a PDF")
    try:
        text = await asyncio.to_thread(_pdf_text, bytes(body))
    except Exception as e:
        raise FilingError("Couldn't read that PDF") from e
    if len(text) < 500:
        raise FilingError("The PDF has almost no text (it may be a scanned image)")
    return text


def _pdf_text(data: bytes) -> str:
    text = ""
    for page in PdfReader(io.BytesIO(data)).pages:
        text += (page.extract_text() or "") + "\n"
        if len(text) >= FILING_MAX_CHARS:
            break
    return " ".join(text.split())[:FILING_MAX_CHARS]
