# PROJECT RULES — ALINA MARKET LAB

1. **Zero Real Capital / Zero Broker Credentials:** Never send live orders, open real accounts, incur external spend, or store secrets in Markdown, CSV, or public commits.
2. **Evidence Integrity:** Separate `FACT`, `ASSUMPTION`, `HYPOTHESIS`, `RESULT`, and `DECISION`. Every metric in any report must be produced by code on verified workspace/cloud artifacts (`path + SHA-256`). Write `NOT RUN` / `BLOCKED` honestly — never cherry-pick or hide failed experiments.
3. **Zero Look-Ahead & Leakage:** Store internal timestamps in UTC. Never inspect future bars (`t+k` returns, centered windows, same-bar close fills, or future normalization). Signal computed at bar close `t` may execute only at `>= t+1`.
4. **Cost-First Backtesting:** Never report frictionless backtests alone. Charge bar-level measured bid/ask spread (or explicit broker spread + commission + slippage + swap bounds). Passive limit fills require conservative touch (`ask_low <= limit` for buy limit; `bid_high >= limit` for sell limit strictly on bars `> signal_bar`).
5. **Locked OOS & Kill Points:** Lock final 6 months OOS untouched during hypothesis selection. Do NOT advance to ML (`Phase D`) or Demo EA until a rule-based baseline achieves net positive expectancy on locked OOS after full realistic costs.
6. **Cloud Storage & Snapshot Hygiene:** Keep `/home/user` well below `128 MB` (`< 10 MB` preferred) via on-demand `/tmp/alina_lab` cloning, git push, Google Drive pack upload (preserving `v2.12` untouched), and `/tmp/` cleanup before turn end.
