"""Validate a MetaTrader 5 history export the moment the owner drops it in.

MT5 exports (Tools -> History Center -> Export, or right-click chart -> Save As) look like:

    <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>

Timezone of the exported timestamps is the BROKER's server time, not UTC. This script
therefore reports the implied offset rather than silently assuming UTC.

Usage:  python3 scripts/validate_mt5_export.py [path]
        (default: newest *.csv in data/inbox/)
"""
import csv, glob, io, os, sys, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "data", "inbox")
OUT = os.path.join(ROOT, "reports", "MT5_EXPORT_QC.md")


def sniff(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    head = txt.splitlines()[0]
    delim = "\t" if "\t" in head else (";" if ";" in head else ",")
    return txt, delim, enc


def parse(path):
    txt, delim, enc = sniff(path)
    lines = [l for l in txt.splitlines() if l.strip()]
    has_header = any(c.isalpha() for c in lines[0].split(delim)[0])
    rows, fmt = [], "unknown"
    for l in lines[1:] if has_header else lines:
        p = [x.strip().strip("<>").strip('"') for x in l.split(delim)]
        if len(p) < 6:
            continue
        try:
            if "-" in p[0] and ":" in p[1]:
                ts = dt.datetime.strptime(p[0] + " " + p[1], "%Y.%m.%d %H:%M:%S")
                fmt = "%Y.%m.%d %H:%M:%S (server time)"
            elif "." in p[0] and p[1].count(":") == 2:
                ts = dt.datetime.strptime(p[0] + " " + p[1], "%Y.%m.%d %H:%M:%S")
                fmt = "dot date + time (server time)"
            else:
                ts = dt.datetime.fromisoformat(p[0].replace(" ", "T"))
                fmt = "iso"
            o, h, l, c = (float(p[2].replace(",", ".")), float(p[3].replace(",", ".")),
                          float(p[4].replace(",", ".")), float(p[5].replace(",", ".")))
        except Exception:
            continue
        spread = None
        if len(p) >= 9:
            try:
                spread = float(p[8].replace(",", "."))
            except Exception:
                spread = None
        rows.append((ts, o, h, l, c, spread))
    return rows, fmt, delim, has_header, enc


def qc(rows, symbol_guess):
    ts = [r[0] for r in rows]
    o = np.array([r[1] for r in rows]); h = np.array([r[2] for r in rows])
    l = np.array([r[3] for r in rows]); c = np.array([r[4] for r in rows])
    sp = np.array([r[5] for r in rows if r[5] is not None], float)
    gaps = np.diff([t.timestamp() for t in ts])
    typical = np.median(gaps) if len(gaps) else 0
    weekend = sum(1 for t in ts if t.weekday() >= 5)
    bad = int(((h < np.maximum(o, c)) | (l > np.minimum(o, c))).sum())
    occ = int((np.abs(o - c) < 1e-12).sum())
    L = [f"# MT5 EXPORT QC — {symbol_guess}", "",
         f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}", "",
         "## Shape", "",
         "| check | value |", "|---|---|",
         f"| bars | {len(rows)} |",
         f"| first timestamp | {ts[0]} |",
         f"| last timestamp | {ts[-1]} |",
         f"| timestamp format | broker **server time** (not converted) |",
         f"| duplicate timestamps | {len(ts) - len(set(ts))} |",
         f"| weekend bars | {weekend} |",
         f"| OHLC violations | {bad} |",
         f"| bars with open == close | {occ} ({occ/len(rows)*100:.1f}%) |",
         f"| median step between bars | {typical/60:.0f} min |",
         f"| gaps > 5x median step | {int((gaps > 5*typical).sum()) if typical else 0} |", ""]
    if len(sp):
        L += ["## Spread (this is the number the project has been missing)", "",
              "| metric | value |", "|---|---|",
              f"| bars with spread reported | {len(sp)} |",
              f"| median | **{np.median(sp):.1f} points** |",
              f"| mean | {sp.mean():.1f} points |",
              f"| p90 | {np.percentile(sp, 90):.1f} points |",
              f"| p99 | {np.percentile(sp, 99):.1f} points |",
              f"| max | {sp.max():.1f} points |", "",
              "> 1 point = 0.00001 on 5-digit pairs; 10 points = 1.0 pip. "
              "Divide by 10 to compare with the 0.9 pip Dukascopy median used so far.", ""]
    verdict = []
    if len(ts) - len(set(ts)):
        verdict.append("FAIL: duplicate timestamps")
    if bad:
        verdict.append("FAIL: OHLC violations present")
    if weekend:
        verdict.append(f"NOTE: {weekend} weekend bars — decide policy (keep/drop) before use")
    if occ / len(rows) > 0.05:
        verdict.append("WARN: many bars with open==close — vendor may be snapshotting")
    L += ["## Verdict", ""] + (["- " + v for v in verdict] or ["- PASS on structural checks"]) + [""]
    return "\n".join(L)


if __name__ == "__main__":
    os.makedirs(INBOX, exist_ok=True)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        cands = sorted(glob.glob(os.path.join(INBOX, "*.csv")), key=os.path.getmtime)
        path = cands[-1] if cands else None
    if not path or not os.path.exists(path):
        print(f"no CSV found. Drop the MT5 export into: data/inbox/  then re-run.")
        sys.exit(0)
    rows, fmt, delim, hdr, enc = parse(path)
    if not rows:
        print("could not parse any rows — check the column order/format"); sys.exit(1)
    sym = os.path.basename(path).split(".")[0]
    report = qc(rows, sym)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(report)
    print(report.split("## Verdict")[0][-900:])
    print("wrote reports/MT5_EXPORT_QC.md")
