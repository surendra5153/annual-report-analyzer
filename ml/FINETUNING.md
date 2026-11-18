# Fine-tuning FinSumm: step-by-step guide

FinSumm is **Qwen2.5-3B-Instruct + a QLoRA adapter** that we train ourselves. It is the fallback language
model for every question the deterministic table reader cannot answer (narrative questions, multi-row
questions, qualifiers such as "attributable to owners", summaries).

| What | Where it runs | Cost |
|---|---|---|
| Build training data | your laptop (CPU) | ₹0 |
| Train (QLoRA) | Kaggle notebook, GPU T4 ×2 | ₹0 (≈30 GPU-h/week free) |
| Serve | your laptop: Ollama on the RTX 3050 (4 GB) | ₹0 |

**Why not train on the laptop?** QLoRA on a 3B model needs about 10–14 GB of GPU memory, and the 3050 has 4 GB.
Inference of the 4-bit model needs about 2.3 GB, so serving fits.

---

## Step 1: collect training reports (never the evaluation companies)
The model must not be trained on the reports it is tested on. The collector **refuses** Adani Enterprises,
HAL, Bharti Airtel and Adarsh, i.e. every company in `ml/eval/rag_*.json` and in the app database:
```
python -m ml.collect.collect_reports --show-excluded
```
BSE and NSE block automated downloads, so download the PDFs in your browser:

1. Pick about 30–40 companies from `ml/collect/train_companies.csv` (large caps across sectors).
2. For each one, download the latest **one or two annual reports** (FY2024–FY2026). Use the company website
   (Investors → Annual Reports) or bseindia.com → company → Financials → Annual Reports.
3. Put the PDFs in `ml/data/train_pdfs/inbox/`, named `TICKER_FY2026_Annual_Report.pdf` (NSE ticker + fiscal year).
   Company name and sector are then looked up automatically. Files with other names need an
   `inbox/manifest.csv` (`file_name,company,sector,fiscal_year`).
4. Register them:
   ```
   python -m ml.collect.collect_reports --from-folder ml/data/train_pdfs/inbox
   ```
   The collector rejects truncated downloads ("incomplete download (22% of 18 MB) — re-download it"). Re-download
   those in the browser and run the command again; already registered files are kept.
   If you have direct PDF links instead, use `--urls urls.csv` with columns `url,company,sector,fiscal_year`.

## Step 2: build the training data
```
python -m ml.finetune.build_sft
```
This writes `ml/data/sft/sft_train.jsonl` and `sft_val.jsonl`. Validation is split **by company**, 5%.

* **Format:** each example is a chat (system, user, assistant) in **exactly the production format**. It uses
  the same system prompt (`rag_qa.system_prompt`), the same statement-page sources and the same citation style.
* **Labels:** answer labels come from the deterministic table reader, so every number is exact. No LLM
  teacher is needed.

| Type | Teaches |
|---|---|
| lookup | find the right row and copy the figure with its unit |
| prior_year | read the year column headers |
| change | show both years and the % change |
| scope | standalone vs consolidated |
| unanswerable | say "not found" (fabricated items, years the report does not cover) |

Rough size: 40 reports × ~130 examples ≈ 5,000 examples.

**Label hygiene** (applied automatically, so no label teaches a wrong number):
* Each table's own unit declaration is used. Banks print standalone figures in ₹ '000 and consolidated in ₹ crore.
  SBI writes it as "(000s omitted)", ICICI as "₹ in '000s".
* Legacy rupee fonts are decoded: TCS "(H crore)", HDFC Bank "(C in '000)", Wipro "(I in millions", "(` in lakh)".
* Year columns are read from dates too ("31.03.2026", "31/03/2026"). The newest year is always "current", even
  where a section (Wipro's IFRS statements) prints the older year first.
* Letter-spaced headings ("S TA N D A L O N E B A L A N C E S H E E T") are recognised. Pages without a textual
  heading are typed from their rows, e.g. a "Total assets" plus "Total equity" table is a balance sheet.
* Cash-flow rows are used only when they are cash movements. The adjustments block repeats P&L names with flipped
  signs, so it is not used.
* Skipped rows:
  * labels that are footnoted, wrapped or merged ("[8]", "18 (5)", "… attributable to");
  * schedule movements ("additions during the year");
  * counts and ratios;
  * labels that appear twice in one table (current vs non-current "Lease liabilities").
* Cash-flow adjustments never override the P&L line with the same name.
* EPS is answered as "₹45.96 per share", not as crore.
* 5- and 10-year highlights pages and "Schedules to the Balance Sheet" pages are not treated as statements.

**Format check without training data:** `python -m ml.finetune.build_sft --smoke` writes 18 examples from one app
report to `smoke.jsonl`. They are for inspection only; never train on them.

## Step 3: train on Kaggle (about 5 minutes of clicks, then 7–8 h of unattended training)
1. kaggle.com → **Datasets → New Dataset** → upload `sft_train.jsonl` and `sft_val.jsonl` → name it `finsight-sft`.
2. **Code → New Notebook → File → Import Notebook** → `ml/finetune/finsumm_qlora_kaggle.ipynb`.
3. **Session options**:
   * Accelerator **GPU T4 ×2**
   * Internet **On**
   * **Add Input** → `finsight-sft`
4. **Save Version → Save & Run All.** It keeps running after you close the tab.
5. Output tab → download:
   * `finsumm/finsumm.Q4_K_M.gguf` (about 2 GB);
   * `finsumm_loss.png` (training/validation loss curves for the report);
   * `finsumm_log_history.json`.

Hyperparameters (in the notebook):

| Setting | Value |
|---|---|
| LoRA r / alpha | 16 / 16 |
| Target modules | all attention + MLP projections |
| Learning rate | 2e-4, cosine schedule, 3% warm-up |
| Effective batch | 16 (2 × grad-accum 8) |
| Epochs | 1 (time guard stops training at 9.5 h, inside Kaggle's 12 h session) |
| Max sequence length | 8,192 |
| Loss | on the assistant answer only |
| Checkpoint kept | the one with the best validation loss |

## Step 4: install the model locally
```
mkdir models\finsumm
move %USERPROFILE%\Downloads\finsumm.Q4_K_M.gguf models\finsumm\
ollama create finsumm -f ml\export\Modelfile.finsumm
ollama run finsumm "Say hello"          # smoke test
```

## Step 5: evaluate (dev first, then test once)
```
python -m ml.eval.run_rag_eval --set dev  --configs H_finsumm,K_finsumm
python -m ml.eval.score_runs   --set dev
python -m ml.eval.run_rag_eval --set test --configs H_finsumm,K_finsumm      # once
python -m ml.eval.tatqa_eval   --configs llm --model finsumm                   # external benchmark
```
* **H_finsumm vs H** measures the fine-tune itself: every answer goes through the LLM.
* **K_finsumm vs J** measures the production gain: the table reader first, then the LLM fallback.
* Use the McNemar test (notebook 06) to check whether differences are significant.

## Step 6: switch production to FinSumm (only if it wins on dev **and** test)
In `backend/.env` add `QA_MODEL=finsumm`, then restart the backend. To roll back, delete the line.

---

### Troubleshooting
| Symptom | Fix |
|---|---|
| Kaggle "CUDA out of memory" | set `MAX_SEQ_LEN = 6144` or `per_device_train_batch_size=1` with `gradient_accumulation_steps=16` |
| Validation loss rises after epoch 1 | keep `EPOCHS = 1` (the best checkpoint is used anyway) |
| `ollama create` cannot find the file | the `FROM` path is relative to `ml/export/`; check `models/finsumm/finsumm.Q4_K_M.gguf` exists |
| Answers end with odd tokens | make sure the Modelfile's `TEMPLATE`/`stop` lines are unchanged (Qwen2.5 chat format) |
---

## FinSumm v2 (after the v1 test result)
v1 (finsumm) beat the base model on dev (81.8% vs 77.3%) but **not** on test v1/v2 (61.5% vs 73.1% / 65.4%;
McNemar p > 0.37). Error analysis of every lost question showed three label-design flaws, all fixed in v2:

| v1 failure | v2 label fix |
|---|---|
| Re-typed figures (₹3,76,766 → ₹37,676.60) | answers copy the figure **verbatim** from the source; a builder check guarantees every ₹ figure in an answer appears in its sources (0 violations) |
| Refused only future years; answered "FY 2019-20" | "not found" for past (FY−4…−7) **and** future years, ~13% of examples, verified absent from the sources |
| Wrong row for natural wording | paraphrased questions with the company name ("How much did Titan spend on its employees…"), mapped back to the statement row; current-ratio questions with the working shown |

Shared-code fixes found while doing this (affect the app too): digit grouping of long numbers was not being
applied to statement pages; unlabelled section totals were named after a sub-heading; consolidated continuation
pages were tagged standalone.

Data v2: 4,693 train / 278 val (v1 data kept in `ml/data/sft/v1/`). Train with the same notebook, install as
`finsumm2` (`ml/export/Modelfile.finsumm2`, GGUF at `models/finsumm2/finsumm.Q4_K_M.gguf`), evaluate with configs
`H_finsumm2` / `K_finsumm2` next to H / J re-run on the same code.
