# Batch 5 MQL5 External Acquisition Guide (Legal / Reproducible Colab & PC Workflow)

**Why 201 items remain `blocked` inside the sandbox:**
`mql5.com` returns `HTTP 403` to automated cloud/datacenter IP ranges. Per project security rules, we **never** bypass website WAF/anti-bot controls from the sandbox. Instead, you (the user) can legally download any desired items from your own residential IP / Colab / browser session and feed them into the reproducible ingestion hook below.

## Step 1 — Export the 201 Pending MQL5 URLs
Run locally or inside your clone:
```bash
python3 -c "
import json
rows = [json.loads(l) for l in open('data/ea_kb/research_queue_batch5.jsonl')]
mql = [r for r in rows if r['kind'] == 'mql5_external_archive']
open('mql5_201_urls.txt', 'w').write('\n'.join(r['target'] for r in mql) + '\n')
print(f'Wrote {len(mql)} URLs to mql5_201_urls.txt')
"
```

## Step 2 — Reproducible Local / Browser Fetch (Residential IP, Rate-Limited >= 2s/req)
Use your logged-in MetaQuotes/MQL5 browser session (or gentle Playwright session with your own cookie jar, >=2s delay between requests) to save `.mq4`, `.mq5`, `.mqh`, or `.zip` archives into:
```
data/ea_kb/sources_batch5_manual/
```
*(Do not store credentials or session cookies in git! Keep archives organized by task_id or filename.)*

## Step 3 — Verify Hashes, Extract Safely & Merge Into `alina_ea_kb.sqlite`
1. Back up `data/ea_kb/alina_ea_kb.sqlite` before importing:
   ```bash
   cp data/ea_kb/alina_ea_kb.sqlite /tmp/alina_ea_kb_pre_manual.sqlite
   ```
2. Unzip any `.zip` archives safely (check for path traversal `..` before extraction), compute SHA256, and re-run `python3 scripts/ea_kb_batch5_build.py` (or register new paths in `batch5_fetch_log.json`).
3. Verify `sqlite3 data/ea_kb/alina_ea_kb.sqlite "PRAGMA integrity_check;"` returns `ok`.
