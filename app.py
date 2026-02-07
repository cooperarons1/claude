#!/usr/bin/env python3
"""
PokePriceTracker - Pokemon TCG Sealed Product Price Tracker
Live prices from PriceCharting API. AI assistant powered by Claude.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, render_template, jsonify, request

import products
import vendnovation

app = Flask(__name__)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pokepricetracker")

# --- Startup validation ---
_OPTIONAL_ENVS = {
    "PRICECHARTING_TOKEN": "Live pricing will be unavailable",
    "ANTHROPIC_API_KEY": "Chat assistant will be unavailable",
}

for _var, _msg in _OPTIONAL_ENVS.items():
    if not os.environ.get(_var):
        log.warning("Environment variable %s is not set. %s.", _var, _msg)

# --- Price context cache ---
_price_context_cache = {"text": None, "ts": 0}
_PRICE_CACHE_TTL = 300  # 5 minutes

MAX_CHAT_MESSAGE_LENGTH = 2000
MAX_CHAT_HISTORY = 10


@app.route("/")
def home():
    """Home page -- browse all sets."""
    sets = products.get_set_list()
    return render_template("home.html", sets=sets)


@app.route("/set/<set_slug>")
def set_page(set_slug):
    """Show all products for a given set with live prices."""
    if set_slug not in products.SET_CATALOG:
        return render_template("404.html"), 404

    try:
        token = products.load_api_token()
        all_products, price_source = products.get_products(token, set_slug)

        type_order = {"booster-box": 0, "etb": 1, "bundle": 2, "build-battle": 3, "pack": 4}
        all_products.sort(key=lambda p: type_order.get(p["type"], 99))

        # Find best value among products that have a price
        priced = [p for p in all_products if p.get("per_pack") and p["per_pack"] > 0]
        best_id = min(priced, key=lambda p: p["per_pack"])["id"] if priced else None

        set_info = products.SET_CATALOG[set_slug]

        return render_template(
            "set.html",
            products=all_products,
            best_id=best_id,
            price_source=price_source,
            sets=products.get_set_list(),
            current_set=set_slug,
            set_name=set_info["name"],
            set_series=set_info["series"],
        )
    except urllib.error.URLError as e:
        log.error("Network error loading set %s: %s", set_slug, e)
        return render_template("404.html"), 503
    except (KeyError, ValueError) as e:
        log.error("Data error loading set %s: %s", set_slug, e)
        return render_template("404.html"), 500


@app.route("/api/products")
@app.route("/api/products/<set_slug>")
def api_products(set_slug="phantasmal-flames"):
    """JSON endpoint for all products in a set."""
    try:
        token = products.load_api_token()
        prods, source = products.get_products(token, set_slug)
        return jsonify({"products": prods, "price_source": source, "set": set_slug})
    except urllib.error.URLError as e:
        log.error("Network error fetching products for %s: %s", set_slug, e)
        return jsonify({"error": "Failed to fetch pricing data"}), 502
    except (KeyError, ValueError) as e:
        log.error("Data error fetching products for %s: %s", set_slug, e)
        return jsonify({"error": str(e)}), 500


def _build_price_context():
    """Fetch live prices for all sets and format as context for Claude.

    Results are cached for 5 minutes to avoid hammering the PriceCharting API.
    """
    now = time.time()
    if _price_context_cache["text"] and (now - _price_context_cache["ts"]) < _PRICE_CACHE_TTL:
        return _price_context_cache["text"]

    token = products.load_api_token()
    if not token:
        return "No live pricing data available (no API token)."

    lines = ["LIVE PRICING DATA FROM PRICECHARTING:"]
    for set_info in products.get_set_list():
        slug = set_info["slug"]
        try:
            prods, source = products.get_products(token, slug)
        except urllib.error.URLError:
            log.warning("Skipping set %s due to network error", slug)
            continue
        except (KeyError, ValueError):
            log.warning("Skipping set %s due to data error", slug)
            continue

        priced = [p for p in prods if p.get("market_price")]
        if not priced:
            continue

        lines.append(f"\n{set_info['series']} -- {set_info['name']}:")
        for p in priced:
            per_pack = f" (${p['per_pack']:.2f}/pack)" if p.get("per_pack") else ""
            lines.append(f"  {p['name']}: ${p['market_price']:.2f} -- {p['packs']} packs{per_pack}")

        # Note best value
        priced_with_pp = [p for p in priced if p.get("per_pack") and p["per_pack"] > 0]
        if priced_with_pp:
            best = min(priced_with_pp, key=lambda p: p["per_pack"])
            lines.append(f"  -> Best value: {best['name']} at ${best['per_pack']:.2f}/pack")

    text = "\n".join(lines)
    _price_context_cache["text"] = text
    _price_context_cache["ts"] = now
    return text


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat endpoint -- proxy to Claude API with live price context."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "Chat assistant is not configured."}), 503

    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("message"), str):
        return jsonify({"error": "No message provided"}), 400

    user_msg = data["message"].strip()
    if not user_msg:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(user_msg) > MAX_CHAT_MESSAGE_LENGTH:
        return jsonify({"error": f"Message too long (max {MAX_CHAT_MESSAGE_LENGTH} characters)"}), 400

    history = data.get("history", [])
    if not isinstance(history, list):
        history = []

    # Build messages for Claude
    messages = []
    for h in history[-MAX_CHAT_HISTORY:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            messages.append({"role": h["role"], "content": h["content"][:MAX_CHAT_MESSAGE_LENGTH]})
    messages.append({"role": "user", "content": user_msg})

    # Fetch live pricing data to give Claude real context
    price_context = _build_price_context()

    system_prompt = (
        "You are a helpful Pokemon TCG pricing assistant on PokePriceTracker. "
        "You help users understand sealed product prices, find the best deals, "
        "and answer questions about Pokemon TCG sets and products. "
        "Keep responses concise and friendly. Use dollar amounts when discussing prices. "
        "You have access to LIVE pricing data below -- use it to answer questions accurately. "
        "You can compare prices across sets, identify best deals, and give buying advice.\n\n"
        f"{price_context}"
    )

    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")

    try:
        payload = json.dumps({
            "model": model,
            "max_tokens": 512,
            "system": system_prompt,
            "messages": messages,
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            reply = result["content"][0]["text"]
            return jsonify({"reply": reply})

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log.error("Claude API HTTP error %d: %s", e.code, body[:200])
        return jsonify({"error": "AI assistant is temporarily unavailable. Please try again."}), 502
    except urllib.error.URLError as e:
        log.error("Claude API network error: %s", e)
        return jsonify({"error": "Could not reach AI assistant. Please try again."}), 502


# ---- VendNovation Vending Machine Dashboard ----

@app.route("/vending")
def vending_dashboard():
    """Vending machine dashboard -- overview of all machines."""
    data = vendnovation.get_dashboard_data()
    configured = data is not None
    return render_template(
        "vending.html",
        configured=configured,
        machines=data["machines"] if data else [],
        sites=data["sites"] if data else [],
        alerts=data["alerts"] if data else [],
        products=data["products"] if data else [],
        selections=data["selections"] if data else [],
    )


@app.route("/vending/machine/<int:machine_id>")
def vending_machine(machine_id):
    """Detail page for a single vending machine."""
    data = vendnovation.get_machine_detail(machine_id)
    if not data or not data["machine"]:
        return render_template("404.html"), 404
    return render_template(
        "vending_machine.html",
        machine=data["machine"],
        selections=data["selections"],
        alerts=data["alerts"],
    )


@app.route("/api/vending/machines")
def api_vending_machines():
    """JSON endpoint for vending machines."""
    try:
        api_key, token = vendnovation.get_auth_token()
        if not api_key:
            return jsonify({"error": "VendNovation not configured"}), 503
        machines = vendnovation.get_machines(api_key, token)
        return jsonify({"machines": machines})
    except urllib.error.URLError as e:
        log.error("VendNovation network error: %s", e)
        return jsonify({"error": "Could not reach VendNovation API"}), 502
    except (KeyError, ValueError) as e:
        log.error("VendNovation data error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/vending/transactions")
def api_vending_transactions():
    """JSON endpoint for recent transactions."""
    try:
        api_key, token = vendnovation.get_auth_token()
        if not api_key:
            return jsonify({"error": "VendNovation not configured"}), 503
        start = request.args.get("start")
        end = request.args.get("end")
        txns = vendnovation.get_transactions(api_key, token, start_date=start, end_date=end)
        return jsonify({"transactions": txns})
    except urllib.error.URLError as e:
        log.error("VendNovation transactions network error: %s", e)
        return jsonify({"error": "Could not reach VendNovation API"}), 502
    except (KeyError, ValueError) as e:
        log.error("VendNovation transactions data error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/vending/alerts")
def api_vending_alerts():
    """JSON endpoint for machine alerts."""
    try:
        api_key, token = vendnovation.get_auth_token()
        if not api_key:
            return jsonify({"error": "VendNovation not configured"}), 503
        alerts = vendnovation.get_alerts(api_key, token)
        return jsonify({"alerts": alerts})
    except urllib.error.URLError as e:
        log.error("VendNovation alerts network error: %s", e)
        return jsonify({"error": "Could not reach VendNovation API"}), 502
    except (KeyError, ValueError) as e:
        log.error("VendNovation alerts data error: %s", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
