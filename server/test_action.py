# -*- coding: utf-8 -*-
"""액션 배틀 (2.6.0) 서버 검사 — 도전 · 수락 · 입장권 · 겹침 · 기록 · 정리 · 웹 화면 내보내기.

    python server/test_action.py

서버를 띄우지 않는다 (임시 DB, test_live 와 같은 방식). 앱으로 나가는 알림(visit.push)은 가로채서 본다.
판 자체(소켓 · 30번/초 굴리기)는 server/test_action_ws.py 가 돌고 있는 서버로 본다.

못 박는 것:
  1. 친구 · 같은 길드 · 앱이 붙어 있고 액션 배틀을 아는 상대에게만 건다.
  2. 걸면 ask, 거절하면 declined, 거두면 gone, 받으면 open - 받는 순간 두 팀을 Lv.50 으로 읽어 둔다.
  3. 입장권은 그 판의 두 사람만, 한 번만, 60초 안에만 (ticket_once · ticket_owner).
  4. 실시간 배틀 · 챔피언리그 · 친선전과 겹치지 않는다 (exclusive_with_live).
  5. 끝난 판은 전적에 한 번만 남는다 (돈 · 점수는 안 움직인다). 서버를 다시 켜면 끝나지 않은 판은 기록 없이 aborted.
  6. 소켓 입력은 믿지 않는다: 이동 값을 자르고 모르는 것은 버리고, 1초에 90개(누름은 20개)까지만. hit.dmg 는 맞은 사람에게만.
     아주 큰 정수도 예외 없이 버리고, 입력이 터진 로그는 방마다 ERR_EVERY 에 한 번. 입장권 줄은 MSG_MAX 를 넘으면 읽지 않는다.
     상대를 기다리는 동안 기권하면 기록 없이 바로 접는다 (cancel).
  7. /action/play 는 index.html (no-cache), /action/static 의 .js 는 text/javascript. 파일이 없으면 404.
"""
import asyncio
import contextlib
import datetime
import io
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-action-")
WEB = os.path.join(TMP, "web")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_CHAMPION_START"] = "2020-01-01T00:00:00+09:00"
os.environ["POKET_ACTION_WEB"] = WEB                    # 아직 없는 곳 - 웹 화면이 없을 때 404 를 본다

from fastapi import HTTPException                                    # noqa: E402

from common.pokelogic import make_pokemon                            # noqa: E402

from app import action, action_routes, action_ws, champion, config, db, deps, friendly, items, live, visit   # noqa: E402

OK = FAIL = 0
TEAM = ("PIKACHU", "BULBASAUR", "CHARMANDER", "SQUIRTLE", "EEVEE", "MACHOP", "GEODUDE")
PUSHED = []


def _fake_push(uid, payload):
    PUSHED.append((uid, payload))


visit.push = _fake_push


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name, level=40, mons=7, app=True, caps=("action",)):
    """사람 하나. app=True 면 앱이 켜져 있다 (놀러 가기 소켓) - caps 는 그 앱이 아는 것."""
    now = live._iso()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,1000,?,?,'')",
                 (name, b"x", b"x", now, now)).lastrowid
    db.run("INSERT INTO sessions (token_hash, user_id, ip, device, created_at, last_seen, expires_at)"
           " VALUES (?,?,'','t',?,?,?)", ("tok-%d" % uid, uid, now, now, now))
    d = deps.dex()
    rng = random.Random(uid)
    for i, sp in enumerate(TEAM[:mons]):
        m = make_pokemon(d.get(sp), level, rng)
        db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
               " shiny, happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
               " VALUES (?,?,?,0,?,?,0,?,0,70,?,?,?,?,?,?,?)",
               (uid, m["species"], level, m["nature"], m.get("ability"), m.get("gender", "M"),
                json.dumps(m["ivs"]), json.dumps(m.get("evs", {})), json.dumps(m["moves"]),
                1 if i < 6 else 0, i, level, now))
    if app:
        app_on(uid, caps)
    return uid


def app_on(uid, caps=("action",)):
    c = visit.Conn(None, uid)
    visit._add(c)
    visit.set_caps(c, list(caps))
    return c


def befriend(a, b):
    now = live._iso()
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at, decided_at)"
           " VALUES (?,?,'accepted',?,?,?)", (min(a, b), max(a, b), a, now, now))


def guild_of(*uids):
    now = live._iso()
    gid = db.run("INSERT INTO guild (name, master_id, created_at) VALUES (?,?,?)",
                 ("길드%d" % uids[0], uids[0], now)).lastrowid
    for u in uids:
        db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,'member',?)",
               (u, gid, now))
    return gid


def pushes(uid):
    return [p for u, p in PUSHED if u == uid and p.get("t") == "action"]


def records(uid):
    return db.q("SELECT * FROM battle_record WHERE user_id=? ORDER BY id", (uid,))


def http(fn, *a):
    """라우트 함수를 부르고 (상태, 답). HTTPException 이면 그 번호."""
    try:
        return 200, fn(*a)
    except HTTPException as e:
        return e.status_code, e.detail


def ctx(uid):
    return {"user": {"id": uid}}


def raises(fn, *a, **kw):
    """던진 예외의 종류 (안 던지면 None)."""
    try:
        fn(*a, **kw)
    except Exception as e:                                  # noqa: BLE001
        return type(e)
    return None


def error(fn, *a):
    """던진 예외의 글 (안 던지면 빈 글)."""
    try:
        fn(*a)
    except Exception as e:                                  # noqa: BLE001
        return str(e)
    return ""


class Rec(object):
    """엔진(ActionBattle) 대신 받은 입력을 적는다 - 소켓 입력 거르기만 본다 (판은 test_action_ws)."""
    phase, t, boom = "fight", 1.25, False

    def __init__(self):
        self.calls = []

    def intro(self, side):
        return {"teams": {"a": [{"kr": "피카츄"}], "b": [{"kr": "이브이"}]}}

    def set_move(self, side, x, y, seq):
        self.calls.append(("move", side, x, y, seq))

    def press(self, side, key, seq):
        if self.boom:
            raise RuntimeError("엔진이 터졌다 (검사)")
        self.calls.append(("press", side, key, seq))

    def pick(self, side, slots):
        self.calls.append(("pick", side, slots))
        return True

    def forfeit(self, side):
        self.calls.append(("ff", side))


class FakeWS(object):
    """소켓 대신 - 첫 메시지(first)를 주고, 보낸 것 · 닫은 번호를 적는다."""

    def __init__(self, first=None):
        self.first, self.sent, self.closed = first, [], None

    async def receive_text(self):
        return self.first

    async def send_text(self, text):
        self.sent.append(text)

    async def close(self, code=1000):
        self.closed = code


class JsonSpy(object):
    """action_ws.json 대신 - loads 에 들어온 글의 길이를 적는다 (읽기 전에 거르는지 본다)."""
    seen = []
    dumps = staticmethod(json.dumps)

    @staticmethod
    def loads(s, *a, **kw):
        JsonSpy.seen.append(len(s))
        return json.loads(s, *a, **kw)


def asgi_get(app, path):
    """ASGI 앱에 GET 하나 (httpx 없이). (상태, 머리말 dict, 본문)."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        sent.append(m)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
             "headers": [(b"host", b"t")], "server": ("t", 80), "client": ("127.0.0.1", 1)}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], dict((k.decode().lower(), v.decode()) for k, v in start["headers"]), body


def main():
    db.init()

    print("=== 걸 수 있나 ===")
    a, b = mkuser("액션가"), mkuser("액션나")
    stranger = mkuser("액션남")
    chk("친구가 아니면 못 건다", "친구" in (action.can_invite(a, b) or ""), action.can_invite(a, b))
    befriend(a, b)
    chk("친구고 앱이 액션 배틀을 알면 걸 수 있다", action.can_invite(a, b) is None, action.can_invite(a, b))
    chk("자기 자신은 못 건다", "자기 자신" in (action.can_invite(a, a) or ""))
    chk("없는 사람", "없습니다" in (action.can_invite(a, 99999) or ""))
    off = mkuser("액션꺼짐", app=False)
    befriend(a, off)
    chk("오프라인 거절 (앱이 안 붙어 있다)", "접속" in (action.can_invite(a, off) or ""), action.can_invite(a, off))
    old = mkuser("액션옛앱", caps=())
    befriend(a, old)
    chk("능력 없는 상대 거절 (옛 앱)", "앱" in (action.can_invite(a, old) or ""), action.can_invite(a, old))
    app_on(old, ("action",))
    chk("  같은 사람이 새 앱으로도 붙어 있으면 된다", action.can_invite(a, old) is None, action.can_invite(a, old))
    g1, g2 = mkuser("액션길1"), mkuser("액션길2")
    guild_of(g1, g2)
    chk("같은 길드면 친구가 아니어도 된다", action.can_invite(g1, g2) is None, action.can_invite(g1, g2))
    empty = mkuser("액션빈손", mons=0)
    befriend(a, empty)
    chk("상대 팀이 없으면 못 건다", "포켓몬" in (action.can_invite(a, empty) or ""), action.can_invite(a, empty))

    print("=== 도전 -> 거절 ===")
    PUSHED.clear()
    row = action.invite(a, b)
    mid = row["id"]
    chk("도전이 생긴다 (a 가 건 쪽)", row["state"] == "invited" and row["a_id"] == a and row["b_id"] == b,
        dict(row))
    chk("받는 사람에게 ask", pushes(b) == [{"t": "action", "s": "ask", "id": mid}], pushes(b))
    chk("  건 사람에게는 안 간다", pushes(a) == [], pushes(a))
    sa, sb = action.state(a), action.state(b)
    chk("건 사람: match 에 내 도전 (mine)", sa["match"] and sa["match"]["id"] == mid and sa["match"]["mine"] is True
        and sa["match"]["state"] == "invited" and sa["incoming"] == [], sa)
    chk("받은 사람: incoming 에 하나, match 는 없다",
        sb["match"] is None and [m["id"] for m in sb["incoming"]] == [mid] and sb["incoming"][0]["mine"] is False, sb)
    m = sb["incoming"][0]
    chk("M 의 모양 (id state foe mine result reason created)",
        set(m) == {"id", "state", "foe", "mine", "result", "reason", "created"}
        and m["foe"] == {"id": a, "name": "액션가"}, m)
    chk("me 카드: 받은 사람은 ask, 건 사람은 wait",
        action.me_card(b) == {"id": mid, "state": "invited", "s": "ask"}
        and action.me_card(a) == {"id": mid, "state": "invited", "s": "wait"}, (action.me_card(a), action.me_card(b)))
    chk("걸어 둔 채로는 둘 다 또 못 건다", action.can_invite(a, old) is not None and action.can_invite(old, b) is not None)
    chk("남은 거절 못 한다", raises(action.answer, stranger, mid, False) is LookupError)
    PUSHED.clear()
    row = action.answer(b, mid, False)
    chk("거절하면 declined", row["state"] == "declined", row["state"])
    chk("건 사람에게 declined", pushes(a) == [{"t": "action", "s": "declined", "id": mid}], pushes(a))
    chk("다시 걸 수 있다", action.can_invite(a, b) is None, action.can_invite(a, b))
    chk("me 카드가 비었다", action.me_card(a) is None and action.me_card(b) is None)

    print("=== 건 사람이 거둔다 ===")
    mid = action.invite(a, b)["id"]
    PUSHED.clear()
    row = action.cancel(a, mid)
    chk("거두면 cancelled", row["state"] == "cancelled", row["state"])
    chk("받는 사람에게 gone", pushes(b) == [{"t": "action", "s": "gone", "id": mid}], pushes(b))
    PUSHED.clear()
    chk("끝난 도전을 또 거두면 ValueError, 알림 없음", raises(action.cancel, a, mid) is ValueError and PUSHED == [])

    print("=== 동시에 걸어도 하나만 ===")
    mid = action.invite(a, b)["id"]
    keep = action.can_invite
    action.can_invite = lambda *_a: None                    # 두 요청이 확인을 같이 지난 셈
    try:
        chk("확인을 같이 지나도 한 사람에게 살아 있는 줄은 하나", raises(action.invite, old, b) is ValueError
            and db.q1("SELECT COUNT(*) n FROM action_match WHERE b_id=? AND state='invited'", (b,))["n"] == 1)
    finally:
        action.can_invite = keep
    action.cancel(a, mid)

    print("=== 받기 -> 판이 열린다 ===")
    mid = action.invite(a, b)["id"]
    chk("건 사람은 수락 못 한다", raises(action.answer, a, mid, True) is ValueError)
    PUSHED.clear()
    row = action.answer(b, mid, True)
    chk("받으면 open", row["state"] == "open", row["state"])
    chk("건 사람에게 open", pushes(a) == [{"t": "action", "s": "open", "id": mid}], pushes(a))
    data = json.loads(row["data"])
    chk("두 팀을 읽어 둔다 (앞 6마리)", len(data["a"]) == 6 and len(data["b"]) == 6, (len(data["a"]), len(data["b"])))
    chk("전원 Lv.%d" % action.LEVEL, all(x["level"] == action.LEVEL for x in data["a"] + data["b"]),
        [x["level"] for x in data["a"]])
    chk("시드가 있다", isinstance(data.get("seed"), int), data.get("seed"))
    chk("me 카드: 둘 다 open", action.me_card(a)["s"] == "open" and action.me_card(b)["s"] == "open")
    chk("둘 다 match 로 본다", action.state(a)["match"]["id"] == mid and action.state(b)["match"]["id"] == mid)
    chk("열린 판에는 또 수락 못 한다", raises(action.answer, b, mid, True) is ValueError)
    chk("열린 판은 거둘 수 없다", raises(action.cancel, a, mid) is ValueError)

    print("=== 입장권 ===")
    t, path = action.ticket(a, mid, clock=1000.0)
    chk("입장권과 주소", t and path == "/action/play#m=%d&t=%s" % (mid, t), (t, path))
    chk("입장권은 조각(#)에만 - 쿼리스트링이 없다", "?" not in path)
    chk("쓰면 그 판 · 그 사람 · 그 쪽", action.redeem(t, clock=1001.0) == (mid, a, "a"))
    chk("ticket_once: 두 번째는 None", action.redeem(t, clock=1001.5) is None)
    chk("ticket_owner: 남의 판 입장권은 못 만든다", raises(action.ticket, stranger, mid) is PermissionError)
    st, _r = http(action_routes.ticket, mid, ctx(stranger))
    chk("  길은 403", st == 403, st)
    t2, _p = action.ticket(b, mid, clock=1000.0)
    chk("60초 지난 입장권은 None", action.redeem(t2, clock=1000.0 + config.ACTION_TICKET_SEC + 1) is None)
    t3, _p = action.ticket(b, mid, clock=2000.0)
    t4, _p = action.ticket(b, mid, clock=2001.0)
    chk("새 입장권을 받으면 앞의 것은 못 쓴다", action.redeem(t3, clock=2002.0) is None
        and action.redeem(t4, clock=2002.0) == (mid, b, "b"))
    chk("없는 판", raises(action.ticket, a, 99999) is LookupError)
    st, _r = http(action_routes.ticket, 99999, ctx(a))
    chk("  길은 404", st == 404, st)
    pend = action.invite(g1, g2)["id"]
    chk("아직 안 받은 도전에는 입장권이 없다", raises(action.ticket, g1, pend) is ValueError)
    st, _r = http(action_routes.ticket, pend, ctx(g1))
    chk("  길은 409", st == 409, st)
    action.cancel(g1, pend)

    print("=== 겹침 (exclusive_with_live) ===")
    x, y, z = mkuser("겹침가", level=50), mkuser("겹침나", level=50), mkuser("겹침다", level=50)
    befriend(x, y)
    befriend(x, z)
    befriend(y, z)
    live.accept(y, live.invite(x, y)["id"])
    chk("실시간 배틀 중이면 액션 도전을 못 건다", "진행 중" in (action.can_invite(x, z) or ""), action.can_invite(x, z))
    chk("실시간 배틀 중인 사람에게도 못 건다", "다른 배틀" in (action.can_invite(z, y) or ""), action.can_invite(z, y))
    st, _r = http(action_routes.invite, y, ctx(z))
    chk("  길은 409", st == 409, st)
    # 액션 판이 열려 있는 a · b (위) - 다른 대전이 막힌다
    befriend(a, z)
    befriend(b, z)
    chk("액션 판 중이면 실시간 배틀을 못 건다", "다른 배틀" in (live.can_invite(a, z) or ""), live.can_invite(a, z))
    chk("액션 판 중인 사람에게 실시간 배틀을 못 건다", "다른 배틀" in (live.can_invite(z, b) or ""),
        live.can_invite(z, b))
    chk("바로 여는 판(친선전 받기 · 챔피언리그)도 막힌다", "다른 배틀" in error(live.open_direct, z, a))
    for u in (a, z):
        db.run("INSERT OR IGNORE INTO champion_member (user_id, qualified_at) VALUES (?,?)", (u, live._iso()))
    chk("챔피언리그 기다리기 · 도전도 막힌다", "다른 배틀" in (champion.why_not(a) or ""), champion.why_not(a))
    chk("  액션 판 중인 사람에게 챔피언리그 도전도 막힌다", "다른 배틀" in error(champion.challenge, z, a),
        error(champion.challenge, z, a))
    guild_of(a, stranger)
    chk("길드 친선전 '상대 구함' 도 막힌다", "다른 배틀" in error(friendly.seek, a, True), error(friendly.seek, a, True))
    pend = action.invite(g1, g2)["id"]
    befriend(z, g2)
    chk("걸어 두기만 한 액션 도전도 다른 대전을 막는다 (실시간과 같다)", "다른 배틀" in (live.can_invite(z, g2) or ""),
        live.can_invite(z, g2))
    action.cancel(g1, pend)

    print("=== 끝난 판은 기록 한 번 ===")
    chk("open -> fighting", action.start_fight(mid) is True and action.get(mid)["state"] == "fighting")
    chk("  두 번째는 False", action.start_fight(mid) is False)
    chk("싸우는 중에도 입장권 (다시 붙기)", raises(action.ticket, a, mid) is None)
    money = (items.money(a), items.money(b))
    PUSHED.clear()
    ok = action.finish(mid, "a", "ko", {"a": 2, "b": 0}, {"a": "피카츄", "b": "꼬부기"}, 74)
    row = action.get(mid)
    chk("끝나면 done · 결과 · 까닭", ok and row["state"] == "done" and row["result"] == "a" and row["reason"] == "ko",
        dict(row))
    chk("  다 쓴 팀은 지운다 (용량)", row["data"] is None)
    ra, rb = records(a), records(b)
    chk("양쪽에 한 줄씩", len(ra) == 1 and len(rb) == 1, (len(ra), len(rb)))
    chk("종류 action · 승패가 반대", ra[0]["kind"] == "action" and ra[0]["result"] == "win" and rb[0]["result"] == "lose",
        (ra[0]["kind"], ra[0]["result"], rb[0]["result"]))
    chk("남은 마릿수 · 선봉", (ra[0]["my_left"], ra[0]["foe_left"], ra[0]["lead"], ra[0]["foe_lead"])
        == (2, 0, "피카츄", "꼬부기") and (rb[0]["my_left"], rb[0]["lead"]) == (0, "꼬부기"), dict(ra[0]))
    chk("건 사람만 started", ra[0]["started"] == 1 and rb[0]["started"] == 0)
    chk("turns 칸에 싸운 초", ra[0]["turns"] == 74 and rb[0]["turns"] == 74, (ra[0]["turns"], rb[0]["turns"]))
    chk("상금 · 점수 없음", ra[0]["reward"] == 0 and ra[0]["delta"] == 0 and ra[0]["rp_delta"] == 0)
    chk("돈이 그대로", (items.money(a), items.money(b)) == money)
    chk("둘 다에게 over", pushes(a) == [{"t": "action", "s": "over", "id": mid}]
        and pushes(b) == [{"t": "action", "s": "over", "id": mid}], (pushes(a), pushes(b)))
    chk("두 번 끝내도 전적이 안 는다", action.finish(mid, "b", "ko", {"a": 0, "b": 1}, {}) is False
        and len(records(a)) == 1 and action.get(mid)["result"] == "a")
    action._record(row, {"a": 2, "b": 0}, {})
    chk("  기록만 다시 불러도 안 는다", len(records(a)) == 1 and len(records(b)) == 1)
    m = action.public(action.get(mid), a)
    chk("M: 내 기준 승패", m["result"] == "win" and action.public(action.get(mid), b)["result"] == "lose"
        and m["reason"] == "ko", m)
    chk("끝난 판에는 입장권이 없다", raises(action.ticket, a, mid) is ValueError)
    chk("끝나면 다시 걸 수 있다", action.can_invite(a, b) is None, action.can_invite(a, b))
    chk("끝나면 실시간 배틀도 된다", live.can_invite(a, z) is None, live.can_invite(a, z))

    print("=== 비긴 판 ===")
    mid = action.answer(b, action.invite(a, b)["id"], True)["id"]
    action.start_fight(mid)
    action.finish(mid, "draw", "timeout", {"a": 1, "b": 1}, {})
    chk("무승부는 양쪽 다 draw", records(a)[-1]["result"] == "draw" and records(b)[-1]["result"] == "draw")

    print("=== 시간이 지나면 ===")
    later = live._now() + datetime.timedelta(seconds=config.ACTION_INVITE_SEC + 5)
    mid = action.invite(a, b)["id"]
    chk("오래된 도전은 (치우기 전에도) 걸린 것으로 안 본다", action.my_match(a, later) is None)
    PUSHED.clear()
    action.expire_old(later)
    chk("도전이 expired", action.get(mid)["state"] == "expired", action.get(mid)["state"])
    chk("  받는 사람에게 gone, 건 사람에게 over", pushes(b) == [{"t": "action", "s": "gone", "id": mid}]
        and pushes(a) == [{"t": "action", "s": "over", "id": mid}], (pushes(a), pushes(b)))
    mid = action.answer(b, action.invite(a, b)["id"], True)["id"]
    PUSHED.clear()
    action.expire_old(live._now() + datetime.timedelta(seconds=config.ACTION_JOIN_SEC + 1))
    chk("들어오기를 기다리는 동안은 안 접는다 (방이 자기 시계로 본다)", action.get(mid)["state"] == "open")
    action.expire_old(live._now() + datetime.timedelta(seconds=action.OPEN_TTL + 5))
    row = action.get(mid)
    chk("아무도 안 들어온 판은 기록 없이 aborted", row["state"] == "aborted" and row["reason"] == "noshow",
        (row["state"], row["reason"]))
    chk("  둘 다에게 over", len(pushes(a)) == 1 and len(pushes(b)) == 1, PUSHED)
    chk("  전적은 그대로", len(records(a)) == 2)

    print("=== 방이 다 찼다 ===")
    mid = action.invite(a, b)["id"]
    keep = config.ACTION_ROOMS
    config.ACTION_ROOMS = action.rooms_in_use()
    try:
        chk("방이 다 차면 받을 수 없다", raises(action.answer, b, mid, True) is ValueError)
        chk("  도전 단추도 흐리게", "방" in (action.can_invite(g1, g2) or ""), action.can_invite(g1, g2))
    finally:
        config.ACTION_ROOMS = keep
    chk("  자리가 나면 받는다", action.answer(b, mid, True)["state"] == "open")

    print("=== 재시작 정리 ===")
    pend = action.invite(g1, g2)["id"]
    action.start_fight(mid)
    PUSHED.clear()
    n = action.abort_all()
    chk("끝나지 않은 판이 전부 aborted", n == 2 and action.get(pend)["state"] == "aborted"
        and action.get(mid)["state"] == "aborted" and action.get(mid)["reason"] == "restart",
        (n, action.get(pend)["state"], action.get(mid)["state"]))
    chk("  기록 없음", len(records(a)) == 2 and records(g1) == [])
    chk("  끝난 판은 그대로", db.q1("SELECT COUNT(*) c FROM action_match WHERE state='done'")["c"] == 2)
    chk("  판에 붙은 팀도 지운다", action.get(mid)["data"] is None)
    chk("aborted 판은 끝낼 수 없다 (기록 없음)", action.finish(mid, "a", "ko", {"a": 1, "b": 0}, {}) is False
        and len(records(a)) == 2)

    print("=== 길 (HTTP) ===")
    st, r = http(action_routes.can, b, ctx(a))
    chk("GET can", st == 200 and r == {"ok": True, "why": ""}, r)
    st, r = http(action_routes.invite, b, ctx(a))
    chk("POST invite -> {match}", st == 200 and r["match"]["state"] == "invited", r)
    mid = r["match"]["id"]
    st, r = http(action_routes.invite, b, ctx(a))
    chk("  또 걸면 409", st == 409, st)
    st, r = http(action_routes.mine, ctx(b))
    chk("GET /api/action -> {match, incoming}", st == 200 and set(r) == {"match", "incoming"}
        and r["incoming"][0]["id"] == mid, r)
    st, r = http(action_routes.answer, 99999, action_routes.AnswerIn(accept=True), ctx(b))
    chk("없는 도전 답은 404", st == 404, st)
    st, r = http(action_routes.answer, mid, action_routes.AnswerIn(accept=True), ctx(b))
    chk("POST answer -> {match} open", st == 200 and r["match"]["state"] == "open", r)
    st, r = http(action_routes.ticket, mid, ctx(b))
    chk("POST ticket -> {ticket, path}", st == 200 and set(r) == {"ticket", "path"} and r["ticket"] in r["path"], r)
    st, r = http(action_routes.cancel, mid, ctx(a))
    chk("열린 판 거두기는 409", st == 409, st)

    print("=== 소켓 입력 (판 없이 - 엔진 대신 받은 것을 적는다) ===")
    eng = Rec()
    room = action_ws.Room(1, eng, 0.0)
    seat = action_ws.Seat(None)

    def say(obj, now=100.0, who="a"):
        return action_ws._on_text(room, who, seat, obj if isinstance(obj, str) else json.dumps(obj), now)
    say({"t": "in", "s": 3, "x": 2.5, "y": -0.5})
    say({"t": "in", "s": 4, "x": True, "y": 0})
    say('{"t": "in", "s": 5, "x": NaN, "y": 0}')
    chk("이동은 −1~1 로 잘라 넣고, 숫자가 아닌 것(참 · NaN)은 버린다", eng.calls == [("move", "a", 1.0, -0.5, 3)], eng.calls)
    eng.calls.clear()
    say({"t": "act", "s": 6, "k": "m9"})
    say({"t": "act", "s": -1, "k": "m0"})
    say({"t": "act", "s": 7, "k": "dodge"})
    chk("모르는 키 · 틀린 번호는 버린다", eng.calls == [("press", "a", "dodge", 7)], eng.calls)
    eng.calls.clear()
    say({"t": "pick", "slots": [0]})
    chk("고른 것은 선봉으로 적어 둔다", room.picks == {"a": [0]} and room.lead("a") == "피카츄" and room.lead("b") == "이브이",
        (room.picks, room.lead("a")))
    chk("png -> pong (c 그대로, ts 판 시각)", json.loads(say({"t": "png", "c": 12.5})) == {"t": "pong", "c": 12.5, "ts": 1.25})
    chk("ping -> pong", say("ping") == "pong")
    chk("너무 긴 줄은 버린다", say(json.dumps({"t": "png", "c": "x" * 600})) is None)
    seat = action_ws.Seat(None)
    eng.calls.clear()
    for i in range(30):
        say({"t": "act", "s": i, "k": "m0"}, now=200.0)
    chk("누름은 1초에 %d개까지" % action_ws.ACT_PER_SEC, len(eng.calls) == action_ws.ACT_PER_SEC, len(eng.calls))
    seat = action_ws.Seat(None)
    eng.calls.clear()
    for i in range(100):
        say({"t": "in", "s": i, "x": 0, "y": 0}, now=200.5)
    chk("메시지는 1초에 %d개까지 (넘는 것은 버린다)" % action_ws.IN_PER_SEC,
        len(eng.calls) == action_ws.IN_PER_SEC, len(eng.calls))
    eng.calls.clear()
    say({"t": "in", "s": 1, "x": 0, "y": 0}, now=201.6)
    chk("  1초가 지나면 다시 받는다", len(eng.calls) == 1, eng.calls)
    eng.boom = True
    chk("엔진이 입력에서 터져도 그 입력만 버린다 (사람을 내쫓지 않는다)", say({"t": "act", "s": 9, "k": "m1"}, now=203) is None)
    room.ended = True
    eng.calls.clear()
    say({"t": "ff"}, now=204)
    chk("끝난 판에는 아무것도 안 넣는다", eng.calls == [], eng.calls)
    hit = {"e": "hit", "w": "a", "v": "b", "dmg": 17, "hpr": 820}
    chk("hit.dmg 는 맞은 사람에게만", "dmg" not in action_ws._for(hit, "a") and action_ws._for(hit, "b")["dmg"] == 17
        and hit["dmg"] == 17, (action_ws._for(hit, "a"), hit))

    print("=== 아주 큰 정수 (JSON 은 400자리 정수도 읽는다) ===")
    eng = Rec()
    room = action_ws.Room(2, eng, 0.0)
    huge = 10 ** 400

    def quiet(m):
        try:
            return action_ws._apply(room, "a", m)
        except Exception as e:                              # noqa: BLE001
            return "던졌다 %s" % type(e).__name__
    bad = [{"t": "png", "c": huge}, {"t": "in", "s": 1, "x": huge, "y": 0}, {"t": "in", "s": 1, "x": 0, "y": -huge},
           {"t": "in", "s": huge, "x": 0, "y": 0}, {"t": "act", "s": huge, "k": "m0"}, {"t": "pick", "slots": [huge]}]
    got = [quiet(m) for m in bad]
    chk("png c · in x/y/s · act s · pick 칸이 아주 큰 정수면 예외 없이 버린다", got == [None] * len(bad) and eng.calls == []
        and room.picks == {}, (got, eng.calls))
    chk("  2**53 까지는 수로 본다 (이동은 1 로 자른다)", quiet({"t": "in", "s": 2, "x": 2 ** 53, "y": 0}) is None
        and eng.calls == [("move", "a", 1.0, 0.0, 2)], eng.calls)
    chk("  참 · 글자 · None 은 수가 아니다", not any(action_ws._finite(v) for v in (True, False, "1", None, [1], 2 ** 53 + 1,
                                                                                  float("inf"), float("nan"))))
    seat = action_ws.Seat(None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        reply = action_ws._on_text(room, "a", seat, '{"t":"png","c":%s}' % ("9" * 400), 300.0)
    chk("  줄로 와도 (400자리 < MSG_MAX) 답 없이 버리고 로그도 안 남긴다", reply is None and buf.getvalue() == "",
        (reply, buf.getvalue()[:200]))
    eng.boom = True
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for i in range(10):
            action_ws._on_text(room, "a", seat, json.dumps({"t": "act", "s": 10 + i, "k": "m1"}), 301.0 + i * 0.5)
    chk("엔진이 입력마다 터져도 로그는 방마다 %g초에 한 번" % action_ws.ERR_EVERY, buf.getvalue().count("[action]") == 1,
        buf.getvalue().count("[action]"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        action_ws._on_text(room, "a", seat, json.dumps({"t": "act", "s": 30, "k": "m1"}), 301.0 + action_ws.ERR_EVERY)
    chk("  %g초가 지나면 다시 남긴다" % action_ws.ERR_EVERY, buf.getvalue().count("[action]") == 1, buf.getvalue()[:200])

    print("=== 입장권 줄은 읽기 전에 길이부터 ===")
    ga, gb = mkuser("액션기가"), mkuser("액션기나")
    befriend(ga, gb)
    wmid = action.answer(gb, action.invite(ga, gb)["id"], True)["id"]
    t, _path = action.ticket(ga, wmid)
    JsonSpy.seen = []
    action_ws.json = JsonSpy
    try:
        fat = asyncio.run(action_ws._auth(FakeWS(json.dumps({"t": "auth", "ticket": t, "pad": "x" * 10000}))))
        lens = list(JsonSpy.seen)
        thin = asyncio.run(action_ws._auth(FakeWS(json.dumps({"t": "auth", "ticket": t}))))
    finally:
        action_ws.json = json
    chk("첫 메시지가 MSG_MAX(%d) 를 넘으면 JSON 으로 읽지도 않고 None (4401)" % action_ws.MSG_MAX,
        fat is None and lens == [], (fat, lens))
    chk("  그 입장권은 안 쓴 채로 남는다 (짧은 줄로 들어간다)", thin == (wmid, ga, "a"), thin)
    chk("  글자가 아닌 것도 None", asyncio.run(action_ws._auth(FakeWS(b"{}"))) is None)

    print("=== 상대를 기다리는 동안 기권 ===")

    async def ff_while_waiting():
        loop = asyncio.get_running_loop()
        room = action_ws.Room(wmid, action_ws._battle(action.get(wmid)), loop.time() + 3.0)
        ws = FakeWS()
        room.attach("a", action_ws.Seat(ws))
        task = asyncio.create_task(action_ws._run(room))
        await asyncio.sleep(0.2)
        t0 = loop.time()
        action_ws._on_text(room, "a", room.seats["a"], json.dumps({"t": "ff"}), t0)
        await asyncio.wait_for(task, 10)
        return ws, loop.time() - t0
    PUSHED.clear()
    ws, took = asyncio.run(ff_while_waiting())
    sent = [json.loads(x) for x in ws.sent]
    chk("먼저 들어온 쪽은 wait 를 받고 있었다", {"t": "wait"} in sent, sent)
    chk("기권하면 바로 (%.2f초) 기록 없이 접는다: over winner null · cancel" % took,
        sent[-1:] == [{"t": "over", "winner": None, "reason": "cancel"}] and took < 1.0, (took, sent[-3:]))
    chk("  닫는다 (1000)", ws.closed == 1000, ws.closed)
    row = action.get(wmid)
    chk("  판은 aborted · cancel", (row["state"], row["reason"]) == ("aborted", "cancel"), (row["state"], row["reason"]))
    chk("  전적은 없다", db.q1("SELECT COUNT(*) c FROM battle_record WHERE kind='action' AND match_id=?",
                              (wmid,))["c"] == 0 and records(ga) == [] and records(gb) == [])
    chk("  둘 다에게 over (앱의 카드가 닫힌다)", pushes(ga) == [{"t": "action", "s": "over", "id": wmid}]
        and pushes(gb) == [{"t": "action", "s": "over", "id": wmid}], PUSHED)

    print("=== 웹 화면 ===")
    from app import main
    st, _h, _b = asgi_get(main.app, "/action/play")
    chk("웹 화면이 없으면 404", st == 404, st)
    os.makedirs(os.path.join(WEB, "js"))
    with open(os.path.join(WEB, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><title>액션 배틀</title>")
    with open(os.path.join(WEB, "js", "main.js"), "w", encoding="utf-8") as f:
        f.write("export const x = 1;\n")
    with open(os.path.join(WEB, "action.css"), "w", encoding="utf-8") as f:
        f.write("body{}\n")
    st, h, body = asgi_get(main.app, "/action/play")
    chk("GET /action/play 는 index.html", st == 200 and "액션 배틀" in body.decode("utf-8")
        and h.get("content-type", "").startswith("text/html"), (st, h))
    chk("  no-cache", h.get("cache-control") == "no-cache", h)
    st, h, body = asgi_get(main.app, "/action/static/js/main.js")
    chk(".js 는 text/javascript", st == 200 and h.get("content-type", "").startswith("text/javascript")
        and body.startswith(b"export"), (st, h))
    chk("  고친 것이 바로 가게 no-cache", h.get("cache-control") == "no-cache", h)
    st, h, _b = asgi_get(main.app, "/action/static/action.css")
    chk(".css 는 text/css", st == 200 and h.get("content-type", "").startswith("text/css"), (st, h))
    st, _h, _b = asgi_get(main.app, "/action/static/../../t.db")
    chk("웹 화면 밖은 못 읽는다", st == 404, st)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
