# BUILD PLAN — auto-trading EA + personal AI, at zero budget, from a phone

Written 2026-11-21 in answer to: "จะสร้าง app trade ที่เทรดออโต้เป็น EA เฉพาะของผมได้ไหม ทุน 0 มี Gemini Plus
กับ Claude Pro (แชร์กับคนอื่น) คุยกับ GPT ฟรี"

**คำตอบสั้น: ทำได้ แต่ไม่ใช่ตามลำดับที่แพลนนั้นวางไว้ และ 3 อย่างในแพลนนั้นจะทำให้เสียเวลาฟรี**

---

## 1. Corrections to the pasted plan (facts, not opinions)

| แพลนเดิมบอก | ความจริง | ผลที่ตามมา |
|---|---|---|
| "เชื่อม Gemini API เป็นสมองหลัก" โดยอ้างว่ามี Gemini Plus | **Gemini Plus (subscription) ไม่ได้ให้ API quota** — API key มาจาก Google AI Studio (free tier มี rate limit) | ถ้าใช้ Gemini Plus คุยในแอป ไม่เกี่ยวกับ API เลย ต้องสร้าง key แยก (ฟรี) |
| Dify เป็นแชต + Agent, ดึง Drive 400 GB มาทำ RAG | Dify free = **50 MB / 50 เอกสาร** | 400 GB เข้าไม่ได้แม้แต่นิดเดียว → RAG แบบ vector search ทั้งกอง **เป็นไปไม่ได้ที่ฟรี** |
| Colab + Unsloth + Qwen3 = เทรน AI ให้เก่งเรื่องตลาด | Fine-tune เปลี่ยน **สไตล์/รูปแบบคำตอบ** ไม่ได้เพิ่มความรู้เรื่องตลาดหรือ alpha | โมเดลที่เทรนแล้วจะ "มั่นใจและ eloquent ขึ้น" แต่ไม่ได้เก่งขึ้นเรื่องทิศทาง — และการ serve LoRA ต้องมี GPU hosting (มีค่าใช้จ่าย) |
| FMP free 250 req/วัน (EOD) เป็นแหล่งข้อมูลหุ้น | เรามีข้อมูลที่ลึกกว่าแล้ว: 115 หุ้น US (10 ปี), 68 ETF (ถึงปี 2000), 64 หุ้น SET (10 ปี), FX hourly bid/ask 23 ปี, SEC XBRL, insider, congress | FMP ไม่จำเป็น และ 250 req/วัน จะหมดใน不到 1 ชั่วโมงถ้าสแกน screener |
| เก็บข้อมูล 400 GB บน Drive | **สินทรัพย์จริงคือชั้นที่คำนวณแล้ว ~70 MB** (datapack v2.7) ไม่ใช่ 400 GB ดิบ | เอาเวลาไปจัดการ 400 GB คือการหลอกตัวเองว่าทำงาน |

**สิ่งที่แพลนนั้นถูก:** RAG มาก่อน fine-tune, เริ่มจาก paper/demo, และไม่ต้องซื้ออะไรตอนเริ่ม — ถูกทั้งสามข้อ

---

## 2. What is actually missing (the real bottleneck)

ไม่ใช่โมเดล ไม่ใช่ GPU ไม่ใช่ hosting สามอย่างนี้คือของที่ขาด:

1. **ยังไม่มีกฎที่ผ่านการทดสอบ** — 19 การทดลอง, 0 edge ที่ผ่านเกณฑ์ (ดู `WHAT_FAILED.md`). EA ที่ไม่มีกฎ =
   เครื่องจักรที่ทำสิ่งที่ไม่มีหลักฐานรองรับ ด้วยความเร็วสูง
2. **Execution plumbing** — ต่อ MT5 demo, จัดการออเดอร์, spread/slippage จริง, reconnect, kill-switch
3. **สมองที่ใช้ได้จริงทุกวันโดยไม่แย่ง quota** — คำถามคือ "อ่านไฟล์ 6–35 KB แล้วตอบ" ไม่ใช่ "ค้น 400 GB"

ของ 1 คือปัญหาวิทยาศาสตร์ ของ 2 คือปัญหาวิศวกรรม (ทำได้) ของ 3 คือปัญหาการออกแบบ (แก้แล้ว ดูข้อ 3)

---

## 3. The architecture that costs ฿0 and works from a phone

```
[collectors]──► [derived layer]──► [one HTML file]──► มือถือ
 GitHub Actions    briefs/latest.md    dashboard/alina_today.html
 (ฟรี) หรือ PC      packs/YYYY-MM-DD.json   (self-contained, ไม่ต้องเน็ต)
        │
        └──► [EA on MT5 demo] ◄── [risk governor + kill switch]
```

| ชั้น | ใช้อะไร | ค่าใช้จ่าย | ทำไมไม่ใช่ตัวที่แพลนเสนอ |
|---|---|---|---|
| Data + compute | GitHub Actions cron (public repo = ฟรีไม่จำกัดนาที) หรือ PC ที่เปิดอยู่ | 0 | Colab ไม่ต้องใช้: งานนี้คือ REST + pandas ไม่ใช่ GPU |
| Derived layer | `collect_daily.py` → brief + pack + technicals + levels | 0 | — |
| **สมอง** | **on-demand เท่านั้น**: Gemini free-tier API key, หรือ Claude/GPT ที่มีอยู่แล้ว, หรือ Qwen3 local ผ่าน Ollama ถ้ามี PC | 0 | Dify + vector DB แก้ปัญหาที่เราไม่มี (ข้อมูลเรา 70 MB อ่านตรงได้) |
| UI | `dashboard/alina_today.html` — 9 KB, inline ทุกอย่าง, เปิดจาก Drive/มือถือได้ | 0 | เว็บแอปที่ต้อง host = server + API key ในเบราว์เซอร์ = ต้นทุน + ช่องโหว่ |
| Execution | MT5 **demo** + EA MQL5 (`ea/AlinaRiskGovernor.mq5` มีอยู่) | 0 | โบรกเกอร์จริงต้องใช้เงิน; demo ให้ spread จริง ฟรี |
| Fine-tune | **ยังไม่ทำ** | 0 | ต้องมี (ก) log 6 เดือน (ข) GPU (ค) เหตุผลว่า style ผิด — ยังไม่มีทั้งสาม |

**RAG ที่ถูกสำหรับงบ 0:** ไม่ใช่ vector search ทั้งกอง แต่คือ **curation** — `briefs/latest.md` (6 KB) +
`packs/<วัน>.json` (35 KB) + `catalog.json` (40 KB ตอนต้องเลือก dataset) → ยัดเข้า context ตรง ๆ ได้เลย
นี่คือเหตุผลที่เราสร้าง event pack: **การเลือกข้อมูลที่ถูก 중요กว่าการค้นข้อมูลเยอะ**

---

## 4. Market decision (ไม่ย้อนถามอีก)

**ทำทั้งสองตลาด แต่ลำดับคือ US ก่อน แล้ว TH** — และเหตุผลไม่ใช่ความชอบ:

| | US | TH (SET) |
|---|---|---|
| ข้อมูลที่มีแล้ว | 115 หุ้น 10 ปี, 68 ETF ถึงปี 2000, SEC XBRL 60 บริษัท, insider, congress | **64 หุ้น 10 ปี (2016-11→2026-11) + SET_EW index สร้างเอง** — เพิ่งเพิ่มวันนี้ |
| ต้นทุนต่อรอบ | ต่ำสุดในบรรดาสินทรัพย์ที่วัดมา (ETF/หุ้น liquid) | spread กว้างกว่า, tick ไม่ฟรี, ค่าธรรมเนียมขั้นต่ำต่อออเดอร์กินสัดส่วนมากเมื่อทุนเล็ก |
| ห้องสมุดผลทดสอบ | 19 การทดลองทั้งหมดอ้างอิงตลาดนี้ | ยังไม่มีแม้แต่การทดลองเดียว |
| EA | MT5 demo ทำได้ทันที | MT5 มี SET จริงผ่าน broker บางเจ้า แต่ symbol mapping ต้องเช็ค |

**ข้อจำกัดที่ต้องพูดตรง ๆ:** SET index (`^SET`) ไม่มีประวัติให้ฟรีจาก Yahoo (คืน 1 แท่ง) → เราสร้าง
`SET_EW` (equal-weight ของ 64 หุ้น, ฐาน 100) ใช้แทนได้ แต่ **ต้องบอกทุกครั้งว่าไม่ใช่ SET50** เพราะน้ำหนัก
ต่างกันมาก และ SET เป็นตลาดที่ dividend yield ~3% ทำให้ price-only index ต่ำกว่าความจริง

---

## 5. ลำดับงาน 7 วัน (สิ่งที่ต้องทำ + ใครทำ)

**ผมทำได้เอง (ไม่ต้องรอ):**
1. ✅ เพิ่มข้อมูล SET 64 หุ้น + `SET_EW` (เสร็จวันนี้)
2. ✅ `dashboard/alina_today.html` — เปิดจากมือถือได้ ไฟล์เดียว (เสร็จวันนี้)
3. ต่อ `collect_daily.py` ให้สร้าง dashboard อัตโนมัติทุกวัน
4. เขียน EA shell: อ่าน JSON จาก pack → ตรวจ risk governor → ส่ง demo order (MQL5, ไม่ compile ในเครื่องนี้ — ต้องมี MT5)
5. ทำ `scripts/ask.py` — CLI ที่ประกอบ prompt จาก brief+pack แล้วเรียก API ที่ผู้ใช้เลือก (key อยู่ใน env)

**ผู้ใช้ต้องทำ (5 นาทีต่อข้อ):**
1. สร้าง **Gemini API key** ที่ aistudio.google.com (ฟรี ไม่ต้องใช้ Plus) → เก็บใน `~/.alina/gemini_key`
2. เปิด **MT5 demo** กับโบรกเกอร์ใดก็ได้ (ฟรี) แล้วแจ้ง symbol ที่ต้องการ
3. ถ้าอยากให้รันเองทุกวัน: เปิด GitHub Actions ใน repo นี้ (workflow ตัวอย่างจะเขียนให้)

**ยังไม่ทำจนกว่าจะมีเหตุผล:** Dify, Colab training, Unsloth/Qwen3, HuggingFace, FMP — ทั้ง 5 ตัวนี้
แก้ปัญหา "การนำเสนอ" ไม่ใช่ปัญหา "ความสามารถ"

---

## 6. กติกาที่ต้องยึด ถ้าอยากให้ EA นี้ไม่ทำลายบัญชี

1. **EA ไม่มีสิทธิ์ตัดสินใจทิศทาง** จนกว่าจะมีกฎที่ผ่าน null + date-split — ตอนนี้ยังไม่มี (19/0)
2. EA ทำได้แค่: sizing, stop placement, spread filter, session filter, daily loss limit, kill switch
3. ทุกออเดอร์ต้องมี stop ที่คำนวณจาก ATR/level จริง ไม่ใช่ตัวเลขกลม
4. บันทึกทุกออเดอร์ลง CSV เพื่อให้ `governor.py` ตรวจย้อนหลังได้
5. **ห้าม martingale** — 5 ใน 5 เครื่องมือในโปรเจกต์นี้ถูกล้างพอร์ตด้วยกฎนั้น (EXP-0007)

> ข้อ 1 คือคำตอบตรง ๆ ของคำถาม "ทำ EA ออโต้ได้ไหม": **ได้ แต่สิ่งที่เทรดออโต้ได้อย่างมีความรับผิดชอบตอนนี้
> คือ "การจัดการความเสี่ยง" ไม่ใช่ "การหาจังหวะ"** เพราะจังหวะยังไม่มีตัวไหนผ่านการทดสอบ
