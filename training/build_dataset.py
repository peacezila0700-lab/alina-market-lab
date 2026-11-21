#!/usr/bin/env python3
"""
build_dataset.py — turn this project's own research record into a fine-tuning set.

WHAT THIS TRAINS (and what it does NOT)
  It trains *behaviour*: cite the sample size, quote n_eff instead of n, refuse to call something an edge
  when the pre-declared bar was not met, name the cost assumption, and say "not measured" rather than
  inventing a number. It does NOT train market knowledge — a 4-bit 8B model cannot learn alpha from 700
  instruction pairs, and pretending otherwise is the most expensive mistake in retail AI.

WHY BEHAVIOUR IS THE RIGHT TARGET
  The failures in this project were never "the model did not know the CPI release date". They were
  "the model quoted Sharpe 1.98 from a same-bar weight bug" (PITFALLS #15), "the model compared a gross
  replay to a real account" (PITFALLS #17), "the model reported n=324 as 324 independent observations"
  (base rates: n_eff 15). Those are all fixable by fine-tuning, and they are all measurable afterwards —
  see TRAINING_EVAL.md for the acceptance tests.

SOURCES (all inside this repo, nothing scraped)
  research/EXPERIMENT_LOG.csv        -> verdict / numbers / why-it-failed QA pairs
  research/HYPOTHESIS_REGISTER.csv   -> "what would falsify this" pairs
  datapack_src/PITFALLS.md           -> "why did this break / how do I avoid it" pairs
  datapack_src/WHAT_FAILED.md        -> "has X been tried" pairs (the most valuable ones: anti-hallucination)
  packs/<latest>.json                -> base-rate and level lookups with n_eff
  data/*/MANIFEST*.json              -> dataset provenance / caveat pairs
  unanswerable.jsonl (generated)     -> explicit abstention examples for things NOT in the pack

OUTPUT
  training/data/train.jsonl / valid.jsonl   chat-format {"messages":[...]}, ~85/15 split by *source*, so
  no experiment appears in both halves (a lesson from PITFALLS #6: reusing a tested sample as a new test).

Run: python3 training/build_dataset.py
"""
import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"
RNG = random.Random(20261121)

SYSTEM = ("You are ALINA, the analyst inside a personal market-research lab. Rules you never break: "
          "(1) every number carries its source and sample size, and you quote n_eff when it exists; "
          "(2) a result that did not pass its pre-declared bar is NOT an edge — say so plainly; "
          "(3) always name the cost assumption behind any return figure; "
          "(4) if something was never measured, answer 'ยังไม่ได้ทดสอบ' instead of estimating; "
          "(5) no buy/sell recommendation: report measured base rates with their dispersion. "
          "Answer in the user's language (usually Thai), compactly, without flattery.")


def pair(q, a, tag):
    return {"messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": q},
                         {"role": "assistant", "content": a}], "tag": tag}


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def md_sections(path):
    txt = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"\n(?=#{2,3} )", txt)
    out = []
    for p in parts:
        head = p.strip().split("\n")[0]
        if head.startswith("##"):
            out.append((head.lstrip("# ").strip(), p.strip()))
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    items = []

    # ---- experiments: verdict, numbers, and the honest reason
    for r in rows(ROOT / "research" / "EXPERIMENT_LOG.csv"):
        q = f"{r['exp_id']}: {r['question']} ผลเป็นยังไง"
        a = (f"{r['exp_id']} — {r['result_status']}\n"
             f"• ช่วงข้อมูล: {r['date_range']}\n"
             f"• costs: {r['cost_assumptions']}\n"
             f"• ผล: {r['metrics']}\n"
             f"• robustness: {r['robustness']}\n"
             f"• ข้อสรุป: {r['decision']}\n"
             f"• ไฟล์: {r['artifact_paths']}")
        items.append(pair(q, a, "experiment"))
        items.append(pair(f"มีคนบอกว่าวิธีแบบ {r['exp_id']} ทำเงินได้ จริงไหม",
                          f"ทดสอบแล้ว — {r['result_status']}. {r['metrics']} ข้อสรุปคือ: {r['decision']}",
                          "experiment-claim"))

    # ---- hypotheses: falsification discipline
    for r in rows(ROOT / "research" / "HYPOTHESIS_REGISTER.csv"):
        q = f"สมมติฐาน {r['hyp_id']} ({r['hypothesis'][:90]}…) ต้องพิสูจน์หรือหักล้างยังไง"
        a = (f"{r['hyp_id']} — {r['status']}\n"
             f"• DV: {r['dv']} / horizon {r['horizon_d']} วัน / costs {r['cost_assumption']}\n"
             f"• null: {r['null_hypothesis']}\n"
             f"• เกณฑ์ตัดสิน (ประกาศก่อนรัน): {r['rejection_criteria']}\n"
             f"• ข้อกำหนดตัวอย่าง: {r['sample_requirement']}\n"
             f"• ความเสี่ยง leakage: {r['leakage_risk']}")
        items.append(pair(q, a, "hypothesis"))

    # ---- pitfalls: the "why did this break" corpus
    for head, body in md_sections(ROOT / "datapack_src" / "PITFALLS.md"):
        title = re.sub(r"^\d+\.\s*", "", head)
        items.append(pair(f"ข้อผิดพลาด '{title}' คืออะไร และกันยังไง",
                          body.strip()[:1800], "pitfall"))

    # ---- what failed: the anti-hallucination corpus (most valuable)
    for head, body in md_sections(ROOT / "datapack_src" / "WHAT_FAILED.md"):
        items.append(pair(f"เรื่อง '{head}' ทดสอบแล้วหรือยัง ได้ผลอะไร",
                          body.strip()[:1800], "failed"))

    # ---- base rates from the newest pack
    packs = sorted((ROOT / "packs").glob("*.json"))
    if packs:
        pack = json.loads(packs[-1].read_text())
        for r in pack.get("base_rates", {}).get("rows", []):
            q = (f"ถ้า {r['conditioner']} อยู่ในช่วง {r['bucket']} แล้ว {int(r['horizon_d'])} วันข้างหน้า "
                 f"สถิติเป็นยังไง")
            a = (f"{r['conditioner']} {r['bucket']}, horizon {int(r['horizon_d'])} วัน:\n"
                 f"• median {r['median_pct']:+.2f}% (mean {r['mean_pct']:+.2f}%)\n"
                 f"• p10 {r['p10_pct']:+.2f}% / p90 {r['p90_pct']:+.2f}% → ช่วงกว้าง อ่านช่วง ไม่ใช่ค่าเดียว\n"
                 f"• บวก {r['pct_positive']:.0f}% ของกรณี\n"
                 f"• n = {int(r['n'])} แต่ **n_eff = {int(r['n_eff'])}** (ค่านี้คือจำนวนเหตุการณ์อิสระจริง "
                 f"ถ้า n_eff ต่ำ อย่าถือว่ามีตัวอย่างเยอะ)\n"
                 f"• realised vol ในหน้าต่างนั้น {r.get('realised_vol_pct', 'n/a')}%\n"
                 f"ไม่ใช่คำแนะนำซื้อขาย — เป็นการกระจายผลลัพธ์ย้อนหลังของสภาวะแบบเดียวกัน")
            items.append(pair(q, a, "base-rate"))

        # market state lookup
        st = {}
        for k, v in (pack.get("market") or {}).items():
            if isinstance(v, (int, float, str)):
                st[k] = v
        if st:
            body = "\n".join(f"• {k}: {v}" for k, v in list(st.items())[:18])
            items.append(pair("วันนี้ตลาดเป็นยังไง (สรุปจาก pack ล่าสุด)",
                              f"จาก packs/{packs[-1].stem}.json:\n{body}\n"
                              f"อ่านประกอบ: ค่าเหล่านี้เป็นระดับ ณ วันปิด ไม่ใช่สัญญาณเข้าเทรด", "state"))

    # ---- dataset cards: provenance and caveats
    for mf in (ROOT / "data").rglob("MANIFEST*.json"):
        try:
            m = json.loads(mf.read_text())
        except Exception:                                         # noqa: BLE001
            continue
        if not isinstance(m, dict):
            continue
        src = m.get("source") or m.get("sources")
        if not src:
            continue
        items.append(pair(f"ข้อมูล {mf.parent.name} มาจากไหน เชื่อถือได้แค่ไหน",
                          f"ไฟล์: {mf.relative_to(ROOT)}\n• source: {src}\n"
                          f"• caveats: {m.get('caveats') or m.get('limitations') or 'ดู README ของโฟลเดอร์'}\n"
                          f"• built: {m.get('built_utc', m.get('generated_utc', 'n/a'))}", "provenance"))

    # ---- dataset cards straight from the pack registry: "does this lab have X, and what is its catch"
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_datapack as bd
        for d in bd.DATASETS:
            cav = "; ".join(d.get("caveats") or []) or "ไม่มี caveat ที่บันทึกไว้"
            uses = ", ".join(d.get("use_for") or []) or "n/a"
            a = (f"{d['id']} (grade {d['grade']}, {d['kind']})\n• {d['title']}\n• {d['card']}\n"
                 f"• ข้อควรระวัง: {cav}\n• ใช้ทำ: {uses}\n• กฎการรั่วข้อมูล: {d.get('leak_rule', 'n/a')}\n"
                 f"• ไฟล์: {', '.join(d.get('src') or [])}")
            items.append(pair(f"lab นี้มีข้อมูลเรื่อง {d['id']} ไหม และต้องระวังอะไร", a, "dataset-card"))
            items.append(pair(f"จะใช้ {d['id']} วิเคราะห์ได้ยังไง มีกับดักอะไร",
                              a, "dataset-card"))
    except Exception as e:                                        # noqa: BLE001
        print(f"  (dataset cards skipped: {type(e).__name__}: {e})")

    # ---- glossary / how-to-backtest / ideas: method discipline
    for doc, tag in (("GLOSSARY.md", "glossary"), ("HOW_TO_BACKTEST.md", "method"),
                     ("IDEAS_TO_TEST.md", "ideas"), ("OPERATING_MANUAL.md", "method")):
        fp = ROOT / "datapack_src" / doc
        if fp.exists():
            for head, body in md_sections(fp):
                items.append(pair(f"{head} — อธิบาย/ทำยังไงให้ถูก (จาก {doc})",
                                  body.strip()[:1600], tag))

    # ---- abstention corpus: things that are NOT in this lab
    abstain = [
        ("ราคา NVDA ตอนนี้เท่าไหร่", "ยังไม่ได้ทดสอบ/ไม่มีในชุดข้อมูลนี้ — ข้อมูลราคาใน pack เป็น daily close "
                                    "ของวันก่อน ไม่ใช่ real-time และ lab นี้ไม่มี feed สด ต้องไปดึงจาก "
                                    "scripts/collect_daily.py หรือ API ภายนอก"),
        ("ควรซื้อหุ้นอะไรพรุ่งนี้", "ไม่ตอบ — 19 การทดลองใน lab นี้ยังไม่มีกฎไหนผ่านเกณฑ์ และระบบไม่มีสิทธิ์ "
                                    "ให้คำแนะนำซื้อขาย สิ่งที่ให้ได้คือ base rate ของสภาวะนี้พร้อม n_eff และช่วง p10–p90"),
        ("ทำ EA martingale ได้ไหม", "ทดสอบแล้วใน EXP-0007: martingale ล้างพอร์ตทั้ง 5 จาก 5 เครื่องมือ "
                                    "ที่ทดสอบ — ไม่ทำ"),
        ("ผลตอบแทน expected ของระบบนี้คือเท่าไหร่", "ยังไม่ได้ทดสอบ — การจะตอบต้องมี (ก) กฎที่ผ่าน null + date-split "
                                                    "(ข) ต้นทุนจริงต่อรอบ (ค) log การเทรดจริง 6 เดือน ตอนนี้ยังไม่มีทั้งสาม"),
        ("ข่าวล่าสุดของหุ้น X", "ข้อมูลข่าวใน lab เป็น RSS ที่เก็บตามรอบ ไม่ใช่ real-time และไม่ครอบคลุมทุกตัว "
                               "ให้บอกชื่อแล้วผมจะเช็คว่ามีใน data/news หรือไม่"),
    ]
    for q, a in abstain:
        items.append(pair(q, a, "abstain"))
        items.append(pair(q, a, "abstain"))

    # ---- split by TAG so no source leaks across the boundary
    RNG.shuffle(items)
    tags = sorted({i["tag"] for i in items})
    # hold out whole tags until the validation slice is 8-20% of the data (a 7-pair valid set measures
    # nothing). Tags are never split, so no experiment or dataset card can appear in both halves.
    counts = {t: sum(1 for i in items if i["tag"] == t) for t in tags}
    order = sorted(tags, key=lambda t: (counts[t], t))
    valid_tags, n_valid = set(), 0
    target = max(12, int(0.08 * len(items)))
    for t in order:
        if n_valid >= target:
            break
        valid_tags.add(t)
        n_valid += counts[t]
    train = [i for i in items if i["tag"] not in valid_tags]
    valid = [i for i in items if i["tag"] in valid_tags]
    for name, data in (("train", train), ("valid", valid)):
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for i in data:
                f.write(json.dumps({"messages": i["messages"]}, ensure_ascii=False) + "\n")
    stats = {"pairs": len(items), "train": len(train), "valid": len(valid),
             "by_tag": {t: sum(1 for i in items if i["tag"] == t) for t in tags},
             "valid_tags": sorted(valid_tags),
             "avg_chars": round(sum(len(json.dumps(i["messages"], ensure_ascii=False))
                                    for i in items) / max(1, len(items)))}
    (OUT / "STATS.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"  pairs {stats['pairs']} (train {stats['train']} / valid {stats['valid']}), "
          f"avg {stats['avg_chars']} chars")
    for t in tags:
        print(f"    {t:<14} {stats['by_tag'][t]}")
    print(f"  held-out tags: {', '.join(sorted(valid_tags))}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    build()
