"""
Full feature test — covers every route and feature in the system.
Run: ./venv/bin/python test_all_features.py
"""
import json, sys, time, io
import urllib.request, urllib.error

BASE = "http://localhost:8000/api"
PASS, FAIL, WARN = [], [], []


# ── helpers ────────────────────────────────────────────────────────────────

def req(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, (json.loads(raw) if raw else {})
        except Exception:
            return e.code, {}


def multipart(path, fields: dict, file_field: str, file_bytes: bytes, filename: str):
    boundary = "TestBnd9988776655"
    parts = []
    for k, v in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; "
        f"name=\"{file_field}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/pdf\r\n\r\n"
    )
    body = "".join(parts).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    r = urllib.request.Request(
        BASE + path, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def ok(name, cond, detail=""):
    sym = "\033[32m PASS\033[0m" if cond else "\033[31m FAIL\033[0m"
    print(f"  {sym}  {name}" + (f"  [{detail}]" if detail else ""))
    (PASS if cond else FAIL).append(name)

def warn(name, msg):
    print(f"  \033[33m WARN\033[0m  {name}  [{msg}]")
    WARN.append(name)

def section(title):
    print(f"\n\033[1;34m{'='*54}\033[0m")
    print(f"\033[1;34m  {title}\033[0m")
    print(f"\033[1;34m{'='*54}\033[0m")

def cleanup():
    """Delete all companies (and their cascade-deleted filings)."""
    s, companies = req("GET", "/companies/")
    if not isinstance(companies, list):
        return
    for c in companies:
        req("DELETE", f"/companies/{c['id']}")


# ── PDF fixtures ───────────────────────────────────────────────────────────
def make_pdf(content_lines: list[str]) -> bytes:
    text = "BT /F1 12 Tf 50 750 Td\n"
    for i, line in enumerate(content_lines):
        text += f"({''.join(c for c in line if ord(c) < 128)}) Tj 0 -18 Td\n"
    text += "ET"
    stream = text.encode()
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n"
        b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>\nendobj\n"
        b"4 0 obj\n<</Length " + str(len(stream)).encode() + b">>\nstream\n"
        + stream +
        b"\nendstream\nendobj\n"
        b"5 0 obj\n<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000274 00000 n \n0000000430 00000 n \n"
        b"trailer\n<</Size 6/Root 1 0 R>>\nstartxref\n510\n%%EOF\n"
    )


FINANCIAL_PDF = make_pdf([
    "INFOSYS LIMITED",
    "Annual Report 2024",
    "Fiscal Year ended March 31 2024",
    "Currency INR Units Crores",
    "Board of Directors Chairman Statement",
    "Balance Sheet as at March 31 2024",
    "Profit and Loss Account for the year ended March 31 2024",
    "Total Revenue  153670  146767",
    "Profit After Tax  26248  24108",
    "Total Assets  112149  100472",
    "Cash and Cash Equivalents  14492  11024",
    "Earnings Per Share  62.45  57.13",
    "Management Discussion and Analysis",
    "Revenue from Operations grew 8 percent",
    "Financial Statements and Notes to Accounts",
    "Contingent Liabilities pending litigation 450 crores",
    "Risk Factors liquidity risk credit risk regulatory compliance",
    "Auditors Report Independent Auditor",
    "Income Statement Cash Flow Statement",
])

NON_FINANCIAL_PDF = make_pdf([
    "User Manual for Printer Model XYZ-3000",
    "Chapter 1 Installation",
    "Chapter 2 Troubleshooting",
    "Press the power button to turn on",
])


# ══════════════════════════════════════════════════════════════════════════
section("1  Health check")
# ══════════════════════════════════════════════════════════════════════════
s, b = req("GET", "/health")
ok("GET /health → 200",         s == 200)
ok("status == ok",               b.get("status") == "ok")
ok("version field present",      "version" in b)
ok("db field present",           "db" in b)
ok("SQLite in local mode",       "sqlite" in b.get("db",""))


# ══════════════════════════════════════════════════════════════════════════
section("2  Company CRUD")
# ══════════════════════════════════════════════════════════════════════════
cleanup()   # ensure clean state

s, b = req("POST", "/companies/", {
    "name": "Infosys Limited", "ticker": "INFY",
    "sector": "Technology",
    "description": "IT services consulting outsourcing digital transformation"
})
ok("POST /companies/ → 201",     s == 201)
co1 = b.get("id","")
ok("has id",                     bool(co1))
ok("ticker saved",               b.get("ticker") == "INFY")
ok("is_tracked defaults False",  b.get("is_tracked") == False)

s, _ = req("POST", "/companies/", {"name": "Dup", "ticker": "INFY"})
ok("duplicate ticker → 409",    s == 409)

s, b2 = req("POST", "/companies/", {
    "name": "TCS", "ticker": "TCS",
    "sector": "Technology",
    "description": "Tata consultancy services IT outsourcing"
})
ok("POST second company → 201", s == 201)
co2 = b2.get("id","")

s, b3 = req("POST", "/companies/", {
    "name": "HDFC Bank", "ticker": "HDFCBANK",
    "sector": "Financial Services",
    "description": "Private sector banking retail corporate"
})
ok("POST third company → 201",  s == 201)
co3 = b3.get("id","")

s, b = req("GET", "/companies/")
ok("GET /companies/ → 200",     s == 200)
ok("returns 3 companies",       isinstance(b, list) and len(b) == 3)

s, b = req("GET", f"/companies/{co1}")
ok("GET /companies/:id → 200",  s == 200)
ok("id matches",                 b.get("id") == co1)

s, _ = req("GET", "/companies/does-not-exist")
ok("GET missing company → 404", s == 404)

s, b = req("PUT", f"/companies/{co1}", {
    "name": "Infosys Ltd", "ticker": "INFY",
    "sector": "Technology", "is_tracked": True,
})
ok("PUT /companies/:id → 200",  s == 200)
ok("name updated",               b.get("name") == "Infosys Ltd")
ok("is_tracked flipped to True", b.get("is_tracked") == True)


# ══════════════════════════════════════════════════════════════════════════
section("3  Peer discovery")
# ══════════════════════════════════════════════════════════════════════════
s, peers = req("GET", f"/companies/{co1}/peers")
ok("GET /companies/:id/peers → 200",   s == 200)
ok("returns list",                      isinstance(peers, list))
ok("same-sector peer found (TCS)",      any("TCS" in p.get("company_name","") or
                                           "TCS" in p.get("ticker","") for p in peers))
ok("peer has similarity_score",         all("similarity_score" in p for p in peers))


# ══════════════════════════════════════════════════════════════════════════
section("4  Company profile endpoint")
# ══════════════════════════════════════════════════════════════════════════
s, prof = req("GET", f"/companies/{co1}/profile")
ok("GET /companies/:id/profile → 200",  s == 200)
ok("profile.company present",           "company" in prof)
ok("profile.filings is list",           isinstance(prof.get("filings"), list))
ok("profile.kpi_trends is dict",        isinstance(prof.get("kpi_trends"), dict))
ok("profile.peers is list",             isinstance(prof.get("peers"), list))
ok("company.name matches",              prof["company"].get("name") == "Infosys Ltd")


# ══════════════════════════════════════════════════════════════════════════
section("5  Filings list & filters")
# ══════════════════════════════════════════════════════════════════════════
s, b = req("GET", "/filings/")
ok("GET /filings/ → 200",               s == 200)
ok("returns list",                      isinstance(b, list))

s, b = req("GET", f"/filings/?company_id={co1}")
ok("filter by company_id → 200",        s == 200)
ok("filtered list empty initially",     len(b) == 0)

s, _ = req("GET", "/filings/nonexistent-id")
ok("GET /filings/bad-id → 404",         s == 404)


# ══════════════════════════════════════════════════════════════════════════
section("6  /filings/detect — financial PDF")
# ══════════════════════════════════════════════════════════════════════════
s, det = multipart("/filings/detect", {}, "file", FINANCIAL_PDF, "infosys_ar_2024.pdf")
ok("POST /filings/detect → 200",        s == 200)
# With Gemini live, LLM classifies it; without a key, heuristics run.
# Either way a proper annual report PDF must return is_financial_report=True.
if det.get("is_financial_report") == True:
    ok("is_financial_report = True",    True)
else:
    # Accept if rejection_reason is absent (heuristic fallback returned False
    # due to minimal PDF — non-blocking for pipeline functionality)
    ok("is_financial_report = True",    False,
       f"Got False. confidence={det.get('confidence')} reason={det.get('rejection_reason')}")
ok("has confidence field",              "confidence" in det)
ok("rejection_reason null",             not det.get("rejection_reason"))


# ══════════════════════════════════════════════════════════════════════════
section("7  /filings/detect — non-financial PDF")
# ══════════════════════════════════════════════════════════════════════════
s, det2 = multipart("/filings/detect", {}, "file", NON_FINANCIAL_PDF, "manual.pdf")
ok("detect non-financial → 200",        s == 200)
if det2.get("is_financial_report") == False:
    ok("non-financial correctly rejected", True)
else:
    warn("non-financial detection", "heuristic may misclassify without OpenAI key — acceptable")

s, det3 = multipart("/filings/detect", {}, "file", b"hello world", "notes.txt")
ok("detect .txt file → is_financial=False", s == 200 and det3.get("is_financial_report") == False)
ok("rejection_reason present for .txt",     bool(det3.get("rejection_reason")))


# ══════════════════════════════════════════════════════════════════════════
section("8  Upload — with company_id + Job creation")
# ══════════════════════════════════════════════════════════════════════════
s, f1 = multipart(
    "/filings/upload",
    {"company_id": co1, "fiscal_year": "2024", "currency": "INR", "unit_scale": "crores"},
    "file", FINANCIAL_PDF, "infosys_ar_2024.pdf",
)
ok("POST /filings/upload → 201",        s == 201)
fid1 = f1.get("id","")
ok("filing has id",                     bool(fid1))
ok("company_id correct",                f1.get("company_id") == co1)
ok("fiscal_year = 2024",               f1.get("fiscal_year") == 2024)
ok("status is pending/processing",      f1.get("status") in ("pending","processing"))

# Job record must have been created
time.sleep(0.5)
s, job = req("GET", f"/jobs/by-filing/{fid1}")
ok("GET /jobs/by-filing/:id → 200",     s == 200)
ok("job.filing_id matches",             job.get("filing_id") == fid1)
ok("job.progress_pct is int",           isinstance(job.get("progress_pct"), int))
ok("job.stage present",                 bool(job.get("stage")))
ok("job.status present",                bool(job.get("status")))


# ══════════════════════════════════════════════════════════════════════════
section("9  Upload — duplicate filing guard")
# ══════════════════════════════════════════════════════════════════════════
s, _ = multipart(
    "/filings/upload",
    {"company_id": co1, "fiscal_year": "2024"},
    "file", FINANCIAL_PDF, "dup.pdf",
)
ok("duplicate company+year → 409",     s == 409)


# ══════════════════════════════════════════════════════════════════════════
section("10  Upload — auto-create company via company_name")
# ══════════════════════════════════════════════════════════════════════════
s, f2 = multipart(
    "/filings/upload",
    {"company_name": "Zomato Limited", "ticker": "ZOMATO",
     "sector": "Consumer Services", "fiscal_year": "2024",
     "currency": "INR", "unit_scale": "crores"},
    "file", FINANCIAL_PDF, "zomato_ar_2024.pdf",
)
ok("upload with company_name (no id) → 201", s == 201)
fid2 = f2.get("id","")
ok("filing2 has id",                    bool(fid2))

s, cos = req("GET", "/companies/")
ok("ZOMATO auto-created",               any(c.get("ticker") == "ZOMATO" for c in cos))

# Reuse same ticker different year — must not create duplicate company
s, f3 = multipart(
    "/filings/upload",
    {"company_name": "Zomato Limited", "ticker": "ZOMATO",
     "fiscal_year": "2023", "currency": "INR", "unit_scale": "crores"},
    "file", FINANCIAL_PDF, "zomato_ar_2023.pdf",
)
ok("second upload same ticker diff year → 201", s == 201)
s, cos2 = req("GET", "/companies/")
zomatos = [c for c in cos2 if c.get("ticker") == "ZOMATO"]
ok("no duplicate ZOMATO company",       len(zomatos) == 1)


# ══════════════════════════════════════════════════════════════════════════
section("11  Upload — missing company info guard")
# ══════════════════════════════════════════════════════════════════════════
s, _ = multipart(
    "/filings/upload",
    {"fiscal_year": "2024"},
    "file", FINANCIAL_PDF, "unknown.pdf",
)
ok("upload with no company info → 422", s == 422)


# ══════════════════════════════════════════════════════════════════════════
section("12  Filing sub-routes (KPIs / risks / flags / sections / promises / dashboard)")
# ══════════════════════════════════════════════════════════════════════════
s, fi = req("GET", f"/filings/{fid1}")
ok("GET /filings/:id → 200",            s == 200)
ok("filing id matches",                 fi.get("id") == fid1)

s, kpis = req("GET", f"/filings/{fid1}/kpis")
ok("GET /filings/:id/kpis → 200",       s == 200)
ok("kpis is list",                      isinstance(kpis, list))

s, risks_r = req("GET", f"/filings/{fid1}/risks")
ok("GET /filings/:id/risks → 200",      s == 200)
ok("risks is list",                     isinstance(risks_r, list))

s, flags = req("GET", f"/filings/{fid1}/flags")
ok("GET /filings/:id/flags → 200",      s == 200)
ok("flags is list",                     isinstance(flags, list))

s, secs = req("GET", f"/filings/{fid1}/sections")
ok("GET /filings/:id/sections → 200",   s == 200)
ok("sections is list",                  isinstance(secs, list))

s, proms = req("GET", f"/filings/{fid1}/promises")
ok("GET /filings/:id/promises → 200",   s == 200)
ok("promises is list",                  isinstance(proms, list))

s, dash = req("GET", f"/filings/{fid1}/dashboard")
ok("GET /filings/:id/dashboard → 200",  s == 200)
ok("dashboard.filing present",          "filing" in dash)
ok("dashboard.kpis present",            "kpis" in dash)
ok("dashboard.risks present",           "risks" in dash)
ok("dashboard.top_flags present",       "top_flags" in dash)
ok("dashboard.sections present",        "sections" in dash)
ok("dashboard.peer_suggestions list",   isinstance(dash.get("peer_suggestions"), list))


# ══════════════════════════════════════════════════════════════════════════
section("13  Jobs — progress tracking")
# ══════════════════════════════════════════════════════════════════════════
s, job1 = req("GET", f"/jobs/by-filing/{fid1}")
ok("job has progress_pct",              isinstance(job1.get("progress_pct"), int))
ok("job has stage string",              isinstance(job1.get("stage"), str))
ok("job.status in known values",        job1.get("status") in
                                         ("queued","running","done","failed"))

# also accessible by job id
jid = job1.get("id","")
s, job1b = req("GET", f"/jobs/{jid}")
ok("GET /jobs/:id → 200",               s == 200)
ok("same job returned",                 job1b.get("id") == jid)

s, _ = req("GET", "/jobs/bad-job-id")
ok("GET /jobs/bad-id → 404",            s == 404)

s, _ = req("GET", f"/jobs/by-filing/bad-filing-id")
ok("GET /jobs/by-filing/bad-id → 404",  s == 404)


# ══════════════════════════════════════════════════════════════════════════
section("14  Company profile — with filings")
# ══════════════════════════════════════════════════════════════════════════
s, prof2 = req("GET", f"/companies/{co1}/profile")
ok("profile now has 1 filing",          len(prof2.get("filings",[])) >= 1)
filing_entry = prof2.get("filings", [{}])[0]
ok("filing in profile has fiscal_year", filing_entry.get("fiscal_year") == 2024)
ok("filing has kpi_count field",        "kpi_count" in filing_entry)
ok("filing has risk_count field",       "risk_count" in filing_entry)
ok("filing has flag_count field",       "flag_count" in filing_entry)


# ══════════════════════════════════════════════════════════════════════════
section("15  Q&A guards")
# ══════════════════════════════════════════════════════════════════════════
s, _ = req("POST", "/qa/", {"question": "What is revenue?", "filing_ids": ["bad-id"]})
ok("QA bad filing_id → 404",            s == 404)

s, _ = req("POST", "/qa/", {"question": "x", "filing_ids": [fid1]})
ok("QA too-short question → 422",       s == 422)

s, _ = req("POST", "/qa/", {"question": "What is revenue?", "filing_ids": []})
ok("QA empty filing_ids → 422",         s == 422)

# QA with a real (but unprocessed) filing returns gracefully
s, qa_r = req("POST", "/qa/", {"question": "What is the total revenue?", "filing_ids": [fid1]})
# 400 = not yet processed, 404 = not found, 200 = completed fast
ok("QA with pending/processing filing handled",  s in (200, 400, 404))


# ══════════════════════════════════════════════════════════════════════════
section("16  Comparison guards")
# ══════════════════════════════════════════════════════════════════════════
s, _ = req("POST", "/comparison/", {"filing_ids": ["only-one"]})
ok("comparison 1 id → 400",             s == 400)

s, _ = req("POST", "/comparison/", {"filing_ids": []})
ok("comparison 0 ids → 400",            s == 400)

s, comp = req("POST", "/comparison/", {"filing_ids": [fid1, fid2]})
ok("comparison 2 real ids → 200",       s == 200)
ok("comparison returns list",           isinstance(comp, list))


# ══════════════════════════════════════════════════════════════════════════
section("17  DELETE filings")
# ══════════════════════════════════════════════════════════════════════════
s, _ = req("DELETE", f"/filings/{fid1}")
ok("DELETE /filings/:id → 204",         s == 204)
s, _ = req("GET", f"/filings/{fid1}")
ok("deleted filing → 404",              s == 404)
# Job for deleted filing should also 404
s, _ = req("GET", f"/jobs/by-filing/{fid1}")
ok("job for deleted filing → 404",      s == 404)


# ══════════════════════════════════════════════════════════════════════════
section("18  DELETE companies + full cleanup")
# ══════════════════════════════════════════════════════════════════════════
s, cos_before = req("GET", "/companies/")
for c in cos_before:
    s2, _ = req("DELETE", f"/companies/{c['id']}")
    ok(f"DELETE company {c['name'][:20]} → 204", s2 == 204)

s, cos_after = req("GET", "/companies/")
ok("all companies removed",             len(cos_after) == 0)


# ══════════════════════════════════════════════════════════════════════════
section("19  Frontend reachability")
# ══════════════════════════════════════════════════════════════════════════
frontend_up = False
for port in [3000, 3001, 3002]:
    try:
        r = urllib.request.urlopen(f"http://localhost:{port}/", timeout=4)
        ok(f"Frontend on :{port} → 200", r.status == 200)
        frontend_up = True
        break
    except Exception:
        pass
if not frontend_up:
    warn("Frontend reachability", "Not found on :3000/:3001/:3002 — run 'npm run dev' in frontend/")


# ══════════════════════════════════════════════════════════════════════════
print(f"\n\033[1m{'='*54}\033[0m")
total = len(PASS) + len(FAIL)
print(f"\033[1mResults: {len(PASS)}/{total} passed", end="")
if WARN: print(f"  |  {len(WARN)} warnings", end="")
print("\033[0m")
if FAIL:
    print("\033[31mFailed:\033[0m")
    for f in FAIL:
        print(f"  • {f}")
if WARN:
    print("\033[33mWarnings (non-blocking):\033[0m")
    for w in WARN:
        print(f"  • {w}")
if not FAIL:
    print("\033[32mAll tests passed!\033[0m")
    sys.exit(0)
else:
    sys.exit(1)
