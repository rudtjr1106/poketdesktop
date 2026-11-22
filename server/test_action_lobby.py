# -*- coding: utf-8 -*-
"""액션 배틀 시험 로비 검사 (11/22, server/app/action_test.py) - 서버 없이 앱 코드를 바로 부른다.

    python server/test_action_lobby.py

못 박는 것:
  1. 열쇠가 없거나 틀리면 로비 · 들어가기 둘 다 404 (있는 줄도 모르게). 맞으면 로비 화면에 두 칸.
  2. 처음 들어가면 시험 계정 둘을 만들고 여섯 마리씩 데리고 다니게 한다 (두 번 불러도 한 번만).
  3. 나 → 판이 열리고 (도전 · 받기 없이) 입장 주소. 친구 → 같은 판, 친구 쪽 입장권.
  4. 들어가기는 쿠키 poket_test=1 을 굽고 303 으로 /action/play#m=..&t=.. (입장권은 주소 조각에만).
  5. 판이 끝나면 다음 들어가기는 새 판. 실시간 배틀 중이면 409. 나 · 친구가 아니면 400.
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-action-lobby-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ.pop("POKET_ACTION_TEST_KEY", None)

from fastapi import HTTPException                                    # noqa: E402

from app import action, action_test, config, db, live, visit         # noqa: E402

OK = FAIL = 0
KEY = "test-key-123"
visit.push = lambda uid, payload: None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def status(fn, *a, **kw):
    """HTTPException 이면 그 번호, 아니면 None."""
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code
    return None


def req(https=True):
    return types.SimpleNamespace(url=types.SimpleNamespace(scheme="http"),
                                 headers={"x-forwarded-proto": "https" if https else "http"})


def frag(path):
    """'/action/play#m=3&t=xx' -> (3, 'xx')."""
    head, _, tail = path.partition("#")
    kv = dict(p.split("=", 1) for p in tail.split("&"))
    return head, int(kv["m"]), kv["t"]


def main():
    db.init()

    print("=== 열쇠 ===")
    config.ACTION_TEST_KEY = ""
    chk("열쇠가 없으면 로비 404", status(action_test.lobby, k="") == 404)
    chk("  열쇠를 넣어도 404 (서버에 열쇠가 없다)", status(action_test.lobby, k=KEY) == 404)
    chk("  들어가기도 404", status(action_test.go, req(), k=KEY, who="a") == 404)
    config.ACTION_TEST_KEY = KEY
    chk("틀린 열쇠 404", status(action_test.lobby, k="nope") == 404)
    page = action_test.lobby(k=KEY)
    body = page.body.decode()
    chk("맞는 열쇠 → 로비 (나 · 친구 두 칸, 열쇠는 그 칸의 주소에)", page.status_code == 200 and "나로 입장" in body
        and "친구로 입장" in body and "k=%s&amp;who=a" % KEY in body, body[:200])
    chk("  저장하지 않게", page.headers.get("cache-control") == "no-store")
    chk("  들어가기도 틀린 열쇠면 404", status(action_test.go, req(), k="nope", who="a") == 404)

    print("=== 처음 들어가기: 계정 · 팀 · 판 ===")
    chk("나 · 친구가 아니면 400", status(action_test.go, req(), k=KEY, who="c") == 400)
    resp = action_test.go(req(), k=KEY, who="a")
    loc = resp.headers["location"]
    head, mid, ta = frag(loc)
    chk("303 으로 /action/play#m=..&t=.. (입장권은 조각에만)", resp.status_code == 303 and head == "/action/play", loc)
    cookie = resp.headers.get("set-cookie", "")
    chk("쿠키 poket_test=1 (하루 · 경로 / · https 면 secure · httponly · lax)",
        "poket_test=1" in cookie and "Max-Age=86400" in cookie and "Path=/" in cookie and "Secure" in cookie
        and "HttpOnly" in cookie and "SameSite=lax" in cookie, cookie)
    got = action.redeem(ta)
    ids = action_test.ensure_users()
    chk("나의 입장권은 a 쪽", got is not None and got[:2] == (mid, ids["a"]) and got[2] == "a", got)
    again = action_test.go(req(https=False), k=KEY, who="a")
    chk("  http 면 secure 를 안 붙인다 · 다시 누르면 같은 판의 새 입장권",
        "Secure" not in again.headers.get("set-cookie", "") and frag(again.headers["location"])[1] == mid)
    users = db.q("SELECT id, username FROM users ORDER BY id")
    chk("시험 계정 둘 (시험나 · 시험친구)", [u["username"] for u in users] == ["시험나", "시험친구"], users)
    chk("  두 번 불러도 한 번만", action_test.ensure_users() == ids and len(db.q("SELECT id FROM users")) == 2)
    team = db.q("SELECT species, moves, slot FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot", (ids["a"],))
    chk("  여섯 마리를 데리고 다닌다 (기술은 정한 대로)", len(team) == 6 and team[0]["species"] == "GARCHOMP"
        and "DRAGONCLAW" in team[0]["moves"], [dict(t) for t in team][:2])
    row = action.get(mid)
    chk("판이 열렸다 (도전 · 받기 없이 state=open, 팀은 Lv.50 여섯씩)", row["state"] == "open"
        and (row["a_id"], row["b_id"]) == (ids["a"], ids["b"]), dict(row))

    print("=== 친구: 같은 판 ===")
    _, mid_b, tb = frag(action_test.go(req(), k=KEY, who="b").headers["location"])
    got = action.redeem(tb)
    chk("친구는 같은 판, b 쪽 입장권", mid_b == mid and got is not None and got[2] == "b", (mid_b, mid, got))
    action.start_fight(mid)
    _, mid_c, _ = frag(action_test.go(req(), k=KEY, who="a").headers["location"])
    chk("싸우는 중에 다시 누르면 그 판에 다시 들어간다 (창이 닫혔을 때)", mid_c == mid, (mid_c, mid))

    print("=== 끝난 뒤 · 막힘 ===")
    action.finish(mid, "a", "ko", {"a": 2, "b": 0}, {"a": "한카리아스", "b": "거북왕"}, 40)
    _, mid_d, _ = frag(action_test.go(req(), k=KEY, who="b").headers["location"])
    chk("판이 끝나면 다음은 새 판", mid_d != mid and action.get(mid_d)["state"] == "open", (mid_d, mid))
    action.abort(mid_d, "noshow")
    live_busy = live.my_match
    live.my_match = lambda uid: {"id": 1} if uid == ids["a"] else None
    try:
        chk("실시간 배틀 중이면 409 (판을 열지 않는다)", status(action_test.go, req(), k=KEY, who="a") == 409)
    finally:
        live.my_match = live_busy
    chk("  같은 사람끼리는 못 연다", _raises(action.open_direct, ids["a"], ids["a"]))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


def _raises(fn, *a):
    try:
        fn(*a)
    except ValueError:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
