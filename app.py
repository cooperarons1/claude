#!/usr/bin/env python3
"""
Pop Counts - Phantasmal Flames Sealed Product Tracker
Live prices from PriceCharting API.
"""

import os
from flask import Flask, render_template, jsonify

import products

app = Flask(__name__)


@app.route("/")
def home():
    """Home page - show all Phantasmal Flames products with live prices."""
    try:
        token = products.load_api_token()
        all_products, price_source = products.get_products(token)

        type_order = {"booster-box": 0, "etb": 1, "bundle": 2, "build-battle": 3, "pack": 4}
        all_products.sort(key=lambda p: type_order.get(p["type"], 99))

        # Find best value among products that have a price
        priced = [p for p in all_products if p.get("per_pack") and p["per_pack"] > 0]
        best_id = min(priced, key=lambda p: p["per_pack"])["id"] if priced else None

        return render_template(
            "home.html",
            products=all_products,
            best_id=best_id,
            price_source=price_source,
        )
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/product/<product_id>")
def product_detail(product_id):
    """Detail page for a single product."""
    token = products.load_api_token()
    product = products.get_product_by_id(product_id, token)
    if not product:
        return render_template("404.html"), 404
    return render_template("product.html", product=product)


@app.route("/api/products")
def api_products():
    """JSON endpoint for all products."""
    try:
        token = products.load_api_token()
        prods, source = products.get_products(token)
        return jsonify({"products": prods, "price_source": source})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
