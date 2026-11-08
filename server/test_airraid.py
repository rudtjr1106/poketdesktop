# -*- coding: utf-8 -*-
"""공습 (2.3.0) 서버. 서버를 띄우지 않는다.

    python server/test_airraid.py

설계 design-notes/2026-11-08-airraid.md: 하루 한 번(KST) · 그날 시각 10:00~22:00 · 바탕화면 파티 + 2~3 · 시작할 때
결과를 계산해 저장 · 쓰러뜨린 공습 포켓몬마다 경험치 · 이기면 몬스터볼 3 + 2,000원 · 두 번 불러도 한 번.
"""
import datetime
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-airraid-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from common import pokelogic as P                            # noqa: E402
from app import airraid as AR                                # noqa: E402
from app import db, deps                                     # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))


def kst(day, h, mi=0):
    y, mo, d = int(day[0:4]), int(day[5:7]), int(day[8:10])
    return datetime.datetime(y, mo, d, h, mi, tzinfo=KST).astimezone(UTC)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


_n = [0]


def mkuser():
    _n[0] += 1
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'2026-10-01T00:00:00+00:00','','')",
        ("공습%d" % _n[0], b"x", b"x"))
    return cur.lastrowid


def mkmon(uid, species="PIKACHU", level=30, seed=3, desk=True):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(seed), force_shiny=False)
    m["evs"] = dict((s, 0) for s in P.STATS)
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=? WHERE id=?", (1 if desk else 0, pid))
    return pid


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    return None


def user(uid):
    return db.q1("SELECT balls, money FROM users WHERE id=?", (uid,))


def exp_of(pid):
    return db.q1("SELECT exp FROM pokemon WHERE id=?", (pid,))["exp"]


def main():
    db.init()
    day = "2026-11-12"
    u = mkuser()
    # ---- 시각
    print("[그날 시각]")
    at = AR.due_at(u, day)
    at_k = at.astimezone(KST)
    chk("시각은 10:00 ~ 22:00 KST", at_k.date().isoformat() == day and 10 <= at_k.hour < 22, at_k)
    chk("같은 사람 · 같은 날이면 같은 시각", AR.due_at(u, day) == at)
    days = set(AR.due_at(u, "2026-11-%02d" % d).astimezone(KST).strftime("%H:%M") for d in range(1, 29))
    chk("날마다 다른 시각 (28일에 20가지 넘게)", len(days) > 20, len(days))
    # ---- 시각 전 · 파티 없음
    print("[막기]")
    st = AR.state(u, now=at - datetime.timedelta(minutes=5))
    chk("시각 전: 안 끝남 · 남은 초", not st["done"] and 290 <= st["dueIn"] <= 310, st)
    chk("시각 전 시작은 막는다", (refused(AR.start, u, now=at - datetime.timedelta(minutes=5)) or (0,))[0] == 409)
    chk("바탕화면 파티가 없으면 막고 그날 것을 쓰지 않는다",
        (refused(AR.start, u, now=at)[0] if refused(AR.start, u, now=at) else 0) == 409
        and not AR.state(u, now=at)["done"])
    # ---- 시작
    print("[시작 · 보상]")
    strong = [mkmon(u, "MEWTWO", 70, seed=s) for s in (1, 2)]
    off = mkmon(u, "CATERPIE", 5, seed=9, desk=False)
    e0 = [exp_of(p) for p in strong]
    b0 = user(u)
    view = AR.start(u, now=at + datetime.timedelta(minutes=1))
    ev = view["events"]
    teams = ev[0]
    chk("명단: 바탕화면 둘 (상자 안 캐터피 빼고) · 공습 4~5", teams["t"] == "teams" and len(teams["me"]) == 2
        and len(teams["foe"]) in (4, 5) and view["ids"] == strong, (len(teams["me"]), len(teams["foe"]), view["ids"]))
    lv = [f["level"] for f in teams["foe"]]
    chk("공습 레벨 = 평균(70) - 7~10 (파티 2마리)", all(60 <= x <= 63 for x in lv), lv)
    chk("센 파티는 이긴다 · 결과 win", view["result"] == "win" and ev[-1]["t"] == "raid", view["result"])
    b1 = user(u)
    chk("이기면 몬스터볼 +3 · 5,000원 (사용자 11/08)", (b1["balls"] - b0["balls"], b1["money"] - b0["money"]) == (3, 5000)
        and view["reward"] == {"balls": 3, "money": 5000}, (dict(b1), view["reward"]))
    chk("쓰러뜨린 포켓몬이 경험치를 받는다 (둘 다)", all(exp_of(p) > e for p, e in zip(strong, e0)),
        [(exp_of(p), e) for p, e in zip(strong, e0)])
    chk("경험치 알림 목록(exp)을 같이 준다", view.get("exp") and all("id" in g or "pokemon" in g for g in view["exp"]),
        (view.get("exp") or [None])[:1])
    # ---- 두 번
    print("[한 번만]")
    again = AR.start(u, now=at + datetime.timedelta(minutes=2))
    b2 = user(u)
    chk("두 번 불러도 보상은 한 번 · 같은 판(이미 함)", dict(b2) == dict(b1) and again.get("already")
        and again["events"] == view["events"], (dict(b2), again.get("already")))
    st = AR.state(u, now=at + datetime.timedelta(minutes=3))
    chk("상태: 끝 · 결과", st["done"] and st["result"] == "win", st)
    card = AR.me_card(u, now=at + datetime.timedelta(minutes=3))
    chk("/api/me 카드: 끝났다 · 결과 · 보상 (다른 PC · 다시 켠 앱이 결과를 한 번 알린다)", card and card["done"]
        and card["day"] == day and card["result"] == "win" and card["reward"] == {"balls": 3, "money": 5000}, card)
    chk("  카드는 각본 덩어리를 안 읽는다 (매 동기화)", "data" not in AR._card_sql)
    nobody = mkuser()
    chk("/api/me 카드: 바탕화면 파티 수 (0 이면 앱이 부르지 않는다)", AR.me_card(nobody)["party"] == 0
        and AR.me_card(u, now=at - datetime.timedelta(hours=1))["party"] == 2, AR.me_card(nobody))
    # ---- 다음 날
    nxt = "2026-11-13"
    at2 = AR.due_at(u, nxt)
    chk("다음 날은 다시 (그날 시각 전엔 안 끝남)", not AR.state(u, now=at2 - datetime.timedelta(seconds=30))["done"])
    v2 = AR.start(u, now=at2)
    chk("다음 날 시작", v2["day"] == nxt and not v2.get("already"), v2.get("day"))
    # 자정 넘김: 22시 시각이 지나고 자정 전 = 그날 것, 자정 지나면 새 날
    late = kst(nxt, 23, 59)
    chk("자정 전까지는 그날 것 (이미 함)", AR.state(u, now=late)["done"])
    # ---- 지는 판 (약한 파티)
    print("[지는 판]")
    w = mkuser()
    weak = [mkmon(w, "MAGIKARP", 40, seed=4)]
    at3 = AR.due_at(w, day)
    wb0 = user(w)
    lost = AR.start(w, now=at3)
    chk("지면 볼 · 돈 없음 (경험치만)", lost["result"] == "lose" and lost["reward"] is None
        and dict(user(w)) == dict(wb0), (lost["result"], lost["reward"]))
    # ---- 배선
    print("[배선]")
    from app import main as M
    def walk(rs):                         # 이 FastAPI 는 붙인 라우터를 한 겹 싸서 둔다 (path 가 없는 칸)
        for r in rs:
            if getattr(r, "path", None):
                yield r.path
            sub = (getattr(r, "routes", None) or getattr(getattr(r, "router", None), "routes", None)
                   or getattr(getattr(r, "original_router", None), "routes", None))
            if sub:
                for x in walk(sub):
                    yield x
    paths = set(walk(M.app.routes))
    chk("라우트 /api/airraid · /api/airraid/start", {"/api/airraid", "/api/airraid/start"} <= paths)
    real = AR.me_card
    AR.me_card = lambda uid: 1 / 0
    try:
        chk("  카드에서 예외가 나면 None", M._airraid_card(u) is None)
    finally:
        AR.me_card = real
    # ---- 정리
    print("[정리]")
    db.run("UPDATE airraid SET created_at='2026-10-01T00:00:00+00:00' WHERE user_id=?", (w,))
    n = AR.prune(now=kst("2026-11-12", 12))
    chk("7일 지난 공습 기록은 지운다", n == 1 and db.q1("SELECT COUNT(*) c FROM airraid WHERE user_id=?", (w,))["c"] == 0,
        n)
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
