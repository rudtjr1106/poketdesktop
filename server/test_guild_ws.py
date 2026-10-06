# -*- coding: utf-8 -*-
"""길드 웹소켓 검사 (1.10.0). 서버를 띄워 놓고 돌린다.

    python server/test_guild_ws.py http://127.0.0.1:8788 /tmp/poket-test.db

두 번째 인자(DB 경로)는 **길드를 만들 돈을 넣는 데만** 쓴다 (5만원을 벌려면 관장을
스무 번 이겨야 한다).

못 박는 것:

  1. 토큰이 없거나 틀리면, 길드가 없으면 끊는다 (4401 / 4404). 번호가 화면까지 간다.
  2. 붙으면 hello 가 오고, 누가 말을 보내면 **묻지 않아도** 새 줄이 온다.
     그 줄 번호는 폴링(GET /api/guild/chat)으로 받는 것과 같다.
  3. 사람이 들어오면 알림 줄과 '바뀌었다' 가 온다.
  4. 내보내지면 '나왔다' 가 오고 서버가 끊는다. 해산해도 마찬가지다.
  5. 한 사람이 너무 많이 붙으면 끊는다 (4429). ping 에는 pong.
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


def main():
    if not DB:
        raise SystemExit("DB 경로를 주세요: python server/test_guild_ws.py <주소> <DB>")
    tag = str(int(time.time() * 10))[-6:]
    ta, a = register("웹길마" + tag)
    tb, b = register("웹길원" + tag)
    tc, _c = register("웹밖" + tag)
    sql("UPDATE users SET money=60000 WHERE id=?", (a,))

    print("=== 못 붙는 경우 ===")
    chk("토큰이 없으면 4401", closed_with(ws()) == 4401)
    chk("토큰이 틀리면 4401", closed_with(ws("nope")) == 4401)
    chk("길드가 없으면 4404", closed_with(ws(tc)) == 4404)

    st, r = call("POST", "/api/guild", {"name": "웹단" + tag, "intro": "", "mode": "open"}, ta)
    chk("길드를 만든다", st == 200, r)
    st, state = call("GET", "/api/guild", token=ta)
    gid = state["guild"]["id"]

    print("\n=== 붙기 ===")
    sa = ws(ta)
    hello = recv(sa)
    st, hist = call("GET", "/api/guild/chat", token=ta)
    chk("붙으면 hello: 내 번호·길드·마지막 줄 번호", isinstance(hello, dict) and hello.get("t") == "hello"
        and hello.get("userId") == a and hello.get("guild") == gid and hello.get("last") == hist["last"],
        (hello, hist.get("last")))
    sa.send("ping")
    try:
        pong = sa.recv(timeout=3)
    except Exception as e:                                  # noqa: BLE001
        pong = repr(e)
    chk("ping 에 pong", pong == "pong", pong)
    chk("아무 일도 없으면 아무것도 안 온다", recv(sa, 0.8) is None)

    print("\n=== 새 줄이 밀려온다 ===")
    t0 = time.time()
    st, r = call("POST", "/api/guild/chat", {"body": "웹소켓으로 가나요"}, ta)
    ev = recv(sa, 3)
    took = time.time() - t0
    chk("말을 보내면 묻지 않아도 온다 (%.2f초)" % took, isinstance(ev, dict) and ev.get("t") == "chat"
        and ev["m"]["body"] == "웹소켓으로 가나요" and ev["m"]["userId"] == a
        and ev["m"]["system"] is False and took < 1.5, ev)
    st, hist = call("GET", "/api/guild/chat?after=%d" % hello["last"], token=ta)
    chk("줄 번호가 폴링으로 받는 것과 같다", isinstance(ev, dict) and [m["id"] for m in hist["messages"]] == [ev["m"]["id"]]
        and r.get("id") == ev["m"]["id"], (hist["messages"], ev))

    print("\n=== 사람이 들어오면 ===")
    call("POST", "/api/guild/%d/join" % gid, {"message": ""}, tb)
    e1, e2 = recv(sa, 3), recv(sa, 3)
    chk("알림 줄과 '바뀌었다' 가 온다", isinstance(e1, dict) and isinstance(e2, dict)
        and e1.get("t") == "chat" and e1["m"]["system"] is True and "들어왔습니다" in e1["m"]["body"]
        and e2 == {"t": "changed"}, (e1, e2))
    sb = ws(tb)
    chk("새 길드원도 붙는다", (recv(sb) or {}).get("t") == "hello")
    call("POST", "/api/guild/chat", {"body": "둘 다 받나요"}, tb)
    ea, eb = recv(sa, 3), recv(sb, 3)
    chk("한 사람이 말하면 둘 다 받는다", isinstance(ea, dict) and isinstance(eb, dict)
        and ea.get("m", {}).get("body") == "둘 다 받나요" and ea == eb, (ea, eb))

    print("\n=== 너무 많이 붙으면 ===")
    more = [ws(ta), ws(ta)]
    hellos = [recv(x) for x in more]
    chk("한 사람이 셋까지는 붙는다", all(isinstance(h, dict) and h.get("t") == "hello" for h in hellos), hellos)
    chk("넷째는 4429 로 끊는다", closed_with(ws(ta)) == 4429)
    for x in more:
        x.close()
    time.sleep(0.5)

    print("\n=== 내보내지면 ===")
    st, r = call("POST", "/api/guild/members/%d/kick" % b, {}, ta)
    eb = recv(sb, 3)
    chk("내보내진 사람에게 '나왔다' 가 온다", eb == {"t": "left"}, eb)
    chk("  그리고 서버가 끊는다", closed_with(sb, 3) is not None)
    e1, e2 = recv(sa, 3), recv(sa, 3)
    chk("남은 사람에게는 알림 줄과 '바뀌었다'", isinstance(e1, dict) and "내보내졌습니다" in e1.get("m", {}).get("body", "")
        and e2 == {"t": "changed"}, (e1, e2))
    chk("내보내진 사람은 다시 못 붙는다 (4404)", closed_with(ws(tb)) == 4404)

    print("\n=== 해산하면 ===")
    call("DELETE", "/api/guild", token=ta)
    ev = recv(sa, 3)
    chk("'나왔다' 가 오고 끊긴다", ev == {"t": "left"} and closed_with(sa, 3) is not None, ev)
    st, r = call("GET", "/api/guild/chat", token=ta)
    chk("폴링 길도 길드가 없다고 답한다", st == 200 and r.get("guild") is None, r)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
