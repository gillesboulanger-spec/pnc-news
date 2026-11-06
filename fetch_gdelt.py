"""Pull positive, solution-focused news from GDELT, one batch per country.

Writes news/YYYY-MM-DD.json and news/latest.json.
GDELT DOC 2.0 API: free, no key. One request per ~5 seconds is polite.
"""
import json
import time
import datetime
import pathlib
import urllib.parse
import urllib.request

# Countries to sample so every newscast is a world snapshot.
COUNTRIES = [
    "india", "brazil", "australia", "unitedstates", "unitedkingdom",
    "nigeria", "kenya", "southafrica", "japan", "germany", "france",
    "canada", "mexico", "thailand", "indonesia", "philippines",
]

# Themes PNC cares about: communities, villages, women, solutions, nature.
TOPICS = (
    "(community OR village OR volunteers OR cooperative OR women OR "
    "restored OR solution OR breakthrough OR garden OR school OR rescued)"
)

# tone>3 keeps clearly positive stories only.
MIN_TONE = 3
MAX_PER_COUNTRY = 20
API = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch(country):
    query = f"{TOPICS} sourcecountry:{country} tone>{MIN_TONE}"
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_PER_COUNTRY,
        "timespan": "24h",
        "sort": "hybridrel",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "pnc-news/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
    except Exception as err:  # GDELT sometimes answers with plain text
        print(f"{country}: skipped ({err})")
        return []
    articles = data.get("articles", [])
    print(f"{country}: {len(articles)} stories")
    return [
        {
            "country": country,
            "title": a.get("title"),
            "source": a.get("domain"),
            "language": a.get("language"),
            "seen": a.get("seendate"),
            "url": a.get("url"),
        }
        for a in articles
    ]


def main():
    stories = []
    seen_urls = set()
    for country in COUNTRIES:
        for story in fetch(country):
            if story["url"] and story["url"] not in seen_urls:
                seen_urls.add(story["url"])
                stories.append(story)
        time.sleep(6)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out = pathlib.Path("news")
    out.mkdir(exist_ok=True)
    payload = {"date": today, "count": len(stories), "stories": stories}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    (out / f"{today}.json").write_text(text, encoding="utf-8")
    (out / "latest.json").write_text(text, encoding="utf-8")
    print(f"Saved {len(stories)} stories for {today}")


if __name__ == "__main__":
    main()
