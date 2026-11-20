import json, os, numpy as np

def load(f):
    d = json.load(open(f))
    c = np.array([np.nan if x is None else x for x in d["q"]["close"]], dtype=float)
    ts = np.array(d["ts"])
    m = ~np.isnan(c)
    return d["sym"], ts[m], c[m]

def hurst(x, lags=(2,3,5,8,13,21,34,55,89)):
    x = np.log(x)
    out = []
    for k in lags:
        d = x[k:] - x[:-k]
        out.append((np.log(k), np.log(np.std(d))))
    a = np.array(out)
    return np.polyfit(a[:,0], a[:,1], 1)[0]

def ar1_halflife(s):
    s = np.asarray(s, float)
    x, y = s[:-1], s[1:]
    beta = np.polyfit(x - x.mean(), y - y.mean(), 1)[0]
    if beta <= 0 or beta >= 1:
        return np.nan
    return -np.log(2) / np.log(beta)

def adf_tstat(s, p=2):
    s = np.asarray(s, float)
    ds = np.diff(s)
    y = ds[p:]
    cols = [s[p:-1] - s[p:-1].mean()]
    for i in range(1, p+1):
        cols.append(ds[p-i:-i])
    X = np.column_stack(cols + [np.ones(len(y))])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    n, k = X.shape
    s2 = resid @ resid / (n - k)
    cov = s2 * np.linalg.inv(X.T @ X)
    return b[0] / np.sqrt(cov[0,0])

def dev_from_ma(c, w=50):
    ma = np.convolve(c, np.ones(w)/w, mode="valid")
    return c[w-1:] / ma - 1

files = sorted(os.listdir("screen/raw"))
data = {}
rows = []
for f in files:
    sym, ts, c = load("screen/raw/" + f)
    data[sym] = c
    r = np.diff(np.log(c))
    vol = r.std() * np.sqrt(252) * 100
    h = hurst(c[-1500:])
    dev = dev_from_ma(c[-1500:], 50)
    hl = ar1_halflife(dev)
    rows.append((sym, len(c), round(vol,1), round(h,3), round(hl,1)))

print("=== SINGLE INSTRUMENTS (last ~1500 daily bars) ===")
print(f"{'symbol':10} {'n':>5} {'vol%ann':>8} {'hurst':>7} {'halflife_d':>11}")
for r in rows:
    print(f"{r[0]:10} {r[1]:>5} {r[2]:>8} {r[3]:>7} {r[4]:>11}")

# ---- pairs ----
pairs = [("EURCHF=X","EURUSD=X"), ("EURGBP=X","EURUSD=X"), ("AUDNZD=X","AUDCAD=X"),
         ("AUDNZD=X","NZDCAD=X"), ("CADCHF=X","EURCHF=X")]
print("\n=== PAIRS: log(A) - beta*log(B), beta by OLS over full sample ===")
print(f"{'pair':22} {'corr':>6} {'halflife':>9} {'ADF t':>7} {'vol':>6} {'beta':>7}")
for a, b in pairs:
    if a not in data or b not in data:
        continue
    n = min(len(data[a]), len(data[b]))
    la, lb = np.log(data[a][-n:]), np.log(data[b][-n:])
    X = np.column_stack([lb, np.ones(n)])
    beta, icpt = np.linalg.lstsq(X, la, rcond=None)[0]
    sp = la - beta*lb
    hl = ar1_halflife(sp[-1500:])
    t = adf_tstat(sp[-1500:])
    corr = np.corrcoef(np.diff(la)[-1500:], np.diff(lb)[-1500:])[0,1]
    vol = np.diff(sp).std()*np.sqrt(252)*100
    print(f"{a[:6]}/{b[:6]:14} {corr:>6.3f} {hl:>9.1f} {t:>7.2f} {vol:>6.1f} {beta:>7.3f}")

# ---- gold/silver ratio ----
if "GC=F" in data and "SI=F" in data:
    n = min(len(data["GC=F"]), len(data["SI=F"]))
    ratio = data["GC=F"][-n:] / data["SI=F"][-n:]
    print("\n=== GOLD/SILVER RATIO ===")
    print(f"current={ratio[-1]:.1f}  mean(last1500)={ratio[-1500:].mean():.1f}  "
          f"min={ratio[-1500:].min():.1f} max={ratio[-1500:].max():.1f}  "
          f"halflife={ar1_halflife(dev_from_ma(ratio[-1500:],50)):.1f}d  "
          f"hurst={hurst(ratio[-1500:]):.3f}")
