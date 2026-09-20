# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 검사 — 초대·수락·턴·전적.

    python server/test_live.py

서버를 띄우지 않고 app.live 를 직접 부른다 (test_raid 와 같은 방식).
돈과 점수가 **안 움직이는 것**까지 본다 - 사용자가 '상금 없이 전적만' 으로
정했으므로, 실수로 pvp 쪽 정산을 타면 부계정끼리 돌려 돈을 만들 수 있다.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-live-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import config, db, items, live, pvp, social          # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=4, level=40):
    import random
    import zlib
    from app import deps
    d = deps.dex()
    rng = random.Random(zlib.crc32(name.encode("utf-8")))
    now = live._iso()
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,1000,?,?,'')",
        (name, b"x", b"x", now, now))
    uid = cur.lastrowid
    # 접속해 있는 것으로 (실시간은 둘 다 켜 있어야 한다)
    db.run("INSERT INTO sessions (token_hash, user_id, ip, device, created_at,"
           " last_seen, expires_at) VALUES (?,?,'','t',?,?,?)",
           ("tok-%d" % uid, uid, now, now, now))
    for i in range(mons):
        m = d.roll_wild(level, level, rng)
        db.run(
            "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
            " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
            " on_desktop, slot, met_level, caught_at)"
            " VALUES (?,?,?,?,?,?,0,?,0,?,?,?,?,1,?,?,?)",
            (uid, m["species"], m["level"], m.get("exp", 0), m["nature"],
             m.get("ability"), m.get("gender", "M"), m.get("happiness", 70),
             json.dumps(m["ivs"]), json.dumps(m.get("evs", {})),
             json.dumps(m["moves"]), i, m["level"], now))
    return uid


def befriend(a, b):
    now = live._iso()
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at,"
           " decided_at) VALUES (?,?,'accepted',?,?,?)",
           (min(a, b), max(a, b), a, now, now))


def records(uid):
    return db.q("SELECT * FROM battle_record WHERE user_id=? ORDER BY id", (uid,))


def main():
    db.init()
    print("=== 걸 수 있나 ===")
    a = mkuser("실시간가")
    b = mkuser("실시간나")
    stranger = mkuser("남남")
    chk("친구가 아니면 못 건다",
        "친구끼리만" in (live.can_invite(a, b) or ""), live.can_invite(a, b))
    befriend(a, b)
    chk("친구면 걸 수 있다", live.can_invite(a, b) is None, live.can_invite(a, b))
    chk("자기 자신은 못 건다", "자기 자신" in (live.can_invite(a, a) or ""))
    chk("모르는 사람도 못 건다", live.can_invite(a, stranger) is not None)
    # 접속을 끊어 본다
    db.run("UPDATE sessions SET last_seen='2020-01-01T00:00:00+00:00'"
           " WHERE user_id=?", (b,))
    chk("상대가 접속해 있지 않으면 못 건다",
        "접속" in (live.can_invite(a, b) or ""), live.can_invite(a, b))
    db.run("UPDATE sessions SET last_seen=? WHERE user_id=?", (live._iso(), b))

    print("=== 초대 ===")
    row = live.invite(a, b)
    chk("초대가 생긴다", row["state"] == "invited", row["state"])
    chk("건 사람이 a", row["a_id"] == a and row["b_id"] == b)
    chk("둘 다 같은 판을 본다",
        live.my_match(a)["id"] == row["id"] and live.my_match(b)["id"] == row["id"])
    v = live.public(row, b)
    chk("받은 쪽은 b", v["me"] == "b" and v["mine"] is False, (v["me"], v["mine"]))
    chk("상대 이름이 보인다", v["foeName"] == "실시간가", v["foeName"])
    chk("남은 시간을 준다", 0 < v.get("inviteLeft", 0) <= config.LIVE_INVITE_SEC,
        v.get("inviteLeft"))
    chk("아직 판은 없다", "battle" not in v)
    chk("걸어 둔 채로 또 못 건다", live.can_invite(a, b) is not None)
    card = live.me_card(b)
    chk("/api/me 가 받은 초대를 알린다", card and card.get("invited") is True, card)
    chk("건 사람에게는 초대가 아니다", (live.me_card(a) or {}).get("invited") is False)

    print("=== 거절 ===")
    live.answer(b, row["id"], False)
    row = live.get(row["id"])
    chk("거절하면 끝", row["state"] == "done" and row["result"] == "declined",
        (row["state"], row["result"]))
    chk("거절은 결과 알림에 안 뜬다", live.unseen(a) == 0, live.unseen(a))
    chk("다시 걸 수 있다", live.can_invite(a, b) is None)

    print("=== 수락하면 판이 열린다 ===")
    row = live.invite(a, b)
    row = live.accept(b, row["id"])
    chk("싸우는 중", row["state"] == "fighting", row["state"])
    va, vb = live.public(row, a), live.public(row, b)
    chk("양쪽 다 판을 본다", "battle" in va and "battle" in vb)
    chk("a 의 me 는 나", va["battle"]["me"]["name"] == "실시간가")
    chk("b 의 me 는 나", vb["battle"]["me"]["name"] == "실시간나")
    chk("전원 Lv.%d" % config.LIVE_LEVEL,
        all(x["level"] == config.LIVE_LEVEL
            for x in va["battle"]["me"]["team"] + va["battle"]["foe"]["team"]),
        [x["level"] for x in va["battle"]["me"]["team"]])
    chk("내 기술만 나에게",
        va["battle"]["me"].get("moves") and "moves" not in va["battle"]["foe"])
    chk("제한 시간을 준다", 0 < va.get("deadlineIn", 0) <= config.LIVE_TURN_SEC,
        va.get("deadlineIn"))
    chk("시작 연출이 실려 온다", any(e.get("t") == "intro" for e in va["events"]))
    # a 가 먼저 소개되므로 b 화면에서는 **첫 줄이 상대**다. 양쪽 다
    # 자기 것 하나, 상대 것 하나가 되어야 한다.
    sw_b = [e for e in vb["events"] if e.get("t") == "switch"]
    chk("b 쪽 연출은 뒤집혀 있다",
        sorted(e["who"] for e in sw_b) == ["foe", "me"], [e["who"] for e in sw_b])
    chk("b 화면의 me 는 b 의 포켓몬",
        [e for e in sw_b if e["who"] == "me"][0]["mon"]["name"]
        == vb["battle"]["me"]["team"][vb["battle"]["me"]["slot"]]["name"])
    chk("남이 못 본다", live.public(row, stranger) is None)

    print("=== 한쪽만 골라서는 안 돈다 ===")
    turn = live.get(row["id"])["turn"]
    mv = va["battle"]["me"]["moves"][0]["key"]
    row = live.act(a, "move", mv)
    chk("고른 것이 남는다", live.public(row, a)["battle"]["me"]["chosen"] is True)
    chk("턴은 그대로", row["turn"] == turn, row["turn"])
    chk("상대에게는 '골랐다' 만", live.public(row, b)["battle"]["foe"]["chosen"] is True)
    mv2 = live.public(row, b)["battle"]["me"]["moves"][0]["key"]
    step = live.public(row, a)["step"]
    row = live.act(b, "move", mv2)
    chk("둘 다 고르면 턴이 돈다", row["turn"] == turn + 1, row["turn"])
    ev = json.loads(row["events"])
    chk("일어난 일이 실린다", len(ev) > 0)

    # **step 은 turn 과 따로 센다.** 교체(_do_switches)는 턴을 안 올리므로,
    # 화면이 turn 만 보면 상대가 다음 포켓몬을 내보낸 것을 못 알아채고
    # 제한 시간이 다 갈 때까지 옛 화면에 앉아 있게 된다 - 실제로 그랬다.
    chk("판이 움직이면 step 이 오른다", live.public(row, a)["step"] > step,
        (step, live.public(row, a)["step"]))
    chk("양쪽이 같은 step 을 본다",
        live.public(row, a)["step"] == live.public(row, b)["step"])
    before = live.public(row, a)["step"]
    lb = live._load(row)
    lb.a.mon.hp = 0
    lb.a.mon.ab["fainted"] = True
    lb._settle([])
    live._save(row, lb, [], None)
    row = live.get(row["id"])
    chk("쓰러지면 교체 차례", live.public(row, a)["battle"]["phase"] == "switch",
        live.public(row, a)["battle"]["phase"])
    turn_before = row["turn"]
    row = live.act(a, "switch", [i for i in lb.a.alive_slots()
                                 if i != lb.a.slot][0])
    chk("교체는 턴을 안 올린다", row["turn"] == turn_before, row["turn"])
    chk("그래도 step 은 오른다 (기다리는 쪽이 알아채야 한다)",
        live.public(row, b)["step"] > before,
        (before, live.public(row, b)["step"]))

    print("=== 시간을 넘기면 서버가 대신 ===")
    turn = row["turn"]
    row = live.tick(row, live._now() + datetime.timedelta(
        seconds=config.LIVE_TURN_SEC + 2))
    chk("마감이 지나면 넘어간다", row["turn"] == turn + 1, row["turn"])
    lb = live._load(row)
    chk("대신 고른 횟수를 센다", lb.a.auto + lb.b.auto >= 2, (lb.a.auto, lb.b.auto))
    chk("마감 전에는 안 넘어간다",
        live.tick(live.get(row["id"]))["turn"] == row["turn"])

    print("=== 끝까지 ===")
    n = 0
    while live.get(row["id"])["state"] == "fighting" and n < 300:
        n += 1
        row = live.tick(live.get(row["id"]), live._now() + datetime.timedelta(
            seconds=(config.LIVE_TURN_SEC + 2) * n))
    row = live.get(row["id"])
    chk("판이 끝난다", row["state"] == "done", row["state"])
    chk("결과가 셋 중 하나", row["result"] in ("a", "b", "draw"), row["result"])
    va = live.public(row, a)
    chk("내 기준 승패를 준다", va["outcome"] in ("win", "lose", "draw"), va["outcome"])
    chk("반대쪽은 반대",
        {"win": "lose", "lose": "win", "draw": "draw"}[va["outcome"]]
        == live.public(row, b)["outcome"])

    print("=== 전적만 남고 돈·점수는 안 움직인다 ===")
    ra, rb = records(a), records(b)
    chk("양쪽에 한 줄씩", len(ra) == 1 and len(rb) == 1, (len(ra), len(rb)))
    chk("종류가 live", ra[0]["kind"] == "live", ra[0]["kind"])
    chk("승패가 반대",
        {"win": "lose", "lose": "win", "draw": "draw"}[ra[0]["result"]]
        == rb[0]["result"], (ra[0]["result"], rb[0]["result"]))
    chk("상금 없음", ra[0]["reward"] == 0 and rb[0]["reward"] == 0)
    chk("점수 안 움직임",
        ra[0]["delta"] == 0 and ra[0]["rp_delta"] == 0, (ra[0]["delta"], ra[0]["rp_delta"]))
    chk("돈이 그대로", items.money(a) == 1000 and items.money(b) == 1000,
        (items.money(a), items.money(b)))
    chk("랭크 점수가 그대로",
        not db.q1("SELECT 1 FROM rank_stat WHERE user_id=? AND rating<>1000", (a,)))
    chk("다시 보기 단추가 안 뜬다 (로그가 없다)", ra[0]["match_id"] is None)
    chk("남은 마릿수를 적는다", ra[0]["my_left"] + ra[0]["foe_left"] >= 0)
    chk("두 번 불러도 전적이 안 는다",
        (live._record(row, live._load(row)), len(records(a)))[1] == 1, len(records(a)))

    print("=== 결과를 볼 때까지 남는다 ===")
    chk("안 본 결과를 센다", live.unseen(a) == 1 and live.unseen(b) == 1)
    chk("끝나도 조회된다", live.current(a) is not None)
    live.mark_seen(a)
    chk("보면 빠진다", live.unseen(a) == 0 and live.current(a) is None)
    chk("상대는 아직 안 봤다", live.unseen(b) == 1)

    print("=== 기권 ===")
    befriend_pair = (mkuser("기권가"), mkuser("기권나"))
    befriend(*befriend_pair)
    c, d_ = befriend_pair
    row = live.accept(d_, live.invite(c, d_)["id"])
    row = live.act(c, "forfeit", None)
    chk("기권하면 바로 끝", row["state"] == "done", row["state"])
    chk("건 사람이 진다", row["result"] == "b", row["result"])
    chk("까닭이 남는다", row["reason"] == "forfeit", row["reason"])
    chk("전적에 남는다", records(c)[0]["result"] == "lose", records(c)[0]["result"])

    print("=== 초대는 시간이 지나면 만료 ===")
    e, f = mkuser("만료가"), mkuser("만료나")
    befriend(e, f)
    row = live.invite(e, f)
    later = live._now() + datetime.timedelta(seconds=config.LIVE_INVITE_SEC + 5)
    row = live.tick(row, later)
    chk("만료된다", row["state"] == "done" and row["result"] == "expired",
        (row["state"], row["result"]))
    chk("만료는 결과 알림에 안 뜬다", live.unseen(e) == 0)
    chk("다시 걸 수 있다", live.can_invite(e, f) is None, live.can_invite(e, f))

    print("=== 남이 끼어들 수 없다 ===")
    g, h = mkuser("끼어가"), mkuser("끼어나")
    befriend(g, h)
    row = live.accept(h, live.invite(g, h)["id"])
    try:
        live.act(stranger, "move", "TACKLE")
        chk("참가자가 아니면 못 움직인다", False)
    except LookupError:
        chk("참가자가 아니면 못 움직인다", True)
    try:
        live.answer(stranger, row["id"], True)
        chk("남이 수락 못 한다", False)
    except LookupError:
        chk("남이 수락 못 한다", True)
    chk("싸우는 중에는 새 초대를 못 건다", live.can_invite(g, h) is not None)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
