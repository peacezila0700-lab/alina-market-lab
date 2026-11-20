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
