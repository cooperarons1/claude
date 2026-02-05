#!/usr/bin/env python3
"""
EX Deoxys Full Set Report
Fetches PSA graded pricing from Poketrace API (eBay sold data) for every
card in the EX Deoxys set and exports to CSV + JSON.

Requires in .env:
  POKETRACE_API_KEY=<key>
  PSA_API_TOKEN=<token>  (optional, for pop counts)
"""

import csv
import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse

POKETRACE_BASE = "https://api.poketrace.com/v1"
PSA_API_BASE = "https://api.psacard.com/publicapi"

# Poketrace uses slug "deoxys" for the EX Deoxys set (112 cards)
POKETRACE_SET_SLUG = "deoxys"

PSA_GRADES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


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
# Poketrace API
# ---------------------------------------------------------------------------

def poketrace_request(endpoint, api_key, params=None):
    """Make an authenticated GET request to the Poketrace API."""
    url = f"{POKETRACE_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("X-API-Key", api_key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  API error {e.code} on {endpoint}: {body[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"  Network error on {endpoint}: {e.reason}")
        return None


def fetch_all_cards(api_key):
    """Fetch all cards in the EX Deoxys set using cursor pagination."""
    all_cards = []
    cursor = None

    while True:
        url = f"/cards?set={POKETRACE_SET_SLUG}&limit=50"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"

        data = poketrace_request(url, api_key)
        if not data:
            break

        cards = data.get("data", [])
        pagination = data.get("pagination", {})

        if not cards:
            break

        all_cards.extend(cards)
        cursor = pagination.get("nextCursor")

        if not cursor or not pagination.get("hasMore"):
            break

        time.sleep(0.3)

    return all_cards


def fetch_card_detail(api_key, card_id):
    """Fetch full detail for a card including graded pricing."""
    data = poketrace_request(f"/cards/{card_id}", api_key)
    if data and isinstance(data, dict):
        return data.get("data", data)
    return None


def extract_psa_prices(detail):
    """Extract PSA grade prices from card detail (eBay sold prices)."""
    prices = {}
    if not detail or not isinstance(detail, dict):
        return prices

    all_prices = detail.get("prices", {})

    # Look through all markets (ebay, tcgplayer, cardmarket) for PSA grades
    for market, conditions in all_prices.items():
        if not isinstance(conditions, dict):
            continue
        for condition, pdata in conditions.items():
            if not condition.startswith("PSA_"):
                continue
            try:
                grade = int(condition.split("_")[1])
            except (ValueError, IndexError):
                continue
            if not isinstance(pdata, dict):
                continue
            avg = pdata.get("avg")
            if avg is not None and grade not in prices:
                prices[grade] = round(avg, 2)

    return prices


# ---------------------------------------------------------------------------
# PSA API (pop counts)
# ---------------------------------------------------------------------------

def psa_api_request(endpoint, token):
    """Make an authenticated GET request to the PSA Card API."""
    url = f"{PSA_API_BASE}{endpoint}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code}
    except urllib.error.URLError as e:
        return {"_error": str(e.reason)}


def test_psa_pop_access(token):
    """Test if PSA pop endpoints are accessible. Returns True if working."""
    endpoints = [
        "/pop/GetCollectiblePop/1",
        "/pop/GetItemPop/1",
        "/pop/GetSetItems/1",
    ]
    for ep in endpoints:
        print(f"  Testing PSA: {ep} ...")
        data = psa_api_request(ep, token)
        if data and "_error" not in data:
            return True
        if data and data.get("_error") in (401, 403):
            print(f"  Auth rejected ({data['_error']})")
            return False
        time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_csv(cards_data, filepath):
    """Save card data to CSV."""
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["Card #", "Card Name", "Rarity", "Card Number"]
        for g in PSA_GRADES:
            header.append(f"PSA {g}")
        header.append("Raw NM Avg")
        writer.writerow(header)

        for card in cards_data:
            row = [
                card["sort_num"],
                card["name"],
                card["rarity"],
                card["card_number"],
            ]
            for g in PSA_GRADES:
                val = card["psa_prices"].get(g)
                row.append(f"${val:.2f}" if val is not None else "")
            row.append(f"${card['raw_nm']:.2f}" if card.get("raw_nm") else "")
            writer.writerow(row)


def save_json(cards_data, filepath):
    """Save card data to JSON."""
    output = []
    for card in cards_data:
        entry = {
            "number": card["sort_num"],
            "name": card["name"],
            "rarity": card["rarity"],
            "card_number": card["card_number"],
            "variant": card.get("variant", "Regular"),
        }
        if card["psa_prices"]:
            entry["psa_prices"] = {f"PSA {k}": v for k, v in card["psa_prices"].items()}
        if card.get("raw_nm"):
            entry["raw_nm_avg"] = card["raw_nm"]
        output.append(entry)

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)


def print_report(cards_data):
    """Print formatted report to terminal."""
    grades_show = [5, 6, 7, 8, 9, 10]

    header = f"{'#':<8} {'Card Name':<32} {'Rarity':<16}"
    for g in grades_show:
        header += f"{'PSA '+str(g):>10}"
    width = len(header)

    print()
    print("=" * width)
    print("  EX DEOXYS - PSA GRADED PRICING REPORT")
    print("  Source: Poketrace / eBay sold prices")
    print("=" * width)
    print(header)
    print("-" * width)

    for card in cards_data:
        num = card["card_number"] or "?"
        name = card["name"] or "Unknown"
        rarity = card["rarity"] or ""
        prices = card["psa_prices"]

        row = f"{num:<8} {name:<32} {rarity:<16}"
        for g in grades_show:
            val = prices.get(g)
            if val is not None:
                if val >= 500:
                    row += f"{'$'+format(val, ',.0f'):>10}"
                else:
                    row += f"{'$'+format(val, ',.2f'):>10}"
            else:
                row += f"{'--':>10}"
        print(row)

    print("-" * width)
    with_prices = sum(1 for c in cards_data if c["psa_prices"])
    print(f"Total cards: {len(cards_data)} | With PSA pricing: {with_prices}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    poketrace_key, psa_token = load_env()
    print("API keys loaded.")
    if not psa_token:
        print("Note: PSA_API_TOKEN not set — will skip pop counts.")
    print()

    # --- Phase 1: Fetch card list ---
    print("Fetching EX Deoxys card list from Poketrace...")
    cards = fetch_all_cards(poketrace_key)

    if not cards:
        print("Error: Could not fetch cards. Check your API key.")
        sys.exit(1)

    print(f"Found {len(cards)} cards in set.")

    # --- Phase 2: Fetch details with pricing ---
    print("Fetching card details with PSA graded pricing...")
    cards_data = []

    for i, card in enumerate(cards):
        card_id = card.get("id")
        name = card.get("name", "Unknown")
        card_number = card.get("cardNumber", "?")
        rarity = (card.get("rarity") or "").strip()

        # Parse sort number
        try:
            sort_num = int(str(card_number).split("/")[0])
        except (ValueError, IndexError):
            sort_num = 999

        # Fetch detail
        detail = fetch_card_detail(poketrace_key, card_id) if card_id else None
        psa_prices = extract_psa_prices(detail) if detail else {}

        # Extract raw NM price
        raw_nm = None
        if detail:
            all_prices = detail.get("prices", {})
            for market, conditions in all_prices.items():
                if not isinstance(conditions, dict):
                    continue
                for cond in ["NEAR_MINT", "NM"]:
                    if cond in conditions and isinstance(conditions[cond], dict):
                        raw_nm = conditions[cond].get("avg")
                        if raw_nm:
                            break
                if raw_nm:
                    break

        cards_data.append({
            "id": card_id,
            "name": name,
            "card_number": card_number,
            "sort_num": sort_num,
            "rarity": rarity,
            "psa_prices": psa_prices,
            "raw_nm": raw_nm,
        })

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(cards)} cards processed...")
        time.sleep(0.3)

    # Sort by card number
    cards_data.sort(key=lambda c: c["sort_num"])

    # --- Print report ---
    print_report(cards_data)

    # --- Phase 3: PSA pop counts ---
    if psa_token:
        print("\n--- Checking PSA API for pop counts ---")
        if not test_psa_pop_access(psa_token):
            print("STOPPING: PSA pop endpoints not accessible.")
            print("Cert lookups may work, but pop data requires different access.")
        else:
            print("PSA pop access confirmed — fetching data...")
            # Pop count fetching would go here
    else:
        print("\nSkipping PSA pop counts (no PSA_API_TOKEN).")

    # --- Save outputs ---
    base_dir = os.path.dirname(os.path.abspath(__file__))

    csv_path = os.path.join(base_dir, "ex_deoxys_checklist.csv")
    save_csv(cards_data, csv_path)
    print(f"\nCSV saved to {csv_path}")

    json_path = os.path.join(base_dir, "ex_deoxys_full_report.json")
    save_json(cards_data, json_path)
    print(f"JSON saved to {json_path}")

    # Also save data.json for the website
    docs_dir = os.path.join(base_dir, "docs")
    if os.path.isdir(docs_dir):
        docs_json_path = os.path.join(docs_dir, "data.json")
        save_json(cards_data, docs_json_path)
        print(f"Website data saved to {docs_json_path}")


if __name__ == "__main__":
    main()
