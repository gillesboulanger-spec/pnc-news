"""PNC news pull: a daily list of positive story candidates, per reporter beat.

Sources:
  1. GDELT DOC 2.0 API (free, no key): worldwide news, filtered to a positive tone.
  2. RSS feeds from good-news outlets (leads) and primary sources.

Output: news/LATEST.md and news/YYYY-MM-DD.md (to read),
        news/latest.json and news/YYYY-MM-DD.json (for other tools).
Needs nothing but Python 3 (no extra packages).
Every story is a CANDIDATE. PNC's rule still applies: two independent sources before it airs.

Usage:  python fetch_gdelt.py            # writes today's list into news/
        python fetch_gdelt.py --out DIR  # somewhere else
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import config

UA = "pnc-news/2.0"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
STOP = set("a an and are as at be by for from has have in is it its new of on or that the to was were will with after over how why what more than this".split())


# ---------------------------------------------------------------- fetching
def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def gdelt_query(q: str, hours: int, tone: float, maxrec: int) -> str:
    params = {
        "query": f"{q} tone>{tone} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(maxrec),
        "timespan": f"{hours}h",
        "sort": "hybridrel",
    }
    return GDELT_URL + "?" + urllib.parse.urlencode(params)


PAUSE = 20        # seconds between GDELT searches
BACKOFF = 45      # seconds to wait after a 429 before trying again


def gdelt_get_json(url: str, get=http_get, retries: int = 3, pause: float = BACKOFF) -> tuple[dict | None, str]:
    """GDELT answers a fast caller with a text message instead of JSON: wait and try again."""
    last = ""
    for attempt in range(1, retries + 1):
        try:
            raw = get(url).decode("utf-8", "replace").strip()
            if raw.startswith("{"):
                return json.loads(raw), ""
            last = raw[:120] or "empty answer"
        except Exception as e:  # network error, timeout, bad JSON
            last = str(e)
        if attempt < retries:
            time.sleep(pause * attempt)
    return None, last


def fetch_gdelt(get=http_get) -> tuple[list[dict], list[str]]:
    """Run every beat's searches. Returns (articles, problems)."""
    items, problems = [], []
    todo = [(beat, q) for beat, queries in config.BEATS.items() for q in queries]
    for round_ in (1, 2):  # second round retries the searches GDELT turned away
        failed = []
        for n, (beat, q) in enumerate(todo):
            if n or round_ == 2:
                time.sleep(PAUSE if round_ == 1 else BACKOFF)
            url = gdelt_query(q, config.HOURS, config.MIN_TONE, config.MAX_PER_QUERY)
            data, err = gdelt_get_json(url, get, retries=2 if round_ == 1 else 3)
            if data is None:
                failed.append((beat, q, err))
                continue
            for a in data.get("articles", []):
                items.append({
                    "beat": beat,
                    "title": clean_title(a.get("title") or ""),
                    "url": a.get("url", ""),
                    "outlet": a.get("domain", ""),
                    "country": a.get("sourcecountry", ""),
                    "language": a.get("language", ""),
                    "seen": parse_gdelt_date(a.get("seendate", "")),
                    "kind": "news",
                    "via": "GDELT",
                })
        todo = [(b, q) for b, q, _ in failed]
        if not todo:
            break
    for beat, q, err in failed:
        problems.append(f"GDELT search for {beat} failed twice: {err} ({q[:60]})")
    return items, problems


def clean_title(t: str) -> str:
    """GDELT titles come with spaces around punctuation ("St . Vincent", "Fofos !")."""
    t = re.sub(r"\s+([.,!?;:)])", r"\1", t)
    t = re.sub(r"([(])\s+", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_gdelt_date(s: str) -> str:
    try:
        return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).isoformat()
    except ValueError:
        return ""


def parse_feed(data: bytes) -> list[dict]:
    """Read an RSS or Atom feed with the standard library. Returns [{title, link, summary, when}]."""
    data = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not data.startswith(b"<"):
        raise ValueError("site sent something other than a feed")
    if data[:200].lower().find(b"<html") != -1:
        raise ValueError("site sent a web page, not a feed (blocked or moved)")
    root = ET.fromstring(data)
    out = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        f = {"title": "", "link": "", "summary": "", "when": None}
        for c in el:
            ct = c.tag.split("}")[-1]
            text = (c.text or "").strip()
            if ct == "title":
                f["title"] = text
            elif ct == "link":
                f["link"] = f["link"] or text or c.get("href", "")
            elif ct in ("description", "summary") and not f["summary"]:
                f["summary"] = text
            elif ct in ("pubDate", "published", "updated", "date") and f["when"] is None:
                f["when"] = parse_feed_date(text)
        out.append(f)
    return out


def parse_feed_date(s: str):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)  # RSS style: "Fri, 06 Nov 2026 03:00:00 +0000"
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom style
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def fetch_rss(get=http_get, now: dt.datetime | None = None) -> tuple[list[dict], list[str]]:
    now = now or dt.datetime.now(dt.timezone.utc)
    window = max(config.HOURS, 36)  # feeds post less often: look a bit further back
    cutoff = now - dt.timedelta(hours=window)
    items, problems = [], []
    for name, url, kind in config.FEEDS:
        try:
            entries = parse_feed(get(url))
        except Exception as e:
            problems.append(f"Feed {name} failed: {e}")
            continue
        if not entries:
            problems.append(f"Feed {name} returned nothing (blocked, moved or empty)")
            continue
        fresh = 0
        for e in entries:
            if e["when"] and e["when"] < cutoff:
                continue
            title = clean_title(e["title"])
            summary = re.sub(r"<[^>]+>", " ", e["summary"])
            text = f"{title} {summary}".lower()
            if not any(k in text for k in config.RSS_KEYWORDS):
                continue
            padded = " " + re.sub(r"[^a-z0-9 ]+", " ", title.lower()) + " "
            if any(" " + w in padded for w in config.NEGATIVE_WORDS):
                continue
            fresh += 1
            items.append({
                "beat": guess_beat(text),
                "title": title,
                "url": e["link"],
                "outlet": name,
                "country": "",
                "language": "English",
                "seen": e["when"].isoformat() if e["when"] else "",
                "kind": kind,
                "via": "RSS",
            })
        if fresh == 0:
            problems.append(f"Feed {name}: nothing new on our beats in the last {window} h")
    return items, problems


BEAT_HINTS = {
    "Kiran - Human Spirit": ["rescue", "volunteer", "kind", "donat", "reunit", "adopt", "sanctuary"],
    "Makeda - Planet & Crisis": ["restor", "rewild", "forest", "reef", "species", "solar", "renewable", "court", "law", "water"],
    "Rory - Planet through art": ["artist", "music", "film", "mural", "festival"],
    "Caio - Society & Culture": ["permaculture", "cooperative", "garden", "village", "women", "girls", "school", "assembly", "democra"],
    "Yejin - Science, Tech & Medicine": ["trial", "treatment", "therapy", "alzheimer", "dementia", "breakthrough", "invent", "scien"],
}


def guess_beat(text: str) -> str:
    scores = {b: sum(text.count(w) for w in ws) for b, ws in BEAT_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "Unsorted"


# ---------------------------------------------------------------- cleaning
def words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP and len(w) > 2}


def excluded(item: dict) -> bool:
    t = f" {item['title'].lower()} "
    where = f"{item['url'].lower()} {t}"
    if item["outlet"].lower() in config.BLOCKED_DOMAINS:
        return True
    return any(w in t for w in config.EXCLUDE_WORDS) or any(w in where for w in config.BLOCKED_WORDS)


def title_key(title: str) -> str:
    """Syndicated copies differ only by an outlet name after "|" or " - "."""
    t = re.split(r"\s[|\uff5c]\s|\s[-\u2013\u2014]\s", title)[0]
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def cluster(items: list[dict], threshold: float = 0.5) -> list[dict]:
    """Group articles about the same story (similar titles). Each story lists all its outlets."""
    stories: list[dict] = []
    seen_urls = set()
    for it in items:
        if not it["title"] or not it["url"] or it["url"] in seen_urls or excluded(it):
            continue
        seen_urls.add(it["url"])
        w = words(title_key(it["title"]))
        for s in stories:
            inter = len(w & s["_words"])
            same = title_key(it["title"]) == s["_key"]
            if same or (w and inter / max(1, min(len(w), len(s["_words"]))) >= threshold and inter >= 3):
                s["sources"].append(it)
                s["_words"] |= w
                break
        else:
            stories.append({"title": it["title"], "beat": it["beat"], "sources": [it], "_words": set(w),
                            "_key": title_key(it["title"])})
    for s in stories:
        outlets = {x["outlet"] for x in s["sources"]}
        s["outlets"] = len(outlets)
        s["countries"] = sorted({x["country"] for x in s["sources"] if x["country"]})
        syndicated = len({title_key(x["title"]) for x in s["sources"]}) == 1 and len(outlets) > 1
        if syndicated:
            s["status"] = f"same article in {len(outlets)} outlets (one source) - needs a second source"
        elif len(outlets) >= 2:
            s["status"] = f"{len(outlets)} outlets - check they're independent"
        else:
            s["status"] = "needs a second source"
        # a story from a "lead" site alone is a tip, not a source
        if all(x["kind"] == "lead" for x in s["sources"]):
            s["status"] = "lead only - trace the original source"
    stories.sort(key=lambda s: (-(s["outlets"] if not s["status"].startswith("same") else 1), s["title"]))
    return stories


# ---------------------------------------------------------------- output
def render(stories: list[dict], problems: list[str], day: str) -> str:
    by_beat: dict[str, list[dict]] = {}
    for s in stories:
        by_beat.setdefault(s["beat"], []).append(s)
    lines = [f"# PNC newsdesk - {day}", "",
             f"{len(stories)} candidate stories from the last {config.HOURS} h "
             f"(GDELT tone > {config.MIN_TONE}, plus RSS). Candidates only: two independent sources before anything airs.", ""]
    order = list(config.BEATS) + ["Unsorted"]
    for beat in order:
        group = by_beat.get(beat, [])
        lines.append(f"## {beat} ({len(group)})")
        lines.append("")
        if not group:
            lines += ["_Nothing today._", ""]
            continue
        for i, s in enumerate(group[:25], 1):
            first = s["sources"][0]
            where = f" ({first['country']})" if first.get("country") else ""
            lines.append(f"{i}. **{s['title']}**{where} - _{s['status']}_")
            for x in s["sources"][:5]:
                lines.append(f"    - [{x['outlet']}]({x['url']})")
        if len(group) > 25:
            lines.append(f"    _...and {len(group) - 25} more in the JSON file._")
        lines.append("")
    if problems:
        lines += ["## Source problems", ""] + [f"- {p}" for p in problems] + [""]
    return "\n".join(lines)


def to_json(stories: list[dict], day: str) -> dict:
    """Same top-level shape as the first version (date, count, stories) so other tools keep working."""
    out = []
    for s in stories:
        first = s["sources"][0]
        out.append({
            "beat": s["beat"], "status": s["status"], "outlets": s["outlets"],
            "country": first["country"], "title": s["title"], "source": first["outlet"],
            "language": first.get("language", ""), "seen": first["seen"], "url": first["url"],
            "all_sources": [{"outlet": x["outlet"], "url": x["url"], "kind": x["kind"]} for x in s["sources"]],
        })
    return {"date": day, "count": len(out), "stories": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="news")
    ap.add_argument("--no-gdelt", action="store_true")
    ap.add_argument("--no-rss", action="store_true")
    a = ap.parse_args(argv)
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    items, problems = [], []
    if not a.no_gdelt:
        i, p = fetch_gdelt(); items += i; problems += p
    if not a.no_rss:
        i, p = fetch_rss(); items += i; problems += p
    stories = cluster(items)
    os.makedirs(a.out, exist_ok=True)
    md = render(stories, problems, day)
    js = json.dumps(to_json(stories, day), indent=2, ensure_ascii=False)
    for name, text in ((f"{day}.md", md), ("LATEST.md", md), (f"{day}.json", js), ("latest.json", js)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"{len(stories)} stories, {len(problems)} source problems -> {a.out}/LATEST.md")
    for p in problems:
        print("  problem:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
