# -*- coding: utf-8 -*-
"""랭크 팀 안에서 같은 지닌 도구는 한 마리만 (시즌 5, season.rules_v5) - 켜짐/꺼짐 둘 다.

    POKET_DB=/tmp/x.db python server/test_held_v5.py

서버 안에서 pvp 를 바로 부른다 (test_pvp.py 와 같은 자리에서 돈다). season.SEASON 을 4 와 5 로 바꿔 가며
  · 시즌 4: 등록·걸기·판·응답 모양이 예전 그대로 (같은 도구 둘이어도 아무 일 없다)
  · 시즌 5: 등록을 이름으로 거절 · 거는 쪽(랭크 팀/바탕화면 파티)은 못 건다 · 걸려온 쪽은 그 판에서만
    뒤의 것이 안 지닌 셈 (원본 그대로) · 메가스톤·Z크리스탈도 도구 · 안 지닌 것(None)은 상관없다
"""
import os
import sys
import tempfile

if not os.environ.get("POKET_DB"):
    os.environ["POKET_DB"] = os.path.join(tempfile.mkdtemp(prefix="poket-held-v5-"), "t.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, pvp, pvp_routes, season               # noqa: E402
from test_pvp import mkuser                              # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mons_of(uid):
    return db.q("SELECT id, held FROM pokemon WHERE user_id=? ORDER BY slot, id", (uid,))


def hold(uid, *helds):
    """자리 차례대로 도구를 들린다 (None = 안 지님)."""
    for r, h in zip(mons_of(uid), helds):
        db.run("UPDATE pokemon SET held=? WHERE id=?", (h, r["id"]))


def ids(uid):
    return [r["id"] for r in mons_of(uid)]


SEEN = []


def spy():
    """PB.simulate 가 받은 두 팀을 적어 둔다 (그 판에 실제로 들고 나간 도구를 보려고)."""
    real = pvp.PB.simulate

    def fake(dex, a, b, **kw):
        SEEN.append((a, b))
        return real(dex, a, b, **kw)
    pvp.PB.simulate = fake


def held_of(team):
    return [m.get("held") for m in team]


def season4():
    print("=== 시즌 4 (지금 운영 중) - 아무것도 안 바뀐다 ===")
    season.SEASON = 4
    a, b = mkuser("zz_hv4_a", rank=True), mkuser("zz_hv4_b", rank=True)
    hold(a, "FOCUSSASH", "FOCUSSASH", None, None, None, None)
    hold(b, "LIFEORB", "LIFEORB", None, None, None, None)
    chk("규칙 꺼짐", not pvp.held_rule_on())
    try:
        pvp.set_team(a, ids(a))
        chk("같은 도구 둘이어도 등록된다", pvp.team_ids(a) == ids(a), pvp.team_ids(a))
    except ValueError as e:
        chk("같은 도구 둘이어도 등록된다", False, str(e))
    chk("걸 수 있다", pvp.can_start(a, "random") is None, pvp.can_start(a, "random"))
    chk("held_short 는 None", pvp.held_short(a) is None)
    del SEEN[:]
    pvp.run_match(a, b, kind="random", seed=5)
    ta, tb = SEEN[-1]
    chk("판에서 거는 쪽 도구 그대로", held_of(ta)[:2] == ["FOCUSSASH", "FOCUSSASH"], held_of(ta))
    chk("판에서 걸려온 쪽 도구 그대로", held_of(tb)[:2] == ["LIFEORB", "LIFEORB"], held_of(tb))
    s = pvp.summary(a)
    chk("요약에 새 칸 없음", "sameHeldMax" not in s and "heldDupes" not in s, sorted(s))
    v = pvp_routes._team_view(a)
    chk("팀 응답에 새 칸 없음", not ({"sameHeldMax", "heldDupIds", "heldShort"} & set(v)), sorted(v))
    r = pvp_routes.ranking(limit=5, ctx={"user": {"id": a}})
    chk("규칙에 새 칸 없음", "sameHeldMax" not in r["rules"], sorted(r["rules"]))
    return a, b


def season5(a4, b4):
    print("\n=== 시즌 5 - 같은 지닌 도구는 한 마리 ===")
    season.SEASON = 5
    chk("규칙 켜짐 (부를 때마다 본다)", pvp.held_rule_on())

    a, b = mkuser("zz_hv5_a", rank=True), mkuser("zz_hv5_b", rank=True)
    hold(a, "FOCUSSASH", None, "FOCUSSASH", None, None, None)
    try:
        pvp.set_team(a, ids(a))
        chk("같은 도구 둘이면 등록 거절", False, pvp.team_ids(a))
    except ValueError as e:
        msg = str(e)
        chk("같은 도구 둘이면 등록 거절", True)
        chk("  도구 이름으로 알린다", "기합의띠" in msg, msg)
        # 누가 겹쳤나도 이름으로 (별명이 없으면 종 이름)
        chk("  지닌 두 마리 이름이 들어간다", msg.count("·") >= 1 and "(" in msg, msg)
    chk("  거절하면 팀은 안 바뀐다", pvp.team_ids(a) == [], pvp.team_ids(a))

    print("  -- 랭크 팀이 없어 바탕화면 파티로 싸우는 경우")
    why = pvp.can_start(a, "random")
    chk("파티가 겹치면 랜덤 배틀을 못 건다", why and "기합의띠" in why, why)
    chk("  바탕화면 파티라고 알려 준다", why and "바탕화면 파티" in why, why)
    chk("  /api/pvp/random 이 can_start 로 막는다 (409 앞에서)",
        pvp.can_fight(a, b, "random") == why, pvp.can_fight(a, b, "random"))

    hold(a, "FOCUSSASH", None, None, None, None, None)
    chk("하나만 남기면 걸 수 있다", pvp.can_start(a, "random") is None, pvp.can_start(a, "random"))
    pvp.set_team(a, ids(a))
    chk("하나면 등록된다", pvp.team_ids(a) == ids(a))
    hold(a, None, None, None, None, None, None)
    pvp.set_team(a, ids(a))
    chk("안 지닌 것(None)끼리는 상관없다", pvp.team_ids(a) == ids(a))

    print("  -- 메가스톤·Z크리스탈도 도구")
    hold(a, "CHARIZARDITEX", "CHARIZARDITEX", None, None, None, None)
    try:
        pvp.set_team(a, ids(a))
        chk("같은 메가스톤 둘이면 거절", False)
    except ValueError as e:
        chk("같은 메가스톤 둘이면 거절", "리자몽나이트" in str(e) or "CHARIZARDITEX" in str(e), str(e))
    hold(a, "FIRIUMZ", "FIRIUMZ", None, None, None, None)
    try:
        pvp.set_team(a, ids(a))
        chk("같은 Z크리스탈 둘이면 거절", False)
    except ValueError as e:
        chk("같은 Z크리스탈 둘이면 거절", "Z" in str(e), str(e))
    hold(a, "CHARIZARDITEX", "FIRIUMZ", "FOCUSSASH", None, None, None)
    pvp.set_team(a, ids(a))
    chk("서로 다른 도구는 된다", pvp.team_ids(a) == ids(a))

    print("  -- 등록한 뒤 도구를 바꿨다 / 시즌 4 에 등록해 둔 겹친 팀")
    hold(a, "CHARIZARDITEX", "FOCUSSASH", "FOCUSSASH", None, None, None)
    why = pvp.can_start(a, "random")
    chk("등록 뒤 겹치면 못 건다", why and "랭크 팀" in why and "기합의띠" in why, why)
    why4 = pvp.can_start(a4, "random")
    chk("시즌 4 에 겹친 채 등록한 팀도 시즌 5 에는 못 건다", why4 and "기합의띠" in why4, why4)
    s = pvp.summary(a)
    chk("요약: sameHeldMax · heldDupes", s.get("sameHeldMax") == 1 and s.get("heldDupes") == 1, s)
    v = pvp_routes._team_view(a)
    third = ids(a)[2]
    chk("팀 응답: 뒤의 것 id 를 표시", v.get("heldDupIds") == [third], v.get("heldDupIds"))
    chk("팀 응답: 고칠 것 한 줄", "기합의띠" in (v.get("heldShort") or ""), v.get("heldShort"))
    chk("팀 응답: 예전 칸은 그대로", "sameSpeciesMax" in v and "rankReady" in v, sorted(v))
    r = pvp_routes.ranking(limit=5, ctx={"user": {"id": a}})
    chk("규칙에 sameHeldMax", r["rules"].get("sameHeldMax") == 1, r["rules"].get("sameHeldMax"))
    chk("규칙의 예전 칸도 그대로", "practice" in r["rules"] and "sameSpeciesMax" in r["rules"], sorted(r["rules"]))

    print("  -- 걸려온 쪽(상대)이 겹쳐 있다")
    hold(a, "CHARIZARDITEX", "FOCUSSASH", None, None, None, None)
    hold(b, "LIFEORB", "CHOICESCARF", "LIFEORB", "LIFEORB", None, None)
    chk("거는 쪽은 이제 된다", pvp.can_start(a, "random") is None, pvp.can_start(a, "random"))
    chk("상대가 겹쳐도 걸 수 있다 (후보에서 안 뺀다)", pvp.can_fight(a, b, "random") is None,
        pvp.can_fight(a, b, "random"))
    chk("상대 고르기에도 그대로 들어간다", b in pvp._all_teams() and pvp.rank_ready(pvp._all_teams()[b])[0])
    del SEEN[:]
    out = pvp.run_match(a, b, kind="random", seed=7)
    tb = SEEN[-1][1]
    chk("그 판에서는 앞의 하나만 지닌다", held_of(tb)[:4] == ["LIFEORB", "CHOICESCARF", None, None],
        held_of(tb))
    chk("원본 도구는 그대로", [r["held"] for r in mons_of(b)][:4] == ["LIFEORB", "CHOICESCARF", "LIFEORB", "LIFEORB"],
        [r["held"] for r in mons_of(b)])
    chk("판은 끝까지 간다", out.get("matchId") and out["turns"] > 0, out.get("turns"))
    del SEEN[:]
    pvp.run_match(a, b, kind="friend", seed=8)
    chk("친구 배틀은 그대로 (랭크만)", held_of(SEEN[-1][1]).count("LIFEORB") == 3, held_of(SEEN[-1][1]))


def main():
    db.init()
    spy()
    try:
        a4, b4 = season4()
        season5(a4, b4)
    finally:
        season.SEASON = 4
        for n in ("zz_hv4_a", "zz_hv4_b", "zz_hv5_a", "zz_hv5_b"):
            db.run("DELETE FROM users WHERE username=?", (n,))
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
