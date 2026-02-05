#!/usr/bin/env python3
"""
PSA Cert Lookup
Fetches PSA certification data by cert number using the PSA Card public API.
"""

import os
import sys
import json
import urllib.request
import urllib.error

PSA_API_BASE = "https://api.psacard.com/publicapi"


def load_psa_token():
    """Load PSA API bearer token from environment variable or .env file."""
    token = os.environ.get("PSA_API_TOKEN")
    if token:
        return token

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("PSA_API_TOKEN="):
                    return line.split("=", 1)[1].strip()

    print("Error: PSA_API_TOKEN not found.")
    print("Set it in .env (PSA_API_TOKEN=<your_token>) or as an environment variable.")
    sys.exit(1)


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
        body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        return None


def get_cert(token, cert_number):
    """Look up a PSA certification by cert number."""
    return psa_api_request(f"/cert/GetByCertNumber/{cert_number}", token)


def print_cert_info(data):
    """Print formatted certification details."""
    if not data:
        print("No data returned.")
        return

    cert = data if isinstance(data, dict) else {}
    if "PSACert" in cert:
        cert = cert["PSACert"]

    fields = [
        ("Cert Number", "CertNumber"),
        ("Brand", "Brand"),
        ("Category", "Category"),
        ("Year", "Year"),
        ("Card Name", "Subject"),
        ("Card Number", "CardNumber"),
        ("Variety", "Variety"),
        ("Grade", "CardGrade"),
        ("Spec Number", "SpecNumber"),
        ("Label Type", "LabelType"),
    ]

    print("=" * 50)
    print("  PSA CERTIFICATION DETAILS")
    print("=" * 50)
    for label, key in fields:
        val = cert.get(key, "N/A")
        if val is not None and str(val).strip():
            print(f"  {label:<16}: {val}")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("Usage: python psa_cert_lookup.py <cert_number> [cert_number ...]")
        print("Example: python psa_cert_lookup.py 12345678")
        sys.exit(1)

    token = load_psa_token()
    print("Loaded PSA API token.")

    for cert_number in sys.argv[1:]:
        print(f"\nLooking up cert #{cert_number}...")
        data = get_cert(token, cert_number)
        print_cert_info(data)


if __name__ == "__main__":
    main()
