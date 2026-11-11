"""User-linked earnings filing PDFs (NSE/BSE/company IR) as research context."""

import httpx
import pytest
from httpx import AsyncClient

from app.models.stock import Stock
from app.providers import filing
from app.providers.filing import FilingError, fetch_filing_text
from app.providers.transcript import TranscriptProvider

SENTENCE = "Revenue grew 12 percent on strong digital demand and margins expanded. "


def _pdf(text: str) -> bytes:
    """A minimal one-page PDF whose text layer is `text`."""
    content = f"BT /F1 10 Tf 20 700 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


@pytest.fixture
def serve(monkeypatch):
    """Serve `routes[url] = httpx.Response` and treat every host as public."""
    routes: dict[str, httpx.Response] = {}

    async def handle(self, request: httpx.Request) -> httpx.Response:
        resp = routes.get(str(request.url), httpx.Response(404))
        return httpx.Response(resp.status_code, headers=resp.headers, content=resp.content, request=request)

    async def public(url: str) -> None:
        if not url.startswith("https://"):
            raise FilingError("Use an https:// link to the PDF")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    monkeypatch.setattr(filing, "_check_public_https", public)
    return routes


@pytest.mark.asyncio
async def test_fetch_filing_text_follows_redirect_and_extracts(serve):
    serve["https://ir.example.com/q2"] = httpx.Response(
        302, headers={"Location": "https://nsearchives.example.com/q2.pdf"}
    )
    serve["https://nsearchives.example.com/q2.pdf"] = httpx.Response(200, content=_pdf(SENTENCE * 10))

    text = await fetch_filing_text("https://ir.example.com/q2")
    assert "strong digital demand" in text


@pytest.mark.asyncio
async def test_fetch_filing_text_rejects_bad_input(serve):
    serve["https://x.example.com/page"] = httpx.Response(200, content=b"<html>not a pdf</html>")
    serve["https://x.example.com/tiny.pdf"] = httpx.Response(200, content=_pdf("Cover page"))
    serve["https://x.example.com/gone.pdf"] = httpx.Response(403)

    for url, message in [
        ("https://x.example.com/page", "no transcript PDF or call recording"),
        ("https://x.example.com/tiny.pdf", "almost no text"),
        ("https://x.example.com/gone.pdf", "HTTP 403"),
    ]:
        with pytest.raises(FilingError, match=message):
            await fetch_filing_text(url)


BLS_PAGE = """<html><body>
<a href="/assets/pdf/BLS-Sustainability-Report.pdf">Sustainability</a>
<a href="/assets/pdf/transcript/Audio-Recording-of-Earnings Call Audio_Q2FY27.mp3">Q2 audio</a>
<a href="/assets/pdf/transcript/Transcript of Earnings call held on August 11 2026.pdf">Q1 transcript</a>
</body></html>"""


@pytest.mark.asyncio
async def test_company_page_resolves_to_its_newest_recording_and_transcribes_it(serve, monkeypatch):
    heard: list[str] = []

    async def transcribe(audio: bytes, filename: str) -> str:
        heard.append(filename)
        assert audio == b"ID3fake-mp3"
        return SENTENCE * 10

    monkeypatch.setattr(filing, "_transcribe", transcribe)
    serve["https://www.bls.example.com/transcript"] = httpx.Response(
        200, headers={"content-type": "text/html"}, content=BLS_PAGE.encode()
    )
    audio = "https://www.bls.example.com/assets/pdf/transcript/Audio-Recording-of-Earnings%20Call%20Audio_Q2FY27.mp3"
    serve[audio] = httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"ID3fake-mp3")

    text = await fetch_filing_text("https://www.bls.example.com/transcript")
    assert "strong digital demand" in text
    assert heard == ["Audio-Recording-of-Earnings%20Call%20Audio_Q2FY27.mp3"]
    # A recording served as a generic download is recognised by its extension
    serve[audio] = httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=b"ID3fake-mp3")
    assert "strong digital demand" in await fetch_filing_text(audio)


@pytest.mark.asyncio
async def test_recordings_without_speech_and_pages_without_calls_are_refused(serve, monkeypatch):
    async def silent(audio: bytes, filename: str) -> str:
        return "Thank you."

    monkeypatch.setattr(filing, "_transcribe", silent)
    serve["https://x.example.com/call.mp3"] = httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"ID3")
    with pytest.raises(FilingError, match="almost no speech"):
        await fetch_filing_text("https://x.example.com/call.mp3")
    # A page is followed one level only, so a page linking pages can't loop
    serve["https://x.example.com/ir"] = httpx.Response(
        200, headers={"content-type": "text/html"}, content=b'<html><a href="/annual-report-2026.pdf">AR</a></html>'
    )
    with pytest.raises(FilingError, match="no transcript PDF or call recording"):
        await fetch_filing_text("https://x.example.com/ir")


@pytest.mark.asyncio
async def test_only_public_https_hosts_are_fetched():
    for url in ["http://example.com/a.pdf", "https://127.0.0.1/a.pdf", "https://169.254.169.254/a.pdf"]:
        with pytest.raises(FilingError):
            await filing._check_public_https(url)


@pytest.mark.asyncio
async def test_filing_endpoints_and_research_priority(client: AsyncClient, db_session, serve):
    headers = {
        "Authorization": "Bearer "
        + (
            await client.post(
                "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
            )
        ).json()["access_token"]
    }
    db_session.add(Stock(ticker="INFY.NS", name="Infosys", price=1500.0))
    await db_session.commit()
    url = "https://nsearchives.example.com/infy-q2-transcript.pdf"
    serve[url] = httpx.Response(200, content=_pdf(SENTENCE * 10))

    bad = await client.put("/api/v1/stocks/INFY.NS/filing", json={"url": "http://a.pdf"}, headers=headers)
    assert bad.status_code == 400 and "https" in bad.json()["detail"]

    saved = await client.put("/api/v1/stocks/infy.ns/filing", json={"url": url}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["url"] == url and saved.json()["chars"] > 500
    assert (await client.get("/api/v1/stocks/INFY.NS/filing", headers=headers)).json()["url"] == url

    # The linked filing is the research context
    stock = await db_session.get(Stock, "INFY.NS")
    await db_session.refresh(stock)
    transcript = await TranscriptProvider().fetch_transcript("INFY.NS", filing=stock)
    assert transcript["url"] == url and "strong digital demand" in transcript["full_text"]

    cleared = await client.delete("/api/v1/stocks/INFY.NS/filing", headers=headers)
    assert cleared.status_code == 204
    assert (await client.get("/api/v1/stocks/INFY.NS/filing", headers=headers)).json()["url"] is None


NSE_FEED = """<rss><channel>
<item><title>Infosys Limited</title><link>https://nse.example.com/xbrl/INFY.xml</link>
<description>INFOSYS LIMITED has informed the Exchange about Transcripts - earnings or quarterly calls</description></item>
<item><title>Other Co</title><link>https://nse.example.com/xbrl/OTHER.xml</link>
<description>OTHER CO has informed the Exchange about Transcripts - earnings or quarterly calls</description></item>
<item><title>Infosys Limited</title><link>https://nse.example.com/xbrl/BM.xml</link>
<description>Outcome of Board Meeting</description></item>
</channel></rss>"""


def _xbrl(symbol: str, code: str, link: str) -> str:
    return f"""<xbrli:xbrl><in-capmkt:NSESymbol contextRef="MainI">{symbol}</in-capmkt:NSESymbol>
<in-capmkt:ScripCode contextRef="MainI">{code}</in-capmkt:ScripCode>
<in-capmkt:PurposeOfDisclosure contextRef="MainI">Transcripts - earnings or quarterly calls</in-capmkt:PurposeOfDisclosure>
<in-capmkt:WeblinkOfTranscripts contextRef="MainI">{link}</in-capmkt:WeblinkOfTranscripts></xbrli:xbrl>"""


def _bse_feed(pdf: str) -> str:
    return f"""<rss><channel><item><title>Infosys Ltd (500209)</title><link>{pdf}</link>
<scripcode>500209</scripcode><description>Transcript of the Earnings Conference Call</description></item>
</channel></rss>"""


@pytest.fixture
def watch(serve, monkeypatch):
    """Fresh watcher state, NSE feed and XBRL served, Slack captured."""
    from app.services import filing_watch

    monkeypatch.setattr(filing_watch, "_seen_xbrl", set())
    monkeypatch.setattr(filing_watch, "_reported_unreadable", set())
    posted: list[str] = []

    async def fake_slack(text: str) -> None:
        posted.append(text)

    monkeypatch.setattr(filing_watch, "notify_slack", fake_slack)
    serve[filing_watch.NSE_ANNOUNCEMENTS_RSS] = httpx.Response(200, text=NSE_FEED)
    serve["https://nse.example.com/xbrl/INFY.xml"] = httpx.Response(
        200, text=_xbrl("INFY", "500209", "https://www.infosys.example.com/investors")
    )
    serve["https://nse.example.com/xbrl/OTHER.xml"] = httpx.Response(
        200, text=_xbrl("OTHER", "500001", "https://other.example.com/t.pdf")
    )
    serve["https://www.infosys.example.com/investors"] = httpx.Response(200, text="<html>IR page</html>")
    return filing_watch, posted


@pytest.mark.asyncio
async def test_watch_links_transcript_via_bse_fallback(db_session, serve, watch):
    from sqlalchemy import select

    from app.models.research import ResearchReport

    filing_watch, posted = watch
    db_session.add(Stock(ticker="INFY.NS", name="Infosys", price=1500.0))
    db_session.add(Stock(ticker="500209.BO", name="Infosys", price=1500.0))
    await db_session.flush()
    db_session.add(ResearchReport(ticker="INFY.NS", structured_json={}, confidence_score=50.0))
    await db_session.commit()
    pdf = "https://www.bse.example.com/AttachLive/infy.pdf"
    serve[filing_watch.BSE_ANNOUNCEMENTS_RSS] = httpx.Response(200, text=_bse_feed(pdf))
    serve[pdf] = httpx.Response(200, content=_pdf(SENTENCE * 80))

    assert await filing_watch.link_new_transcripts(db_session) == 2
    for ticker in ["INFY.NS", "500209.BO"]:
        stock = await db_session.get(Stock, ticker)
        await db_session.refresh(stock)
        assert stock.filing_url == pdf and "strong digital demand" in stock.filing_text
    # The stale report is dropped so the next view regenerates with the transcript
    assert (await db_session.execute(select(ResearchReport))).first() is None
    assert len(posted) == 1 and "INFY.NS" in posted[0]

    # Already handled: the next pass does nothing
    assert await filing_watch.link_new_transcripts(db_session) == 0
    assert len(posted) == 1


@pytest.mark.asyncio
async def test_watch_skips_cover_letters_and_retries(db_session, serve, watch):
    filing_watch, posted = watch
    db_session.add(Stock(ticker="INFY.NS", name="Infosys", price=1500.0))
    await db_session.commit()
    pdf = "https://www.bse.example.com/AttachLive/infy.pdf"
    serve[filing_watch.BSE_ANNOUNCEMENTS_RSS] = httpx.Response(200, text=_bse_feed(pdf))
    serve[pdf] = httpx.Response(200, content=_pdf(SENTENCE * 10))  # a cover letter's worth of text

    assert await filing_watch.link_new_transcripts(db_session) == 0
    assert await filing_watch.link_new_transcripts(db_session) == 0
    assert len(posted) == 1 and "no readable PDF or recording" in posted[0]  # reported once, not every pass

    # The full transcript turns up later and is picked up
    serve[pdf] = httpx.Response(200, content=_pdf(SENTENCE * 80))
    assert await filing_watch.link_new_transcripts(db_session) == 1
