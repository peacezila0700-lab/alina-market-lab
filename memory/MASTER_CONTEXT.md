# MASTER CONTEXT

| field | value |
|---|---|
| Project | ALINA MARKET LAB |
| Owner | Project Owner |
| Agent | Alina (Arena Agent Mode) |
| Status | Track 1 (EA KB Batch 4 / v2.15), Track 2 (KB Blueprint), Track 3 Phases A–C COMPLETE · Phase D ML & Demo EA PARKED (Kill Point enforced) |
| Instrument (LOCKED) | EURGBP primary · EURUSD control (Decision D13 / Plan v1) |
| Timeframe | D1/H1 multi-day research + 23y H1 bid/ask validation |
| Approach (LOCKED) | Honest cost-aware validation across public broker tiers; no live trading until OOS > 0 |
| Money at risk | **ZERO** — `AlinaRiskGovernor.mq5` stays `SIG_NONE`, `MODE_PAPER` |
| Data authority | Dukascopy H1 bid/ask (23y, live `.bi5` cross-verified) + ECB official daily ref (1999–2026) |
| Repo | `github.com/peacezila0700-lab/alina-market-lab` (private) |

## Verified workspace capabilities (2026-11-21)
- Drive: upload / verify / list / trash active (`ALINA_DATAPACK_v2.15.zip`, `v2.12` preserved)
- GitHub: push via PAT + temporary `GIT_ASKPASS` verified
- Python 3.13: numpy, pandas, scipy, scikit-learn, sqlite3+FTS5, lzma/bi5 decoder, 17/17 unit tests passing
- Sandbox constraint: `mql5.com/en/code/download/...` returns HTTP 403/IP block (`201` archives) — covered cleanly by standalone `scripts/fetch_mql5_non_sandbox.py`
- Public multi-broker cost models (`configs/broker_cost_models.json`): Dukascopy Measured, IC Markets Raw ECN, Exness Raw, Exness Standard + `[0.0, 0.35]` pip/night swap sensitivity

## Known constraints & hard truths
- 25 pre-registered experiments (incl. `EXP-0024`/`EXP-0025` across 23y Dukascopy EURGBP & EURUSD), 168 screen tests, 144 free-EA family tests -> **0 validated directional edges**.
- EURGBP H1 ATR ≈ 5.9 pips -> H1 scalping loses `-3.35` to `-5.86` pips/trade across all brokers (`D02` empirically confirmed).
- Passive limit orders reduce execution drag (`+0.78` pips/trade vs market on 23y EURGBP), yet underlying mean-reversion signal remains negative net of costs (`-1.41` to `-2.24` pips ALL).
