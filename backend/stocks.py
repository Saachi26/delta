"""Stock-universe lookup and search."""

FALLBACK_STOCKS = {
    "RELIANCE.NS": ("Reliance Industries", "Energy & Industrials"),
    "ONGC.NS": ("ONGC", "Energy & Industrials"),
    "NTPC.NS": ("NTPC", "Energy & Industrials"),
    "POWERGRID.NS": ("Power Grid", "Energy & Industrials"),
    "COALINDIA.NS": ("Coal India", "Energy & Industrials"),
    "ADANIENT.NS": ("Adani Enterprises", "Energy & Industrials"),
    "ADANIPOWER.NS": ("Adani Power", "Energy & Industrials"),
    "LT.NS": ("Larsen & Toubro", "Energy & Industrials"),

    "HDFCBANK.NS": ("HDFC Bank", "Banking & Finance"),
    "ICICIBANK.NS": ("ICICI Bank", "Banking & Finance"),
    "SBIN.NS": ("State Bank of India", "Banking & Finance"),
    "KOTAKBANK.NS": ("Kotak Mahindra Bank", "Banking & Finance"),
    "AXISBANK.NS": ("Axis Bank", "Banking & Finance"),
    "BAJFINANCE.NS": ("Bajaj Finance", "Banking & Finance"),

    "TCS.NS": ("Tata Consultancy Services", "Technology"),
    "INFY.NS": ("Infosys", "Technology"),
    "WIPRO.NS": ("Wipro", "Technology"),
    "HCLTECH.NS": ("HCL Technologies", "Technology"),
    "TECHM.NS": ("Tech Mahindra", "Technology"),

    "ITC.NS": ("ITC", "Consumer"),
    "HINDUNILVR.NS": ("Hindustan Unilever", "Consumer"),
    "TITAN.NS": ("Titan Company", "Consumer"),
    "ASIANPAINT.NS": ("Asian Paints", "Consumer"),
    "DMART.NS": ("Avenue Supermarts (DMart)", "Consumer"),
    "MARUTI.NS": ("Maruti Suzuki", "Consumer"),
    "SUNPHARMA.NS": ("Sun Pharma", "Consumer"),

    "TMPV.NS": ("Tata Motors Passenger Vehicles", "Metals & Materials"),
    "TATASTEEL.NS": ("Tata Steel", "Metals & Materials"),
    "JSWSTEEL.NS": ("JSW Steel", "Metals & Materials"),
    "ULTRACEMCO.NS": ("UltraTech Cement", "Metals & Materials"),

    "BHARTIARTL.NS": ("Bharti Airtel", "Services"),
    "IRCTC.NS": ("IRCTC", "Services"),
}

# Curated entries override the larger inferred listing set.
try:
    from universe import STOCKS as CURATED, POPULARITY as CURATED_ORDER
except ImportError:  # pragma: no cover - only hit in a stripped checkout
    CURATED, CURATED_ORDER = FALLBACK_STOCKS, list(FALLBACK_STOCKS)

try:
    from nse_listings import LISTINGS
except ImportError:  # pragma: no cover
    LISTINGS = {}

STOCKS = {**LISTINGS, **CURATED}
# Curated symbols are ranked before the remaining alphabetical entries.
POPULARITY = CURATED_ORDER + sorted(s for s in STOCKS if s not in set(CURATED_ORDER))

SEARCH_LIMIT = 12


def name_of(symbol):
    return STOCKS[symbol][0] if symbol in STOCKS else symbol


def sector_of(symbol):
    return STOCKS[symbol][1] if symbol in STOCKS else "Other"


def exists(symbol):
    return symbol in STOCKS


def as_result(symbol):
    return {"symbol": symbol, "name": name_of(symbol), "sector": sector_of(symbol)}


def search(query):
    """Match symbols and company names, ordered by match quality."""
    q = query.strip().lower()
    if not q:
        return [as_result(s) for s in POPULARITY[:SEARCH_LIMIT]]

    hits = []
    for symbol in STOCKS:
        ticker = symbol.split(".")[0].lower()
        name = name_of(symbol).lower()
        if ticker == q:
            rank = 0
        elif ticker.startswith(q):
            rank = 1
        elif name.startswith(q):
            rank = 2
        elif q in name:
            rank = 3
        elif q in ticker:
            rank = 4
        else:
            continue
        hits.append((rank, POPULARITY.index(symbol) if symbol in POPULARITY else 9999, symbol))

    hits.sort()
    return [as_result(s) for _, _, s in hits[:SEARCH_LIMIT]]


def by_sector():
    """All known stocks grouped by sector, for the Discover page."""
    groups = {}
    for symbol in STOCKS:
        groups.setdefault(sector_of(symbol), []).append(symbol)
    return groups
