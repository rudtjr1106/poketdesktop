# -*- coding: utf-8 -*-
"""액션 배틀 소켓 검사 (2.6.0) - 두 사람이 실제로 한 판. 서버를 띄워 놓고 돌린다 (판 길이를 줄여서).

    서버: POKET_ACTION_PICK_SEC=1 POKET_ACTION_READY_SEC=0.5 POKET_ACTION_FIGHT_SEC=8 POKET_ACTION_GRACE=2
    python server/test_action_ws.py http://127.0.0.1:8791 /tmp/poket-action.db

두 번째 인자(DB 경로)는 판 줄 · 전적을 직접 보는 데만 쓴다. POKET_ACTION_GRACE 는 서버에 준 값과 같게 준다 (기본 2).
POKET_ACTION_JOIN_SEC 를 5~10 으로 서버와 같이 주면 '아무도 안 온 판' 도 본다 (기본 45초라 평소엔 건너뛴다).

못 박는 것:
  1. 두 사람이 앱(놀러 가기 소켓)으로 붙어 caps 를 알려야 걸 수 있다. 걸기 · 받기 알림이 바로 온다. /api/me 의 action.
  2. 입장권은 **첫 메시지로만** (주소 쿼리 · 머리말 없이), 한 번만. 틀리면 · 다시 쓰면 · 5초 안에 안 보내면 4401.
  3. 둘 다 들어오면 hello -> 고르기 -> 3 2 1 -> 싸움 스냅숏 (30번/초). 먼저 온 쪽은 wait. 누르면 cast 가 둘 다에게.
     시계 맞추기 png/pong · ping/pong. 상대의 체력 · 쿨타임 · PP · 기술 · 남이 맞은 데미지는 안 온다.
  4. disconnect_forfeit: 한쪽 창을 닫으면 GRACE 뒤 남은 쪽이 기권승 (over), 방이 닫히고 전적이 한 번.
  5. 기권(ff) -> 상대 승. 시간이 다 되면 over timeout. 끝난 판의 입장권은 409.
  6. 첫 메시지가 MSG_MAX 를 넘으면 읽지 않고 4401 (입장권은 안 쓴 채로 남는다).
  7. 상대를 기다리는 동안 기권하면 바로 기록 없이 접는다 (over winner null · cancel, aborted, 전적 없음).
"""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8791").rstrip("/")
DB = sys.argv[2] if len(sys.argv) > 2 else None
WSBASE = BASE.replace("https://", "wss://").replace("http://", "ws://")
GRACE = float(os.environ.get("POKET_ACTION_GRACE", "2"))
JOIN = float(os.environ.get("POKET_ACTION_JOIN_SEC", "45"))
AUTH_SEC = 5
LINGER = 3
OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:400]))


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}


def register(name):
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": "PIKACHU", "device": "t"})
    if st != 200:
        raise SystemExit("가입 실패 %s %s" % (st, r))
    return r.get("token") or r["session"]["token"], r["user"]["id"]


def befriend(asker_tok, asker_id, target_tok, target_name):
    st, r = call("POST", "/api/friends/request", {"username": target_name}, token=asker_tok)
    if st != 200:
        raise SystemExit("친구 신청 실패 %s %s" % (st, r))
    st, r = call("POST", "/api/friends/%d/accept" % asker_id, {}, token=target_tok)
    if st != 200:
        raise SystemExit("친구 수락 실패 %s %s" % (st, r))


def rows(q, args=()):
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    out = [dict(r) for r in c.execute(q, args)]
    c.close()
    return out


def visit_ws(token):
    return connect(WSBASE + "/ws/visit", additional_headers={"Authorization": "Bearer " + token}, open_timeout=10)


def action_ws():
    """머리말도 쿼리도 없이 붙는다 - 입장권은 첫 메시지로만."""
    return connect(WSBASE + "/ws/action", open_timeout=10)


def until(sock, pred, sec=4.0, seen=None):
    """pred 가 참인 메시지가 올 때까지 받는다 (지나간 것은 seen 에 쌓는다). 안 오면 None, 끊기면 ('closed', 번호)."""
    end = time.time() + sec
    while time.time() < end:
        try:
            raw = sock.recv(timeout=max(0.05, end - time.time()))
        except TimeoutError:
            return None
        except ConnectionClosed as e:
            return ("closed", e.rcvd.code if e.rcvd else 1006)
        msg = raw if raw == "pong" else json.loads(raw)
        if seen is not None:
            seen.append(msg)
        if pred(msg):
            return msg
    return None


def kind(t, **kw):
    """t 가 그것이고 kw 가 다 맞는 메시지."""
    return lambda m: isinstance(m, dict) and m.get("t") == t and all(m.get(k) == v for k, v in kw.items())


def cast_by_a(m):
    """a 가 기술을 쓴 이벤트가 실린 스냅숏."""
    return kind("s")(m) and any(e.get("e") == "cast" and e.get("w") == "a" for e in m.get("ev") or [])


def push(sock, s, mid):
    """놀러 가기 소켓으로 온 액션 알림 (다른 것은 건너뛴다)."""
    return until(sock, kind("action", s=s, id=mid))


def closed_with(sock, sec=4.0):
    """서버가 끊은 번호 (그 사이 오는 것은 버린다). 그 시간 안에 안 끊기면 None."""
    got = until(sock, lambda m: False, sec)
    return got[1] if isinstance(got, tuple) else None


def enter(ticket):
    """입장권으로 들어가 hello 를 받는다 -> (소켓, hello)."""
    s = action_ws()
    s.send(json.dumps({"t": "auth", "ticket": ticket}))
    return s, until(s, kind("hello"))


def open_match(ta, tb, b, va, vb):
    """a 가 b 에게 걸고 b 가 받는다 -> 판 번호."""
    st, r = call("POST", "/api/action/invite/%d" % b, {}, ta)
    mid = (r.get("match") or {}).get("id")
    if st != 200 or push(vb, "ask", mid) is None:
        raise SystemExit("도전 실패 %s %s" % (st, r))
    st, r = call("POST", "/api/action/%d/answer" % mid, {"accept": True}, tb)
    if st != 200 or push(va, "open", mid) is None:
        raise SystemExit("받기 실패 %s %s" % (st, r))
    return mid


def ticket(tok, mid):
    st, r = call("POST", "/api/action/%d/ticket" % mid, {}, tok)
    return st, r


def to_fight(ta, tb, mid):
    """둘 다 들어가 고르고 싸움이 시작될 때까지 -> (a 소켓, b 소켓, a 의 hello, a 가 받은 첫 싸움 스냅숏)."""
    sa, ha = enter(ticket(ta, mid)[1]["ticket"])
    sb, _hb = enter(ticket(tb, mid)[1]["ticket"])
    for s in (sa, sb):
        s.send(json.dumps({"t": "pick", "slots": [0]}))
    lim = ha["limits"]
    snap = until(sa, kind("s", ph="fight"), lim["pick"] + lim["ready"] + 3)
    return sa, sb, ha, snap


def main():
    if not DB:
        raise SystemExit("DB 경로를 주세요: python server/test_action_ws.py <주소> <DB>")
    tag = str(int(time.time() * 10))[-6:]
    na, nb = "액션소가" + tag, "액션소나" + tag
    ta, a = register(na)
    tb, b = register(nb)
    befriend(ta, a, tb, nb)
    va, vb = visit_ws(ta), visit_ws(tb)

    print("=== 앱이 알려야 걸 수 있다 ===")
    hello = until(va, kind("hello"))
    until(vb, kind("hello"))
    chk("놀러 가기 hello 의 push 에 action", hello and "action" in (hello.get("push") or []), hello)
    st, r = call("GET", "/api/action/can/%d" % b, token=ta)
    chk("상대 앱이 caps 를 안 알렸으면 못 건다", st == 200 and r["ok"] is False and "앱" in r["why"], r)
    for s in (va, vb):
        s.send(json.dumps({"t": "caps", "v": ["action"]}))
    time.sleep(0.3)
    st, r = call("GET", "/api/action/can/%d" % b, token=ta)
    chk("caps 를 알리면 걸 수 있다", st == 200 and r == {"ok": True, "why": ""}, r)

    print("\n=== 입장권 없이는 못 들어간다 ===")
    chk("틀린 입장권은 4401", closed_with(enter("nope")[0]) == 4401)
    silent = action_ws()
    t0 = time.time()
    chk("입장권을 안 보내면 %d초 뒤 4401" % AUTH_SEC, closed_with(silent, AUTH_SEC + 3) == 4401
        and time.time() - t0 >= AUTH_SEC - 0.5, time.time() - t0)

    print("\n=== 걸기 -> 받기 ===")
    st, r = call("POST", "/api/action/invite/%d" % b, {}, ta)
    mid = (r.get("match") or {}).get("id")
    chk("건다", st == 200 and r["match"]["state"] == "invited" and r["match"]["foe"]["id"] == b, (st, r))
    chk("  받는 사람에게 ask 가 바로 온다", push(vb, "ask", mid) is not None)
    st, r = call("GET", "/api/action", token=tb)
    chk("  알림을 받고 물으면 받은 도전이 보인다", st == 200 and [m["id"] for m in r["incoming"]] == [mid], r)
    st, r = call("POST", "/api/action/%d/answer" % mid, {"accept": True}, tb)
    chk("받으면 open", st == 200 and r["match"]["state"] == "open", (st, r))
    chk("  건 사람에게 open 이 바로 온다", push(va, "open", mid) is not None)
    st, me = call("GET", "/api/me", token=ta)
    chk("/api/me 의 action", st == 200 and me.get("action") == {"id": mid, "state": "open", "s": "open"},
        me.get("action"))

    print("\n=== 입장권 ===")
    st, ra = ticket(ta, mid)
    chk("입장권과 주소 (조각에만 - 쿼리스트링이 없다)", st == 200 and ra["path"] == "/action/play#m=%d&t=%s"
        % (mid, ra["ticket"]) and "?" not in ra["path"], ra)
    fat = action_ws()
    fat.send(json.dumps({"t": "auth", "ticket": ra["ticket"], "pad": "x" * 10000}))
    chk("첫 메시지가 너무 길면 (10000자) 읽지 않고 4401", closed_with(fat) == 4401)
    sa, ha = enter(ra["ticket"])
    chk("들어가면 hello (intro): 나는 a, 마당 1600x900", ha and ha.get("you") == "a" and ha.get("arena") == [1600, 900],
        ha)
    chk("  상대 팀은 보이지만 기술 · 도구는 없다", ha and ha["teams"]["b"] and all(
        "moves" not in m and "item" not in m for m in ha["teams"]["b"]) and ha["teams"]["a"][0].get("moves"), ha)
    chk("ticket_once: 같은 입장권을 다시 쓰면 4401", closed_with(enter(ra["ticket"])[0]) == 4401)
    chk("먼저 들어간 쪽은 wait 를 받는다", until(sa, kind("wait"), 2.5) is not None)
    sa.send("ping")
    chk("ping 에 pong", until(sa, lambda m: m == "pong", 2) == "pong")

    print("\n=== 고르기 -> 싸움 ===")
    sb, hb = enter(ticket(tb, mid)[1]["ticket"])
    chk("b 도 들어간다", hb and hb.get("you") == "b", hb)
    first = until(sa, kind("s"), 3)
    chk("둘 다 오면 고르기 스냅숏", first and first.get("ph") == "pick", first)
    for s in (sa, sb):
        s.send(json.dumps({"t": "pick", "slots": [0]}))
    lim = ha["limits"]
    seen_a = []
    snap = until(sa, kind("s", ph="fight"), lim["pick"] + lim["ready"] + 3, seen_a)
    chk("고르고 3 2 1 뒤 싸움 스냅숏", snap is not None, seen_a[-1:] if seen_a else None)
    snap = snap or {}
    me_f, foe_f = (snap.get("f") or {}).get("a") or {}, (snap.get("f") or {}).get("b") or {}
    chk("  내 것에는 체력 · 쿨타임 · PP", all(k in me_f for k in ("hp", "mhp", "cd", "pp")), me_f)
    chk("  상대 것에는 비율만 (체력 · 쿨타임 · PP 없음)", "hpr" in foe_f and not any(
        k in foe_f for k in ("hp", "mhp", "cd", "pp")), foe_f)
    moves = ha["teams"]["a"][0]["moves"]
    k = next((i for i, m in enumerate(moves) if m.get("ok")), 0)
    sa.send(json.dumps({"t": "in", "s": 1, "x": 0.5, "y": 0}))
    sa.send(json.dumps({"t": "act", "s": 2, "k": "m%d" % k}))
    chk("누르면 cast 이벤트 (%s)" % moves[k].get("key"), until(sa, cast_by_a, 3, seen_a) is not None, moves[k])
    chk("  상대에게도 같은 cast 가 간다", until(sb, cast_by_a, 3) is not None)
    chk("  내 입력 번호가 ack 로 돌아온다", until(sa, lambda m: kind("s")(m) and m.get("ack", 0) >= 2, 2, seen_a)
        is not None)
    sa.send(json.dumps({"t": "png", "c": 12.5}))
    pong = until(sa, kind("pong"), 2, seen_a)
    chk("시계 맞추기 png -> pong (c 그대로, ts 판 시각)", pong and pong["c"] == 12.5
        and isinstance(pong.get("ts"), (int, float)), pong)
    time.sleep(0.5)
    hits = [e for m in seen_a if isinstance(m, dict) for e in m.get("ev") or [] if e.get("e") == "hit"]
    chk("남이 맞은 데미지(hit.dmg)는 안 온다", all("dmg" not in e for e in hits if e.get("v") != "a"), hits[:5])

    print("\n=== disconnect_forfeit: 한쪽 창을 닫는다 ===")
    sb.close()
    t0 = time.time()
    over = until(sa, kind("over"), GRACE + 4)
    took = time.time() - t0
    chk("GRACE(%g초) 뒤 남은 쪽의 기권승 (%.1f초)" % (GRACE, took), over == {"t": "over", "winner": "a", "reason": "forfeit"}
        and took >= GRACE - 0.3, over)
    chk("  over 뒤 서버가 닫는다 (1000)", closed_with(sa, LINGER + 3) == 1000)
    chk("  둘 다에게 over 알림", push(va, "over", mid) is not None and push(vb, "over", mid) is not None)
    row = rows("SELECT * FROM action_match WHERE id=?", (mid,))[0]
    chk("  판은 done · a · forfeit, 팀은 지웠다", (row["state"], row["result"], row["reason"], row["data"])
        == ("done", "a", "forfeit", None), row)
    rec = rows("SELECT * FROM battle_record WHERE kind='action' AND user_id IN (?,?) ORDER BY user_id", (a, b))
    chk("  전적이 한 줄씩 (이긴 쪽 win)", [(r["user_id"], r["result"]) for r in rec] == [(a, "win"), (b, "lose")], rec)
    st, r = call("GET", "/api/action", token=ta)
    chk("  내 판이 없다", st == 200 and r == {"match": None, "incoming": []}, r)
    chk("  끝난 판의 입장권은 409", ticket(ta, mid)[0] == 409)

    print("\n=== 기권 ===")
    mid = open_match(ta, tb, b, va, vb)
    sa, sb, _ha, snap = to_fight(ta, tb, mid)
    chk("다시 한 판 (싸움까지)", snap is not None)
    sa.send(json.dumps({"t": "ff"}))
    chk("기권하면 상대 승", until(sb, kind("over"), 3) == {"t": "over", "winner": "b", "reason": "forfeit"})
    chk("  건 사람도 같은 over", until(sa, kind("over"), 3) == {"t": "over", "winner": "b", "reason": "forfeit"})
    for s in (sa, sb):
        closed_with(s, LINGER + 3)

    print("\n=== 시간이 다 되면 ===")
    mid = open_match(ta, tb, b, va, vb)
    sa, sb, ha, snap = to_fight(ta, tb, mid)
    over = until(sa, kind("over"), ha["limits"]["fight"] + 4)
    chk("아무것도 안 하면 시간 끝 (timeout)", over and over.get("reason") == "timeout"
        and over.get("winner") in ("a", "b", "draw"), over)
    for s in (sa, sb):
        closed_with(s, LINGER + 3)
    rec = rows("SELECT COUNT(*) n FROM battle_record WHERE kind='action' AND user_id=?", (a,))[0]["n"]
    chk("세 판, 전적 세 줄", rec == 3, rec)

    print("\n=== 상대를 기다리는 동안 기권 ===")
    mid = open_match(ta, tb, b, va, vb)
    sa, _ha = enter(ticket(ta, mid)[1]["ticket"])
    chk("먼저 들어간 쪽은 wait", until(sa, kind("wait"), 2.5) is not None)
    t0 = time.time()
    sa.send(json.dumps({"t": "ff"}))
    over = until(sa, kind("over"), 4)
    took = time.time() - t0
    chk("기다리는 동안 기권하면 바로 (%.1f초) 기록 없이 접는다" % took, over == {"t": "over", "winner": None,
                                                                 "reason": "cancel"} and took < 2, over)
    chk("  서버가 닫는다 (1000)", closed_with(sa, 3) == 1000)
    row = rows("SELECT state, reason FROM action_match WHERE id=?", (mid,))[0]
    chk("  aborted · cancel", (row["state"], row["reason"]) == ("aborted", "cancel"), row)
    chk("  이 판의 전적은 없다", rows("SELECT COUNT(*) n FROM battle_record WHERE kind='action' AND match_id=?",
                                    (mid,))[0]["n"] == 0)
    chk("  둘 다에게 over 알림", push(va, "over", mid) is not None and push(vb, "over", mid) is not None)
    chk("  b 는 이제 못 들어간다 (409)", ticket(tb, mid)[0] == 409)

    if JOIN <= 10:
        print("\n=== 아무도 안 온 판 ===")
        mid = open_match(ta, tb, b, va, vb)
        sa, _ha = enter(ticket(ta, mid)[1]["ticket"])
        over = until(sa, kind("over"), JOIN + 3)
        chk("한 사람만 오면 JOIN(%g초) 뒤 기록 없이 접는다" % JOIN, over == {"t": "over", "winner": None,
                                                                    "reason": "noshow"}, over)
        row = rows("SELECT state, reason FROM action_match WHERE id=?", (mid,))[0]
        chk("  aborted · noshow", (row["state"], row["reason"]) == ("aborted", "noshow"), row)
        chk("  전적은 그대로", rows("SELECT COUNT(*) n FROM battle_record WHERE kind='action' AND user_id=?",
                                   (a,))[0]["n"] == 3)

    for s in (va, vb):
        s.close()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
