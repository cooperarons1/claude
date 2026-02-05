#!/usr/bin/env python3
"""
Pokemon Card Vending Machine - Pricing Model with SKU Tracking

Uses the Poketrace API to fetch live market prices for Pokemon cards
and sealed products (booster boxes, ETBs, tins, bundles) and manages
a vending machine inventory with configurable pricing strategies.

Usage:
    python vending_machine.py                   # Interactive menu
    python vending_machine.py add <card_id>     # Add a card SKU
    python vending_machine.py addbox <set_id>   # Add a sealed box SKU
    python vending_machine.py list              # List all SKUs
    python vending_machine.py refresh           # Update all prices
    python vending_machine.py report            # Full pricing report
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse

API_BASE = "https://api.poketrace.com/v1"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vending_inventory.json")


# ---------------------------------------------------------------------------
# Poketrace API layer
# ---------------------------------------------------------------------------

def load_api_key():
    """Load API key from environment or .env file."""
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

    print("Error: POKETRACE_API_KEY not found.")
    print("Set it in .env or as an environment variable.")
    sys.exit(1)


def api_request(endpoint, api_key, params=None):
    """Make an authenticated GET request to the Poketrace API."""
    url = f"{API_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("X-API-Key", api_key)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  API error {e.code} on {endpoint}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  Network error on {endpoint}: {e.reason}")
        return None


def search_cards(api_key, query, market="US"):
    """Search for cards by name via the Poketrace API."""
    all_cards = []
    params = {"search": query, "market": market, "limit": 50}
    data = api_request("/cards", api_key, params)
    if not data:
        return all_cards

    cards = data if isinstance(data, list) else data.get("data", data.get("cards", []))
    all_cards.extend(cards)
    return all_cards


def fetch_card_detail(api_key, card_id):
    """Fetch full detail for a card including current market prices."""
    data = api_request(f"/cards/{card_id}", api_key)
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else data


def fetch_price_history(api_key, card_id, tier="raw"):
    """Fetch historical price data for a card from the Poketrace API.

    Tier can be 'raw', 'psa-9', 'psa-10', etc.
    """
    data = api_request(f"/cards/{card_id}/prices/{tier}/history", api_key)
    if not data:
        return []
    return data if isinstance(data, list) else data.get("data", data.get("history", []))


def extract_market_price(card_data):
    """Pull the current market price from card detail data."""
    if not card_data or not isinstance(card_data, dict):
        return None

    # Try common price locations in the response
    prices = card_data.get("prices", card_data.get("market", {}))
    if isinstance(prices, dict):
        # Try raw / ungraded price first
        for key in ("raw", "ungraded", "market", "tcgplayer", "average"):
            val = prices.get(key)
            if isinstance(val, dict):
                val = val.get("price", val.get("market", val.get("value")))
            if isinstance(val, (int, float)):
                return float(val)

        # Try any numeric price field
        for val in prices.values():
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict):
                for sub in ("price", "market", "value", "mid"):
                    if isinstance(val.get(sub), (int, float)):
                        return float(val[sub])

    # Top-level price field
    for key in ("price", "marketPrice", "value"):
        val = card_data.get(key)
        if isinstance(val, (int, float)):
            return float(val)

    return None


def extract_graded_prices(card_data):
    """Extract graded (PSA) prices from card detail data."""
    graded = {}
    if not card_data or not isinstance(card_data, dict):
        return graded

    prices = card_data.get("prices", card_data.get("graded", {}))
    if isinstance(prices, dict):
        psa = prices.get("psa", prices.get("PSA", {}))
        if isinstance(psa, dict):
            for grade in range(1, 11):
                key = str(grade)
                if key in psa:
                    val = psa[key]
                    if isinstance(val, dict):
                        val = val.get("price", val.get("value", val.get("marketPrice")))
                    if isinstance(val, (int, float)):
                        graded[grade] = float(val)
    return graded


# ---------------------------------------------------------------------------
# Box / sealed product support
# ---------------------------------------------------------------------------

BOX_TYPES = {
    "booster_box": {"label": "Booster Box", "packs": 36, "cards_per_pack": 10},
    "etb": {"label": "Elite Trainer Box", "packs": 8, "cards_per_pack": 10},
    "booster_bundle": {"label": "Booster Bundle", "packs": 6, "cards_per_pack": 10},
    "tin": {"label": "Collector Tin", "packs": 4, "cards_per_pack": 10},
    "collection_box": {"label": "Collection Box", "packs": 4, "cards_per_pack": 10},
    "blister_3pack": {"label": "3-Pack Blister", "packs": 3, "cards_per_pack": 10},
    "blister_1pack": {"label": "1-Pack Blister", "packs": 1, "cards_per_pack": 10},
    "custom": {"label": "Custom Box", "packs": 0, "cards_per_pack": 0},
}


def fetch_set_info(api_key, set_id):
    """Fetch set metadata from Poketrace."""
    data = api_request(f"/sets", api_key)
    if not data:
        return None

    sets = data if isinstance(data, list) else data.get("data", data.get("sets", []))
    for s in sets:
        sid = s.get("id", s.get("slug", ""))
        if sid == set_id or s.get("name", "").lower() == set_id.lower():
            return s
    return None


def estimate_box_value(api_key, set_id, box_type_key="booster_box"):
    """Estimate a sealed box's value based on its set's card market prices.

    Fetches all cards in the set, computes average card value, and multiplies
    by the number of cards in the box type. This gives a rough floor estimate.
    """
    box_info = BOX_TYPES.get(box_type_key, BOX_TYPES["booster_box"])
    total_cards = box_info["packs"] * box_info["cards_per_pack"]
    if total_cards == 0:
        return None, {}

    all_cards = []
    page = 1
    while True:
        params = {"set": set_id, "limit": 50}
        if page > 1:
            params["page"] = page
        data = api_request("/cards", api_key, params)
        if not data:
            break
        cards = data if isinstance(data, list) else data.get("data", data.get("cards", []))
        if not cards:
            break
        all_cards.extend(cards)
        total = data.get("totalCount", data.get("total")) if isinstance(data, dict) else None
        if total and len(all_cards) >= total:
            break
        if len(cards) < 50:
            break
        page += 1
        time.sleep(0.5)

    if not all_cards:
        return None, {}

    prices = []
    for card in all_cards:
        p = extract_market_price(card)
        if p is not None:
            prices.append(p)

    stats = {}
    if prices:
        prices.sort()
        stats["card_count"] = len(all_cards)
        stats["priced_cards"] = len(prices)
        stats["avg_card_price"] = round(sum(prices) / len(prices), 2)
        stats["median_card_price"] = round(prices[len(prices) // 2], 2)
        stats["min_card_price"] = round(prices[0], 2)
        stats["max_card_price"] = round(prices[-1], 2)
        stats["total_cards_in_box"] = total_cards
        # Estimate: average card price * number of cards in box
        estimated = round(stats["avg_card_price"] * total_cards, 2)
        return estimated, stats

    return None, stats


def add_box_sku(inventory, api_key, set_id, box_type="booster_box", quantity=1,
                strategy="percentage_margin", pricing_config=None, manual_price=None):
    """Add a sealed Pokemon box product as a vending machine SKU.

    The SKU ID is formatted as 'box-<set_id>-<box_type>'.
    Market price can be set manually or estimated from set card values.
    """
    sku_id = f"box-{set_id}-{box_type}"
    existing = find_sku(inventory, sku_id)
    if existing:
        existing["quantity"] += quantity
        print(f"  SKU {sku_id} already exists — increased quantity to {existing['quantity']}.")
        return existing

    box_info = BOX_TYPES.get(box_type, BOX_TYPES["custom"])
    label = f"{box_info['label']}"

    # Get set info for the name
    set_info = fetch_set_info(api_key, set_id)
    set_name = set_id
    if set_info and isinstance(set_info, dict):
        set_name = set_info.get("name", set_id)

    product_name = f"{set_name} {label}"

    # Determine market price
    market_price = manual_price
    box_stats = {}
    if market_price is None:
        print(f"  Estimating box value from set card prices...")
        market_price, box_stats = estimate_box_value(api_key, set_id, box_type)

    sku = {
        "sku_id": sku_id,
        "sku_type": "box",
        "card_name": product_name,
        "card_number": "",
        "card_set": set_name,
        "box_type": box_type,
        "box_info": box_info,
        "box_stats": box_stats,
        "quantity": quantity,
        "market_price": market_price,
        "graded_prices": {},
        "vend_price": None,
        "pricing_strategy": strategy,
        "pricing_config": pricing_config or _default_config(strategy),
        "price_history": [],
        "added_at": _now(),
        "last_updated": _now(),
    }

    if market_price is not None:
        sku["price_history"].append({"date": _now(), "price": market_price})

    sku["vend_price"] = calc_vend_price(sku)
    inventory["skus"].append(sku)
    return sku


def refresh_box_price(sku, api_key):
    """Refresh the estimated price for a box SKU."""
    set_id = sku["sku_id"].replace("box-", "", 1)
    # Remove the box_type suffix
    box_type = sku.get("box_type", "booster_box")
    suffix = f"-{box_type}"
    if set_id.endswith(suffix):
        set_id = set_id[:-len(suffix)]

    estimated, stats = estimate_box_value(api_key, set_id, box_type)
    if estimated is not None:
        sku["market_price"] = estimated
        sku["box_stats"] = stats
    return estimated


# ---------------------------------------------------------------------------
# Pricing strategies
# ---------------------------------------------------------------------------

PRICING_STRATEGIES = {
    "fixed_markup": "Apply a fixed dollar markup over market price",
    "percentage_margin": "Apply a percentage margin over market price",
    "dynamic": "Adjust price based on market trend (rising = higher margin)",
    "floor_ceiling": "Market-based with min/max price bounds",
}


def calc_vend_price(sku, strategy=None):
    """Calculate the vending price for an SKU using its pricing strategy.

    Returns the computed vend price or None if market data is unavailable.
    """
    strategy = strategy or sku.get("pricing_strategy", "percentage_margin")
    market_price = sku.get("market_price")
    if market_price is None:
        return sku.get("vend_price")

    config = sku.get("pricing_config", {})

    if strategy == "fixed_markup":
        markup = config.get("markup", 1.00)
        return round(market_price + markup, 2)

    if strategy == "percentage_margin":
        margin = config.get("margin_pct", 25)
        return round(market_price * (1 + margin / 100), 2)

    if strategy == "dynamic":
        base_margin = config.get("base_margin_pct", 20)
        history = sku.get("price_history", [])
        if len(history) >= 2:
            recent = history[-1].get("price", market_price)
            older = history[-2].get("price", market_price)
            if older and older > 0:
                change_pct = ((recent - older) / older) * 100
                # Rising prices -> add extra margin; falling -> reduce margin
                adjusted = base_margin + (change_pct * 0.5)
                adjusted = max(5, min(adjusted, 50))  # clamp 5-50%
                return round(market_price * (1 + adjusted / 100), 2)
        return round(market_price * (1 + base_margin / 100), 2)

    if strategy == "floor_ceiling":
        margin = config.get("margin_pct", 20)
        floor = config.get("floor_price", 0.50)
        ceiling = config.get("ceiling_price", 999.99)
        price = round(market_price * (1 + margin / 100), 2)
        return max(floor, min(price, ceiling))

    # Fallback: 25% margin
    return round(market_price * 1.25, 2)


# ---------------------------------------------------------------------------
# Inventory persistence
# ---------------------------------------------------------------------------

def load_inventory():
    """Load vending machine inventory from disk."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"skus": [], "metadata": {"created": _now(), "last_refresh": None}}


def save_inventory(inventory):
    """Persist vending machine inventory to disk."""
    with open(DATA_FILE, "w") as f:
        json.dump(inventory, f, indent=2)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_sku(inventory, sku_id):
    """Find an SKU by its ID (card_id)."""
    for s in inventory["skus"]:
        if s["sku_id"] == sku_id:
            return s
    return None


# ---------------------------------------------------------------------------
# SKU management
# ---------------------------------------------------------------------------

def add_sku(inventory, api_key, card_id, quantity=1, strategy="percentage_margin",
            pricing_config=None):
    """Add a card as a vending machine SKU.

    Fetches current market data from Poketrace and initializes the SKU.
    """
    existing = find_sku(inventory, card_id)
    if existing:
        existing["quantity"] += quantity
        print(f"  SKU {card_id} already exists — increased quantity to {existing['quantity']}.")
        return existing

    print(f"  Fetching card data for {card_id}...")
    detail = fetch_card_detail(api_key, card_id)
    if not detail:
        print(f"  Warning: Could not fetch data for {card_id}. Adding with no market price.")

    market_price = extract_market_price(detail) if detail else None
    graded_prices = extract_graded_prices(detail) if detail else {}

    card_name = ""
    card_number = ""
    card_set = ""
    if detail and isinstance(detail, dict):
        card_name = detail.get("name", "")
        card_number = detail.get("number", detail.get("cardNumber", ""))
        card_set = detail.get("set", detail.get("setId", ""))
        if isinstance(card_set, dict):
            card_set = card_set.get("name", card_set.get("id", ""))

    sku = {
        "sku_id": card_id,
        "sku_type": "card",
        "card_name": card_name,
        "card_number": card_number,
        "card_set": card_set,
        "quantity": quantity,
        "market_price": market_price,
        "graded_prices": graded_prices,
        "vend_price": None,
        "pricing_strategy": strategy,
        "pricing_config": pricing_config or _default_config(strategy),
        "price_history": [],
        "added_at": _now(),
        "last_updated": _now(),
    }

    # Record initial price snapshot
    if market_price is not None:
        sku["price_history"].append({"date": _now(), "price": market_price})

    sku["vend_price"] = calc_vend_price(sku)
    inventory["skus"].append(sku)
    return sku


def _default_config(strategy):
    """Return default pricing config for a strategy."""
    if strategy == "fixed_markup":
        return {"markup": 1.00}
    if strategy == "percentage_margin":
        return {"margin_pct": 25}
    if strategy == "dynamic":
        return {"base_margin_pct": 20}
    if strategy == "floor_ceiling":
        return {"margin_pct": 20, "floor_price": 0.50, "ceiling_price": 999.99}
    return {"margin_pct": 25}


def remove_sku(inventory, sku_id):
    """Remove an SKU from the vending machine."""
    before = len(inventory["skus"])
    inventory["skus"] = [s for s in inventory["skus"] if s["sku_id"] != sku_id]
    removed = before - len(inventory["skus"])
    return removed > 0


def refresh_prices(inventory, api_key):
    """Refresh market prices for all SKUs from Poketrace."""
    updated = 0
    for sku in inventory["skus"]:
        card_id = sku["sku_id"]
        old_price = sku.get("market_price")

        # Box SKUs use set-based estimation instead of card detail
        if sku.get("sku_type") == "box":
            new_price = refresh_box_price(sku, api_key)
            graded = {}
        else:
            detail = fetch_card_detail(api_key, card_id)
            if not detail:
                print(f"  Could not refresh {card_id} ({sku.get('card_name', '')}).")
                continue
            new_price = extract_market_price(detail)
            graded = extract_graded_prices(detail)

        sku["market_price"] = new_price
        sku["graded_prices"] = graded
        sku["last_updated"] = _now()

        if new_price is not None:
            sku["price_history"].append({"date": _now(), "price": new_price})
            # Keep last 90 data points
            if len(sku["price_history"]) > 90:
                sku["price_history"] = sku["price_history"][-90:]

        sku["vend_price"] = calc_vend_price(sku)

        direction = ""
        if old_price is not None and new_price is not None:
            if new_price > old_price:
                direction = " (+)"
            elif new_price < old_price:
                direction = " (-)"

        label = sku.get("card_name") or card_id
        if new_price is not None:
            price_str = f"${new_price:.2f}"
        else:
            price_str = "N/A"
        vend_str = f" -> vend ${sku['vend_price']:.2f}" if sku.get("vend_price") else ""
        print(f"  {label}: {price_str}{vend_str}{direction}")
        updated += 1
        time.sleep(0.3)

    inventory["metadata"]["last_refresh"] = _now()
    return updated


def set_sku_strategy(inventory, sku_id, strategy, config=None):
    """Change the pricing strategy for an SKU."""
    sku = find_sku(inventory, sku_id)
    if not sku:
        return False
    sku["pricing_strategy"] = strategy
    sku["pricing_config"] = config or _default_config(strategy)
    sku["vend_price"] = calc_vend_price(sku)
    return True


def set_sku_quantity(inventory, sku_id, quantity):
    """Update stock quantity for an SKU."""
    sku = find_sku(inventory, sku_id)
    if not sku:
        return False
    sku["quantity"] = max(0, quantity)
    return True


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_inventory(inventory):
    """Print a formatted inventory listing."""
    skus = inventory["skus"]
    if not skus:
        print("  Vending machine is empty. Use 'add' to stock cards.")
        return

    hdr = (f"{'SKU ID':<28} {'Name':<26} {'Set':<14} {'Type':<5} "
           f"{'Qty':>4} {'Market':>9} {'Vend':>9} {'Margin':>7} {'Strategy':<18}")
    print("=" * len(hdr))
    print("  VENDING MACHINE INVENTORY")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    total_market = 0.0
    total_vend = 0.0
    total_qty = 0

    for sku in sorted(skus, key=lambda s: s.get("card_name", "")):
        sid = sku["sku_id"][:27]
        name = (sku.get("card_name") or "Unknown")[:25]
        card_set = (sku.get("card_set") or "")[:13]
        sku_type = (sku.get("sku_type") or "card")[:4]
        qty = sku.get("quantity", 0)
        mp = sku.get("market_price")
        vp = sku.get("vend_price")
        strat = sku.get("pricing_strategy", "")

        mp_str = f"${mp:,.2f}" if mp is not None else "--"
        vp_str = f"${vp:,.2f}" if vp is not None else "--"

        margin_str = "--"
        if mp and vp and mp > 0:
            margin_pct = ((vp - mp) / mp) * 100
            margin_str = f"{margin_pct:+.1f}%"

        print(f"{sid:<28} {name:<26} {card_set:<14} {sku_type:<5} "
              f"{qty:>4} {mp_str:>9} {vp_str:>9} {margin_str:>7} {strat:<18}")

        if mp:
            total_market += mp * qty
        if vp:
            total_vend += vp * qty
        total_qty += qty

    print("-" * len(hdr))
    print(f"  Total SKUs: {len(skus)}  |  Total Stock: {total_qty}  |  "
          f"Market Value: ${total_market:,.2f}  |  Vend Value: ${total_vend:,.2f}")
    if total_market > 0:
        overall_margin = ((total_vend - total_market) / total_market) * 100
        print(f"  Overall Margin: {overall_margin:+.1f}%")

    last = inventory["metadata"].get("last_refresh")
    print(f"  Last price refresh: {last or 'never'}")
    print()


def print_sku_detail(sku):
    """Print detailed info for a single SKU."""
    sku_type = sku.get("sku_type", "card")
    print(f"\n  SKU Detail: {sku['sku_id']}")
    print(f"  {'Type:':<18} {sku_type}")
    print(f"  {'Name:':<18} {sku.get('card_name', 'Unknown')}")
    if sku_type == "card":
        print(f"  {'Number:':<18} {sku.get('card_number', '?')}")
    else:
        box_type = sku.get("box_type", "?")
        box_info = BOX_TYPES.get(box_type, {})
        print(f"  {'Box Type:':<18} {box_info.get('label', box_type)}")
        print(f"  {'Packs:':<18} {box_info.get('packs', '?')}")
        print(f"  {'Cards/Pack:':<18} {box_info.get('cards_per_pack', '?')}")
    print(f"  {'Set:':<18} {sku.get('card_set', '?')}")
    print(f"  {'Quantity:':<18} {sku.get('quantity', 0)}")
    print(f"  {'Market Price:':<18} "
          f"{'$'+format(sku['market_price'], ',.2f') if sku.get('market_price') is not None else 'N/A'}")
    print(f"  {'Vend Price:':<18} "
          f"{'$'+format(sku['vend_price'], ',.2f') if sku.get('vend_price') is not None else 'N/A'}")
    print(f"  {'Strategy:':<18} {sku.get('pricing_strategy', 'N/A')}")
    print(f"  {'Config:':<18} {json.dumps(sku.get('pricing_config', {}))}")
    print(f"  {'Added:':<18} {sku.get('added_at', '?')}")
    print(f"  {'Last Updated:':<18} {sku.get('last_updated', '?')}")

    graded = sku.get("graded_prices", {})
    if graded:
        print(f"  {'Graded Prices:':<18}")
        for g in sorted(graded.keys(), key=lambda x: int(x)):
            print(f"    PSA {g:>2}: ${graded[g]:,.2f}")

    box_stats = sku.get("box_stats", {})
    if box_stats:
        print(f"  {'Box Valuation:':<18}")
        print(f"    Cards in set:    {box_stats.get('card_count', '?')}")
        print(f"    Priced cards:    {box_stats.get('priced_cards', '?')}")
        print(f"    Avg card price:  ${box_stats.get('avg_card_price', 0):,.2f}")
        print(f"    Median card:     ${box_stats.get('median_card_price', 0):,.2f}")
        print(f"    Min card:        ${box_stats.get('min_card_price', 0):,.2f}")
        print(f"    Max card:        ${box_stats.get('max_card_price', 0):,.2f}")
        print(f"    Cards in box:    {box_stats.get('total_cards_in_box', '?')}")

    history = sku.get("price_history", [])
    if history:
        print(f"  {'Price History:':<18} ({len(history)} data points)")
        for entry in history[-5:]:
            print(f"    {entry['date'][:19]}  ${entry['price']:,.2f}")
        if len(history) > 5:
            print(f"    ... and {len(history) - 5} earlier entries")
    print()


def print_pricing_report(inventory):
    """Print a comprehensive pricing analysis report."""
    skus = inventory["skus"]
    if not skus:
        print("  No SKUs in inventory.")
        return

    print("=" * 80)
    print("  VENDING MACHINE - PRICING ANALYSIS REPORT")
    print(f"  Generated: {_now()[:19]}")
    print("=" * 80)

    # Summary by SKU type
    cards = [s for s in skus if s.get("sku_type", "card") == "card"]
    boxes = [s for s in skus if s.get("sku_type") == "box"]
    print(f"\n  SKU Type Breakdown:  {len(cards)} card(s)  |  {len(boxes)} box(es)  |  {len(skus)} total")

    # Summary by strategy
    by_strategy = {}
    for sku in skus:
        strat = sku.get("pricing_strategy", "unknown")
        by_strategy.setdefault(strat, []).append(sku)

    print("\n  Pricing Strategy Breakdown:")
    print(f"  {'Strategy':<22} {'SKUs':>5} {'Avg Market':>12} {'Avg Vend':>12} {'Avg Margin':>11}")
    print("  " + "-" * 62)
    for strat, items in sorted(by_strategy.items()):
        market_prices = [s["market_price"] for s in items if s.get("market_price")]
        vend_prices = [s["vend_price"] for s in items if s.get("vend_price")]
        avg_m = sum(market_prices) / len(market_prices) if market_prices else 0
        avg_v = sum(vend_prices) / len(vend_prices) if vend_prices else 0
        avg_margin = ((avg_v - avg_m) / avg_m * 100) if avg_m > 0 else 0
        print(f"  {strat:<22} {len(items):>5} "
              f"{'$'+format(avg_m,',.2f'):>12} {'$'+format(avg_v,',.2f'):>12} "
              f"{avg_margin:>+10.1f}%")

    # Top 5 highest value SKUs
    priced = [s for s in skus if s.get("vend_price")]
    priced.sort(key=lambda s: s["vend_price"], reverse=True)
    print(f"\n  Top {min(5, len(priced))} Highest Priced SKUs:")
    for s in priced[:5]:
        print(f"    ${s['vend_price']:>8,.2f}  {s.get('card_name','?'):<30} ({s['sku_id']})")

    # Price movement summary
    movers = []
    for sku in skus:
        hist = sku.get("price_history", [])
        if len(hist) >= 2:
            old_p = hist[-2]["price"]
            new_p = hist[-1]["price"]
            if old_p and old_p > 0:
                change = ((new_p - old_p) / old_p) * 100
                movers.append((sku, change))

    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        print("\n  Recent Price Movements:")
        for sku, change in movers[:5]:
            direction = "+" if change >= 0 else ""
            print(f"    {direction}{change:.1f}%  {sku.get('card_name','?'):<30} ({sku['sku_id']})")

    # Stock value
    total_cost = sum((s.get("market_price", 0) or 0) * s.get("quantity", 0) for s in skus)
    total_revenue = sum((s.get("vend_price", 0) or 0) * s.get("quantity", 0) for s in skus)
    total_items = sum(s.get("quantity", 0) for s in skus)
    print(f"\n  Inventory Valuation:")
    print(f"    Total items in stock:   {total_items}")
    print(f"    Total cost (market):    ${total_cost:,.2f}")
    print(f"    Total revenue (vend):   ${total_revenue:,.2f}")
    print(f"    Projected profit:       ${total_revenue - total_cost:,.2f}")
    if total_cost > 0:
        print(f"    ROI:                    {((total_revenue - total_cost) / total_cost) * 100:+.1f}%")
    print("=" * 80)
    print()


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def interactive_menu(api_key, inventory):
    """Run the interactive vending machine management CLI."""
    print("\n  Pokemon Card Vending Machine - Pricing Model")
    print("  Powered by Poketrace API")
    print("  Type 'help' for commands.\n")

    while True:
        try:
            cmd = input("vending> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0].lower()

        if action in ("quit", "exit", "q"):
            break

        elif action == "help":
            print_help()

        elif action == "list":
            print_inventory(inventory)

        elif action == "add":
            if len(parts) < 2:
                print("  Usage: add <card_id> [quantity] [strategy]")
                print("  Strategies: fixed_markup, percentage_margin, dynamic, floor_ceiling")
                continue
            card_id = parts[1]
            qty = int(parts[2]) if len(parts) > 2 else 1
            strat = parts[3] if len(parts) > 3 else "percentage_margin"
            sku = add_sku(inventory, api_key, card_id, quantity=qty, strategy=strat)
            save_inventory(inventory)
            print(f"  Added: {sku.get('card_name') or card_id}")
            if sku.get("vend_price"):
                print(f"  Market: ${sku['market_price']:.2f}  ->  Vend: ${sku['vend_price']:.2f}")

        elif action == "addbox":
            if len(parts) < 2:
                print("  Usage: addbox <set_id> [box_type] [quantity] [strategy] [manual_price]")
                print("  Box types: booster_box, etb, booster_bundle, tin, collection_box,")
                print("             blister_3pack, blister_1pack, custom")
                continue
            set_id = parts[1]
            btype = parts[2] if len(parts) > 2 else "booster_box"
            qty = int(parts[3]) if len(parts) > 3 else 1
            strat = parts[4] if len(parts) > 4 else "percentage_margin"
            mprice = float(parts[5]) if len(parts) > 5 else None
            sku = add_box_sku(inventory, api_key, set_id, box_type=btype,
                              quantity=qty, strategy=strat, manual_price=mprice)
            save_inventory(inventory)
            print(f"  Added box: {sku.get('card_name') or set_id}")
            if sku.get("market_price") is not None:
                mp_str = f"${sku['market_price']:.2f}"
            else:
                mp_str = "N/A (set manual price with: stock <sku_id> ...)"
            vp_str = f"${sku['vend_price']:.2f}" if sku.get("vend_price") else "N/A"
            print(f"  Market: {mp_str}  ->  Vend: {vp_str}")
            stats = sku.get("box_stats", {})
            if stats:
                print(f"  Estimated from {stats.get('priced_cards', 0)} cards "
                      f"(avg ${stats.get('avg_card_price', 0):.2f}/card)")

        elif action == "boxtypes":
            print("\n  Available Box Types:")
            for key, info in BOX_TYPES.items():
                total = info["packs"] * info["cards_per_pack"]
                print(f"    {key:<18} {info['label']:<22} "
                      f"{info['packs']} packs x {info['cards_per_pack']} cards = {total} cards")
            print()

        elif action == "remove":
            if len(parts) < 2:
                print("  Usage: remove <sku_id>")
                continue
            if remove_sku(inventory, parts[1]):
                save_inventory(inventory)
                print(f"  Removed SKU {parts[1]}.")
            else:
                print(f"  SKU {parts[1]} not found.")

        elif action == "detail":
            if len(parts) < 2:
                print("  Usage: detail <sku_id>")
                continue
            sku = find_sku(inventory, parts[1])
            if sku:
                print_sku_detail(sku)
            else:
                print(f"  SKU {parts[1]} not found.")

        elif action == "refresh":
            print("  Refreshing prices from Poketrace...")
            count = refresh_prices(inventory, api_key)
            save_inventory(inventory)
            print(f"  Updated {count} SKU(s).")

        elif action == "search":
            if len(parts) < 2:
                print("  Usage: search <card_name>")
                continue
            query = " ".join(parts[1:])
            print(f"  Searching Poketrace for '{query}'...")
            results = search_cards(api_key, query)
            if not results:
                print("  No results found.")
            else:
                print(f"  Found {len(results)} card(s):")
                for c in results[:20]:
                    cid = c.get("id", c.get("cardId", "?"))
                    cname = c.get("name", "?")
                    cset = c.get("set", c.get("setId", ""))
                    if isinstance(cset, dict):
                        cset = cset.get("name", cset.get("id", ""))
                    print(f"    {cid:<30} {cname:<28} {cset}")

        elif action == "strategy":
            if len(parts) < 3:
                print("  Usage: strategy <sku_id> <strategy_name>")
                print("  Strategies: fixed_markup, percentage_margin, dynamic, floor_ceiling")
                continue
            if set_sku_strategy(inventory, parts[1], parts[2]):
                save_inventory(inventory)
                sku = find_sku(inventory, parts[1])
                print(f"  Strategy set to '{parts[2]}' for {parts[1]}.")
                if sku and sku.get("vend_price"):
                    print(f"  New vend price: ${sku['vend_price']:.2f}")
            else:
                print(f"  SKU {parts[1]} not found.")

        elif action == "stock":
            if len(parts) < 3:
                print("  Usage: stock <sku_id> <quantity>")
                continue
            try:
                qty = int(parts[2])
            except ValueError:
                print("  Quantity must be a number.")
                continue
            if set_sku_quantity(inventory, parts[1], qty):
                save_inventory(inventory)
                print(f"  Stock updated: {parts[1]} -> {qty}")
            else:
                print(f"  SKU {parts[1]} not found.")

        elif action == "report":
            print_pricing_report(inventory)

        elif action == "history":
            if len(parts) < 2:
                print("  Usage: history <sku_id> [tier]")
                print("  Tier examples: raw, psa-9, psa-10")
                continue
            tier = parts[2] if len(parts) > 2 else "raw"
            print(f"  Fetching price history for {parts[1]} (tier: {tier})...")
            hist = fetch_price_history(api_key, parts[1], tier)
            if not hist:
                print("  No history available.")
            else:
                entries = hist if isinstance(hist, list) else [hist]
                for entry in entries[-20:]:
                    if isinstance(entry, dict):
                        date = entry.get("date", entry.get("timestamp", "?"))
                        price = entry.get("price", entry.get("value", "?"))
                        print(f"    {date}  ${price}")
                    else:
                        print(f"    {entry}")

        elif action == "export":
            path = parts[1] if len(parts) > 1 else "vending_export.json"
            export = {
                "exported_at": _now(),
                "total_skus": len(inventory["skus"]),
                "skus": [],
            }
            for sku in inventory["skus"]:
                export["skus"].append({
                    "sku_id": sku["sku_id"],
                    "card_name": sku.get("card_name"),
                    "card_set": sku.get("card_set"),
                    "quantity": sku.get("quantity", 0),
                    "market_price": sku.get("market_price"),
                    "vend_price": sku.get("vend_price"),
                    "strategy": sku.get("pricing_strategy"),
                    "margin": (
                        round(((sku["vend_price"] - sku["market_price"]) / sku["market_price"]) * 100, 1)
                        if sku.get("vend_price") and sku.get("market_price") and sku["market_price"] > 0
                        else None
                    ),
                })
            export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
            with open(export_path, "w") as f:
                json.dump(export, f, indent=2)
            print(f"  Exported to {export_path}")

        else:
            print(f"  Unknown command: {action}. Type 'help' for commands.")

    save_inventory(inventory)
    print("  Inventory saved. Goodbye.")


def print_help():
    """Print CLI help."""
    print("""
  Commands:
    list                              Show all SKUs in the vending machine
    add <card_id> [qty] [strat]       Add a card SKU (fetches price from Poketrace)
    addbox <set_id> [type] [qty]      Add a sealed box product
              [strat] [manual_price]
    boxtypes                          List available box types
    remove <sku_id>                   Remove an SKU
    detail <sku_id>                   Show detailed SKU info
    search <card_name>                Search Poketrace for cards by name
    refresh                           Update all SKU prices from Poketrace
    strategy <sku_id> <strategy>      Change pricing strategy for an SKU
    stock <sku_id> <quantity>         Update stock quantity
    report                            Full pricing analysis report
    history <sku_id> [tier]           Fetch price history (tier: raw, psa-9, psa-10)
    export [filename]                 Export inventory to JSON
    help                              Show this help
    quit                              Exit

  Box Types:
    booster_box       36 packs (360 cards)    etb              8 packs (80 cards)
    booster_bundle     6 packs (60 cards)     tin              4 packs (40 cards)
    collection_box     4 packs (40 cards)     blister_3pack    3 packs (30 cards)
    blister_1pack      1 pack  (10 cards)     custom           manual entry

  Pricing Strategies:
    fixed_markup          Fixed dollar amount above market price (default $1.00)
    percentage_margin     Percentage markup over market (default 25%)
    dynamic               Auto-adjust margin based on price trends
    floor_ceiling         Percentage margin with min/max price bounds
""")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    api_key = load_api_key()
    inventory = load_inventory()

    if len(sys.argv) < 2:
        interactive_menu(api_key, inventory)
        return

    action = sys.argv[1].lower()

    if action == "add":
        if len(sys.argv) < 3:
            print("Usage: vending_machine.py add <card_id> [quantity] [strategy]")
            sys.exit(1)
        card_id = sys.argv[2]
        qty = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        strat = sys.argv[4] if len(sys.argv) > 4 else "percentage_margin"
        sku = add_sku(inventory, api_key, card_id, quantity=qty, strategy=strat)
        save_inventory(inventory)
        print(f"Added: {sku.get('card_name') or card_id}")
        if sku.get("vend_price"):
            print(f"Market: ${sku['market_price']:.2f}  ->  Vend: ${sku['vend_price']:.2f}")

    elif action == "addbox":
        if len(sys.argv) < 3:
            print("Usage: vending_machine.py addbox <set_id> [box_type] [quantity] [strategy] [manual_price]")
            sys.exit(1)
        set_id = sys.argv[2]
        btype = sys.argv[3] if len(sys.argv) > 3 else "booster_box"
        qty = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        strat = sys.argv[5] if len(sys.argv) > 5 else "percentage_margin"
        mprice = float(sys.argv[6]) if len(sys.argv) > 6 else None
        sku = add_box_sku(inventory, api_key, set_id, box_type=btype,
                          quantity=qty, strategy=strat, manual_price=mprice)
        save_inventory(inventory)
        print(f"Added box: {sku.get('card_name') or set_id}")
        if sku.get("vend_price"):
            print(f"Market: ${sku['market_price']:.2f}  ->  Vend: ${sku['vend_price']:.2f}")

    elif action == "remove":
        if len(sys.argv) < 3:
            print("Usage: vending_machine.py remove <sku_id>")
            sys.exit(1)
        if remove_sku(inventory, sys.argv[2]):
            save_inventory(inventory)
            print(f"Removed SKU {sys.argv[2]}.")
        else:
            print(f"SKU {sys.argv[2]} not found.")

    elif action == "list":
        print_inventory(inventory)

    elif action == "refresh":
        print("Refreshing prices from Poketrace...")
        count = refresh_prices(inventory, api_key)
        save_inventory(inventory)
        print(f"Updated {count} SKU(s).")

    elif action == "report":
        print_pricing_report(inventory)

    elif action == "search":
        query = " ".join(sys.argv[2:])
        print(f"Searching for '{query}'...")
        results = search_cards(api_key, query)
        for c in results[:20]:
            cid = c.get("id", "?")
            cname = c.get("name", "?")
            print(f"  {cid:<30} {cname}")

    elif action == "export":
        path = sys.argv[2] if len(sys.argv) > 2 else "vending_export.json"
        save_inventory(inventory)
        print(f"Exported to {path}")

    else:
        print(f"Unknown command: {action}")
        print("Commands: add, addbox, remove, list, refresh, report, search, export")
        sys.exit(1)


if __name__ == "__main__":
    main()
