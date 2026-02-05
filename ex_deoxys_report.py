#!/usr/bin/env python3
"""
EX Deoxys Full Set Report
Combines Poketrace pricing data with PSA pop counts for every card variant
in the EX Deoxys set (regular, holo, reverse holo).

Requires both API keys in .env:
  POKETRACE_API_KEY=<key>
  PSA_API_TOKEN=<token>
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse

POKETRACE_BASE = "https://api.poketrace.com/v1"
PSA_API_BASE = "https://api.psacard.com/publicapi"

# EX Deoxys full set: 107 cards + 4 secret rares (108/107 through 111/107)
# Card variants: Regular, Holo Rare, Reverse Holo, EX (full art holo)
EX_DEOXYS_CARDS = [
    # --- Common ---
    {"num": 1, "name": "Baltoy", "rarity": "Common", "has_reverse": True},
    {"num": 2, "name": "Carvanha", "rarity": "Common", "has_reverse": True},
    {"num": 3, "name": "Corphish", "rarity": "Common", "has_reverse": True},
    {"num": 4, "name": "Electrike", "rarity": "Common", "has_reverse": True},
    {"num": 5, "name": "Gulpin", "rarity": "Common", "has_reverse": True},
    {"num": 6, "name": "Lotad", "rarity": "Common", "has_reverse": True},
    {"num": 7, "name": "Makuhita", "rarity": "Common", "has_reverse": True},
    {"num": 8, "name": "Mudkip", "rarity": "Common", "has_reverse": True},
    {"num": 9, "name": "Numel", "rarity": "Common", "has_reverse": True},
    {"num": 10, "name": "Pikachu", "rarity": "Common", "has_reverse": True},
    {"num": 11, "name": "Poochyena", "rarity": "Common", "has_reverse": True},
    {"num": 12, "name": "Ralts", "rarity": "Common", "has_reverse": True},
    {"num": 13, "name": "Shroomish", "rarity": "Common", "has_reverse": True},
    {"num": 14, "name": "Slugma", "rarity": "Common", "has_reverse": True},
    {"num": 15, "name": "Spoink", "rarity": "Common", "has_reverse": True},
    {"num": 16, "name": "Taillow", "rarity": "Common", "has_reverse": True},
    {"num": 17, "name": "Zubat", "rarity": "Common", "has_reverse": True},
    # --- Uncommon ---
    {"num": 18, "name": "Breloom", "rarity": "Uncommon", "has_reverse": True},
    {"num": 19, "name": "Cacturne", "rarity": "Uncommon", "has_reverse": True},
    {"num": 20, "name": "Claydol", "rarity": "Uncommon", "has_reverse": True},
    {"num": 21, "name": "Combusken", "rarity": "Uncommon", "has_reverse": True},
    {"num": 22, "name": "Crawdaunt", "rarity": "Uncommon", "has_reverse": True},
    {"num": 23, "name": "Gloom", "rarity": "Uncommon", "has_reverse": True},
    {"num": 24, "name": "Golbat", "rarity": "Uncommon", "has_reverse": True},
    {"num": 25, "name": "Golduck", "rarity": "Uncommon", "has_reverse": True},
    {"num": 26, "name": "Grumpig", "rarity": "Uncommon", "has_reverse": True},
    {"num": 27, "name": "Hariyama", "rarity": "Uncommon", "has_reverse": True},
    {"num": 28, "name": "Kirlia", "rarity": "Uncommon", "has_reverse": True},
    {"num": 29, "name": "Lombre", "rarity": "Uncommon", "has_reverse": True},
    {"num": 30, "name": "Manectric", "rarity": "Uncommon", "has_reverse": True},
    {"num": 31, "name": "Marshtomp", "rarity": "Uncommon", "has_reverse": True},
    {"num": 32, "name": "Mightyena", "rarity": "Uncommon", "has_reverse": True},
    {"num": 33, "name": "Minun", "rarity": "Uncommon", "has_reverse": True},
    {"num": 34, "name": "Ninjask", "rarity": "Uncommon", "has_reverse": True},
    {"num": 35, "name": "Plusle", "rarity": "Uncommon", "has_reverse": True},
    {"num": 36, "name": "Shedinja", "rarity": "Uncommon", "has_reverse": True},
    {"num": 37, "name": "Shiftry", "rarity": "Uncommon", "has_reverse": True},
    {"num": 38, "name": "Silcoon", "rarity": "Uncommon", "has_reverse": True},
    {"num": 39, "name": "Swalot", "rarity": "Uncommon", "has_reverse": True},
    {"num": 40, "name": "Swellow", "rarity": "Uncommon", "has_reverse": True},
    {"num": 41, "name": "Tropius", "rarity": "Uncommon", "has_reverse": True},
    {"num": 42, "name": "Volbeat", "rarity": "Uncommon", "has_reverse": True},
    # --- Rare ---
    {"num": 43, "name": "Altaria", "rarity": "Rare", "has_reverse": True},
    {"num": 44, "name": "Beautifly", "rarity": "Rare", "has_reverse": True},
    {"num": 45, "name": "Blaziken", "rarity": "Rare", "has_reverse": True},
    {"num": 46, "name": "Camerupt", "rarity": "Rare", "has_reverse": True},
    {"num": 47, "name": "Gardevoir", "rarity": "Rare", "has_reverse": True},
    {"num": 48, "name": "Gyarados", "rarity": "Rare", "has_reverse": True},
    {"num": 49, "name": "Jirachi", "rarity": "Rare", "has_reverse": True},
    {"num": 50, "name": "Ludicolo", "rarity": "Rare", "has_reverse": True},
    {"num": 51, "name": "Lunatone", "rarity": "Rare", "has_reverse": True},
    {"num": 52, "name": "Magcargo", "rarity": "Rare", "has_reverse": True},
    {"num": 53, "name": "Mightyena", "rarity": "Rare", "has_reverse": True},
    {"num": 54, "name": "Nosepass", "rarity": "Rare", "has_reverse": True},
    {"num": 55, "name": "Raichu", "rarity": "Rare", "has_reverse": True},
    {"num": 56, "name": "Salamence", "rarity": "Rare", "has_reverse": True},
    {"num": 57, "name": "Sharpedo", "rarity": "Rare", "has_reverse": True},
    {"num": 58, "name": "Solrock", "rarity": "Rare", "has_reverse": True},
    {"num": 59, "name": "Starmie", "rarity": "Rare", "has_reverse": True},
    {"num": 60, "name": "Swampert", "rarity": "Rare", "has_reverse": True},
    {"num": 61, "name": "Vileplume", "rarity": "Rare", "has_reverse": True},
    # --- Holo Rare ---
    {"num": 62, "name": "Altaria", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 63, "name": "Beautifly", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 64, "name": "Crobat", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 65, "name": "Dusclops", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 66, "name": "Gardevoir", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 67, "name": "Gyarados", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 68, "name": "Ludicolo", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 69, "name": "Metagross", "rarity": "Holo Rare", "has_reverse": True},
    {"num": 70, "name": "Salamence", "rarity": "Holo Rare", "has_reverse": True},
    # --- Rare EX ---
    {"num": 71, "name": "Crobat ex", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 72, "name": "Deoxys ex (Normal)", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 73, "name": "Deoxys ex (Attack)", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 74, "name": "Deoxys ex (Defense)", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 75, "name": "Deoxys ex (Speed)", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 76, "name": "Hariyama ex", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 77, "name": "Manectric ex", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 78, "name": "Rayquaza ex", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 79, "name": "Salamence ex", "rarity": "Rare Holo EX", "has_reverse": False},
    {"num": 80, "name": "Sharpedo ex", "rarity": "Rare Holo EX", "has_reverse": False},
    # --- Trainers ---
    {"num": 81, "name": "Crystal Shard", "rarity": "Uncommon", "has_reverse": True},
    {"num": 82, "name": "Meteor Falls", "rarity": "Uncommon", "has_reverse": True},
    {"num": 83, "name": "Professor Birch", "rarity": "Uncommon", "has_reverse": True},
    {"num": 84, "name": "Professor Cozmo's Discovery", "rarity": "Uncommon", "has_reverse": True},
    {"num": 85, "name": "Rare Candy", "rarity": "Uncommon", "has_reverse": True},
    {"num": 86, "name": "Space Center", "rarity": "Uncommon", "has_reverse": True},
    {"num": 87, "name": "Strength Charm", "rarity": "Uncommon", "has_reverse": True},
    # --- Energy ---
    {"num": 88, "name": "Boost Energy", "rarity": "Uncommon", "has_reverse": True},
    {"num": 89, "name": "Double Rainbow Energy", "rarity": "Rare", "has_reverse": True},
    {"num": 90, "name": "Scramble Energy", "rarity": "Uncommon", "has_reverse": True},
    # --- Additional Pokemon (cards 91-107) ---
    {"num": 91, "name": "Cacnea", "rarity": "Common", "has_reverse": True},
    {"num": 92, "name": "Duskull", "rarity": "Common", "has_reverse": True},
    {"num": 93, "name": "Magikarp", "rarity": "Common", "has_reverse": True},
    {"num": 94, "name": "Nincada", "rarity": "Common", "has_reverse": True},
    {"num": 95, "name": "Oddish", "rarity": "Common", "has_reverse": True},
    {"num": 96, "name": "Psyduck", "rarity": "Common", "has_reverse": True},
    {"num": 97, "name": "Seedot", "rarity": "Common", "has_reverse": True},
    {"num": 98, "name": "Staryu", "rarity": "Common", "has_reverse": True},
    {"num": 99, "name": "Swablu", "rarity": "Common", "has_reverse": True},
    {"num": 100, "name": "Torchic", "rarity": "Common", "has_reverse": True},
    {"num": 101, "name": "Bagon", "rarity": "Common", "has_reverse": True},
    {"num": 102, "name": "Beldum", "rarity": "Common", "has_reverse": True},
    {"num": 103, "name": "Metang", "rarity": "Uncommon", "has_reverse": True},
    {"num": 104, "name": "Shelgon", "rarity": "Uncommon", "has_reverse": True},
    {"num": 105, "name": "Wurmple", "rarity": "Common", "has_reverse": True},
    {"num": 106, "name": "Nuzleaf", "rarity": "Uncommon", "has_reverse": True},
    {"num": 107, "name": "Dusclops", "rarity": "Uncommon", "has_reverse": True},
    # --- Secret Rares ---
    {"num": 108, "name": "Latias Gold Star", "rarity": "Secret Rare", "has_reverse": False},
    {"num": 109, "name": "Latios Gold Star", "rarity": "Secret Rare", "has_reverse": False},
    {"num": 110, "name": "Rayquaza Gold Star", "rarity": "Secret Rare", "has_reverse": False},
    {"num": 111, "name": "Rocket's Raikou ex", "rarity": "Secret Rare", "has_reverse": False},
]


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def load_env():
    """Load API keys from .env file or environment variables."""
    env = {}
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip()

    poketrace_key = os.environ.get("POKETRACE_API_KEY", env.get("POKETRACE_API_KEY"))
    psa_token = os.environ.get("PSA_API_TOKEN", env.get("PSA_API_TOKEN"))

    if not poketrace_key:
        print("Error: POKETRACE_API_KEY not found in .env or environment.")
        sys.exit(1)

    return poketrace_key, psa_token


# ---------------------------------------------------------------------------
# Poketrace API (pricing)
# ---------------------------------------------------------------------------

def poketrace_request(endpoint, api_key, params=None):
    """Make an authenticated GET request to the Poketrace API."""
    url = f"{POKETRACE_BASE}{endpoint}"
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
        print(f"  Poketrace API error {e.code} on {endpoint}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  Poketrace network error on {endpoint}: {e.reason}")
        return None


def fetch_poketrace_cards(api_key):
    """Fetch all EX Deoxys cards from Poketrace with pricing."""
    # Try to find the set
    data = poketrace_request("/sets", api_key)
    set_id = None
    if data:
        sets = data if isinstance(data, list) else data.get("data", data.get("sets", []))
        for s in sets:
            name = s.get("name", "").lower()
            slug = s.get("id", s.get("slug", "")).lower()
            if "deoxys" in name or "deoxys" in slug:
                set_id = s.get("id", s.get("slug"))
                break

    if not set_id:
        set_id = "ex-deoxys"

    # Fetch cards with pagination
    all_cards = []
    page = 1
    while True:
        params = {"set": set_id, "limit": 50}
        if page > 1:
            params["page"] = page

        data = poketrace_request("/cards", api_key, params)
        if not data:
            break

        cards = data if isinstance(data, list) else data.get("data", data.get("cards", []))
        if not cards:
            break

        all_cards.extend(cards)

        total = None
        if isinstance(data, dict):
            total = data.get("totalCount", data.get("total"))
        if total and len(all_cards) >= total:
            break
        if len(cards) < 50:
            break

        page += 1
        time.sleep(0.5)

    # Try alternate IDs if needed
    if not all_cards:
        for alt_id in ["ex-deoxys", "deoxys", "EX Deoxys", "dx"]:
            params = {"set": alt_id, "limit": 50}
            data = poketrace_request("/cards", api_key, params)
            if data:
                cards = data if isinstance(data, list) else data.get("data", data.get("cards", []))
                if cards:
                    all_cards = cards
                    break
            time.sleep(0.3)

    return all_cards


def extract_psa_prices(card_data):
    """Extract PSA grade pricing from Poketrace card data."""
    grades = {}
    if not card_data or not isinstance(card_data, dict):
        return grades

    detail = card_data.get("data", card_data)
    prices = detail.get("prices", detail.get("graded", {}))
    if isinstance(prices, dict):
        psa = prices.get("psa", prices.get("PSA", {}))
        if isinstance(psa, dict):
            for grade in range(1, 11):
                key = str(grade)
                if key in psa:
                    val = psa[key]
                    if isinstance(val, dict):
                        grades[grade] = val.get("price", val.get("value", val.get("marketPrice")))
                    else:
                        grades[grade] = val

    # Fallback: look for psa-prefixed keys
    if not grades:
        for key, val in detail.items():
            if "psa" in key.lower() and "10" in key:
                grades[10] = val
            elif "psa" in key.lower() and "9" in key:
                grades[9] = val

    return grades


def match_poketrace_to_card(poketrace_cards, card_num, variant):
    """Try to match a Poketrace card entry to a specific card number + variant."""
    for c in poketrace_cards:
        number = str(c.get("number", c.get("cardNumber", ""))).split("/")[0].strip()
        try:
            num_int = int(number)
        except ValueError:
            continue

        if num_int != card_num:
            continue

        name = c.get("name", "").lower()
        card_variant = c.get("variant", c.get("type", "")).lower()

        if variant == "Reverse Holo":
            if "reverse" in name or "reverse" in card_variant:
                return c
        elif variant == "Holo":
            if ("holo" in name or "holo" in card_variant) and "reverse" not in name and "reverse" not in card_variant:
                return c
        else:
            # Regular — skip if it's explicitly a variant
            if "reverse" not in name and "reverse" not in card_variant:
                return c

    return None


# ---------------------------------------------------------------------------
# PSA API (pop counts)
# ---------------------------------------------------------------------------

def psa_api_request(endpoint, token):
    """Make an authenticated GET request to the PSA Card API."""
    url = f"{PSA_API_BASE}{endpoint}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"_error": e.code, "_body": body}
    except urllib.error.URLError as e:
        return {"_error": "network", "_body": str(e.reason)}


def test_psa_pop_access(token):
    """
    Test whether we can reach PSA pop endpoints.
    Tries several known/possible pop endpoint patterns.
    Returns (endpoint_pattern, test_data) on success, or (None, None).
    """
    # Known PSA public API pop endpoint patterns to try
    pop_endpoints = [
        "/pop/GetCollectiblePop/1",
        "/pop/GetItemPop/1",
        "/pop/GetSetItems/1",
        "/pop/GetPopReport/1",
        "/pop/GetSetInfo/1",
    ]

    for endpoint in pop_endpoints:
        print(f"  Trying PSA endpoint: {endpoint} ...")
        data = psa_api_request(endpoint, token)
        if data and "_error" not in data:
            print(f"  Found working pop endpoint: {endpoint}")
            return endpoint, data
        elif data and data.get("_error") == 404:
            # Endpoint exists but item not found — still a valid endpoint
            continue
        elif data and data.get("_error") in (401, 403):
            print(f"  PSA pop endpoint returned {data['_error']} - auth issue.")
            return None, None
        time.sleep(0.3)

    return None, None


def fetch_psa_pop_for_cert(token, cert_number):
    """Fetch PSA cert data (includes grade) for a cert number."""
    return psa_api_request(f"/cert/GetByCertNumber/{cert_number}", token)


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def build_variant_list():
    """Build the full list of card variants for the EX Deoxys set."""
    variants = []
    for card in EX_DEOXYS_CARDS:
        # Regular / Holo version
        variants.append({
            "num": card["num"],
            "name": card["name"],
            "rarity": card["rarity"],
            "variant": "Holo" if "Holo" in card["rarity"] else "Regular",
            "prices": {},
            "pop_counts": {},
        })
        # Reverse Holo version
        if card["has_reverse"]:
            variants.append({
                "num": card["num"],
                "name": card["name"],
                "rarity": card["rarity"],
                "variant": "Reverse Holo",
                "prices": {},
                "pop_counts": {},
            })
    return variants


def fmt_price(val):
    """Format a price value for display."""
    if val is None:
        return "--"
    if isinstance(val, (int, float)):
        return f"${val:,.0f}"
    return str(val)


def print_pricing_report(variants):
    """Print the pricing report section."""
    grades_to_show = [5, 6, 7, 8, 9, 10]

    header = f"{'#':<5} {'Card Name':<28} {'Variant':<14} {'Rarity':<16}"
    for g in grades_to_show:
        header += f"{'PSA '+str(g):>9}"
    width = len(header)

    print()
    print("=" * width)
    print("  EX DEOXYS - PSA GRADED PRICING REPORT (via Poketrace)")
    print("=" * width)
    print(header)
    print("-" * width)

    current_rarity = None
    for v in variants:
        if v["rarity"] != current_rarity:
            current_rarity = v["rarity"]
            if v != variants[0]:
                print()

        num_str = str(v["num"])
        row = f"{num_str:<5} {v['name']:<28} {v['variant']:<14} {v['rarity']:<16}"
        for g in grades_to_show:
            row += f"{fmt_price(v['prices'].get(g)):>9}"
        print(row)

    print("-" * width)
    total_with_prices = sum(1 for v in variants if v["prices"])
    print(f"Total variants: {len(variants)} | With pricing data: {total_with_prices}")
    print()


def print_pop_report(variants):
    """Print the PSA pop count report section."""
    grades_to_show = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    header = f"{'#':<5} {'Card Name':<28} {'Variant':<14}"
    for g in grades_to_show:
        header += f"{'PSA '+str(g):>7}"
    header += f"{'Total':>8}"
    width = len(header)

    print("=" * width)
    print("  EX DEOXYS - PSA POPULATION COUNTS")
    print("=" * width)
    print(header)
    print("-" * width)

    for v in variants:
        pop = v.get("pop_counts", {})
        if not pop:
            continue
        num_str = str(v["num"])
        row = f"{num_str:<5} {v['name']:<28} {v['variant']:<14}"
        total = 0
        for g in grades_to_show:
            count = pop.get(g, pop.get(str(g), 0))
            if count:
                total += int(count)
            row += f"{count or '--':>7}"
        row += f"{total:>8}"
        print(row)

    print("-" * width)
    total_with_pop = sum(1 for v in variants if v.get("pop_counts"))
    print(f"Variants with pop data: {total_with_pop}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    poketrace_key, psa_token = load_env()
    print("API keys loaded.")
    if not psa_token:
        print("Note: PSA_API_TOKEN not set - will skip pop counts.")
    print()

    # Build full variant list
    variants = build_variant_list()
    print(f"EX Deoxys set: {len(EX_DEOXYS_CARDS)} cards, {len(variants)} total variants (including reverse holos)")

    # --- Phase 1: Poketrace pricing ---
    print("\n--- Phase 1: Fetching pricing from Poketrace ---")
    poketrace_cards = fetch_poketrace_cards(poketrace_key)

    if poketrace_cards:
        print(f"Got {len(poketrace_cards)} cards from Poketrace. Fetching details...")

        # Fetch individual card details for pricing
        card_details = {}
        for i, c in enumerate(poketrace_cards):
            card_id = c.get("id", c.get("cardId"))
            if card_id and card_id not in card_details:
                detail = poketrace_request(f"/cards/{card_id}", poketrace_key)
                if detail:
                    card_details[card_id] = detail
                if (i + 1) % 10 == 0:
                    print(f"  Fetched details for {i + 1}/{len(poketrace_cards)} cards...")
                time.sleep(0.3)

        # Match pricing to variants
        for v in variants:
            matched = match_poketrace_to_card(poketrace_cards, v["num"], v["variant"])
            if matched:
                card_id = matched.get("id", matched.get("cardId"))
                detail = card_details.get(card_id, matched)
                v["prices"] = extract_psa_prices(detail)

        matched_count = sum(1 for v in variants if v["prices"])
        print(f"Matched pricing for {matched_count}/{len(variants)} variants.")
    else:
        print("Could not fetch cards from Poketrace. Continuing with card list only.")

    print_pricing_report(variants)

    # --- Phase 2: PSA pop counts ---
    if not psa_token:
        print("Skipping PSA pop counts (no PSA_API_TOKEN).")
        print("Add PSA_API_TOKEN=<token> to .env to enable pop counts.")
    else:
        print("--- Phase 2: Checking PSA API for pop counts ---")

        # Test if we can access pop endpoints at all
        pop_endpoint, test_data = test_psa_pop_access(psa_token)

        if not pop_endpoint:
            print()
            print("STOPPING: Could not access PSA pop count endpoints.")
            print("The PSA public API may not expose pop data, or auth may be insufficient.")
            print("Cert lookups still work — pop counts require different API access.")
            print()
            print("Pricing report above is still valid (sourced from Poketrace).")
        else:
            print(f"PSA pop endpoint available: {pop_endpoint}")
            print("Fetching pop counts for all variants...")

            for i, v in enumerate(variants):
                # Build a query for this specific card
                # PSA API pop data typically needs a spec number or item ID
                # We'll try the endpoint pattern discovered above
                endpoint = pop_endpoint.rsplit("/", 1)[0] + f"/{v['num']}"
                data = psa_api_request(endpoint, psa_token)

                if data and "_error" not in data:
                    # Try to extract grade counts from response
                    pop = data if isinstance(data, dict) else {}
                    if "PSAPop" in pop:
                        pop = pop["PSAPop"]
                    grades = {}
                    for grade in range(1, 11):
                        for key_pattern in [str(grade), f"PSA {grade}", f"psa{grade}", f"grade{grade}"]:
                            if key_pattern in pop:
                                grades[grade] = pop[key_pattern]
                                break
                    v["pop_counts"] = grades

                if (i + 1) % 20 == 0:
                    print(f"  Processed {i + 1}/{len(variants)} variants...")
                time.sleep(0.3)

            pop_count = sum(1 for v in variants if v["pop_counts"])
            if pop_count > 0:
                print_pop_report(variants)
            else:
                print("No pop count data was returned by the PSA API.")
                print("STOPPING pop count collection — endpoint may not serve item-level data.")

    # --- Save combined output ---
    output = []
    for v in variants:
        entry = {
            "number": v["num"],
            "name": v["name"],
            "rarity": v["rarity"],
            "variant": v["variant"],
        }
        if v["prices"]:
            entry["psa_prices"] = {f"PSA {k}": v for k, v in v["prices"].items()}
        if v.get("pop_counts"):
            entry["psa_pop"] = {f"PSA {k}": v for k, v in v["pop_counts"].items()}
        output.append(entry)

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ex_deoxys_full_report.json")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Full data saved to {output_file}")


if __name__ == "__main__":
    main()
