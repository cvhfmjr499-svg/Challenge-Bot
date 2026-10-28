"""Asset classes. Crypto uses yfinance symbols like BTC-USD and trades 24/7."""

CRYPTO = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "LTC", "DOT", "SUI20947"]


def is_crypto(symbol):
    return symbol.upper().endswith("-USD")


def normalize(symbol):
    """'btc' -> 'BTC-USD', 'sui' -> 'SUI20947-USD', stocks unchanged."""
    s = symbol.upper()
    if s == "SUI":
        s = "SUI20947"
    return f"{s}-USD" if s in CRYPTO else s
