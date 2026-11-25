# -*- coding: utf-8 -*-
"""더블배틀 (독도 · 실시간) 서버 검사 - 2026-11-25.

    python server/test_live_double.py

서버를 띄우지 않는다 (임시 DB). 앱으로 나가는 알림(visit.push)은 가로채서 본다.

무엇을 못 박나:
  1. 판의 형식(live_match.fmt): 더블 판은 더블 엔진으로 열리고, 두 마리 몫을 **한 번에** 보낸다 (kind="picks").
     싱글 방식(기술 하나)으로는 못 고른다. 한 턴은 45초 (싱글 30초). 넘기면 서버가 대신 고른다.
  2. 독도: [더블 상대 찾기] 는 더블을 기다리는 사람끼리만 붙는다 (싱글을 기다리는 사람과는 안 붙는다).
     한 사람은 한 형식만 기다린다. 직접 도전도 형식을 따른다.
  3. 전적 · 순위는 형식마다 따로 센다. 지금 있던 열쇠(순위 · 내 전적 · 최근 판 · 진행 중)는 **싱글 그대로**이고,
     더블은 state(double=True) 의 "double" 아래에 온다 (옛 앱은 못 본다).
  4. 옛 앱 지키기: 더블 초대를 받은 사람의 앱이 더블을 모르면(GET /api/live 에 double=1 이 없다) 그 자리에서
     거절로 접고, 건 사람에게 까닭을 알린다. 옛 앱에는 더블 판이 보이지 않는다.
  5. 더블 판은 관전하지 않는다 (목록에는 나오되 [관전] 은 없다). 다른 참가자에게 '판이 열렸다' 를 밀지 않는다.
  6. 상대의 지닌 도구는 판 어디에도 실리지 않는다.
"""
import datetime
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-live-double-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_CHAMPION_START"] = "2020-01-01T00:00:00+09:00"

from common.pokelogic import make_pokemon                            # noqa: E402

from app import champion, config, db, deps, gym, live, live_routes, visit   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
TEAM = ("PIKACHU", "BULBASAUR", "CHARMANDER", "SQUIRTLE", "EEVEE", "MACHOP")
HELD = ("LEFTOVERS", "LIFEORB", "SITRUSBERRY", "FOCUSSASH", "ROCKYHELMET", "CHOICESCARF")
PUSHED = []
visit.push = lambda uid, payload: PUSHED.append((uid, payload))
champion._schedule = lambda delay: None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name, level=50, mons=6):
    now = live._iso()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,1000,?,?,'')",
                 (name, b"x", b"x", now, now)).lastrowid
    db.run("INSERT INTO sessions (token_hash, user_id, ip, device, created_at, last_seen, expires_at)"
           " VALUES (?,?,'','t',?,?,?)", ("tok-%d" % uid, uid, now, now, now))
    d = deps.dex()
    rng = random.Random(uid)
    for i, sp in enumerate(TEAM[:mons]):
        m = make_pokemon(d.get(sp), level, rng)
        db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
               " shiny, happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at, held)"
               " VALUES (?,?,?,0,?,?,0,?,0,70,?,?,?,1,?,?,?,?)",
               (uid, m["species"], level, m["nature"], m.get("ability"), m.get("gender", "M"),
                json.dumps(m["ivs"]), json.dumps(m.get("evs", {})), json.dumps(m["moves"]), i, level, now, HELD[i]))
    return uid


def member(name):
    uid = mkuser(name)
    now = live._iso()
    for code in sorted(gym.gyms()["regions"]):
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at, last_at, paid_on)"
               " VALUES (?,?,?,1,5,?,?,'')", (uid, code, gym.gyms()["regions"][code], now, now))
    champion.qualify(uid)
    return uid


def pushed(uid, s=None):
    return [p for u, p in PUSHED if u == uid and p.get("t") == "champion" and (s is None or p.get("s") == s)]


def ctx(uid):
    return {"user": {"id": uid}}


def picks_of(view):
    """화면이 받은 판(view)만 보고 두 마리 몫을 고른다 - 첫 기술을 첫 대상에게."""
    me = view["me"]
    if view["phase"] == "switch":
        left = list(me["switches"])
        return [{"pos": pos, "kind": "switch", "slot": left.pop(0)} for pos in me["need"]]
    out = []
    for act in me["acts"]:
        if act is None:
            continue
        m = next((x for x in act["moves"] if not x["blocked"] and x["pp"] > 0), act["moves"][0])
        out.append({"pos": act["pos"], "kind": "move", "move": m["key"],
                    "target": m["targets"][0] if m["targets"] else None})
    return out


def main():
    db.init()
    champion.reset()
    cols = [r["name"] for r in db.q("PRAGMA table_info(live_match)")]
    print("=== 판의 형식 ===")
    chk("live_match 에 fmt 칸이 있다 (기본 single)", "fmt" in cols, cols)
    a, b, c, d = member("가람"), member("나래"), member("다솜"), member("라온")

    PUSHED[:] = []
    chk("더블을 기다리기 시작한다", champion.seek(a, True, fmt="double") is None)
    st = champion.state(a, double=True)
    chk("  더블 쪽에만 '기다리는 중' 이 켜진다", st["double"]["seeking"] is True and st["seeking"] is False,
        (st["double"]["seeking"], st["seeking"]))
    chk("  다른 사람에게는 더블을 기다리는 사람으로 보인다",
        [w["id"] for w in champion.state(b, double=True)["double"]["waiting"]] == [a]
        and champion.state(b)["waiting"] == []
        and next(o for o in champion.state(b, double=True)["online"] if o["id"] == a).get("waiting2") is True)
    chk("싱글을 찾는 사람과는 안 붙는다", champion.seek(b, True) is None and live.my_match(a) is None)
    chk("  한 사람은 한 형식만 기다린다 (더블로 바꾸면 싱글 대기는 사라진다)",
        champion.state(b)["seeking"] is True)
    row = champion.seek(b, True, fmt="double")
    chk("더블을 찾으면 기다리던 사람과 그 자리에서 열린다 (먼저 기다린 사람이 a)",
        row is not None and row["state"] == "fighting" and row["a_id"] == a and row["b_id"] == b
        and live.fmt_of(row) == "double" and live.kind_of(row) == "champion", row and dict(row).get("fmt"))
    chk("  싱글 대기도 같이 걷힌다", champion.state(b)["seeking"] is False and champion.state(b, double=True)["double"]["seeking"] is False)
    chk("  두 사람에게 '판이 열렸다' 가 형식과 함께 간다",
        [p.get("fmt") for p in pushed(a, "match")] == ["double"] and len(pushed(b, "match")) == 1, pushed(a))
    chk("  다른 참가자에게 '관전하라' 는 알림은 안 간다 (더블은 관전이 없다)", not pushed(c, "fight") and not pushed(d, "fight"))

    pa, pb = live.public(live.get(row["id"]), a), live.public(live.get(row["id"]), b)
    chk("판: 형식 · 한 턴 45초 · 두 마리씩", pa["fmt"] == "double" and pa["turnSec"] == config.LIVE_TURN_SEC_DOUBLE == 45
        and pa["battle"]["fmt"] == "double" and pa["battle"]["me"]["active"] == [0, 1]
        and 40 <= pa["deadlineIn"] <= 45, (pa.get("fmt"), pa.get("turnSec"), pa.get("deadlineIn")))
    blob = json.dumps(pb, ensure_ascii=False)
    chk("상대의 지닌 도구는 판 어디에도 없다 (내 것은 있다)",
        pb["battle"]["me"]["team"][0]["held"] == "LEFTOVERS"
        and not any("held" in m for m in pb["battle"]["foe"]["team"])
        and all("held" not in e.get("mon", {}) for e in pb["events"] if e.get("t") == "switch" and e.get("who") == "foe")
        and blob.count("먹다남은음식") == blob.count("LEFTOVERS") == 2,
        (blob.count("먹다남은음식"), blob.count("LEFTOVERS")))
    chk("  일 목록의 자리는 보는 사람 기준이다", sorted(e["at"] for e in pb["events"] if e.get("t") == "switch")
        == ["foe0", "foe1", "me0", "me1"], [e.get("at") for e in pb["events"]])

    print("=== 고르기 ===")
    try:
        live.act(a, "move", pa["battle"]["me"]["acts"][0]["moves"][0]["key"])
        single = True
    except ValueError:
        single = False
    chk("싱글 방식(기술 하나)으로는 못 고른다", not single)
    r = live.act(a, "picks", picks_of(pa["battle"]))
    chk("한쪽만 고르면 턴이 안 돈다", r["turn"] == 0 and live.public(r, b)["battle"]["foe"]["chosen"] is True)
    r = live.act(b, "picks", picks_of(pb["battle"]))
    chk("둘 다 고르면 턴이 돈다", r["turn"] == 1 and r["state"] == "fighting", (r["turn"], r["state"]))
    ev = live.public(r, a)["events"]
    chk("  일마다 누구의 일인지 자리가 붙는다", len([e for e in ev if e.get("t") == "move"]) >= 3
        and all(str(e.get("at", "")).startswith(e["who"]) for e in ev
                if e.get("who") in ("me", "foe") and e.get("t") not in ("choose", "over", "intro")),
        [(e.get("t"), e.get("who"), e.get("at")) for e in ev][:8])
    late = datetime.datetime.fromisoformat(r["deadline"]) + datetime.timedelta(seconds=1)
    early = late - datetime.timedelta(seconds=10)
    chk("제한 시간 전에는 안 넘어간다", live.tick(r, early)["turn"] == 1)
    r = live.tick(r, late)
    chk("제한 시간이 지나면 서버가 두 마리 몫을 대신 고른다", r["turn"] == 2, r["turn"])

    body = live_routes.ActIn(kind="picks", picks=picks_of(live.public(r, a)["battle"]))
    out = live_routes.act(body, ctx(a))
    chk("POST /api/live/act {kind: picks, picks: [...]}", out["fmt"] == "double" and out["battle"]["me"]["chosen"] is True)
    try:
        live_routes.act(live_routes.ActIn(kind="picks", picks=[{"pos": 0, "kind": "move", "move": "NOPE"}]), ctx(b))
        bad = None
    except Exception as e:                                  # noqa: BLE001
        bad = getattr(e, "status_code", None)
    chk("  잘못 고르면 409", bad == 409, bad)

    print("=== 옛 앱 ===")
    chk("옛 앱(GET /api/live 에 double 이 없다)에는 진행 중인 더블 판이 안 보인다",
        live_routes.mine(ctx=ctx(b))["match"] is None and live_routes.mine(double=1, ctx=ctx(b))["match"]["fmt"] == "double")
    live.act(b, "forfeit", None)
    done = live.get(row["id"])
    chk("기권으로 끝난다 · 전적은 한 번만", done["state"] == "done" and done["result"] == "a" and done["recorded"] == 1
        and db.q1("SELECT COUNT(*) c FROM battle_record WHERE user_id=?", (a,))["c"] == 1)
    live.mark_seen(a)
    live.mark_seen(b)

    PUSHED[:] = []
    inv = champion.challenge(c, d, fmt="double")
    chk("직접 도전: 상대가 받아야 시작한다 (형식은 더블)", inv["state"] == "invited" and live.fmt_of(inv) == "double"
        and [p.get("fmt") for p in pushed(d, "ask")] == ["double"], pushed(d))
    got = live_routes.mine(ctx=ctx(d))
    after = live.get(inv["id"])
    chk("옛 앱이 더블 초대를 물으면 그 자리에서 거절로 접힌다", got["match"] is None and after["state"] == "done"
        and after["result"] == "declined" and live.my_match(c) is None, (after["state"], after["result"]))
    why = pushed(c, "declined")
    chk("  건 사람에게 까닭이 간다", len(why) == 1 and "더블" in why[0].get("why", "") and why[0].get("id") == inv["id"], why)
    inv = champion.challenge(c, d, fmt="double")
    got = live_routes.mine(double=1, ctx=ctx(d))
    chk("새 앱에는 초대가 보이고, 받으면 열린다", got["match"]["state"] == "invited" and got["match"]["fmt"] == "double")
    opened = live.answer(d, inv["id"], True)
    chk("  더블 판으로 열린다", opened["state"] == "fighting" and live.public(opened, c)["battle"]["fmt"] == "double")

    print("=== 관전 · 목록 ===")
    st = champion.state(a, double=True)
    chk("진행 중인 더블 판은 더블 목록에만 나온다 (싱글 목록 = 옛 앱이 [관전] 을 누르는 곳)",
        [f["id"] for f in st["double"]["fights"]] == [opened["id"]] and st["fights"] == [], (st["fights"], st["double"]["fights"]))
    try:
        champion.watch(a, opened["id"])
        w = None
    except ValueError as e:
        w = str(e)
    chk("더블 판은 관전할 수 없다", w is not None and "더블" in w, w)
    sp = champion.fight(opened["id"], a)
    chk("  구경용 모습에는 포켓몬이 실리지 않는다", sp is not None and sp.get("fmt") == "double" and "mon" not in sp["a"]
        and sp["events"] == [], sp and sorted(sp["a"]))
    live.act(d, "forfeit", None)
    live.mark_seen(c)
    live.mark_seen(d)

    print("=== 전적 · 순위는 형식마다 ===")
    r1 = champion.challenge(a, c)                           # 싱글 한 판: c 가 이긴다
    live.answer(c, r1["id"], True)
    live.act(a, "forfeit", None)
    live.mark_seen(a)
    live.mark_seen(c)
    st = champion.state(a, double=True)
    single = dict((r["id"], r) for r in st["ranking"])
    double = dict((r["id"], r) for r in st["double"]["ranking"])
    chk("싱글 순위에는 싱글 판만", single[c]["wins"] == 1 and single[a]["losses"] == 1 and single[a]["wins"] == 0
        and single[b]["played"] == 0, (single[a], single[c]))
    chk("더블 순위에는 더블 판만", double[a]["wins"] == 1 and double[b]["losses"] == 1 and double[c]["wins"] == 1
        and double[d]["losses"] == 1 and double[a]["losses"] == 0, (double[a], double[c]))
    chk("  내 전적도 따로", st["me"]["wins"] == 0 and st["me"]["losses"] == 1 and st["double"]["me"]["wins"] == 1
        and st["double"]["me"]["played"] == 1, (st["me"], st["double"]["me"]))
    chk("  최근 판도 따로", [x["foeId"] for x in st["recent"]] == [c] and [x["foeId"] for x in st["double"]["recent"]] == [b]
        and st["double"]["recent"][0]["outcome"] == "win", (st["recent"], st["double"]["recent"]))
    old = champion.state(a)
    chk("옛 앱이 묻는 모습(double 없이)에는 더블 칸이 없고 싱글은 그대로", "double" not in old and old["ranking"] == st["ranking"]
        and old["me"] == st["me"])
    chk("GET /api/champion?double=1", "double" in champion.get_state(double=1, ctx=ctx(a))
        and "double" not in champion.get_state(ctx=ctx(a)))

    print("=== 기다리는 사람에게 도전 ===")
    champion.reset()
    champion.seek(b, True, fmt="double")
    r2 = champion.challenge(a, b)                           # b 는 더블을 기다린다 - 싱글 도전은 물어본다
    chk("더블을 기다리는 사람에게 싱글로 도전하면 바로 열리지 않고 묻는다", r2["state"] == "invited" and live.fmt_of(r2) == "single")
    live.answer(b, r2["id"], False)
    champion.seek(b, True, fmt="double")
    r3 = champion.challenge(a, b, fmt="double")
    chk("더블로 도전하면 바로 시작한다 (기다리던 사람이 a 자리)", r3["state"] == "fighting" and r3["a_id"] == b
        and live.fmt_of(r3) == "double")
    out = champion.post_seek(champion.SeekIn(on=False, fmt="double", double=True), ctx(c))
    chk("POST /api/champion/seek {fmt, double}", "double" in out and out["double"]["seeking"] is False)

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
