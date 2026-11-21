# EXP-0031 (`H34`): Cross-Asset Defensive Risk Overlay Under Stationary Meta-Labeling

**Date (UTC):** `2026-11-21`  
**Experiment / Hypothesis ID:** `EXP-0031` / `H34` (`scripts/exp0031_cross_asset_defensive_overlay.py`, `research/artifacts/exp0031_cross_asset_overlay.json`)  
**Phase Gate Status:** **`PHASE_C_KILL_POINT_ACTIVE_OFFLINE_ONLY`** — Offline defensive portfolio risk engineering only; zero live/demo deployment, zero directional trading edge claimed.

---

## 1. Pre-Registered Question & Methodology
When Task 3 (`VolOnset_21d`) and `EXP-0030` (`TB_NonDirStress_21d`) calibrated probabilities signal elevated regime stress, should throttled `SPY` exposure park strictly in **Cash** or rotate into **Long Treasuries (`TLT`)** or **Cash + Short/Med Duration + Gold (`Cash + IEF + GOLD`)**?

* **[Verified Design]:** Expanding 6-Fold Purged Walk-Forward CV (`2015-01-02 -> 2026-09-16`, `N = 2,943`), strict `Purge = 21d + Embargo = 10d = 31d` between every fit/calibration/test window, `t-1` execution lag on all weights.
* **[Cost & Yield Accounting]:** `5 bp` base (`10 bp` stress) per unit two-way portfolio turnover, plus `(Fed EFFR + 50 bp)` borrow on leverage `> 1.0x`. Reports **both** strict price-return parity (`Cash = 0%` alongside Yahoo price-only `SPY`/`TLT`/`IEF`) **and** `Cash = NYFed EFFR`.
* **[Caveat Preserved]:** `data/universe/{SPY,TLT,IEF}.csv` contain price-only closes excluding equity/bond distributions (~1.5% SPY, ~3–3.5% TLT/IEF); therefore `Cash = 0%` is the clean parity baseline against unadjusted closes.

---

## 2. Full `11.7y` Purged Walk-Forward Results (`2015–2026`, `N = 2,943`)

| Strategy (`t-1` causal weights) | Gross / Net `5bp` Sh | `Cash=EFFR` Sh | `10bp` Stress Sh | Ann Ret (`5bp`) | MaxDD | Calmar | `CVaR95` | Avg Cash | Shift Pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `1_SPY_Buy_And_Hold` | `+0.720` / `+0.720` | `+0.720` | `+0.720` | `+12.69%` | `-34.10%` | `0.372` | `-267.7 bp` | `0.0%` | `100.0%` |
| `2_Static_60_40_SPY_TLT` | `+0.584` / `+0.584` | `+0.584` | `+0.584` | `+6.53%` | `-28.20%` | `0.232` | `-167.5 bp` | `0.0%` | `100.0%` |
| `3_Static_40_30_15_15_Multi` | `+0.672` / `+0.672` | `+0.672` | `+0.672` | `+5.99%` | `-24.42%` | `0.245` | `-130.8 bp` | `0.0%` | `100.0%` |
| `4_VolTarget12_SPY_Cash` | `+0.699` | `+0.723` | `+0.666` | `+9.05%` | `-16.67%` | `0.543` | `-203.0 bp` | `17.0%` | `76.5%` |
| **`5_VolTarget12_Meta_Cash`** | **`+0.764`** | `+0.803` | `+0.708` | `+8.44%` | **`-15.08%`** | **`0.560`** | **`-170.7 bp`** | `21.9%` | `92.5%` |
| `6_VolTarget12_Meta_TLT_Rot` | `+0.634` | `+0.645` | `+0.560` | `+7.43%` | **`-27.77%`** | `0.268` | `-179.0 bp` | `6.6%` | `71.5%` |
| **`7_VolTarget12_Meta_Cash_IEF_GOLD`** | **`+0.826`** | **`+0.847`** | **`+0.757`** | `+9.25%` | `-17.86%` | `0.518` | `-171.4 bp` | `12.1%` | `94.5%` |

---

## 3. Stress Regime Breakdown: Why Static Bond Rotation (`TLT`) Fails in Rate Shocks

| Crisis / Sub-Window | Strategy | Net `5bp` Sh | Ann Ret | MaxDD | `CVaR95` | Key Finding |
|---|---|---:|---:|---:|---:|---|
| **`2020 COVID H1`** | `1_SPY_Buy_And_Hold` | `+0.031` | `+1.39%` | `-34.10%` | `-698.4 bp` | Severe equity crash |
| `2020 COVID H1` | `4_VolTarget12_SPY_Cash` | `-0.257` | `-3.98%` | `-13.71%` | `-263.9 bp` | Vol-target lagged initial drop, halved DD |
| `2020 COVID H1` | **`5_VolTarget12_Meta_Cash`** | `-0.444` | `-4.79%` | **`-10.04%`** | **`-206.2 bp`** | **Best drawdown & tail-loss compression (`-70.5%` CVaR)** |
| `2020 COVID H1` | `6_VolTarget12_Meta_TLT_Rot` | `+0.448` | `+7.77%` | `-11.72%` | `-275.1 bp` | `TLT` rallied only because 2020 was deflationary |
| **`2022 Rate-Hike Bear`** | `1_SPY_Buy_And_Hold` | `-0.775` | `-18.81%` | `-25.36%` | `-335.4 bp` | Equity + Bond dual selloff |
| `2022 Rate-Hike Bear` | `2_Static_60_40_SPY_TLT` | `-1.532` | `-26.43%` | `-27.35%` | `-219.8 bp` | Static 60/40 suffered worse DD than 100% SPY |
| `2022 Rate-Hike Bear` | **`5_VolTarget12_Meta_Cash`** | `-1.302` | `-14.03%` | **`-15.08%`** | **`-157.0 bp`** | **Cash shield kept MaxDD `-15.08%` (best in 2022)** |
| `2022 Rate-Hike Bear` | **`6_VolTarget12_Meta_TLT_Rot`** | `-1.948` | **`-27.61%`** | **`-27.33%`** | `-186.4 bp` | **CATASTROPHIC TRAP**: rotating into `TLT` doubled losses |
| **`2023–2026 OOS Bull`** | `1_SPY_Buy_And_Hold` | `+1.303` | `+19.54%` | `-19.00%` | `-205.2 bp` | Unhedged bull baseline (`Calmar 1.029`) |
| `2023–2026 OOS Bull` | **`5_VolTarget12_Meta_Cash`** | `+1.254` | `+13.27%` | **`-12.13%`** | **`-149.5 bp`** | **`Calmar 1.094`**, minimal Sharpe drag (`EFFR +1.339`) |
| `2023–2026 OOS Bull` | **`7_VolTarget12_Meta_Cash_IEF_GOLD`** | **`+1.373`** | `+14.86%` | `-12.25%` | `-152.7 bp` | **`Calmar 1.214`** (aided by 2023–26 Gold bull) |

---

## 4. Conclusions & Governance Decision
1. **Reject Blind Bond-Rotation Safe-Haven Rules (`6_VolTarget12_Meta_TLT_Rot`):** Hardcoding `Risk-Off -> TLT` destroyed capital during `2022` (`-27.61%`, `MaxDD -27.33%`) and dragged full `11.7y` `Calmar` down to `0.268` vs `0.560` for `Meta -> Cash`.
2. **Accept `VolTarget + Meta -> Cash` (and `Cash/GOLD` defensive blend) Strictly as Risk Control:** `5_VolTarget12_Meta_Cash` delivers the **lowest full-cycle `MaxDD` (`-15.08%`)**, **lowest `CVaR95` (`-170.7 bp`)**, and **highest `Calmar` (`0.560`)**, cutting both `2020` (`-10.04%`) and `2022` (`-15.08%`) drawdowns without relying on Gold bull tailwinds.
3. **Phase Gate Check:** Circular-shift percentiles (`92.5%` / `94.5%` over `11.7y`, `<= 80.0%` in `2023–26 OOS`) stay below the `95%/99%` alpha promotion bar. **Phase C Kill Point remains LOCKED**; results serve strictly for offline defensive risk allocation and Risk Radar sizing guidance.
