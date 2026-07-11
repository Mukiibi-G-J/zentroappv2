#!/usr/bin/env python
"""
Test script to debug Sales Order lines update endpoint
"""
import requests
from requests.adapters import HTTPAdapter
import json

# Configuration
# Use 127.0.0.1 instead of demo.localhost to avoid DNS resolution issues
# The Host header will tell Django Tenants which tenant to use
BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/api/sales-orders/3/update_lines/"

# Custom adapter to set Host header for Django Tenants
class TenantHTTPAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
    
    def send(self, request, **kwargs):
        # Set Host header for tenant routing
        request.headers['Host'] = 'demo.localhost:8000'
        return super().send(request, **kwargs)

# Extract access token from the provided JSON
TOKEN_JSON = """{"session":{"signedIn":true,"accessToken":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYzODgyODg4LCJpYXQiOjE3NjM0NTA4ODgsImp0aSI6IjZkZGUwMWRkMWNmZTRiOTJiMjI1OTM5OGMwZDI2OTYyIiwidXNlcl9pZCI6MiwidXNlcm5hbWUiOiJkZWJ1Z19hZG1pbiIsImZ1bGxfbmFtZSI6IkRlYnVnIEFkbWluIiwiZW1haWwiOiJtdWtpaWJpam9zZXBoMTlAZ21haWwuY29tIiwidmVyaWZpZWQiOnRydWUsImlzX3N1cGVydXNlciI6dHJ1ZSwicGhvbmUiOiIrMjU2Nzc3Nzc3Nzc3IiwiYXV0aG9yaXR5IjpbImFkbWluIl0sImVuYWJsZWRfbW9kdWxlcyI6WyJwb3MiXSwic3Vic2NyaXB0aW9uIjp7InBsYW4iOiJTdGFydGVyIFBhY2siLCJzdGF0dXMiOiJhY3RpdmUiLCJpc190cmlhbCI6ZmFsc2UsImlzX2FjdGl2ZSI6dHJ1ZSwidHJpYWxfZW5kX2RhdGUiOiIyMDI2LTAyLTEzIiwic3Vic2NyaXB0aW9uX2VuZF9kYXRlIjoiMjAyNi0wMi0xMyJ9LCJzY2hlbWFfbmFtZSI6ImRlbW8iLCJzdGFydGVyX3BhY2siOnsiaGFzX3N0YXJ0ZXJfcGFjayI6dHJ1ZSwib3JkZXJfaWQiOjQsIm9mZmVyX25hbWUiOiJaZW50cm8gS2l0IC0gRGV2aWNlICsgMyBNb250aHMgRnJlZSIsInBheW1lbnRfYW1vdW50IjoiMTAwMDAwMC4wMCIsInBheW1lbnRfc3RhdHVzIjoiY29tcGxldGVkIiwib3JkZXJfc3RhdHVzIjoiYWN0aXZlIiwiZGV2aWNlX2luY2x1ZGVkIjp0cnVlLCJmcmVlX21vbnRoc19lYXJuZWQiOjMsImZyZWVfcGVyaW9kX2FjdGl2ZSI6dHJ1ZSwiZnJlZV9wZXJpb2RfZGF5c19yZW1haW5pbmciOjg2LCJzdWJzY3JpcHRpb25fYWN0aXZlIjp0cnVlLCJzdWJzY3JpcHRpb25fZGF5c19yZW1haW5pbmciOjg2LCJzaG91bGRfc3RhcnRfbW9udGhseSI6ZmFsc2UsIm9mZmVyX3dhc19hY3RpdmVfYXRfcGF5bWVudCI6dHJ1ZSwib3JkZXJfZGF0ZSI6IjIwMjUtMTEtMTVUMDc6MjE6MTQuNDIyMDg2KzAwOjAwIiwic3Vic2NyaXB0aW9uX3N0YXJ0X2RhdGUiOiIyMDI1LTExLTE1VDA3OjIxOjE0LjQ0MzA4NiswMDowMCIsInN1YnNjcmlwdGlvbl9lbmRfZGF0ZSI6IjIwMjYtMDItMTNUMDc6MjE6MTQuNDQzMDg2KzAwOjAwIiwiZnJlZV9wZXJpb2RfZW5kX2RhdGUiOiIyMDI2LTAyLTEzVDA3OjIxOjE0LjQ0MzA4NiswMDowMCJ9LCJ1c2VyX2dyb3VwcyI6W3siY29kZSI6IkFkbWluIiwibmFtZSI6IkFkbWluIiwiZGVmYXVsdF9yb2xlIjoiQWRtaW4iLCJwZXJtaXNzaW9uX3NldHMiOlsiQ09NUEFOWV9GVUxMIiwiQ09NUEFOWV9WSUVXX09OTFkiLCJDT05GSUdfUEFDS0FHRVNfRlVMTCIsIkNPTkZJR19QQUNLQUdFU19WSUVXX09OTFkiLCJDVVNUT01FUl9CQVNJQyIsIkNVU1RPTUVSX0ZVTEwiLCJDVVNUT01FUl9WSUVXX09OTFkiLCJFWFBFTlNFU19DUkVBVEUiLCJFWFBFTlNFU19GVUxMIiwiRklOQU5DSUFMU19GVUxMIiwiRklOQU5DSUFMU19WSUVXX09OTFkiLCJJVEVNU19GVUxMIiwiSVRFTVNfVklFV19PTkxZIiwiUEFZTUVOVFNfRlVMTCIsIlBBWU1FTlRTX1ZJRVdfT05MWSIsIlBSRVBBWU1FTlRTX0ZVTEwiLCJQUkVQQVlNRU5UU19WSUVXIiwiUFJPRklMRV9GVUxMIiwiUFVSQ0hBU0VTX0NSRUFURSIsIlBVUkNIQVNFU19GVUxMIiwiUk9MRVNfRlVMTCIsIlJPTEVTX1ZJRVdfT05MWSIsIlNBTEVTX0JBU0lDIiwiU0FMRVNfRlVMTCIsIlNBTEVTX0hJU1RPUllfT05MWSIsIlNVUFBMSUVSU19CQVNJQyIsIlNVUFBMSUVSU19GVUxMIiwiU1VQUExJRVJTX1ZJRVdfT05MWSIsIlVTRVJfTUdNVF9CQVNJQyIsIlVTRVJfTUdNVF9GVUxMIiwiVVNFUl9NR01UX1ZJRVdfT05MWSJdfV0sInBlcm1pc3Npb25fc2V0cyI6WyJTQUxFU19GVUxMIiwiU0FMRVNfQkFTSUMiLCJTQUxFU19ISVNUT1JZX09OTFkiLCJQUkVQQVlNRU5UU19GVUxMIiwiUFJFUEFZTUVOVFNfVklFVyIsIkNVU1RPTUVSX0ZVTEwiLCJDVVNUT01FUl9CQVNJQyIsIkNVU1RPTUVSX1ZJRVdfT05MWSIsIklURU1TX0ZVTEwiLCJJVEVNU19WSUVXX09OTFkiLCJQVVJDSEFTRVNfRlVMTCIsIlBVUkNIQVNFU19DUkVBVEUiLCJTVVBQTElFUlNfRlVMTCIsIlNVUFBMSUVSU19CQVNJQyIsIlNVUFBMSUVSU19WSUVXX09OTFkiLCJQQVlNRU5UU19GVUxMIiwiUEFZTUVOVFNfVklFV19PTkxZIiwiRklOQU5DSUFMU19GVUxMIiwiRklOQU5DSUFMU19WSUVXX09OTFkiLCJFWFBFTlNFU19GVUxMIiwiRVhQRU5TRVNfQ1JFQVRFIiwiQ09NUEFOWV9GVUxMIiwiQ09NUEFOWV9WSUVXX09OTFkiLCJST0xFU19GVUxMIiwiUk9MRVNfVklFV19PTkxZIiwiUFJPRklMRV9GVUxMIiwiVVNFUl9NR01UX0ZVTEwiLCJVU0VSX01HTVRfQkFTSUMiLCJVU0VSX01HTVRfVklFV19PTkxZIiwiQ09ORklHX1BBQ0tBR0VTX0ZVTEwiLCJDT05GSUdfUEFDS0FHRVNfVklFV19PTkxZIl0sInJvbGVzIjpbIkFkbWluIl0sInJvbGVfY2VudGVyX21vZHVsZXMiOlsiY29tcGFueSIsInJvbGVzIiwidXNlck1hbmFnZW1lbnQiLCJpdGVtcyIsInB1cmNoYXNlcyIsImZpbmFuY2lhbHMiLCJwcmVQYXltZW50cyIsInByb2ZpbGUiLCJwYXltZW50cyIsImV4cGVuc2VzIiwicmVwb3J0cyIsImN1c3RvbWVycyIsInNhbGVzIiwiY29uZmlnUGFja2FnZXMiLCJzZXR0aW5ncyJdLCJwYWdlX3Blcm1pc3Npb25zIjp7IkNvbXBhbnkgTWFuYWdlbWVudCI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiQ29uZmlndXJhdGlvbiBQYWNrYWdlcyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiQ3VzdG9tZXIgTWFuYWdlbWVudCI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiRXhwZW5zZXMiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIkNoYXJ0IG9mIEFjY291bnRzIjp7InJlYWQiOnRydWUsImluc2VydCI6dHJ1ZSwibW9kaWZ5Ijp0cnVlLCJkZWxldGUiOnRydWV9LCJGaW5hbmNpYWwgUmVwb3J0cyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOmZhbHNlLCJtb2RpZnkiOmZhbHNlLCJkZWxldGUiOmZhbHNlfSwiUHJvZml0ICYgTG9zcyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOmZhbHNlLCJtb2RpZnkiOmZhbHNlLCJkZWxldGUiOmZhbHNlfSwiQWRqdXN0IEludmVudG9yeSI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiQWRqdXN0IEludmVudG9yeSBIaXN0b3J5Ijp7InJlYWQiOnRydWUsImluc2VydCI6dHJ1ZSwibW9kaWZ5Ijp0cnVlLCJkZWxldGUiOnRydWV9LCJJdGVtcyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiUGF5bWVudCBIaXN0b3J5Ijp7InJlYWQiOnRydWUsImluc2VydCI6dHJ1ZSwibW9kaWZ5Ijp0cnVlLCJkZWxldGUiOnRydWV9LCJQYXltZW50cyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiUHJlcGF5bWVudHMiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlByb2ZpbGUgU2V0dGluZ3MiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlB1cmNoYXNlIEhpc3RvcnkiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlB1cmNoYXNlcyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiUm9sZSBNYW5hZ2VtZW50Ijp7InJlYWQiOnRydWUsImluc2VydCI6dHJ1ZSwibW9kaWZ5Ijp0cnVlLCJkZWxldGUiOnRydWV9LCJTYWxlcyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiU2FsZXMgRGFzaGJvYXJkIjp7InJlYWQiOnRydWUsImluc2VydCI6ZmFsc2UsIm1vZGlmeSI6ZmFsc2UsImRlbGV0ZSI6ZmFsc2V9LCJTYWxlcyBJbnZvaWNlIFBhZ2UiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlNhbGVzIEhpc3RvcnkiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlN1cHBsaWVycyI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiUGVybWlzc2lvbiBTZXQgTWFuYWdlbWVudCI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiUm9sZSBDZW50ZXIgTWFuYWdlbWVudCI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfSwiVXNlciBHcm91cCBNYW5hZ2VtZW50Ijp7InJlYWQiOnRydWUsImluc2VydCI6dHJ1ZSwibW9kaWZ5Ijp0cnVlLCJkZWxldGUiOnRydWV9LCJVc2VyIE1hbmFnZW1lbnQiOnsicmVhZCI6dHJ1ZSwiaW5zZXJ0Ijp0cnVlLCJtb2RpZnkiOnRydWUsImRlbGV0ZSI6dHJ1ZX0sIlVzZXIgUm9sZXMgTWFuYWdlbWVudCI6eyJyZWFkIjp0cnVlLCJpbnNlcnQiOnRydWUsIm1vZGlmeSI6dHJ1ZSwiZGVsZXRlIjp0cnVlfX19"}"""

token_data = json.loads(TOKEN_JSON)
ACCESS_TOKEN = token_data["session"]["accessToken"]

# Payload
payload = {
    "system_id": "385ed152-9c6a-4eb4-8b42-8d8c5d0f3043",
    "id": 3,
    "lines": [
        {
            "id": 1,
            "item": "213ed82f-bfdb-4df8-91a7-563849453c54",
            "item_no": "ITM-000002",
            "item_name": "Cement",
            "description": "",
            "quantity": "1",
            "unit_price": "35000",
            "unit_of_measure": "PCS",
            "total_amount": "35000",
            "inventory": 67,
            "type": "Inventory",
            "uom_options": [
                {
                    "code": "PCS",
                    "description": "PCS",
                    "default": True,
                    "quantity_per_unit": 1
                }
            ],
            "system_id": "385ed152-9c6a-4eb4-8b42-8d8c5d0f3043"
        }
    ]
}

# Headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "X-Schema-Name": "demo"  # Backup tenant identifier
}

# Create session with custom adapter to set Host header
session = requests.Session()
session.mount("http://", TenantHTTPAdapter())

# Make request
url = f"{BASE_URL}{ENDPOINT}"
print(f"Making POST request to: {url}")
print(f"Host header will be set to: demo.localhost:8000")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "="*80 + "\n")

try:
    response = session.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print("\nResponse Body:")
    print(json.dumps(response.json(), indent=2))
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

