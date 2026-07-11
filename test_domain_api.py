"""
test_domain_api.py
==================
Quick test of the Domain Developer API to see what suburb-level
data is available. Run this, paste the output back to Claude.

SETUP
─────
1. Log in to https://developer.domain.com.au
2. Create an app (or use existing) to get client_id + client_secret
3. Fill them in below and run:

   python3 test_domain_api.py
"""

import json
import requests

# ── Fill these in ──────────────────────────────────────────────────────────────
CLIENT_ID     = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"
# ──────────────────────────────────────────────────────────────────────────────

AUTH_URL = "https://auth.domain.com.au/v1/connect/token"
API_BASE = "https://api.domain.com.au/v2"

TEST_SUBURB  = "paddington"
TEST_STATE   = "qld"
TEST_POSTCODE = "4064"


def get_token():
    resp = requests.post(AUTH_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "api_listings_read api_demographics_read",
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print("✅ Token obtained\n")
    return token


def get(token, path, params=None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(f"{API_BASE}{path}", headers=headers, params=params, timeout=15)
    print(f"  GET {path}  →  HTTP {resp.status_code}")
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"  Body: {resp.text[:300]}")
        return None


def main():
    if CLIENT_ID == "YOUR_CLIENT_ID_HERE":
        print("Fill in CLIENT_ID and CLIENT_SECRET first.")
        return

    token = get_token()

    # 1. Suburb search — find the suburb ID we need for other calls
    print("── Suburb search ─────────────────────────────────────────────")
    result = get(token, "/suburbs/_suggest", {"terms": f"{TEST_SUBURB} {TEST_STATE}"})
    if result:
        print(json.dumps(result[:3], indent=2))

    # 2. Demographics / suburb insights
    print("\n── Demographics ──────────────────────────────────────────────")
    result = get(token, "/demographics/suburbinsights", {
        "suburb": TEST_SUBURB, "state": TEST_STATE, "postcode": TEST_POSTCODE
    })
    if result:
        print(json.dumps(result, indent=2)[:2000])

    # 3. Market statistics (if it exists)
    print("\n── Market statistics ─────────────────────────────────────────")
    result = get(token, "/suburbPerformanceStatistics", {
        "suburb": TEST_SUBURB, "state": TEST_STATE, "postcode": TEST_POSTCODE,
        "propertyCategory": "house",
    })
    if result:
        print(json.dumps(result, indent=2)[:2000])

    # 4. Listing count as a proxy
    print("\n── Recent house listings in Paddington QLD ───────────────────")
    result = get(token, "/listings/residential/_search", {})
    # This one is POST — just checking endpoint is accessible
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(f"{API_BASE}/listings/residential/_search", headers=headers, json={
        "listingType": "Sale",
        "propertyTypes": ["House"],
        "locations": [{"state": "QLD", "suburb": "Paddington", "postCode": "4064"}],
        "pageSize": 3,
    })
    print(f"  POST /listings/residential/_search  →  HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total results: {data.get('totalResults', '?')}")
        if data.get("listings"):
            sample = data["listings"][0]
            print(f"  Sample: {sample.get('listing', {}).get('priceDetails', {})}")


if __name__ == "__main__":
    main()
