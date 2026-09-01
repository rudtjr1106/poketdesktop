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

# 닉네임: 한글/영문/숫자와 _ - . 만. 앞뒤 공백과 연속 공백은 안 된다.
USERNAME_RE = re.compile(r"^[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ][0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ _.-]*$")
PIN_RE = re.compile(r"^[0-9]+$")


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
        return None, "닉네임은 %d~%d자여야 합니다." % (config.MIN_USERNAME,
                                                config.MAX_USERNAME)
    if not USERNAME_RE.match(name):
        return None, "닉네임에는 한글, 영문, 숫자와 _ - . 만 쓸 수 있습니다."
    if "  " in name:
        return None, "닉네임에 공백을 이어서 쓸 수 없습니다."
    return name, None


def check_password(pw):
    pw = pw or ""
    n = config.PIN_DIGITS
    if len(pw) != n or not PIN_RE.match(pw):
        return "비밀번호는 숫자 %d자리입니다." % n
    return None


def name_taken(name):
    return db.q1("SELECT id FROM users WHERE username=?", (name,)) is not None


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


# 마지막 접속 시각을 얼마나 자주 적을지(초).
# 인증된 요청마다 적으면 폴링이 촘촘해지는 순간 이게 제일 비싼 쿼리가
# 된다 - Turso 는 원격이라 쓰기 한 번이 왕복 한 번이다. 접속 여부를
# 판정하는 여유는 이 간격보다 훨씬 크게 잡아야 판정이 흔들리지 않는다.
TOUCH_EVERY = 30


def touch_session(token, ip, seen=None):
    """마지막으로 말을 건 시각을 갱신한다.

    seen 은 부르는 쪽이 이미 읽어 둔 세션 행의 last_seen 이다.
    넘겨주면 최근에 적었는지 조회 없이 판단해서, 대부분의 요청에서
    쓰기를 아예 건너뛴다.
    """
    if seen:
        last = parse_iso(seen)
        if last and (datetime.datetime.now(datetime.timezone.utc)
                     - last).total_seconds() < TOUCH_EVERY:
            return
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
        # Cloudflare 가 앞에 있으면 이게 가장 믿을 만하다. 클라이언트가 무엇을
        # 보내든 Cloudflare 가 덮어쓰기 때문이다. (Render 가 Cloudflare 뒤에 있다)
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            parts = [p.strip() for p in fwd.split(",") if p.strip()]
            # 맨 뒤는 '우리와 가장 가까운 프록시' 다. 우리 Caddy 처럼 헤더를
            # 덮어쓰는 구조에서는 그게 진짜 접속자다.
            # 그런데 Render 처럼 프록시가 여러 겹이면 맨 뒤가 내부 주소
            # (10.x) 라서 쓸모가 없다. 그럴 때는 사설 대역이 아닌 마지막
            # 값을 고른다 — 클라이언트가 앞에 끼워 넣은 가짜는 그 뒤의
            # 프록시들이 붙인 값에 밀려나므로 여기까지 오지 못한다.
            for part in reversed(parts):
                if not _is_private(part):
                    return part
            if parts:
                return parts[-1]
    return request.client.host if request.client else ""


def _is_private(raw):
    """사설/특수 대역인지. 진짜 접속자 주소일 리 없는 것들."""
    try:
        addr = ipaddress.ip_address((raw or "").strip())
    except ValueError:
        return True
    return (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_unspecified)


def ip_is_real(request):
    """지금 보이는 IP 가 '진짜 접속자의 IP' 인지.

    도커 데스크톱은 포트포워딩할 때 출발지 IP 를 브리지 게이트웨이(172.x.0.1)로
    바꿔버린다. 그 상태에서 IP 를 비교하면 모든 사용자가 같은 IP 로 보여서
    검사가 무의미해진다. 그래서 IP 를 진짜로 알 수 있을 때만 비교한다.

    - 리버스 프록시를 신뢰하도록 켜두고 X-Forwarded-For 가 실제로 왔다  -> 진짜
    - 도커/루프백 대역이 아니다 (도커 없이 직접 띄운 경우)                -> 진짜
    - 그 외                                                            -> 가짜
    """
    # 헤더가 왔다는 것만으로 '진짜 IP' 라고 볼 수 없다.
    # Render 는 프록시를 여러 겹 두는데 우리가 집어 든 값이 내부 주소
    # (10.24.x / 10.25.x) 일 수 있고, 그건 **요청마다 바뀐다.**
    # 그걸 세션에 묶으면 자동 로그인이 무작위로 풀린다.
    # 그래서 실제로 고른 주소를 보고 판단한다.
    return not _is_private(client_ip(request))


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
