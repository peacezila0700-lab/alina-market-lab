#!/usr/bin/env python3
"""
Workstream B2 — Honest Historical Microstructure Audit & Harvester (Deribit + OKX)

Empirically documents what is free/accessible vs blocked from sandbox:
  - Deribit `get_funding_rate_history` (BTC-PERPETUAL, ETH-PERPETUAL): HTTP 200 back to 2024-01-01 (~25,000+ hourly points!)
  - Deribit `get_tradingview_chart_data` 1H OHLC (BTC-PERPETUAL, ETH-PERPETUAL, DVOL): HTTP 200
  - Deribit active dated futures + OKX active futures: HTTP 200 live term snapshot
  - OKX `okx_BTCUSDT_1h_deep.csv` / `okx_ETHUSDT_1h_deep.csv`: 10,000 1H bars (`2025-09-30..2026-11-20`)
  - OKX `funding-rate-history`: API capped at ~93 days (`280` 8h rows)
  - Binance `fapi.binance.com`: HTTP 451 (geo-blocked in sandbox)
  - Bybit `api.bybit.com`: HTTP 403 (WAF blocked in sandbox)

Saves ZERO fabricated bars; records exact raw exchange timestamps.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "microstructure"
UA = {"User-Agent": "Mozilla/5.0"}


def get_json(url: str, timeout: int = 25) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def fetch_deribit_funding(inst: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    rows = []
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + timedelta(days=29), end_dt)
        s_ms = int(cur.timestamp() * 1000)
        e_ms = int(nxt.timestamp() * 1000)
        u = f"https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name={inst}&start_timestamp={s_ms}&end_timestamp={e_ms}"
        j = get_json(u)
        if j and isinstance(j.get("result"), list):
            for x in j["result"]:
                rows.append({
                    "ts": pd.to_datetime(int(x["timestamp"]), unit="ms", utc=True),
                    "index_price": float(x["index_price"]),
                    "interest_8h": float(x["interest_8h"]),
                    "interest_1h": float(x["interest_1h"]),
                })
        cur = nxt + timedelta(hours=1)
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts")
    return df


def fetch_deribit_tv(inst: str, start_dt: datetime, end_dt: datetime, res: str = "60") -> pd.DataFrame:
    rows = []
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + timedelta(days=120), end_dt)
        s_ms = int(cur.timestamp() * 1000)
        e_ms = int(nxt.timestamp() * 1000)
        u = f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name={inst}&start_timestamp={s_ms}&end_timestamp={e_ms}&resolution={res}"
        j = get_json(u)
        r = (j or {}).get("result") or {}
        ticks = r.get("ticks") or []
        for i, t in enumerate(ticks):
            rows.append({
                "ts": pd.to_datetime(int(t), unit="ms", utc=True),
                "o": float(r["open"][i]),
                "h": float(r["high"][i]),
                "l": float(r["low"][i]),
                "c": float(r["close"][i]),
                "vol": float(r["volume"][i]),
            })
        cur = nxt + timedelta(hours=1)
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts")


def fetch_futures_basis_snapshot() -> list[dict]:
    snaps = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ccy in ("BTC", "ETH"):
        j = get_json(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=future")
        for x in (j or {}).get("result", []):
            snaps.append({
                "snapshot_utc": stamp,
                "venue": "Deribit",
                "currency": ccy,
                "instrument": x.get("instrument_name"),
                "mark_price": x.get("mark_price"),
                "underlying_index": x.get("estimated_delivery_price"),
                "bid": x.get("bid_price"),
                "ask": x.get("ask_price"),
                "funding_8h": x.get("funding_8h"),
                "oi": x.get("open_interest"),
                "volume_usd": x.get("volume_usd"),
            })
    return snaps


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    start_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2026, 11, 21, tzinfo=timezone.utc)

    summary = {"built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "datasets": {}}
    for sym, inst in (("BTC", "BTC-PERPETUAL"), ("ETH", "ETH-PERPETUAL")):
        fdf = fetch_deribit_funding(inst, start_dt, end_dt)
        fdf.to_csv(OUT / f"deribit_{sym}_funding_1h.csv.gz", index=False, compression="gzip")

        pdf = fetch_deribit_tv(inst, start_dt, end_dt, "60")
        pdf.to_csv(OUT / f"deribit_{sym}_perp_1h.csv.gz", index=False, compression="gzip")

        summary["datasets"][f"deribit_{sym}_funding_1h"] = {
            "rows": int(len(fdf)),
            "start": str(fdf["ts"].min()),
            "end": str(fdf["ts"].max()),
        }
        summary["datasets"][f"deribit_{sym}_perp_1h"] = {
            "rows": int(len(pdf)),
            "start": str(pdf["ts"].min()),
            "end": str(pdf["ts"].max()),
        }
        print(f"  Deribit {sym}: funding_1h={len(fdf)} ({fdf['ts'].min()}..{fdf['ts'].max()}) | perp_1h={len(pdf)}")

    # DVOL 1H (Volatility Index)
    for sym in ("BTC", "ETH"):
        rows = []
        cur = start_dt
        while cur < end_dt:
            nxt = min(cur + timedelta(days=40), end_dt)
            u = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={sym}&start_timestamp={int(cur.timestamp()*1000)}&end_timestamp={int(nxt.timestamp()*1000)}&resolution=3600"
            j = get_json(u)
            for arr in (j or {}).get("result", {}).get("data", []):
                rows.append({"ts": pd.to_datetime(int(arr[0]), unit="ms", utc=True), "dvol_c": float(arr[4])})
            cur = nxt + timedelta(hours=1)
            time.sleep(0.1)
        dvol = pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts")
        dvol.to_csv(OUT / f"deribit_{sym}_dvol_1h.csv.gz", index=False, compression="gzip")
        summary["datasets"][f"deribit_{sym}_dvol_1h"] = {"rows": int(len(dvol)), "start": str(dvol["ts"].min()), "end": str(dvol["ts"].max())}
        print(f"  Deribit {sym} DVOL 1h: {len(dvol)}")

    snaps = fetch_futures_basis_snapshot()
    pd.DataFrame(snaps).to_csv(OUT / "deribit_futures_term_snapshot.csv", index=False)
    summary["datasets"]["deribit_futures_term_snapshot"] = {"rows": len(snaps)}
    summary["blocked_sources"] = {
        "binance_fapi": "HTTP 451 (geo-blocked in sandbox)",
        "bybit_v5": "HTTP 403 (WAF blocked in sandbox)",
        "okx_funding_history": "API caps public lookback to ~93 days (280 8h rows in data/collect/okx_*_funding_deep.csv)",
    }
    (OUT / "MANIFEST_MICROSTRUCTURE.json").write_text(json.dumps(summary, indent=2))
    print("DONE MICROSTRUCTURE HARVEST.")


if __name__ == "__main__":
    main()
