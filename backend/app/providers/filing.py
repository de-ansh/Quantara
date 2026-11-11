"""Text of an earnings filing (NSE/BSE/company IR): a PDF, a call recording, or a page linking either.

Many Indian companies post the earnings call as an MP3 before (or instead of) a PDF transcript,
so audio is transcribed with OpenAI speech-to-text.
"""

import asyncio
import io
import ipaddress
import re
import socket
from pathlib import PurePosixPath
from urllib.parse import quote, urljoin, urlparse

import httpx
from openai import AsyncOpenAI, OpenAIError
from pypdf import PdfReader

from app.core.config import settings

# OpenAI's per-file transcription limit. shortcut: longer or high-bitrate recordings are refused, not split; split with ffmpeg if that becomes common
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
FILING_MAX_CHARS = 30_000  # same budget as SEC earnings releases
TRANSCRIBE_MODEL = "whisper-1"  # handles a full hour-long call; gpt-4o-transcribe caps output length
# Spellings Whisper otherwise garbles on Indian earnings calls ("F by 27" for FY27)
TRANSCRIBE_HINT = "Indian company earnings call: FY26, FY27, Q1, Q2, H1, EBITDA, PAT, crore, lakh, YoY, QoQ, CAGR."
AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".mp4", ".mpeg", ".mpga", ".webm"}
_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
_CALL_WORDS = re.compile(r"transcript|concall|call|audio|recording", re.I)


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


async def _download(url: str) -> tuple[bytes, str, str]:
    """Body, content type and final URL, re-checking every redirect hop."""
    body = bytearray()
    content_type = ""
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
                    content_type = resp.headers.get("content-type", "").lower()
                    async for part in resp.aiter_bytes():
                        body += part
                        if len(body) > MAX_DOWNLOAD_BYTES:
                            raise FilingError("The file is larger than 25 MB")
                    break
            except httpx.HTTPError as e:
                raise FilingError(f"Download failed: {e}") from e
        else:
            raise FilingError("Too many redirects")
    return bytes(body), content_type, url


def newest_call_link(html: str, page_url: str) -> str | None:
    """First transcript PDF or call recording on a company page; IR pages list the newest first."""
    for href in _LINK.findall(html):
        absolute = urljoin(page_url, href.strip())
        path = urlparse(absolute).path
        suffix = PurePosixPath(path).suffix.lower()
        if (suffix == ".pdf" or suffix in AUDIO_SUFFIXES) and _CALL_WORDS.search(path):
            return quote(absolute, safe=":/?#[]@!$&'()*+,;=%~")  # file names often contain spaces
    return None


async def _transcribe(audio: bytes, filename: str) -> str:
    try:
        result = await AsyncOpenAI(api_key=settings.openai_api_key).audio.transcriptions.create(
            model=TRANSCRIBE_MODEL, file=(filename, audio), prompt=TRANSCRIBE_HINT
        )
    except OpenAIError as e:
        raise FilingError("Couldn't transcribe that recording") from e
    return result.text


async def fetch_filing_text(url: str, follow_page: bool = True) -> str:
    """Text of the PDF, recording or linked call at `url`, capped at FILING_MAX_CHARS. Raises FilingError."""
    body, content_type, final_url = await _download(url)
    suffix = PurePosixPath(urlparse(final_url).path).suffix.lower()

    if not body.startswith(b"%PDF"):
        if content_type.startswith("audio/") or suffix in AUDIO_SUFFIXES:
            text = " ".join((await _transcribe(body, PurePosixPath(urlparse(final_url).path).name or "call.mp3")).split())
            if len(text) < 500:
                raise FilingError("The recording has almost no speech")
            return text[:FILING_MAX_CHARS]
        if "html" in content_type or body.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
            link = newest_call_link(body.decode("utf-8", "replace"), final_url) if follow_page else None
            if link is None:
                raise FilingError("That page has no transcript PDF or call recording")
            return await fetch_filing_text(link, follow_page=False)
        raise FilingError("That link is not a PDF or a call recording")
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
