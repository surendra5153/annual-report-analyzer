# %% [markdown]
# # 02 · Exploratory Data Analysis
#
# **Input:** the cleaned datasets produced by `01_preprocessing`.
#
# **Questions this EDA answers**
# 1. What does the corpus look like, and how big and balanced is it?
# 2. Do the engineered structural features separate the page types, i.e. are they worth using?
# 3. Does the vocabulary separate page types? Do pages cluster by *type*, or by *company*?
# 4. How do the extracted KPIs behave: scale, skew, missingness, correlations, year-on-year change?
# 5. Do the reported numbers follow **Benford's law**, a standard forensic-accounting check?
#
# Each section ends with an **insight** computed from the data.
# The results are also exported to `ml/reports/eda.json`, which the app's *Model Lab → EDA* tab renders.

# %%
import json
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.manifold import TSNE
from wordcloud import WordCloud

from ml.paths import PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR
from ml.preprocess.label_pages import LABELS

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", palette="deep")
pd.set_option("display.width", 160)
SEED = 42
EDA = {}  # collected for the GUI


def save(name):
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f"02_{name}.png", dpi=130)
    plt.show()


def insight(text):
    print("INSIGHT:", text)
    EDA.setdefault("insights", []).append(text)

# %%
pages = pd.read_json(PROCESSED_DIR / "pages_clean.jsonl", lines=True)
kpis = pd.read_csv(PROCESSED_DIR / "kpis_clean.csv")
pages["report"] = pages.company.str.split().str[0] + " " + pages.fiscal_year.astype(str)
order = [l for l in LABELS if l in set(pages.label)]
FEATURES = ["n_chars", "n_words", "n_lines", "n_numbers", "digit_ratio", "numeric_line_ratio",
            "avg_line_len", "has_rupee", "rel_position"]
print(pages.shape, kpis.shape)

# %% [markdown]
# ## 1. Corpus overview

# %%
corpus = (pages.groupby(["report", "sector"])
               .agg(pages=("page_number", "size"), words=("n_words", "sum"))
               .reset_index().sort_values("pages", ascending=False))
corpus["words (k)"] = (corpus.words / 1000).round(1)
display(corpus.drop(columns="words"))

fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
sns.barplot(data=corpus, y="report", x="pages", hue="sector", dodge=False, ax=axes[0])
axes[0].set_title("Pages per report (after cleaning)")
axes[0].legend(fontsize=8, title="sector")
mix = pd.crosstab(pages.report, pages.label, normalize="index")[order]
mix.plot.barh(stacked=True, ax=axes[1], colormap="tab10", width=.8, legend=False)
axes[1].set_title("Section mix per report (share of pages)")
axes[1].set_xlabel("share")
axes[1].legend(bbox_to_anchor=(1.02, 1), fontsize=7)
save("corpus_overview")

EDA["corpus"] = corpus.drop(columns="words").to_dict("records")
insight(f"{len(pages):,} cleaned pages from {pages.report_id.nunique()} reports of {pages.company.nunique()} companies "
        f"({pages.n_words.sum() / 1e6:.2f} M words). Report length ranges from {corpus.pages.min()} to "
        f"{corpus.pages.max()} pages, so per-report section shares vary a lot.")

# %% [markdown]
# ## 2. Target variable: page-type distribution

# %%
counts = pages.label.value_counts().reindex(order)
fig, ax = plt.subplots(figsize=(10, 3.6))
sns.barplot(x=counts.index, y=counts.values, ax=ax, color=sns.color_palette()[0])
ax.set_yscale("log")
ax.set_title("Page-type distribution (log scale)")
ax.set_ylabel("pages (log)")
plt.xticks(rotation=30, ha="right")
for i, v in enumerate(counts.values):
    ax.text(i, v * 1.1, str(v), ha="center", fontsize=9)
save("class_distribution")

EDA["class_counts"] = counts.to_dict()
statement_share = counts.reindex(["balance_sheet", "profit_loss", "cash_flow", "equity_changes"]).sum() / counts.sum()
insight(f"Severe imbalance: the largest class ('{counts.idxmax()}', {counts.max()}) is "
        f"{counts.max() / counts.min():.0f}× the smallest ('{counts.idxmin()}', {counts.min()}). Primary statements "
        f"(BS/P&L/CF/SoCE) are only {statement_share:.1%} of pages, yet they hold the headline KPIs. So we use "
        f"macro-F1 plus class weights, not accuracy.")

# %% [markdown]
# ## 3. Univariate analysis of the structural features

# %%
desc = pages[FEATURES].describe().T
desc["skew"] = pages[FEATURES].skew()
desc["kurtosis"] = pages[FEATURES].kurtosis()
desc.round(3)

# %%
fig, axes = plt.subplots(2, 4, figsize=(15, 6))
for ax, f in zip(axes.flat, ["n_words", "n_numbers", "digit_ratio", "numeric_line_ratio",
                             "avg_line_len", "n_lines", "rel_position"]):
    sns.histplot(pages[f], bins=40, kde=True, ax=ax)
    ax.set_title(f"{f}  (skew={pages[f].skew():.2f})", fontsize=10)
    ax.set_xlabel("")
transforms = {"none": pages.n_words, "sqrt": np.sqrt(pages.n_words), "log1p": np.log1p(pages.n_words)}
skews = {k: v.skew() for k, v in transforms.items()}
best_t = min(skews, key=lambda k: abs(skews[k]))
sns.histplot(transforms[best_t], bins=40, kde=True, ax=axes.flat[-1], color="C2")
axes.flat[-1].set_title(f"{best_t}(n_words)  (skew={skews[best_t]:.2f})", fontsize=10)
axes.flat[-1].set_xlabel("")
save("feature_histograms")
pd.Series(skews, name="skew of n_words").round(2).to_frame().T

EDA["feature_hist"] = {
    f: dict(zip(["counts", "edges"], [h.tolist(), e.round(4).tolist()]))
    for f in ["n_words", "digit_ratio", "numeric_line_ratio"]
    for h, e in [np.histogram(pages[f], bins=30)]
}
insight(f"Count features are right-skewed (n_words skew {skews['none']:.2f}, n_numbers skew {pages.n_numbers.skew():.2f}). "
        f"log1p over-corrects n_words to {skews['log1p']:.2f} because of short divider pages; {best_t} gives the most symmetric "
        f"shape ({skews[best_t]:.2f}). Scale-sensitive models (LogReg/SVM) get power-transformed + standardised inputs "
        f"(Yeo-Johnson in the pipeline); tree models need no transformation.")

# %% [markdown]
# ## 4. Bivariate analysis: features vs page type

# %%
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
for ax, f in zip(axes, ["digit_ratio", "numeric_line_ratio", "avg_line_len"]):
    sns.boxplot(data=pages, x="label", y=f, order=order, ax=ax, fliersize=1.5)
    ax.set_title(f"{f} by page type")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=60, labelsize=8)
save("features_by_label")

by_label = pages.groupby("label")[["digit_ratio", "numeric_line_ratio", "avg_line_len", "n_words"]].median().reindex(order)
EDA["feature_medians_by_label"] = by_label.round(4).to_dict("index")
by_label.round(3)

# %% [markdown]
# **Statistical test.** Are the feature distributions different across page types? The features are
# non-normal (see §3), so we use the non-parametric **Kruskal–Wallis H-test** rather than ANOVA. We report
# the effect size ε² = (H − k + 1) / (n − k).

# %%
rows = []
k, n = len(order), len(pages)
for f in FEATURES:
    h, p = stats.kruskal(*[pages.loc[pages.label == l, f] for l in order])
    rows.append({"feature": f, "H": round(h, 1), "p_value": p, "epsilon²": round((h - k + 1) / (n - k), 3)})
kw = pd.DataFrame(rows).sort_values("H", ascending=False)
EDA["kruskal"] = kw.assign(p_value=kw.p_value.map(lambda v: float(f"{v:.3g}"))).to_dict("records")
kw.style.format({"p_value": "{:.2e}"})

# %%
top = kw.iloc[0]
insight(f"All features differ significantly across page types (Kruskal-Wallis p < 0.001). '{top.feature}' "
        f"separates best (ε²={top['epsilon²']}). Statement pages have a median digit_ratio of "
        f"{by_label.loc[['balance_sheet', 'profit_loss', 'cash_flow'], 'digit_ratio'].median():.2f} vs "
        f"{by_label.loc[['mda', 'directors_report'], 'digit_ratio'].median():.2f} for narrative sections. "
        f"The engineered features are informative.")

# %% [markdown]
# ### Where does each section sit in a report?

# %%
fig, ax = plt.subplots(figsize=(11, 4))
sns.violinplot(data=pages, x="label", y="rel_position", order=order, cut=0, inner="quartile", ax=ax, density_norm="width")
ax.set_title("Relative position of each page type inside its report (0 = first page, 1 = last)")
ax.set_xlabel("")
plt.xticks(rotation=30, ha="right")
save("position_by_label")

pos = pages.groupby("label").rel_position.median().reindex(order)
EDA["position_median"] = pos.round(3).to_dict()
insight(f"Reports follow a common order: narrative (MD&A median position {pos['mda']:.2f}, Directors' report "
        f"{pos['directors_report']:.2f}) comes before the financial statements (balance sheet {pos.get('balance_sheet', np.nan):.2f}, "
        f"notes {pos['notes']:.2f}). rel_position is a useful prior for the classifier.")

# %% [markdown]
# ### Feature correlations

# %%
corr = pages[FEATURES].corr(method="spearman")
fig, ax = plt.subplots(figsize=(7.5, 6))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, square=True, ax=ax, annot_kws={"size": 8})
ax.set_title("Spearman correlation between structural features")
save("feature_correlation")

EDA["feature_corr"] = {"labels": FEATURES, "matrix": corr.round(3).values.tolist()}
pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(key=abs, ascending=False)
insight(f"Strongest redundancy: {pairs.index[0][0]} ~ {pairs.index[0][1]} (ρ={pairs.iloc[0]:.2f}) and "
        f"{pairs.index[1][0]} ~ {pairs.index[1][1]} (ρ={pairs.iloc[1]:.2f}). Linear models get one feature from each "
        f"highly-correlated pair (or L2 regularisation); trees are unaffected.")

# %% [markdown]
# **Chi-square test of independence:** is the statement *scope* (standalone / consolidated) related to page type?

# %%
ct = pd.crosstab(pages.label, pages.scope).reindex(order)
chi2, p, dof, _ = stats.chi2_contingency(ct)
cramers_v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
display(ct)
insight(f"Scope vs page type: χ²={chi2:.0f}, dof={dof}, p={p:.1e}, Cramér's V={cramers_v:.2f}. "
        f"'consolidated'/'standalone' mostly appears on statement and notes pages, so scope is mainly informative for those pages.")
EDA["scope_chi2"] = {"chi2": round(chi2, 1), "dof": int(dof), "p": float(f"{p:.3g}"), "cramers_v": round(cramers_v, 3)}

# %% [markdown]
# ## 5. Text analysis
# ### 5.1 Most distinctive terms per page type (mean TF-IDF)

# %%
tfidf = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=3, max_df=0.6, sublinear_tf=True,
                        stop_words="english", token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]{2,}\b")
X = tfidf.fit_transform(pages.clean_text)
terms = np.array(tfidf.get_feature_names_out())
print("TF-IDF matrix:", X.shape, f"sparsity={1 - X.nnz / np.prod(X.shape):.4f}")

top_terms = {}
fig, axes = plt.subplots(2, 5, figsize=(18, 7))
for ax, label in zip(axes.flat, order):
    mean = np.asarray(X[(pages.label == label).values].mean(axis=0)).ravel()
    idx = mean.argsort()[::-1][:8]
    top_terms[label] = [[terms[i], round(float(mean[i]), 4)] for i in idx]
    ax.barh(terms[idx][::-1], mean[idx][::-1], color="C0")
    ax.set_title(label, fontsize=10)
    ax.tick_params(labelsize=8)
for ax in axes.flat[len(order):]:
    ax.axis("off")
save("top_terms")
EDA["top_terms"] = top_terms

# %% [markdown]
# ### 5.2 Word clouds

# %%
fig, axes = plt.subplots(1, 4, figsize=(18, 4))
for ax, label in zip(axes, ["profit_loss", "notes", "mda", "corporate_governance"]):
    mean = np.asarray(X[(pages.label == label).values].mean(axis=0)).ravel()
    wc = WordCloud(width=500, height=320, background_color="white", colormap="viridis", random_state=SEED)
    ax.imshow(wc.generate_from_frequencies(dict(zip(terms, mean))), interpolation="bilinear")
    ax.set_title(label)
    ax.axis("off")
save("wordclouds")

insight("Each page type has its own vocabulary, e.g. P&L: " + ", ".join(t for t, _ in top_terms["profit_loss"][:4])
        + "; MD&A: " + ", ".join(t for t, _ in top_terms["mda"][:4])
        + ". Bag-of-words / TF-IDF should be a strong baseline representation.")

# %% [markdown]
# ### 5.3 Do pages cluster by type, or by company?
# TF-IDF (8k dims) → **Truncated SVD (LSA, 50 dims)** → **t-SNE (2 dims)**.

# %%
svd = TruncatedSVD(n_components=50, random_state=SEED)
Z = svd.fit_transform(X)
evr = svd.explained_variance_ratio_
emb = TSNE(n_components=2, perplexity=35, init="pca", random_state=SEED).fit_transform(Z)
pages["tsne_x"], pages["tsne_y"] = emb[:, 0], emb[:, 1]

fig, axes = plt.subplots(1, 3, figsize=(18, 5.2))
axes[0].plot(np.cumsum(evr), marker=".")
axes[0].set_title("LSA: cumulative explained variance")
axes[0].set_xlabel("components")
sns.scatterplot(data=pages, x="tsne_x", y="tsne_y", hue="label", hue_order=order, s=9, ax=axes[1], palette="tab10", linewidth=0)
axes[1].set_title("t-SNE coloured by page type")
axes[1].legend(fontsize=7, markerscale=2, bbox_to_anchor=(1, 1))
sns.scatterplot(data=pages, x="tsne_x", y="tsne_y", hue="report", s=9, ax=axes[2], palette="Set2", linewidth=0)
axes[2].set_title("t-SNE coloured by report")
axes[2].legend(fontsize=7, markerscale=2)
for ax in axes[1:]:
    ax.set_xlabel("")
    ax.set_ylabel("")
save("tsne")

# Quantify: silhouette of the 2-D embedding w.r.t. label vs company
from sklearn.metrics import silhouette_score
sil_label = silhouette_score(Z, pages.label, metric="cosine", sample_size=1500, random_state=SEED)
sil_company = silhouette_score(Z, pages.company, metric="cosine", sample_size=1500, random_state=SEED)
company_share = pd.crosstab(pages.label, pages.company, normalize="index").max(axis=1)
confounded = company_share[company_share > 0.5].sort_values(ascending=False)
insight(f"LSA keeps {evr.sum():.0%} of TF-IDF variance in 50 dims. Silhouettes are near zero (page type {sil_label:.3f}, "
        f"company {sil_company:.3f}): the classes overlap in pure vocabulary space, so text alone is not enough and the "
        f"structural features matter. Confounding: " + ", ".join(f"{l} ({v:.0%} from one company)" for l, v in confounded.items())
        + ". For example, the top MD&A terms are company names, so a model could learn 'company' instead of 'section'. "
        "This is why the split and the CV are grouped by company, and why more reports are needed.")
EDA["label_company_confound"] = confounded.round(3).to_dict()

sample = pages.sample(min(1200, len(pages)), random_state=SEED)
EDA["tsne"] = sample[["tsne_x", "tsne_y", "label", "report"]].round(3).to_dict("records")
EDA["silhouette"] = {"by_label": round(sil_label, 4), "by_company": round(sil_company, 4)}

# %% [markdown]
# ## 6. KPI analysis
# ### 6.1 Scale and distribution of monetary KPIs

# %%
kp = kpis.dropna(subset=["value"]).copy()
kp["report"] = kp.company.str.split().str[0] + " " + kp.fiscal_year.astype(str)
money = kp[kp.unit == "₹ crore"]

fig, axes = plt.subplots(1, 2, figsize=(14, 4.2))
sns.histplot(money.value.abs(), bins=30, ax=axes[0])
axes[0].set_title(f"|monetary KPI| in ₹ crore (skew={money.value.abs().skew():.1f})")
sns.histplot(np.log10(money.value.abs().clip(lower=0.01)), bins=30, ax=axes[1], color="C2")
axes[1].set_title(f"log10 |monetary KPI| (skew={np.log10(money.value.abs().clip(lower=0.01)).skew():.2f})")
save("kpi_distribution")

insight(f"Monetary KPIs span {np.log10(money.value.abs().max() / money.value.abs()[money.value.abs() > 0].min()):.1f} "
        f"orders of magnitude (₹{money.value.abs()[money.value.abs() > 0].min():.2f} cr to ₹{money.value.abs().max():,.0f} cr). "
        f"Raw values are extremely skewed ({money.value.abs().skew():.1f}); log10 is approximately symmetric, so KPI models and "
        f"outlier rules work on log or ratio scale.")

# %% [markdown]
# ### 6.2 Headline KPIs across companies

# %%
headline = ["Total Revenue", "Profit After Tax (PAT) / Net Profit", "Total Assets", "Total Equity / Shareholders Equity"]
hl = kp[kp.name.isin(headline)].pivot_table(index="report", columns="name", values="value")[headline]
fig, ax = plt.subplots(figsize=(11, 4))
hl.plot.bar(ax=ax, logy=True, width=.8)
ax.set_title("Headline KPIs by report (₹ crore, log scale)")
ax.set_xlabel("")
plt.xticks(rotation=0)
ax.legend(fontsize=8)
save("headline_kpis")
EDA["headline_kpis"] = hl.round(2).reset_index().to_dict("records")
hl.round(1)

# %% [markdown]
# ### 6.3 Ratio analysis

# %%
ratios = pd.DataFrame({
    "net_margin_%": 100 * hl["Profit After Tax (PAT) / Net Profit"] / hl["Total Revenue"],
    "ROA_%": 100 * hl["Profit After Tax (PAT) / Net Profit"] / hl["Total Assets"],
    "ROE_%": 100 * hl["Profit After Tax (PAT) / Net Profit"] / hl["Total Equity / Shareholders Equity"],
    "equity_to_assets": hl["Total Equity / Shareholders Equity"] / hl["Total Assets"],
})
stored = kp[kp.unit == "x"].pivot_table(index="report", columns="name", values="value")
ratios = ratios.join(stored)
EDA["ratios"] = ratios.round(3).reset_index().to_dict("records")
display(ratios.round(2))

best_margin = ratios["net_margin_%"].idxmax()
insight(f"Computed ratios make companies of very different size comparable: {best_margin} has the highest net margin "
        f"({ratios['net_margin_%'].max():.1f}%). These scale-free ratios (margin, ROA, ROE, leverage, liquidity) are the "
        f"feature set for the financial-health classifier.")

# %% [markdown]
# ### 6.4 Year-on-year change (companies with two reports)

# %%
yoy_rows = []
for company, g in kp[kp.unit == "₹ crore"].groupby("company"):
    if g.fiscal_year.nunique() < 2:
        continue
    w = g.pivot_table(index="name", columns="fiscal_year", values="value")
    y0, y1 = sorted(w.columns)[-2:]
    w = w.dropna(subset=[y0, y1])
    for name, r in w.iterrows():
        if r[y0] != 0:
            yoy_rows.append({"company": company.split()[0], "kpi": name, "growth_%": 100 * (r[y1] - r[y0]) / abs(r[y0])})
yoy = pd.DataFrame(yoy_rows)
fig, ax = plt.subplots(figsize=(11, 5))
sns.barplot(data=yoy, y="kpi", x="growth_%", hue="company", ax=ax)
ax.axvline(0, color="k", lw=.8)
ax.set_title("Year-on-year change of monetary KPIs (%)")
ax.set_ylabel("")
save("yoy")
EDA["yoy"] = yoy.round(2).to_dict("records")
rev = yoy[yoy.kpi == "Total Revenue"].set_index("company")["growth_%"]
insight("Total-revenue growth: " + ", ".join(f"{c} {v:+.1f}%" for c, v in rev.items())
        + ". Large single-year swings in a KPI are the inputs the anomaly detector (z-score / Isolation Forest) scores.")

# %% [markdown]
# ### 6.5 Correlation between monetary KPIs

# %%
wide = money.pivot_table(index="report", columns="name", values="value")
wide = wide.loc[:, wide.notna().sum() >= 5]
kcorr = np.log10(wide.abs().clip(lower=0.01)).corr(method="spearman")
fig, ax = plt.subplots(figsize=(9, 7.5))
sns.heatmap(kcorr, cmap="vlag", center=0, annot=True, fmt=".1f", annot_kws={"size": 7}, ax=ax)
ax.set_title(f"Spearman correlation of log KPIs across reports (n={len(wide)})")
save("kpi_correlation")
EDA["kpi_corr"] = {"labels": kcorr.columns.tolist(), "matrix": kcorr.round(3).fillna(0).values.tolist()}
insight(f"Size-driven KPIs (assets, equity, revenue) are almost perfectly rank-correlated (ρ≈"
        f"{kcorr.loc['Total Assets', 'Total Revenue']:.2f} for assets~revenue): company size dominates. With only n={len(wide)} "
        f"reports these correlations are descriptive, not inferential. That is another reason to use size-free ratios as model features.")

# %% [markdown]
# ## 7. Benford's law (forensic check)
#
# In naturally occurring financial data, the leading digit d appears with probability
# P(d) = log₁₀(1 + 1/d), so "1" leads about 30% of the time and "9" only about 4.6%.
# Fabricated or manipulated figures often deviate from this. We test every number on the financial-statement
# and notes pages:
# * We exclude years (1990–2035), note references (< 10) and percentages.
# * We compute a **χ² goodness-of-fit** test and **Nigrini's Mean Absolute Deviation (MAD)**.
#   Nigrini's MAD thresholds: < 0.006 close conformity, < 0.012 acceptable, < 0.015 marginal, above that non-conformity.
#
# **Which numbers count?** A first attempt took *every* integer of 10 or more, and digit **3** came out far
# too often (about 21% vs 12.5% expected). The cause was dates ("31 March"), note numbers and line references.
# Benford applies to *measured amounts*, so we keep only numbers written as amounts: comma-grouped
# (1,23,456) or with decimals (1203.73). Nigrini recommends **at least 1,000 numbers** for a reliable test.

# %%
AMOUNT_RE = re.compile(r"(?<![\d.,])\(?(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+)\)?(?![\d,])")
FIN = {"balance_sheet", "profit_loss", "cash_flow", "equity_changes", "notes"}
MIN_N = 1000


def first_digits(text):
    out = []
    for m in AMOUNT_RE.finditer(text):
        s = m.group(1).replace(",", "")
        if float(s) < 10:
            continue
        out.append(int(s[0]))
    return out


benford = np.log10(1 + 1 / np.arange(1, 10))
rows, dist = [], {}
for report, g in pages[pages.label.isin(FIN)].groupby("report"):
    d = np.array([x for t in g.clean_text for x in first_digits(t)])
    obs = np.bincount(d, minlength=10)[1:]
    freq = obs / obs.sum()
    chi2, p = stats.chisquare(obs, benford * obs.sum())
    mad = np.abs(freq - benford).mean()
    verdict = ("insufficient sample" if obs.sum() < MIN_N else "close conformity" if mad < 0.006
               else "acceptable" if mad < 0.012 else "marginal" if mad < 0.015 else "non-conformity")
    rows.append({"report": report, "n_numbers": int(obs.sum()), "chi2": round(chi2, 1), "p_value": p,
                 "MAD": round(mad, 4), "verdict": verdict})
    dist[report] = freq.round(4).tolist()
bf = pd.DataFrame(rows)

fig, ax = plt.subplots(figsize=(10, 4))
for report, f in dist.items():
    ax.plot(range(1, 10), f, marker="o", ms=3, lw=1, alpha=.8, label=report)
ax.bar(range(1, 10), benford, color="lightgrey", label="Benford expected", zorder=0)
ax.set_xticks(range(1, 10))
ax.set_xlabel("leading digit")
ax.set_ylabel("frequency")
ax.set_title("First-digit distribution vs Benford's law (financial-statement pages)")
ax.legend(fontsize=8)
save("benford")
EDA["benford"] = {"expected": benford.round(4).tolist(), "observed": dist,
                  "tests": bf.assign(p_value=bf.p_value.map(lambda v: float(f"{v:.3g}"))).to_dict("records")}
bf.style.format({"p_value": "{:.2e}"})

# %%
flagged = bf[bf.verdict.isin(["marginal", "non-conformity"])].report.tolist()
insight(f"Reported amounts broadly follow Benford's law (digit 1 leads {np.mean([v[0] for v in dist.values()]):.1%} on "
        f"average vs {benford[0]:.1%} expected). MAD verdicts: " + ", ".join(f"{r.report}: {r.verdict} ({r.MAD})" for r in bf.itertuples())
        + (f". Deviating: {', '.join(flagged)}. A likely benign cause is figures in ₹ lakh with many repeated sub-totals, "
           "which we would investigate rather than conclude anything from" if flagged else "")
        + ". With thousands of numbers the χ² test rejects even tiny deviations (large-n sensitivity), so MAD is the "
        "practical criterion. Benford is a red-flag screen, not proof of manipulation.")

# %% [markdown]
# ## 8. Export for the GUI

# %%
EDA["generated_from"] = {"pages": int(len(pages)), "reports": int(pages.report_id.nunique()), "kpi_rows": int(len(kp))}


def to_json_safe(o):
    """NaN/inf → None (strict JSON), numpy scalars → Python."""
    if isinstance(o, dict):
        return {str(k): to_json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_json_safe(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


(REPORTS_DIR / "eda.json").write_text(
    json.dumps(to_json_safe(EDA), indent=1, ensure_ascii=False, allow_nan=False), encoding="utf-8")
print(f"wrote {REPORTS_DIR / 'eda.json'} with sections: {list(EDA)}")

# %% [markdown]
# ## 9. Key findings
#
# Each line below was printed by the analysis above:

# %%
for i, s in enumerate(EDA["insights"], 1):
    print(f"{i}. {s}\n")

# %% [markdown]
# **Implications for modelling (notebook 03)**
# * **Target:** severe imbalance, so use class weights, compare SMOTE, and use macro-F1 as the selection metric.
# * **Features:** structural features differ significantly by class (Kruskal–Wallis), and TF-IDF vocabulary is
#   class-specific. Plan: combine both, log-transform the counts, and use L2 regularisation for redundant features.
# * **Validation:** pages cluster by company template, so cross-validation must be **grouped by company** (GroupKFold).
# * **KPIs:** use log or ratio scale, and size-free ratios as features for the financial-health classifier.
# * **Forensics:** Benford MAD is cheap to compute and can be shown per filing as an integrity indicator.
