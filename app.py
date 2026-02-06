#!/usr/bin/env python3
"""
Pop Counts - Phantasmal Flames Sealed Product Tracker
Track prices for booster boxes, bundles, and ETBs.
Pulls live data from Poketrace API with fallback pricing.
"""

import os
from flask import Flask, render_template, request, jsonify

import products

app = Flask(__name__)


def get_api_key():
    return products.load_api_key()


@app.route("/")
def home():
    """Home page - show all Phantasmal Flames products (fast, no API calls)."""
    try:
        # Load with fallback prices first (instant, no API call)
        all_products, price_source = products.get_products(api_key=None)

        type_order = {"booster-box": 0, "etb": 1, "bundle": 2, "build-battle": 3, "pack": 4}
        all_products.sort(key=lambda p: type_order.get(p["type"], 99))

        best_id = None
        if all_products:
            best = min(all_products, key=lambda p: p["per_pack"])
            best_id = best["id"]

        return render_template(
            "home.html",
            products=all_products,
            best_id=best_id,
            price_source=price_source,
            has_api_key=bool(get_api_key()),
        )
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/product/<product_id>")
def product_detail(product_id):
    """Detail page for a single product."""
    product = products.get_product_by_id(product_id, api_key=None)
    if not product:
        return render_template("404.html"), 404
    return render_template("product.html", product=product)


@app.route("/api/refresh-prices")
def refresh_prices():
    """Fetch live prices from Poketrace API (called via JS)."""
    api_key = get_api_key()
    if not api_key:
        return jsonify({"error": "No API key configured"}), 400

    try:
        all_products, price_source = products.get_products(api_key)
        return jsonify({"products": all_products, "price_source": price_source})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug")
def debug_api():
    """Debug page showing raw Poketrace API responses."""
    api_key = get_api_key()
    if not api_key:
        return render_template("debug.html", error="No API key configured", results={})

    try:
        results = products.probe_api(api_key)
    except Exception as e:
        results = {"error": str(e)}

    return render_template("debug.html", error=None, results=results)


@app.route("/api/products")
def api_products():
    """JSON endpoint for all products."""
    try:
        api_key = get_api_key()
        prods, source = products.get_products(api_key)
        return jsonify({"products": prods, "price_source": source})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
