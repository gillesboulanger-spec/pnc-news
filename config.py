"""What the newsdesk looks for. Edit this file to change beats, keywords or feeds.

GDELT query rules (https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/):
  - several words in brackets with OR between them = any of them
  - "two words" in quotes = that exact phrase
  - a minus sign in front of a word = leave out articles with it
"""

# How positive an article must be on GDELT's tone scale (about -10 to +10; 0 = neutral).
MIN_TONE = 3
# How far back to look, in hours.
HOURS = 24
# Most articles to take from GDELT per search.
MAX_PER_QUERY = 150

# ONE search per reporter: GDELT rations requests from GitHub's shared servers, so fewer,
# bigger searches get through far more reliably than many small ones (run #5: 5 of 13 refused).
BEATS = {
    "Kiran - Human Spirit": [
        '(rescued OR rescue OR volunteers OR kindness OR donated OR reunited OR "good samaritan" '
        'OR "animal rescue" OR sanctuary OR adopted OR "acts of kindness")',
    ],
    "Makeda - Planet & Crisis": [
        '(restoration OR rewilding OR reforestation OR "species recovery" OR "landmark ruling" '
        'OR "rights of nature" OR "renewable energy" OR "clean water" OR "coral reef" OR mangroves '
        'OR "protected area" OR "back from extinction")',
    ],
    "Rory - Planet through art": [
        '(artist OR musician OR filmmaker OR mural OR documentary OR festival) '
        '(river OR forest OR ocean OR climate OR wildlife OR nature)',
    ],
    "Caio - Society & Culture": [
        '(permaculture OR cooperative OR "community garden" OR "food forest" OR ecovillage '
        'OR "citizens assembly" OR "participatory budgeting" OR "community land trust" '
        'OR "women-led" OR "first woman" OR "women farmers" OR villagers)',
    ],
    "Yejin - Science, Tech & Medicine": [
        '("clinical trial" OR breakthrough OR "new therapy" OR alzheimer OR dementia '
        'OR "approved treatment" OR invention OR "low cost device") -mice -rats -mouse',
    ],
}

# Outlets that produce noise (property listings, press releases, coupons). From the first run.
BLOCKED_DOMAINS = {
    "bchomez.com", "finanznachrichten.de", "newswit.com", "presseportal.de",
    "unternehmen-heute.de", "thailand-business-news.com", "globenewswire.com",
    "prnewswire.com", "businesswire.com", "einpresswire.com", "openpr.com", "nigeriasun.com",
}
# Words in a title or link that mark ads, listings, sponsored pages, money news and gossip.
BLOCKED_WORDS = [
    "discount", "coupon", "promo code", "for sale", "press release", "presswire", "newswire",
    "singles day", "rabatt", "gutschein", "cashback", "especial-publicitario", "sponsored",
    "financial results", "quarterly results", "unaudited", "q3 fy", "q3 2026",
    "romance", "dating", "boyfriend", "girlfriend", "pregnan", "celebrity",
    # added after run #4: horoscopes, election results, event calendars, earnings, search callouts
    "horoscope", "concede", "election", "midterm", "mayor race", "race for", "calendar",
    "events this week", "holiday events", "shopping event", "walk of fame", "restaurants to visit",
    "q1 fy", "q2 fy", "q3 fy", "q4 fy", "missing person", "missing fisherman", "search teams",
]

# Feeds are not tone-checked by GDELT, so drop feed items whose title reads as bad news.
# Matched as whole words or word starts (a space is put in front), so "dies" won't catch "studies".
NEGATIVE_WORDS = [
    "threatens", "threaten ", "grab", "launder", "havoc", "stalls", "contamina", "illegal", "sinking",
    "crisis", "decline", "loss of", "dies", "death", "flood", "wildfire", "drought", "warns", "fear",
    "attack", "pollution", "settle ", "lawsuit", "smaller",
]

# RSS feeds. "lead" feeds are good-news sites: use them to spot stories, then trace the
# original source. "primary" feeds publish first-hand (research, UN, local reporting).
FEEDS = [
    # good-news outlets (leads only)
    ("Positive News", "https://www.positive.news/feed/", "lead"),
    ("Reasons to be Cheerful", "https://reasonstobecheerful.world/feed/", "lead"),
    ("Fix the News", "https://fixthenews.com/feed", "lead"),
    ("Good News Network", "https://www.goodnewsnetwork.org/feed/", "lead"),
    ("YES! Magazine", "https://www.yesmagazine.org/feed", "lead"),
    ("Shareable", "https://www.shareable.net/feed/", "lead"),
    ("The Better India", "https://thebetterindia.com/feed/", "lead"),
    # primary or near-primary sources
    # UN News removed: its feed sends a web page to GitHub's servers (runs #4 and #5)
    ("NPR Science", "https://feeds.npr.org/1007/rss.xml", "primary"),
    ("Guardian Environment", "https://www.theguardian.com/environment/rss", "primary"),
    ("Mongabay", "https://news.mongabay.com/feed/", "primary"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml", "primary"),
    ("Global Voices", "https://globalvoices.org/feed/", "primary"),
    ("BBC Science & Environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "primary"),
]

# Feed items must contain at least one of these words to make the list
# (good-news feeds are already positive, so this only drops off-topic items).
RSS_KEYWORDS = [
    "rescue", "volunteer", "kind", "communit", "restor", "rewild", "forest", "reef", "species",
    "solar", "renewable", "water", "court", "ruling", "law", "artist", "music", "film", "permaculture",
    "cooperative", "garden", "village", "women", "girls", "school", "assembly", "democra", "trial",
    "treatment", "therapy", "alzheimer", "dementia", "breakthrough", "invent", "farmer", "clean",
]

# Words that knock an item out (we report good news, and the audience doesn't want lab-animal studies).
EXCLUDE_WORDS = ["mice", "mouse", "rats ", "killed", "dead", "murder", "war ", "shooting", "obituary", "election rally"]

# GDELT does not accept brackets inside brackets: keep each (... OR ...) group flat.

# Title words for each beat (word starts). GDELT matches a search anywhere in the article text,
# so many hits never mention the topic in their headline. A story whose title names its topic
# is listed under its reporter; the rest go to a short "weaker matches" list at the bottom.
TITLE_STEMS = {
    "Kiran - Human Spirit": ["rescu", "volunteer", "kind", "donat", "reunit", "adopt", "sanctuar", "charit",
        "fundrais", "free meal", "community meal", "helps", "help ", "hero", "saves", "saved", "shelter",
        "neighbo", "grit", "hope", "gift", "leaves", "wish", "puppy", "dog", "kitten", "aid "],
    "Makeda - Planet & Crisis": ["restor", "rewild", "reforest", "forest", "species", "wildlife", "conserv",
        "biodivers", "reef", "mangrove", "wetland", "solar", "renewable", "clean energy", "energy storage",
        "clean water", "rainwater", "deforest", "ruling", "court", "protected", "ocean", "nature",
        "sustainab", "farm", "agricult", "climate"],
    "Rory - Planet through art": ["artist", "art ", "mural", "music", "film", "documentar", "festival",
        "sculpt", "paint", "exhibit", "theatre", "dance", "poet", "craft", "artisan", "ceramic"],
    "Caio - Society & Culture": ["cooperative", "co-op", "co - op", "permaculture", "garden", "village",
        "women", "woman", "girls", "first woman", "first female", "first black", "first indigenous", "assembly", "budget", "land trust", "democra", "inclus",
        "disabilit", "access", "school", "youth", "tradition"],
    "Yejin - Science, Tech & Medicine": ["trial", "therap", "treatment", "alzheimer", "dementia", "brain",
        "cancer", "vaccine", "scien", "discover", "invent", "innovat", "device", "patient",
        "healthcare", "public health", "medic", "research", "study", "biomed"],
}
# How many weaker matches to list at the bottom of LATEST.md (all are kept in latest.json).
MAX_WEAK = 40
