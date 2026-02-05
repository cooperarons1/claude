#!/usr/bin/env python3
"""
EX Deoxys PSA Pop Report
Fetches PSA graded pricing data for every card in the EX Deoxys set
using the Poketrace API and displays it as a population-style report.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse

API_BASE = "https://api.poketrace.com/v1"


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
        print(f"API error {e.code} on {endpoint}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"Network error on {endpoint}: {e.reason}")
        return None


def find_deoxys_set(api_key):
    """Find the EX Deoxys set slug from the sets endpoint."""
    data = api_request("/sets", api_key)
    if not data:
        return None

    sets = data if isinstance(data, list) else data.get("data", data.get("sets", []))
    for s in sets:
        name = s.get("name", "").lower()
        slug = s.get("id", s.get("slug", "")).lower()
        if "deoxys" in name or "deoxys" in slug:
            return s.get("id", s.get("slug"))

    return None


def fetch_set_cards(api_key, set_id):
    """Fetch all cards in a set, handling pagination."""
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

        total = None
        if isinstance(data, dict):
            total = data.get("totalCount", data.get("total"))
        if total and len(all_cards) >= total:
            break
        if len(cards) < 50:
            break

        page += 1
        time.sleep(0.5)

    return all_cards


def fetch_card_detail(api_key, card_id):
    """Fetch detailed info for a single card including graded prices."""
    return api_request(f"/cards/{card_id}", api_key)


def extract_psa_grades(card_data):
    """Extract PSA grade pricing from card data."""
    grades = {}
    if not card_data:
        return grades

    detail = card_data.get("data", card_data) if isinstance(card_data, dict) else card_data

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

    if not grades and isinstance(detail, dict):
        for key, val in detail.items():
            if "psa" in key.lower() and "10" in key:
                grades[10] = val
            elif "psa" in key.lower() and "9" in key:
                grades[9] = val

    return grades


def print_report(cards_data):
    """Print the PSA pop-style report."""
    header = f"{'#':<6} {'Card Name':<30} "
    for g in range(1, 11):
        header += f"{'PSA '+str(g):>10} "
    print("=" * len(header))
    print("  EX DEOXYS - PSA GRADED PRICE REPORT")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for card in sorted(cards_data, key=lambda c: c.get("sort_num", 999)):
        num = card.get("number", "?")
        name = card.get("name", "Unknown")
        grades = card.get("psa_grades", {})

        row = f"{num:<6} {name:<30} "
        for g in range(1, 11):
            val = grades.get(g)
            if val is not None:
                if isinstance(val, (int, float)):
                    row += f"{'$'+format(val, ',.2f'):>10} "
                else:
                    row += f"{str(val):>10} "
            else:
                row += f"{'--':>10} "
        print(row)

    print("-" * len(header))
    print(f"Total cards: {len(cards_data)}")


def main():
    api_key = load_api_key()
    print("Loaded Poketrace API key.")

    print("Searching for EX Deoxys set...")
    set_id = find_deoxys_set(api_key)

    if not set_id:
        print("Could not find EX Deoxys set by browsing sets.")
        print("Trying direct search...")
        set_id = "ex-deoxys"

    print(f"Using set ID: {set_id}")

    print("Fetching cards...")
    cards = fetch_set_cards(api_key, set_id)

    if not cards:
        print("No cards found. Trying alternate set IDs...")
        for alt_id in ["ex-deoxys", "deoxys", "EX Deoxys", "dx"]:
            cards = fetch_set_cards(api_key, alt_id)
            if cards:
                set_id = alt_id
                break

    if not cards:
        print("Error: Could not retrieve cards for EX Deoxys.")
        print("Check your API key and try again.")
        sys.exit(1)

    print(f"Found {len(cards)} cards. Fetching PSA grade details...")

    cards_data = []
    for i, card in enumerate(cards):
        card_id = card.get("id", card.get("cardId"))
        name = card.get("name", "Unknown")
        number = card.get("number", card.get("cardNumber", "?"))

        try:
            sort_num = int(str(number).split("/")[0])
        except (ValueError, IndexError):
            sort_num = 999

        detail = fetch_card_detail(api_key, card_id) if card_id else card
        psa_grades = extract_psa_grades(detail or card)

        cards_data.append({
            "id": card_id,
            "name": name,
            "number": number,
            "sort_num": sort_num,
            "psa_grades": psa_grades,
        })

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(cards)} cards...")
        time.sleep(0.3)

    print()
    print_report(cards_data)

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "psa_pop_deoxys.json")
    with open(output_file, "w") as f:
        json.dump(cards_data, f, indent=2)
    print(f"\nRaw data saved to {output_file}")


if __name__ == "__main__":
    main()
