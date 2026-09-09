#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 맥에서 DB 를 브라우저로 본다. `포스크탑 관리.app` 이 이걸 부른다.
#
#   bash deploy/dbview-mac.sh          # 물어본다
#   bash deploy/dbview-mac.sh --read   # 안 물어보고 읽기 전용
#
# 하는 일은 윈도우의 deploy/dbview.ps1 과 똑같다.
#   서버에서 sqlite-web 켜기 -> SSH 터널 뚫기 -> 브라우저 열기
#
# **이 창을 닫으면 연결이 끊기고 서버 쪽도 꺼진다.** 그게 곧 '닫기' 다.
# 창을 닫아 SIGHUP 이 와도 trap 이 뒷정리를 한다. 그마저 놓쳤더라도
# 다음에 켤 때 dbview.sh 가 `docker rm -f` 로 지우고 새로 띄우므로
# 찌꺼기가 쌓이지는 않는다.
#
# DB 에는 닉네임과 비밀번호 해시가 들어 있다. 비밀번호가 숫자 네 자리라
# 해시가 새어 나가면 오프라인에서 만 번만 돌려도 뚫린다. 그래서 서버
# 쪽은 127.0.0.1 에만 묶여 있고, 들어가는 길은 이 터널뿐이다.
# ---------------------------------------------------------------------------
set -uo pipefail

HOST="${POKET_HOST:-ubuntu@13.124.198.66}"
KEY="${POKET_KEY:-$HOME/.ssh/LightsailDefaultKey-ap-northeast-2.pem}"
PORT="${POKET_DBVIEW_PORT:-8081}"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10)

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }

hold() {
    # 창이 그냥 사라지면 무엇이 잘못됐는지 볼 수가 없다.
    printf '\n엔터를 누르면 닫습니다 '
    read -r _ || true
}

printf '\033]0;포스크탑 관리\007'          # 터미널 창 제목
clear
cat <<'EOF'

  포스크탑 관리
  -------------
EOF

if [ ! -f "$KEY" ]; then
    warn "SSH 키가 없습니다: $KEY"
    echo "   Lightsail 콘솔 > Account > SSH keys 에서 서울 리전 기본키를 받아"
    echo "   위 경로에 두고, 권한을 600 으로 맞추세요:"
    echo "      chmod 600 \"$KEY\""
    hold
    exit 1
fi

# 키 권한이 헐거우면 ssh 가 아예 거절한다. 원인이 안 보이는 실패라
# 미리 알려 준다.
perm=$(stat -f "%Lp" "$KEY" 2>/dev/null || echo "")
if [ -n "$perm" ] && [ "$perm" != "600" ] && [ "$perm" != "400" ]; then
    warn "키 권한이 $perm 입니다. ssh 가 거절합니다."
    echo "      chmod 600 \"$KEY\""
    hold
    exit 1
fi

MODE=""
LABEL="읽기 전용"
if [ "${1:-}" != "--read" ]; then
    echo "   1) 읽기만  (안전. 아무것도 안 바뀝니다)"
    echo "   2) 고치기  (행을 바꾸고 지울 수 있습니다)"
    echo
    printf "  고르세요 [1]: "
    read -r pick || pick=1
    if [ "${pick:-1}" = "2" ]; then
        echo
        warn "고치기 모드입니다. 여기서 지운 것은 되돌릴 수 없습니다."
        printf "  정말 하시겠습니까? '고칠래요' 를 그대로 입력: "
        read -r yes || yes=""
        if [ "$yes" != "고칠래요" ]; then
            echo
            echo "  그만둡니다."
            sleep 2
            exit 0
        fi
        # 고치기 전에는 반드시 백업부터. 실수는 되돌릴 수 있어야 한다.
        say "먼저 백업을 뜹니다"
        ssh "${SSH_OPTS[@]}" "$HOST" \
            "cd ~/poketdesktop && bash deploy/backup.sh 2>&1 | grep -E 'OK|!!'"
        if [ $? -ne 0 ]; then
            warn "백업에 실패했습니다. 고치기 모드로는 안 엽니다."
            hold
            exit 1
        fi
        MODE="--write"
        LABEL="고칠 수 있음"
    fi
fi

stop_remote() {
    ssh "${SSH_OPTS[@]}" "$HOST" \
        "cd ~/poketdesktop && bash deploy/dbview.sh --stop" >/dev/null 2>&1
}

cleanup() {
    trap - EXIT INT TERM HUP
    say "연결을 끊었습니다. 서버 쪽도 끕니다"
    stop_remote
    ok "끝"
    sleep 1
}
trap cleanup EXIT INT TERM HUP

say "서버에서 DB 보기를 켭니다 ($LABEL)"
ssh "${SSH_OPTS[@]}" "$HOST" \
    "cd ~/poketdesktop && bash deploy/dbview.sh $MODE 2>&1 | grep -E 'OK|!!'"
if [ $? -ne 0 ]; then
    warn "서버에서 켜지 못했습니다."
    hold
    exit 1
fi

# 터널이 자리를 잡은 뒤에 연다. 먼저 열면 '연결할 수 없음' 이 뜬다.
( sleep 4; open "http://127.0.0.1:$PORT" >/dev/null 2>&1 ) &

echo
echo "  ---------------------------------------------"
echo "   http://127.0.0.1:$PORT  이 곧 열립니다"
if [ -n "$MODE" ]; then
    printf '   \033[31m고치기 모드입니다\033[0m\n'
else
    printf '   \033[32m읽기 전용입니다\033[0m\n'
fi
echo
printf '   \033[1;33m** 이 창을 닫으면 연결이 끊깁니다 **\033[0m\n'
echo "  ---------------------------------------------"
echo

# 터널을 잡고 있는다. 이 창이 살아 있는 동안만 접속된다.
# -N 은 명령을 안 돌린다는 뜻이고, ExitOnForwardFailure 를 켜 두면
# 8081 이 이미 쓰이고 있을 때 조용히 성공한 척하지 않는다.
ssh "${SSH_OPTS[@]}" -N -o ExitOnForwardFailure=yes \
    -L "${PORT}:127.0.0.1:${PORT}" "$HOST"
code=$?
if [ $code -ne 0 ] && [ $code -ne 130 ]; then
    warn "터널이 끊겼습니다 (코드 $code)."
    echo "   8081 을 이미 쓰고 있으면 그 창을 먼저 닫으세요."
    hold
fi
