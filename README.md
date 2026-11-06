# pnc-news
Positive News Channel: daily news pull (GDELT + RSS), sorted by reporter beat.

**Read today's list:** [`news/LATEST.md`](news/LATEST.md). Data for other tools: `news/latest.json`.

- Runs every day at 5 am Chiang Mai time (Actions tab -> Daily PNC news pull -> Run workflow to run it now).
- Searches are per beat (Kiran, Makeda, Rory, Caio, Yejin), positive tone only, English-language outlets worldwide.
- Articles about the same story are grouped. Each story is marked: *N outlets*, *same article syndicated (one source)*, *needs a second source*, or *lead only* (good-news sites: trace the original).
- Noise filters: property listings, press releases, coupons, sponsored pages, earnings, gossip.
- **Source problems** at the bottom of LATEST.md lists searches or feeds that failed.

Change beats, search words, feeds and filters in [`config.py`](config.py). Every story is a candidate: two independent sources before it airs.
