# ALINA Market Lab — Cloud Data & Research Continuation (`v2.20`)

Date UTC: `2026-11-21` | Baseline: `v2.19 (82e2d16)` | Active Phase: **Phase C Kill Point LOCKED (`0/35` directional edges passed)**

---

## 1. สิ่งที่ทำสำเร็จในรอบ `v2.20` (ขยายข้อมูล + ทดลองจริงทั้งหมด)
1. **ขยายหุ้นสหรัฐฯ ที่ Delisted/ล้มละลาย/M&A (`data/stocks_delisted_tiingo/` + `data/sec/pit_fundamentals_delisted.csv`):**
   - ดึง Tiingo EOD (`adjClose + divCash + splitFactor`) เพิ่ม `45` ตัว (`44` ตัว `>= 100` แถว) และคัดกรองตัวที่ symbol ถูกนำกลับมาใช้ซ้ำในตลาดปัจจุบันหรือข้อมูลสั้น (`SPLS`, `CA`, `EMC`, `WRK`, `NFX`) ออกทั้งหมด เหลือไฟล์สะอาด **`70` ตัว** (`90/500` โควตาเดือน Tiingo, เหลือ `410` symbols).
   - จับคู่ SEC EDGAR CIK ครบ **`41/41` ตัวที่เพิ่มมา** (`40` ตัวจาก SEC DERA `sub.txt` + `CTRA -> 858470`) และสร้าง `pit_fundamentals_delisted.csv` ใหม่เป็น **`2,372` PIT snapshots ครอบคลุม `68` บริษัท Delisted (`leaks = 0`)** (เพิ่ม `2.5x` จาก `27` บริษัทใน `v2.19`).
2. **ดึงข้อมูล SEC Form 4 Insider Transactions (`2018q1..2026q1`, 8.25 ปี):**
   - รวม 33 ไตรมาสจาก SEC DERA (`2018q1..2024q4` + `2025q1..2026q1`) เป็นไฟล์ `data/sec/insider_form4_2018_2026q1.csv.gz` (**`971,831` แถว `P/S` open-market across `8,826` tickers**, `21.18 MB`) และลบไฟล์ซ้ำ `2025_2026q1` ออกแล้ว.
3. **ตรวจสอบ FINRA API & ย้ายมาใช้ FINRA RegSHO Daily Short Sale Volume (`2019–2026-11-20`):**
   - ตรวจสอบ `api.finra.org/data/group/otcMarket/name/equityShortInterest` แล้วพบว่า API ฟรี (ไม่มี OAuth) ส่งคืนเฉพาะตลาด **`Other OTC` ปี `2018-09-14`** เท่านั้น ไม่ใช่ Short Interest ของ NYSE/NASDAQ จึงลบไฟล์ `finra_short_interest_latest5k.csv.gz` ที่อาจทำให้เข้าใจผิดออก.
   - ดึงข้อมูลสาธารณะรายวัน **FINRA RegSHO Consolidated NMS (`CNMSshvolYYYYMMDD.txt`)** ย้อนหลังเกือบ 8 ปี (**`1,984` วันทำการ `2019-01-02 .. 2026-11-20`**) ทั้งภาพรวมตลาด (`finra_regsho_market_daily.csv`) และรายหุ้น `375` ตัวในจักรวาล Active+Delisted (`finra_regsho_universe_daily.csv.gz`, **`661,677` แถว**).

---

## 2. ผลทดลอง `EXP-0034` (`H37`) & `EXP-0035` (`H38`) — ผลจริงแบบไม่เลือกข้าง
| Experiment | คำถามวิจัย | ผลที่วัดได้จริง (Survivorship-Free + Strict Lag) | การตัดสินใจ |
|---|---|---|---|
| **`EXP-0034`** (`H37`) | เมื่อขยายจาก `+27` เป็น **`+68` หุ้น Delisted** (`385` บริษัทรวม, `2016–2026`), `F_NEG_ACCRUALS` ยังรอด OOS และ 200 permutations หรือไม่? | `F_NEG_ACCRUALS (10bp)`: Active (`317`) **+0.729** (`IS +0.890 / OOS +0.572`, perm `99.5/92.5%`) $\rightarrow$ `+27 Del` (`344`) **+0.579** $\rightarrow$ **`+68 Del` (`385`) `+0.453`** (`IS +0.489 / OOS +0.413`, perm **`91.5/73.5%`**, `-37.9%` collapse; `528` delisted-quarters หลงเข้าฝั่ง Long vs `332` Short). `F_SECTOR_NEUT_ACCRUALS` OOS ร่วง `+0.227 -> -0.064` (`48.5%`). `F_CFO_ASSETS` แบบไม่จำกัดราคา `$2` ร่วง `OOS -1.199`. | **`FAIL_SURVIVORSHIP` — ปิดตาย Accounting Accruals Alpha ถาวร** |
| **`EXP-0035`** (`H38`) | SEC Form 4 (`filing_date + 1td`, `2018–26`) หรือ FINRA RegSHO (`date + 1td`, `2019–26`) สร้าง Alpha หรือช่วยเพิ่ม Walk-Forward AUC ของ Risk Radar ได้หรือไม่? | **Form 4:** ทั้ง 3 ปัจจัยเลือกทิศ `[neg]` ใน IS (ขายโดยผู้บริหารหุ้นใหญ่ vs หุ้นใกล้ล้มละลายซื้อถัว) และ **ไม่ผ่าน Fixed-Label Ticker Permutation (`OOS 72.5–86.5%` < `95%`)**.<br>**RegSHO:** `SHORT_RATIO` & `SHORT_SURGE` แพ้ (`All -0.030, -0.379`). `REGSHO_EXEMPT_RATIO_20D` (`All +0.753`) พึ่งพาปี COVID **`2020 (+3.399)`** เพียงปีเดียว ขณะที่ `2021 (-0.395)`, `2022 (-0.534)`, `2024 (-0.995)` ติดลบหมด และ OOS หลังทำลาย tie ได้แค่ `+0.335` (`perm 89.0%`).<br>**Risk Meta ML:** การเติม RegSHO ลงใน Walk-Forward Risk Meta ทำให้ `TailStress AUC` **ลดลง `0.6624 -> 0.6347 (-0.0277)`**. | **`NO_EDGE` — ไม่ใช้เป็น Signal และไม่ใส่ใน HGBC Risk Meta; นำเข้าเฉพาะ Panel 9 เชิงบริบท** |

---

## 3. อัปเกรด Risk Radar (`scripts/risk_radar.py`) & ระบบทดสอบ (`36/36 pytest`)
- เพิ่ม **Panel 9 (`equity_short_insider_breadth`)** อ่านค่า `finra_regsho_market_daily.csv` รายวัน (ล่าสุด **`2026-11-20`**: `mkt_short_ratio = 0.4612`, `z60 = -2.02`, `12,414` NMS symbols) + บริบท Form 4 (`2018q1..2026q1`) **โดยไม่ปนเปื้อนโมเดล Risk Meta 23 ปัจจัย** (`TailStress WF AUC 0.697` คงเดิม).
- ผลรันล่าสุด: **`RISK RADAR OK: overall=HIGH | fresh=9/9 | alerts=4`** (`VIX=35.89`, `VIX/VIX3M=1.160`, `SPY RV20=26.3%`, `RegSHO z60=-2.02`).
- Regenerate `dashboard/alina_today.html` (`13 KB`, self-contained offline) และผ่าน **`36/36 pytest` (`3.10s`)** รวมถึง `test_exp0034_0035_expanded_survivorship_and_form4_regsho`.
