# -*- coding: utf-8 -*-
"""악당 출현 (시즌 4) — 날짜로 정해지는 출현, 간부 셋, 전설, 알.

    python server/test_boss.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. 언제·어디에·누가 나오는지는 **날짜로 정해진다.** 한국 시각 09:00~12:00 사이에 나타나고,
     그 전에는 아무것도 알려 주지 않는다. 밤 11시까지 머문다. 시즌 시작일부터 2주 동안만 나온다.
  2. 간부의 팀: 마릿수 = 내 파티 수, 레벨 = 내 파티 레벨(높은 순), 개체값 전부 31.
     기술·특성·도구·노력치는 관장 자료 그대로. 전설·환상은 뺀다.
  3. 간부 셋을 차례로 이겨야 전설전이 열린다. 지면 그 간부부터 다시.
  4. 전설: 한 마리, 내 파티의 가장 높은 레벨, 개체값 31. 쓰러뜨리면 70% 로 하루 한 번 그 전설의 알.
  5. 관장 기록(이긴 곳)에는 안 남는다. 상금은 관장 재도전 상금과 같은 식.
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

TMP = tempfile.mkdtemp(prefix="poket-boss-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import boss, boss_routes, config, db, deps, eggs, gym, gym_routes, items  # noqa: E402
from app import season                                         # noqa: E402
from common import pokelogic as P                             # noqa: E402
from common import trainer_battle as TB                       # noqa: E402

OK = FAIL = 0
KST = boss.KST


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


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


def at(day, hour, minute=0):
    y, m, d = (int(x) for x in day.split("-"))
    return datetime.datetime(y, m, d, hour, minute, tzinfo=KST).astimezone(datetime.timezone.utc)


def win_now(uid, region, trainer_id, level, seed):
    """판을 끝까지 두지 않고 '이겼다' 만 처리한다 (진행·상금·알을 보는 검사)."""
    return boss.on_win(uid, region, trainer_id, level, rng=random.Random(seed))


def main():
    # 아래 날짜는 시즌 4 (10/17 시작) 기준이다. 악당은 시즌 4 에만, 시작한 날부터 2주 나온다 (boss.in_event).
    print("=== 시즌 5 에는 안 나온다 (2026-10-31 사용자 결정) ===")
    chk("시즌 5 (11/1~) 에는 2주 안이어도 안 나온다", not boss.in_event("2026-11-01") and not boss.in_event("2026-11-10"),
        (season.SEASON, season.SEASON_STARTS))
    season.SEASON, season.SEASON_STARTS = 4, "2026-10-17"
    db.init()
    d = deps.dex()

    print("=== 자료 ===")
    teams = boss.table()["teams"]
    chk("조직 일곱 곳", len(teams) == 7, [t["name"] for t in teams])
    chk("조직마다 간부 셋을 채울 수 있다", all(len(t["pool"]) + (1 if t["boss"] else 0) >= 3 for t in teams))
    chk("간부는 전부 관장 자료에 있는 트레이너", all(gym.trainer(i) for t in teams
                                       for i in t["pool"] + ([t["boss"]] if t["boss"] else [])))
    chk("시·도 열여섯 곳", len(boss.sidos()) == 16 and boss.sidos()["11"] == "서울특별시", len(boss.sidos()))

    print("\n=== 날짜로 정해진다 ===")
    days = [(datetime.date(2026, 10, 17) + datetime.timedelta(days=i)).isoformat() for i in range(120)]
    plans = [boss.plan(x) for x in days]
    chk("같은 날은 언제 물어도 같다", boss.plan(days[0]) == plans[0])
    chk("나타나는 시각은 09:00 ~ 12:00 사이", all(0 <= p["minute"] < 3 * 60 for p in plans)
        and all(9 <= boss.appears_at(x).hour <= 11 for x in days),
        (min(p["minute"] for p in plans), max(p["minute"] for p in plans)))
    chk("그날 안에 나타난다", all(boss.appears_at(x).date().isoformat() == x for x in days))
    chk("조직이 골고루 나온다", len(set(p["team"]["id"] for p in plans)) == 7,
        sorted(set(p["team"]["id"] for p in plans)))
    chk("시·도가 골고루 나온다", len(set(p["sido"] for p in plans)) == 16, len(set(p["sido"] for p in plans)))
    chk("시각이 날마다 다르다", len(set(p["minute"] for p in plans)) > 60)
    chk("늘 셋이 선다", all(len(p["members"]) == 3 and len(set(p["members"])) == 3 for p in plans))
    chk("보스가 있는 조직은 보스가 마지막에 선다",
        all(p["members"][-1] == p["team"]["boss"] for p in plans if p["team"]["boss"]))

    print("\n=== 전설은 사람마다 (2026-10-17 사용자 결정, 10/18 부터) ===")
    pool = eggs.pool("legendary")
    first = [boss.legend_of("2026-10-17", u) for u in range(1, 51)]
    chk("10/17 은 예전처럼 모두 같다 (미라이돈)", set(first) == {"MIRAIDON"}
        and boss.team_legend("2026-10-17") == "MIRAIDON", set(first))
    chk("  사람마다는 10/18 부터", boss.PER_USER_FROM == "2026-10-18")
    days = [x for x in days if x >= boss.PER_USER_FROM]
    same_day = [boss.legend_of(days[0], u) for u in range(1, 201)]
    chk("같은 날이라도 사람마다 다르다 (200명에 %d종)" % len(set(same_day)), len(set(same_day)) >= 40,
        len(set(same_day)))
    chk("  같은 날 같은 사람은 언제 물어도 같다", all(boss.legend_of(days[0], u) == same_day[u - 1]
                                          for u in range(1, 201)))
    days = [(datetime.date(2026, 10, 17) + datetime.timedelta(days=i)).isoformat() for i in range(120)]
    one_user = [boss.legend_of(x, 7) for x in days]
    chk("  한 사람도 날마다 다시 뽑는다", len(set(one_user)) >= 30, len(set(one_user)))
    chk("  전부 전설의 알에서 나올 수 있는 종 (도감의 전설, 환상·울트라비스트·패러독스·이벤트 빼고)",
        set(same_day + one_user) <= set(pool) and "MEW" not in pool and config.EVENT_SPECIES not in pool,
        sorted(set(same_day + one_user) - set(pool)))
    chk("  plan 에는 전설이 없다 (모두에게 같은 것은 조직·간부·곳·시각뿐)", "legend" not in plans[0])

    day = "2026-10-17"
    p = boss.plan(day)
    t0 = boss.appears_at(day)
    print("  (%s: %s, %s, %02d:%02d, %s)" % (day, p["team"]["name"], boss.sidos()[p["sido"]], t0.hour,
                                             t0.minute, p["members"]))
    before = t0 - datetime.timedelta(minutes=1)
    uid = mkuser("boss_a")
    LG = boss.legend_of(day, uid)                    # 이 사람이 오늘 만나는 전설
    # 안 나와 있으면 '오늘이 기간인가' 만 싣는다 (관장 탭이 09~12시에 다시 물어볼지 정한다, 게시판 #252).
    # 언제 나오는지는 여전히 안 알려 준다.
    chk("나타나기 1분 전에는 없다 (기간이라는 것만, 시각은 안 알린다)", boss.active(before) is None
        and boss.brief(uid, before) == {"active": False, "event": True}
        and boss.card(uid, before) == {"active": False}, boss.brief(uid, before))
    chk("그 시각부터 있다", (boss.active(t0) or {}).get("day") == day)
    chk("밤 11시 직전까지 머문다", (boss.active(at(day, 22, 59)) or {}).get("day") == day)
    chk("밤 11시가 되면 떠난다", boss.active(at(day, 23, 0)) is None
        and boss.brief(uid, at(day, 23, 0)) == {"active": False, "event": True}
        and boss.card(uid, at(day, 23, 0)) == {"active": False}, boss.brief(uid, at(day, 23, 0)))
    late = datetime.datetime(2026, 11, 20, 10, 0, tzinfo=boss.KST)
    chk("  기간이 끝나면 event False (관장 탭이 더 안 물어본다)",
        boss.brief(uid, late) == {"active": False, "event": False}, boss.brief(uid, late))
    chk("자정이 지나면 다음 날의 것 (아직 안 나타났다)", boss.active(at("2026-10-18", 0, 1)) is None)
    chk("남은 시간은 밤 11시까지", boss.ends_in(at(day, 22, 0)) == 3600 and boss.ends_in(at(day, 23, 30)) == 0,
        (boss.ends_in(at(day, 22, 0)), boss.ends_in(at(day, 23, 30))))

    print("\n=== 2주 동안만 ===")
    def seen(d):
        return (boss.active(boss.appears_at(d) + datetime.timedelta(minutes=1)) or {}).get("day") == d
    chk("시즌 시작 전날에는 안 나온다", not seen("2026-10-16"))
    chk("시즌 첫날(10/17)부터 나온다", seen("2026-10-17"))
    chk("14일째(10/30)까지 나온다", seen("2026-10-30") and all(
        seen((datetime.date(2026, 10, 17) + datetime.timedelta(days=i)).isoformat()) for i in range(14)))
    chk("15일째(10/31)부터는 안 나온다", not seen("2026-10-31") and not seen("2026-11-05"))
    br = boss.brief(uid, t0)
    chk("개요: 검게 칠할 시·도와 조직 이름, 내 진행",
        br["active"] and br["sido"] == p["sido"] and br["sidoName"] == boss.sidos()[p["sido"]]
        and br["team"] == p["team"]["name"] and br["stage"] == 0 and not br["done"], br)

    print("\n=== 간부의 팀 ===")
    levels = [72, 100, 55]
    # 같은 종은 한 팀에 한 마리만 나간다 (10/22) - 세 마리가 다 나가게 종을 달리한다
    for i, (sp, lv) in enumerate(zip(("SALAMENCE", "GARCHOMP", "DRAGONITE"), levels)):
        mkmon(uid, sp, lv, i)
    party = gym_routes._party(uid)
    tr = boss.admin_trainer(p["members"][0], party)
    src = gym.trainer(p["members"][0])
    chk("마릿수는 내 파티 수", len(tr["team"]) == 3, len(tr["team"]))
    chk("레벨은 내 파티 레벨, 높은 순", [m["level"] for m in tr["team"]] == [100, 72, 55],
        [m["level"] for m in tr["team"]])
    chk("개체값은 전부 31", all(m["iv"] == 31 for m in tr["team"]))
    chk("종·기술·특성·도구·노력치는 관장 자료 그대로",
        all(all(m[k] == s[k] for k in ("species", "moves", "ability", "held", "evs", "nature"))
            for m, s in zip(tr["team"], src["team"])))
    chk("이름·역할·도트도 그대로", (tr["name"], tr["role"], tr["sprite"]) == (src["name"], src["role"], src["sprite"]))
    f = TB.trainer_mon(tr["team"][0])
    chk("엔진이 먹는 꼴: 개체값 31", all(v == 31 for v in f["ivs"].values()) and f["level"] == 100)
    gio = boss.admin_trainer("giovanni", [{"level": 80}] * 6)
    chk("전설은 뺀다 (비주기의 뮤츠)", "MEWTWO" not in [m["species"] for m in gio["team"]]
        and len(gio["team"]) == 5, [m["species"] for m in gio["team"]])
    one = boss.admin_trainer(p["members"][0], party[:1])
    chk("한 마리만 데리고 가면 상대도 한 마리", len(one["team"]) == 1 and one["team"][0]["level"] == party[0]["level"])

    print("\n=== 전설 ===")
    lg = boss.legend_trainer(LG, party)
    chk("한 마리, 내 파티의 가장 높은 레벨, 개체값 31",
        len(lg["team"]) == 1 and lg["team"][0]["level"] == 100 and lg["team"][0]["iv"] == 31
        and lg["team"][0]["species"] == LG, lg["team"])
    chk("그 레벨에서 아는 기술 넷", len(lg["team"][0]["moves"]) == 4, lg["team"][0]["moves"])
    chk("트레이너가 아니라 마주친 포켓몬이다", lg["wild"] and lg["role"] == "전설의 포켓몬"
        and lg["name"] == d.get(LG)["kr"])
    tb = TB.TrainerBattle(d, party, lg, random.Random(3))
    ev = tb.start()
    chk("문구: 승부를 걸어오지 않고 모습을 드러낸다", "모습을 드러냈다" in ev[0]["text"]
        and "앞을 막아섰다" in ev[1]["text"], [e.get("text") for e in ev[:2]])
    chk("볼을 던지는 길이 없다 (이 판은 관장 배틀이다)", not hasattr(tb, "throw") and "catch" not in tb.view())

    print("\n=== 메가스톤을 받지 않는다 (높은 레벨에서) ===")
    hundred = [{"level": 100}] * 6
    lm = boss.legend_trainer("MEWTWO", hundred)
    tbm = TB.TrainerBattle(d, party, lm, random.Random(3))
    chk("Lv.100 뮤츠가 메가스톤을 쥐지 않는다", tbm.foe_team[0].held is None and not tbm.keystone["foe"]
        and tbm.bt.can_mega("foe") is None, (tbm.foe_team[0].held, tbm.keystone))
    gv = boss.admin_trainer("giovanni", hundred)
    src_held = [m["held"] for m in gym.trainer("giovanni")["team"]
                if not (d.get(m["species"]) or {}).get("legendary")]
    tbg = TB.TrainerBattle(d, party, gv, random.Random(3))
    chk("Lv.100 간부의 도구도 자료 그대로다", [f.mon.get("held") for f in tbg.foe_team] == src_held
        and not tbg.keystone["foe"], [f.mon.get("held") for f in tbg.foe_team])
    plain_gym = TB.TrainerBattle(d, party, dict(gym.trainer("giovanni"), level=100), random.Random(3))
    chk("(보통 관장은 예전처럼 높은 레벨에서 메가스톤을 받는다)", plain_gym.keystone["foe"] is True)

    print("\n=== 길: 시작 ===")
    real_now = boss._now
    boss._now = lambda: before
    chk("나타나기 전에는 시작할 수 없다", status_of(lambda: boss_routes.start(ctx=me(uid))) == 404)
    boss._now = lambda: t0 + datetime.timedelta(minutes=5)
    empty = mkuser("boss_empty")
    chk("포켓몬이 없으면 못 한다", status_of(lambda: boss_routes.start(ctx=me(empty))) == 409)
    out = boss_routes.start(ctx=me(uid))
    chk("첫 간부와 판이 열린다", out["region"] == "boss:%s:0" % day
        and out["battle"]["trainer"]["name"] == gym.trainer(p["members"][0])["name"], out["region"])
    foe = json.loads(db.q1("SELECT data FROM gym_battle WHERE id=?", (out["id"],))["data"])["foe"]
    chk("  상대는 세 마리, 레벨 100·72·55", [x["mon"]["level"] for x in foe] == [100, 72, 55],
        [x["mon"]["level"] for x in foe])
    again = boss_routes.start(ctx=me(uid))
    chk("하던 판이 있으면 이어서 준다", again["id"] == out["id"] and again.get("resumed"))
    card = boss.card(uid)
    chk("악당 창: 하던 판이 실린다", card["battle"] == {"id": out["id"]} and card["stage"] == 0)
    chk("악당 창: 첫째는 다음, 나머지는 잠김", [m["state"] for m in card["members"]] == ["next", "locked", "locked"])
    chk("악당 창: 전설은 아직 누구인지 안 보인다", card["legend"] == {"open": False, "done": False, "egg": None},
        card["legend"])
    chk("관장에게 도전하려 하면 악당과의 승부부터 끝내라고 한다",
        status_of(lambda: gym_routes.start(next(iter(gym.gyms()["regions"])), ctx=me(uid))) == 409)

    print("\n=== 길: 지면 그대로, 이기면 다음 ===")
    r = gym_routes.act(out["id"], gym_routes.ActIn(kind="forfeit"), ctx=me(uid))
    chk("기권하면 진행은 그대로", r["battle"]["result"] == "forfeit" and boss.run(uid, day)["stage"] == 0)
    out = boss_routes.start(ctx=me(uid))
    chk("다시 같은 간부부터", out["region"] == "boss:%s:0" % day)
    # 끝까지 싸워 이긴다 (Lv.100 한카리아스가 지진으로 민다 - 못 이기면 판을 접고 이긴 것으로 친다)
    won = None
    for _ in range(200):
        row = db.q1("SELECT * FROM gym_battle WHERE id=?", (out["id"],))
        tbx = TB.TrainerBattle.load(d, json.loads(row["data"]))
        if tbx.over:
            break
        if tbx.need_switch:
            r = gym_routes.act(out["id"], gym_routes.ActIn(kind="switch", slot=tbx.valid_switches()[0]),
                               ctx=me(uid))
        else:
            r = gym_routes.act(out["id"], gym_routes.ActIn(kind="move", move="EARTHQUAKE"), ctx=me(uid))
        if r["battle"]["over"]:
            won = r
            break
    if won and won["battle"]["result"] == "won":
        rw = won["reward"]
        chk("실제로 이기면 진행이 오른다", boss.run(uid, day)["stage"] == 1 and rw.get("boss") and rw["stage"] == 1, rw)
        chk("  상금은 레벨 x 관장 재도전 상금", rw["prize"] == 100 * config.GYM_REPEAT_PER_LEVEL
            and items.money(uid) == rw["prize"], rw)
        chk("  화면에 띄울 줄이 온다", any("남았다" in s for s in rw["lines"]), rw["lines"])
        chk("  관장 기록에는 안 남는다", gym.clears(uid) == {}, list(gym.clears(uid)))
    else:
        db.run("UPDATE gym_battle SET state='done', result='lost' WHERE id=?", (out["id"],))
        rw = win_now(uid, out["region"], p["members"][0], 100, 1)
        chk("(판은 졌다 - 이긴 처리만 따로 본다) 진행이 오른다", boss.run(uid, day)["stage"] == 1, rw)
    chk("같은 자리를 두 번 이겨도 한 번만 센다",
        win_now(uid, "boss:%s:0" % day, p["members"][0], 100, 1)["lines"] == ["이미 이긴 상대다."]
        and boss.run(uid, day)["stage"] == 1)
    money1 = items.money(uid)

    print("\n=== 간부 셋 -> 전설 ===")
    chk("간부를 다 이기기 전에는 전설전이 안 열린다",
        boss.next_fight(uid, party)[0] == "boss:%s:1" % day)
    chk("건너뛰어 전설을 이겼다고 해도 안 받는다",
        win_now(uid, "boss:%s:3" % day, "legend:" + LG, 100, 1)["lines"] == ["이미 끝난 승부다."]
        and not boss.run(uid, day)["legend"])
    for i in (1, 2):
        region, tid, _t = boss.next_fight(uid, party)
        chk("%d번째 상대는 %s" % (i + 1, gym.trainer(p["members"][i])["name"]),
            (region, tid) == ("boss:%s:%d" % (day, i), p["members"][i]), (region, tid))
        rw = win_now(uid, region, tid, 100, 1)
    chk("셋째를 이기면 전설이 나온다고 알린다", any("전설의 포켓몬" in s for s in rw["lines"]), rw["lines"])
    chk("상금은 간부마다", items.money(uid) == money1 + 2 * 100 * config.GYM_REPEAT_PER_LEVEL)
    card = boss.card(uid)
    chk("악당 창: 셋 다 이김", [m["state"] for m in card["members"]] == ["won", "won", "won"])
    chk("악당 창: 전설이 누구인지 보인다", card["legend"]["open"] and card["legend"]["species"] == LG
        and card["legend"]["name"] == d.get(LG)["kr"] and not card["legend"]["done"], card["legend"])
    region, tid, t = boss.next_fight(uid, party)
    chk("다음 상대는 전설", region == "boss:%s:3" % day and tid == "legend:" + LG and t["wild"])
    out = boss_routes.start(ctx=me(uid))
    chk("길로 열어도 전설전", out["region"] == region and out["battle"]["trainer"].get("wild")
        and len(out["battle"]["foe"]["team"]) == 1, out["region"])
    gym_routes.act(out["id"], gym_routes.ActIn(kind="forfeit"), ctx=me(uid))
    chk("져도(기권) 다시 도전할 수 있다", boss.next_fight(uid, party)[0] == region and not boss.run(uid, day)["legend"])

    print("\n=== 알: 70% ===")
    n = 0
    trials = 2000
    for seed in range(trials):
        n += random.Random(seed).random() < boss.EGG_RATE
    chk("확률은 70%% (2000번 굴려 %d번)" % n, boss.EGG_RATE == 0.70 and 0.66 < n / float(trials) < 0.74, n)
    lucky = next(s for s in range(100) if random.Random(s).random() < boss.EGG_RATE)
    unlucky = next(s for s in range(100) if random.Random(s).random() >= boss.EGG_RATE)
    eggs0 = db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (uid,))["c"]
    rw = win_now(uid, region, tid, 100, lucky)
    egg = db.q1("SELECT * FROM egg WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,))
    chk("나오면 그 전설의 알이 들어온다", rw["egg"] is True and egg is not None and egg["species"] == LG
        and egg["kind"] == "legendary" and egg["known"] == 1
        and db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (uid,))["c"] == eggs0 + 1, dict(egg) if egg else rw)
    chk("  알을 얻었다고 알린다", any("알을 얻었다" in s for s in rw["lines"]), rw["lines"])
    run = boss.run(uid, day)
    chk("오늘은 끝났다고 적힌다", run["legend"] and run["egg"] == 1 and boss.brief(uid)["done"])
    chk("한 번 더 이겼다고 해도 알은 하루 한 번", win_now(uid, region, tid, 100, lucky)["lines"] == ["이미 끝난 승부다."]
        and db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (uid,))["c"] == eggs0 + 1)
    chk("끝낸 뒤에는 시작할 수 없다", status_of(lambda: boss_routes.start(ctx=me(uid))) == 409)
    card = boss.card(uid)
    chk("악당 창: 끝, 알을 얻음", card["done"] and card["legend"]["done"] and card["legend"]["egg"] == 1)

    other = mkuser("boss_b")
    mkmon(other, "GARCHOMP", 60, 0)
    chk("진행은 사람마다 따로다", boss.run(other, day)["stage"] == 0 and not boss.brief(other)["done"])
    op = gym_routes._party(other)
    for i in range(3):
        region, tid, _t = boss.next_fight(other, op)
        win_now(other, region, tid, 60, 1)
    region, tid, _t = boss.next_fight(other, op)
    rw = win_now(other, region, tid, 60, unlucky)
    chk("안 나오면 알이 없다", rw["egg"] is False
        and db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (other,))["c"] == 0, rw)
    chk("  그래도 오늘은 끝이다", boss.run(other, day)["legend"] and boss.run(other, day)["egg"] == 0
        and any("내일" in s for s in rw["lines"]))

    print("\n=== 같은 순간에 두 번 이겨도 ===")
    import threading
    racer = mkuser("boss_race")
    mkmon(racer, "GARCHOMP", 70, 0)
    rp_ = gym_routes._party(racer)
    out_rows = []

    def hit(region_, tid_, seed_):
        out_rows.append(boss.on_win(racer, region_, tid_, 70, rng=random.Random(seed_)))

    region_, tid_, _t = boss.next_fight(racer, rp_)
    ts = [threading.Thread(target=hit, args=(region_, tid_, lucky)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    chk("간부 한 명을 여덟 번 동시에 이겨도 진행은 한 칸, 상금은 한 번",
        boss.run(racer, day)["stage"] == 1 and items.money(racer) == 70 * config.GYM_REPEAT_PER_LEVEL
        and sum(1 for r in out_rows if r.get("prize")) == 1,
        (boss.run(racer, day), items.money(racer)))
    for _ in range(2):
        region_, tid_, _t = boss.next_fight(racer, rp_)
        boss.on_win(racer, region_, tid_, 70, rng=random.Random(lucky))
    region_, tid_, _t = boss.next_fight(racer, rp_)
    out_rows[:] = []
    ts = [threading.Thread(target=hit, args=(region_, tid_, lucky)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    chk("전설을 여덟 번 동시에 쓰러뜨려도 알은 하나",
        db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (racer,))["c"] == 1
        and sum(1 for r in out_rows if r.get("egg")) == 1 and boss.run(racer, day)["egg"] == 1,
        (db.q1("SELECT COUNT(*) c FROM egg WHERE user_id=?", (racer,))["c"], [r.get("egg") for r in out_rows]))

    print("\n=== 다음 날 ===")
    day2 = "2026-10-18"
    boss._now = lambda: boss.appears_at(day2) + datetime.timedelta(minutes=1)
    chk("다음 날에는 처음부터", boss.run(uid, day2)["stage"] == 0 and not boss.brief(uid)["done"]
        and boss.brief(uid)["day"] == day2)
    chk("어제 것은 그대로 남아 있다", boss.run(uid, day)["legend"])
    boss._now = real_now

    print("\n=== 관장 개요에 실린다 ===")
    boss._now = lambda: t0 + datetime.timedelta(minutes=5)
    ov = gym_routes.overview(ctx=me(other))
    chk("나타나 있으면 시·도와 조직", ov["boss"]["active"] and ov["boss"]["sido"] == p["sido"], ov["boss"])
    boss._now = lambda: before
    ov = gym_routes.overview(ctx=me(other))
    chk("아직이면 active False 와 기간 여부뿐", ov["boss"] == {"active": False, "event": True}, ov["boss"])
    boss._now = real_now

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
