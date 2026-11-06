"""Pull positive, solution-focused news from GDELT, one batch per country.

Writes news/YYYY-MM-DD.json and news/latest.json.
GDELT DOC 2.0 API: free, no key. It throttles fast callers, so we go slowly
and retry when it answers with an error page instead of data.
"""
import json
import time
import datetime
import pathlib
import urllib.parse
import urllib.request

# Two-letter GDELT country codes, so every newscast is a world snapshot.
COUNTRIES = {
    "IN": "India", "BR": "Brazil", "AS": "Australia", "US": "United States",
    "UK": "United Kingdom", "NI": "Nigeria", "KE": "Kenya",
    "SF": "South Africa", "JA": "Japan", "GM": "Germany", "FR": "France",
    "CA": "Canada", "MX": "Mexico", "TH": "Thailand", "ID": "Indonesia",
    "RP": "Philippines",
}

# Words that signal a constructive story (community, nature, women, solutions).
TOPICS = (
    "(volunteers OR cooperative OR villagers OR restored OR reforestation OR "
    "rescued OR breakthrough OR \"women farmers\" OR \"community garden\" OR "
    "\"clean water\" OR \"solar\" OR scholarship OR \"new school\")"
)

MIN_TONE = 4          # higher = more clearly positive
MAX_PER_COUNTRY = 25
PAUSE = 15            # seconds between requests (GDELT throttles fast callers)
RETRIES = 4
API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Sources that produce noise (listings, press releases, coupons).
BLOCKED_DOMAINS = {
    "bchomez.com", "finanznachrichten.de", "newswit.com", "presseportal.de",
    "unternehmen-heute.de", "sueddeutsche.de", "thailand-business-news.com",
    "globenewswire.com", "prnewswire.com", "businesswire.com",
    "einpresswire.com", "openpr.com", "nigeriasun.com",
}

# Title fragments that mark ads, listings and coupons.
BLOCKED_WORDS = [
    "rabatt", "gutschein", "cashback", "discount", "coupon", "promo code",
    "for sale", "$", "press release", "presswire", "newswire", "singles day",
]


def log(message):
    print(message, flush=True)


def fetch(code, name):
    query = f"{TOPICS} sourcecountry:{code} tone>{MIN_TONE}"
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_PER_COUNTRY,
        "timespan": "24h",
        "sort": "hybridrel",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": "pnc-news/1.1"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            articles = data.get("articles", [])
            log(f"{name}: {len(articles)} stories")
            return [
                {
                    "country": name,
                    "title": a.get("title"),
                    "source": a.get("domain"),
                    "language": a.get("language"),
                    "seen": a.get("seendate"),
                    "url": a.get("url"),
                }
                for a in articles
            ]
        except Exception as err:
            log(f"{name}: attempt {attempt} failed ({err})")
            time.sleep(30 * attempt)
    log(f"{name}: giving up")
    return []


def is_noise(story):
    title = (story["title"] or "").lower()
    domain = (story["source"] or "").lower()
    if domain in BLOCKED_DOMAINS:
        return True
    return any(word in title for word in BLOCKED_WORDS)


def title_key(story):
    # Syndicated copies differ only after a "|" or " - " suffix.
    title = (story["title"] or "").split("|")[0].strip().lower()
    return title


def main():
    stories = []
    seen_urls = set()
    seen_titles = set()
    for code, name in COUNTRIES.items():
        for story in fetch(code, name):
            if not story["url"] or story["url"] in seen_urls:
                continue
            if is_noise(story) or title_key(story) in seen_titles:
                continue
            seen_urls.add(story["url"])
            seen_titles.add(title_key(story))
            stories.append(story)
        time.sleep(PAUSE)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out = pathlib.Path("news")
    out.mkdir(exist_ok=True)
    payload = {"date": today, "count": len(stories), "stories": stories}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    (out / f"{today}.json").write_text(text, encoding="utf-8")
    (out / "latest.json").write_text(text, encoding="utf-8")
    log(f"Saved {len(stories)} stories for {today}")


if __name__ == "__main__":
    main()
