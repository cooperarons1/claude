"""
Phantasmal Flames product data and pricing.
Sealed product catalog with live price fetching from Poketrace API
and fallback to known market data.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.poketrace.com/v1"

# Phantasmal Flames sealed product catalog
PRODUCTS = [
    {
        "id": "pf-booster-box",
        "name": "Booster Box",
        "description": "36 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 36,
        "type": "booster-box",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/booster-box.png",
        "retailers": {
            "Amazon": "https://www.amazon.com/Pokemon-TCG-Evolutions-Phantasmal-Booster/dp/B0FPLKXJZD",
            "Best Buy": "https://www.bestbuy.com/product/pokemon-trading-card-game-mega-evolution-phantasmal-flames-booster-box-36-packs/JJG2TL3XYR",
        },
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/booster-box",
        "market_price": 292.74,
    },
    {
        "id": "pf-etb",
        "name": "Elite Trainer Box",
        "description": "Mega Charizard X ETB with 9 booster packs, energy cards, dice, and storage box.",
        "packs": 9,
        "type": "etb",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/etb.png",
        "retailers": {
            "Amazon": "https://www.amazon.com/s?k=phantasmal+flames+elite+trainer+box",
            "Walmart": "https://www.walmart.com/search?q=phantasmal+flames+elite+trainer+box",
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/elite-trainer-box",
        "market_price": 78.19,
    },
    {
        "id": "pf-pc-etb",
        "name": "Pokemon Center Exclusive ETB",
        "description": "Mega Charizard X exclusive ETB with 11 packs and bonus stamped promo card.",
        "packs": 11,
        "type": "etb",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/pc-etb.png",
        "retailers": {
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/elite-trainer-box",
        "market_price": 192.89,
    },
    {
        "id": "pf-bundle",
        "name": "Booster Bundle",
        "description": "6 booster packs of Mega Evolution — Phantasmal Flames.",
        "packs": 6,
        "type": "bundle",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/booster-bundle.png",
        "retailers": {
            "Amazon": "https://www.amazon.com/Pok%C3%A9mon-TCG-Evolution-Phantasmal-Flames-Booster/dp/B0FPLLR939",
            "Walmart": "https://www.walmart.com/ip/POKEMON-ME2-PHANTASMAL-FLAMES-BOOSTER-BUNDLE/17785924366",
        },
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/booster-bundle",
        "market_price": 46.54,
    },
    {
        "id": "pf-build-battle",
        "name": "Build & Battle Box",
        "description": "Pre-release kit with 4 booster packs, 23-card evolution pack, and promo card.",
        "packs": 4,
        "type": "build-battle",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/build-battle.png",
        "retailers": {},
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/build-and-battle-box",
        "market_price": 53.03,
    },
    {
        "id": "pf-booster-pack",
        "name": "Booster Pack",
        "description": "Single booster pack with 10 cards.",
        "packs": 1,
        "type": "pack",
        "image": "https://tcg.pokemon.com/assets/img/expansions/phantasmal-flames/booster-pack.png",
        "retailers": {
            "Pokemon Center": "https://www.pokemoncenter.com/category/phantasmal-flames",
        },
        "pricecharting": "https://www.pricecharting.com/game/pokemon-phantasmal-flames/booster-pack",
        "market_price": 7.68,
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
        raise RuntimeError(f"API error {e.code} on {endpoint}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error on {endpoint}: {e.reason}")


def get_products():
    """Return the product catalog with per-pack pricing calculated."""
    products = []
    for p in PRODUCTS:
        product = dict(p)
        price = product["market_price"]
        packs = product["packs"]
        product["per_pack"] = round(price / packs, 2) if packs > 0 else 0
        products.append(product)
    return products


def get_product_by_id(product_id):
    """Find a single product by its ID."""
    for p in PRODUCTS:
        if p["id"] == product_id:
            product = dict(p)
            price = product["market_price"]
            packs = product["packs"]
            product["per_pack"] = round(price / packs, 2) if packs > 0 else 0
            return product
    return None
