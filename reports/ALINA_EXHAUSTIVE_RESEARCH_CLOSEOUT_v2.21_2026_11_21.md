# ALINA Market Lab — Exhaustive Multi-Asset Research Closeout (`v2.21` · `EXP-0001..0042`)

**Date:** `2026-11-21 (UTC)` · **Commit:** `v2.21` · **Test Suite:** `37/37 pytest PASSED (3.00s)`  
**Governance:** Phase C Directional Market-Neutral / Stock-Selection Alpha Kill Point **LOCKED (`0/41` non-trend experiments pass; Phase D ML & Auto-Execution PARKED)** · Two Audited Long-Only Defensive Risk/Trend Overlays Operational (`EXP-0033` Equities + `EXP-0041` Crypto).

---

## 1. บทสรุปผู้บริหาร (Executive Summary — Exhaustive Wave `EXP-0036..0042`)

หลังจากอุดช่องโหว่ด้านข้อมูลครบทุกแกนใน `v2.19–v2.20` (Tiingo TR `adjClose` + `BIL`, `70` หุ้น delisted / `68` SEC XBRL `0` leaks, `971,831` Form 4, `1,984` วัน FINRA RegSHO, Binance Vision 6.8 ปี 1h spot/perp/funding/OFI, Deribit DVOL 5.6 ปี, FRED Rates & 408 Treasury Auctions, และ ETF TR 26 ปี ครบ `73/73` ไฟล์) ทีมวิจัยได้ทดสอบสมมติฐานที่เหลืออยู่ทั้งหมดแบบ **"จนตันสุดๆ"** เพิ่มอีก **7 การทดลอง (`EXP-0036 .. EXP-0042`, รวมเป็น `42` การทดลองตลอดโครงการ)** ผลลัพธ์ทางวิทยาศาสตร์ชัดเจนและเฉียบขาดดังนี้:

1. **ตลาดที่ถูก Front-Run, Arbitrage, หรือ Cost-Wall ทำลายจนไม่เหลือ Alpha ทิศทาง (`6/7` การทดลองใหม่ `NO_EDGE`):**
   - **`EXP-0036` S&P 500 Index Rebalance Drift (`2015–2026`, `558` เหตุการณ์ / `123` matched at `t_eff+1td`):** กองทุนสถาบัน front-run ก่อนวัน effective (`ADD +5d` net20bp **`-0.925%`**, `t=-1.91, p=0.066`, `+21d p=0.79`; `REMOVE +21d` กลับทิศ `IS +8.535% -> OOS -8.828%`; Calendar 21d L/S `All = -0.139`).
   - **`EXP-0037` Causal SEC EDGAR PEAD (`2015–2026`, `15,000` filings across `388` active+delisted firms):** ข้อมูลที่ยึด timestamp `available_from` จาก SEC ยืนยันว่าตลาดรับรู้จาก earnings call ไปหมดแล้ว (`car_2d` IC `IS +0.0284 -> OOS -0.0089`; 21d L/S 10bp **ติดลบทุกตัว** `-0.022` ถึง `-0.672`).
   - **`EXP-0038` Crypto 6.8y 1H Microstructure, Cash-and-Carry & DVOL (`2020–2026`):**
     - `1H OFI / Basis Reversion / Ret4h` พังยับหลังหักค่าธรรมเนียม `4bp/side` (`BTC BASIS_REV` gross `+2.451` $\rightarrow$ **`net4bp OOS -1.946, All -0.314`**; `OFI_MOM_1H` `-1.612 .. -3.992`).
     - `Cash-and-Carry (50/50 unlevered, 8bp)` หลัง Spot ETF ปี `2024–2026` ถูกบีบเหลือผลตอบแทน **`+3.56%/yr (BTC, DD -0.22%)`** และ **`+3.47%/yr (ETH)`** — เทียบเท่าดอกเบี้ย T-Bill ก่อนคิดความเสี่ยง exchange/liquidation!
     - `VRP = DVOL - RV21` พยากรณ์ความผันผวนได้จริง (`VolOnset AUC = 0.7198`) แต่การนำ `DVOL` มา throttle `VT30` ทำให้ Sharpe ลดลง (`+0.376, Cal 0.131` vs `VT30 +0.467`).
   - **`EXP-0039` SqueezeMetrics DIX/GEX, Multi-Asset ETF Allocation (`GEM / GTAA-6 / RiskParity`), & 26y US Sector Mom12-1:**
     - กลยุทธ์ชื่อดังจากหนังสือทั้งหมด **ไม่ผ่าน OOS / Circular Shift (`2009–2026` TR + `BIL`)** เทียบกับ `60/40 (All +0.963, +10.01%, Cal 0.461)` และ `SPY (+0.877, +14.52%)`: `Antonacci GEM` (`IS +0.599 -> OOS +0.358, shift 15.0%`), `Faber GTAA-6` (`shift 72.5%`), `RiskParity 10VT` (`IS +1.370 -> OOS +0.693, shift 50.5%`).
     - `SPDR 9-Sector Mom12-1 (2001–2026)`: `Top3 LO +0.584` ไม่ต่างจาก `EW +0.575 (shift 66.5%)`; `Top3-Bot3 L/S All = -0.035`.
     - `DIX/GEX` เมื่อนำไปต่อกับ **Risk Meta 23 ตัวแปรเต็มรูปแบบ (`2014–2026 WF`)** ไม่ช่วยเพิ่ม AUC (`VolOnset 0.7656 -> 0.7633`, `TailStress 0.6461 -> 0.6451`).
   - **`EXP-0040` Treasury Yield-Curve Regime + 408 Auctions (`2007–2026` excess over `BIL`):**
     - `TLT` หมดยุค QE พังจาก `IS +0.454 -> OOS -0.160 (DD -48.4%)`; กฎ `10y3m > 0`, `10y2y > 0`, `SMA126` **ติดลบ OOS ทุกสูตร (`-0.067 .. -0.327`, shifts `39–80%`)** และ `408` การประมูลพันธบัตร 10Y/30Y มีสหสัมพันธ์กับผลตอบแทนล่วงหน้าใกล้ศูนย์ (`r = -0.0075 .. -0.0427`).
   - **`EXP-0042` Overnight (`C->O`) vs Intraday (`O->C`) Cost Wall (`2000–2026`, `6,762` วัน):**
     - Gross `Overnight 0bp` ดูสวย (`SPY +0.686 / QQQ +0.947 / IWM +1.105 / GLD +0.832`) แต่หมุนเวียน `252 รอบ/ปี` มี **Breakeven เพียง `1.52–2.90 bp/side`** — แค่ค่าคอม/สเปรด `2 bp/side` ทำให้ `SPY -0.217`, `GLD +0.067`, `QQQ +0.249` และ `5 bp/side` พังหมด **`-0.80 .. -2.49`**!

2. **หนึ่งเดียวที่รอดบททดสอบความจริงข้ามทศวรรษ — `EXP-0041` Crypto Daily Trend + Vol-Targeting (`Long-Only Defensive Regime Overlay`):**
   - ทดสอบแบบ **zero-tuning** (`SMA(50)` และ `TrendEns(20,40,60,90,120)` + `VolTarget 25%`, หัก `EFFR` risk-free rate, ทดสอบความหน่วง `1-day` และ `2-day`, ค่าธรรมเนียม `10–50 bp/side`, และ `1,000` circular shifts):
   - **`BTC 11.5 ปี (2015-06 .. 2026-11-21)` ผ่านครบทุก 3 ยุค (`2015–19` | `2020–22` | `2023–26 Post-ETF`):**
     - `SMA50_VT25 (10bp)`: **`Excess Sharpe +1.665`**, `CAGR +45.3%`, **`MaxDD -33.5%` (ลดจาก `-83.4%`)**, **`Calmar 1.350`** (`15-19: +2.220` | `20-22: +1.190` | `23-26: +1.292`) — ยังคงบวกที่ **`50bp/side = +1.415`**, และชนะ **`99.9%` (`999/1000`, `p = 0.001`)** ของ circular shifts (ผ่านแม้กระทั่ง **Bonferroni 42 การทดลอง `<0.00119`**!) ขณะที่ `Last Era 23-26 = 97.4%` และชนะ `Pure_VT25_NoTrend` (`Sh +1.030, DD -48.6%`).
     - `TrendEns(20,40,60,90,120)_VT25`: `All Sh +1.590, DD -27.8%, Calmar 1.446` (`Shift1000 = 99.9%`), แม้ดีเลย์ **2 วันเต็ม (`2dLag`)** ยังได้ **`+1.484 (Shift1000 = 99.7%)`**!
   - **ยืนยันซ้ำข้ามเหรียญและ ETF:**
     - `ETH 7.1y (2020–2026)` `SMA50_VT25`: **`Sh +1.288, CAGR +33.5%, MaxDD -21.6%` (vs `ETH B&H -79.3%`), `Calmar 1.552`, `Shift1000 = 99.5%` (`23–26 = 98.0%`)**.
     - `3-Coin Basket (BTC+ETH+SOL, 2021–2026)` `TrendEns_VT25`: `All Sh +1.128, MaxDD -22.72%, Cal 0.976` (ยุค Post-ETF `23–26: Sh +1.087, DD -16.06%, Cal 1.499`).
     - `IBIT Spot ETF (2024–2026)`: `SMA50_1dLag` **`Sh +0.670 (+19.9%, DD -25.9%)`** vs `IBIT B&H +0.139 (-1.7%, DD -54.0%)`.
   - **Cross-Asset Synergy กับ `EXP-0033` Equity Defense (`2015–2026`, `n = 2,888` วันทำการ NYSE):**
     - สหสัมพันธ์รายวัน `corr(SPY_VT12, BTC_TrendEns_VT25) = +0.108`!
     - พอร์ตผสม **`85% SPY_VT12 + 15% BTC_TrendEns_VT25`**: Excess Sharpe เพิ่มจาก **`+0.736 -> +1.157`** (`OOS 20–26: +0.671 -> +0.897`, `PostETF 23–26: +0.794 -> +0.996`), `CAGR +10.35% -> +14.80%`, `Calmar 0.693 -> 0.962` ที่ **`MaxDD -15.38%` แทบไม่เพิ่มความเสี่ยงขาลง!**
   - **ข้อจำกัดที่ต้องซื่อสัตย์ 100% (`Epistemic Honesty`):** นี่คือ **Long-Only Volatility-Managed Trend Regime Overlay** (*ไม่ใช่* Market-Neutral Arbitrage): ยังคงมี Drawdown `-22% .. -34%`, แพ้ whipsaw ในตลาดหมีไซด์เวย์ปี 2022, และ `SOL` ยุค `23–26` เสื่อมเหลือ `shift 74.6%` จึงต้องใช้เพื่อ **กำหนดสัดส่วนเสี่ยง/ถือเงินสด** ใน `Risk Radar` ไม่ใช่เป็นสัญญาณเทรดระยะสั้นอัตโนมัติ

---

## 2. สรุปผลการทดลองคลื่นสุดท้าย (`EXP-0036 .. EXP-0042`)

| Exp | Hypothesis | Asset / Dataset | Key Quantitative Results (Strict Causal + Costs) | Perm / Shift | Verdict |
|---|---|---|---|---|---|
| **EXP-0036** | `H39` S&P 500 Rebalance Drift | `558` events (`123` matched), `2015–26` | `ADD+5d` net20bp `-0.925%` (`p=0.066`), `+21d` `+0.281%` (`p=0.79`); `REMOVE+21d` flipped `+8.54% -> -8.83%`; `21d L/S All -0.139` | IS/OOS fail | **`NO_EDGE`** |
| **EXP-0037** | `H40` SEC PIT PEAD & Surprises | `15,000` filings (`388` firms, `68` delisted) | Event IC OOS collapsed (`car_2d -0.0089`, `d_rev +0.0033`, `d_ni -0.0012`); `21d L/S` All `-0.022` to `-0.672` | `1.5–81.5%` OOS | **`NO_EDGE`** |
| **EXP-0038** | `H41` Crypto 6.8y 1H / Funding / DVOL | Binance 1h (`60k` bars) + Deribit DVOL | 1h `4bp` all negative (`-0.31..-3.99`); Post-2024 Cash-Carry `+3.5–3.6%/yr`; `VT30+DVOL` (`+0.376`) < `VT30` (`+0.467`); Daily SMA escalated | `96–97%` SMA | **`MIXED_ESCALATED`** |
| **EXP-0039** | `H42` DIX/GEX, ETF Book Rules, Sectors | `17.5–26y` TR ETFs + `BIL` + `DIX/GEX` | `GEM OOS +0.358`, `GTAA-6 +0.718`, `RP OOS +0.693` vs `60/40 +0.963`; Sector `L/S -0.035`; `+DIX/GEX` on 23f AUC `-0.002` | `15.0–87.5%` | **`NO_EDGE`** |
| **EXP-0040** | `H43` Treasury Curve + 408 Auctions | `TLT/IEF/BIL` `08–26` + `408` 10Y/30Y auctions | `TLT ex-BIL OOS -0.160`; ALL Curve+SMA OOS `-0.067..-0.327`; Auctions `r=-0.0075..-0.0427` | `39.0–80.0%` | **`NO_EDGE`** |
| **EXP-0041** | `H44` Crypto Daily Trend + VT25% (11.5y) | `BTC 11.5y`, `ETH 7.1y`, `SOL`, `IBIT`, `SPY` | `BTC SMA50_VT25`: `Sh +1.665 DD -33.5% Cal 1.350` (`50bp +1.415`); `ETH +1.288 DD -21.6%`; `85/15` Blend `Sh +1.157 DD -15.38%` | **`99.9%` BTC / `99.5%` ETH** | **`VALIDATED_TREND_REGIME_DEFENSE`** |
| **EXP-0042** | `H45` Overnight vs Intraday Cost Wall | `SPY/QQQ/IWM/TLT/GLD` (`26.8y`, `6,762d`) | `0bp ON +0.686..+1.105` (BE `1.52–2.90 bp/side`) collapses at `2bp` (`SPY -0.217`, `GLD +0.067`) and `5bp` (`-0.80..-2.49`) | Cost Wall | **`NO_EDGE`** |

---

## 3. สภาพล่าสุดใน Daily Risk Radar (`2026-11-21`, `9/9 FRESH`, `overall = HIGH`)

- **Equity Defense (`EXP-0033` · 23-feat HGBC + Platt):** `VolTarget12% = 46.9%` × `MetaThrottle = 0.952` $\rightarrow$ **Equity `44.6%` / Cash (`BIL`) `55.4%`** (`VIX = 35.89`, `P(VolOnset_21d)` & `P(TailStress_21d)` calibrated active).
- **Crypto Trend Overlay (`EXP-0041` · `BTC-USD` as of `2026-11-21`):** `Close = $59,958.45` < `SMA(50) = $77,133.24`, `TrendEns(20..120) = 0.00`, `RV21 = 51.06% ann` $\rightarrow$ **BTC Target `0.0%` / Cash (`EFFR`) `100.0%`** (หลบขาลงโดยอัตโนมัติ).
- **Phase C Governance:** Pure directional alpha count = **`0 / 41`** (`EXP-0001..0040, 0042`); `AlinaRiskGovernor.mq5` = `SIG_NONE` / `MODE_PAPER`; Phase D ML & live trading remain **PARKED**.
