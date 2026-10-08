# -*- coding: utf-8 -*-
"""길드 친선전 웹소켓 검사 (1.10.3). 서버를 띄워 놓고 돌린다.

    python server/test_friendly_ws.py http://127.0.0.1:8788 /tmp/poket-test.db

두 번째 인자(DB 경로)는 **길드를 만들 돈을 넣는 데만** 쓴다.

규칙(누가 받을 수 있나, 동시에 몇 판인가)은 test_friendly.py 가 본다. 여기서는 **진짜 서버와 진짜
웹소켓으로 셋이 붙었을 때** 그것이 서로에게 가는지를 본다.

  1. '상대 구함' 을 켜면 붙어 있는 길드원에게 지금 모습이 밀려온다 (채팅에도 한 줄).
  2. 길드원이 받으면 **실시간 배틀이 진짜로 열린다** (GET /api/live). 구한 사람에게는 '배틀 창을
     띄우라' 는 알림이 따로 가고, 길드원 모두에게 구경용 모습이 온다 (누가 무엇을 내보냈는지).
  3. 턴이 돌면 일어난 일이 밀려온다. 한쪽이 기권하면 끝난 판이 오고 목록에서 빠진다.
  4. 접속 중인 길드원에게 직접 신청하면 상대에게 바로 알림이 간다.
  5. **채팅의 카드**: 구하면 채팅에 카드 줄이 밀려오고, 받으면 **같은 줄**이 '진행 중' 으로, 끝나면
     결과로 바뀌었다는 소식(t=card)이 온다. 나중에 채팅을 받아 와도 그 모습 그대로다.
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
DB = sys.argv[2] if len(sys.argv) > 2 else None
WS = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/ws/guild"
OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


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


def sql(q, args=()):
    c = sqlite3.connect(DB, timeout=20)
    c.execute(q, args)
    c.commit()
    c.close()


def ws(token=None):
    head = {"Authorization": "Bearer " + token} if token else {}
    return connect(WS, additional_headers=head, open_timeout=10)


def recv(sock, sec=4.0):
    """그 시간 안에 온 것 하나 (dict). 안 오면 None, 끊겼으면 ('closed', 번호)."""
    try:
        return json.loads(sock.recv(timeout=sec))
    except TimeoutError:
        return None
    except ConnectionClosed as e:
        return ("closed", e.rcvd.code if e.rcvd else None)


def closed_with(sock, sec=4.0):
    """서버가 끊은 번호. 그 시간 안에 안 끊기면 None."""
    end = time.time() + sec
    while time.time() < end:
        try:
            sock.recv(timeout=0.3)
        except TimeoutError:
            continue
        except ConnectionClosed as e:
            return e.rcvd.code if e.rcvd else 1006
    return None


def until(sock, want, sec=5.0):
    """want(ev) 가 참인 것이 올 때까지 받는다. 그것과, 그때까지 받은 것 전부를 돌려준다."""
    seen, end = [], time.time() + sec
    while time.time() < end:
        ev = recv(sock, max(0.05, end - time.time()))
        if ev is None:
            break
        seen.append(ev)
        if isinstance(ev, dict) and want(ev):
            return ev, seen
        if isinstance(ev, tuple):
            break
    return None, seen


def drain(sock, sec=0.4):
    out = []
    while True:
        ev = recv(sock, sec)
        if ev is None or isinstance(ev, tuple):
            return out
        out.append(ev)


def main():
    if not DB:
        raise SystemExit("DB 경로를 주세요: python server/test_friendly_ws.py <주소> <DB>")
    tag = str(int(time.time() * 10))[-6:]
    ta, a = register("친선가" + tag)
    tb, b = register("친선나" + tag)
    tc, c = register("친선다" + tag)
    sql("UPDATE users SET money=60000 WHERE id=?", (a,))
    st, r = call("POST", "/api/guild", {"name": "친선" + tag, "intro": "", "mode": "open"}, ta)
    st, state = call("GET", "/api/guild", token=ta)
    gid = state["guild"]["id"]
    call("POST", "/api/guild/%d/join" % gid, {"message": ""}, tb)
    call("POST", "/api/guild/%d/join" % gid, {"message": ""}, tc)
    sa, sb, sc = ws(ta), ws(tb), ws(tc)
    for s in (sa, sb, sc):
        recv(s)
        drain(s, 0.3)

    print("=== 상대 구함 ===")
    st, v = call("GET", "/api/guild/friendly", token=tb)
    chk("처음에는 아무도 없다", st == 200 and v == {"seeking": [], "fights": [], "limit": 3}, (st, v))
    t0 = time.time()
    st, v = call("POST", "/api/guild/friendly/seek", {"on": True}, ta)
    ev, seen = until(sb, lambda e: e.get("t") == "friendly", 4)
    chk("켜면 붙어 있는 길드원에게 지금 모습이 밀려온다 (%.2f초)" % (time.time() - t0), st == 200 and ev is not None
        and [(s["id"], s["name"]) for s in ev["seeking"]] == [(a, "친선가" + tag)] and ev["limit"] == 3, ev)
    lines = [e["m"] for e in seen + drain(sb, 0.3) if e.get("t") == "chat" and e["m"].get("card")]
    line = lines[0]["id"] if lines else 0
    chk("  **길드 채팅에 카드 줄이 밀려온다** (카드를 모르는 옛 화면은 글만 본다)", len(lines) == 1 and lines[0]["system"]
        and "친선전 상대를 구합니다" in lines[0]["body"]
        and lines[0]["card"] == {"k": "friendly", "s": "seek", "a": {"id": a, "name": "친선가" + tag}}, lines)
    chk("  지금 모습에 그 줄 번호가 실린다", ev is not None and ev["seeking"][0].get("card") == line > 0, ev)
    drain(sa, 0.3)
    drain(sc, 0.3)

    print("\n=== 받기 -> 실시간 배틀 ===")
    st, r = call("POST", "/api/guild/friendly/accept/%d" % a, {}, tb)
    chk("받으면 판이 열린다 (받은 사람에게 그 판을 돌려준다)", st == 200 and r["match"]["state"] == "fighting", (st, r))
    live_ev, seen_a = until(sa, lambda e: e.get("t") == "live", 5)
    chk("**구한 사람에게 '배틀 창을 띄우라' 는 알림이 간다** (그쪽은 기다리기만 했다)", live_ev == {"t": "live"}, seen_a)
    fc, seen_c = until(sc, lambda e: e.get("t") == "friendly_fight", 6)
    f = (fc or {}).get("fight") or {}
    chk("구경꾼에게 구경용 모습이 온다: 두 사람, 나와 있는 포켓몬과 체력", fc is not None and f.get("over") is False
        and (f["a"]["id"], f["b"]["id"]) == (a, b) and f["a"]["mon"]["num"] > 0
        and f["a"]["mon"]["hp"] == f["a"]["mon"]["maxhp"] > 0, fc)
    texts = [e.get("text") for e in f.get("events") or []]
    sw = [e for e in f.get("events") or [] if e.get("t") == "switch"]
    chk("  일어난 일은 구경꾼이 읽을 글로 온다 (누가 내보냈는지, '상대' 없이)", texts and texts[0] == "친선가%s 님과 친선나%s 님의 승부!" % (tag, tag)
        and len(sw) == 2 and sw[0]["text"].startswith("친선가%s: 가랏! " % tag) and sw[0]["mon"]["num"] > 0
        and not any("상대" in (x or "") for x in texts), texts)
    moved = [e for e in seen_c if e.get("t") == "card"]
    chk("  **같은 카드가 '진행 중' 으로 바뀌었다는 소식이 온다** (채팅에 줄이 새로 서지 않는다)", len(moved) == 1 and moved[0]["id"] == line
        and moved[0]["card"].get("s") == "fight" and moved[0]["card"].get("mid") == f.get("id")
        and moved[0]["card"]["b"] == {"id": b, "name": "친선나" + tag} and f.get("card") == line
        and not [e for e in seen_c if e.get("t") == "chat"], (moved, f.get("card")))
    st, mine = call("GET", "/api/live", token=ta)
    m = (mine or {}).get("match") or {}
    chk("**실시간 배틀이 진짜로 열렸다** (GET /api/live)", st == 200 and m.get("state") == "fighting" and m.get("id") == f.get("id"))
    st, v = call("GET", "/api/guild/friendly", token=tc)
    chk("목록: 진행 중인 판에 올라가고 '상대 구함' 에서는 빠진다", [x["id"] for x in v["fights"]] == [f["id"]] and v["seeking"] == [], v)

    print("\n=== 턴이 돌고, 끝난다 ===")
    for s in (sa, sb, sc):
        drain(s, 0.3)
    mv = (m.get("battle") or {}).get("me", {}).get("moves") or []
    call("POST", "/api/live/act", {"kind": "move", "move": mv[0]["key"]}, ta)
    chk("한쪽만 고르면 아무것도 밀려오지 않는다 (장면이 그대로다)", not [e for e in drain(sc, 0.8) if e.get("t") == "friendly_fight"])
    st, mb = call("GET", "/api/live", token=tb)
    call("POST", "/api/live/act", {"kind": "move", "move": mb["match"]["battle"]["me"]["moves"][0]["key"]}, tb)
    f1, _s = until(sc, lambda e: e.get("t") == "friendly_fight", 6)
    chk("둘 다 고르면 턴이 돌고 일어난 일이 밀려온다", f1 is not None and f1["fight"]["turn"] == 1
        and any(e.get("t") == "move" and e.get("move") for e in f1["fight"]["events"]), f1)
    call("POST", "/api/live/act", {"kind": "forfeit"}, ta)
    over, seen = until(sc, lambda e: e.get("t") == "friendly_fight" and e["fight"].get("over"), 6)
    chk("한쪽이 기권하면 끝난 판이 온다 (누가 이겼는지)", over is not None and over["fight"].get("result") in ("a", "b"), over)
    after = seen + drain(sc, 0.6)
    chk("  끝난 뒤의 목록이 밀려온다 (진행 중인 판 없음)", any(e.get("t") == "friendly" and e["fights"] == [] for e in after), after)
    ended = [e for e in after if e.get("t") == "card" and e["card"].get("s") == "over"]
    chk("  **카드에 결과가 적힌다** (가가 기권했다 - 나 승)", len(ended) == 1 and ended[0]["id"] == line and ended[0]["card"].get("result") == "b"
        and "친선나%s 님 승리" % tag in (ended[0].get("body") or ""), ended)
    st, chat = call("GET", "/api/guild/chat", token=tc)
    kept = [x for x in (chat or {}).get("messages") or [] if x["id"] == line]
    chk("  나중에 채팅을 받아 와도 그 카드는 결과 그대로다", st == 200 and len(kept) == 1 and kept[0].get("card", {}).get("s") == "over"
        and kept[0]["card"].get("result") == "b" and kept[0]["system"], kept)

    print("\n=== 직접 신청 ===")
    drain(sc, 0.3)
    st, r = call("POST", "/api/guild/friendly/ask/%d" % c, {}, tb)
    ev, _s = until(sc, lambda e: e.get("t") == "live", 4)
    chk("접속 중인 길드원에게 신청하면(친구가 아니어도) 상대에게 바로 알림이 간다", st == 200 and r["match"]["state"] == "invited"
        and ev == {"t": "live"}, (st, r, ev))
    st, mc = call("GET", "/api/live", token=tc)
    chk("  상대에게는 평소의 초대로 보인다 (받아야 시작한다)", (mc.get("match") or {}).get("state") == "invited"
        and (mc["match"] or {}).get("foeName") == "친선나" + tag, mc.get("match"))
    call("POST", "/api/live/%d/answer" % mc["match"]["id"], {"accept": False}, tc)
    for s in (sa, sb, sc):
        s.close()

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
