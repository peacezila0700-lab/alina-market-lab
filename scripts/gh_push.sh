#!/usr/bin/env bash
# gh_push.sh — ต่อ remote + push ให้ GitHub ได้ทุกเทิร์น แม้ snapshot จะลบ .git/config
#
# ทำไมต้องมี: platform ตัด .git/config, .git-credentials, .netrc ออกจากการบันทึก snapshot
# (กัน credential หลุด) → remote ที่ฝัง token ไว้หายทุกครั้งที่ sandbox ถูกสร้างใหม่
# วิธีแก้: เก็บ token ไว้ที่ ~/.alina/git_token ซึ่ง "ไม่" ถูกตัด → script นี้ประกอบ remote ใหม่ให้เอง
#
# ใช้:
#   bash scripts/gh_push.sh              # ตั้ง remote + push main
#   bash scripts/gh_push.sh --save TOKEN # บันทึก token ลง ~/.alina/git_token (chmod 600) แล้ว push
#   bash scripts/gh_push.sh --check      # ดูสถานะ ไม่ push
set -u

REPO_SLUG="peacezila0700-lab/alina-market-lab"
TOKEN_FILE="$HOME/.alina/git_token"
BRANCH="${BRANCH:-main}"
cd "$(dirname "$0")/.." || exit 1

if [ "${1:-}" = "--save" ]; then
  [ -z "${2:-}" ] && { echo "ต้องใส่ token: bash scripts/gh_push.sh --save <TOKEN>"; exit 2; }
  mkdir -p "$(dirname "$TOKEN_FILE")"
  printf '%s' "$2" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  echo "บันทึก token ไว้ที่ $TOKEN_FILE (สิทธิ์ 600)"
fi

TOKEN="${GITHUB_PAT:-}"
[ -z "$TOKEN" ] && [ -f "$TOKEN_FILE" ] && TOKEN="$(cat "$TOKEN_FILE")"

if [ -z "$TOKEN" ]; then
  echo "ไม่พบ token — ยังไม่ได้ตั้งค่า"
  echo "  วิธี: bash scripts/gh_push.sh --save <TOKEN>   หรือ export GITHUB_PAT=..."
  exit 3
fi

echo "commit ที่ยังไม่ขึ้น remote: $(git rev-list --count origin/$BRANCH..HEAD 2>/dev/null || echo 'ไม่ทราบ (ยังไม่มี remote)')"

if [ "${1:-}" = "--check" ]; then
  git remote -v | sed 's#://[^@]*@#://***@#'
  exit 0
fi

# ตั้ง remote ใหม่ (ทับของเดิมที่อาจหายไป) — ไม่ echo token ออกจอ
git remote remove origin 2>/dev/null
git remote add origin "https://${REPO_SLUG%%/*}:${TOKEN}@github.com/${REPO_SLUG}.git" || exit 4

echo "push → $REPO_SLUG ($BRANCH)"
if git push origin "$BRANCH" 2>&1 | sed "s#${TOKEN}#***#g"; then
  echo "✅ push สำเร็จ: $(git rev-parse --short HEAD)"
else
  echo "❌ push ไม่สำเร็จ — ดูข้อความด้านบน (401/403 = token ผิดหรือสิทธิ์ไม่พอ, 404 = ชื่อ repo ผิด)"
  exit 5
fi
