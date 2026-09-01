#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# DB 를 떠서 잠그고 보관한다. 하루 한 번 cron 으로 돈다.
#
# 여기서는 **SQLite 파일 하나가 유일본**이다. Turso 를 쓸 때는 그쪽이
# 알아서 들고 있었지만 이제는 아니다. 인스턴스가 죽으면 그것으로 끝이다.
#
#   bash deploy/backup.sh --install   # cron 에 걸기 (하루 한 번)
#   bash deploy/backup.sh             # 지금 한 번 뜨기
#   bash deploy/backup.sh --restore <파일>
#
# 왜 잠그나: 백업에는 닉네임과 비밀번호 해시가 들어 있다. 비밀번호가
# 숫자 네 자리라 해시가 새어 나가면 오프라인에서 만 번만 돌려도 뚫린다.
#
# 열쇠는 deploy/.env 의 POKET_BACKUP_KEY 다. **따로 적어 두어라.**
# 잃어버리면 백업을 영영 못 연다.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${POKET_BACKUP_DIR:-$HOME/poket-backups}"
KEEP="${POKET_BACKUP_KEEP:-14}"
CONTAINER="${POKET_CONTAINER:-poketdesktop-server}"
DB_IN_CONTAINER="/data/poket.db"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
die()  { printf '   \033[31m!!\033[0m  %s\n' "$*" >&2; exit 1; }

[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

# ---------------------------------------------------------------- cron 등록
if [ "${1:-}" = "--install" ]; then
  line="17 3 * * * bash $HERE/backup.sh >> $OUT_DIR/backup.log 2>&1"
  mkdir -p "$OUT_DIR"
  # 이미 있으면 두 번 넣지 않는다
  if crontab -l 2>/dev/null | grep -Fq "$HERE/backup.sh"; then
    ok "cron 에 이미 있음"
  else
    (crontab -l 2>/dev/null; echo "$line") | crontab -
    ok "cron 등록: 매일 새벽 3시 17분"
  fi
  crontab -l | grep backup.sh
  echo
  echo "   지금 한 번 돌려서 되는지 보세요:  bash $HERE/backup.sh"
  exit 0
fi

# ---------------------------------------------------------------- 되살리기
if [ "${1:-}" = "--restore" ]; then
  f="${2:-}"
  [ -f "$f" ] || die "되살릴 파일을 주세요:  bash backup.sh --restore <파일>"
  [ -n "${POKET_BACKUP_KEY:-}" ] || die "POKET_BACKUP_KEY 가 없습니다 (deploy/.env)"
  say "되살리기 — 지금 들어 있는 것을 덮어씁니다"
  read -rp "   정말 하시겠습니까? '덮어씁니다' 를 그대로 입력: " yes
  [ "$yes" = "덮어씁니다" ] || die "그만둡니다"
  tmp="$(mktemp -d)"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
          -in "$f" -out "$tmp/poket.db" -pass env:POKET_BACKUP_KEY \
    || die "열지 못했습니다. 열쇠가 맞습니까?"
  # 서버를 세우고 바꾼다. 켜진 채로 파일을 갈아끼우면 열려 있는 커넥션이
  # 옛 파일을 붙잡고 있어서 조용히 어긋난다.
  docker stop "$CONTAINER" >/dev/null
  # 옛 WAL 이 남아 있으면 새 본체 위에 옛 변경분이 덧씌워진다. 먼저 지운다.
  docker run --rm --volumes-from "$CONTAINER" busybox sh -c "rm -f $DB_IN_CONTAINER-wal $DB_IN_CONTAINER-shm" 2>/dev/null || true
  docker cp "$tmp/poket.db" "$CONTAINER:$DB_IN_CONTAINER"
  docker start "$CONTAINER" >/dev/null
  rm -rf "$tmp"
  ok "되살렸습니다. /api/health 로 확인하세요."
  exit 0
fi

# ---------------------------------------------------------------- 뜨기
[ -n "${POKET_BACKUP_KEY:-}" ] || die "POKET_BACKUP_KEY 가 없습니다.
   deploy/.env 에 넣으세요. 아무 긴 문자열이면 됩니다:
      echo \"POKET_BACKUP_KEY=\$(openssl rand -base64 36)\" >> $HERE/.env
   **넣은 값을 따로 적어 두세요.** 잃어버리면 백업을 못 엽니다."

docker inspect "$CONTAINER" >/dev/null 2>&1 || die "$CONTAINER 가 안 돕니다"
mkdir -p "$OUT_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 살아 있는 SQLite 파일을 그냥 복사하면 안 된다. 쓰는 도중이면 반쪽짜리가
# 나오고, WAL 에만 있고 본체에 아직 안 들어간 내용을 놓친다.
# sqlite3 의 온라인 백업 API 는 켜져 있는 DB 에서도 온전한 사본을 만든다.
docker exec -i "$CONTAINER" python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/poket.db")
dst = sqlite3.connect("/tmp/snap.db")
with dst:
    src.backup(dst)
dst.close()
src.close()
print("snapshot ok")
PY

docker cp "$CONTAINER:/tmp/snap.db" "$tmp/poket.db" >/dev/null
docker exec "$CONTAINER" rm -f /tmp/snap.db

size=$(stat -c%s "$tmp/poket.db")
[ "$size" -gt 4096 ] || die "떠낸 것이 너무 작습니다 ($size 바이트). DB 가 비었습니까?"

out="$OUT_DIR/poket-$stamp.db.enc"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
        -in "$tmp/poket.db" -out "$out" -pass env:POKET_BACKUP_KEY

# 열리지 않는 백업은 백업이 아니다. 매번 확인한다.
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
        -in "$out" -out "$tmp/check.db" -pass env:POKET_BACKUP_KEY
head -c 16 "$tmp/check.db" | grep -aq "SQLite format 3" || die "다시 열었더니 SQLite 파일이 아닙니다. 백업을 믿을 수 없습니다."

ok "$(basename "$out")  ($(numfmt --to=iec "$size" 2>/dev/null || echo "$size B"))"

# 오래된 것 정리
ls -1t "$OUT_DIR"/poket-*.db.enc 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
  echo "   지움: $(basename "$old")"
done

echo
echo "   보관 위치: $OUT_DIR  (최근 $KEEP 개)"
echo "   **이 인스턴스가 죽으면 여기 있는 것도 같이 죽습니다.**"
echo "   Lightsail 자동 스냅샷도 같이 켜 두세요 (콘솔 > Snapshots)."
echo "   내 PC 로 내려받기:"
echo "      scp ubuntu@<고정IP>:$OUT_DIR/poket-*.db.enc ."
