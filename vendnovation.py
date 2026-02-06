"""
VendNovation API Client — Vending Machine Inventory & Sales Management.

VendNovation API v2.1 docs: https://docs.vendnovation-services.com/vendor/v2.1/
- Two-layer auth: x-api-key header + login token
- Base URL: https://vendor-api.vendnovation-services.com
- POST-based reads with filter bodies
- Tokens valid for 3 days
"""

import json
import os
import time
import urllib.error
import urllib.request

VN_BASE = "https://vendor-api.vendnovation-services.com"
VN_STAGE = "prod"

# In-memory token cache (token valid for 3 days)
_token_cache = {"token": None, "expires": 0}


def load_credentials():
    """Load VendNovation credentials from environment variables.

    Required env vars:
        VENDNOVATION_API_KEY - AWS API Gateway key (x-api-key header)
        VENDNOVATION_USERNAME - Login username
        VENDNOVATION_PASSWORD - Login password
    """
    api_key = os.environ.get("VENDNOVATION_API_KEY")
    username = os.environ.get("VENDNOVATION_USERNAME")
    password = os.environ.get("VENDNOVATION_PASSWORD")
    return api_key, username, password


def _make_request(endpoint, api_key, auth_token=None, body=None, method="POST"):
    """Make a request to the VendNovation API."""
    url = f"{VN_BASE}/{VN_STAGE}{endpoint}"

    payload = json.dumps(body).encode() if body else b"{}"

    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", api_key)
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")

    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_body = resp.read().decode()
        if resp_body:
            return json.loads(resp_body)
        return None


def authenticate(api_key, username, password):
    """Authenticate with VendNovation and get an access token.

    Tokens are valid for 3 days.
    """
    global _token_cache

    # Return cached token if still valid (with 1 hour buffer)
    if _token_cache["token"] and time.time() < _token_cache["expires"]:
        return _token_cache["token"]

    body = {"username": username, "password": password}
    result = _make_request("/authenticate", api_key, body=body)

    if result and result.get("token"):
        _token_cache["token"] = result["token"]
        # Cache for 2.5 days (token valid for 3 days, buffer for safety)
        _token_cache["expires"] = time.time() + (2.5 * 24 * 3600)
        return result["token"]

    raise Exception("VendNovation authentication failed")


def test_api_key(api_key):
    """Test if the API key is configured correctly.

    This endpoint does NOT require authentication.
    """
    try:
        result = _make_request("/api-key-test", api_key)
        return True, result
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def get_auth_token():
    """Get a valid auth token using env credentials."""
    api_key, username, password = load_credentials()
    if not all([api_key, username, password]):
        return None, None
    token = authenticate(api_key, username, password)
    return api_key, token


# ---- Organization & Accounts ----

def get_organizations(api_key, token, org_ids=None):
    """Get organizations the user has access to."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/organizations", api_key, token, body)


def get_accounts(api_key, token, org_ids=None, account_ids=None):
    """Get accounts within the organization."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if account_ids:
        body["requestFilter"]["accountIds"] = account_ids
    return _make_request("/accounts", api_key, token, body)


# ---- Sites ----

def get_sites(api_key, token, org_ids=None, site_ids=None):
    """Get sites (locations where machines are deployed)."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    return _make_request("/sites", api_key, token, body)


# ---- Machines ----

def get_machines(api_key, token, org_ids=None, site_ids=None, machine_ids=None):
    """Get vending machines."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    return _make_request("/machines", api_key, token, body)


def get_machine_models(api_key, token):
    """Get available machine models."""
    return _make_request("/machines/models", api_key, token, {"requestFilter": {}})


def get_machine_types(api_key, token):
    """Get available machine types."""
    return _make_request("/machines/types", api_key, token, {"requestFilter": {}})


# ---- Products ----

def get_products(api_key, token, org_ids=None):
    """Get products in the catalog."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/products", api_key, token, body)


def create_products(api_key, token, products):
    """Create new products.

    products: list of dicts with product fields.
    """
    body = {"body": products}
    return _make_request("/products/create", api_key, token, body)


def get_product_variants(api_key, token, org_ids=None):
    """Get product variants."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/product-variants", api_key, token, body)


# ---- Selections (Machine Inventory / Planogram) ----

def get_selections(api_key, token, machine_ids=None, site_ids=None):
    """Get selections (what's loaded in each machine slot)."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    return _make_request("/selections", api_key, token, body)


# ---- Alerts ----

def get_alerts(api_key, token, machine_ids=None, site_ids=None, org_ids=None):
    """Get machine alerts."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/alerts", api_key, token, body)


def get_alert_codes(api_key, token):
    """Get all possible alert codes."""
    return _make_request("/alerts/codes", api_key, token, {"requestFilter": {}})


# ---- Reports ----

def get_transactions(api_key, token, machine_ids=None, site_ids=None,
                     start_date=None, end_date=None):
    """Get transaction reports."""
    body = {"requestFilter": {}, "routeFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    return _make_request("/reports/transactions", api_key, token, body)


def get_sales_statistics(api_key, token, machine_ids=None, site_ids=None,
                         start_date=None, end_date=None):
    """Get sales statistics."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    return _make_request("/reports/sales-statistics", api_key, token, body)


def get_inventory_adjustments(api_key, token, machine_ids=None, site_ids=None,
                              start_date=None, end_date=None):
    """Get inventory adjustment events."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = machine_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    return _make_request("/reports/inventory-adjustments", api_key, token, body)


# ---- Templates ----

def get_templates(api_key, token, org_ids=None):
    """Get machine templates."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/templates", api_key, token, body)


# ---- High-level helpers for the dashboard ----

def get_dashboard_data():
    """Fetch all data needed for the vending dashboard.

    Returns a dict with machines, sites, alerts, and products.
    Returns None if credentials are not configured.
    """
    api_key, token = get_auth_token()
    if not api_key or not token:
        return None

    data = {
        "machines": [],
        "sites": [],
        "alerts": [],
        "products": [],
        "selections": [],
    }

    try:
        sites_resp = get_sites(api_key, token)
        data["sites"] = sites_resp if isinstance(sites_resp, list) else sites_resp.get("data", []) if sites_resp else []
    except Exception:
        pass

    try:
        machines_resp = get_machines(api_key, token)
        data["machines"] = machines_resp if isinstance(machines_resp, list) else machines_resp.get("data", []) if machines_resp else []
    except Exception:
        pass

    try:
        alerts_resp = get_alerts(api_key, token)
        data["alerts"] = alerts_resp if isinstance(alerts_resp, list) else alerts_resp.get("data", []) if alerts_resp else []
    except Exception:
        pass

    try:
        products_resp = get_products(api_key, token)
        data["products"] = products_resp if isinstance(products_resp, list) else products_resp.get("data", []) if products_resp else []
    except Exception:
        pass

    try:
        selections_resp = get_selections(api_key, token)
        data["selections"] = selections_resp if isinstance(selections_resp, list) else selections_resp.get("data", []) if selections_resp else []
    except Exception:
        pass

    return data


def get_machine_detail(machine_id):
    """Fetch detailed data for a single machine."""
    api_key, token = get_auth_token()
    if not api_key or not token:
        return None

    data = {"machine": None, "selections": [], "alerts": []}

    try:
        machines_resp = get_machines(api_key, token, machine_ids=[machine_id])
        machines = machines_resp if isinstance(machines_resp, list) else machines_resp.get("data", []) if machines_resp else []
        data["machine"] = machines[0] if machines else None
    except Exception:
        pass

    try:
        sel_resp = get_selections(api_key, token, machine_ids=[machine_id])
        data["selections"] = sel_resp if isinstance(sel_resp, list) else sel_resp.get("data", []) if sel_resp else []
    except Exception:
        pass

    try:
        alerts_resp = get_alerts(api_key, token, machine_ids=[machine_id])
        data["alerts"] = alerts_resp if isinstance(alerts_resp, list) else alerts_resp.get("data", []) if alerts_resp else []
    except Exception:
        pass

    return data
