"""
Step 0 — collect raw data (no cleaning here; that is notebook 01).

Sources
  * Annual-report PDFs already uploaded through the app (paths + company/sector/
    year metadata come from the backend SQLite DB).
  * Optional extra PDFs: put them in a folder with a `manifest.csv`
    (columns: file_name, company, sector, fiscal_year) and pass --extra-dir.
  * KPIs the current rule-based extractor stored in the DB (for KPI EDA and as
    the "before" baseline).

Outputs (ml/data/raw/)
  pages_raw.jsonl — one record per PDF page: report_id, company, sector,
                    fiscal_year, page_number, n_pages, raw_text
  kpis_raw.csv    — KPI rows joined with company/filing metadata
  reports.csv     — one row per report

Usage (from repo root):
    python -m ml.preprocess.extract_raw [--extra-dir path/to/pdfs]
"""
import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import fitz  # PyMuPDF

from ml.paths import BACKEND_DIR, RAW_DIR

DB_PATH = BACKEND_DIR / "annual_reports.db"


def _reports_from_db() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT f.id, f.file_path, f.file_name, f.fiscal_year, c.name AS company, c.sector
           FROM filings f JOIN companies c ON c.id = f.company_id
           WHERE f.status = 'completed'"""
    ).fetchall()
    con.close()
    reports = []
    for r in rows:
        path = Path(r["file_path"])
        if not path.is_absolute():
            path = BACKEND_DIR / path
        reports.append({
            "report_id": r["id"], "path": path, "file_name": r["file_name"],
            "company": r["company"], "sector": r["sector"] or "Unknown",
            "fiscal_year": r["fiscal_year"],
        })
    return reports


def _reports_from_dir(extra_dir: Path) -> list[dict]:
    with open(extra_dir / "manifest.csv", newline="", encoding="utf-8") as f:
        return [
            {
                "report_id": hashlib.sha1(row["file_name"].encode()).hexdigest()[:12],
                "path": extra_dir / row["file_name"], "file_name": row["file_name"],
                "company": row["company"], "sector": row.get("sector") or "Unknown",
                "fiscal_year": int(row["fiscal_year"]),
            }
            for row in csv.DictReader(f)
        ]


def _export_kpis() -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        """SELECT k.name, k.value, k.unit, k.currency, k.page_number, k.is_verified,
                  k.category, k.source_text, f.id AS report_id, f.fiscal_year,
                  c.name AS company, c.sector
           FROM kpis k JOIN filings f ON f.id = k.filing_id JOIN companies c ON c.id = f.company_id"""
    )
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    con.close()
    with open(RAW_DIR / "kpis_raw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


def main(extra_dir: Path | None) -> None:
    reports = _reports_from_db() + (_reports_from_dir(extra_dir) if extra_dir else [])
    n_pages = 0
    with open(RAW_DIR / "pages_raw.jsonl", "w", encoding="utf-8") as out, \
         open(RAW_DIR / "reports.csv", "w", newline="", encoding="utf-8") as rep:
        rw = csv.writer(rep)
        rw.writerow(["report_id", "file_name", "company", "sector", "fiscal_year", "n_pages"])
        for r in reports:
            if not r["path"].exists():
                print(f"skip (missing): {r['path']}")
                continue
            doc = fitz.open(r["path"])
            rw.writerow([r["report_id"], r["file_name"], r["company"], r["sector"], r["fiscal_year"], doc.page_count])
            for i, page in enumerate(doc):
                out.write(json.dumps({
                    "report_id": r["report_id"], "company": r["company"], "sector": r["sector"],
                    "fiscal_year": r["fiscal_year"], "page_number": i + 1, "n_pages": doc.page_count,
                    "has_images": int(bool(page.get_images())),
                    "raw_text": page.get_text(),
                }, ensure_ascii=False) + "\n")
            n_pages += doc.page_count
            print(f"{r['file_name']}: {doc.page_count} pages")
            doc.close()

    n_kpis = _export_kpis()
    print(f"\n{len(reports)} reports, {n_pages} pages, {n_kpis} KPI rows → {RAW_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-dir", type=Path, default=None)
    main(ap.parse_args().extra_dir)
