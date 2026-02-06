#!/usr/bin/env python3
"""
PokePriceTracker - Pokemon TCG Sealed Product Price Tracker
Live prices from PriceCharting API. AI assistant powered by Claude.
"""

import json
import os
import urllib.request
import urllib.parse

from flask import Flask, render_template, jsonify, request

import products

app = Flask(__name__)


@app.route("/")
def home():
    """Home page — browse all sets."""
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
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/api/products")
@app.route("/api/products/<set_slug>")
def api_products(set_slug="phantasmal-flames"):
    """JSON endpoint for all products in a set."""
    try:
        token = products.load_api_token()
        prods, source = products.get_products(token, set_slug)
        return jsonify({"products": prods, "price_source": source, "set": set_slug})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _build_price_context():
    """Fetch live prices for all sets and format as context for Claude."""
    token = products.load_api_token()
    if not token:
        return "No live pricing data available (no API token)."

    lines = ["LIVE PRICING DATA FROM PRICECHARTING:"]
    for set_info in products.get_set_list():
        slug = set_info["slug"]
        try:
            prods, source = products.get_products(token, slug)
        except Exception:
            continue

        priced = [p for p in prods if p.get("market_price")]
        if not priced:
            continue

        lines.append(f"\n{set_info['series']} — {set_info['name']}:")
        for p in priced:
            per_pack = f" (${p['per_pack']:.2f}/pack)" if p.get("per_pack") else ""
            lines.append(f"  {p['name']}: ${p['market_price']:.2f} — {p['packs']} packs{per_pack}")

        # Note best value
        priced_with_pp = [p for p in priced if p.get("per_pack") and p["per_pack"] > 0]
        if priced_with_pp:
            best = min(priced_with_pp, key=lambda p: p["per_pack"])
            lines.append(f"  -> Best value: {best['name']} at ${best['per_pack']:.2f}/pack")

    return "\n".join(lines)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat endpoint — proxy to Claude API with live price context."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "No ANTHROPIC_API_KEY configured"}), 500

    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "No message provided"}), 400

    user_msg = data["message"]
    history = data.get("history", [])

    # Build messages for Claude
    messages = []
    for h in history[-10:]:  # Keep last 10 messages for context
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    # Fetch live pricing data to give Claude real context
    price_context = _build_price_context()

    system_prompt = (
        "You are a helpful Pokemon TCG pricing assistant on PokePriceTracker. "
        "You help users understand sealed product prices, find the best deals, "
        "and answer questions about Pokemon TCG sets and products. "
        "Keep responses concise and friendly. Use dollar amounts when discussing prices. "
        "You have access to LIVE pricing data below — use it to answer questions accurately. "
        "You can compare prices across sets, identify best deals, and give buying advice.\n\n"
        f"{price_context}"
    )

    try:
        payload = json.dumps({
            "model": "claude-opus-4-6",
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
        return jsonify({"error": f"Claude API error: {e.code}", "detail": body}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
