# %% [markdown]
# # FinSumm: QLoRA fine-tuning of Qwen2.5-3B-Instruct (Kaggle, free T4)
#
# **What this trains.** A 3-billion-parameter model that answers questions about Indian annual reports in
# the FinSight style:
# * cites its sources as [n];
# * copies figures exactly, with the unit as printed;
# * reads the right year column;
# * says "not found" when the sources do not contain the answer.
#
# **Why Kaggle.** QLoRA on a 3B model needs about 10–14 GB of GPU memory. A laptop RTX 3050 has 4 GB, which
# is enough to *run* the result but not to *train* it. Kaggle gives about 30 GPU-hours a week for free.
#
# ## Before you run (one-time setup, about 5 minutes)
# 1. On your laptop, build the data: `python -m ml.finetune.build_sft`. This creates
#    `ml/data/sft/sft_train.jsonl` and `ml/data/sft/sft_val.jsonl`.
# 2. kaggle.com → **Datasets → New Dataset** → upload both files → name it **`finsight-sft`**.
# 3. kaggle.com → **Code → New Notebook** → **File → Import Notebook** → choose this `.ipynb`.
# 4. Right panel → **Session options**:
#    * **Accelerator: GPU T4 ×2**
#    * **Internet: On**
#    * **Add Input** → your `finsight-sft` dataset.
# 5. **Run All.** Training takes about 7–8 hours (1 epoch, ~295 steps); a time guard stops it at 9.5 h so the export always runs. You can close the browser:
#    use **Save Version → Save & Run All** and it keeps running.
# 6. When it finishes, open the notebook's **Output** tab and download
#    **`finsumm/finsumm.Q4_K_M.gguf`** (about 2 GB).
#
# ## After download (on your laptop)
# ```
# mkdir models\finsumm
# move finsumm.Q4_K_M.gguf models\finsumm\
# ollama create finsumm -f ml\export\Modelfile.finsumm
# ```
# Then follow `ml/FINETUNING.md` § "Evaluate".

# %%
# 1 · Install Unsloth (2× faster QLoRA, lower memory; pinned for reproducibility where possible)
!pip install -q unsloth
!pip install -q --no-deps "trl<0.15" peft accelerate bitsandbytes

# %%
# 2 · Configuration
import json, os, glob
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"   # set before torch loads: less fragmentation on the T4

# Wherever Kaggle mounted the "finsight-sft" dataset (/kaggle/input/finsight-sft or a nested path)
DATA_DIR = os.path.dirname(next(iter(glob.glob("/kaggle/input/**/sft_train.jsonl", recursive=True)),
                                "/kaggle/input/finsight-sft/sft_train.jsonl"))
print("training data:", DATA_DIR)
OUT_DIR = "/kaggle/working/finsumm"
BASE_MODEL = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"   # same base as the app's qwen2.5:3b
MAX_SEQ_LEN = 8192                                     # app context is ~3k tokens; 8k leaves headroom
EPOCHS = 1                                             # ~295 steps at ~90 s/step on a T4 ≈ 7.5 h
TIME_BUDGET_H = 9.5                                    # stop training here so export finishes inside Kaggle's 12 h
EVAL_EXAMPLES = 120                                    # validation subset: each eval pass stays a few minutes
LR = 2e-4
LORA_R = 16
SEED = 3407

print(glob.glob(f"{DATA_DIR}/*"))

# %%
# 3 · Load the 4-bit base model + attach LoRA adapters
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL, max_seq_length=MAX_SEQ_LEN, dtype=None, load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R, lora_alpha=LORA_R, lora_dropout=0, bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth", random_state=SEED,
)
model.print_trainable_parameters()

# %%
# 4 · Data: chat messages → Qwen2.5 chat template (exactly what Ollama will apply at inference)
from datasets import load_dataset
from unsloth.chat_templates import get_chat_template, train_on_responses_only

tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")
ds = load_dataset("json", data_files={"train": f"{DATA_DIR}/sft_train.jsonl", "val": f"{DATA_DIR}/sft_val.jsonl"})


def to_text(batch):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False) for m in batch["messages"]]}


ds = ds.map(to_text, batched=True, remove_columns=[c for c in ds["train"].column_names if c != "type"])
lengths = [len(tokenizer(t).input_ids) for t in ds["train"]["text"][:200]]
print(ds, "\nmedian tokens:", sorted(lengths)[len(lengths) // 2], "max:", max(lengths))
print(ds["train"][0]["text"][-600:])

# %%
# 5 · Train: loss only on the assistant answer (the sources/question are context, not targets)
import time
from transformers import TrainerCallback
from trl import SFTTrainer, SFTConfig


class TimeBudget(TrainerCallback):
    """Stop cleanly before Kaggle's 12 h limit, so the best checkpoint is still exported."""
    def __init__(self, hours):
        self.deadline = time.time() + hours * 3600

    def on_step_end(self, args, state, control, **kw):
        if time.time() > self.deadline:
            print(f"time budget reached at step {state.global_step} — stopping and exporting the best checkpoint")
            control.should_save = True
            control.should_training_stop = True
        return control


val_small = ds["val"].shuffle(seed=SEED).select(range(min(EVAL_EXAMPLES, len(ds["val"]))))
trainer = SFTTrainer(
    model=model, tokenizer=tokenizer,
    train_dataset=ds["train"], eval_dataset=val_small,
    dataset_text_field="text", max_seq_length=MAX_SEQ_LEN, packing=False,
    callbacks=[TimeBudget(TIME_BUDGET_H)],
    args=SFTConfig(
        per_device_train_batch_size=2, gradient_accumulation_steps=8,      # effective batch 16
        # eval at batch 1 and loss only: the default (batch 8 + full 152k-vocab logits) runs out of T4 memory
        per_device_eval_batch_size=1, prediction_loss_only=True,
        num_train_epochs=EPOCHS, learning_rate=LR, lr_scheduler_type="cosine", warmup_ratio=0.03,
        weight_decay=0.01, optim="adamw_8bit", fp16=True, bf16=False,
        logging_steps=10, eval_strategy="steps", eval_steps=50, save_strategy="steps", save_steps=50,
        save_total_limit=2, load_best_model_at_end=True, metric_for_best_model="eval_loss",
        output_dir="/kaggle/working/checkpoints", seed=SEED, report_to="none",
    ),
)
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                  response_part="<|im_start|>assistant\n")
stats = trainer.train()
print(stats)
# Save the LoRA adapter (~120 MB) right away: if the GGUF export below fails, the training is not lost
model.save_pretrained("/kaggle/working/finsumm_lora")
tokenizer.save_pretrained("/kaggle/working/finsumm_lora")

# %%
# 6 · Learning curves (save the figure for the report / viva)
import matplotlib.pyplot as plt

hist = trainer.state.log_history
tr = [(h["step"], h["loss"]) for h in hist if "loss" in h]
ev = [(h["step"], h["eval_loss"]) for h in hist if "eval_loss" in h]
plt.figure(figsize=(7, 3.5))
plt.plot(*zip(*tr), label="train loss")
if ev:
    plt.plot(*zip(*ev), marker="o", label="validation loss")
plt.xlabel("step"); plt.ylabel("loss"); plt.legend(); plt.title("FinSumm QLoRA")
plt.tight_layout(); plt.savefig("/kaggle/working/finsumm_loss.png", dpi=130); plt.show()
json.dump(hist, open("/kaggle/working/finsumm_log_history.json", "w"))

# %%
# 7 · Quick sanity check on a validation example
FastLanguageModel.for_inference(model)
ex = ds["val"][0]["text"]
prompt = ex[: ex.rfind("<|im_start|>assistant")] + "<|im_start|>assistant\n"
ids = tokenizer(prompt, return_tensors="pt").to("cuda")
out = model.generate(**ids, max_new_tokens=120, temperature=0.0, do_sample=False)
print("MODEL :", tokenizer.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True))
print("TARGET:", ex[ex.rfind("<|im_start|>assistant") + 22:][:300])

# %%
# 8 · Export: merge LoRA into the base and quantise to GGUF Q4_K_M (~2 GB) for Ollama
import shutil
shutil.rmtree("/kaggle/working/checkpoints", ignore_errors=True)   # free disk for the merge (Kaggle allows 20 GB)
model.save_pretrained_gguf(OUT_DIR, tokenizer, quantization_method="q4_k_m")
for f in glob.glob(f"{OUT_DIR}*/*.gguf") + glob.glob(f"{OUT_DIR}/*.gguf"):
    print(f, round(os.path.getsize(f) / 1e9, 2), "GB")
# Rename to the name the Modelfile expects
gguf = (glob.glob(f"{OUT_DIR}*/*Q4_K_M*.gguf") + glob.glob(f"{OUT_DIR}/*Q4_K_M*.gguf"))[0]
os.makedirs(OUT_DIR, exist_ok=True)
os.replace(gguf, f"{OUT_DIR}/finsumm.Q4_K_M.gguf")
print("download →", f"{OUT_DIR}/finsumm.Q4_K_M.gguf")
