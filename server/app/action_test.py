# -*- coding: utf-8 -*-
"""액션 배틀 시험 로비 (11/22) — 운영 옆에 따로 띄운 **시험 서버에서만** 켠다 (POKET_ACTION_TEST_KEY).

사용자: "이 기능 친구랑 테스트해볼 수 있게" · "main 에 합치는 게 아니라 테스트용이야". 지금 나가 있는 앱에는 '액션' 버튼이
없으므로, 두 사람이 브라우저만으로 들어오게 한다.

    GET  /action-test?k=<열쇠>              로비: '나' · '친구' 두 칸
    POST /action-test/go?k=<열쇠>&who=a|b   그 자리 시험 계정으로 판에 들어간다 (살아 있는 판이 없으면 새로 연다)
                                            -> 쿠키 poket_test=1 을 굽고 /action/play#m=..&t=.. 로 (303)

열쇠가 비어 있거나 틀리면 두 길 다 없는 것처럼 404. 쿠키는 운영 Caddy 가 이 브라우저의 요청을 시험 서버로 보내는 표다
(deploy/action-test/docker-compose.yml) - 앱은 쿠키를 안 보내므로 늘 운영 서버로 간다.

시험 계정 둘(시험나 · 시험친구)은 처음 들어올 때 만든다 - 로그인은 안 쓴다 (비밀번호는 아무도 모르는 무작위). 팀은 기술
모양을 고루 볼 수 있는 여섯 마리씩, 판에서 셋을 고른다. 친구 · 접속 · 앱 능력 검사는 건너뛴다 (로비가 곧 도전이다).
판 규칙 · 입장권 · 기록은 그대로 action 을 쓴다.
"""
import hmac
import html
import json
import random
import secrets
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from common import pokelogic as P

from . import action, auth, config, db, deps

router = APIRouter()

COOKIE = "poket_test"
COOKIE_SEC = 24 * 3600
NAMES = {"a": "시험나", "b": "시험친구"}
LABEL = {"a": "나", "b": "친구"}
# (종, 기술 넷, 이로치) - 근접 돌진 · 바람 · 불 · 번개 · 물 · 광선 · 내려찍기 · 강화 · 회복 · 방어를 다 볼 수 있게
TEAMS = {
    "a": [("GARCHOMP", ["DRAGONCLAW", "EARTHQUAKE", "STONEEDGE", "SWORDSDANCE"], 0),
          ("PIDGEOT", ["GUST", "HURRICANE", "AIRSLASH", "QUICKATTACK"], 0),
          ("CHARIZARD", ["FLAMETHROWER", "HEATWAVE", "FIREPUNCH", "ROOST"], 0),
          ("LUCARIO", ["AURASPHERE", "CLOSECOMBAT", "EXTREMESPEED", "PROTECT"], 0),
          ("GENGAR", ["SHADOWBALL", "SLUDGEBOMB", "THUNDERBOLT", "HYPNOSIS"], 1),
          ("SCIZOR", ["XSCISSOR", "BULLETPUNCH", "NIGHTSLASH", "SWORDSDANCE"], 0)],
    "b": [("BLASTOISE", ["HYDROPUMP", "ICEBEAM", "AQUAJET", "SURF"], 0),
          ("JOLTEON", ["THUNDERBOLT", "THUNDER", "SHADOWBALL", "QUICKATTACK"], 0),
          ("VENUSAUR", ["SOLARBEAM", "SLUDGEBOMB", "LEECHSEED", "PETALDANCE"], 0),
          ("TYRANITAR", ["STONEEDGE", "CRUNCH", "EARTHQUAKE", "DRAGONDANCE"], 0),
          ("GYARADOS", ["WATERFALL", "BOUNCE", "ICEFANG", "DRAGONDANCE"], 0),
          ("ALAKAZAM", ["PSYCHIC", "SHADOWBALL", "DAZZLINGGLEAM", "RECOVER"], 0)],
}

_lock = threading.Lock()


def _gate(k):
    key = config.ACTION_TEST_KEY
    if not key or not isinstance(k, str) or not hmac.compare_digest(k, key):
        raise HTTPException(404, "Not Found")


def ensure_users():
    """시험 계정 둘의 id {a, b}. 없으면 만들고 팀을 넣는다 (두 번 불러도 한 번만)."""
    with _lock:
        return {who: _user(who) for who in ("a", "b")}


def _user(who):
    name = NAMES[who]
    row = db.q1("SELECT id FROM users WHERE username=?", (name,))
    if row:
        return row["id"]
    h, salt, it = auth.hash_password(secrets.token_urlsafe(24))
    ts = auth.now_iso()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES (?,?,?,?,?,?,?,?,?)", (name, h, salt, it, 0, 0, ts, ts, "")).lastrowid
    dex, rng = deps.dex(), random.Random(uid)
    for slot, (species, moves, shiny) in enumerate(TEAMS[who]):
        mon = P.make_pokemon(dex.get(species), action.LEVEL, rng, force_shiny=bool(shiny))
        mid = db.insert_mon(uid, mon, ts)
        db.run("UPDATE pokemon SET moves=?, on_desktop=1, slot=? WHERE id=?", (json.dumps(moves), slot, mid))
    return uid


def enter(who):
    """who(a|b) 가 들어갈 판의 입장 주소. 살아 있는 판(열렸거나 싸우는 중)이 있으면 그 판에, 없으면 새로 연다."""
    if who not in NAMES:
        raise HTTPException(400, "나 · 친구 가운데 고르세요.")
    ids = ensure_users()
    row = action.my_match(ids["a"])
    if not row or row["state"] not in ("open", "fighting") or row["b_id"] != ids["b"]:
        try:
            row = action.open_direct(ids["a"], ids["b"])
        except ValueError as e:
            raise HTTPException(409, str(e))
    return action.ticket(ids[who], row["id"])[1]


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>액션 배틀 시험</title>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0f1420;color:#e8ecf5;
font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif}
main{width:min(560px,92vw);text-align:center}h1{font-size:28px;margin:0 0 8px}p{color:#a9b1c9;line-height:1.6}
form{display:inline-block;margin:10px}button{font:inherit;font-size:22px;padding:22px 34px;border-radius:14px;border:0;
cursor:pointer;background:#ffc043;color:#1b1d26;font-weight:700}button.b{background:#6bd3ff}small{color:#7d86a3}
</style></head><body><main>
<h1>액션 배틀 시험</h1>
<p>한 사람은 <b>나</b>, 다른 사람은 <b>친구</b>를 누르세요. 둘 다 들어오면 판이 시작됩니다.<br>
판이 끝나면 이 화면으로 돌아와 다시 누르면 새 판이 열립니다.</p>
<form method="post" action="/action-test/go?k=%(k)s&amp;who=a"><button>나로 입장</button></form>
<form method="post" action="/action-test/go?k=%(k)s&amp;who=b"><button class="b">친구로 입장</button></form>
<p><small>조작: 방향키 이동 · Z X C V 기술 · 1 2 3 교체 · Esc 기권 · H 도움말</small></p>
</main></body></html>"""


@router.get("/action-test", response_class=HTMLResponse)
def lobby(k: str = ""):
    _gate(k)
    return HTMLResponse(PAGE % {"k": html.escape(k, quote=True)}, headers={"Cache-Control": "no-store"})


@router.post("/action-test/go")
def go(request: Request, k: str = "", who: str = ""):
    _gate(k)
    path = enter(who)
    resp = RedirectResponse(path, status_code=303)
    resp.set_cookie(COOKIE, "1", max_age=COOKIE_SEC, path="/", secure=request.url.scheme == "https"
                    or request.headers.get("x-forwarded-proto") == "https", httponly=True, samesite="lax")
    resp.headers["Cache-Control"] = "no-store"
    return resp
