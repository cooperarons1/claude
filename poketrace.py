"""
Poketrace API client module.
Provides reusable functions for fetching PSA pop report data
across any Pokemon TCG set.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.poketrace.com/v1"

# WOTC-era sets (Wizards of the Coast, 1999-2003)
WOTC_SLUGS = {
    "base-set", "jungle", "fossil", "base-set-2", "team-rocket",
    "gym-heroes", "gym-challenge", "neo-genesis", "neo-discovery",
    "neo-revelation", "neo-destiny", "legendary-collection",
    "expedition-base-set", "expedition", "aquapolis", "skyridge",
    "wizards-black-star-promos", "wotc-promo", "bs-promos",
    "best-of-game",
}

# Broader matching for WOTC sets by name keywords
WOTC_NAME_HINTS = [
    "base set", "jungle", "fossil", "team rocket",
    "gym heroes", "gym challenge",
    "neo genesis", "neo discovery", "neo revelation", "neo destiny",
    "legendary collection", "expedition", "aquapolis", "skyridge",
    "wizards", "best of game",
]


def load_api_key():
    """Load API key from .env file or environment variable."""
    api_key = os.environ.get("POKETRACE_API_KEY")
    if api_key:
        return api_key

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("POKETRACE_API_KEY="):
                    return line.split("=", 1)[1].strip()

    return None


def api_request(endpoint, api_key, params=None):
    """Make an authenticated GET request to the Poketrace API."""
    url = f"{API_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("X-API-Key", api_key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "PopCounts/1.0 (Pokemon TCG Pop Report App)")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"API error {e.code} on {endpoint}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error on {endpoint}: {e.reason}")


def is_wotc_set(s):
    """Check if a set dict is a WOTC-era set."""
    slug = s.get("id", s.get("slug", "")).lower()
    name = s.get("name", "").lower()

    if slug in WOTC_SLUGS:
        return True
    for hint in WOTC_NAME_HINTS:
        if hint in name:
            return True
    return False


def fetch_all_sets(api_key):
    """Fetch all available card sets."""
    data = api_request("/sets", api_key)
    if not data:
        return []
    sets = data if isinstance(data, list) else data.get("data", data.get("sets", []))
    return sets


def fetch_wotc_sets(api_key):
    """Fetch only WOTC-era sets."""
    all_sets = fetch_all_sets(api_key)
    return [s for s in all_sets if is_wotc_set(s)]


def find_set_by_id(api_key, set_id):
    """Find a specific set by its ID/slug."""
    sets = fetch_all_sets(api_key)
    for s in sets:
        sid = s.get("id", s.get("slug", ""))
        if sid == set_id:
            return s
    return None


def fetch_set_cards(api_key, set_id):
    """Fetch all cards in a set, handling cursor-based pagination."""
    all_cards = []
    cursor = None

    while True:
        params = {"set": set_id, "limit": 50, "market": "US"}
        if cursor:
            params["cursor"] = cursor

        data = api_request("/cards", api_key, params)
        if not data:
            break

        # Handle both list and dict responses
        if isinstance(data, list):
            cards = data
            has_more = False
        else:
            cards = data.get("data", data.get("cards", []))
            pagination = data.get("pagination", {})
            has_more = pagination.get("hasMore", False)
            cursor = pagination.get("nextCursor")

        if not cards:
            break

        all_cards.extend(cards)

        if not has_more or not cursor:
            break

        time.sleep(0.5)

    return all_cards


def fetch_card_detail(api_key, card_id):
    """Fetch detailed info for a single card including graded prices."""
    return api_request(f"/cards/{card_id}", api_key)


def extract_psa_grades(card_data):
    """Extract PSA grade pricing from card detail data.

    Poketrace API structure:
      data.prices.ebay.PSA_10.avg  (uppercase PSA_N keys)
    """
    grades = {}
    if not card_data:
        return grades

    detail = card_data.get("data", card_data) if isinstance(card_data, dict) else card_data
    if not isinstance(detail, dict):
        return grades

    prices = detail.get("prices", {})
    if not isinstance(prices, dict):
        return grades

    # Check each marketplace for PSA graded data
    for market_key in ("ebay", "eBay", "tcgplayer", "TCGPlayer", "cardmarket", "CardMarket"):
        market_prices = prices.get(market_key, {})
        if not isinstance(market_prices, dict):
            continue

        for grade in range(1, 11):
            if grade in grades:
                continue  # already found from a higher-priority marketplace

            # Try various key formats: PSA_10, psa_10, PSA 10, psa10
            for key_fmt in (f"PSA_{grade}", f"psa_{grade}", f"PSA {grade}", f"psa{grade}"):
                val = market_prices.get(key_fmt)
                if val is not None:
                    if isinstance(val, dict):
                        price = val.get("avg", val.get("price", val.get("value",
                                val.get("marketPrice", val.get("low")))))
                        if price is not None:
                            grades[grade] = price
                    elif isinstance(val, (int, float)):
                        grades[grade] = val
                    break

    # Fallback: check top-level keys like psa10Price, psaTenPrice
    if not grades:
        for key, val in detail.items():
            kl = key.lower()
            for grade in range(1, 11):
                if f"psa" in kl and str(grade) in kl and grade not in grades:
                    if isinstance(val, (int, float)):
                        grades[grade] = val
                    elif isinstance(val, dict):
                        p = val.get("avg", val.get("price", val.get("value")))
                        if p is not None:
                            grades[grade] = p

    return grades


def build_set_card_list(api_key, set_id):
    """Build a card list for a set (fast, no individual detail calls).

    Returns a list of dicts with basic card info from the list endpoint.
    """
    cards = fetch_set_cards(api_key, set_id)
    if not cards:
        return []

    cards_data = []
    for card in cards:
        card_id = card.get("id", card.get("cardId"))
        name = card.get("name", "Unknown")
        number = card.get("cardNumber", card.get("number", card.get("card_number", "?")))
        image = card.get("image", card.get("imageUrl", ""))
        if not image and isinstance(card.get("images"), dict):
            image = card["images"].get("small", card["images"].get("large", ""))
        rarity = card.get("rarity", "")
        variant = card.get("variant", "")
        top_price = card.get("topPrice")
        has_graded = card.get("hasGraded", False)

        try:
            sort_num = int(str(number).split("/")[0])
        except (ValueError, IndexError):
            sort_num = 999

        # Extract any graded prices already in the list response
        psa_grades = extract_psa_grades(card)

        cards_data.append({
            "id": card_id,
            "name": name,
            "number": number,
            "sort_num": sort_num,
            "image": image,
            "rarity": rarity,
            "variant": variant,
            "top_price": top_price,
            "has_graded": has_graded,
            "psa_grades": psa_grades,
        })

    cards_data.sort(key=lambda c: c["sort_num"])
    return cards_data


def fetch_card_prices(api_key, card_id):
    """Fetch PSA graded prices for a single card (for async loading)."""
    try:
        detail = fetch_card_detail(api_key, card_id)
        return extract_psa_grades(detail)
    except Exception:
        return {}
