"""
End-to-end API smoke tests — no OpenAI key needed for most routes.
Run: ./venv/bin/python test_api.py
"""
import json, sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api"
PASS = []
FAIL = []

def req(method, path, data=None, content_type="application/json"):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method,
                                headers={"Content-Type": content_type} if body else {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else {}

def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
        PASS.append(name)
    else:
        print(f"  FAIL  {name}  {detail}")
        FAIL.append(name)

print("\n=== Health ===")
s, b = req("GET", "/health")
check("GET /health → 200", s == 200)
check("health.status == ok", b.get("status") == "ok")
check("health.db is sqlite", "sqlite" in b.get("db",""))

print("\n=== Companies CRUD ===")
s, b = req("GET", "/companies/")
check("GET /companies/ → 200", s == 200)
check("returns list", isinstance(b, list))

# Clean up any leftover data from previous runs
for c in b:
    req("DELETE", f"/companies/{c['id']}")

s, b = req("POST", "/companies/", {"name": "Reliance Industries", "ticker": "RELIANCE",
           "sector": "Energy", "description": "Oil & gas, retail, telecom conglomerate"})
check("POST /companies/ → 201", s == 201)
co_id = b.get("id","")
check("company has id", bool(co_id))
check("company name matches", b.get("name") == "Reliance Industries")

# Duplicate ticker
s, _ = req("POST", "/companies/", {"name": "Dup", "ticker": "RELIANCE"})
check("duplicate ticker → 409", s == 409)

s, b = req("GET", f"/companies/{co_id}")
check("GET /companies/:id → 200", s == 200)
check("company id matches", b.get("id") == co_id)

# Peer suggestions (only 1 company, should return empty)
s, b = req("GET", f"/companies/{co_id}/peers")
check("GET /companies/:id/peers → 200", s == 200)
check("peers is list", isinstance(b, list))

# Second company for comparison tests
s, b2 = req("POST", "/companies/", {"name": "TCS", "ticker": "TCS",
            "sector": "Technology", "description": "IT services and consulting"})
check("POST second company → 201", s == 201)
co2_id = b2.get("id","")

# Peers now (2 companies)
s, p = req("GET", f"/companies/{co_id}/peers")
check("peers returns suggestions with 2 companies", s == 200 and isinstance(p, list))

print("\n=== Filings ===")
s, b = req("GET", "/filings/")
check("GET /filings/ → 200", s == 200)
check("returns list", isinstance(b, list))

s, b = req("GET", f"/filings/?company_id={co_id}")
check("GET /filings/?company_id → 200", s == 200)
check("filtered list is empty", len(b) == 0)

# Non-existent filing
s, b = req("GET", "/filings/nonexistent-id")
check("GET /filings/:bad_id → 404", s == 404)

print("\n=== Q&A (no filings yet) ===")
s, b = req("POST", "/qa/", {"question": "What is revenue?", "filing_ids": ["bad-id"]})
check("QA with bad filing_id → 404", s == 404)

print("\n=== Comparison ===")
s, b = req("POST", "/comparison/", {"filing_ids": ["a"]})
check("comparison with 1 id → 400", s == 400)

print("\n=== Update / Delete ===")
s, b = req("PUT", f"/companies/{co_id}", {"name": "Reliance Industries Ltd",
           "ticker": "RELIANCE", "sector": "Energy", "is_tracked": True})
check("PUT /companies/:id → 200", s == 200)
check("name updated", b.get("name") == "Reliance Industries Ltd")
check("is_tracked updated", b.get("is_tracked") == True)

s, _ = req("DELETE", f"/companies/{co2_id}")
check("DELETE /companies/:id → 204", s == 204)
s, _ = req("GET", f"/companies/{co2_id}")
check("deleted company → 404", s == 404)

print(f"\n{'='*40}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed:", FAIL)
    sys.exit(1)
else:
    print("All tests passed!")
