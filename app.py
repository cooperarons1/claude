#!/usr/bin/env python3
"""
Pop Counts - PSA Population Report Web App
Browse PSA graded pricing data for WOTC-era Pokemon TCG sets.
"""

import json
import os
from flask import Flask, render_template, request, jsonify

import poketrace

app = Flask(__name__)

# Cache sets in memory
_all_sets_cache = None
_wotc_sets_cache = None


def get_api_key():
    key = poketrace.load_api_key()
    if not key:
        raise RuntimeError(
            "POKETRACE_API_KEY not configured. "
            "Set it in .env or as an environment variable."
        )
    return key


def get_all_sets():
    """Fetch and cache all available sets."""
    global _all_sets_cache
    if _all_sets_cache is None:
        api_key = get_api_key()
        _all_sets_cache = poketrace.fetch_all_sets(api_key)
    return _all_sets_cache


def get_wotc_sets():
    """Fetch and cache WOTC-era sets."""
    global _wotc_sets_cache
    if _wotc_sets_cache is None:
        all_sets = get_all_sets()
        _wotc_sets_cache = [s for s in all_sets if poketrace.is_wotc_set(s)]
    return _wotc_sets_cache


@app.route("/")
def home():
    """Home page - WOTC sets by default, all sets with filter."""
    error = None
    search = request.args.get("q", "").strip().lower()
    show_all = request.args.get("all", "").strip() == "1"

    try:
        if show_all:
            sets = get_all_sets()
        else:
            sets = get_wotc_sets()
    except RuntimeError as e:
        sets = []
        error = str(e)

    if search:
        sets = [
            s for s in sets
            if search in s.get("name", "").lower()
            or search in s.get("id", s.get("slug", "")).lower()
        ]

    return render_template(
        "home.html",
        sets=sets,
        search=request.args.get("q", ""),
        show_all=show_all,
        error=error,
    )


@app.route("/set/<set_id>")
def set_report(set_id):
    """PSA pop report for a specific set."""
    error = None
    cards_data = []
    set_info = None

    try:
        api_key = get_api_key()
        set_info = poketrace.find_set_by_id(api_key, set_id)
        cards_data = poketrace.build_set_report(api_key, set_id)
    except RuntimeError as e:
        error = str(e)

    set_name = set_info.get("name", set_id) if set_info else set_id

    return render_template(
        "report.html",
        set_id=set_id,
        set_name=set_name,
        cards=cards_data,
        error=error,
    )


@app.route("/api/sets")
def api_sets():
    """JSON endpoint for WOTC sets."""
    try:
        sets = get_wotc_sets()
        return jsonify(sets)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/report/<set_id>")
def api_report(set_id):
    """JSON endpoint for a set's pop report."""
    try:
        api_key = get_api_key()
        cards_data = poketrace.build_set_report(api_key, set_id)
        return jsonify(cards_data)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
