#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 서버를 최신 코드로 올린다.
#
#   내 PC 에서:  bash deploy/update.sh
#   서버 안에서: bash deploy/update.sh --here
#
# **Render 는 밀어 넣으면 알아서 배포했지만 여기는 아니다.**
# 옮긴 뒤 한동안 이걸 잊어서, 서버가 1.0.0 인 채로 클라이언트만 1.0.4 가
# 됐다. 새로 만든 경로(/api/pokemon/order)가 서버에 없으니 405 가 났다 -
# 없는 경로가 아니라 **같은 경로의 다른 메서드**로 걸려서 404 도 아니었다.
#
# 하는 일: 백업 -> 받기 -> 다시 빌드 -> 확인. 확인이 실패하면 알려준다.
# ---------------------------------------------------------------------------
set -euo pipefail

HOST="${POKET_HOST:-ubuntu@13.124.198.66}"
KEY="${POKET_KEY:-$HOME/.ssh/LightsailDefaultKey-ap-northeast-2.pem}"
APP="${POKET_APP:-$HOME/poketdesktop}"
URL="${POKET_URL:-https://posktop.duckdns.org}"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }

remote() {
  say "1. 올리기 전에 백업"
  cd "$APP"
  bash deploy/backup.sh 2>&1 | grep -E "OK|!!" || true

  say "2. 새 코드 받기"
  echo "   지금: $(git log --oneline -1)"
  # 손으로 올려 둔 파일이 있으면 받기가 막힌다. 저장소 판으로 맞춘다.
  git fetch -q origin
  git checkout -q -- . 2>/dev/null || true
  git clean -qfd deploy 2>/dev/null || true
  git pull -q
  echo "   받음: $(git log --oneline -1)"

  say "3. 다시 빌드"
  docker compose -f deploy/docker-compose.prod.yml up -d --build 2>&1 | tail -5

  say "4. 뜰 때까지 기다리기"
  for _i in $(seq 1 30); do
    sleep 2
    if curl -fsS --max-time 5 http://127.0.0.1/api/health >/dev/null 2>&1; then
      break
    fi
  done
  docker ps --format '   {{.Names}}  {{.Status}}'
}

if [ "${1:-}" = "--here" ]; then
  remote
  exit 0
fi

# ---- 내 PC 에서 돌릴 때 ----
[ -f "$KEY" ] || { warn "키가 없습니다: $KEY"; exit 1; }

say "서버로 들어가서 올립니다  ($HOST)"
ssh -i "$KEY" -o StrictHostKeyChecking=no "$HOST" \
    'cd ~/poketdesktop && git fetch -q origin && git checkout -q -- . && git pull -q && bash deploy/update.sh --here'

say "바깥에서 확인"
# **컨테이너가 뜰 때까지 기다린다.** 다시 빌드한 직후에는 아직
# health: starting 이라 곧바로 물으면 답이 없다. 그걸 "버전이 다르다" 로
# 읽고 헛경보를 냈다.
#
# `python` 이 아니라 `python3` 을 쓴다. 맥에는 `python` 이라는 이름이 없다
# (셸 별칭은 스크립트에서 안 보인다). 그래서 값이 늘 "?" 로 나왔다.
PY=$(command -v python3 || command -v python)
ver="?"
for _i in $(seq 1 20); do
  ver=$(curl -fsS --max-time 20 "$URL/api/health" 2>/dev/null \
        | "$PY" -c "import json,sys; print(json.load(sys.stdin)['version'])" 2>/dev/null || echo "?")
  [ "$ver" != "?" ] && break
  sleep 3
done
want=$(grep -oE '"[0-9]+\.[0-9]+\.[0-9]+"' common/version.py | head -1 | tr -d '"')
echo "   서버 $ver  ·  저장소 $want"
if [ "$ver" = "$want" ]; then
  ok "같은 버전입니다"
else
  warn "버전이 다릅니다. 빌드가 실패했는지 로그를 보세요:"
  echo "      ssh -i <키> $HOST 'docker logs poketdesktop-server --tail 40'"
  exit 1
fi
