import urllib.request, lzma, struct, datetime as dt, numpy as np

URL = "https://datafeed.dukascopy.com/datafeed/EURGBP/2025/00/02/00h_ticks.bi5"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=30).read()
print("compressed bytes:", len(raw))

data = lzma.LZMADecompressor().decompress(raw) if raw else b""
print("decompressed bytes:", len(data), "| record size 20 ->", len(data)//20, "ticks")

rows = []
for i in range(0, len(data) - 19, 20):
    ms, ask, bid, av, bv = struct.unpack(">3I2f", data[i:i+20])
    rows.append((ms, ask, bid, av, bv))

base = dt.datetime(2025, 1, 2, 0, 0, tzinfo=dt.timezone.utc)   # month is 0-based in path: 00 = Jan
ts = [base + dt.timedelta(milliseconds=r[0]) for r in rows]
ask = np.array([r[1] for r in rows]) / 1e5
bid = np.array([r[2] for r in rows]) / 1e5
spread_pips = (ask - bid) * 1e4

print("first tick:", ts[0], f"bid={bid[0]:.5f} ask={ask[0]:.5f}")
print("last  tick:", ts[-1], f"bid={bid[-1]:.5f} ask={ask[-1]:.5f}")
print(f"spread pips: median={np.median(spread_pips):.2f} mean={spread_pips.mean():.2f} "
      f"p95={np.percentile(spread_pips,95):.2f} max={spread_pips.max():.2f}")
ohlc = f"O={bid[0]:.5f} H={bid.max():.5f} L={bid.min():.5f} C={bid[-1]:.5f}"
print("1h bar from ticks:", ohlc)
