# -*- coding: utf-8 -*-
"""탐험 파견이 HTTP 로 오가는지 (1.10.4).

서버를 띄워 놓고 돌린다. 돌아올 시각을 당기려고 DB 를 직접 만진다 (test_event 와 같은 방식).

    python server/test_expedition_http.py http://127.0.0.1:8788 /tmp/poket-test.db

규칙과 굴리기는 server/test_expedition.py 가 본다. 여기서는 **화면이 읽는 모양 그대로 오가는지**만 본다 -
화면 검사(client/test_expedition_ui.py)의 가짜 서버가 이 모양을 흉내 내고 있어서, 둘이 어긋나면
화면은 검사를 통과하고도 진짜 서버 앞에서 깨진다.
"""
import json
import random
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
DB = sys.argv[2] if len(sys.argv) > 2 else None
OK = FAIL = 0
TOKEN = {"v": None}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN["v"]:
        req.add_header("Authorization", "Bearer " + TOKEN["v"])
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:                                   # noqa: BLE001
            return e.code, {}


def main():
    name = "탐험%06d" % random.randrange(1000000)
    st, r = call("POST", "/api/auth/register", {"username": name, "password": "1234", "starter": "BULBASAUR"})
    if st != 200:
        print("가입 실패:", st, r)
        return 1
    TOKEN["v"] = r["token"]
    st, me = call("GET", "/api/me")
    chk("/api/me 에 탐험 요약이 실린다 (나간 것 없음)", st == 200 and me.get("expedition") == {"out": 0, "ready": 0, "nextIn": None},
        me.get("expedition"))
    st, mons = call("GET", "/api/pokemon")
    pid = mons["pokemon"][0]["id"]
    st, s0 = call("GET", "/api/expedition")
    chk("처음 상태: 칸 3, 비어 있다", st == 200 and s0["slots"] == 3 and s0["free"] == 3 and s0["out"] == []
        and s0["hours"] == [2, 4, 8] and s0["nextIn"] is None, s0)
    st, r = call("POST", "/api/expedition/send", {"pokemon": pid, "place": "forest", "hours": 2})
    chk("데리고 다니는 포켓몬은 못 보낸다 (409, 까닭이 온다)", st == 409 and "박스" in (r.get("error") or r.get("detail") or ""), (st, r))
    call("POST", "/api/pokemon/%d/desktop" % pid, {"on": False})
    st, r = call("POST", "/api/expedition/send", {"pokemon": pid, "place": "forest", "hours": 2})
    one = (r.get("out") or [{}])[0]
    want = {"id", "pokemon", "place", "placeKr", "hours", "grade", "gradeKr", "score", "items", "startedAt", "endsAt",
            "left", "total", "ready"}
    chk("보냈다: 화면이 읽는 칸이 다 있다", st == 200 and r.get("ok") and set(one) == want and r["free"] == 2
        and r["nextIn"] == one["left"] and "message" in r, (st, sorted(set(one) ^ want), r.get("message")))
    mon = one.get("pokemon") or {}
    chk("  포켓몬: 이름·도감 번호·레벨·타입·색", set(mon) >= {"id", "name", "num", "level", "shiny", "tint", "types"}
        and mon["id"] == pid and mon["num"] == 1 and mon["types"] == ["GRASS", "POISON"] and one["placeKr"] == "숲"
        and one["gradeKr"] in ("보통", "성공", "대성공") and 7190 <= one["left"] <= 7200 and one["total"] == 7200, mon)
    st, lst = call("GET", "/api/pokemon")
    chk("포켓몬 목록에 '나가 있음' 이 실린다", lst["pokemon"][0].get("away") is True, lst["pokemon"][0].get("away"))
    st, r2 = call("POST", "/api/pokemon/%d/desktop" % pid, {"on": True})
    chk("나가 있는 동안은 데리고 다닐 수 없다 (409)", st == 409 and "탐험" in (r2.get("error") or r2.get("detail") or ""), (st, r2))
    st, r2 = call("DELETE", "/api/pokemon/%d" % pid)
    chk("놓아줄 수 없다 (409)", st == 409, (st, r2))
    st, r2 = call("POST", "/api/expedition/%d/claim" % one["id"], {})
    chk("돌아오기 전에는 못 받는다 (409)", st == 409 and "아직" in (r2.get("error") or r2.get("detail") or ""), (st, r2))
    st, me = call("GET", "/api/me")
    chk("/api/me: 나간 것 1, 돌아온 것 0, 남은 초", me["expedition"]["out"] == 1 and me["expedition"]["ready"] == 0
        and 7100 < me["expedition"]["nextIn"] <= 7200, me["expedition"])

    if not DB:
        print("  (DB 경로를 안 줘서 돌아온 뒤의 검사는 건너뛴다)")
    else:
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("UPDATE expedition SET ends_at='2020-01-01T00:00:00+00:00' WHERE id=?", (one["id"],))
        conn.commit()
        conn.close()
        st, s1 = call("GET", "/api/expedition")
        chk("돌아왔다 (ready, 남은 초 0)", s1["out"][0]["ready"] is True and s1["out"][0]["left"] == 0 and s1["ready"] == 1
            and s1["nextIn"] is None and s1["free"] == 2, s1["out"][0])
        st, me = call("GET", "/api/me")
        chk("/api/me: 돌아온 것 1", me["expedition"] == {"out": 1, "ready": 1, "nextIn": None}, me["expedition"])
        bag0 = dict(me.get("bag") or {})
        st, got = call("POST", "/api/expedition/claim", {})
        cl = (got.get("claimed") or [{}])[0]
        want = {"id", "pokemon", "place", "placeKr", "hours", "grade", "gradeKr", "items", "tm"}
        chk("전부 받기: 화면이 읽는 칸이 다 있다", st == 200 and got.get("ok") and len(got["claimed"]) == 1 and set(cl) == want
            and got["free"] == 3 and got["out"] == [] and set(got) >= {"bag", "money", "balls", "message"},
            (st, sorted(set(cl) ^ want)))
        items = cl.get("items") or []
        chk("  물건마다 이름·개수·등급", len(items) >= 1 and all(set(i) >= {"id", "kr", "count", "tier", "rarity", "sell"} for i in items)
            and sum(i["count"] for i in items) == s1["out"][0]["items"], items)
        chk("  가방에 들어갔다", all(got["bag"].get(i["id"], 0) - bag0.get(i["id"], 0) == i["count"] for i in items),
            (bag0, got["bag"]))
        st, r2 = call("POST", "/api/expedition/%d/claim" % one["id"], {})
        chk("같은 보따리를 두 번 못 받는다 (404)", st == 404, (st, r2))
        st, lst = call("GET", "/api/pokemon")
        chk("포켓몬이 돌아왔다 ('나가 있음' 이 없다)", "away" not in lst["pokemon"][0])
        st, r2 = call("POST", "/api/pokemon/%d/desktop" % pid, {"on": True})
        chk("  다시 데리고 다닐 수 있다", st == 200, (st, r2))
        call("POST", "/api/pokemon/%d/desktop" % pid, {"on": False})

    st, r = call("POST", "/api/expedition/send", {"pokemon": pid, "place": "ruins", "hours": 8})
    eid = r["out"][0]["id"] if st == 200 else 0
    st, back = call("POST", "/api/expedition/%d/recall" % eid, {})
    chk("불러들이기: 칸이 비고 빈손이라고 알린다", st == 200 and back.get("ok") and back["free"] == 3 and "빈손" in back.get("message", ""),
        (st, back.get("message")))
    st, r = call("POST", "/api/expedition/send", {"pokemon": pid, "place": "moon", "hours": 8})
    chk("없는 곳은 400", st == 400, (st, r))
    st, r = call("POST", "/api/expedition/send", {"pokemon": pid, "place": "forest", "hours": 3})
    chk("없는 시간은 400", st == 400, (st, r))
    TOKEN["v"] = None
    st, r = call("GET", "/api/expedition")
    chk("로그인하지 않으면 401", st == 401, st)

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
