"""
Collect annual-report PDFs for fine-tuning (FinSumm) — NEVER the evaluation companies.

The training data must come from companies that are not in the dev/test Q&A sets or the
app's own reports; otherwise the fine-tuned model would be tested on what it was trained on.

Two ways in (BSE / NSE block automated downloads — download in a browser instead):

1. A folder you filled by hand (recommended)
      ml/data/train_pdfs/inbox/*.pdf  +  ml/data/train_pdfs/inbox/manifest.csv
      manifest columns: file_name,company,sector,fiscal_year
      → python -m ml.collect.collect_reports --from-folder ml/data/train_pdfs/inbox

2. Direct PDF URLs (e.g. company investor-relations pages)
      urls.csv columns: url,company,sector,fiscal_year
      → python -m ml.collect.collect_reports --urls urls.csv
   Polite: one request every 5 s, a normal browser User-Agent, and any blocked or non-PDF
   response is skipped (no attempt to get around access controls).

Suggested companies: ml/collect/train_companies.csv (large caps across sectors, eval companies excluded).
Output: ml/data/train_pdfs/<slug>_<fy>.pdf + ml/data/train_pdfs/manifest.csv
"""
import argparse
import csv
import json
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Optional

from ml.paths import BACKEND_DIR, DATA_DIR, ML_DIR

OUT = DATA_DIR / "train_pdfs"
MANIFEST = OUT / "manifest.csv"
FIELDS = ["file_name", "company", "sector", "fiscal_year", "pages", "source"]


def _key(name: str) -> str:
    """Normalise a company name for comparison ('Adani Enterprises Ltd.' → 'adani enterprises')."""
    name = re.sub(r"\b(limited|ltd|pvt|private|plc|inc|corporation|corp|company|co)\b\.?", " ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def eval_companies() -> set:
    """
    Companies in the dev/test Q&A sets — excluded from training, because the fine-tuned model
    is scored on them. (Companies merely uploaded to the app are allowed; see app_companies.)
    """
    names = set()
    for f in ("rag_gold.json", "rag_dev.json", "rag_gold_v2.json"):
        p = ML_DIR / "eval" / f
        if p.exists():
            names |= {_key(v["company"].split(" FY")[0]) for v in json.loads(p.read_text(encoding="utf-8"))["filings"].values()}
    return names


def app_companies() -> set:
    """Companies uploaded to the app (allowed for training; reported so the overlap is visible)."""
    db = BACKEND_DIR / "annual_reports.db"
    return {_key(r[0]) for r in sqlite3.connect(db).execute("select name from companies")} if db.exists() else set()


def _excluded(company: str, banned: set) -> bool:
    k = _key(company)
    return any(k == b or k.startswith(b) or b.startswith(k) for b in banned if b)


def _is_pdf(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(5) == b"%PDF-"


def _pages(path: Path) -> int:
    import fitz
    with fitz.open(path) as d:
        return d.page_count


def _load_manifest() -> list:
    if not MANIFEST.exists():
        return []
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_manifest(rows: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _add(rows: list, src: Path, company: str, sector: str, fy: str, source: str, banned: set) -> None:
    if _excluded(company, banned):
        print(f"  ✗ {company}: evaluation company — excluded from training")
        return
    if _excluded(company, app_companies()):
        print(f"  · {company}: also uploaded to the app — allowed (not in any evaluation set)")
    if not _is_pdf(src):
        print(f"  ✗ {src.name}: not a PDF")
        return
    problem = _incomplete(src)
    if problem:
        print(f"  ✗ {src.name}: {problem} — re-download it")
        return
    if src.resolve().is_relative_to(OUT.resolve()):
        name = src.resolve().relative_to(OUT.resolve()).as_posix()      # already under train_pdfs/: register in place
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", _key(company)).strip("_")
        name = f"{slug}_fy{fy}.pdf"
        shutil.copyfile(src, OUT / name)
    rows[:] = [r for r in rows if r["file_name"] != name]
    rows.append({"file_name": name, "company": company, "sector": sector, "fiscal_year": fy,
                 "pages": _pages(OUT / name), "source": source})
    print(f"  ✓ {company} FY{fy} → {name} ({rows[-1]['pages']} pages)")


def _incomplete(path: Path) -> Optional[str]:
    """Truncated downloads: linearized PDFs declare their full size (/L) and end with %%EOF."""
    size = path.stat().st_size
    with open(path, "rb") as fh:
        head = fh.read(1024)
        fh.seek(max(0, size - 2048))
        tail = fh.read()
    m = re.search(rb"/L\s+(\d+)", head)
    if m and int(m.group(1)) > size * 1.01:
        return f"incomplete download ({100 * size // int(m.group(1))}% of {int(m.group(1)) // 2**20} MB)"
    if b"%%EOF" not in tail:
        return "incomplete download (no end-of-file marker)"
    try:
        if _pages(path) == 0:
            return "no readable pages"
    except Exception as e:
        return f"unreadable ({e})"
    return None


def _manifest_from_names(folder: Path) -> list:
    """
    No manifest.csv? Derive it from file names like 'TCS_FY2026_Annual_Report.pdf'
    (NSE ticker + fiscal year), with company name and sector from the app's NSE list.
    """
    nse_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "nse_companies.json"
    nse = {c["ticker"].upper(): c for c in json.loads(nse_path.read_text(encoding="utf-8"))}
    aliases = {"MANDM": "M&M"}
    out = []
    for p in sorted(folder.glob("*.pdf")):
        m = re.match(r"(.+?)_FY(\d{4})", p.name, re.I)
        if not m:
            print(f"  ? {p.name}: name is not TICKER_FY<year>_… — add it to manifest.csv by hand")
            continue
        ticker = aliases.get(m.group(1).upper(), m.group(1).upper())
        c = nse.get(ticker)
        if not c:
            print(f"  ? {p.name}: ticker {ticker} not in the NSE list — add it to manifest.csv by hand")
            continue
        out.append({"file_name": p.name, "company": c["name"], "sector": c.get("sector", ""), "fiscal_year": m.group(2)})
    return out


def from_folder(folder: Path) -> None:
    banned, rows = eval_companies(), _load_manifest()
    manifest = folder / "manifest.csv"
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            entries = list(csv.DictReader(f))
    else:
        entries = _manifest_from_names(folder)
        print(f"No manifest.csv — derived {len(entries)} entries from file names")
    for r in entries:
        _add(rows, folder / r["file_name"], r["company"], r.get("sector", ""), r["fiscal_year"], "manual", banned)
    _save_manifest(rows)
    print(f"{len(rows)} training reports registered in {MANIFEST}")


def from_urls(urls_csv: Path) -> None:
    import httpx
    banned, rows = eval_companies(), _load_manifest()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FinSight-research/1.0"}
    tmp = OUT / "_download.pdf"
    OUT.mkdir(parents=True, exist_ok=True)
    with open(urls_csv, newline="", encoding="utf-8") as f, httpx.Client(headers=headers, timeout=120, follow_redirects=True) as client:
        for r in csv.DictReader(f):
            if _excluded(r["company"], banned):
                print(f"  ✗ {r['company']}: evaluation company — excluded")
                continue
            try:
                resp = client.get(r["url"])
            except Exception as e:
                print(f"  ✗ {r['company']}: {e}")
                continue
            if resp.status_code != 200 or not resp.content.startswith(b"%PDF-"):
                print(f"  ✗ {r['company']}: HTTP {resp.status_code} / not a PDF — skipped (download it in a browser)")
            else:
                tmp.write_bytes(resp.content)
                _add(rows, tmp, r["company"], r.get("sector", ""), r["fiscal_year"], r["url"], banned)
            time.sleep(5)
    tmp.unlink(missing_ok=True)
    _save_manifest(rows)
    print(f"{len(rows)} training reports in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--from-folder", type=Path)
    g.add_argument("--urls", type=Path)
    g.add_argument("--show-excluded", action="store_true")
    a = ap.parse_args()
    if a.show_excluded:
        print(sorted(eval_companies()))
    elif a.from_folder:
        from_folder(a.from_folder)
    else:
        from_urls(a.urls)
