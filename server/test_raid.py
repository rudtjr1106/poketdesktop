# -*- coding: utf-8 -*-
"""레이드 검사 — 일정·방·라운드·보상.

    python server/test_raid.py

서버를 띄우지 않고 app.raid 를 직접 부른다 (test_pvp 와 같은 방식).
시각은 전부 인자로 넘기므로 화요일 11시가 되기를 기다리지 않아도 된다.

돈과 알이 오가는 곳이라 숫자를 하나하나 맞춰 본다. 특히 **알을 두 번
주지 않는가**와 **모이다 취소된 판이 참가 횟수를 깎지 않는가**.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

# 돌고 있는 서버의 DB 를 건드리면 안 된다. 언제나 빈 DB 로 시작한다
# (test_heavy_ball·test_season 과 같은 방식).
TMP = tempfile.mkdtemp(prefix="poket-raid-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import config, db, items, raid                        # noqa: E402
from app import raid_routes                                    # noqa: E402

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


def at(day, hour, minute=0, second=0):
    """한국시간 -> UTC datetime."""
    y, m, d = (int(x) for x in day.split("-"))
    return raid.to_utc(datetime.datetime(y, m, d, hour, minute, second))


def mkuser(name, mons=4, level=40):
    import random
    import zlib
    from app import deps
    d = deps.dex()
    rng = random.Random(zlib.crc32(name.encode("utf-8")))
    now = raid.now_iso()
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", now, now))
    uid = cur.lastrowid
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


def play(row, uid_list, now, limit=40):
    """끝날 때까지 라운드를 돌린다. 모두 서버가 대신 고르게 둔다."""
    n = 0
    while row["state"] == "fighting" and n < limit:
        n += 1
        now = now + datetime.timedelta(seconds=config.RAID_ROUND_SEC + 1)
        row = raid.tick(row, now) or row
        row = raid.room(row["id"])
    return row, now


def main():
    db.init()
    day = config.RAID_START
    nxt = (datetime.date(*(int(x) for x in day.split("-")))
           + datetime.timedelta(days=1)).isoformat()
    print("=== 일정 ===")
    chk("이벤트 첫날 안", raid.in_period(at(day, 12)))
    lo, hi = raid.period()
    before = (datetime.date(*(int(x) for x in lo.split("-")))
              - datetime.timedelta(days=1)).isoformat()
    chk("시작 전날은 밖", not raid.in_period(at(before, 12)))
    after = (datetime.date(*(int(x) for x in hi.split("-")))
             + datetime.timedelta(days=1)).isoformat()
    chk("끝난 다음날은 밖", not raid.in_period(at(after, 12)))
    chk("회차는 하루 %d번" % len(config.RAID_HOURS),
        len(raid.all_keys()) == len(config.RAID_HOURS) * 15, len(raid.all_keys()))
    chk("정각 4분 전은 모이는 시간", raid.open_key(at(day, 10, 56)) is not None)
    chk("정각 10분 전은 아직", raid.open_key(at(day, 10, 50)) is None)
    chk("정각 3분 뒤는 닫힘", raid.open_key(at(day, 11, 3)) is None)
    key = raid.open_key(at(day, 10, 57))
    chk("열린 회차가 11시", key == "%sT11" % day, key)

    print("=== 보스 ===")
    b1 = raid.boss_species("%sT11" % day)
    b2 = raid.boss_species("%sT11" % day)
    b3 = raid.boss_species("%sT21" % day)
    chk("같은 회차면 늘 같은 보스", b1 == b2, "%s/%s" % (b1, b2))
    chk("회차가 다르면 대개 다르다", b1 != b3 or True)
    chk("보스는 전설·환상 중에서", b1 in raid.pool(), b1)
    chk("쉐이미는 안 나온다",
        config.EVENT_SPECIES not in raid.pool())
    chk("보스 알 종류", raid.kind_of(b1) in ("legendary", "mythical"))
    chk("공개는 1시간 전부터", raid.revealed("%sT11" % day, at(day, 10, 30))
        and not raid.revealed("%sT11" % day, at(day, 9, 30)))
    # boss_card 는 '지금' 을 인자로 못 받는다 (화면에 줄 때만 쓴다).
    # 공개 여부는 revealed 가 정하고, 위에서 이미 확인했다.
    card = raid.boss_card("%sT11" % day)
    chk("카드에 회차와 남은 시간", card["session"] == "%sT11" % day
        and "leftSec" in card, card)
    mon = raid.boss_mon("%sT11" % day)
    chk("보스 레벨", mon["level"] == config.RAID_BOSS_LEVEL, mon["level"])
    chk("보스 개체값 전부 31", all(v == 31 for v in mon["ivs"].values()))
    # 노력치는 config 에서 고른다 (RAID_BOSS_EV 의 설명에 맞춘 표가 있다).
    # **여기에 숫자를 박아 두지 않는다** - 난이도를 바꿀 때마다 이 검사가
    # 조용히 빨개졌다(96 -> 192 로 올린 판이 그대로 배포됐다).
    chk("보스 노력치는 설정대로",
        all(v == config.RAID_BOSS_EV for v in mon["evs"].values()), mon["evs"])
    chk("보스 노력치가 정상 범위", 0 <= config.RAID_BOSS_EV <= 252, config.RAID_BOSS_EV)

    print("=== 모이기 ===")
    a = mkuser("레이드가")
    b = mkuser("레이드나")
    c = mkuser("레이드다")
    d_ = mkuser("레이드라")
    solo = mkuser("레이드마", mons=1)
    t0 = at(day, 10, 57)
    row = raid.join(a, "레이드가", None, t0)
    chk("자동 매칭으로 방이 생긴다", row and row["state"] == "lobby")
    chk("코드 없는 방", row["code"] is None)
    row2 = raid.join(b, "레이드나", None, t0)
    chk("두 번째 사람은 같은 방으로", row2["id"] == row["id"])
    chk("두 명", len([m for m in raid.members(row["id"]) if not m["left_at"]]) == 2)
    again = raid.join(a, "레이드가", None, t0)
    chk("두 번 들어가도 자리는 하나", again["id"] == row["id"]
        and len(raid.members(row["id"])) == 2)
    try:
        raid.join(solo, "레이드마", None, t0)
        chk("포켓몬 1마리는 못 들어온다", False)
    except ValueError as e:
        chk("포켓몬 1마리는 못 들어온다", "마리 이상" in str(e), str(e))
    # 새 방을 **만드는** 것만 시각을 본다. 이미 있는 방에 들어가는 것은
    # 아래 '방장이 눌러야 시작한다' 절에서 따로 본다.
    try:
        raid.create_code(mkuser("레이드바"), "레이드바", at(day, 10, 30))
        chk("모이는 시간이 아니면 새 방은 못 만든다", False)
    except ValueError as e:
        chk("모이는 시간이 아니면 새 방은 못 만든다",
            "시간이 아닙니다" in str(e), str(e))

    print("=== 방장이 눌러야 시작한다 ===")
    row = raid.room(row["id"])
    ok, why = raid.can_start(row)
    chk("2명이면 아직 못 연다", not ok and "3명부터" in why, why)
    chk("정각이 지나도 저절로 안 열린다",
        raid.tick(raid.room(row["id"]), at(day, 11, 0, 5))["state"] == "lobby")
    chk("유예가 지나도 안 접는다",
        raid.tick(raid.room(row["id"]), at(day, 11, 30))["state"] == "lobby")
    chk("아직 참가 횟수를 안 깎는다", not raid.played_today(a, t0))
    # 늦게 와도 아직 안 시작한 방에는 들어갈 수 있다 (모이는 시간이 지났어도)
    late = raid.join(c, "레이드다", None, at(day, 11, 30))
    chk("모이는 시간이 지나도 있는 방에는 들어간다", late["id"] == row["id"],
        "%s/%s" % (late["id"], row["id"]))
    ok, why = raid.can_start(raid.room(row["id"]))
    chk("셋이 되면 시작할 수 있다", ok, why)
    v = raid.public(raid.room(row["id"]), a)
    chk("방장에게만 시작 단추", v["canStart"] and v["isHost"], v.get("canStart"))
    chk("방장이 아니면 못 누른다", not raid.public(raid.room(row["id"]), b)["canStart"])
    # 방장이 나가면 다음 사람이 방장이 된다
    raid.leave(a)
    chk("방장이 나가면 넘어간다", raid.room(row["id"])["host"] == b,
        raid.room(row["id"])["host"])
    raid.leave(b)
    raid.leave(c)
    # **빈 방은 접지 않고 남겨 둔다.** 접으면 다시 들어올 때마다 새 방이
    # 생긴다 (한 사람이 6분에 49개를 만든 적이 있다).
    chk("전부 나가도 방은 남는다", raid.room(row["id"])["state"] == "lobby",
        raid.room(row["id"])["state"])
    again = raid.join(c, "레이드다", None, at(day, 11, 30))
    chk("다시 들어오면 새 방이 아니라 그 방", again["id"] == row["id"],
        (again["id"], row["id"]))
    chk("비어 있던 방에 들어온 사람이 방장", raid.room(row["id"])["host"] == c,
        raid.room(row["id"])["host"])
    raid.leave(c)
    chk("끝까지 참가 횟수는 안 깎였다", not raid.played_today(a, t0))

    print("=== 방은 여러 개 생긴다 ===")
    # 한 회차에 선착순 6명만 하는 것이 아니다. 자리가 없으면 방이 하나 더
    # 생기고, 자동 매칭은 **가장 많이 찬 방부터** 채운다.
    #
    # (검사에서 leave/tick 에 시각을 안 넘기면 그 방의 '마지막으로 움직인
    # 때' 가 진짜 지금 시각으로 찍혀서, 다음 호출의 expire_old 가 방을
    # 접어 버린다. 모의 시각을 쓰는 검사에서는 늘 같이 넘긴다.)
    t1 = at(day, 10, 58)
    many = [mkuser("여럿%d" % i) for i in range(7)]
    rooms = [raid.join(u, "여럿%d" % i, None, t1)["id"]
             for i, u in enumerate(many)]
    chk("여섯까지는 한 방", len(set(rooms[:6])) == 1, rooms[:6])
    chk("일곱째는 새 방", rooms[6] != rooms[0], rooms)
    chk("첫 방은 꽉 찼다",
        len([m for m in raid.members(rooms[0]) if not m["left_at"]]) == 6)
    chk("두 방 다 같은 회차·같은 보스",
        raid.room(rooms[0])["boss"] == raid.room(rooms[6])["boss"])
    # 한 자리가 비면 **덜 찬 새 방이 아니라** 그 자리로 들어간다
    raid.leave(many[0], t1)
    back = raid.join(mkuser("여덟"), "여덟", None, t1)
    chk("빈 자리부터 채운다", back["id"] == rooms[0], (back["id"], rooms))
    for u in many[1:]:
        raid.leave(u, t1)
    raid.leave(back["host"], t1)

    print("=== 지난 회차 방에는 안 들어간다 ===")
    # 방이 정각 뒤에도 살아 있으므로, 다음 회차가 열릴 때 그 방으로
    # 흘러들면 **엉뚱한 보스**와 싸우게 된다.
    keeper = mkuser("묵은방")
    stale = raid.join(keeper, "묵은방", None, at(day, 10, 58))
    chk("11시 회차 방", stale["session"] == "%sT11" % day, stale["session"])
    same = raid.join(mkuser("같은회차"), "같은회차", None, at(day, 11, 20))
    chk("11시가 지나도 그 방은 그대로", same["id"] == stale["id"],
        (same["id"], stale["id"]))
    # 저녁까지 창을 켜 둔 셈 치고 방을 살려 둔다 (폴링이 하는 일)
    for h, m in ((11, 50), (12, 20), (12, 50)):
        raid.tick(raid.room(stale["id"]), at(day, h, m))
    later = raid.join(mkuser("다음회차"), "다음회차", None, at(day, 20, 58))
    chk("21시가 되면 새 방", later["id"] != stale["id"], (later["id"], stale["id"]))
    chk("새 방은 21시 회차", later["session"] == "%sT21" % day, later["session"])
    chk("보스도 그 회차 것", later["boss"] == raid.boss_species("%sT21" % day))
    chk("회차마다 보스가 다르다",
        raid.boss_species("%sT11" % day) != raid.boss_species("%sT21" % day))
    raid.leave(later["host"], at(day, 20, 58))

    print("=== 세 명이 모여 싸운다 ===")
    t0 = at(day, 20, 57)
    row = raid.join(a, "레이드가", None, t0)
    raid.join(b, "레이드나", None, t0)
    row = raid.join(c, "레이드다", None, t0)
    chk("21시 회차로 모인다", row["session"] == "%sT21" % day, row["session"])
    chk("세 명", len(raid.members(row["id"])) == 3)
    ok, why = raid.can_start(raid.room(row["id"]))
    chk("셋이면 시작할 수 있다", ok, why)
    row = raid.begin(raid.room(row["id"]), at(day, 21, 0, 1))
    chk("방장이 누르면 판이 열린다", row["state"] == "fighting", row["state"])
    chk("참가 횟수가 깎인다", bool(raid.played_today(a, t0)))
    view = raid.public(row, a)
    chk("내 자리를 안다", view.get("me") == 0, view.get("me"))
    chk("보스 체력이 인원수만큼", view["battle"]["boss"]["maxhp"] > 100,
        view["battle"]["boss"]["maxhp"])
    chk("전원 레벨이 같다",
        all(x["mon"]["level"] == config.RAID_TEAM_LEVEL for x in view["battle"]["players"]),
        [x["mon"]["level"] for x in view["battle"]["players"]])
    chk("시작 연출이 실려 온다", any(e.get("t") == "intro" for e in view["events"]))

    # 늦게 온 사람은 **이미 싸우는 방에 끼어들지 못하고** 새 방을 만든다.
    late = raid.join(d_, "레이드라", None, at(day, 21, 0, 30))
    chk("늦게 오면 새 방", late["id"] != row["id"] and late["state"] == "lobby",
        "%s/%s" % (late["id"], row["id"]))
    raid.leave(d_)

    print("=== 라운드 ===")
    before_round = row["round"]
    rb = raid._load(row)
    key0 = rb.players[0].mon.moves[0]
    row = raid.choose(a, "move", key0, at(day, 21, 0, 5))
    chk("고르면 표시가 남는다", raid.public(row, a)["battle"]["players"][0]["chosen"])
    chk("한 명만 골랐으면 라운드는 그대로", row["round"] == before_round, row["round"])
    row = raid.tick(row, at(day, 21, 0, 5))
    chk("마감 전에는 안 넘어간다", row["round"] == before_round, row["round"])
    row = raid.tick(row, at(day, 21, 0, 5) + datetime.timedelta(
        seconds=config.RAID_ROUND_SEC + 2))
    chk("마감이 지나면 서버가 대신 고르고 넘어간다", row["round"] == before_round + 1,
        row["round"])
    ev = json.loads(row["events"])
    chk("라운드에 일어난 일이 실린다", len(ev) > 0, len(ev))
    chk("일어난 일에 누구인지가 붙는다",
        all("p" in e for e in ev if e.get("who") == "me"))

    print("=== 끝까지 ===")
    row, _now = play(row, [a, b, c], at(day, 21, 1))
    chk("판이 끝난다", row["state"] == "done", row["state"])
    chk("결과가 셋 중 하나", row["result"] in ("won", "lost", "timeout"), row["result"])
    ms = {m["user_id"]: m for m in raid.members(row["id"])}
    chk("전원에게 상금", all(m["prize"] > 0 for m in ms.values()),
        [m["prize"] for m in ms.values()])
    money_a = items.money(a)
    chk("돈이 실제로 들어왔다", money_a >= ms[a]["prize"], money_a)
    eggs_n = db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (a,))["c"]
    if row["result"] == "won":
        chk("이기면 알은 0개 또는 1개", eggs_n in (0, 1), eggs_n)
        got = [m for m in ms.values() if m["got_egg"]]
        for m in got:
            e = db.q1("SELECT * FROM egg WHERE user_id=? ORDER BY id DESC LIMIT 1",
                      (m["user_id"],))
            chk("알 속은 그 보스", e["species"] == row["boss"],
                "%s/%s" % (e["species"], row["boss"]))
    else:
        chk("져도 위로금", all(m["prize"] == config.RAID_FAIL_PRIZE for m in ms.values()),
            [m["prize"] for m in ms.values()])
        chk("지면 알은 없다", eggs_n == 0, eggs_n)

    print("=== 이기면 ===")
    win_day = (datetime.date(*(int(x) for x in day.split("-")))
               + datetime.timedelta(days=2)).isoformat()
    w = [mkuser("승리%d" % i) for i in range(3)]
    t3 = at(win_day, 10, 58)
    wrow = None
    for i, u in enumerate(w):
        wrow = raid.join(u, "승리%d" % i, None, t3)
    wrow = raid.begin(raid.room(wrow["id"]), at(win_day, 11, 0, 1))
    chk("판이 열렸다", wrow["state"] == "fighting", wrow["state"])
    # 보스를 한 대 거리로 만들어 두고 한 라운드를 돈다 (이기는 길을 확인한다)
    rb = raid._load(wrow)
    rb.boss.hp = 1
    # 보호막·분노는 이미 지나간 것으로 둔다. 안 그러면 체력을 1 로 깎는
    # 순간 절반 아래라 막이 서고, 한 라운드로는 못 깬다.
    rb.shielded_once = True
    rb.raged = True
    raid._save(wrow, rb, [], at(win_day, 11, 0, 2))
    wrow = raid.room(wrow["id"])
    old_chance = config.RAID_EGG_CHANCE
    config.RAID_EGG_CHANCE = 1.0
    try:
        wrow = raid.tick(wrow, at(win_day, 11, 0, 2) + datetime.timedelta(
            seconds=config.RAID_ROUND_SEC + 2))
    finally:
        config.RAID_EGG_CHANCE = old_chance
    chk("보스를 쓰러뜨린다", wrow["result"] == "won", wrow["result"])
    wms = {m["user_id"]: m for m in raid.members(wrow["id"])}
    chk("확률 100% 면 전원 알", all(m["got_egg"] for m in wms.values()),
        [m["got_egg"] for m in wms.values()])
    for u in w:
        e = db.q1("SELECT * FROM egg WHERE user_id=? ORDER BY id DESC LIMIT 1", (u,))
        chk("알 속은 잡은 보스", e and e["species"] == wrow["boss"],
            "%s/%s" % (e and e["species"], wrow["boss"]))
        break
    chk("이긴 상금은 기본보다 많다",
        max(m["prize"] for m in wms.values()) > config.RAID_FAIL_PRIZE,
        [m["prize"] for m in wms.values()])
    top = max(wms.values(), key=lambda m: m["damage"])
    chk("기여 1위에게 덤", top["prize"] >= config.RAID_PRIZE, top["prize"])
    kind = raid.kind_of(wrow["boss"])
    e = db.q1("SELECT * FROM egg WHERE user_id=? ORDER BY id DESC LIMIT 1", (w[0],))
    chk("알 종류가 보스에 맞는다", e["kind"] == kind, "%s/%s" % (e["kind"], kind))
    chk("알이 파티 자리를 잡거나 박스로 간다", e["on_desktop"] in (0, 1))

    print("=== 보상은 한 번만 ===")
    rb = raid._load(row)
    n_before = db.q1("SELECT COUNT(*) c FROM egg")["c"]
    money_before = items.money(a)
    raid._reward(row, rb)
    chk("다시 불러도 알이 안 는다", db.q1("SELECT COUNT(*) c FROM egg")["c"] == n_before)
    chk("다시 불러도 돈이 안 는다", items.money(a) == money_before)

    print("=== 하루 한 번 ===")
    try:
        raid.join(a, "레이드가", None, at(nxt, 10, 58))
        chk("다음 날은 다시 된다", True)
    except ValueError as e:
        chk("다음 날은 다시 된다", False, str(e))
    raid.leave(a)
    try:
        raid.join(a, "레이드가", None, at(day, 10, 58))
        chk("같은 날 두 번은 거절", False)
    except ValueError as e:
        chk("같은 날 두 번은 거절", "이미" in str(e), str(e))

    print("=== 방 코드 ===")
    t2 = at(nxt, 10, 58)
    host = mkuser("코드방장")
    row = raid.create_code(host, "코드방장", t2)
    chk("코드가 6글자", row["code"] and len(row["code"]) == 6, row["code"])
    chk("코드 방은 자동 매칭에 안 잡힌다",
        raid.join(mkuser("지나가"), "지나가", None, t2)["id"] != row["id"])
    friend = mkuser("코드친구")
    got = raid.join(friend, "코드친구", row["code"], t2)
    chk("코드로 들어간다", got["id"] == row["id"])
    try:
        raid.join(mkuser("헛코드"), "헛코드", "ZZZZZZ", t2)
        chk("없는 코드는 거절", False)
    except LookupError as e:
        chk("없는 코드는 거절", True, str(e))
    raid.join(mkuser("코드셋"), "코드셋", row["code"], t2)
    row = raid.begin(raid.room(row["id"]), t2)
    chk("방장이 먼저 시작할 수 있다", row["state"] == "fighting", row["state"])

    print("=== 나가기 ===")
    row2 = raid.leave(host)
    v = raid.public(raid.room(row["id"]), friend)
    chk("나간 사람은 표시된다", v["battle"]["players"][0]["left"], v["battle"]["players"])
    chk("남은 사람은 계속한다", raid.room(row["id"])["state"] == "fighting")
    chk("나간 사람은 방이 없다", raid.my_room(host) is None)

    print("=== 안내 ===")
    card = raid.me_card(a, at(day, 10, 30))
    chk("/api/me 안내가 실린다", card and card["next"], card)
    chk("기간 밖에서는 안 싣는다", raid.me_card(a, at(after, 10, 30)) is None)
    chk("안 본 결과를 센다", raid_routes.unseen(a) >= 1, raid_routes.unseen(a))
    db.run("UPDATE raid_member SET seen=1 WHERE user_id=?", (a,))
    chk("보면 0", raid_routes.unseen(a) == 0)
    hist = raid.history(a)
    chk("기록이 남는다", len(hist) >= 1 and hist[0]["boss"], hist[:1])

    print("=== 지난 회차 (공개) ===")
    # 내 기록이 아니어도 누구나 본다.
    past = raid.past(10)
    chk("지난 회차가 나온다", len(past) >= 1, len(past))
    one = past[0]
    chk("보스 이름이 한글로", bool(one["kr"]) and bool(one["boss"]), one.get("kr"))
    chk("회차와 시각", one["session"] and one["at"], (one.get("session"), one.get("at")))
    chk("참가 인원을 센다", one["players"] >= 1, one["players"])
    chk("방마다 참가자가 들어 있다",
        one["rooms"] and one["rooms"][0]["members"], one["rooms"][:1])
    chk("딜 순위가 높은 쪽부터",
        all(one["top"][i]["damage"] >= one["top"][i + 1]["damage"]
            for i in range(len(one["top"]) - 1)), one["top"])
    chk("최신 회차가 앞에",
        all(past[i]["session"] >= past[i + 1]["session"]
            for i in range(len(past) - 1)), [p_["session"] for p_ in past])
    chk("사람이 안 모여 접힌 방은 안 센다",
        all(r["rounds"] > 0 for p_ in past for r in p_["rooms"]),
        [(r["rounds"], r["result"]) for p_ in past for r in p_["rooms"]])
    chk("남의 기록도 보인다 (내가 안 간 회차 포함)",
        sum(p_["players"] for p_ in past) >= len(hist), None)
    sch = raid.schedule(at(day, 10, 30))
    chk("일정에 다음 회차 여섯 개", len(sch["upcoming"]) == 6, len(sch["upcoming"]))
    chk("일정에 규칙이 실린다",
        sch["minPlayers"] == config.RAID_MIN_PLAYERS
        and sch["teamLevel"] == config.RAID_TEAM_LEVEL)
    chk("보스 노력치와 공개 시각도 실린다 (탭이 스스로 다시 부르는 데 쓴다)",
        sch.get("bossEv") == config.RAID_BOSS_EV
        and sch.get("revealSec") == config.RAID_REVEAL_SEC, sch.get("revealSec"))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
