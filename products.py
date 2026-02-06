"""
Phantasmal Flames sealed product pricing via PriceCharting API.

PriceCharting API docs: https://www.pricecharting.com/api-documentation
- Auth: ?t=TOKEN parameter
- Prices in pennies (1732 = $17.32)
- /api/products?q=search — find products
- /api/product?id=ID — get pricing for one product
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

PC_BASE = "https://www.pricecharting.com"

# Phantasmal Flames product search terms and metadata
PRODUCT_CATALOG = [
    {
        "id": "pf-booster-box",
        "search": ["phantasmal flames booster box"],
        "name": "Booster Box",
        "description": "36 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 36,
        "type": "booster-box",
    },
    {
        "id": "pf-etb",
        "search": ["phantasmal flames elite trainer box"],
        "name": "Elite Trainer Box",
        "description": "Mega Charizard X ETB with 9 booster packs, energy cards, dice, and storage box.",
        "packs": 9,
        "type": "etb",
    },
    {
        "id": "pf-pc-etb",
        "search": ["phantasmal flames pokemon center elite trainer"],
        "name": "Pokemon Center Exclusive ETB",
        "description": "Mega Charizard X exclusive ETB with 11 packs and bonus stamped promo card.",
        "packs": 11,
        "type": "etb",
    },
    {
        "id": "pf-bundle",
        "search": ["phantasmal flames booster bundle", "phantasmal flames bundle", "mega evolution phantasmal flames bundle"],
        "name": "Booster Bundle",
        "description": "6 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 6,
        "type": "bundle",
    },
    {
        "id": "pf-build-battle",
        "search": ["phantasmal flames build and battle", "phantasmal flames build battle", "phantasmal flames prerelease"],
        "name": "Build & Battle Box",
        "description": "Pre-release kit with 4 booster packs, 23-card evolution pack, and promo card.",
        "packs": 4,
        "type": "build-battle",
    },
    {
        "id": "pf-booster-pack",
        "search": ["phantasmal flames booster pack", "phantasmal flames pack", "mega evolution phantasmal flames pack"],
        "name": "Booster Pack",
        "description": "Single booster pack with 10 cards.",
        "packs": 1,
        "type": "pack",
    },
]


def load_api_token():
    """Load PriceCharting API token from env."""
    token = os.environ.get("PRICECHARTING_TOKEN")
    if token:
        return token

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("PRICECHARTING_TOKEN="):
                    return line.split("=", 1)[1].strip()

    return None


def pc_request(endpoint, token, params=None):
    """Make a GET request to the PriceCharting API."""
    if params is None:
        params = {}
    params["t"] = token

    url = f"{PC_BASE}{endpoint}?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "PopCounts/1.0 (Pokemon TCG Sealed Product Tracker)")

    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def pennies_to_dollars(pennies):
    """Convert PriceCharting penny price to dollars."""
    if pennies and isinstance(pennies, (int, float, str)):
        try:
            return round(int(pennies) / 100, 2)
        except (ValueError, TypeError):
            pass
    return None


def search_products(token, query):
    """Search PriceCharting for products matching query."""
    data = pc_request("/api/products", token, {"q": query})
    if data.get("status") == "success":
        return data.get("products", [])
    return []


def get_product_price(token, product_id):
    """Get full pricing for a PriceCharting product ID."""
    data = pc_request("/api/product", token, {"id": product_id})
    if data.get("status") == "success":
        return data
    return None


def fetch_all_products(token):
    """Fetch live pricing for all Phantasmal Flames products.

    Returns list of product dicts with live prices.
    """
    results = []

    for catalog in PRODUCT_CATALOG:
        product = {
            "id": catalog["id"],
            "name": catalog["name"],
            "description": catalog["description"],
            "packs": catalog["packs"],
            "type": catalog["type"],
            "market_price": None,
            "new_price": None,
            "cib_price": None,
            "loose_price": None,
            "graded_price": None,
            "pc_id": None,
            "pc_url": None,
            "price_source": "not_found",
        }

        # Search PriceCharting — try multiple search terms
        search_terms = catalog["search"]
        best_match = None

        for query in search_terms:
            try:
                matches = search_products(token, query)
            except Exception:
                matches = []

            # Find best match (look for Pokemon console/category)
            for m in matches:
                name = (m.get("product-name") or "").lower()
                console = (m.get("console-name") or "").lower()
                if "pokemon" in console or "phantasmal" in name:
                    best_match = m
                    break

            # If no Pokemon-specific match, take the first result
            if not best_match and matches:
                best_match = matches[0]

            if best_match:
                break

        if best_match:
            pc_id = best_match.get("id")
            product["pc_id"] = pc_id

            # Build proper PriceCharting URL from console + product slugs
            console = best_match.get("console-name", "")
            prod_name = best_match.get("product-name", "")
            if console and prod_name:
                console_slug = console.lower().replace(" ", "-")
                name_slug = prod_name.lower().replace(" ", "-")
                product["pc_url"] = f"{PC_BASE}/game/{console_slug}/{name_slug}"
            else:
                product["pc_url"] = f"{PC_BASE}/offers?product={pc_id}"

            # Fetch full pricing
            try:
                price_data = get_product_price(token, pc_id)
                if price_data:
                    product["new_price"] = pennies_to_dollars(price_data.get("new-price"))
                    product["cib_price"] = pennies_to_dollars(price_data.get("cib-price"))
                    product["loose_price"] = pennies_to_dollars(price_data.get("loose-price"))
                    product["graded_price"] = pennies_to_dollars(price_data.get("graded-price"))

                    # Use new (sealed) price as the main market price
                    product["market_price"] = (
                        product["new_price"]
                        or product["cib_price"]
                        or product["loose_price"]
                    )
                    if product["market_price"]:
                        product["price_source"] = "pricecharting"
            except Exception:
                pass

        # Calculate per-pack cost
        if product["market_price"] and product["packs"] > 0:
            product["per_pack"] = round(product["market_price"] / product["packs"], 2)
        else:
            product["per_pack"] = 0

        results.append(product)

    return results


def get_products(token=None):
    """Return all products with pricing.

    Returns (products_list, price_source) tuple.
    """
    if token:
        try:
            products = fetch_all_products(token)
            has_live = any(p["price_source"] == "pricecharting" for p in products)
            return products, "pricecharting" if has_live else "no_data"
        except Exception:
            pass

    # No token — return catalog with no prices
    products = []
    for c in PRODUCT_CATALOG:
        products.append({
            "id": c["id"],
            "name": c["name"],
            "description": c["description"],
            "packs": c["packs"],
            "type": c["type"],
            "market_price": None,
            "new_price": None,
            "cib_price": None,
            "loose_price": None,
            "graded_price": None,
            "per_pack": 0,
            "price_source": "no_token",
            "pc_id": None,
            "pc_url": None,
        })
    return products, "no_token"


def get_product_by_id(product_id, token=None):
    """Find a single product by ID."""
    all_products, _ = get_products(token)
    for p in all_products:
        if p["id"] == product_id:
            return p
    return None
