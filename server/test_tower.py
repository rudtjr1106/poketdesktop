# -*- coding: utf-8 -*-
"""배틀타워 (시즌 7) — 차례로 오르기, 처음 한 번 보상, 시즌 문, 관장 판에 얹기.

    python server/test_tower.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다 (test_boss.py 와 같은 꼴). 못 박는 것:

  1. **시즌 7 에 열린다** (config.TOWER_FROM). 시즌 번호를 부를 때마다 본다 - 6 에서는 닫혀 있다.
  2. **차례로만 오른다.** 가장 높이 이긴 층 + 1 까지만 도전하고, 그 위는 카드도 안 준다.
  3. **보상은 층마다 처음 한 번** - 돈 · 도구 · 알. 다시 이기면 기록(이긴 횟수 · 가장 적은 턴)만 바뀐다.
     같은 층을 두 판으로 이겨도 한 번이다. 칭호는 없다.
  4. 보상을 넣다 오류가 나도 판은 끝나고 클리어는 남는다 (오류는 server_error 에 적힌다).
  5. 자료에 없는 층의 판이 끝나도 죽지 않는다 (층 자료를 고치는 배포 사이에 하던 판).
  6. 판은 관장 배틀 그대로다 (gym_battle.region = "tower:<층>") - 같은 종 · 같은 도구가 겹친 상대 팀도 열린다.
"""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-tower-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_TOWER_FROM", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import db, deps, eggs, gym_routes, items, season     # noqa: E402
from app import tower                                          # noqa: E402
from common import pokelogic as P                             # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot, moves=("EARTHQUAKE", "DRAGONCLAW")):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(slot + 1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 252 if s in ("atk", "spe") else 0) for s in P.STATS)
    m["moves"] = list(moves)
    pid = db.insert_mon(uid, m, "2026-01-01")
    db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=?, ivs=?, evs=?, moves=? WHERE id=?",
           (slot, level, json.dumps(m["ivs"]), json.dumps(m["evs"]), json.dumps(m["moves"]), pid))
    return pid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def status_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code
    return None


def raises(kind, fn):
    try:
        fn()
    except kind:
        return True
    return False


def balls(uid):
    return db.q1("SELECT balls FROM users WHERE id=?", (uid,))["balls"]


def bag(uid, item):
    return items.bag_count(uid, item)


def core():
    """tower.py: 시즌 문 · 진행 · 보상."""
    u = mkuser("climber")
    for i in range(6):
        mkmon(u, "GARCHOMP", 100, i)        # 같은 종 여섯 - 판에는 한 마리만 나간다 (pvp.split_restricted)

    print("=== 시즌 문 ===")
    season.SEASON = 6
    chk("시즌 6 에는 닫혀 있다", not tower.is_open() and tower.overview(u) == {"open": False, "from": 7},
        tower.overview(u))
    chk("닫힌 글", tower.closed_text() == "배틀타워는 시즌 7에 열립니다.", tower.closed_text())
    chk("닫혀 있으면 판을 못 연다", raises(ValueError, lambda: tower.start(u, gym_routes._party(u), 1)))
    season.SEASON = 7
    ov = tower.overview(u)
    chk("시즌 7 에 열린다", tower.is_open() and ov["open"] and ov["total"] == 50 and tower.total() == 50, ov.get("total"))

    print("\n=== 차례로 오른다 ===")
    chk("처음에는 1층만 도전", [f["state"] for f in ov["floors"][:3]] == ["next", "locked", "locked"] and ov["top"] == 0)
    chk("개요의 층 한 줄", set(ov["floors"][0]) == {"floor", "name", "kind", "level", "size", "state", "reward", "bestTurns"}
        and ov["floors"][0]["name"] == "풀숲" and ov["floors"][0]["level"] == 30 and ov["floors"][0]["size"] == 3,
        ov["floors"][0])
    chk("잠긴 층도 보상 글줄은 보인다", ov["floors"][4]["reward"] == ["상금 4,000원", "이상한사탕 ×1"], ov["floors"][4]["reward"])
    chk("지역 코드", tower.region_of(13) == "tower:13" and tower.parse("tower:13") == 13
        and tower.is_tower("tower:1") and not tower.is_tower("boss:2026-10-17:1") and not tower.is_tower(None)
        and tower.parse("tower:x") is None and tower.parse("11710") is None)
    chk("다른 판에 알릴 이름", tower.busy_name("tower:13") == "배틀타워 13층", tower.busy_name("tower:13"))
    card = tower.card(u, 1)
    chk("카드는 종 · 레벨만 (기술 · 도구 · 특성은 안 보낸다)",
        set(card["team"][0]) == {"species", "num", "kr", "level", "types"}, card["team"][0])
    chk("카드의 트레이너 · 보상", card["floor"] == 1 and card["name"] == "풀숲" and card["trainer"]["name"] == "민화"
        and card["trainer"]["sprite"] == "erika" and card["reward"] == ["상금 2,000원", "몬스터볼 ×5"]
        and card["state"] == "next", {k: card[k] for k in ("floor", "name", "trainer", "reward", "state")})
    chk("건너뛴 층의 카드는 안 준다", raises(ValueError, lambda: tower.card(u, 3)))
    chk("없는 층", raises(LookupError, lambda: tower.card(u, 51)) and raises(LookupError, lambda: tower.card(u, 0))
        and tower.floor(51) is None)
    chk("건너뛴 층은 판을 못 연다", raises(ValueError, lambda: tower.start(u, gym_routes._party(u), 2)))

    print("\n=== 처음 한 번 보상 ===")
    r = tower.on_win(u, "tower:1", 9)
    chk("1층 첫 승: 2,000원 + 몬스터볼 5", r["first"] and r["top"] == 1 and r["floor"] == 1 and r["total"] == 50
        and r["tower"] is True and items.money(u) == 2000 and r["money"] == 2000 and balls(u) == 10 + 5, r)
    chk("결과 글줄", r["lines"][:2] == ["상금 2,000원", "몬스터볼 ×5"], r["lines"])
    r2 = tower.on_win(u, "tower:1", 7)
    chk("다시 이기면(같은 층을 두 판으로 이겨도) 보상 없음, 기록만", not r2["first"] and items.money(u) == 2000
        and balls(u) == 15 and tower.clears(u)[1]["wins"] == 2 and tower.clears(u)[1]["best_turns"] == 7, r2)
    tower.on_win(u, "tower:1", 30)
    chk("가장 적은 턴은 안 늘어난다", tower.clears(u)[1]["best_turns"] == 7 and tower.clears(u)[1]["wins"] == 3)
    ov = tower.overview(u)
    chk("이긴 층 · 다음 층", [f["state"] for f in ov["floors"][:3]] == ["cleared", "next", "locked"]
        and ov["floors"][0]["bestTurns"] == 7 and ov["top"] == 1 and tower.top(u) == 1)
    chk("이긴 층의 카드는 다시 볼 수 있다", tower.card(u, 1)["state"] == "cleared" and tower.card(u, 2)["state"] == "next")

    print("\n=== 보상을 넣다 오류가 나도 ===")
    real = eggs.give

    def boom(*_a, **_k):
        raise RuntimeError("boom")
    eggs.give = boom
    try:
        for n in range(2, 50):
            tower.on_win(u, tower.region_of(n), 20)
        r50 = tower.on_win(u, "tower:50", 30)
    finally:
        eggs.give = real
    chk("알이 실패해도 판은 끝나고 클리어는 남는다", r50["first"] and tower.top(u) == 50, r50)
    chk("못 넣은 알은 글줄에 없다 (넣은 것만 적는다)", "전설의 포켓몬 알" not in r50["lines"]
        and r50["lines"][:2] == ["상금 30,000원", "타입 확정 기술머신 뽑기권 ×1"], r50["lines"])
    chk("오류가 적혔다", db.q1("SELECT COUNT(*) c FROM server_error WHERE path='tower.on_win'")["c"] == 1)
    chk("50층까지의 돈 합계", items.money(u) == 390000, items.money(u))
    chk("가방에 실제로 들어왔다", (bag(u, "GOLDBOTTLECAP"), bag(u, "MASTERBALL"), bag(u, "SHINYCANDY"),
                          bag(u, "RANKTICKETTM"), bag(u, "RANKTICKETTMTYPE")) == (3, 1, 1, 2, 2))
    chk("칭호는 주지 않는다", not db.q1("SELECT 1 FROM user_reward WHERE user_id=?", (u,)))
    r99 = tower.on_win(u, "tower:99", 5)
    chk("없는 층의 판이 끝나도 죽지 않는다", r99["first"] is False and r99["tower"] is True and tower.top(u) == 50
        and items.money(u) == 390000 and not db.q1("SELECT 1 FROM tower_clear WHERE floor=99"), r99)
    chk("다 오른 뒤의 개요", all(f["state"] == "cleared" for f in tower.overview(u)["floors"]))

    print("\n=== 알 ===")
    w = mkuser("egghead")
    r = tower.on_win(w, "tower:50", 44)
    chk("50층: 전설의 알이 들어온다", r["first"] and "전설의 포켓몬 알" in r["lines"]
        and db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=? AND kind='legendary'", (w,))["c"] == 1, r["lines"])
    tower.on_win(w, "tower:50", 40)
    chk("알도 한 번뿐", db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (w,))["c"] == 1)

    print("\n=== 판은 관장 배틀 그대로 ===")
    dup = next(f["floor"] for f in tower.data()["floors"]
               if len({m["species"] for m in f["trainer"]["team"]}) < len(f["trainer"]["team"]))
    region, tid, tb, events = tower.start(u, gym_routes._party(u), dup)
    chk("같은 종이 겹친 층이 열린다", region == "tower:%d" % dup and tid == "tower-%d" % dup
        and [x.mon["species"] for x in tb.foe_team] == [m["species"] for m in tower.floor(dup)["trainer"]["team"]]
        and bool(events), (region, tid))
    _r, _t, tb41, _e = tower.start(u, gym_routes._party(u), 41)
    _r, _t, tb1, _e = tower.start(u, gym_routes._party(u), 1)
    chk("41층부터 길드전 AI, 그 아래는 관장 AI", tb41.trainer.get("ai") == "war" and tb1.trainer.get("ai") == "gym")
    _r, _t, tb35, _e = tower.start(u, gym_routes._party(u), 35, keystone=True, zring=True, orb=True)
    chk("내 키스톤 · Z링 · 테라오브는 서버가 채운 대로", tb35.keystone["me"] and tb35.zring["me"] and tb35.tera_orb["me"])
    chk("메가스톤을 쥔 층은 상대도 메가진화한다", tb35.keystone["foe"] is True and tb1.keystone["foe"] is False
        and tb41.keystone["foe"] is False)
    return u


def main():
    db.init()
    core()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
