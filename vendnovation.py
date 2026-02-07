"""
VendNovation Vendor API Client — Vending Machine Inventory & Sales Management.

API docs: https://docs.vendnovation-services.com/vendor/v2.1/
Postman collection: https://doctest.vendnovation.com/VendorAPI-CustomerFacing.postman_collection.json

Auth flow:
  1. All requests require x-api-key header (AWS API Gateway key)
  2. POST /authenticate with username+password -> returns accessToken
  3. Pass accessToken as access-token header on all subsequent requests
  4. Tokens valid for 3 days

Pagination: page and size headers (max size 50)
Machine identifiers are STRINGS (can be numeric IDs or PROSE serial numbers)
"""

import json
import os
import time
import urllib.error
import urllib.request

VN_BASE = "https://vendor-api.vendnovation-services.com"
VN_STAGE = "prod"
VN_PAGE_SIZE = 50

# In-memory token cache (token valid for 3 days)
_token_cache = {"token": None, "expires": 0}


def load_credentials():
    """Load VendNovation credentials from environment variables.

    Required env vars:
        VENDNOVATION_API_KEY - AWS API Gateway key (x-api-key header)
        VENDNOVATION_USERNAME - Login username
        VENDNOVATION_PASSWORD - Login password

    Optional:
        VENDNOVATION_STAGE - API stage (default: prod)
    """
    api_key = os.environ.get("VENDNOVATION_API_KEY")
    username = os.environ.get("VENDNOVATION_USERNAME")
    password = os.environ.get("VENDNOVATION_PASSWORD")
    return api_key, username, password


def _get_stage():
    return os.environ.get("VENDNOVATION_STAGE", VN_STAGE)


def _make_request(endpoint, api_key, auth_token=None, body=None,
                  method="POST", page=1, size=VN_PAGE_SIZE):
    """Make a request to the VendNovation API.

    Args:
        endpoint: API path (e.g. "/machines")
        api_key: AWS API Gateway key for x-api-key header
        auth_token: Access token from /authenticate
        body: Request body dict (will be JSON-encoded)
        method: HTTP method (POST, PUT, PATCH, DELETE)
        page: Page number for pagination (header)
        size: Page size for pagination (header, max 50)
    """
    stage = _get_stage()
    url = f"{VN_BASE}/{stage}{endpoint}"

    payload = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", api_key)

    # Auth token goes in access-token header (not Authorization: Bearer)
    if auth_token:
        req.add_header("access-token", auth_token)

    # Pagination headers
    req.add_header("page", str(page))
    req.add_header("size", str(min(size, VN_PAGE_SIZE)))

    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_body = resp.read().decode()
        if resp_body:
            return json.loads(resp_body)
        return None


def authenticate(api_key, username, password):
    """Authenticate with VendNovation and get an access token.

    POST /authenticate -> { "accessToken": "..." }
    Tokens are valid for 3 days.
    """
    global _token_cache

    # Return cached token if still valid
    if _token_cache["token"] and time.time() < _token_cache["expires"]:
        return _token_cache["token"]

    body = {"username": username, "password": password}
    result = _make_request("/authenticate", api_key, body=body)

    if result and result.get("accessToken"):
        _token_cache["token"] = result["accessToken"]
        # Cache for 2.5 days (token valid for 3 days, buffer for safety)
        _token_cache["expires"] = time.time() + (2.5 * 24 * 3600)
        return result["accessToken"]

    raise Exception("VendNovation authentication failed")


def test_api_key(api_key):
    """Test if the API key is configured correctly.

    POST /token-test — does NOT require access-token.
    Returns success message if key is valid, 403 if not.
    """
    try:
        result = _make_request("/token-test", api_key)
        return True, result
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def get_token_info(api_key, username, password):
    """Get token information. Also returns a fresh accessToken.

    POST /token-info with username + password.
    """
    body = {"username": username, "password": password}
    return _make_request("/token-info", api_key, body=body)


def get_auth_token():
    """Get a valid auth token using env credentials.

    Returns (api_key, access_token) or (None, None) if not configured.
    """
    api_key, username, password = load_credentials()
    if not all([api_key, username, password]):
        return None, None
    token = authenticate(api_key, username, password)
    return api_key, token


# ---- Organization & Accounts ----

def get_organizations(api_key, token, org_ids=None, page=1):
    """POST /organizations — Get organizations the user has access to."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/organizations", api_key, token, body, page=page)


def get_accounts(api_key, token, org_ids=None, account_ids=None, page=1):
    """POST /accounts — Get accounts within the organization."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if account_ids:
        body["requestFilter"]["accountIds"] = account_ids
    return _make_request("/accounts", api_key, token, body, page=page)


# ---- Sites ----

def get_sites(api_key, token, org_ids=None, account_ids=None, site_ids=None, page=1):
    """POST /sites — Get sites (locations where machines are deployed)."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if account_ids:
        body["requestFilter"]["accountIds"] = account_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    return _make_request("/sites", api_key, token, body, page=page)


def create_sites(api_key, token, sites):
    """PUT /sites — Create new sites. sites: list of site dicts."""
    body = {"body": sites}
    return _make_request("/sites", api_key, token, body, method="PUT")


def update_sites(api_key, token, sites):
    """PATCH /sites — Update existing sites."""
    body = {"body": sites}
    return _make_request("/sites", api_key, token, body, method="PATCH")


def delete_sites(api_key, token, site_ids):
    """DELETE /sites — Delete sites."""
    body = {"body": [{"id": sid} for sid in site_ids]}
    return _make_request("/sites", api_key, token, body, method="DELETE")


# ---- Machines ----

def get_machines(api_key, token, org_ids=None, site_ids=None,
                 machine_ids=None, include_deleted=False, page=1):
    """POST /machines — Get vending machines.

    machine_ids should be a list of STRINGS (numeric IDs or PROSE serial numbers).
    """
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if machine_ids:
        # Machine identifiers are strings in VendNovation
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if include_deleted:
        body["requestFilter"]["includeDeleted"] = True
    return _make_request("/machines", api_key, token, body, page=page)


def update_machines(api_key, token, machines):
    """PATCH /machines — Update existing machines."""
    body = {"body": machines}
    return _make_request("/machines", api_key, token, body, method="PATCH")


def get_machine_settings(api_key, token, machine_ids=None, page=1):
    """POST /machines/settings — Get machine settings."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    return _make_request("/machines/settings", api_key, token, body, page=page)


def get_machine_models(api_key, token, page=1):
    """POST /machines/models — Get available machine models."""
    return _make_request("/machines/models", api_key, token, {"requestFilter": {}}, page=page)


def get_machine_types(api_key, token, page=1):
    """POST /machines/types — Get available machine types."""
    return _make_request("/machines/types", api_key, token, {"requestFilter": {}}, page=page)


# ---- Products ----

def get_products(api_key, token, org_ids=None, product_ids=None, page=1):
    """POST /products — Get products in the catalog."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if product_ids:
        body["requestFilter"]["productIds"] = product_ids
    return _make_request("/products", api_key, token, body, page=page)


def create_products(api_key, token, products):
    """PUT /products — Create new products. products: list of product dicts."""
    body = {"body": products}
    return _make_request("/products", api_key, token, body, method="PUT")


def get_product_variants(api_key, token, org_ids=None, product_ids=None,
                         variant_ids=None, page=1):
    """POST /products/variants — Get product variants."""
    body = {"requestFilter": {}, "routeFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if product_ids:
        body["requestFilter"]["productIds"] = product_ids
    if variant_ids:
        body["routeFilter"]["productVariantIds"] = variant_ids
    return _make_request("/products/variants", api_key, token, body, page=page)


# ---- Selections (Machine Inventory / Planogram) ----

def get_selections(api_key, token, machine_ids=None, site_ids=None,
                   selection_ids=None, include_deleted=False, page=1):
    """POST /selections — Get selections (what's loaded in each machine slot)."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if selection_ids:
        body["requestFilter"]["selectionIds"] = selection_ids
    if include_deleted:
        body["requestFilter"]["includeDeleted"] = True
    return _make_request("/selections", api_key, token, body, page=page)


def create_selections(api_key, token, selections):
    """PUT /selections — Create new selections (assign products to machine slots).

    Each selection dict should have: machineId, productId, price, selectionNumber,
    depth, count, restockTo, isActive, etc.
    """
    body = {"body": selections}
    return _make_request("/selections", api_key, token, body, method="PUT")


def delete_selections(api_key, token, selection_ids):
    """DELETE /selections — Delete selections."""
    body = {"body": [{"id": sid} for sid in selection_ids]}
    return _make_request("/selections", api_key, token, body, method="DELETE")


def apply_selection_deltas(api_key, token, deltas):
    """POST /selections/apply-delta — Apply inventory count changes.

    deltas: list of {"selectionId": int, "delta": int}
    Positive delta = add inventory, negative = remove.
    """
    body = {"body": deltas}
    return _make_request("/selections/apply-delta", api_key, token, body)


# ---- Alerts ----

def get_alerts(api_key, token, machine_ids=None, site_ids=None, org_ids=None,
               alert_ids=None, alert_codes=None, page=1):
    """POST /alerts/ — Get machine alerts."""
    body = {"requestFilter": {}, "routeFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    if alert_ids:
        body["routeFilter"]["alertIds"] = alert_ids
    if alert_codes:
        body["routeFilter"]["alertCodes"] = alert_codes
    return _make_request("/alerts/", api_key, token, body, page=page)


def get_alert_codes(api_key, token, page=1):
    """POST /alerts/codes/ — Get all possible alert codes."""
    return _make_request("/alerts/codes/", api_key, token,
                         {"requestFilter": {}}, page=page)


def clear_alerts(api_key, token, alert_ids):
    """POST /alerts/clear — Clear alerts."""
    body = {"body": [{"id": aid} for aid in alert_ids]}
    return _make_request("/alerts/clear", api_key, token, body)


# ---- Reports ----

def get_transactions(api_key, token, machine_ids=None, site_ids=None,
                     start_date=None, end_date=None,
                     transaction_ids=None, page=1):
    """POST /reports/transactions — Get transaction reports."""
    body = {"requestFilter": {}, "routeFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    if transaction_ids:
        body["routeFilter"]["transactionIdentifiers"] = [str(t) for t in transaction_ids]
    return _make_request("/reports/transactions", api_key, token, body, page=page)


def get_sales_statistics(api_key, token, machine_ids=None, site_ids=None,
                         start_date=None, end_date=None, page=1):
    """POST /reports/product-sales-stats — Get product sales statistics."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    return _make_request("/reports/product-sales-stats", api_key, token, body, page=page)


def get_inventory_adjustments(api_key, token, machine_ids=None, site_ids=None,
                              start_date=None, end_date=None, page=1):
    """POST /reports/inventory-adjustments — Get inventory adjustment events.

    Note: date filters are clamped to a max range of one month.
    """
    body = {"requestFilter": {}, "routeFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    if site_ids:
        body["requestFilter"]["siteIds"] = site_ids
    if start_date:
        body["requestFilter"]["startDate"] = start_date
    if end_date:
        body["requestFilter"]["endDate"] = end_date
    return _make_request("/reports/inventory-adjustments", api_key, token, body, page=page)


# ---- Templates ----

def get_templates(api_key, token, org_ids=None, page=1):
    """POST /templates — Get machine templates."""
    body = {"requestFilter": {}}
    if org_ids:
        body["requestFilter"]["organizationIds"] = org_ids
    return _make_request("/templates", api_key, token, body, page=page)


def get_template_selections(api_key, token, page=1):
    """POST /template-selections — Get template selections."""
    return _make_request("/template-selections", api_key, token,
                         {"requestFilter": {}}, page=page)


# ---- Sessions ----

def get_sessions(api_key, token, machine_ids=None, page=1):
    """POST /sessions/management — Get sessions."""
    body = {"requestFilter": {}}
    if machine_ids:
        body["requestFilter"]["machineIdentifiers"] = [str(m) for m in machine_ids]
    return _make_request("/sessions/management", api_key, token, body, page=page)


# ---- Credit ----

def get_credit_gateways(api_key, token, page=1):
    """POST /credit/gateway — Get credit payment gateways."""
    return _make_request("/credit/gateway", api_key, token,
                         {"requestFilter": {}}, page=page)


def get_charge_keys(api_key, token, page=1):
    """POST /credit/charge-key — Get charge keys."""
    return _make_request("/credit/charge-key", api_key, token,
                         {"requestFilter": {}}, page=page)


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
        machines_resp = get_machines(api_key, token, machine_ids=[str(machine_id)])
        machines = machines_resp if isinstance(machines_resp, list) else machines_resp.get("data", []) if machines_resp else []
        data["machine"] = machines[0] if machines else None
    except Exception:
        pass

    try:
        sel_resp = get_selections(api_key, token, machine_ids=[str(machine_id)])
        data["selections"] = sel_resp if isinstance(sel_resp, list) else sel_resp.get("data", []) if sel_resp else []
    except Exception:
        pass

    try:
        alerts_resp = get_alerts(api_key, token, machine_ids=[str(machine_id)])
        data["alerts"] = alerts_resp if isinstance(alerts_resp, list) else alerts_resp.get("data", []) if alerts_resp else []
    except Exception:
        pass

    return data
