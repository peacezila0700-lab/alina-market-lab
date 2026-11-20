# STAGE 0 — WORKSPACE & PERMISSION AUDIT + ROADMAP REVIEW

- **วันที่ (UTC):** 2026-11-20
- **ผู้ทำ:** Alina (Arena Agent Mode)
- **ที่มาของแผน:** `uploads/ALINA_MARKET_LAB_MASTER_ROADMAP_TH.md` (v1.0, 1,207 บรรทัด)
- **สถานะ:** Stage 0 = PARTIAL PASS (มี blocker 2 ข้อที่ต้องตัดสินใจก่อน Stage 2)
- **ขอบเขตที่ทำ:** audit สิทธิ์/สภาพแวดล้อม + วิเคราะห์ roadmap เท่านั้น
- **ยังไม่ได้ทำ (ตามเจตนา):** ไม่เขียน trading strategy, ไม่สร้างโมเดล, ไม่เชื่อม broker, ไม่ใช้เงิน, ไม่บันทึก credential ลงไฟล์ใด ๆ

---

## 1. CAPABILITY MATRIX

| # | Capability | สถานะ | หลักฐาน (verified evidence) |
|---|---|---|---|
| 1 | Google Drive — read/search/list | ✅ VERIFIED | connector `google_drive` = enabled, tool list ครบ (list_files, search_files, read_file_text) |
| 2 | Google Drive — create/upload/read-back/delete | ✅ **VERIFIED (ทดสอบจริง 2026-11-20)** | upload → id `1nGX8ZTk6UZNeRg6rJzDIi7hVPInhFvhI` (402 bytes) → read_file_text คืนเนื้อหาตรง + checksum token ตรง → trash_file สำเร็จ `trashed:true` |
| 3 | Google Drive — folder tree 50+ โฟลเดอร์ | ⚠️ NOT VERIFIED | ยังไม่ทดสอบสร้างซ้อนหลายชั้น/จำนวนมาก |
| 4 | GitHub — connector | ❌ ไม่มี | `list_connector_tools(github)` → `unsupported` |
| 5 | GitHub — ผ่าน git + token ใน sandbox | ✅ VERIFIED | `GET /user` → 200, login `peacezila0700-lab`, 9 repos, scope มี `repo`,`workflow` |
| 6 | GitHub — push/commit/branch/PR | ✅ VERIFIED (สิทธิ์) / ⏳ ยังไม่ทดสอบ commit จริง | `GET /repos/...` → `permissions.push = true`, `admin = true` ทั้ง `tgat1-english-studio` (master) และ `Learning-tgat1` (main) |
| 7 | Python runtime | ✅ VERIFIED | Python 3.13.18 |
| 8 | Library | ✅ numpy 2.3.5, pandas 2.2.3, scipy 1.17.1, matplotlib 3.11.2, scikit-learn 1.6.1 | ❌ ไม่มี: statsmodels, yfinance (ติดตั้งได้/ไม่ได้ = ยังไม่ทดสอบ) |
| 9 | Network outbound HTTPS | ✅ VERIFIED | `api.github.com` 200, Yahoo Finance 200 |
| 10 | แหล่งข้อมูลราคา EURUSD | ⚠️ PARTIAL | ดูหัวข้อ 2 |
| 11 | Runtime ทำงานต่อเนื่อง 24/7 | ❌ BLOCKER | session-scoped, ไม่มี scheduler → Stage 10 (autonomous loop) และ Stage 12 (paper ต่อเนื่อง) ทำแบบ real-time ไม่ได้ |
| 12 | Broker / feed จริง | ❌ N/A | ยังไม่เชื่อม (ถูกต้องตามนโยบาย) |

**สรุป:** พื้นที่ที่ใช้งานได้จริง = sandbox (code/run) + Drive (doc) + GitHub (version control ผ่าน token)
พื้นที่ที่ **ทำไม่ได้** = ระบบรันต่อเนื่อง 24/7, real-time feed, scheduled job

---

## 2. DATA FEASIBILITY PROBE (ทดสอบจริง ไม่ใช่สมมติ)

### Yahoo Finance — EURUSD=X, interval 1h
```
bars          : 17,512
ช่วงข้อมูล    : 2024-02-05 00:00 UTC → 2026-11-20 14:42 UTC  (~2 ปี)
null closes   : 318
gaps > 3h     : 145 (ใหญ่สุด 50h = weekend/holiday)
volume/spread : ไม่มี
timezone      : GMT per meta, แต่ candle boundary ต้องตรวจซ้ำ
```

### แหล่งอื่นที่ทดสอบ
| แหล่ง | ผล | หมายเหตุ |
|---|---|---|
| Stooq (CSV) | ❌ blocked | เจอ JavaScript challenge ไม่ใช่ CSV |
| Dukascopy (`datafeed.dukascopy.com/.../ticks.bi5`) | ⚠️ HTTP 429 | rate limit แต่ endpoint มีจริง — เป็นแหล่ง tick + spread ที่ถูกต้อง ต้อง decode `.bi5` (LZMA) และโหลดทีละชั่วโมง |
| Yahoo H1 | ✅ ใช้ได้ | ข้อจำกัด 730 วัน, ไม่มี spread |

**ข้อสรุป data:** ถ้าจะทดสอบ H1 จริงจังต้องใช้ **Dukascopy tick → aggregate H1** (ได้ spread จริง) ซึ่งเป็นงานวิศวกรรม 2–4 ชั่วโมง และมี rate limit ต้อง throttle
ถ้ายอมรับข้อจำกัด → Yahoo H1 2 ปีใช้เป็น **provisional dataset สำหรับสร้าง pipeline/QC** ได้ แต่ **ห้ามใช้สรุป edge** (สั้นเกิน + ไม่มีต้นทุนจริง)

---

## 3. ROADMAP REVIEW — จุดที่เอกสารแข็งแรง

1. **Gate 0 (ตรวจสิทธิ์ก่อนสร้างอะไร)** — ถูกต้องและหายาก เอกสารเทรดทั่วไปข้ามขั้นนี้
2. **แยก FACT / ASSUMPTION / HYPOTHESIS / RESULT / DECISION** — ตรงจุดตายของงาน quant
3. **Defense ครบเรื่อง leakage / time-split / OOS / cost** — ครอบคลุมกว่ามาตรฐานบทความทั่วไปมาก
4. **AI ไม่มีสิทธิ์แก้ risk policy / เปิด live / ลบ evidence** — governance ถูกทิศ
5. **"สิ่งที่โครงการนี้ไม่ใช่"** ข้อ 1.2 — กล้าเขียนข้อจำกัดตัวเอง ดีมาก
6. **Definition of Done** ที่ไม่ยอมรับ "สร้างไฟล์แล้ว" เป็นความสำเร็จ

---

## 4. ROADMAP REVIEW — จุดที่จะพังในทางปฏิบัติ (8 ข้อ)

### 4.1 Documentation-first trap (สำคัญสุด)
Stage 1 สั่งสร้าง Drive tree ~50 โฟลเดอร์ + ไฟล์ canonical 14 ไฟล์ **ก่อน**มีข้อมูลสักแท่ง
สำหรับคนเดียวที่ยังไม่มี runtime = 2–3 session ของงานเอกสารที่ให้ **ข้อมูลใหม่ 0 บิต** และขัดกับ Definition of Done ในข้อ 15 ของเอกสารเอง
**แก้:** สร้าง 5 ไฟล์ที่มีประโยชน์ทันที (`MASTER_CONTEXT`, `PROJECT_RULES`, `CURRENT_STATE`, `MASTER_TASKS`, `SESSION_HANDOFF`) — ที่เหลือสร้าง "ตอนมีเนื้อหาใส่" ใช้ lazy creation

### 4.2 15 gate แต่ information gain ไม่เท่ากัน
ด่านที่ให้ข้อมูลจริง = Stage 2 (feasibility), 3 (data), 4 (descriptive), 7 (backtest)
Stage 11, 13, 15 = operating overhead ที่ควรเลื่อนไปทำหลังมี strategy ที่รอดชีวิต
**แก้:** ยุบเป็น 4 phase / 6 kill-point (หัวข้อ 5)

### 4.3 ไม่มี "เกณฑ์หยุด" (exit criteria) — มีแต่เกณฑ์ผ่าน
เอกสารบอกว่าผ่านด่านแล้วทำอะไรต่อ แต่ไม่บอกว่า **เมื่อไรควรเลิก** ทั้งที่งานนี้ base rate ของ "ไม่มี edge" สูงมาก
**ต้องเพิ่ม:** time box + experiment budget + kill criteria เช่น
- "ทดสอบ ≤ 12 hypotheses แล้วยังไม่ได้ net expectancy > 0 บน OOS → หยุด projekt-lab และสรุปบทเรียน"
- "ถ้า 2 sessions ติดกันไม่ได้ artifact ที่รันซ้ำได้ → ทบทวน scope"

### 4.4 ขาดคณิตศาสตร์ของ feasibility (ตัวเลขที่ต้องคิดก่อนเขียนโค้ด)
EURUSD H1: ATR ~ 10–15 pips; spread + commission round-trip ~1.0–2.0 pips (ขึ้นกับ broker/บัญชี)
→ ต้นทุน = **8–20% ของ ATR ต่อเทรด** → edge ต้องชนะต้นทุนนี้ก่อนพูดถึงกำไร
→ 2 ปี H1 ≈ 500 วันซื้อขาย, independent trades ที่ไม่ทับซ้อนอาจเหลือ 200–400 → statistical power ต่ำ
**แก้:** ประกาศ "ต้นทุนต่อเทรด" และ "จำนวน trade ขั้นต่ำ" เป็นตัวเลขก่อน Stage 6 และกำหนด minimum sample size ต่อการทดลอง

### 4.5 ไม่ระบุ broker/บัญชี/ค่าธรรมเนียม
Stage 7 สั่งให้คิด spread/commission/swap แต่ไม่มีแหล่งอ้างอิง → จะกลายเป็น "เดาต้นทุนให้ผลสวย"
**แก้:** ต้องล็อก 1 broker + 1 ประเภทบัญชี + เอกสาร contract spec ก่อน Stage 7 (ยังไม่ต้องสมัคร ไม่ต้องใช้เงิน — แค่ใช้เอกสาร public)

### 4.6 "Autonomous Research Loop" ขัดกับ runtime จริง
Stage 10–12 เขียนเหมือน agent ทำงานต่อเนื่อง แต่ session ไม่ต่อเนื่อง
**แก้:** เปลี่ยนเป็น **batch research mode**: 1 session = 1 experiment ที่จบในตัว + handoff (ตรงกับข้อ 13 ระดับ A เท่านั้น)

### 4.7 ไม่มีกฎกัน "agent แต่งตัวเลข"
risk ที่แท้จริงของโครงการนี้คือ AI เขียน metric สวย ๆ ในรายงานโดยไม่มี artifact
**แก้:** กฎเหล็ก — **ทุกตัวเลขในรายงานต้องมาจากไฟล์ผลลัพธ์ที่โค้ดใน workspace สร้าง พร้อม path + checksum** ถ้าไม่มีไฟล์ = เขียน NOT RUN

### 4.8 ไม่มี data licensing / redistribution check
Stage 2 พูดถึง license แค่ผ่าน ๆ แต่ Dukascopy/Yahoo มีข้อจำกัด redistribution → สำคัญถ้าเอาข้อมูลขึ้น GitHub
**แก้:** `.gitignore` data/, ใช้ manifest + checksum ชี้ path แทน (ตรงกับข้อ 5.2 ของเอกสารอยู่แล้ว — แค่ต้องบังคับใช้)

---

## 5. แผนที่压缩แล้ว (เสนอแทน 15 stage)

| Phase | ทำอะไร | ผ่านเมื่อ (Gate) | Kill point |
|---|---|---|---|
| **A. Foundation (1 session)** | Stage 0 ให้จบ + ล็อก 4 การตัดสินใจ (instrument / data source / broker cost model / experiment budget) + 5 memory files | เปิด session ใหม่แล้วตอบสถานะได้โดยไม่ต้องเล่าใหม่ | — |
| **B. Data (1–2 sessions)** | Dukascopy tick→H1 pipeline + QC + manifest/checksum + unit tests (ถ้า tick ไม่ไหว → Yahoo H1 provisional พร้อมเขียนข้อจำกัด) | สร้าง dataset ซ้ำจาก config เดิมได้ และ QC report ผ่าน | ≥5 ปี H1 + spread model ไม่ได้ → re-scope ก่อนไปต่อ |
| **C. Baseline + Backtest (2–3 sessions)** | descriptive stats → 1 baseline rule-based → cost-aware backtest engine + unit tests → walk-forward | baseline มี net expectancy หลังต้นทุน > 0 และไม่ leak | expectancy ≤ 0 → **ยังไม่ทำ ML** ทบทวน hypothesis |
| **D. ML / News (ยังไม่เริ่ม)** | เฉพาะเมื่อ C ผ่าน | ML ชนะ baseline บน OOS หลังต้นทุน | ไม่ชนะ → reject candidate |

Stage 9 (news), 11 (ops), 12 (paper), 13 (execution) = **parked** จนกว่า C จะผ่าน

---

## 6. การตัดสินใจที่ต้องได้จาก Owner ก่อนไป Stage 2

1. **Instrument / timeframe** — EURUSD H1 ตามเอกสาร หรือเปลี่ยน
2. **Data source** — Dukascopy tick (ถูก/ช้า/มี spread) หรือ Yahoo H1 (เร็ว/2 ปี/ไม่มี spread) หรือมีไฟล์เอง
3. **Broker + ประเภทบัญชี** สำหรับ cost model (ใช้เอกสาร public เท่านั้น ยังไม่สมัคร)
4. **โครงสร้างความจำ** — 14 ไฟล์ตามเอกสาร หรือย่อเป็น 5 ไฟล์ (แนะนำ)
5. **Experiment budget** — จำนวน hypothesis สูงสุดก่อนทบทวนสถานะโครงการ

---

## 7. สิ่งที่ยัง NOT VERIFIED (ห้ามถือว่าทำแล้ว)

- Drive write + read-back จริง (upload → อ่านกลับ)
- GitHub write (commit/push/branch)
- การติดตั้ง library เพิ่ม (statsmodels / หรือ decode `.bi5` ด้วย Python `lzma` — มาตรฐาน มีใน stdlib)
- Dukascopy ดึงข้อมูลจำนวนมากแบบไม่ติด rate limit
- ความถูกต้องของ candle boundary ของ Yahoo H1 (ต้องทดสอบกับ tick source)
