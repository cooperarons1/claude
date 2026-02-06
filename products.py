"""
Phantasmal Flames product data and pricing.
Fetches live sealed product pricing from the Poketrace API,
with fallback to hardcoded market data.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.poketrace.com/v1"

# Search terms to find each product in the API
PRODUCT_CATALOG = [
    {
        "id": "pf-booster-box",
        "name": "Booster Box",
        "search_terms": ["phantasmal flames booster box"],
        "description": "36 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 36,
        "type": "booster-box",
        "retailers": {
            "Amazon": "https://www.amazon.com/Pokemon-TCG-Evolutions-Phantasmal-Booster/dp/B0FPLKXJZD",
            "Best Buy": "https://www.bestbuy.com/product/pokemon-trading-card-game-mega-evolution-phantasmal-flames-booster-box-36-packs/JJG2TL3XYR",
        },
        "fallback_price": 292.74,
    },
    {
        "id": "pf-etb",
        "name": "Elite Trainer Box",
        "search_terms": ["phantasmal flames elite trainer box", "phantasmal flames etb"],
        "description": "Mega Charizard X ETB with 9 booster packs, energy cards, dice, and storage box.",
        "packs": 9,
        "type": "etb",
        "retailers": {
            "Amazon": "https://www.amazon.com/s?k=phantasmal+flames+elite+trainer+box",
            "Walmart": "https://www.walmart.com/search?q=phantasmal+flames+elite+trainer+box",
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "fallback_price": 78.19,
    },
    {
        "id": "pf-pc-etb",
        "name": "Pokemon Center Exclusive ETB",
        "search_terms": ["phantasmal flames pokemon center etb", "phantasmal flames pc exclusive"],
        "description": "Mega Charizard X exclusive ETB with 11 packs and bonus stamped promo card.",
        "packs": 11,
        "type": "etb",
        "retailers": {
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "fallback_price": 192.89,
    },
    {
        "id": "pf-bundle",
        "name": "Booster Bundle",
        "search_terms": ["phantasmal flames booster bundle", "phantasmal flames bundle"],
        "description": "6 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 6,
        "type": "bundle",
        "retailers": {
            "Amazon": "https://www.amazon.com/Pok%C3%A9mon-TCG-Evolution-Phantasmal-Flames-Booster/dp/B0FPLLR939",
            "Walmart": "https://www.walmart.com/ip/POKEMON-ME2-PHANTASMAL-FLAMES-BOOSTER-BUNDLE/17785924366",
        },
        "fallback_price": 46.54,
    },
    {
        "id": "pf-build-battle",
        "name": "Build & Battle Box",
        "search_terms": ["phantasmal flames build battle", "phantasmal flames prerelease"],
        "description": "Pre-release kit with 4 booster packs, 23-card evolution pack, and promo card.",
        "packs": 4,
        "type": "build-battle",
        "retailers": {},
        "fallback_price": 53.03,
    },
    {
        "id": "pf-booster-pack",
        "name": "Booster Pack",
        "search_terms": ["phantasmal flames booster pack"],
        "description": "Single booster pack with 10 cards.",
        "packs": 1,
        "type": "pack",
        "retailers": {
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "fallback_price": 7.68,
    },
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
    req.add_header("User-Agent", "PopCounts/1.0 (Pokemon TCG Sealed Product Tracker)")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"_error": f"HTTP {e.code}", "_body": body}
    except urllib.error.URLError as e:
        return {"_error": f"Network: {e.reason}"}


def _extract_price(data):
    """Try to extract a price from an API response item."""
    if not isinstance(data, dict):
        return None

    # Direct price fields
    for key in ("price", "marketPrice", "market_price", "topPrice",
                "avgPrice", "avg_price", "value", "currentPrice"):
        val = data.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return val

    # Nested prices object
    prices = data.get("prices", {})
    if isinstance(prices, dict):
        # Check tcgplayer market price
        for market in ("tcgplayer", "TCGPlayer", "ebay", "eBay"):
            mp = prices.get(market, {})
            if isinstance(mp, dict):
                for pk in ("marketPrice", "market_price", "price", "avg", "value"):
                    val = mp.get(pk)
                    if isinstance(val, (int, float)) and val > 0:
                        return val
                # Check for NEAR_MINT or similar
                for condition in ("NEAR_MINT", "near_mint", "NM"):
                    cp = mp.get(condition, {})
                    if isinstance(cp, dict):
                        for pk in ("price", "avg", "marketPrice", "value"):
                            val = cp.get(pk)
                            if isinstance(val, (int, float)) and val > 0:
                                return val

    return None


def _extract_image(data):
    """Try to extract an image URL from an API response item."""
    if not isinstance(data, dict):
        return ""
    for key in ("image", "imageUrl", "image_url", "thumbnail"):
        val = data.get(key)
        if val and isinstance(val, str):
            return val
    images = data.get("images", {})
    if isinstance(images, dict):
        return images.get("small", images.get("large", images.get("thumbnail", "")))
    return ""


def probe_api(api_key):
    """Probe the Poketrace API to discover sealed product data.

    Tries multiple endpoint patterns and search strategies.
    Returns a dict with raw results for debugging.
    """
    results = {}

    # 1. Try dedicated sealed/products endpoints
    for endpoint in ("/sealed-products", "/products", "/sealed"):
        data = api_request(endpoint, api_key, {"search": "phantasmal flames"})
        results[f"GET {endpoint}"] = data
        if not data.get("_error"):
            break
        time.sleep(0.3)

    # 2. Search cards endpoint for sealed products
    for search in ("phantasmal flames booster box", "phantasmal flames"):
        data = api_request("/cards", api_key, {
            "search": search,
            "market": "US",
            "limit": 10,
        })
        results[f"GET /cards?search={search}"] = data
        time.sleep(0.3)

    # 3. Find the set first
    sets_data = api_request("/sets", api_key)
    results["GET /sets (filtered)"] = None
    if sets_data and not sets_data.get("_error"):
        sets_list = sets_data if isinstance(sets_data, list) else sets_data.get("data", sets_data.get("sets", []))
        pf_sets = [s for s in sets_list if "phantasmal" in s.get("name", "").lower()
                    or "phantasmal" in s.get("id", s.get("slug", "")).lower()]
        results["GET /sets (filtered)"] = pf_sets

        # If we found the set, try to get its products
        for pf_set in pf_sets:
            set_id = pf_set.get("id", pf_set.get("slug"))
            if set_id:
                # Try products for this set
                for endpoint in (f"/sets/{set_id}/products", f"/sets/{set_id}/sealed"):
                    data = api_request(endpoint, api_key)
                    results[f"GET {endpoint}"] = data
                    time.sleep(0.3)

                # Also try cards with set filter
                data = api_request("/cards", api_key, {
                    "set": set_id,
                    "market": "US",
                    "limit": 5,
                })
                results[f"GET /cards?set={set_id}"] = data
                time.sleep(0.3)

    return results


def fetch_live_prices(api_key):
    """Try to fetch live prices from the Poketrace API.

    Returns a dict mapping product search terms to prices found.
    """
    prices = {}

    # Try the sealed products endpoint first
    for endpoint in ("/sealed-products", "/products", "/sealed"):
        data = api_request(endpoint, api_key, {"search": "phantasmal flames", "limit": 20})
        if data and not data.get("_error"):
            items = data if isinstance(data, list) else data.get("data", data.get("products", []))
            if isinstance(items, list):
                for item in items:
                    name = (item.get("name") or "").lower()
                    price = _extract_price(item)
                    image = _extract_image(item)
                    if price:
                        prices[name] = {"price": price, "image": image, "raw": item}
            if prices:
                return prices
        time.sleep(0.3)

    # Fallback: search cards endpoint for each product
    for catalog_item in PRODUCT_CATALOG:
        for term in catalog_item["search_terms"]:
            data = api_request("/cards", api_key, {
                "search": term,
                "market": "US",
                "limit": 5,
            })
            if data and not data.get("_error"):
                items = data if isinstance(data, list) else data.get("data", data.get("cards", []))
                if isinstance(items, list):
                    for item in items:
                        price = _extract_price(item)
                        image = _extract_image(item)
                        if price:
                            prices[catalog_item["id"]] = {"price": price, "image": image, "raw": item}
                            break
                if catalog_item["id"] in prices:
                    break
            time.sleep(0.3)

    return prices


def _match_price(product_id, product_name, live_prices):
    """Try to match a catalog product to a live price."""
    # Direct ID match
    if product_id in live_prices:
        return live_prices[product_id]

    # Fuzzy name match
    name_lower = product_name.lower()
    for api_name, data in live_prices.items():
        if not isinstance(api_name, str):
            continue
        # Check if key product words appear
        if "booster box" in name_lower and "booster box" in api_name:
            if "bundle" not in api_name:
                return data
        elif "elite trainer" in name_lower and ("elite trainer" in api_name or "etb" in api_name):
            if "pokemon center" in name_lower and "pokemon center" in api_name:
                return data
            elif "pokemon center" not in name_lower and "pokemon center" not in api_name:
                return data
        elif "bundle" in name_lower and "bundle" in api_name:
            return data
        elif "build" in name_lower and ("build" in api_name or "battle" in api_name):
            return data
        elif "booster pack" in name_lower and "booster pack" in api_name:
            if "box" not in api_name and "bundle" not in api_name:
                return data

    return None


def get_products(api_key=None):
    """Return products with live prices from API (or fallback).

    Returns (products_list, price_source) tuple.
    """
    live_prices = {}
    price_source = "fallback"

    if api_key:
        try:
            live_prices = fetch_live_prices(api_key)
            if live_prices:
                price_source = "poketrace_api"
        except Exception:
            pass

    products = []
    for p in PRODUCT_CATALOG:
        product = {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "packs": p["packs"],
            "type": p["type"],
            "retailers": p["retailers"],
            "image": "",
        }

        # Try live price first
        match = _match_price(p["id"], p["name"], live_prices)
        if match:
            product["market_price"] = match["price"]
            product["image"] = match.get("image", "")
            product["price_source"] = "live"
        else:
            product["market_price"] = p["fallback_price"]
            product["price_source"] = "fallback"

        price = product["market_price"]
        packs = product["packs"]
        product["per_pack"] = round(price / packs, 2) if packs > 0 else 0
        products.append(product)

    return products, price_source


def get_product_by_id(product_id, api_key=None):
    """Find a single product by ID with live pricing."""
    all_products, _ = get_products(api_key)
    for p in all_products:
        if p["id"] == product_id:
            return p
    return None
