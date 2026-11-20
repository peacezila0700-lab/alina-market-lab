# ALINA MARKET LAB — PLAN v1: Instrument Selection & Data Strategy

- **วันที่:** 2026-11-20 (UTC)
- **สถานะ:** PROPOSAL — รอ owner ยืนยัน 3 ข้อ (ท้ายไฟล์) ก่อนเริ่ม Phase B
- **ที่มาโจทย์:** owner ต้องการสินทรัพย์ที่ (1) ไม่ผันผวนรุนแรง อยู่ในกรอบ (2) มีหลักการทางคณิตศาสตร์ + เศรษฐศาสตร์รองรับ (3) เป็นที่ใช้กันทั่วโลก เชื่อถือได้ (4) แหล่งข้อมูลเยอะทั้งทางการและไม่ทางการ (5) เทรดแบบปกติด้วย EA ไม่ใช่ prop firm
- **หลักฐานทั้งหมดในไฟล์นี้มาจากการทดสอบจริง** (`alina_lab/screen/`) ไม่ใช่ความเห็น

---

# 1. สรุปคำแนะนำ (RECOMMENDATION)

| บทบาท | สินทรัพย์ | เหตุผลสั้น |
|---|---|---|
| **ตัวหลัก (research instrument)** | **EURGBP — Daily/4H bias, H1 execution** | range-bound ที่สุดในกลุ่ม FX หลัก + ข้อมูลเป็นทางการเยอะที่สุดในโลกคู่หนึ่ง |
| **ตัวควบคุม (control / pipeline test)** | **EURUSD** | ต้นทุน/ATR ดีที่สุด + liquidity สูงสุด → ใช้ตรวจว่า pipeline/backtest engine เราไม่เพี้ยน |
| **ไม่แนะนำในรอบนี้** | XAU/XAG, EURCHF, AUDNZD | ดูหัวข้อ 2.3 |

---

# 2. หลักฐานการคัดเลือก

## 2.1 วัด "ความอยู่ในกรอบ" (range-ness) — ข้อมูลจริง 10 ปี

| symbol | vol% ต่อปี | Hurst (ต่ำ=ย้อนกลับ) | half-life ของ dev จาก 50dMA | เวลาที่อยู่ใน ±2% ของ 200dMA |
|---|---|---|---|---|
| **EURGBP** | 8.1 | **0.297** (ต่ำสุด) | **4.2 วัน** (เร็วสุด) | **66%** |
| AUDNZD | 5.1 | 0.472 | 21.4 วัน | — |
| EURCHF | 4.9 | 0.423 | 15.4 วัน | — |
| AUDCAD | 7.1 | 0.427 | 13.7 วัน | — |
| EURUSD | 7.1 | 0.500 (trending) | 21.5 วัน | 41% |
| GBPUSD | 8.5 | 0.471 | 18.9 วัน | — |
| USDJPY | 8.6 | 0.512 (trending) | 23.9 วัน | — |
| ทองคำ GC | 17.2 | 0.475 | 20.1 วัน | — |
| เงิน SI | 35.4 | 0.462 | 16.6 วัน | — |

**FACT:** EURGBP มีค่า Hurst 0.297 = พฤติกรรมย้อนกลับ (mean-reverting) ชัดที่สุด และอยู่ห่างจาก 200dMA ไม่เกิน ±2% ถึง 66% ของเวลา — ตรงกับโจทย์ "อยู่ใน range" ที่สุดในบรรดาสินทรัพย์ที่ทดสอบ

## 2.2 ช่วงราคาจริงรายปี (EURGBP)

```
2018  0.8635–0.9085 ( 5.2%)      2023  0.8512–0.8958 ( 5.2%)
2019  0.8300–0.9323 (12.3%)      2024  0.8230–0.8671 ( 5.4%)
2020  0.8303–0.9425 (13.5%)      2025  0.8250–0.8842 ( 7.2%)
2021  0.8385–0.9056 ( 8.0%)      2026  0.8324–0.8771 ( 5.4%)
2022  0.8229–0.9790 (19.0%)  ← ปีที่หลุดกรอบ (Brexit/energy crisis + USD shock)
```
ปัจจุบัน 0.83773 — **อยู่ครึ่งล่างของกรอบ 10 ปี** (0.823–0.979, โซนหนาแน่น 0.825–0.90)

## 2.3 ทำไมไม่เลือกตัวอื่น

| ตัวเลือก | เหตุผลที่ปฏิเสธ (มีตัวเลข) |
|---|---|
| **XAU/XAG (ทอง/เงิน)** | ratio ย้อนกลับดี (half-life 12.6d, Hurst 0.421) **แต่** ตัวสินทรัพย์เองผันผวน 17% และ 35%/ปี → ผิดโจทย์ "ไม่ผันผวน" + ต้องจ่าย spread สอง legs |
| **EURCHF** | vol ต่ำสุด (4.9%) แต่มีความเสี่ยงเชิงโครงสร้าง: SNB เคยปลดเพดาน 2015 → ราคากระโดด ~30% ในนาทีเดียว (tail risk ที่ EA ไม่มีทางป้องกัน) |
| **AUDNZD** | ทฤษฎีสวย (สองเศรษฐกิจคล้ายกัน) แต่ทดสอบ cointegration กับ AUDCAD/NZDCAD ได้ ADF t = -0.84 / -0.82 (ไม่ผ่านเกณฑ์ -2.86) → "ทฤษฎีดี แต่ข้อมูลไม่รองรับ" |
| **คู่ spread อื่น** | ทดสอบแล้ว ADF ไม่ผ่านเกณฑ์ทุกคู่ ยกเว้น EURGBP/EURUSD (t=-3.55) ซึ่งเป็นคู่แปลก (corr เพียง 0.10) ไม่มีความหมายเชิงเศรษฐกิจ |

## 2.4 หลักการรองรับ (ตอบโจทย์ข้อ 2)

**เศรษฐศาสตร์**
- EURGBP คือราคาเปรียบเทียบของสองเศรษฐกิจที่ผูกกันด้วยการค้า: EU เป็นคู่ค้ารายใหญ่สุดของ UK (~50% ของ UK trade) → มีแรงดึงดูดตามทฤษฎี **PPP / law of one price** ระยะกลาง
- ดอกเบี้ย (ECB vs BoE) เป็นตัวขับทิศทาง แต่ส่วนต่างมักแกว่งในกรอบ → ราคาแกว่งตามส่วนต่าง ไม่วิ่งทางเดียว
- Trade flow / current account เป็นแรงย้อนกลับเมื่อราคาเบี่ยงมาก (UK import แพงขึ้น → demand EUR ลด)

**คณิตศาสตร์**
- Mean reversion = กระบวนการ **Ornstein–Uhlenbeck**: dX = θ(μ−X)dt + σdW → half-life = ln2/θ (เราวัดได้ = 4.2 วัน)
- Stationarity test = **ADF**; การวัด Hurst < 0.5 = anti-persistent
- Position sizing/risk มาจาก volatility targeting ไม่ใช่ความรู้สึก

**ความน่าเชื่อถือของข้อมูล (ตอบโจทย์ข้อ 3–4)**
- เป็นคู่เงิน major ที่ทุก broker ทั่วโลกมี, spread แคบ, ไม่มีปัญหา liquidity
- แหล่งข้อมูลทางการที่มี: **ECB ( Statistical Data Warehouse)**, **BoE database**, **ONS (UK statistics)**, **Eurostat**, **BIS**, **IMF/IFS**
- แหล่งราคา: **Dukascopy (tick ฟรี)**, Yahoo/Stooq (OHLC), broker MT5 history, TrueFX, HistData

---

# 3. ต้นทุน — ตัวเลขที่ต้องรู้ก่อนเขียน EA

**FACT (วัดจาก tick จริงของ Dukascopy — EURGBP 2025-01-02 ชั่วโมง 00:00 UTC, 1,332 ticks):**
```
spread median 0.90 pip | mean 0.96 | p95 1.20
H1 bar จาก tick: O=0.82672 H=0.82724 L=0.82663 C=0.82703
```

**FACT (Yahoo H1, 2 ปี):**

| instrument | ATR(H1) pips | spread ตัวแทน | spread / ATR |
|---|---|---|---|
| EURGBP | 5.9 | 0.9 | **15%** |
| EURCHF | 10.9 | 0.9 | 8% |
| EURUSD | 9.4 | 0.2–0.9 | **2–10%** |
| AUDNZD | 12.1 | 1.5 | 12% |

**IMPLICATION (สำคัญมาก — เปลี่ยนรูปแบบ EA ที่ควรทำ):**
EURGBP ผันผวนต่ำ → spread กิน 15% ของ ATR ต่อขา ⇒ **ห้ามทำ EA scalping H1** (target 5–8 pips จะถูกต้นทุนกินหมด)
ต้องเป็น **mean-reversion ระดับวัน: target 15–40 pips, holding 1–5 วัน, เข้าด้วย limit order** (ได้ spread ดีขึ้น + ไม่จ่ายค่า spread ตอนแพ้)
กติกาขั้นต่ำที่ควรตั้ง: `expected move ≥ 3 × round-trip cost` (เช่น target ≥ 6 pips, จริงควร ≥ 15)

---

# 4. Data Strategy — ใช้หลายแหล่ง ตรวจกันไปมา

| # | แหล่ง | ให้อะไร | สถานะที่ทดสอบแล้ว |
|---|---|---|---|
| 1 | **Dukascopy datafeed** | tick + spread จริง, ทุกคู่ FX/metals, ย้อนหลัง ~20 ปี | ✅ ทดสอบ decode สำเร็จ (HTTP 200, 5,242 bytes → 1,332 ticks) ⚠️ มี rate limit/TLS reset ต้อง throttle + retry |
| 2 | **Yahoo Finance** | OHLC H1 730 วัน / Daily 10 ปี | ✅ ใช้งานได้ (17,217 bars, 295 null) แต่ไม่มี spread/volume |
| 3 | **ECB Data Warehouse** | EUR/GBP reference rate ทางการ รายวัน | ✅ ทดสอบแล้ว (CSV data API) |
| 4 | **BoE / ONS / Eurostat** | ดอกเบี้ย, เงินเฟ้อ, การค้า (macro context) | ⏳ ยังไม่ทดสอบ |
| 5 | **FRED** | ชุดข้อมูลมหภาคสำรอง | ⚠️ timeout ในการทดสอบ (ลองใหม่ได้) |
| 6 | **broker MT5** | ข้อมูลจริงของโบรกที่ใช้ + spread จริง | ⏳ ต้องให้ owner export |
| 7 | HistData / TrueFX | tick ทางเลือกสำรอง | ⏳ ยังไม่ทดสอบ |
| 8 | Stooq | OHLC | ❌ ติด JS challenge |

**หลักการ:** ใช้ **Dukascopy = source of truth** สำหรับราคา+spread, ใช้ **ECB = ตรวจความถูกต้องของระดับราคา (sanity anchor)**, ใช้ **Yahoo = ช่วงยาว/ตรวจซ้ำเร็ว**, และ **broker spread = cost model จริง**
ห้ามใช้ข้อมูลแหล่งเดียวโดยไม่ตรวจ — ถ้าสองแหล่งต่างกันเกิน threshold ให้ตั้งธงว่าเป็น data quality issue

---

# 5. แผนดำเนินการ (แก้จาก 15 Stage → 4 Phase)

## Phase A — Foundation (session นี้/ถัดไป, ไม่เกิน 1 session)
- ปิด Stage 0: ทดสอบ Drive write + read-back จริง / GitHub commit จริง (เขียนไฟล์ทดสอบ 1 commit แล้วลบ)
- ล็อกการตัดสินใจ 3 ข้อ (ท้ายไฟล์) → บันทึก DECISION_LOG
- สร้าง 5 ไฟล์ความจำ: `MASTER_CONTEXT`, `PROJECT_RULES`, `CURRENT_STATE`, `MASTER_TASKS`, `SESSION_HANDOFF`
- **Gate A:** เปิด session ใหม่แล้วตอบสถานะได้โดยไม่ต้องเล่าใหม่

## Phase B — Data Pipeline (1–3 session)
- `ingest_duka.py`: ดาวน์โหลด tick EURGBP (throttle + retry + cache) → aggregate เป็น **H1 (bid + spread เฉลี่ย)**
- ถ้า tick ไหว → ย้อนหลังให้ได้ **≥ 5 ปี** (ปีละ ~2,000 ไฟล์ชั่วโมง; ต้อง throttle ~0.5–1 วิ/ไฟล์ → หลายชั่วโมง, รันเป็น batch ได้)
- `qc.py`: sorted timestamp, duplicate bars, missing bars (weekend/holiday calendar), OHLC consistency, spread distribution, cross-check กับ ECB daily
- `manifest.json` + checksum, แยก `data/raw`, `data/processed` (data/ อยู่ใน .gitignore)
- **Gate B:** สร้าง dataset ซ้ำจาก config เดิมได้ + QC report ผ่าน
- **Kill point:** ถ้าได้ < 5 ปี หรือ spread model ไม่ได้ → หยุด re-scope ก่อนไปต่อ

## Phase C — Research + Baseline + Backtest (2–4 session)
- Descriptive: half-life, regime segmentation, จุดที่ pattern เปลี่ยน (2016 Brexit, 2022) — ทุกข้อมี status supported/weak/inconclusive/rejected
- Baseline 2 ตัวเท่านั้น: (1) no-trade (2) mean-reversion จาก dev ของ MA + z-score threshold, limit entry, time stop
- Backtest engine: next-bar execution, spread, slippage, swap, position state, unit tests
- Walk-forward + OOS (ห้ามแตะชุดสุดท้ายจนจบ)
- **Gate C:** net expectancy หลังต้นทุน > 0 บน OOS และไม่ leak
- **Kill point:** expectancy ≤ 0 → **ไม่ทำ ML** (ตามเอกสาร) ทบทวน hypothesis หรือหยุด

## Phase D — ML / News (park ไว้)
เฉพาะเมื่อ C ผ่าน และ ML ต้องชนะ baseline บน OOS หลังต้นทุน

## EA (MT5) — เมื่อไร
หลัง Phase C ผ่านเท่านั้น: prototype เป็น Python → freeze logic เป็น spec → เขียน MQL5 EA ที่ **แยก strategy / risk / order** → demo forward test
**ยังไม่แตะเงินจริง** ตาม Risk Policy ข้อ 1–3

## Experiment budget (ข้อเสนอ)
- ทดสอบไม่เกิน **12 hypotheses** ก่อนทบทวนสถานะโครงการทั้งก้อน
- 1 session = 1 experiment ที่จบในตัว (batch mode เพราะไม่มี runtime 24/7)
- ชุดข้อมูล OOS 6 เดือนสุดท้าย = **ล็อก** ห้ามแตะจนกว่าจะตัดสินใจสุดท้าย

---

# 6. สิ่งที่ต้องให้ owner ยืนยัน (3 ข้อ)

1. **สินทรัพย์:** EURGBP เป็นตัวหลัก + EURUSD เป็น control — ตกลงหรือไม่ (ถ้าไม่ ตอบว่าอยากได้อะไร แล้วผมทดสอบให้ด้วยหลักฐานแบบเดียวกัน)
2. **โบรกเกอร์:** ชื่อ + ประเภทบัญชี (เช่น Exness Standard / IC Markets Raw) — ใช้แค่เอกสาร public ทำ cost model ไม่ต้องสมัคร ไม่ต้องใช้เงิน ไม่ต้องส่ง credential
3. **รูปแบบ EA:** ยืนยันว่าเน้น mean-reversion ระดับวัน (ไม่ใช่ scalping H1) เพราะตัวเลขต้นทุนบังคับ — หรือต้องการให้ทดสอบทั้งสองแบบแล้วเทียบกัน

---

# 7. สถานะ/ข้อจำกัดที่ยังไม่ยืนยัน (NOT VERIFIED)

- Drive write + read-back จริง
- GitHub write (commit/push)
- ดาวน์โหลด Dukascopy หลายพันไฟล์แบบไม่ถูกบล็อก (ต้องทดสอบ rate limit จริงใน Phase B)
- spread ของโบรกเกอร์จริง (ยังไม่มี spec)
- swap/financing (ต้องดึงจาก broker spec)
