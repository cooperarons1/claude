#!/usr/bin/env python3
"""
Pop Counts - Phantasmal Flames Sealed Product Tracker
Track prices for booster boxes, bundles, and ETBs.
"""

import os
from flask import Flask, render_template, request, jsonify

import products

app = Flask(__name__)


@app.route("/")
def home():
    """Home page - show all Phantasmal Flames products."""
    all_products = products.get_products()

    # Sort: booster box first, then ETBs, bundle, build & battle, pack
    type_order = {"booster-box": 0, "etb": 1, "bundle": 2, "build-battle": 3, "pack": 4}
    all_products.sort(key=lambda p: type_order.get(p["type"], 99))

    # Find best value (lowest per-pack cost)
    if all_products:
        best = min(all_products, key=lambda p: p["per_pack"])
        best_id = best["id"]
    else:
        best_id = None

    return render_template("home.html", products=all_products, best_id=best_id)


@app.route("/product/<product_id>")
def product_detail(product_id):
    """Detail page for a single product."""
    product = products.get_product_by_id(product_id)
    if not product:
        return render_template("404.html"), 404
    return render_template("product.html", product=product)


@app.route("/api/products")
def api_products():
    """JSON endpoint for all products."""
    try:
        return jsonify(products.get_products())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
