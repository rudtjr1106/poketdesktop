#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 리눅스 VM 한 대에 포켓 데스크톱 서버를 통째로 올린다.
# AWS Lightsail 기준으로 적었지만 우분투면 어디서든 돈다.
#
# 왜 한 대에 다 올리나:
#   Render(싱가포르) + Turso(도쿄) 조합은 쿼리마다 바다를 건넜다. 재보니
#   왕복 하나가 100~200ms 고, DB 를 안 쓰는 요청도 220ms 였다.
#   지역을 맞추는 길은 없다 - Turso 에 싱가포르가 없고 Render 에 도쿄가 없다.
#   서버와 DB 를 한 대에 두면 왕복이 아예 사라진다. 서울에 두면 한국에서 6ms 다.
#
# 미리 해둘 것:
#   1) Lightsail 에서 인스턴스 생성 (서울 ap-northeast-2, Ubuntu, 512MB 이상)
#   2) **고정 IP(Static IP)를 만들어 붙인다** - 안 붙이면 재부팅 때 주소가 바뀐다
#   3) Networking 탭에서 80, 443 을 연다 (기본은 22 만 열려 있다)
#   4) 도메인이 이 IP 를 가리키게 한다 (공짜: https://www.duckdns.org)
#
# 그다음 SSH 로 들어와서:
#   cd ~
#   git clone https://github.com/rudtjr1106/poketdesktop.git
#   bash poketdesktop/deploy/setup-aws.sh
#
# `curl ... | bash` 로 돌리지 마라. 이 스크립트는 도메인을 물어보는데,
# 파이프로 넣으면 read 가 스크립트의 나머지 줄을 답으로 먹어 버린다.
# 물어보는 게 싫으면 미리 넣어 주면 된다:
#   POKET_DOMAIN=x.duckdns.org ACME_EMAIL=me@example.com bash deploy/setup-aws.sh
# ---------------------------------------------------------------------------
set -euo pipefail

# apt 가 설치 중에 물어보면 화면에 안 뜨고 그대로 멈춘다.
export DEBIAN_FRONTEND=noninteractive

REPO_URL="${REPO_URL:-https://github.com/rudtjr1106/poketdesktop.git}"
APP_DIR="${APP_DIR:-$HOME/poketdesktop}"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }

# ---------------------------------------------------------------- 0. 확인
if [ "$(id -u)" -eq 0 ]; then
  warn "root 로 돌리지 마세요. 일반 사용자(ubuntu)로 실행하세요."
  exit 1
fi

. /etc/os-release
say "운영체제: $PRETTY_NAME"

# ---------------------------------------------------------------- 1. 스왑
# 제일 싼 Lightsail 은 메모리가 512MB 다. 스왑 없이 도커 빌드를 하면
# 거의 확실히 죽는다. 빌드가 끝난 뒤에도 남겨 둔다 - 여유가 없다.
if ! swapon --show | grep -q .; then
  say "스왑 2GB 만들기 (512MB VM 에서 빌드가 죽는 걸 막는다)"
  sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  ok "스왑 켜짐"
else
  ok "스왑이 이미 있음"
fi

# ---------------------------------------------------------------- 2. 도커
if ! command -v docker >/dev/null 2>&1; then
  say "도커 설치"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  ok "설치 완료"
else
  ok "도커가 이미 있음: $(docker --version)"
fi

# 도커 그룹은 **로그인할 때** 정해진다. 방금 usermod 로 넣었어도 지금 셸은
# 모른다. 그래서 여기서 바로 docker 를 부르면 permission denied 로 죽는다.
# sg 로 그룹을 바꿔 실행하면 다시 로그인하지 않고도 넘어갈 수 있다.
SG=""
if ! docker info >/dev/null 2>&1; then
  if sg docker -c "docker info" >/dev/null 2>&1; then
    SG="yes"
    ok "도커 그룹을 이 실행에만 적용합니다 (다시 로그인 안 해도 됩니다)"
  else
    warn "아직 도커를 쓸 권한이 없습니다."
    echo "   한 번 나갔다가 다시 들어온 뒤 이 스크립트를 다시 돌리세요."
    echo "   (스크립트는 여러 번 돌려도 안전합니다 - 이미 된 것은 건너뜁니다)"
    exit 1
  fi
fi

# docker 를 부르는 유일한 통로. 그룹 문제를 한 군데서만 다룬다.
d() {
  if [ -n "$SG" ]; then
    sg docker -c "cd '$PWD' && docker $*"
  else
    docker "$@"
  fi
}

if ! d compose version >/dev/null 2>&1; then
  say "docker compose 플러그인 설치"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq docker-compose-plugin
  else
    sudo dnf install -y docker-compose-plugin || true
  fi
fi

# ---------------------------------------------------------------- 3. 방화벽
# Lightsail 의 진짜 관문은 **콘솔의 IPv4 Firewall** 이다. 우분투 이미지는
# 안쪽에서 80, 443 을 막지 않는다.
#
# 예전에는 여기서 iptables 규칙을 넣고 iptables-persistent 를 설치했다.
# 그런데 그 패키지는 설치 중에 "지금 규칙을 저장할까요?" 를 **물어본다.**
# 출력을 /dev/null 로 보내 두어서 화면에는 아무것도 안 뜨고 그대로 멈췄다.
# Lightsail 에서는 애초에 필요 없는 일이라 아예 뺐다.
say "인스턴스 안쪽 방화벽 확인"
if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  warn "ufw 가 켜져 있습니다. 80, 443 을 엽니다."
  sudo ufw allow 80/tcp >/dev/null 2>&1 || true
  sudo ufw allow 443/tcp >/dev/null 2>&1 || true
  ok "ufw 에 규칙 추가"
else
  ok "안쪽에서 막고 있지 않습니다"
fi

# 80, 443 을 이미 누가 잡고 있으면 Caddy 가 못 뜬다. 먼저 알려준다.
busy=""
for port in 80 443; do
  if sudo ss -lntp 2>/dev/null | grep -q ":$port "; then
    busy="$busy $port"
  fi
done
if [ -n "$busy" ]; then
  warn "포트$busy 를 이미 누가 쓰고 있습니다. Caddy 가 못 뜹니다."
  sudo ss -lntp 2>/dev/null | grep -E ":(80|443) " || true
  echo "        도커 컨테이너면:  docker ps"
  echo "        아파치/엔진엑스면:  sudo systemctl disable --now apache2 nginx"
  exit 1
fi

warn "Lightsail 콘솔의 [인스턴스 > Networking > IPv4 Firewall] 에도 규칙이 있어야 합니다."
echo "        HTTP(80) 과 HTTPS(443) 을 추가하세요. 기본은 22 만 열려 있습니다."

# ---------------------------------------------------------------- 4. 코드
if [ -d "$APP_DIR/.git" ]; then
  say "이미 받아둔 코드 갱신"
  git -C "$APP_DIR" pull --ff-only
else
  say "코드 받기"
  warn "비공개 저장소라면 먼저 SSH 키를 등록하거나 gh auth login 을 해두세요."
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR/deploy"

# ---------------------------------------------------------------- 5. 도메인
if [ ! -f .env ]; then
  say "도메인 설정"
  echo "   HTTPS 인증서를 받으려면 이 VM 을 가리키는 도메인이 필요합니다."
  echo "   공짜로 만들려면 https://www.duckdns.org 에서 하나 만드세요."
  echo "   (예: poketdesktop.duckdns.org  ->  이 VM 의 공인 IP)"
  echo
  DOMAIN="${POKET_DOMAIN:-}"
  EMAIL="${ACME_EMAIL:-}"
  [ -n "$DOMAIN" ] || read -rp "   도메인: " DOMAIN
  [ -n "$EMAIL" ] || read -rp "   이메일 (인증서 만료 알림용): " EMAIL
  [ -n "$DOMAIN" ] || { warn "도메인 없이는 HTTPS 를 못 켭니다."; exit 1; }
  printf 'POKET_DOMAIN=%s\nACME_EMAIL=%s\n' "$DOMAIN" "$EMAIL" > .env
  ok ".env 저장"
else
  ok ".env 가 이미 있음: $(grep POKET_DOMAIN .env)"
fi

# ---------------------------------------------------------------- 6. 실행
say "빌드하고 띄우기 (처음이면 몇 분 걸립니다)"
d compose -f docker-compose.prod.yml up -d --build

say "상태 확인"
sleep 8
d compose -f docker-compose.prod.yml ps

DOMAIN=$(grep POKET_DOMAIN .env | cut -d= -f2)
echo
if curl -fsS --max-time 20 "https://$DOMAIN/api/health" >/dev/null 2>&1; then
  ok "https://$DOMAIN 정상 동작"
  curl -s "https://$DOMAIN/api/health"
  echo
  echo
  echo "   서버 주소:  https://$DOMAIN"
  echo
  warn "아직 두 가지가 남았습니다:"
  echo "     1) 백업을 켜세요:  bash deploy/backup.sh --install"
  echo "        여기서는 SQLite 파일 하나가 유일본입니다. 날아가면 끝입니다."
  echo "     2) 클라이언트가 새 주소를 보게 하세요."
  echo "        client/poketdesktop/config.py 의 SERVER 를 바꾸고,"
  echo "        OLD_SERVERS 에 옛 주소를 넣은 다음 새 버전을 릴리스합니다."
else
  warn "아직 응답이 없습니다. 인증서 발급에 1~2분 걸리기도 합니다."
  echo "   확인:  docker compose -f docker-compose.prod.yml logs -f caddy"
  echo "   흔한 원인:"
  echo "     - 도메인이 이 VM 의 고정 IP 를 안 가리킴 (dig +short $DOMAIN 으로 확인)"
  echo "     - Lightsail Networking 탭에 80/443 규칙이 없음"
  echo "     - 고정 IP 를 인스턴스에 안 붙였음"
fi
