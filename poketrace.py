"""
Poketrace API client module.
Provides reusable functions for fetching PSA pop report data
across any Pokémon TCG set.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

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


def fetch_all_sets(api_key):
    """Fetch all available card sets."""
    data = api_request("/sets", api_key)
    if not data:
        return []
    sets = data if isinstance(data, list) else data.get("data", data.get("sets", []))
    return sets


def find_set_by_id(api_key, set_id):
    """Find a specific set by its ID/slug."""
    sets = fetch_all_sets(api_key)
    for s in sets:
        sid = s.get("id", s.get("slug", ""))
        if sid == set_id:
            return s
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


def build_set_report(api_key, set_id):
    """Build a full PSA pop report for a given set.

    Returns a list of dicts with card info and PSA grades.
    """
    cards = fetch_set_cards(api_key, set_id)
    if not cards:
        return []

    cards_data = []
    for card in cards:
        card_id = card.get("id", card.get("cardId"))
        name = card.get("name", "Unknown")
        number = card.get("number", card.get("cardNumber", "?"))
        image = card.get("image", card.get("imageUrl", card.get("images", {}).get("small", "")))
        rarity = card.get("rarity", "")

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
            "image": image,
            "rarity": rarity,
            "psa_grades": psa_grades,
        })

        time.sleep(0.3)

    cards_data.sort(key=lambda c: c["sort_num"])
    return cards_data
