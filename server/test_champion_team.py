# -*- coding: utf-8 -*-
"""독도 팀 (2.5.8, 게시판 #858 '랭크 팀이랑 독도 팀 선정을 따로 하면 편하겠다').

    cd server && python test_champion_team.py

  1. 정하지 않으면 독도에서도 랭크 팀 (없으면 바탕화면 파티) - 예전과 같다
  2. 독도 팀을 정하면 독도 판(kind=champion)은 그 팀으로, 친구 실시간 배틀은 그대로 랭크 팀으로 싸운다
  3. 규칙은 랭크 팀과 같다 (여섯 마리 · 내 것만 · 전설 · 환상 한 마리 · 같은 종 한 마리) - 문구는 '독도 팀'
  4. 빈 목록이면 등록을 풀고 다시 랭크 팀
  5. 창이 받는 꼴(/api/champion/team)은 랭크 팀 창과 같다 · 리그 모습에 teamSet · teamLabel
  6. 독도 팀이 리그 조건(Lv.50 이상 6마리)을 못 채우면 상대 찾기 · 도전을 막는다 (까닭에 '독도 팀')
  7. 포켓몬을 놓아주면 그 자리가 독도 팀에서도 빠진다 (내 것만 센다)
"""
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="poket-champion-team-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_CHAMPION_START"] = "2020-01-01T00:00:00+09:00"

from common.pokelogic import make_pokemon                   # noqa: E402
from app import champion, db, deps, live, pvp               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


PARTY = ["PIKACHU", "CHARIZARD", "BLASTOISE", "VENUSAUR", "SNORLAX", "GENGAR"]
BOX = ["GYARADOS", "DRAGONITE", "LUCARIO", "GARCHOMP", "METAGROSS", "TYRANITAR", "MEWTWO", "LUGIA"]


def mkuser(name):
    now = live._iso()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES (?,?,?,1,10,1000,?,?,'')", (name, b"x", b"x", now, now)).lastrowid
    d = deps.dex()
    rng = random.Random(uid)
    ids = {}
    for i, sp in enumerate(PARTY + BOX):
        m = make_pokemon(d.get(sp), 60, rng)
        on = i < len(PARTY)
        ids[sp] = db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
                         " shiny, happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
                         " VALUES (?,?,?,0,?,?,0,?,0,70,?,?,?,?,?,?,?)",
                         (uid, sp, 60, m["nature"], m.get("ability"), m.get("gender", "N"), __import__("json").dumps(m["ivs"]),
                          __import__("json").dumps(m["evs"]), __import__("json").dumps(m["moves"]), 1 if on else 0,
                          i if on else None, 60, now)).lastrowid
    return uid, ids


def species(mons):
    return [m["species"] for m in mons]


def main():
    db.init()
    uid, ids = mkuser("독도사람")
    other, _ = mkuser("남")
    print("=== 독도 팀 (#858)")
    chk("1. 정하지 않으면 독도도 바탕화면 파티 (랭크 팀도 없음)", species(champion.team(uid)) == PARTY
        and champion.team_label(uid) == "바탕화면 파티", species(champion.team(uid)))
    rank = [ids[s] for s in ("GYARADOS", "DRAGONITE", "LUCARIO", "GARCHOMP", "METAGROSS", "TYRANITAR")]
    pvp.set_team(uid, rank)
    chk("   랭크 팀을 정하면 독도도 랭크 팀 (예전과 같다)", species(champion.team(uid)) == species(pvp.ranked_team(uid))
        and champion.team_label(uid) == "랭크 팀")

    dokdo = [ids[s] for s in ("PIKACHU", "CHARIZARD", "GARCHOMP", "LUCARIO", "SNORLAX", "MEWTWO")]
    champion.set_team(uid, dokdo)
    chk("2. 독도 팀을 정하면 독도는 그 팀", species(champion.team(uid)) == ["PIKACHU", "CHARIZARD", "GARCHOMP", "LUCARIO",
                                                                    "SNORLAX", "MEWTWO"] and champion.team_label(uid) == "독도 팀",
        species(champion.team(uid)))
    chk("   독도 판(kind=champion)은 독도 팀 · 친구 실시간 배틀은 랭크 팀", species(live._team(uid, "champion"))[:3]
        == ["PIKACHU", "CHARIZARD", "GARCHOMP"] and species(live._team(uid, "live"))[:3] == ["GYARADOS", "DRAGONITE", "LUCARIO"],
        (species(live._team(uid, "champion")), species(live._team(uid, "live"))))
    chk("   랭크 팀은 그대로", species(pvp.ranked_team(uid))[:2] == ["GYARADOS", "DRAGONITE"])
    chk("   독도 판은 레벨 50 으로 맞춘다 (실시간 배틀과 같다)", all(m["level"] == 50 for m in live._team(uid, "champion")))

    def refused(ids_):
        try:
            champion.set_team(uid, ids_)
            return None
        except ValueError as e:
            return str(e)
    msg = refused([ids[s] for s in ("PIKACHU", "CHARIZARD", "BLASTOISE", "VENUSAUR", "SNORLAX", "GENGAR", "GYARADOS")])
    chk("3. 일곱 마리는 거절 ('독도 팀은 최대 6마리')", msg and "독도 팀은 최대 6마리" in msg, msg)
    other_mon = db.q1("SELECT id FROM pokemon WHERE user_id=? LIMIT 1", (other,))["id"]
    chk("   남의 포켓몬은 거절", refused([ids["PIKACHU"], other_mon]) and "내 포켓몬만" in refused([ids["PIKACHU"], other_mon]))
    msg = refused([ids["MEWTWO"], ids["LUGIA"]])
    chk("   전설 · 환상 두 마리는 거절 (문구에 '독도 팀')", msg and "독도 팀에는 전설" in msg, msg)
    chk("   거절되면 등록한 팀은 그대로", species(champion.team(uid))[0] == "PIKACHU")

    champion.set_team(uid, [])
    chk("4. 빈 목록이면 등록을 풀고 다시 랭크 팀", not champion.team_ids(uid) and champion.team_label(uid) == "랭크 팀"
        and species(champion.team(uid))[0] == "GYARADOS")

    champion.set_team(uid, dokdo)
    ctx = {"user": {"id": uid}}
    view = champion.get_team(ctx)
    keys = {"registered", "ids", "pokemon", "levelCap", "maxParty", "restrictedMax", "rankMin", "rankReady"}
    chk("5. 창이 받는 꼴은 랭크 팀 창과 같다 (등록함 · 고른 순서)", keys <= set(view) and view["registered"] is True
        and view["ids"] == dokdo, sorted(view))
    put = champion.put_team(type("B", (), {"ids": []})(), ctx)
    chk("   PUT 빈 목록 -> 등록을 풀고 랭크 팀을 보여 준다", put["registered"] is False and put["ids"] == rank, put["ids"])
    from fastapi import HTTPException
    try:
        champion.put_team(type("B", (), {"ids": [ids["MEWTWO"], ids["LUGIA"]]})(), ctx)
        code = None
    except HTTPException as e:
        code = (e.status_code, e.detail)
    chk("   규칙에 걸리면 400 + 까닭", code and code[0] == 400 and "독도 팀" in code[1], code)
    champion.set_team(uid, dokdo)
    st = champion.state(uid)
    chk("   리그 모습에 teamSet · teamLabel", st.get("teamSet") is True and st.get("teamLabel") == "독도 팀", (st.get("teamSet"), st.get("teamLabel")))

    champion.set_team(uid, [ids["PIKACHU"], ids["CHARIZARD"]])
    why = champion.team_why(uid)
    chk("6. 독도 팀이 리그 조건(6마리)을 못 채우면 막는다", why and "6마리" in why, why)
    champion.set_team(uid, dokdo)
    chk("   채우면 통과", champion.team_why(uid) is None, champion.team_why(uid))

    db.run("DELETE FROM pokemon WHERE id=?", (ids["MEWTWO"],))
    chk("7. 놓아준 포켓몬은 독도 팀에서도 빠진다", ids["MEWTWO"] not in champion.team_ids(uid) and len(champion.team_ids(uid)) == 5,
        champion.team_ids(uid))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
