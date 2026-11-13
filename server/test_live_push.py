# -*- coding: utf-8 -*-
"""실시간 배틀 초대가 소켓으로 오는지 (2.5.0). 서버를 띄워 놓고 돌린다.

    python server/test_live_push.py http://127.0.0.1:8788

예전에는 친구 탭을 열어 둔 사람마다 4초에 한 번씩 GET /api/live 를 물었다 (서버 일의 3분의 1이 넘었다).
이제 서버가 놀러 가기 소켓(/ws/visit - 앱이 켜져 있는 동안 늘 붙어 있다)으로 그 사람에게만 민다.
판은 싣지 않는다 - 받은 앱이 /api/live 를 한 번 묻는다.

못 박는 것:

  1. hello 에 push=["live"] - 앱은 이걸 보고서야 폴링을 멈춘다 (옛 서버에 붙으면 예전처럼 묻는다).
  2. 걸면 받는 사람에게 ask, 거절하면 건 사람에게 declined, 건 사람이 거두면 받는 사람에게 gone,
     받으면 건 사람에게 open. 모두 그 판 번호가 같이 간다.
  3. 상관없는 사람에게는 아무것도 안 간다.
  4. 알림을 받고 물으면 그 판이 그대로 보인다 (알림과 /api/live 가 어긋나지 않는다).
"""
import json
import sys
import time
import urllib.error
import urllib.request

from websockets.sync.client import connect

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
WS = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/ws/visit"
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


def befriend(asker_tok, asker_id, target_tok, target_name):
    st, r = call("POST", "/api/friends/request", {"username": target_name}, token=asker_tok)
    if st != 200:
        raise SystemExit("친구 신청 실패 %s %s" % (st, r))
    st, r = call("POST", "/api/friends/%d/accept" % asker_id, {}, token=target_tok)
    if st != 200:
        raise SystemExit("친구 수락 실패 %s %s" % (st, r))


def ws(token):
    return connect(WS, additional_headers={"Authorization": "Bearer " + token}, open_timeout=10)


def recv(sock, want="live", timeout=4.0):
    """t 가 want 인 것이 올 때까지 받는다 (다른 것은 버린다). 안 오면 None."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            raw = sock.recv(timeout=max(0.05, end - time.time()))
        except TimeoutError:
            return None
        if raw == "pong":
            continue
        msg = json.loads(raw)
        if want is None or msg.get("t") == want:
            return msg
    return None


def main():
    tag = str(int(time.time() * 10))[-6:]
    na, nb, nc = "알림가" + tag, "알림나" + tag, "알림다" + tag
    ta, a = register(na)
    tb, b = register(nb)
    tc, c = register(nc)
    befriend(ta, a, tb, nb)
    befriend(tc, c, ta, na)          # c 는 a 의 친구지만 이 판과는 상관없다
    sa, sb, sc = ws(ta), ws(tb), ws(tc)

    print("=== hello ===")
    hellos = [recv(s, "hello") for s in (sa, sb, sc)]
    chk("붙으면 hello 에 push=['live'] (앱은 이걸 보고 폴링을 멈춘다)",
        all(h and "live" in (h.get("push") or []) for h in hellos), hellos)
    chk("검사 서버는 최신 앱 판을 모른다 (깃허브를 안 본다) - latest 가 없다",
        all(h and "latest" not in h for h in hellos), hellos)

    print("\n=== 걸기 -> 거절 ===")
    t0 = time.time()
    st, r = call("POST", "/api/live/invite/%d" % b, {}, ta)
    mid = r.get("id")
    ev = recv(sb)
    chk("걸면 받는 사람에게 ask 가 바로 온다 (%.2f초)" % (time.time() - t0), st == 200 and ev == {"t": "live", "s": "ask", "id": mid},
        (st, r, ev))
    st, mine = call("GET", "/api/live", token=tb)
    chk("  알림을 받고 물으면 그 초대가 보인다", st == 200 and (mine.get("match") or {}).get("id") == mid
        and mine["match"]["state"] == "invited", mine)
    chk("  건 사람에게는 안 간다", recv(sa, timeout=0.5) is None)
    st, r = call("POST", "/api/live/%d/answer" % mid, {"accept": False}, tb)
    ev = recv(sa)
    chk("거절하면 건 사람에게 declined", st == 200 and ev == {"t": "live", "s": "declined", "id": mid}, (st, ev))

    print("\n=== 걸기 -> 건 사람이 거두기 ===")
    st, r = call("POST", "/api/live/invite/%d" % b, {}, ta)
    mid = r.get("id")
    chk("다시 걸면 다시 ask", st == 200 and recv(sb) == {"t": "live", "s": "ask", "id": mid}, (st, r))
    st, r = call("POST", "/api/live/%d/answer" % mid, {"accept": False}, ta)
    ev = recv(sb)
    chk("건 사람이 거두면 받는 사람에게 gone", st == 200 and ev == {"t": "live", "s": "gone", "id": mid}, (st, ev))
    chk("  거둔 사람에게는 안 간다", recv(sa, timeout=0.5) is None)
    st, r = call("POST", "/api/live/%d/answer" % mid, {"accept": False}, ta)
    chk("  이미 끝난 초대를 또 거둬도 다시 밀지 않는다", st == 409 and recv(sb, timeout=0.5) is None, (st, r))

    print("\n=== 걸기 -> 받기 ===")
    st, r = call("POST", "/api/live/invite/%d" % b, {}, ta)
    mid = r.get("id")
    chk("걸면 ask", st == 200 and recv(sb) == {"t": "live", "s": "ask", "id": mid}, (st, r))
    t0 = time.time()
    st, r = call("POST", "/api/live/%d/answer" % mid, {"accept": True}, tb)
    ev = recv(sa)
    chk("받으면 건 사람에게 open 이 바로 온다 (%.2f초) - 3초 폴링을 기다리지 않는다" % (time.time() - t0),
        st == 200 and r.get("state") == "fighting" and ev == {"t": "live", "s": "open", "id": mid}, (st, r, ev))
    st, mine = call("GET", "/api/live", token=ta)
    chk("  알림을 받고 물으면 판이 열려 있다", st == 200 and (mine.get("match") or {}).get("id") == mid
        and mine["match"]["state"] == "fighting", mine)
    chk("  받은 사람에게는 안 간다 (답으로 판을 받았다)", recv(sb, timeout=0.5) is None)
    call("POST", "/api/live/act", {"kind": "forfeit"}, ta)

    print("\n=== 상관없는 사람 ===")
    chk("a 의 친구 c 에게는 아무것도 안 갔다", recv(sc, timeout=0.5) is None)

    for s in (sa, sb, sc):
        s.close()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
