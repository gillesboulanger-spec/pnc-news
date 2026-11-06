"""Offline tests: no network. Run with  python -m pytest -q"""
import datetime as dt, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, fetch_gdelt as fg  # noqa: E402

NOW = dt.datetime(2026, 11, 6, 6, 0, tzinfo=dt.timezone.utc)
calls = {"rewild": 0}

def art(t, u, d, c="India"):
    return {"title": t, "url": u, "domain": d, "sourcecountry": c, "language": "English", "seendate": "20261106T010000Z"}

def fake_gdelt(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
    assert "tone>" in q and "sourcelang:english" in q
    if "permaculture" in q:
        return json.dumps({"articles": [
            art("Village women turn barren hillside into a food forest", "https://a.in/1", "a.in"),
            art("Women turn a barren hillside into food forest in Indian village", "https://b.com/2", "b.com", "United States"),
        ]}).encode()
    if "clinical trial" in q:
        return json.dumps({"articles": [art("Drug reverses memory loss in mice", "https://c/3", "c.org")]}).encode()
    if "rescued" in q and "volunteers" in q:
        return json.dumps({"articles": [
            art("Volunteer spotlight : John Haliburton | Devon Dispatch", "https://d1/x", "devondispatch.ca", "Canada"),
            art("Volunteer spotlight : John Haliburton | Spruce Grove Examiner", "https://d2/x", "sprucegroveexaminer.com", "Canada"),
            art("2716 TYLNEY LANE , Abbotsford $1 , 175 , 000", "https://e/1", "bchomez.com", "Canada"),
            art("Prefeitura entrega equipamentos", "https://g1.globo.com/especial-publicitario/x", "g1.globo.com", "Brazil"),
        ]}).encode()
    if "rewilding" in q:
        calls["rewild"] += 1
        if calls["rewild"] == 1:
            return b"Please limit requests to one every 5 seconds"
        return json.dumps({"articles": [art("Mali Moringa Queen wins UN recognition for restoring degraded land", "https://m/1", "news.mongabay.com", "Mali")]}).encode()
    return b'{"articles": []}'

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Rescued sea turtles return to the ocean</title><link>https://pn/1</link><pubDate>Fri, 06 Nov 2026 03:00:00 +0000</pubDate></item>
<item><title>Old story about a reef</title><link>https://pn/2</link><pubDate>Sat, 31 Oct 2026 03:00:00 +0000</pubDate></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Solar microgrids bring power to 300 villages</title>
<link href="https://un/1"/><updated>2026-11-06T02:00:00Z</updated><summary>renewable</summary></entry></feed>"""

def fake_rss(url):
    if "positive.news" in url: return RSS
    if "news.un.org" in url: return ATOM
    raise OSError("403 Forbidden")

def test_no_nested_brackets():
    for qs in config.BEATS.values():
        for q in qs:
            d = 0
            for ch in q:
                d += (ch == "(") - (ch == ")")
                assert d <= 1, q

def test_pipeline(monkeypatch):
    monkeypatch.setattr(fg.time, "sleep", lambda s: None)
    g, gp = fg.fetch_gdelt(get=fake_gdelt)
    r, rp = fg.fetch_rss(get=fake_rss, now=NOW)
    st = fg.cluster(g + r)
    T = {s["title"]: s for s in st}
    assert not any("mice" in t or "TYLNEY" in t or "Prefeitura" in t or "Old story" in t for t in T)
    ff = [s for s in st if "food forest" in s["title"].lower()]
    assert len(ff) == 1 and ff[0]["status"].startswith("2 outlets")
    vol = [s for s in st if "Haliburton" in s["title"]]
    assert len(vol) == 1 and vol[0]["status"].startswith("same article in 2 outlets")
    assert "Volunteer spotlight: John Haliburton | Devon Dispatch" == vol[0]["title"]
    assert any("Moringa" in t for t in T)          # retried after throttling
    assert T["Rescued sea turtles return to the ocean"]["status"].startswith("lead only")
    assert T["Solar microgrids bring power to 300 villages"]["status"] == "needs a second source"
    assert any("403" in p for p in rp) and not any("Makeda" in p for p in gp)
    js = fg.to_json(st, "2026-11-06")
    assert set(js) == {"date", "count", "stories"} and js["count"] == len(st)
    md = fg.render(st, gp + rp, "2026-11-06")
    assert "## Caio - Society & Culture" in md and "## Source problems" in md


def test_filters_from_run_4():
    bad = ["Pisces Horoscope Today, November 06, 2026", "Braun concedes race for Washington 3rd District",
           "Muthoot Microfin Ltd announces Q2 FY27 results", "Santa Monica Events This Week: Ice Skating"]
    good = ["Clinical trial results show dementia drug slows decline", "It was his wish: Late musician leaves instruments to school"]
    mk = lambda t: {"title": t, "url": "https://x/" + t, "outlet": "x.com"}
    assert all(fg.excluded(mk(t)) for t in bad)
    assert not any(fg.excluded(mk(t)) for t in good)


def test_feed_negative_words_are_whole_words(monkeypatch):
    feed = b"""<rss><channel>
<item><title>Studies show community gardens cut loneliness</title><link>https://s/1</link></item>
<item><title>Singapore sand imports threaten a fishing community</title><link>https://s/2</link></item>
</channel></rss>"""
    monkeypatch.setattr(config, "FEEDS", [("T", "https://t", "primary")])
    items, _ = fg.fetch_rss(get=lambda u: feed, now=NOW)
    titles = [i["title"] for i in items]
    assert titles == ["Studies show community gardens cut loneliness"]


def test_web_page_instead_of_feed():
    import pytest
    with pytest.raises(ValueError):
        fg.parse_feed(b"<!DOCTYPE html><html><body>Access denied</body></html>")
