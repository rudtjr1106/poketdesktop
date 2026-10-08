#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 직접 그린 캐릭터 도트를 운영 서버의 그 사람에게 넣는다.
#
#   bash deploy/avatar_set.sh <닉네임> <받은파일.png>     넣는다
#   bash deploy/avatar_set.sh --show  <닉네임>            지금 무엇을 쓰고 있나
#   bash deploy/avatar_set.sh --clear <닉네임>            넣어 둔 도트를 지운다
#
# 넣기 전에 내 PC 에서 규격을 먼저 본다 (tools/avatar_check.py). 미리보기 그림도 만들어 주니
# **눈으로 한 번 보고** 넣는다 - 규격에 맞아도 넣으면 안 되는 그림이 있다 (안내서의 '받지 않는 것').
# 서버도 넣을 때 규격을 다시 검사한다. 화면에서 그림을 올리는 길은 없다 (server/app/avatar.py).
# ---------------------------------------------------------------------------
set -euo pipefail

HOST="${POKET_HOST:-ubuntu@13.124.198.66}"
KEY="${POKET_KEY:-$HOME/.ssh/LightsailDefaultKey-ap-northeast-2.pem}"
BOX="${POKET_CONTAINER:-poketdesktop-server}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${POKET_PY:-$HERE/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

tool() { ssh -i "$KEY" "$HOST" "docker exec -i $BOX python -m app.avatar_tool $*"; }

case "${1:-}" in
  --show)  [ $# -eq 2 ] || { sed -n '2,12p' "$0"; exit 2; }; tool show  "'$2'"; exit ;;
  --clear) [ $# -eq 2 ] || { sed -n '2,12p' "$0"; exit 2; }; tool clear "'$2'"; exit ;;
esac
[ $# -eq 2 ] || { sed -n '2,12p' "$0"; exit 2; }
NAME="$1"; FILE="$2"

"$PY" "$HERE/tools/avatar_check.py" "$FILE"
printf '\n%s 에게 이 도트를 넣을까요? 미리보기를 확인했으면 y: ' "$NAME"
read -r yes
[ "$yes" = "y" ] || { echo "넣지 않았습니다."; exit 1; }
tool set "'$NAME'" < "$FILE"
