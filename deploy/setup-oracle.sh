#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Oracle Cloud 무료 VM 에 포켓 데스크톱 서버를 올린다.
#
#   1) Oracle 콘솔에서 VM 을 만들고 (Always Free shape)
#   2) 보안 목록에 80, 443 인그레스 규칙을 넣고
#   3) SSH 로 들어와서 이 스크립트를 돌린다
#
#   curl -fsSL <이 파일 주소> | bash
#   또는  bash deploy/setup-oracle.sh
#
# 자세한 절차는 docs/DEPLOY.md 를 보세요.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rudtjr1106/poketdesktop.git}"
APP_DIR="${APP_DIR:-$HOME/poketdesktop}"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }

# ---------------------------------------------------------------- 0. 확인
if [ "$(id -u)" -eq 0 ]; then
  warn "root 로 돌리지 마세요. 일반 사용자(ubuntu / opc)로 실행하세요."
  exit 1
fi

. /etc/os-release
say "운영체제: $PRETTY_NAME"

# ---------------------------------------------------------------- 1. 스왑
# 무료 VM 은 메모리가 1GB 라서 도커 빌드 중에 죽을 수 있다.
if ! swapon --show | grep -q .; then
  say "스왑 2GB 만들기 (메모리 1GB VM 에서 빌드가 죽는 걸 막는다)"
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
  ok "설치 완료 (그룹 반영을 위해 나중에 다시 로그인해야 할 수 있습니다)"
else
  ok "도커가 이미 있음: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  say "docker compose 플러그인 설치"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq docker-compose-plugin
  else
    sudo dnf install -y docker-compose-plugin || true
  fi
fi

# ---------------------------------------------------------------- 3. 방화벽
# Oracle 이미지는 인스턴스 안쪽에도 방화벽이 걸려 있다.
# 콘솔에서 보안 목록만 열고 이걸 안 하면 "분명 열었는데 안 된다" 가 된다.
say "인스턴스 방화벽에서 80, 443 열기"
if command -v firewall-cmd >/dev/null 2>&1 && sudo firewall-cmd --state >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-port=80/tcp
  sudo firewall-cmd --permanent --add-port=443/tcp
  sudo firewall-cmd --reload
  ok "firewalld 에 규칙 추가"
else
  for port in 80 443; do
    if ! sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
      sudo iptables -I INPUT 1 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
    fi
  done
  if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save >/dev/null
  else
    sudo apt-get install -y -qq iptables-persistent >/dev/null 2>&1 || true
    sudo netfilter-persistent save >/dev/null 2>&1 || true
  fi
  ok "iptables 에 규칙 추가 (재부팅해도 남도록 저장)"
fi
warn "Oracle 콘솔의 [네트워킹 > VCN > 보안 목록] 에도 80, 443 인그레스 규칙이 있어야 합니다."

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
  read -rp "   도메인: " DOMAIN
  read -rp "   이메일 (인증서 만료 알림용): " EMAIL
  printf 'POKET_DOMAIN=%s\nACME_EMAIL=%s\n' "$DOMAIN" "$EMAIL" > .env
  ok ".env 저장"
else
  ok ".env 가 이미 있음: $(grep POKET_DOMAIN .env)"
fi

# ---------------------------------------------------------------- 6. 실행
say "빌드하고 띄우기 (처음이면 몇 분 걸립니다)"
docker compose -f docker-compose.prod.yml up -d --build

say "상태 확인"
sleep 8
docker compose -f docker-compose.prod.yml ps

DOMAIN=$(grep POKET_DOMAIN .env | cut -d= -f2)
echo
if curl -fsS --max-time 20 "https://$DOMAIN/api/health" >/dev/null 2>&1; then
  ok "https://$DOMAIN 정상 동작"
  curl -s "https://$DOMAIN/api/health"
  echo
  echo
  echo "   클라이언트 로그인 창의 '서버 주소' 에 이걸 넣으세요:"
  echo "      https://$DOMAIN"
else
  warn "아직 응답이 없습니다. 인증서 발급에 1~2분 걸리기도 합니다."
  echo "   확인:  docker compose -f docker-compose.prod.yml logs -f caddy"
  echo "   흔한 원인:"
  echo "     - 도메인이 이 VM 의 공인 IP 를 안 가리킴"
  echo "     - Oracle 콘솔 보안 목록에 80/443 인그레스 규칙이 없음"
fi
