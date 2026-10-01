# -*- coding: utf-8 -*-
"""전설·환상 한 마리 제한 검사 (시즌 3).

    python server/test_legend_limit.py

시즌 2 까지는 랭크(랜덤·실시간)에만 걸었다. 시즌 3 부터 **모든 팀 배틀**에 건다.

  1. 앞 자리의 한 마리만 나가고 나머지는 쉰다. 순서는 그대로다.
  2. 친구 배틀 — 실제로 싸운 팀(로그의 teams)에 전설·환상이 한 마리.
  3. 관장 — 나가는 팀에 한 마리, 판 처음(인사 뒤)에 누가 쉬는지 알린다.
  4. 레이드 — 나가는 팀에 한 마리. 제한 때문에 두 마리가 안 되면 까닭을 말한다.
  5. 랭크·실시간 — 예전처럼 한 마리.
  6. 바탕화면 야생 배틀은 팀 대 팀이 아니라서 그대로 (교체 목록에 다 있다).
  7. 전설이 없거나 한 마리면 아무것도 안 바뀐다.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-legend-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import battle_routes, db, deps, gym, gym_routes, pvp, raid, raid_routes  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, species, nick=None):
    """species 를 바탕화면 파티 순서대로. nick = {자리: 별명}."""
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x"))
    uid = cur.lastrowid
    for i, sp in enumerate(species):
        db.run("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
               " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
               " on_desktop, slot, met_level, caught_at)"
               " VALUES (?,?,?,50,0,'HARDY',NULL,0,'M',0,70,'{}','{}','[\"TACKLE\"]',1,?,50,'')",
               (uid, sp, (nick or {}).get(i), i))
    return uid


def species_of(mons):
    return [m.get("species") for m in mons]


def main():
    db.init()
    deps.dex()
    legend = pvp.restricted_species()
    chk("전설·환상 목록 (뮤츠·루기아·뮤)", {"MEWTWO", "LUGIA", "MEW"} <= legend)
    chk("  울트라비스트·패러독스는 들어 있지 않다 (예전 랭크 기준 그대로)",
        not ({"NIHILEGO", "GREATTUSK"} & legend), {"NIHILEGO", "GREATTUSK"} & legend)

    print("=== 나누기 ===")
    team, benched = pvp.split_restricted(
        [{"species": s} for s in ("PIKACHU", "LUGIA", "EEVEE", "MEWTWO", "MEW", "SNORLAX")])
    chk("앞의 전설 한 마리만 남고 순서는 그대로",
        species_of(team) == ["PIKACHU", "LUGIA", "EEVEE", "SNORLAX"], species_of(team))
    chk("  나머지는 쉰다", species_of(benched) == ["MEWTWO", "MEW"], species_of(benched))
    chk("restrict 는 예전처럼 (팀, 빠진 수)",
        pvp.restrict([{"species": "MEWTWO"}, {"species": "MEW"}])[1] == 1)
    note = pvp.bench_note([{"species": "MEWTWO", "nickname": "뮤츠짱"}, {"species": "MEW"}])
    chk("알림에 별명·종 이름", "뮤츠짱·뮤" in note and "한 마리만" not in note
        and "1마리만" in note, note)
    chk("쉬는 게 없으면 알림도 없다", pvp.bench_note([]) == "")

    rich = mkuser("부자", ["MEWTWO", "LUGIA", "PIKACHU", "MEW", "SNORLAX"], {1: "루기"})
    rich2 = mkuser("부자2", ["HOOH", "KYOGRE", "EEVEE"])
    plain = mkuser("보통", ["PIKACHU", "EEVEE", "SNORLAX"])
    one = mkuser("하나", ["MEWTWO", "PIKACHU"])
    only = mkuser("전설뿐", ["MEWTWO", "LUGIA"])

    print("\n=== 친구 배틀 ===")
    out = pvp.run_match(rich, rich2, kind="friend", seed=7)
    row = db.q1("SELECT log FROM pvp_match WHERE id=?", (out["matchId"],))
    teams = next(e for e in pvp.unpack(row["log"]) if e.get("t") == "teams")
    me = [x["species"] for x in teams["me"]]
    foe = [x["species"] for x in teams["foe"]]
    chk("건 쪽: 전설 한 마리 (뮤츠) + 나머지", me == ["MEWTWO", "PIKACHU", "SNORLAX"], me)
    chk("받은 쪽도: 칠색조만", foe == ["HOOH", "EEVEE"], foe)
    out = pvp.run_match(plain, one, kind="friend", seed=8)
    row = db.q1("SELECT log FROM pvp_match WHERE id=?", (out["matchId"],))
    teams = next(e for e in pvp.unpack(row["log"]) if e.get("t") == "teams")
    chk("전설이 없거나 한 마리면 그대로",
        [x["species"] for x in teams["me"]] == ["PIKACHU", "EEVEE", "SNORLAX"]
        and [x["species"] for x in teams["foe"]] == ["MEWTWO", "PIKACHU"], teams)

    print("\n=== 랭크·실시간 (예전부터) ===")
    chk("랭크 팀도 한 마리", species_of(pvp.ranked_team(rich)) == ["MEWTWO", "PIKACHU", "SNORLAX"],
        species_of(pvp.ranked_team(rich)))

    print("\n=== 관장 ===")
    region = next(iter(gym.gyms()["_by_region"]))
    r = gym_routes.start(region, ctx={"user": {"id": rich}})
    team = [m["species"] for m in r["battle"]["me"]["team"]]
    chk("나가는 팀에 전설 한 마리", team == ["MEWTWO", "PIKACHU", "SNORLAX"], team)
    kinds = [e.get("t") for e in r["events"]]
    chk("인사 바로 뒤에 쉬는 포켓몬 알림", kinds[:2] == ["intro", "note"], kinds[:4])
    chk("  알림에 별명(루기)과 뮤", "루기·뮤" in r["events"][1]["text"], r["events"][1])
    gym_routes.act(r["id"], gym_routes.ActIn(kind="forfeit"), ctx={"user": {"id": rich}})
    r = gym_routes.start(region, ctx={"user": {"id": plain}})
    chk("쉬는 게 없으면 알림도 없다", not any(e.get("t") == "note" for e in r["events"]),
        [e.get("t") for e in r["events"]])
    gym_routes.act(r["id"], gym_routes.ActIn(kind="forfeit"), ctx={"user": {"id": plain}})

    print("\n=== 레이드 ===")
    chk("나가는 팀에 전설 한 마리",
        species_of(raid.party_of(rich)) == ["MEWTWO", "PIKACHU", "SNORLAX"],
        species_of(raid.party_of(rich)))
    chk("  데리고 다니는 전부는 다섯", len(raid.party_all(rich)) == 5)
    # 레이드 기간·오늘 참가 여부와 상관없이 파티 조건만 본다 (기간이 지나도 돌게)
    real = raid.in_period, raid.played_today
    raid.in_period = lambda now=None: True
    raid.played_today = lambda uid, now=None: False
    try:
        raid._can_play(only, now=None)
        msg = ""
    except ValueError as e:
        msg = str(e)
    finally:
        raid.in_period, raid.played_today = real
    chk("전설 두 마리뿐이면 한 마리만 나가서 못 들어간다 - 까닭을 말한다",
        "전설·환상" in msg and "한 마리만" in msg, msg)
    ov = raid_routes.overview(ctx={"user": {"id": rich}})
    chk("화면용: 나가는 수·전부·알림", ov["party"] == 3 and ov["partyAll"] == 5
        and "루기·뮤" in ov["benchNote"], (ov["party"], ov["partyAll"], ov["benchNote"]))
    ov = raid_routes.overview(ctx={"user": {"id": plain}})
    chk("  쉬는 게 없으면 알림 없음", ov["party"] == ov["partyAll"] == 3
        and ov["benchNote"] == "", (ov["party"], ov["partyAll"], ov["benchNote"]))

    print("\n=== 야생 배틀은 그대로 ===")
    chk("바탕화면 야생 배틀의 교체 목록에는 다 있다",
        len(battle_routes._party(rich)) == 5, len(battle_routes._party(rich)))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
