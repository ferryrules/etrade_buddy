"""
Parse spoken natural language into (symbol, field) pairs.

Handles queries like:
    "what's the price of apple"
    "how much is my tesla worth"
    "total gain on microsoft"
    "amazon dividend yield"
    "what's AAPL trading at"
"""

import re

COMMON_STOCKS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "tesla": "TSLA",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "disney": "DIS",
    "walmart": "WMT",
    "johnson and johnson": "JNJ",
    "johnson & johnson": "JNJ",
    "jp morgan": "JPM",
    "jpmorgan": "JPM",
    "bank of america": "BAC",
    "coca cola": "KO",
    "coca-cola": "KO",
    "coke": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "boeing": "BA",
    "intel": "INTC",
    "amd": "AMD",
    "at&t": "T",
    "at and t": "T",
    "verizon": "VZ",
    "ford": "F",
    "general motors": "GM",
    "general electric": "GE",
    "home depot": "HD",
    "procter and gamble": "PG",
    "proctor and gamble": "PG",
    "exxon": "XOM",
    "exxon mobil": "XOM",
    "chevron": "CVX",
    "pfizer": "PFE",
    "unitedhealth": "UNH",
    "united health": "UNH",
    "visa": "V",
    "mastercard": "MA",
    "paypal": "PYPL",
    "costco": "COST",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "oracle": "ORCL",
    "cisco": "CSCO",
    "ibm": "IBM",
    "qualcomm": "QCOM",
    "starbucks": "SBUX",
    "nike": "NKE",
    "mcdonald's": "MCD",
    "mcdonalds": "MCD",
    "target": "TGT",
    "berkshire": "BRK.B",
    "berkshire hathaway": "BRK.B",
    "broadcom": "AVGO",
    "spotify": "SPOT",
    "uber": "UBER",
    "airbnb": "ABNB",
    "snowflake": "SNOW",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "robinhood": "HOOD",
    "sofi": "SOFI",
    "lucid": "LCID",
    "rivian": "RIVN",
    "snap": "SNAP",
    "snapchat": "SNAP",
    "pinterest": "PINS",
    "zoom": "ZM",
    "shopify": "SHOP",
    "square": "SQ",
    "block": "SQ",
    "roku": "ROKU",
    "draftkings": "DKNG",
    "crowdstrike": "CRWD",
    "datadog": "DDOG",
    "twilio": "TWLO",
    "okta": "OKTA",
    "splunk": "SPLK",
    "arm": "ARM",
}

FIELD_PATTERNS = [
    # Multi-word specific patterns must come before their shorter substrings.
    (r"\b(intrinsic value)\b", "intrinsic_value"),
    (r"\b(open interest)\b", "open_interest"),
    (r"\b(opening price)\b", "open"),
    (r"\b(implied volatility)\b", "iv_pct"),
    (r"\b(bid.?ask spread|spread)\b", "bid_ask_spread"),
    (r"\b(bid size)\b", "bid_size"),
    (r"\b(ask size)\b", "ask_size"),
    (r"\b(days to expiration|expiration|when does it expire)\b", "days_to_expiration"),
    (r"\b(price|trading at|stock price|current price|last price|how much is .+ trading)\b", "price"),
    (r"\b(market value|value|worth|how much .+ worth)\b", "value"),
    (r"\b(total gain percent|gain percent)\b", "gain_pct"),
    (r"\b(total gain|overall gain|gain loss|gain or loss)\b", "gain"),
    (r"\b(today.?s? gain percent|day.?s? gain percent)\b", "days_gain_pct"),
    (r"\b(today.?s? gain|day.?s? gain|daily gain)\b", "days_gain"),
    (r"\b(today.?s? change|change today|daily change)\b", "change"),
    (r"\b(change percent|percent change)\b", "change_pct"),
    (r"\b(change)\b", "change"),
    (r"\b(shares|quantity|how many)\b", "quantity"),
    (r"\b(cost per share|average cost)\b", "cost_per_share"),
    (r"\b(cost basis|total cost)\b", "cost"),
    (r"\b(price paid|paid)\b", "price_paid"),
    (r"\b(percent of portfolio|portfolio percent|allocation)\b", "pct_of_portfolio"),
    (r"\b(volume|trading volume)\b", "volume"),
    (r"\b(p\.?e\.? ratio|price.?to.?earnings|pe ratio|p e ratio)\b", "pe_ratio"),
    (r"\b(earnings per share|eps)\b", "eps"),
    (r"\b(estimated earnings|earnings estimate)\b", "est_earnings"),
    (r"\b(dividend yield|div yield)\b", "div_yield"),
    (r"\b(annual dividend|yearly dividend)\b", "annual_dividend"),
    (r"\b(ex.?dividend date|ex.?div date|ex date)\b", "ex_div_date"),
    (r"\b(dividend pay date|dividend payment date|pay date)\b", "div_pay_date"),
    (r"\b(net expense ratio|expense ratio)\b", "expense_ratio"),
    (r"\b(gross expense ratio)\b", "gross_expense_ratio"),
    (r"\b(annual yield|yearly yield|annual return)\b", "annual_yield"),
    (r"\b(dividend distribution amount|dividend distribution|dividend amount|dividend|dividends)\b", "dividend"),
    (r"\b(market cap|market capitalization)\b", "market_cap"),
    (r"\b(52.?week high|fifty.?two week high|yearly high|year high)\b", "week52_high"),
    (r"\b(52.?week low|fifty.?two week low|yearly low|year low)\b", "week52_low"),
    (r"\b(52.?week range|fifty.?two week range|52 week range)\b", "week52_range"),
    (r"\b(today.?s? range|day.?s? range|daily range|high and low|high low)\b", "days_range"),
    (r"\b(bid)\b", "bid"),
    (r"\b(ask)\b", "ask"),
    (r"\b(open)\b", "open"),
    (r"\b(previous close|prev close|yesterday.?s? close)\b", "prev_close"),
    (r"\b(beta)\b", "beta"),
    (r"\b(one month performance|1 month performance|last month)\b", "perform_1month"),
    (r"\b(three month performance|3 month performance)\b", "perform_3month"),
    (r"\b(six month performance|6 month performance)\b", "perform_6month"),
    (r"\b(twelve month performance|12 month performance|one year performance|year performance)\b", "perform_12month"),
    (r"\b(when did i buy|date acquired|purchase date|date purchased|when bought)\b", "date_acquired"),
    (r"\b(commissions?|fees|commission and fees)\b", "commissions"),
    (r"\b(delta)\b", "delta"),
    (r"\b(gamma)\b", "gamma"),
    (r"\b(theta|time decay)\b", "theta"),
    (r"\b(vega)\b", "vega"),
    (r"\b(rho)\b", "rho"),
    (r"\b(iv)\b", "iv_pct"),
    (r"\b(volatility)\b", "iv_pct"),
    (r"\b(exchange)\b", "exchange"),
]

FIELD_HELP = [
    "price", "value", "gain", "today's gain", "change", "quantity", "cost",
    "volume", "dividend", "annual dividend", "dividend yield",
    "ex-dividend date", "dividend pay date",
    "P E ratio", "earnings per share", "estimated earnings",
    "market cap", "52-week high", "52-week low", "52-week range",
    "today's range", "bid", "ask", "spread", "open", "previous close",
    "beta", "1 month performance", "3 month performance",
    "6 month performance", "12 month performance",
    "when did I buy", "commissions",
    "delta", "gamma", "theta", "vega", "rho",
    "implied volatility", "open interest", "days to expiration",
]

STOP_WORDS = {
    "what", "what's", "whats", "how", "much", "is", "the", "my",
    "of", "for", "on", "in", "a", "an", "about", "tell", "me",
    "give", "get", "show", "check", "look", "up", "can", "you",
    "please", "do", "does", "did", "has", "have", "had", "it",
    "that", "this", "to", "and", "or", "with",
}


def register_portfolio_stocks(positions):
    """
    Add stocks from a live portfolio into the lookup table.

    Call this after fetching portfolio data so the parser can recognize
    company names that aren't in the built-in COMMON_STOCKS dict.

    :param positions: dict mapping symbol/description to position data,
                      or list of position dicts from the E*TRADE API
    """
    if isinstance(positions, dict):
        items = []
        seen = set()
        for pos in positions.values():
            pid = id(pos)
            if pid in seen:
                continue
            seen.add(pid)
            items.append(pos)
    else:
        items = positions

    added = 0
    for pos in items:
        symbol = pos.get("Product", {}).get("symbol", "").upper()
        desc = pos.get("symbolDescription", "")
        if not symbol:
            continue

        if symbol not in COMMON_STOCKS.values():
            name_lower = desc.lower().strip()
            if name_lower and name_lower not in COMMON_STOCKS:
                COMMON_STOCKS[name_lower] = symbol
                added += 1

            short_name = _simplify_description(name_lower)
            if short_name and short_name not in COMMON_STOCKS and short_name != name_lower:
                COMMON_STOCKS[short_name] = symbol
                added += 1

    return added


def _simplify_description(desc):
    """
    Turn an E*TRADE description like 'ACME CORP INC COM' into 'acme'
    or 'BERKSHIRE HATHAWAY INC CL B' into 'berkshire hathaway'.

    Strips common suffixes so the user can say just the company name.
    """
    suffixes = {
        "inc", "corp", "corporation", "co", "company", "ltd", "limited",
        "plc", "llc", "lp", "group", "holdings", "holding", "international",
        "intl", "enterprises", "com", "common", "cl", "class", "new",
        "ser", "series", "shs", "shares", "stock", "ordinary", "ads",
        "adr", "depositary", "receipt", "receipts", "trust", "reit",
        "etf", "fund", "index", "a", "b", "c", "d", "i", "ii", "iii",
        "usa", "us", "nv", "sa", "ag", "se", "n.v", "technologies",
        "technology", "tech", "systems", "solutions", "services",
        "global", "worldwide", "industries", "partners", "capital",
        "financial", "bancorp", "bancshares", "pharmaceutical",
        "pharmaceuticals", "therapeutics", "biosciences", "energy",
        "resources", "communications", "brands", "labs", "laboratories",
    }
    words = desc.lower().split()
    cleaned = []
    for w in words:
        if w in suffixes:
            break
        cleaned.append(w)
    result = " ".join(cleaned).strip()
    return result if len(result) > 1 else ""


TICKER_BLACKLIST = {
    "I", "A", "AM", "PM", "THE", "AND", "FOR", "HOW", "YES", "NO",
    "IS", "IT", "AT", "ON", "OF", "IN", "TO", "DO", "MY", "ME",
    "UP", "SO", "OR", "IF", "BE", "HE", "WE", "AS", "BY", "AN",
    "WHAT", "MUCH", "TELL", "SHOW", "CHECK", "LOOK", "GIVE", "GET",
    "HAS", "HAD", "CAN", "DID", "DOES", "THIS", "THAT", "WITH",
    "ABOUT", "PLEASE", "HAVE", "PRICE", "VALUE", "GAIN", "CHANGE",
    "OPEN", "CLOSE", "HIGH", "LOW", "BID", "ASK", "RANGE", "COST",
    "TRADE", "VOLUME", "SHARE", "SHARES", "DAY", "WEEK", "TOTAL",
    "PERCENT", "RATIO", "YIELD", "LAST", "TODAY", "DAILY",
    "PREVIOUS", "TRADING", "WORTH", "MANY",
}


def _extract_ticker(text):
    """Look for an explicit ticker symbol (all caps, 1-5 letters)."""
    for match in re.finditer(r"\b([A-Z]{1,5})\b", text):
        candidate = match.group(1)
        if candidate not in TICKER_BLACKLIST:
            return candidate
    return None


def _extract_company(text):
    """Match a company name from the known list, longest match first."""
    lower = text.lower()
    sorted_names = sorted(COMMON_STOCKS.keys(), key=len, reverse=True)

    for name in sorted_names:
        if name in lower:
            return COMMON_STOCKS[name]

    words = lower.split()
    best_match = None
    best_len = 0
    for i in range(len(words)):
        for j in range(i + 2, len(words) + 1):
            fragment = " ".join(words[i:j])
            if len(fragment) < 5:
                continue
            for name in sorted_names:
                if name.startswith(fragment) and len(fragment) > best_len:
                    best_match = COMMON_STOCKS[name]
                    best_len = len(fragment)
    return best_match


def _extract_remaining_symbol(text):
    """After removing field-related words and stop words, whatever's left is likely the symbol."""
    cleaned = text.lower()
    for pattern, _ in FIELD_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)

    words = cleaned.split()
    remaining = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    if remaining:
        candidate = remaining[-1].upper()
        if re.match(r"^[A-Z]{1,5}$", candidate):
            return candidate
        company = _extract_company(" ".join(remaining))
        if company:
            return company

    return None


def _extract_field(text):
    """Determine which data field the user is asking about."""
    lower = text.lower()
    for pattern, field in FIELD_PATTERNS:
        if re.search(pattern, lower):
            return field
    return "summary"


def parse_query(text):
    """
    Parse a spoken query into (symbol, field).

    Returns None if no stock could be identified.
    Returns (symbol, field) where field defaults to "summary" if unclear.
    """
    if not text or not text.strip():
        return None

    field = _extract_field(text)

    symbol = _extract_company(text)
    if not symbol:
        symbol = _extract_ticker(text.upper())
    if not symbol:
        symbol = _extract_remaining_symbol(text)

    if not symbol:
        return None

    return (symbol, field)
