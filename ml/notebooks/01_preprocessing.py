# %% [markdown]
# # 01 · Data Cleansing & Pre-processing
#
# **Project:** FinSight — Annual Report Analyzer (self-hosted ML)
#
# This notebook turns raw annual-report PDFs into two clean, analysis-ready datasets:
#
# | Dataset | Unit of observation | Used for |
# |---|---|---|
# | `pages_clean.jsonl` | one PDF page | **PageClassifier** (page-type classification) and the KPI-NER training corpus |
# | `kpis_clean.csv` | one KPI of one report | KPI EDA, the financial-health classifier, and the KPI-accuracy baseline |
#
# **Pipeline:** raw extraction → quality audit → text cleansing → noise removal → weak labelling →
# feature engineering → class-imbalance handling → leakage-free split → KPI cleansing → export.
#
# Raw data comes from `python -m ml.preprocess.extract_raw`. It reads every processed report in the app DB
# with PyMuPDF and exports the KPIs found by the current rule-based extractor.

# %%
import json
import warnings
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.utils.class_weight import compute_class_weight

from ml.paths import RAW_DIR, PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR
from ml.preprocess.text_clean import clean_document, normalize_unicode, page_features
from ml.preprocess.label_pages import label_document, scope_of, LABELS
from ml.preprocess.kpi_clean import detect_report_unit_with_fallback, clean_kpis, iqr_outliers

warnings.filterwarnings("ignore")
pd.set_option("display.max_colwidth", 90)
pd.set_option("display.width", 160)
sns.set_theme(style="whitegrid", palette="deep")
SEED = 42

# %% [markdown]
# ## 1. Load the raw data

# %%
pages = pd.read_json(RAW_DIR / "pages_raw.jsonl", lines=True)
reports = pd.read_csv(RAW_DIR / "reports.csv")
kpis_raw = pd.read_csv(RAW_DIR / "kpis_raw.csv")

print(f"pages: {pages.shape}   reports: {reports.shape}   kpis: {kpis_raw.shape}")
reports

# %%
pages.drop(columns="raw_text").head()

# %%
pages.dtypes.to_frame("dtype").T

# %% [markdown]
# ## 2. Data-quality audit (before cleaning)
#
# We measure each known noise source *before* touching the data, so its effect can be shown afterwards.

# %%
raw = pages["raw_text"]
audit = pd.Series({
    "empty pages (< 50 chars)":             (raw.str.strip().str.len() < 50).sum(),
    "pages with ligatures (ﬁ ﬂ ﬀ)":         raw.str.contains("[ﬀ-ﬆ]").sum(),
    "pages with legacy ₹ glyph (`)":         raw.str.contains(r"`\s*(?:in\b|\d)", regex=True).sum(),
    "pages with 'Rs.' / 'INR' notation":     raw.str.contains(r"\bRs\.?\s?\d|\bINR\s?\d", regex=True).sum(),
    "pages with unicode dashes (– — −)":     raw.str.contains("[–—−]").sum(),
    "pages with curly quotes (’ ”)":         raw.str.contains("[’”]").sum(),
    "pages with line-break hyphenation":     raw.str.contains(r"[a-z]-\n[a-z]", regex=True).sum(),
    "exact-duplicate pages":                 raw.duplicated().sum(),
    "missing values (any column)":           pages.isna().sum().sum(),
}, name="count").to_frame()
audit["% of pages"] = (100 * audit["count"] / len(pages)).round(1)
audit

# %% [markdown]
# **Running headers / footers.** Report pages repeat the company name, report title and section name at
# the top or bottom. The cleaner flags any line that appears at a page edge on at least 30% of a report's
# pages. Digits are normalised first, so "Annual Report 2025-26 | 14" and "… | 15" count as the same line.

# %%
from ml.preprocess.text_clean import find_running_lines

for rid, g in pages.groupby("report_id", sort=False):
    counts = find_running_lines(g["raw_text"].tolist())
    top = [(line, round(c / len(g), 2)) for line, c in counts.most_common(4)]
    print(f"{g['company'].iat[0][:28]:<28} {g['fiscal_year'].iat[0]}  →  {top}")

# %% [markdown]
# ## 3. Text cleansing
#
# `clean_document` (in `ml/preprocess/text_clean.py`) applies these steps to every report:
# 1. **Unicode normalisation (NFKC):** ligatures become plain letters (ﬁ → fi) and full-width characters become ASCII.
# 2. **Look-alike characters unified:** dashes become `-`, curly quotes become `'`/`"`, and `Rs.`/`INR`/the legacy backtick glyph become `₹`.
# 3. **Running header/footer removal:** only lines at page edges are checked.
# 4. **Page-number removal:** also restricted to page edges, because bare numbers mid-page are table cells.
# 5. **De-hyphenation** across line breaks (`opera-\ntions` → `operations`).
# 6. **Whitespace normalisation.**

# %%
# Sorted so each report's pages are contiguous and in order (groupby below preserves that order)
pages = pages.sort_values(["report_id", "page_number"]).reset_index(drop=True)
clean_rows, stat_rows = [], []
for rid, g in pages.groupby("report_id", sort=False):
    result = clean_document(g["raw_text"].tolist())
    clean_rows += result.pages
    stat_rows += [st.__dict__ for st in result.stats]

stats = pd.DataFrame(stat_rows)
pages = pd.concat([pages, stats], axis=1)
pages["clean_text"] = clean_rows

summary = stats[["chars_before", "chars_after", "header_footer_lines", "page_number_lines",
                 "hyphen_joins", "unicode_fixes"]].sum()
summary["% characters removed"] = round(100 * (1 - summary.chars_after / summary.chars_before), 2)
summary.to_frame("total")

# %% [markdown]
# ### Before / after: one page

# %%
ex = pages.loc[(pages.header_footer_lines >= 2) & (pages.page_number_lines >= 1) & (pages.hyphen_joins >= 1)
               & (pages.unicode_fixes >= 1)].iloc[0]
print(f"── {ex.company}, page {ex.page_number} ── BEFORE ──\n{ex.raw_text[:900]}")
print(f"\n── AFTER ──\n{ex.clean_text[:900]}")

# %%
check = pd.Series({
    "ligatures remaining":            pages.clean_text.str.contains("[ﬀ-ﬆ]").sum(),
    "legacy ₹ glyphs remaining":      pages.clean_text.str.contains(r"`\s*(?:in\b|\d)", regex=True).sum(),
    "unicode dashes remaining":       pages.clean_text.str.contains("[–—−]").sum(),
    "line-break hyphenations left":   pages.clean_text.str.contains(r"[a-z]-\n[a-z]", regex=True).sum(),
}, name="after cleaning")
check.to_frame()

# %% [markdown]
# ## 4. Noise removal: empty and duplicate pages
#
# * **Near-empty pages** (under 50 characters after cleaning) are covers, full-page photos or divider
#   pages. They carry no text signal for a text classifier.
# * **Duplicate pages** inside the same report (identical cleaned text) are dropped so they do not get
#   extra weight in training.

# %%
n0 = len(pages)
pages["is_empty"] = pages.clean_text.str.len() < 50
pages["is_duplicate"] = pages.duplicated(["report_id", "clean_text"]) & ~pages.is_empty

removed = pd.Series({
    "near-empty pages": pages.is_empty.sum(),
    "  of which contain images": (pages.is_empty & (pages.has_images == 1)).sum(),
    "duplicate pages": pages.is_duplicate.sum(),
})
print(removed.to_string())

# %% [markdown]
# ## 5. Weak labelling (page type)
#
# There is no hand-labelled dataset of Indian annual-report pages, so labels are produced with **weak
# supervision** (`ml/preprocess/label_pages.py`):
# * Search the top of each page for section-heading patterns, e.g. *"Statement of Profit and Loss"* or
#   *"Balance Sheet as at"*, and take the earliest match.
# * Narrative sections print their heading only on the first page, so their label is **carried forward**
#   until the next heading.
# * Labelling runs on the *normalised but un-stripped* text, because running headers such as
#   "Management Discussion & Analysis" are strong section signals.
#
# `label_source` keeps track of where each label came from. A held-out sample will be hand-corrected into
# a **gold** set, which is used to evaluate the classifier honestly.

# %%
labels, sources, scopes = [], [], []
for rid, g in pages.groupby("report_id", sort=False):
    norm = [normalize_unicode(t) for t in g["raw_text"]]
    for (label, src), t in zip(label_document(norm), norm):
        labels.append(label)
        sources.append(src)
        scopes.append(scope_of(t))
pages["label"], pages["label_source"], pages["scope"] = labels, sources, scopes

pd.crosstab(pages.label, pages.label_source, margins=True).loc[LABELS + ["All"]]

# %% [markdown]
# ## 6. Feature engineering
#
# Structural features are computed from the cleaned text. Together with TF-IDF vectors (built in notebook
# 03), they are the inputs to the page classifier.
#
# | feature | why it helps |
# |---|---|
# | `n_words`, `n_lines`, `avg_line_len` | narrative pages have long lines; statement pages have short tabular ones |
# | `n_numbers`, `digit_ratio`, `numeric_line_ratio` | financial statements are dense with numbers |
# | `has_rupee` | currency declarations appear on statement and notes pages |
# | `rel_position` | the order of sections is similar across reports (narrative first, then financials) |
# | `scope` | standalone vs consolidated statements |

# %%
feat = pd.DataFrame([page_features(t) for t in pages.clean_text])
pages = pd.concat([pages, feat], axis=1)
pages["rel_position"] = (pages.page_number / pages.n_pages).round(4)
FEATURES = list(feat.columns) + ["rel_position"]
pages[FEATURES].describe().T.round(3)

# %% [markdown]
# ## 7. Final page dataset and class imbalance

# %%
# Top of the page *before* running-header removal: section headers are the strongest page-type cue,
# so they are kept as a separate model input (`head_text`); available identically at inference time.
pages["head_text"] = pages.raw_text.map(lambda t: normalize_unicode(t)[:400].lower())

data = pages[~pages.is_empty & ~pages.is_duplicate].reset_index(drop=True)
print(f"pages: {n0} raw → {len(data)} after noise removal ({n0 - len(data)} removed)")

counts = data.label.value_counts().reindex(LABELS)
imbalance_ratio = counts.max() / counts.min()
print(f"imbalance ratio (largest / smallest class) = {imbalance_ratio:.0f} : 1")

fig, ax = plt.subplots(figsize=(9, 3.6))
counts.sort_values().plot.barh(ax=ax, color=sns.color_palette("deep")[0])
ax.set_title("Page-type class distribution after cleaning")
ax.set_xlabel("pages")
for i, v in enumerate(counts.sort_values()):
    ax.text(v + 5, i, str(v), va="center", fontsize=9)
plt.tight_layout()
plt.savefig(FIGURES_DIR / "01_class_distribution.png", dpi=130)
plt.show()

# %% [markdown]
# The classes are **heavily imbalanced**. Financial statements (balance sheet, P&L, cash flow) take up only
# a few pages per report, while notes and narrative take hundreds. Plain accuracy would reward a model that
# never predicts the rare statement classes, even though those are the pages KPI extraction depends on.
#
# Two mitigations:
# 1. **Class weights** inversely proportional to frequency (`class_weight="balanced"`), computed below and
#    passed to every model in notebook 03.
# 2. **Evaluation on macro-F1** rather than accuracy, so every class counts equally.
#
# SMOTE oversampling is compared as an alternative in notebook 03 and applied only to the training fold,
# never before splitting.

# %%
present = [l for l in LABELS if l in set(data.label)]
weights = compute_class_weight("balanced", classes=np.array(present), y=data.label)
class_weights = dict(zip(present, np.round(weights, 3)))
pd.Series(class_weights, name="class weight").to_frame().T

# %% [markdown]
# ## 8. Leakage-free train / validation / test split
#
# Pages of the same report share templates, fonts and running text. A random page-level split would
# therefore leak information and inflate scores. We split **by company**, so every report of a company ends
# up on the same side of the split.
#
# With few companies, one random group split can be badly unbalanced (e.g. a test set larger than the
# training set). So we draw many random group partitions and keep the one whose **page** proportions are
# closest to 70 / 10 / 20. The search only looks at group sizes, never at labels or scores, so it adds
# no leakage.

# %%
TARGET = {"train": 0.70, "val": 0.10, "test": 0.20}
companies = data.company.unique()
pages_per_company = data.company.value_counts()
rng = np.random.default_rng(SEED)

best, best_err = None, np.inf
for _ in range(500):
    perm = rng.permutation(companies)
    for i in range(1, len(perm) - 1):
        for j in range(i + 1, len(perm)):
            assign = {**{c: "train" for c in perm[:i]}, **{c: "val" for c in perm[i:j]},
                      **{c: "test" for c in perm[j:]}}
            share = pages_per_company.groupby(pd.Series(assign)).sum() / len(data)
            err = sum(abs(share.get(s, 0) - t) for s, t in TARGET.items())
            if err < best_err:
                best, best_err = assign, err

data["split"] = data.company.map(best)
print(f"chosen split (L1 distance from 70/10/20 = {best_err:.3f}):")
print((data.split.value_counts(normalize=True).reindex(TARGET).round(3)).to_string())

split_table = data.groupby(["split", "company"]).size().unstack(0).fillna(0).astype(int)
split_table.loc["TOTAL"] = split_table.sum()
split_table

# %%
assert not set(data[data.split == "train"].company) & set(data[data.split == "test"].company), "company leakage!"
pd.crosstab(data.label, data.split).reindex(LABELS)

# %% [markdown]
# ## 9. KPI cleansing
#
# The existing rule-based extractor stores **every** KPI as "₹ crore". The audit below shows three
# kinds of problem with that:
# * **Scale:** HAL reports in *₹ lakh* and Airtel in *₹ million*, so their values are inflated 10–100×.
# * **Misreads:** "Revenue from Operations" = 4.89 is a growth % or a note number, not revenue.
# * **Wrong cell:** ratios stored as percentages (D/E = 335.2), values copied from the comparative
#   (prior-year) column, and impossible values (EPS = 1.25 × 10⁹).
#
# ### 9.1 Detect each report's reporting unit
# Reports declare their unit, e.g. *"(₹ in Lakhs)"*. We count declarations on the financial-statement pages
# found in step 5, and fall back to the whole report when there is too little evidence.

# %%
FIN = {"balance_sheet", "profit_loss", "cash_flow", "equity_changes", "notes"}
unit_rows, report_units = [], {}
for rid, g in pages.groupby("report_id", sort=False):
    norm = [normalize_unicode(t) for t in g.raw_text]
    fin = [t for t, l in zip(norm, g.label) if l in FIN]
    unit, counts, scope = detect_report_unit_with_fallback(fin, norm)
    report_units[rid] = unit
    unit_rows.append({"company": g.company.iat[0], "fiscal_year": g.fiscal_year.iat[0],
                      "detected_unit": unit, "evidence_from": scope, "declaration_counts": counts})
pd.DataFrame(unit_rows)

# %% [markdown]
# ### 9.2 Apply the cleansing rules (`ml/preprocess/kpi_clean.py`)
# Every change goes into an audit log, so each corrected value can be traced back to the rule and the reason.

# %%
kpis, audit_log = clean_kpis(kpis_raw, report_units)
audit_log.groupby("rule").size().rename("changes").to_frame().T

# %%
(audit_log[audit_log.rule != "scale"]
 .assign(company=lambda d: d.company.str[:18])
 [["rule", "company", "fiscal_year", "kpi", "old", "new", "reason"]])

# %% [markdown]
# ### 9.3 Before vs after

# %%
def pivot(df, col):
    return (df.assign(report=df.company.str.split().str[0] + " " + df.fiscal_year.astype(str))
              .pivot_table(index="name", columns="report", values=col, aggfunc="first"))

headline = ["Total Revenue", "Profit After Tax (PAT) / Net Profit", "Total Assets",
            "Total Equity / Shareholders Equity", "Current Ratio", "Debt-to-Equity Ratio"]
before = pivot(kpis_raw, "value").reindex(headline)
after = pivot(kpis, "value").reindex(headline)
pd.concat({"BEFORE (raw)": before, "AFTER (₹ crore / x)": after}, axis=1).round(2)

# %% [markdown]
# ### 9.4 Missing values
#
# Every KPI that cleansing rejects becomes `NaN`, and some KPIs were never found. Missingness is **not
# random**: per-share and ratio KPIs are missing more often because they appear in narrative highlights
# rather than in tables. Policy:
# * **Ratios** are *derived* from their components wherever possible (already done in rule 6c). This is
#   domain imputation, not statistical imputation.
# * For the tabular financial-health model, the remaining gaps are imputed with the **median within the
#   same sector**, and a `*_was_missing` indicator is added. This happens inside the training pipeline,
#   after the split.
# * Nothing is imputed in the EDA dataset, so the EDA shows the true missingness.

# %%
miss = pivot(kpis, "value").isna()
fig, ax = plt.subplots(figsize=(8, 7))
sns.heatmap(miss, cbar=False, cmap=["#4c72b0", "#f0f0f0"], linewidths=.4, ax=ax)
ax.set_title("KPI missingness after cleansing (light = missing)")
ax.set_xlabel("")
ax.set_ylabel("")
plt.tight_layout()
plt.savefig(FIGURES_DIR / "01_kpi_missingness.png", dpi=130)
plt.show()
print(f"overall KPI missingness: {miss.values.mean():.1%}")

# %% [markdown]
# ### 9.5 Outliers: Tukey IQR rule on log₁₀ values
#
# Monetary KPIs span 5+ orders of magnitude, from ₹0.2 crore (a small-cap) to ₹5,50,000 crore (Airtel's
# total assets). An IQR rule on raw values would flag every large company, so it is applied to
# **log₁₀ |value|** within each KPI. Values that survive the domain rules but fall outside the log-IQR fence
# are **flagged, not dropped**: a small-cap company is a legitimate outlier.

# %%
money = kpis[kpis.unit == "₹ crore"].dropna(subset=["value"]).copy()
money["log_outlier"] = money.groupby("name")["value"].transform(
    lambda s: iqr_outliers(s) if s.notna().sum() >= 4 else False)
money.loc[money.log_outlier, ["company", "fiscal_year", "name", "value"]]

# %% [markdown]
# ## 10. Export

# %%
keep = ["report_id", "company", "sector", "fiscal_year", "page_number", "n_pages", "label", "label_source",
        "scope", "split", "clean_text", "head_text"] + FEATURES
data[keep].to_json(PROCESSED_DIR / "pages_clean.jsonl", orient="records", lines=True, force_ascii=False)
kpis.to_csv(PROCESSED_DIR / "kpis_clean.csv", index=False)
audit_log.to_csv(PROCESSED_DIR / "kpi_audit_log.csv", index=False)
(PROCESSED_DIR / "class_weights.json").write_text(json.dumps(class_weights, indent=2), encoding="utf-8")

summary_out = {
    "raw_pages": int(n0),
    "clean_pages": int(len(data)),
    "reports": int(reports.shape[0]),
    "companies": int(data.company.nunique()),
    "chars_removed_pct": float(summary["% characters removed"]),
    "header_footer_lines_removed": int(summary.header_footer_lines),
    "page_number_lines_removed": int(summary.page_number_lines),
    "hyphen_joins": int(summary.hyphen_joins),
    "empty_pages_removed": int(pages.is_empty.sum()),
    "duplicate_pages_removed": int(pages.is_duplicate.sum()),
    "quality_audit": {k: int(v) for k, v in audit["count"].items()},
    "class_counts": {k: int(v) for k, v in counts.items()},
    "imbalance_ratio": round(float(imbalance_ratio), 1),
    "class_weights": {k: float(v) for k, v in class_weights.items()},
    "splits": {s: int(n) for s, n in data.split.value_counts().items()},
    "split_companies": {s: sorted(g.company.unique().tolist()) for s, g in data.groupby("split")},
    "kpi_rows_raw": int(len(kpis_raw)),
    "kpi_rows_clean": int(kpis.value.notna().sum()),
    "kpi_rule_counts": {k: int(v) for k, v in audit_log.groupby("rule").size().items()},
    "report_units": {r["company"] + " " + str(r["fiscal_year"]): r["detected_unit"] for r in unit_rows},
    "kpi_missingness": round(float(miss.values.mean()), 3),
}
(REPORTS_DIR / "preprocessing_summary.json").write_text(json.dumps(summary_out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: summary_out[k] for k in ("raw_pages", "clean_pages", "splits", "kpi_rule_counts")}, indent=1))

# %% [markdown]
# ## Summary
#
# | Step | Result |
# |---|---|
# | Text cleansing | Unicode/ligature/₹ normalisation, running headers and footers, page numbers, hyphenation (see table §3) |
# | Noise removal | Near-empty and duplicate pages dropped (§4) |
# | Labels | 10 page types by weak supervision, with provenance recorded (§5) |
# | Features | 9 structural features, plus TF-IDF in notebook 03 (§6) |
# | Imbalance | Measured, with balanced class weights computed; evaluation uses macro-F1 (§7) |
# | Split | Grouped by company, with leakage asserted absent (§8) |
# | KPIs | Unit-normalised to ₹ crore, misreads rejected, ratios recomputed or derived, outliers flagged, full audit log (§9) |
#
# Next: **02_eda**.
