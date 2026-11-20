"""Build canonical D1 datasets from raw vendor files.

Cleaning rules (all logged, nothing silent):
  R1 fix Sunday-labeled bars     — Yahoo labels the Friday session as Sunday in
                                   294 of 522 weeks (Friday absent, Sunday present;
                                   |r| Thu->Sun = 32.1 pips vs Thu->Fri = 35.5 pips on
                                   real Fridays, so the bar carries Friday's move).
                                   Rule: if the week has no Friday bar, relabel the
                                   Sunday bar to Friday. If a Friday bar already
                                   exists, the Sunday bar is a duplicate stub -> drop.
  R2 clamp OHLC inconsistency    — vendor rows where close/open sit outside [low,high]
                                   by a fraction of a pip; high:=max(o,h,c), low:=min(o,l,c)
  R3 drop isolated bad prints   — a close that deviates >5% from BOTH neighbours while
                                   those neighbours agree within 1% = vendor bad print
                                   (observed: EURGBP 0.97900 on 2022-10-07 between
                                   0.8766 and 0.8765, which fabricated two ±11% moves
                                   and pushed kurtosis to 173). Bar is dropped, not repaired.
  R4 no forward fill             — missing weekdays stay missing (holidays, no data)

Outputs: data/processed/{SYM}_D1_clean.csv + CLEANING_LOG.csv
"""
import csv, os, json, hashlib, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")

log = [["symbol", "date", "rule", "detail"]]


def clean(name):
    rows = list(csv.DictReader(open(os.path.join(P, name))))
    kept, dropped_sun, clamped, relabeled, dropped_spike = [], 0, 0, 0, 0
    have_friday = {dt.date.fromisoformat(r["ts_utc"][:10])
                   for r in rows
                   if dt.date.fromisoformat(r["ts_utc"][:10]).weekday() == 4}
    for r in rows:
        date = dt.date.fromisoformat(r["ts_utc"][:10])
        o, h, l, c = (float(r["open"]), float(r["high"]),
                      float(r["low"]), float(r["close"]))
        if date.weekday() == 6:
            fri = date - dt.timedelta(days=2)
            if fri in have_friday:
                dropped_sun += 1
                log.append([name, str(date), "R1_drop_duplicate_sunday", f"close={c:.5f}"])
                continue
            date = fri                       # relabel: this bar is Friday's session
            relabeled += 1
            log.append([name, str(date), "R1_relabel_sunday_to_friday", f"close={c:.5f}"])
        hi2, lo2 = max(h, o, c), min(l, o, c)
        if (hi2, lo2) != (h, l):
            clamped += 1
            log.append([name, str(date), "R2_clamp_ohlc",
                        f"high {h:.5f}->{hi2:.5f} low {l:.5f}->{lo2:.5f}"])
            h, l = hi2, lo2
        kept.append([f"{date.isoformat()} 00:00:00", round(o, 6), round(h, 6),
                     round(l, 6), round(c, 6)])
    kept.sort(key=lambda x: x[0])
    # R3 isolated bad prints (needs neighbours, so run after sorting)
    filt = []
    for i, row in enumerate(kept):
        if 0 < i < len(kept) - 1:
            c0, c1, c2 = float(kept[i-1][4]), float(row[4]), float(kept[i+1][4])
            if (abs(c1/c0 - 1) > 0.05 and abs(c1/c2 - 1) > 0.05
                    and abs(c2/c0 - 1) < 0.01):
                dropped_spike += 1
                log.append([name, row[0][:10], "R3_drop_isolated_spike",
                            f"close={c1:.5f} between {c0:.5f} and {c2:.5f}"])
                continue
        filt.append(row)
    kept = filt
    out = os.path.join(P, name.replace(".csv", "_clean.csv"))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_utc", "open", "high", "low", "close"])
        w.writerows(kept)
    return len(rows), len(kept), dropped_sun, relabeled, clamped, dropped_spike, out


if __name__ == "__main__":
    summary = []
    for n in ["EURGBP_D1.csv", "EURUSD_D1.csv"]:
        n_in, n_out, sun, relab, clamp, spike, out = clean(n)
        summary.append((n, n_in, n_out, sun, relab, clamp, spike, out))
    with open(os.path.join(P, "CLEANING_LOG.csv"), "w", newline="") as f:
        csv.writer(f).writerows(log)
    mpath = os.path.join(P, "MANIFEST.json")
    m = json.load(open(mpath))
    for n, n_in, n_out, sun, relab, clamp, spike, out in summary:
        m["datasets"].append({
            "id": n.replace(".csv", "_clean"),
            "derived_from": n,
            "transformations": [f"R1_relabel_sunday_to_friday(n={relab})",
                                f"R1_drop_duplicate_sunday(n={sun})",
                                f"R2_clamp_ohlc(n={clamp})",
                                f"R3_drop_isolated_spike(n={spike})"],
            "caveat": "vendor open==close in ~39% of bars -> OHLC unreliable, closes used for research",
            "rows": n_out, "path": os.path.relpath(out, ROOT),
            "sha256": hashlib.sha256(open(out, "rb").read()).hexdigest(),
            "cleaning_log": "data/processed/CLEANING_LOG.csv",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        print(f"{n}: in={n_in} out={n_out} relabeled={relab} dup_sunday={sun} "
              f"clamped={clamp} spikes={spike}")
    json.dump(m, open(mpath, "w"), indent=2, ensure_ascii=False)
    print("cleaning log rows:", len(log) - 1)
