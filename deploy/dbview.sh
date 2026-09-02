#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# DB 를 브라우저에서 들여다본다.
#
#   bash deploy/dbview.sh          # 읽기만 (기본)
#   bash deploy/dbview.sh --write  # 고칠 수도 있게
#   bash deploy/dbview.sh --stop   # 끄기
#
# **인터넷에 열지 않는다.** 127.0.0.1 에만 붙여 두고, 볼 때는 SSH 터널로
# 들어온다. DB 에는 닉네임과 비밀번호 해시가 들어 있고, 비밀번호가 숫자
# 네 자리라 해시가 새어 나가면 오프라인에서 만 번만 돌려도 뚫린다.
# 방화벽(Lightsail 콘솔)에도 이 포트를 열지 마라.
#
# 내 PC 에서:
#   ssh -i <키> -L 8081:127.0.0.1:8081 ubuntu@<고정IP>
# 그리고 브라우저에서  http://127.0.0.1:8081
# ---------------------------------------------------------------------------
set -euo pipefail

NAME="poket-dbview"
PORT="${POKET_DBVIEW_PORT:-8081}"
SERVER="${POKET_CONTAINER:-poketdesktop-server}"
DB="/data/poket.db"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }

if [ "${1:-}" = "--stop" ]; then
  docker rm -f "$NAME" >/dev/null 2>&1 && ok "껐습니다" || ok "돌고 있지 않았습니다"
  exit 0
fi

MODE="읽기 전용"
RO="--read-only"
if [ "${1:-}" = "--write" ]; then
  MODE="고칠 수 있음"
  RO=""
  warn "고칠 수 있는 모드입니다. 여기서 지운 것은 되돌릴 수 없습니다."
  warn "먼저 백업을 떠 두세요:  bash deploy/backup.sh"
fi

docker inspect "$SERVER" >/dev/null 2>&1 || { warn "$SERVER 가 안 돕니다"; exit 1; }
docker rm -f "$NAME" >/dev/null 2>&1 || true

say "DB 보기 켜는 중 ($MODE)"
# --volumes-from 으로 서버가 쓰는 /data 를 그대로 본다. 사본이 아니라
# **지금 그 파일**이라 방금 잡은 포켓몬도 바로 보인다.
# 포트는 127.0.0.1 에만 묶는다. 0.0.0.0 으로 열면 인터넷에 그대로 뚫린다.
docker run -d --rm --name "$NAME" \
  --volumes-from "$SERVER" \
  -p "127.0.0.1:$PORT:8080" \
  coleifer/sqlite-web \
  sqlite_web -H 0.0.0.0 -p 8080 $RO "$DB" >/dev/null

sleep 3
if ! docker ps --format '{{.Names}}' | grep -q "^$NAME$"; then
  warn "안 떴습니다. 로그:"
  docker logs "$NAME" 2>&1 | tail -20 || true
  exit 1
fi

ok "켜졌습니다 (127.0.0.1:$PORT — 바깥에서는 못 들어옵니다)"
cat <<EOF

   내 PC 에서 터널을 열고:
      ssh -i <키파일> -L $PORT:127.0.0.1:$PORT ubuntu@<고정IP>

   브라우저에서:
      http://127.0.0.1:$PORT

   다 보고 나면 꺼 주세요:
      bash deploy/dbview.sh --stop
EOF
