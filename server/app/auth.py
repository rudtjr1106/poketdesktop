# -*- coding: utf-8 -*-
"""계정과 세션.

비밀번호는 PBKDF2-HMAC-SHA256 으로만 저장한다(평문 저장 안 함).
토큰은 원본을 주고 DB 에는 해시만 넣는다. DB 가 새어도 토큰을 못 쓴다.

자동 로그인은 '토큰 + 기기 + IP' 세 가지가 모두 맞아야 통과한다.
IP 는 보조 조건이지 인증 수단이 아니다 — 토큰이 없으면 IP 가 같아도 못 들어온다.
"""
import datetime
import hashlib
import hmac
import ipaddress
import re
import secrets

from . import config, db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 비밀번호
def hash_password(password, salt=None, iterations=None):
    salt = salt or secrets.token_bytes(16)
    iterations = iterations or config.PW_ITERATIONS
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return h, salt, iterations


def verify_password(password, pw_hash, salt, iterations):
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(h, pw_hash)


def check_username(name):
    name = (name or "").strip()
    if not (config.MIN_USERNAME <= len(name) <= config.MAX_USERNAME):
        return None, "아이디는 %d~%d자여야 합니다." % (config.MIN_USERNAME, config.MAX_USERNAME)
    if not USERNAME_RE.match(name):
        return None, "아이디는 영문/숫자/_.- 만 쓸 수 있습니다."
    return name, None


def check_password(pw):
    if len(pw or "") < config.MIN_PASSWORD:
        return "비밀번호는 %d자 이상이어야 합니다." % config.MIN_PASSWORD
    return None


# ---------------------------------------------------------------- 토큰
def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(user_id, ip, device, ip_real=False):
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    exp = now + datetime.timedelta(days=config.TOKEN_DAYS)
    db.run(
        "INSERT OR REPLACE INTO sessions"
        " (token_hash, user_id, ip, ip_real, device, created_at, last_seen, expires_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (token_hash(token), user_id, ip or "", int(bool(ip_real)), device or "",
         now.isoformat(), now.isoformat(), exp.isoformat()))
    return token, exp.isoformat()


def revoke_token(token):
    db.run("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))


def revoke_all(user_id):
    db.run("DELETE FROM sessions WHERE user_id=?", (user_id,))


def purge_expired():
    db.run("DELETE FROM sessions WHERE expires_at < ?", (now_iso(),))


def lookup_session(token):
    """토큰으로 세션 행을 찾는다. 만료면 지우고 None."""
    if not token:
        return None
    row = db.q1("SELECT * FROM sessions WHERE token_hash=?", (token_hash(token),))
    if not row:
        return None
    exp = parse_iso(row["expires_at"])
    if exp and exp < datetime.datetime.now(datetime.timezone.utc):
        db.run("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
        return None
    return row


def touch_session(token, ip):
    db.run("UPDATE sessions SET last_seen=?, ip=? WHERE token_hash=?",
           (now_iso(), ip or "", token_hash(token)))


def client_ip(request):
    """프록시를 신뢰하도록 설정했을 때만 프록시가 넣은 헤더를 본다.

    X-Real-IP 를 먼저 본다. 우리 프록시(Caddy)는 이 헤더를 항상 실제
    접속자 IP 로 '덮어쓰기' 때문에 위조할 수 없다.

    X-Forwarded-For 는 원래 여러 값이 쉼표로 이어지는 형식이라,
    프록시가 덧붙이기만 하면 클라이언트가 미리 넣어둔 가짜 값이 맨 앞에
    온다. 그래서 이걸 그대로 믿으면 IP 를 마음대로 속일 수 있다.
    deploy/Caddyfile 에서 이 헤더도 덮어쓰도록 해뒀고, 혹시 다른 프록시를
    쓰더라도 안전하도록 여기서는 **마지막 값**을 쓴다.
    (마지막 값 = 우리와 가장 가까운 프록시가 본 주소)
    """
    if config.TRUST_PROXY:
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            parts = [p.strip() for p in fwd.split(",") if p.strip()]
            if parts:
                return parts[-1]
    return request.client.host if request.client else ""


def ip_is_real(request):
    """지금 보이는 IP 가 '진짜 접속자의 IP' 인지.

    도커 데스크톱은 포트포워딩할 때 출발지 IP 를 브리지 게이트웨이(172.x.0.1)로
    바꿔버린다. 그 상태에서 IP 를 비교하면 모든 사용자가 같은 IP 로 보여서
    검사가 무의미해진다. 그래서 IP 를 진짜로 알 수 있을 때만 비교한다.

    - 리버스 프록시를 신뢰하도록 켜두고 X-Forwarded-For 가 실제로 왔다  -> 진짜
    - 도커/루프백 대역이 아니다 (도커 없이 직접 띄운 경우)                -> 진짜
    - 그 외                                                            -> 가짜
    """
    if config.TRUST_PROXY and (request.headers.get("x-real-ip")
                               or request.headers.get("x-forwarded-for")):
        return True
    raw = request.client.host if request.client else ""
    if not raw:
        return False
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if addr.is_loopback:
        return False
    # 도커 기본 브리지 대역(172.16.0.0/12)의 .1 게이트웨이 주소는 위장된 값이다
    if addr.version == 4 and addr in ipaddress.ip_network("172.16.0.0/12"):
        return not str(addr).endswith(".0.1")
    return True


def user_public(row, extra=None):
    d = {
        "id": row["id"],
        "username": row["username"],
        "createdAt": row["created_at"],
        "lastLogin": row["last_login"],
    }
    if extra:
        d.update(extra)
    return d
