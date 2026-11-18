# %% [markdown]
# # 08 · Benchmarks: how good is FinSight Q&A, and how does it compare?
#
# Three evaluations, all run **once per frozen configuration** (nothing here was used for tuning):
#
# | Benchmark | What it measures | Size |
# |---|---|---|
# | **Test v1** (`rag_gold.json`) | direct statement lookups on our 6 Indian reports | 26 answerable + 4 unanswerable |
# | **Test v2** (`rag_gold_v2.json`) | natural phrasing, computed ratios, growth, narrative, new unanswerables | 26 answerable + 4 unanswerable |
# | **TAT-QA** (Zhu et al., ACL 2021), public | hybrid table + text QA over real (mostly US) annual reports, official EM/F1 | 300-question stratified dev sample |
#
# Configurations: **D** (hybrid retrieval + cleaned KPI table, notebook 05), **H** (statement-aware LLM,
# notebook 06) and **J** (deterministic table reader, then H as fallback; the live setting).

# %%
import json
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from ml.paths import DATA_DIR, FIGURES_DIR, REPORTS_DIR
from ml.eval.score_runs import score, summarise
from ml.eval.reader_eval import evaluate as reader_evaluate
from ml.eval import tatqa_eval

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", palette="deep")
pd.set_option("display.width", 180)
pd.set_option("display.max_colwidth", 120)
CONFIGS = {"D_hybrid_all_kpis": "D · hybrid + KPI table", "H_statements_no_kpi": "H · statement-aware LLM",
           "J_table_reader": "J · table reader → LLM (live)"}


def save(name):
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f"08_{name}.png", dpi=130)
    plt.show()


def ci(x, n=5000, seed=0):
    x = np.asarray(x, float)
    m = np.random.default_rng(seed).choice(x, (n, len(x))).mean(1)
    return np.percentile(m, [2.5, 97.5])


def table(qset):
    d = score(qset)
    d = d[d.config.isin(CONFIGS)]
    s = summarise(d).loc[[c for c in CONFIGS if c in set(d.config)]]
    ans = d[d.kind != "unanswerable"]
    bounds = {c: ci(ans[ans.config == c].numeric_correct.astype(float)) for c in s.index}
    s.insert(2, "ci", [f"{bounds[c][0]:.0%}–{bounds[c][1]:.0%}" for c in s.index])
    s.index = [CONFIGS[c] for c in s.index]
    return d, s

# %% [markdown]
# ## 1. Test v1: direct statement lookups

# %%
d1, t1 = table("test")
t1

# %% [markdown]
# ## 2. Test v2: harder, natural questions

# %%
d2, t2 = table("test2")
t2

# %%
kinds = d2[d2.kind != "unanswerable"].groupby(["kind", "config"]).numeric_correct.mean().unstack()[list(CONFIGS)]
kinds.columns = [CONFIGS[c] for c in kinds.columns]
kinds.round(2)

# %%
fig, ax = plt.subplots(figsize=(9, 3.8))
both = pd.DataFrame({"test v1": t1.accuracy, "test v2": t2.accuracy})
both.plot.barh(ax=ax)
ax.set_xlim(0, 1)
ax.set_title("Numeric accuracy on our Indian annual-report test sets")
for c in ax.containers:
    ax.bar_label(c, fmt="%.0f%%", labels=[f"{v * 100:.0f}%" for v in c.datavalues], fontsize=8)
save("indian_tests")

# %% [markdown]
# ## 3. The table reader on its own (no LLM)
# The reader is the deterministic part of J. It answers only when confident; everything else goes to the LLM.

# %%
reader = {}
for qset in ("dev", "test", "test2"):
    _, s = reader_evaluate(qset, verbose=False)
    reader[qset] = s
reader_df = pd.DataFrame(reader).T[["questions", "coverage", "precision", "false_confident_on_unanswerable"]]
reader_df

# %% [markdown]
# **Reading this.**
# * **Precision** is the share of the reader's answers that are correct. It stays at 100% on every set:
#   when it answers, it is right.
# * **Coverage** drops from v1 to v2. Natural phrasing ("How much did *HAL spend on its employees*…",
#   "…*on a consolidated basis*"), company names and computed ratios trip its strict "no extra qualifiers"
#   guard, and those questions fall back to the LLM.
# * Widening coverage without losing precision is the next reader improvement. It must be tuned on the dev
#   set, never on v2.

# %% [markdown]
# ## 4. TAT-QA (public benchmark, official metric)

# %%
tq = tatqa_eval.score(["llm", "reader"], 300)
tq_df = pd.DataFrame(tq).T
tq_df

# %%
published = pd.DataFrame([
    {"system": "Human experts", "EM": 84.1, "F1": 90.8, "split": "test", "source": "Zhu et al. 2021"},
    {"system": "TagOp (paper's model, RoBERTa-large, trained on TAT-QA)", "EM": 50.1, "F1": 58.0, "split": "test", "source": "Zhu et al. 2021"},
    {"system": "NumNet+ V2 (strongest baseline in the paper)", "EM": 37.0, "F1": 46.9, "split": "test", "source": "Zhu et al. 2021"},
    {"system": "FinSight J: table reader → Qwen2.5-3B (zero-shot, local)", "EM": tq["reader"]["em"], "F1": tq["reader"]["f1"], "split": "dev sample (300)", "source": "this notebook"},
    {"system": "FinSight: Qwen2.5-3B only (zero-shot, local)", "EM": tq["llm"]["em"], "F1": tq["llm"]["f1"], "split": "dev sample (300)", "source": "this notebook"},
])
published

# %% [markdown]
# **Interpretation (honest comparison)**
# * Our numbers are on a 300-question **dev** sample, while the published numbers are on the **test** split,
#   whose answers are hidden. The comparison is indicative, not exact.
# * The published systems were **trained on TAT-QA's 13k training questions**. Ours is **zero-shot**: a 3B
#   model plus rules, never trained on TAT-QA, running on a 4 GB laptop GPU.
# * The deterministic reader roughly **doubles** the zero-shot LLM, mostly on arithmetic questions, where a
#   small LLM's arithmetic fails and Python's does not.
# * Reader precision on TAT-QA is lower than on Indian reports. US/UK tables have different layouts and
#   question styles. Its rules were inspected on this dev sample, so the honest estimate comes from a
#   **separate, unseen** TAT-QA train sample: **85.5% precision at 19.8% coverage** (1,500 questions).
# * Closing the gap to TagOp needs what TagOp had: training on financial table QA. That is FinSumm
#   (`ml/FINETUNING.md`), and TAT-QA's train split could be added to its SFT data.

# %%
fig, ax = plt.subplots(figsize=(9, 3.6))
p = published.iloc[::-1]
colors = [sns.color_palette()[3] if "FinSight" in s else sns.color_palette()[0] for s in p.system]
ax.barh(p.system.str.slice(0, 55), p.F1, color=colors)
for i, (f1, sp) in enumerate(zip(p.F1, p.split)):
    ax.text(f1 + 1, i, f"{f1:.1f}  ({sp})", va="center", fontsize=8)
ax.set_xlim(0, 100)
ax.set_xlabel("F1")
ax.set_title("TAT-QA: published (test) vs FinSight zero-shot (dev sample)")
save("tatqa")

# %% [markdown]
# ## 5. Latency (local hardware: RTX 3050 4 GB)

# %%
lat = pd.concat([d1.assign(set="test v1"), d2.assign(set="test v2")])
lat = lat.groupby(["set", "config"]).latency_s.median().unstack()[list(CONFIGS)]
lat.columns = [CONFIGS[c] for c in lat.columns]
lat.round(2)

# %% [markdown]
# ## 6. Publish

# %%
metrics_path = REPORTS_DIR / "metrics.json"
metrics = json.loads(metrics_path.read_text(encoding="utf-8"))


def records(t):
    return [{"config": i, **{k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in r.items()}}
            for i, r in t.iterrows()]


metrics["benchmarks"] = {
    "test_v1": records(t1), "test_v2": records(t2),
    "test_v2_by_kind": kinds.round(3).reset_index().to_dict("records"),
    "reader_only": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in reader.items()},
    "tatqa": {"ours": tq, "published": published.to_dict("records"),
              "reader_unseen_train_sample": {"questions": 1500, "coverage": 0.198, "precision": 0.855},
              "note": "ours = 300-question stratified dev sample; published = test split; ours zero-shot"},
    "latency_median_s": lat.round(3).reset_index().to_dict("records"),
}
metrics_path.write_text(json.dumps(metrics, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
print("metrics.json → benchmarks:", list(metrics["benchmarks"]))
