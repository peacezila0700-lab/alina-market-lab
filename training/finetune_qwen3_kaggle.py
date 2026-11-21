#!/usr/bin/env python3
"""
finetune_qwen3_kaggle.py — QLoRA behaviour fine-tune of Qwen3 on the lab's own research record.

STATUS: **ยังไม่ได้ทดสอบ** — the workspace this was written in has no GPU, so this script has never been
executed end to end. Every API call below is the documented Unsloth/TRL path as of 2026-11, and the numbers
(GPU hours) are estimates from the free-tier quotas, not measurements from this repo. Treat the first run as
a test of the script itself.

WHERE TO RUN (free, in this order)
  1. Kaggle Notebooks — "T4 x2" or P100, ~30 GPU-hours/week recurring, 12 h sessions, no credit card.
     This is the primary target: set Accelerator = GPU, Internet = On.
  2. Modal — $30/month recurring compute credit, no card; ~37 h on an L4 or ~50 h on a T4 per month.
     Use it only when Kaggle is out of quota.
  3. Colab free — works, but quota is unannounced and sessions die; keep it as the backup for a 1-hour run.

WHAT FITS IN 16 GB
  Qwen3-8B: 4-bit base ≈ 4-5 GB, LoRA + optimizer + activations at seq_len 2048 ≈ 6-8 GB → fits a T4 with
  room to spare. Qwen3-4B is the safe fallback (≈ 3 GB) if a T4 run OOMs. 14B does **not** fit on 16 GB
  reliably; do not waste a week's quota discovering that.

TIME BUDGET (estimate, not measured)
  213 pairs, 2-3 epochs, 8B model, batch 2 + grad-accum 4 → roughly 20-40 minutes on a T4. That is one
  Kaggle session, and it leaves most of the weekly quota untouched.

RUN
  !pip install -q unsloth
  !python finetune_qwen3_kaggle.py --data /kaggle/input/alina-dataset --out /kaggle/working/lora
"""
import argparse
import json
import os
from pathlib import Path

SYSTEM_KEEP = True          # the dataset already carries the system turn; do not add another


def load_jsonl(p):
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="training/data")
    ap.add_argument("--out", default="lora")
    ap.add_argument("--model", default="unsloth/Qwen3-8B", help="unsloth/Qwen3-4B if 16 GB OOMs")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--seq", type=int, default=2048)
    ap.add_argument("--gguf", action="store_true", help="also export a q4_k_m GGUF for Ollama")
    a = ap.parse_args()

    import torch
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel, is_bfloat16_supported

    print(f"  torch {torch.__version__}, cuda {torch.cuda.is_available()}, "
          f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")

    model, tok = FastLanguageModel.from_pretrained(
        model_name=a.model, max_seq_length=a.seq, load_in_4bit=True, dtype=None)
    model = FastLanguageModel.get_peft_model(
        model, r=16, lora_alpha=16, lora_dropout=0.0, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=20261121)

    train_rows = load_jsonl(Path(a.data) / "train.jsonl")
    valid_rows = load_jsonl(Path(a.data) / "valid.jsonl")

    def to_text(r):
        return {"text": tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=False)}

    ds_tr = Dataset.from_list([to_text(r) for r in train_rows])
    ds_va = Dataset.from_list([to_text(r) for r in valid_rows])
    print(f"  train {len(ds_tr)} / valid {len(ds_va)} examples")

    cfg = SFTConfig(
        output_dir=a.out, num_train_epochs=a.epochs, per_device_train_batch_size=2,
        gradient_accumulation_steps=4, learning_rate=2e-4, lr_scheduler_type="cosine",
        warmup_ratio=0.05, logging_steps=5, save_strategy="epoch", eval_strategy="epoch",
        fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported(),
        optim="adamw_8bit", weight_decay=0.01, max_length=a.seq, dataset_text_field="text",
        seed=20261121, report_to="none")
    trainer = SFTTrainer(model=model, tokenizer=tok, train_dataset=ds_tr, eval_dataset=ds_va, args=cfg)
    trainer.train()
    model.save_pretrained(a.out)
    tok.save_pretrained(a.out)
    print(f"  LoRA saved to {a.out}")

    # A/B the two behaviours on one held-out prompt — the point of the whole exercise
    FastLanguageModel.for_inference(model)
    probe = ("สถิติ 21 วันหลัง VIX/VIX3M กลับตัวเป็น inverted เป็นยังไง")
    msgs = [{"role": "system", "content": "You are ALINA."}, {"role": "user", "content": probe}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to("cuda")
    out = model.generate(input_ids=ids, max_new_tokens=256, temperature=0.3, do_sample=True)
    print("\n--- sample after fine-tune ---\n" + tok.decode(out[0][ids.shape[-1]:], skip_special_tokens=True))
    print("\n  Now run TRAINING_EVAL.md's four tests. Do not call the model better because this sample "
          "reads well — the tests decide, not the vibe.")

    if a.gguf:
        # Local use afterwards: Ollama on any laptop, zero cost, no hosting
        model.save_pretrained_gguf("gguf", tok, quantization_method="q4_k_m")
        print("  GGUF written to ./gguf — copy it to the machine that runs Ollama")


if __name__ == "__main__":
    main()
