#!/usr/bin/env python3
"""B3 — DAILY COLLECTOR. Turns one-off snapshots into accumulating history.

Why this is the highest-value piece of engineering in the project: half of the interesting data
(option chains, funding rates, dealer gamma, calendars) is published *only* as the latest value.
Nobody can download its history later — you get it by being there every day. This script is that
"being there": it is idempotent, appends with de-duplication, and records what worked in a log so a
downstream AI can see the collection's own reliability.

Run:  python3 scripts/collect_daily.py           (safe to run many times a day)
Cron: 30 22 * * *  cd /path/to/alina_lab && python3 scripts/collect_daily.py >> data/collect/collector.log 2>&1

Everything is free and key-less. Each function is independent: one failure never blocks the rest.
"""
from __future__ import annotations

import io
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "collect")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
LOG: list[dict] = []


def get(url: str, timeout: int = 40) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                                    # noqa: BLE001
            time.sleep(1.5)
            err = e
    print(f"    GET failed: {err}")
    return None


def upsert(name: str, df: pd.DataFrame, keys: list[str], mode: str = "append") -> int:
    """Append with de-duplication on `keys`; mode='replace' for sources that republish full history."""
    path = os.path.join(OUT, f"{name}.csv")
    df = df.copy()
    df["_collected_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if mode == "replace" or not os.path.exists(path):
        df.drop_duplicates(subset=keys, keep="last").to_csv(path, index=False)
        return len(df)
    old = pd.read_csv(path)
    merged = pd.concat([old, df], ignore_index=True)
    merged = merged.drop_duplicates(subset=keys, keep="last")
    merged.to_csv(path, index=False)
    return len(merged) - len(old)


def rec(name: str, added: int) -> None:
    LOG.append({"source": name, "added_rows": added,
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    print(f"  {name:26} +{added} rows")


# ------------------------------------------------------------------ sources
def c_dix_gex() -> None:
    raw = get("https://squeezemetrics.com/monitor/static/DIX.csv")
    if not raw:
        return rec("dix_gex", -1)
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip().lower() for c in df.columns]
    rec("dix_gex", upsert("dix_gex", df, ["date"], mode="replace"))


def c_ofr_fsi() -> None:
    raw = get("https://www.financialresearch.gov/financial-stress-index/data/fsi.csv")
    if not raw:
        return rec("ofr_fsi", -1)
    rec("ofr_fsi", upsert("ofr_fsi", pd.read_csv(io.BytesIO(raw)), ["Date"], mode="replace"))


def c_vix_skew() -> None:
    for name, url in (("vix", "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"),
                      ("skew", "https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv")):
        raw = get(url)
        if raw:
            rec(name, upsert(name, pd.read_csv(io.BytesIO(raw)), ["DATE"], mode="replace"))


def c_okx() -> None:
    raw = get("https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100")
    if raw:
        d = pd.DataFrame(json.loads(raw).get("data", []))
        if not d.empty:
            d["ts"] = pd.to_datetime(d.fundingTime.astype("int64"), unit="ms", utc=True)
            d["fundingRate"] = d.fundingRate.astype(float)
            rec("okx_btc_funding", upsert("okx_btc_funding", d[["ts", "fundingRate"]], ["ts"]))
    raw = get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D")
    if raw:
        d = pd.DataFrame(json.loads(raw).get("data", []), columns=["ts_ms", "long_short_ratio"])
        if not d.empty:
            d["date"] = pd.to_datetime(d.ts_ms.astype("int64"), unit="ms", utc=True)
            d["long_short_ratio"] = d.long_short_ratio.astype(float)
            rec("okx_btc_lsr", upsert("okx_btc_lsr", d[["date", "long_short_ratio"]], ["date"]))


def c_deribit() -> None:
    raw = get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option")
    if not raw:
        return rec("deribit_btc_chain", -1)
    res = json.loads(raw).get("result", [])
    rows = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in res:
        p = r.get("instrument_name", "").split("-")
        if len(p) != 4:
            continue
        try:
            rows.append({"snapshot_utc": stamp, "expiry": p[1], "strike": float(p[2]), "kind": p[3].lower(),
                         "iv_pct": float(r.get("mark_iv") or 0), "oi": float(r.get("open_interest") or 0),
                         "volume": float(r.get("volume") or 0),
                         "underlying": float(r.get("underlying_price") or 0)})
        except (TypeError, ValueError):
            continue
    if rows:
        df = pd.DataFrame(rows)
        rec("deribit_btc_chain", upsert("deribit_btc_chain", df, ["snapshot_utc", "expiry", "strike", "kind"]))


def c_calendar() -> None:
    for fmt, url in (("xml", "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"),
                     ("xml", "https://nfs.faireconomy.media/ff_calendar_nextweek.xml")):
        raw = get(url)
        if not raw:
            continue
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw)
            rows = [{c.tag: (c.text or "") for c in ev} for ev in root.findall("event")]
            if rows:
                df = pd.DataFrame(rows)
                df["collected"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                key = [c for c in ("date", "time", "title", "country") if c in df.columns]
                rec("econ_calendar", upsert("econ_calendar", df, key))
        except Exception as e:                                    # noqa: BLE001
            print(f"    calendar parse: {e}")


def c_eia() -> None:
    for name, url in (("eia_crude_stocks_w", "https://www.eia.gov/dnav/pet/hist_xls/WCRSTUS1w.xls"),
                      ("eia_henryhub_w", "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDw.xls")):
        raw = get(url)
        if not raw:
            rec(name, -1)
            continue
        try:
            xl = pd.ExcelFile(io.BytesIO(raw), engine="xlrd")
            sheet = [s for s in xl.sheet_names if "Data" in s][0]
            df = pd.read_excel(xl, sheet_name=sheet, header=2)
            df.columns = ["date", "value"] + list(df.columns[2:])
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date", "value"])[["date", "value"]]
            rec(name, upsert(name, df, ["date"], mode="replace"))
        except Exception as e:                                    # noqa: BLE001
            print(f"    {name}: {e}")


def c_epu_gpr() -> None:
    raw = get("https://www.policyuncertainty.com/media/US_Historical_EPU_data.xlsx")
    if raw:
        try:
            xl = pd.ExcelFile(io.BytesIO(raw))
            sheet = "US Historical EPU Data" if "US Historical EPU Data" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(xl, sheet_name=sheet)
            rec("epu_us_monthly", upsert("epu_us_monthly", df.iloc[:, :4], ["Year", "Month"], mode="replace"))
        except Exception as e:                                    # noqa: BLE001
            print(f"    epu: {e}")
    raw = get("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls")
    if raw:
        try:
            df = pd.read_excel(io.BytesIO(raw))
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            rec("gpr_monthly", upsert("gpr_monthly", df, ["month"], mode="replace"))
        except Exception as e:                                    # noqa: BLE001
            print(f"    gpr: {e}")


def c_treasury() -> None:
    base = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
            "?fields=auction_date,security_type,security_term,bid_to_cover_ratio,high_yield,offering_amt"
            "&sort=-auction_date&page%5Bsize%5D=200&page%5Bnumber%5D=1")
    raw = get(base)
    if raw:
        d = pd.DataFrame(json.loads(raw).get("data", []))
        if not d.empty:
            rec("treasury_auctions", upsert("treasury_auctions", d,
                                            ["auction_date", "security_type", "security_term"]))
    yc = get("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
             f"{datetime.now().year}/all?type=daily_treasury_yield_curve&"
             f"field_tdr_date_value={datetime.now().year}&_format=csv")
    if yc:
        df = pd.read_csv(io.BytesIO(yc))
        rec("treasury_yield_curve", upsert("treasury_yield_curve", df, ["Date"], mode="replace"))


def c_macro_intraday() -> None:
    """Crypto 1H candles: the only genuinely free intraday series with deep history and 24/7 cover."""
    for inst in ("BTC-USDT", "ETH-USDT"):
        rows, after = [], ""
        for _ in range(6):
            url = (f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar=1H&limit=100"
                   + (f"&after={after}" if after else ""))
            raw = get(url, timeout=25)
            if not raw:
                break
            d = json.loads(raw).get("data", [])
            if not d:
                break
            rows += d
            after = d[-1][0]
            time.sleep(0.2)
        if rows:
            df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "vol", "volc", "volq", "confirm"])
            df["ts"] = pd.to_datetime(df.ts.astype("int64"), unit="ms", utc=True)
            for c in ("o", "h", "l", "c", "vol"):
                df[c] = df[c].astype(float)
            rec(f"okx_{inst.replace('-', '')}_1h",
                upsert(f"okx_{inst.replace('-', '')}_1h", df[["ts", "o", "h", "l", "c", "vol"]], ["ts"]))


def c_downstream() -> None:
    """After the raw sources: refresh the derived layers a local AI actually reads."""
    import subprocess
    for script in ("scripts/fetch_vol_term.py", "scripts/fetch_news.py", "scripts/build_levels.py",
                   "scripts/build_event_db.py", "scripts/build_vol_regimes.py", "scripts/daily_brief.py"):
        p = os.path.join(ROOT, script)
        if not os.path.exists(p):
            continue
        try:
            r = subprocess.run(["python3", p], capture_output=True, text=True, timeout=600)
            tail = (r.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
            print(f"  {script:28} {tail[0][:90]}")
            LOG.append({"source": script, "added_rows": 0 if r.returncode == 0 else -1,
                        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        except Exception as e:                                    # noqa: BLE001
            print(f"  {script}: {e}")
            LOG.append({"source": script, "added_rows": -2,
                        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


def main() -> None:
    print(f"collector run {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    for fn in (c_dix_gex, c_ofr_fsi, c_vix_skew, c_okx, c_deribit, c_calendar, c_eia, c_epu_gpr,
               c_treasury, c_macro_intraday, c_downstream):
        try:
            fn()
        except Exception as e:                                    # noqa: BLE001
            print(f"  {fn.__name__} EXCEPTION {e}")
            rec(fn.__name__, -2)
    log_path = os.path.join(OUT, "collector_log.jsonl")
    with open(log_path, "a") as f:
        for r in LOG:
            f.write(json.dumps(r) + "\n")
    ok = sum(1 for r in LOG if r["added_rows"] >= 0)
    print(f"\n{ok}/{len(LOG)} sources ok → data/collect/  (log appended)")


if __name__ == "__main__":
    main()
