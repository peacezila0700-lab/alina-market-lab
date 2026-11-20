# ALINA DATAPACK v1 — สรุปภาษาไทย

## นี่คืออะไร
ชุดข้อมูล + โค้ด + ผลทดลอง สำหรับให้ AI ตัวอื่น (หรือเราในอนาคต) ดึงไปใช้ต่อ **โดยไม่ต้องไปงมหา
ข้อมูลใหม่ทางเน็ต** และไม่ต้องเสีย token คิดสิ่งที่เราทดสอบจนรู้ผลแล้ว

## มีอะไรข้างใน
| หมวด | ไฟล์ | สาระ |
|---|---|---|
| ราคา FX ทางการ | `data/fx_official_ecb_daily` | ECB 10 คู่ 1999–2026 (71,410 แถว) — ใช้ตัวนี้ ไม่ใช่ Yahoo |
| ราคาสินทรัพย์ 24 ตัว | `data/universe_daily_etf` | หุ้น/ทอง/น้ำมัน/คริปโต/บอนด์ (160,363 แถว) |
| **ใครถือโพซิชัน** | `data/cot_weekly_cftc` | CFTC COT รายสัปดาห์ 1986–2026, 24 สัญญา (35,936 แถว) — เจ้ามือ/กองทุน/รายย่อย |
| ฟีเจอร์ COT สำเร็จรูป | `data/cot_features_derived` | z-score + percentile 3 ปี + การเปลี่ยนแปลง 4 สัปดาห์ พร้อมใช้ |
| ความกลัว/หางความเสี่ยง | `data/vix_cboe_daily`, `data/skew_cboe_daily` | VIX + SKEW ตั้งแต่ 1990 |
| ต้นทุนจริง | `data/spreads_measured_dukascopy` | สเปรด bid/ask ที่วัดจริง 10 คู่ (ตัวที่ทำให้ verdict พลิก) |
| ปฏิทิน | `data/fomc_decision_dates`, `data/econ_calendar_archive` | วันประชุม Fed 205 วัน / ปฏิทินเศรษฐกิจ (เริ่มสะสม 2026-11) |
| ความสนใจสาธารณะ | `data/attention_wikipedia_pageviews` | pageviews 8 สินทรัพย์ 2016–2026 |
| ระบบนิเวศ EA ฟรี | `data/free_ea_catalog` | 332 แหล่ง + ผลทดสอบ 144 แบบ (ไม่มีตัวไหนชนะ null) |
| ผลทดลองทั้งหมด | `results/experiments.jsonl` | 8 การทดลอง + verdict + ตัวเลข |
| **DIX/GEX** | `data/dix_gex` | dark-pool flow + dealer gamma รายวัน 2011–2026 |
| **ความเครียดระบบการเงิน** | `data/ofr_financial_stress` | OFR FSI + 5 sub-index (credit/funding/vol) 2000–2026 |
| **ความเสี่ยงนโยบาย/ภูมิรัฐศาสตร์** | `data/policy_geopolitical_risk` | EPU + GPR รายเดือน ตั้งแต่ 1900 |
| **ซัพพลายจริง** | `data/physical_supply_eia` | สต็อกน้ำมันรายสัปดาห์ 1982– / Henry Hub 1997– |
| **โพซิชันคริปโต** | `data/crypto_positioning_flows` | funding rate + long/short ratio (OKX) |
| **ราคา options คริปโต** | `data/deribit_btc_options` | IV surface + term structure (Deribit) |
| **ความน่าจะเป็นพื้นฐาน** | `data/base_rates_conditional` | VIX/DIX/GEX/FSI → ผลตอบแทน SPY 5/21/63/252 วัน (96 แถว) |
| **แผนที่ปัจจัยตัดสินใจ** | `knowledge/DECISION_INPUTS_ATLAS.md` | 12 ชั้นข้อมูลที่นักวิเคราะห์ใช้ + หลักความน่าจะเป็น |
| **สิ่งที่บอทยังขาด** | `knowledge/WHAT_THE_BOT_NEEDS.md` | ช่องว่าง 7 ข้อ + backlog จัดอันดับตาม prior |
| **ฐานข้อมูลเหตุการณ์** | `data/event_reaction_db` | 2,028 เหตุการณ์ (FOMC/ประมูลพันธบัตร/OPEX/VIX แตะ 30/วันผันผวน >2.5σ) + สถิติการตอบสนองที่วัดจริง |
| **ที่เก็บข้อมูลรายวัน** | `data/collector_store` | 16 แหล่งดึงทุกวันตั้งแต่ 2026-11-20 — ส่วนที่กูเกิลย้อนหลังไม่ได้ |
| องค์ความรู้ | `knowledge/*.md` | แหล่งข้อมูลที่ยังใช้ได้/ตายแล้ว, กับดัก, สิ่งที่ล้มเหลว, ไอเดียที่ยังไม่ได้ทดสอบพร้อม "ความน่าจะเป็น" |
| โค้ด | `code/` | สคริปต์ทั้งหมด + EA (AlinaRiskGovernor.mq5) |

## อ่านยังไงให้เร็วที่สุด (สำหรับ AI)
1. `catalog.json` — schema, จำนวนแถว, ช่วงเวลา, sha256, ตัวอย่าง 2 แถว, ข้อควรระวัง, กติกา look-ahead
2. `results/experiments.jsonl` — เช็คก่อนว่าความคิดที่จะทดสอบ "ตายไปแล้วหรือยัง"
3. `knowledge/PITFALLS.md` — 3 บั๊กที่ทำให้เห็น edge ปลอม
4. `knowledge/IDEAS_TO_TEST.md` — ไอเดียที่ยังไม่ได้ลอง พร้อม prior probability

## ความจริงที่ต้องพูดตรง ๆ
ทดสอบไปแล้ว 8 การทดลอง + 320 การทดสอบย่อย → **ยังไม่พบ edge ที่ผ่านการทดสอบจริง**
ตัวเลข Sharpe สวย ๆ ทั้งหมดในชุดนี้เคยถูกหักล้างด้วย (ก) ต้นทุนจริง (ข) ข้อมูล hold-out (ค) การสุ่มเทียบ
สิ่งที่ยังเหลือคือ "ข้อมูลใหม่ + ไอเดียใหม่" ไม่ใช่การขัดของเก่าให้เงา

## อัปเดตยังไง
`python3 code/scripts/fetch_cot.py` (COT), `fetch_universe.py`, `fetch_official.py`,
`measure_spreads.py`, `fetch_events.py` แล้วรัน `build_datapack.py` เพื่อประกอบชุดใหม่


---

## อัปเดต v2.1 (2026-11-20)

- **ไฟล์ที่ควรอ่านก่อนทุกอย่าง: `briefs/latest.md`** — สรุปสถานะตลาดทั้งวัน (VIX, GEX, DIX, ระดับรับส่ง, ข่าว, ปฏิทิน 7 วัน) เหลือ ~1.5k token
- **`knowledge/OPERATING_MANUAL.md`** — วิธีรันจริงทุกวัน (cron 3 บรรทัด) + ตาราง "ของที่ล้มแล้ว อย่าทำซ้ำ"
- เพิ่ม dataset: `news_headlines` (294 ข่าว/15 สำนัก), `levels_support_resistance` (28 เครื่องมือ), `broad_cross_section` (68 ETF, 5 กลุ่ม), `daily_briefs`
- ทดลองใหม่ 3 ตัว รอบนี้ **ล้มทั้งหมด**:
  - EXP-0010 เหตุการณ์ (FOMC/OPEX/สิ้นเดือน/VIX ทะลุ 30) ไม่เปลี่ยน *ทิศ* ของราคา 5 วัน เปลี่ยนแค่ *ความผันผวน*
  - EXP-0011 อุปสงค์ประมูลพันธบัตร (bid-to-cover, dealer share) ทำนาย TLT/IEF/SPY ไม่ได้
  - EXP-0012 โมเมนตัม 12-1 / reversal 1 เดือน / 5 วัน บน 68 ETF ไม่มีตัวไหนชนะ null ที่ turnover เท่ากัน
- บทเรียนสำคัญ: null ที่สลับหุ้นทุกสัปดาห์จะ "ปลอม" ให้ทุกอย่างดูเก่ง เพราะจ่ายค่าคอมทิ้ง — ต้องใช้ null ที่สลับครั้งเดียวทั้งช่วง (เขียนไว้ใน PITFALLS ข้อ 11–12)
- สรุป: **12 การทดลอง, 0 edge ที่ผ่านการตรวจ** — ชุดข้อมูลสะอาด งานต่อไปคือหาข้อมูล/ไอเดียใหม่ ไม่ใช่ปรับของเก่าให้สวย

### ปิดท้ายรอบเดียวกัน (EXP-0013, EXP-0014)
- ทดสอบ overlay ปรับขนาดโพซิชันด้วย "สภาวะตลาด" 7 แบบ (breadth, เครดิต, VIX, การกระจายตัว, dealer gamma) กับ SPY
  → **ล้มทั้งหมด** ยกเว้น gamma ที่ชนะ null ครบ 200/200 ใน-sample แต่ OOS อยู่แค่เปอร์เซ็นไทล์ 90
- จึงทดสอบซ้ำแบบเข้มงวด: gamma ชนะ "การปรับขนาดตามความผันผวน" (vol targeting) จริงไหม
  → **ไม่จริง** (Δ Sharpe +0.067 ใน-sample, +0.041 OOS = อยู่ในช่วง noise)
- บทสรุปที่ใช้ได้จริง: ตัวแปรสภาวะตลาด **ลด drawdown ได้** (gamma overlay -27% เทียบ buy&hold -51%)
  แต่ **ไม่เพิ่มผลตอบแทน** → ใช้จัดขนาดโพซิชัน ไม่ใช่หาทิศทาง
