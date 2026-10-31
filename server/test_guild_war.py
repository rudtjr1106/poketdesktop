# -*- coding: utf-8 -*-
"""길드전 (시즌 4) — 원형 지도의 칸을 뺏는 전쟁.

    python server/test_guild_war.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. 일정: 시즌이 시작한 순간부터 신청 3일 -> 전쟁 4일 -> 끝. 시각으로 넘어간다.
  2. 신청·취소는 마스터와 부마스터, 길드원 5명 이상. 팀은 신청 기간에만 짜고 전쟁이 시작되면 고정.
  3. **지도**: 원형 - 길드마다 같은 부채꼴 15칸 (줄 5 x 칸 3). 모든 길드가 한 덩어리, 이웃 길드 2곳, 남과
     맞닿은 칸 10칸. 다시 계산해도 같다. 그림(부채꼴·길드 이름)은 지도 응답에 함께 (가진 것이면 안 싣는다).
  4. **지키는 사람**: 한 사람이 한 칸씩 (15명 길드는 15칸 전부 사람), 남는 칸은 AI 수비대 (Lv.50).
     길드장이 옮길 수 있다 - 공격받은 칸은 못 건드린다.
  5. **공격**: 길드 합 30번, 처음엔 인원수로 나눠 두고 길드장이 다시 나눈다 (한 사람 최소 1번).
     우리 칸과 맞닿은 남의 칸만. 관장식 판(gym_battle)이 열리고 공격권 하나를 쓴다.
     기권·시간 초과는 진 것. 같은 상대를 길드가 합쳐 3번 이기면 칸이 넘어오고, 넘어간 칸은 다시 못 뺏는다.
     길드 하나가 받는 공격은 30번까지.
  6. 남의 방어팀은 **앞 3마리만** 응답에 실린다 (우리 칸은 전부).
  7. 순위는 가진 칸 수. 끝나면 진행 중인 판은 진 것으로 접고, 순위대로 보상이 **한 번만** 나간다.
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

TMP = tempfile.mkdtemp(prefix="poket-gwar-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import config, db, deps, friendly, guild, guild_war as GW, gym_routes, items, pvp, season, watchers  # noqa: E402
from common import pokelogic as P                             # noqa: E402
from common import trainer_battle as TB                       # noqa: E402

OK = FAIL = 0
KST = GW.KST
T0 = GW.starts()


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def code_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code
    return None


def mkuser(name, species="GARCHOMP", level=60, mons=2):
    uid = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid
    d = deps.dex()
    for i in range(mons):
        m = P.make_pokemon(d.get(species), level, random.Random(uid * 10 + i), shiny_rate=10 ** 9)
        pid = db.insert_mon(uid, m, "2026-01-01")
        db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=? WHERE id=?", (i, level, pid))
    return uid


def mkguild(name, n, species="GARCHOMP", level=60):
    """n 명짜리 길드. 첫 사람이 마스터, 둘째가 부마스터. (길드 번호, 사람들)"""
    ids = [mkuser("%s_%02d" % (name, i), species, level) for i in range(n)]
    gid = db.run("INSERT INTO guild (name, intro, join_mode, master_id, created_at) VALUES (?,?,?,?,?)",
                 (name, "", "open", ids[0], "2026-10-01T00:00:00+00:00")).lastrowid
    for i, uid in enumerate(ids):
        role = "master" if i == 0 else ("sub" if i == 1 else "member")
        db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
               (uid, gid, role, "2026-10-01T00:%02d:00+00:00" % i))
    return gid, ids


def at(days=0, hours=0, minutes=0):
    return (T0 + datetime.timedelta(days=days, hours=hours, minutes=minutes)).astimezone(datetime.timezone.utc)


def clock(t):
    # 관장 배틀 쪽 시계도 같이. 공격 판은 gym_battle 에 있고 gym_routes 가 '1시간 손 놓은 판' 을 자기
    # 시계로 접는다 - 길드전 시계만 옮기면, 진짜 날짜가 검사 속 전쟁 기간(T0 + 7일~)을 지난 뒤로는
    # 막 연 판이 곧바로 접혔다 (10/29 CI, 날짜 폭탄).
    GW._now = lambda: t
    gym_routes._now = lambda: t


def mon_ids(uid):
    return [r["id"] for r in db.q("SELECT id FROM pokemon WHERE user_id=? ORDER BY slot", (uid,))]


def give(uid, species, level, slot=None, seed=0):
    """포켓몬 한 마리를 준다. slot 을 주면 바탕화면 파티의 그 자리에."""
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(seed or uid), shiny_rate=10 ** 9)
    pid = db.insert_mon(uid, m, "2026-01-01")
    if slot is not None:
        db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=? WHERE id=?", (slot, level, pid))
    return pid


def wipe():
    for t in ("guild_war_attack", "guild_war_tile", "guild_war_team", "guild_war_entry"):
        db.run("DELETE FROM %s" % t)
    db.run("DELETE FROM gym_battle")
    db.run("DELETE FROM meta WHERE k LIKE 'gw:%'")


def lands(gid):
    return [r["region"] for r in db.q("SELECT region FROM guild_war_tile WHERE season=? AND guild_id=?"
                                      " ORDER BY region", (season.SEASON, gid))]


def guard_of(uid):
    r = db.q1("SELECT region FROM guild_war_tile WHERE season=? AND guard_user=? AND taken_at IS NULL",
              (season.SEASON, uid))
    return r["region"] if r else None


def me(uid):
    return {"user": {"id": uid}}


def fight(uid, region, win=True):
    """그 칸에 승부를 걸고 끝까지 둔다. win 이면 가장 아픈 기술로 싸우고, 아니면 바로 기권한다."""
    r = GW.attack(uid, region)
    bid = r["id"]
    if not win:
        return gym_routes.act(bid, gym_routes.ActIn(kind="forfeit"), ctx=me(uid))
    out = None
    for _ in range(80):
        row = db.q1("SELECT * FROM gym_battle WHERE id=?", (bid,))
        if row["state"] != "active":
            break
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(row["data"]))
        if tb.need_switch:
            out = gym_routes.act(bid, gym_routes.ActIn(kind="switch", slot=tb.valid_switches()[0]), ctx=me(uid))
        else:
            _d, k = tb._best(tb.me, tb.foe)
            out = gym_routes.act(bid, gym_routes.ActIn(kind="move", move=k or tb.bt.usable(tb.me)[0]),
                                 ctx=me(uid))
    return out


def main():
    db.init()

    print("=== 일정 ===")
    # 시즌마다 시작한 날부터 센다 (시즌 4 는 10/17, 시즌 5 는 11/1).
    chk("시즌이 시작하는 날 0시(한국)부터", T0.astimezone(KST).isoformat() == GW.season.SEASON_STARTS + "T00:00:00+09:00",
        T0.isoformat())
    day = datetime.timedelta(days=1)
    chk("신청 3일, 전략 4일, 전쟁 6일, 결산 1일 (시즌 2주)",
        (GW.APPLY_DAYS, GW.PLAN_DAYS, GW.WAR_DAYS, GW.SETTLE_DAYS) == (3, 4, 6, 1)
        and GW.APPLY_DAYS + GW.PLAN_DAYS + GW.WAR_DAYS + GW.SETTLE_DAYS == 14
        and GW.plan_at() - T0 == 3 * day and GW.war_at() - T0 == 7 * day and GW.ends_at() - T0 == 13 * day)
    chk("시작 전", GW.phase(at(minutes=-1))[0] == "before")
    chk("시작한 순간부터 신청", GW.phase(at())[0] == "apply" and GW.phase(at(days=2, hours=23, minutes=59))[0] == "apply")
    chk("사흘 뒤부터 전략", GW.phase(at(days=3))[0] == "plan" and GW.phase(at(days=6, hours=23, minutes=59))[0] == "plan")
    chk("이레 뒤부터 전쟁", GW.phase(at(days=7))[0] == "war" and GW.phase(at(days=12, hours=23, minutes=59))[0] == "war")
    chk("열사흘 뒤에 끝 (결산)", GW.phase(at(days=13))[0] == "done" and GW.phase(at(days=13))[1] is None)
    chk("규칙의 수: 공격 30번, 길드당 15칸, 3승, 미리보기 3마리",
        (GW.TOTAL_ATTACKS, GW.TILES_PER_GUILD, GW.WINS_TO_TAKE, GW.SHOWN) == (30, 15, 3, 3))

    print("\n=== 처음 나누는 공격 횟수 (길드장이 나중에 바꾼다) ===")
    for n, want in ((15, [2] * 15), (8, [4] * 6 + [3] * 2), (5, [6] * 5)):
        chk("%d명: 합 30" % n, GW.quota(n) == want and sum(GW.quota(n)) == GW.TOTAL_ATTACKS, GW.quota(n))

    print("\n=== 지도: 원형 - 길드마다 같은 부채꼴 15칸 (10/16 결정: 한반도는 자리마다 이웃이 1~7곳으로 갈렸다) ===")
    for g in (1, 2, 3, 5, 8, 13, 17, 30):
        cells, owner, per = GW.layout(list(range(100, 100 + g)))
        cadj = GW._cell_adj(cells)
        spots = set((c[0], c[1]) for c in cells)
        same, nbs, fronts = True, set(), set()
        for x in set(owner):
            mine = set(i for i, o in enumerate(owner) if o == x)
            seen, st_ = set(), [min(mine)]
            while st_:
                i = st_.pop()
                if i not in seen:
                    seen.add(i)
                    st_.extend(j for j in cadj[i] if j in mine)
            same = same and seen == mine
            nbs.add(len(set(owner[j] for i in mine for j in cadj[i] if owner[j] != x)))
            fronts.add(sum(1 for i in mine if any(owner[j] != x for j in cadj[i])))
        want_nb = 0 if g == 1 else (1 if g == 2 else 2)
        chk("%d길드: 길드마다 15칸, 칸 자리가 겹치지 않는다" % g,
            per == 15 and sorted(owner.count(x) for x in set(owner)) == [15] * g and len(spots) == 15 * g,
            (per, len(spots)))
        chk("  모든 길드가 같다: 한 덩어리 · 이웃 길드 %d곳 · 남과 맞닿은 칸 %d칸" % (want_nb, 0 if g == 1 else 10),
            same and nbs == {want_nb} and fronts == {0 if g == 1 else 10}, (same, nbs, fronts))
    cells, owner, _per = GW.layout([7, 3, 5, 9])
    cadj = GW._cell_adj(cells)
    near = dict((g_, set(owner[j] for i, o in enumerate(owner) if o == g_ for j in cadj[i] if owner[j] != g_))
                for g_ in (7, 3, 5, 9))
    chk("이웃은 차례의 앞뒤 (끝과 처음도) - 7·3·5·9", near == {7: {9, 3}, 3: {7, 5}, 5: {3, 9}, 9: {5, 7}}, near)
    chk("  같은 차례면 늘 같은 지도", GW.layout([7, 3, 5, 9]) == GW.layout([7, 3, 5, 9]))
    chk("길드가 많아도 15칸 (18길드)", GW.layout(list(range(18)))[2] == 15)
    print("\n=== 이웃 배치: 신청이 끝나고 4일째에 무작위로 (적어 두고 그대로) ===")
    real_rand = GW._RAND
    try:
        orders = set()
        for k in range(12):
            GW._RAND = random.Random(k)
            db.run("DELETE FROM meta WHERE k='gw:99:order'")
            orders.add(tuple(GW.placement(99, [1, 2, 3, 4, 5, 6])))
        chk("뽑을 때마다 배치가 달라진다 (무작위)", len(orders) >= 8 and all(sorted(o) == [1, 2, 3, 4, 5, 6] for o in orders),
            len(orders))
        GW._RAND = random.Random(123)
        first = GW.placement(99, [1, 2, 3, 4, 5, 6])
        GW._RAND = random.Random(456)
        chk("  한 번 적어 두면 다시 불러도 같다 (나누다 끊겨도 같은 배치)", GW.placement(99, [6, 5, 4, 3, 2, 1]) == first,
            first)
    finally:
        GW._RAND = real_rand
        db.run("DELETE FROM meta WHERE k='gw:99:order'")
    cells, owner, per = GW.layout([1, 2, 3, 4])
    fake = [{"region": GW.cell_id(i), "codes": json.dumps(c), "home_guild": owner[i]} for i, c in enumerate(cells)]
    geo = GW.ring_geo(fake, {1: "가", 2: "나", 3: "다", 4: "라"})
    shapes = dict((x["code"], x["rings"][0]) for x in geo["sgg"])
    cadj = GW._cell_adj(cells)
    shared = all(len(set(map(tuple, shapes[GW.cell_id(i)])) & set(map(tuple, shapes[GW.cell_id(j)]))) >= 2
                 for i in cadj for j in cadj[i])
    chk("지도 그림: 칸마다 부채꼴 하나, 맞닿은 칸은 경계의 점이 똑같다 (화면이 경계선을 고른다)",
        len(shapes) == 60 and shared and all(len(r) >= 6 for r in shapes.values()), len(shapes))
    chk("  부채꼴 바깥에 길드 이름, 판 크기(이름까지 들어가게)", sorted(lb["text"] for lb in geo["labels"])
        == ["가", "나", "다", "라"] and geo["box"][1] > 1000 and all(
            abs(lb["x"]) <= geo["box"][1] and abs(lb["y"]) <= geo["box"][3] for lb in geo["labels"]), geo["box"])

    print("\n=== 신청 ===")
    ga, a = mkguild("가길드", 15)
    gb, b = mkguild("나길드", 8, species="DRAGONITE")
    gc, c = mkguild("다길드", 5, species="TYRANITAR")
    gs, sm = mkguild("작은길드", 4)
    solo = mkuser("길드없음")
    clock(at(minutes=-5))
    chk("시작 전에는 신청할 수 없다", code_of(lambda: GW.apply(a[0])) == 409)
    clock(at(hours=1))
    chk("일반 길드원은 신청할 수 없다", code_of(lambda: GW.apply(a[5])) == 403)
    chk("길드가 없으면 못 한다", code_of(lambda: GW.apply(solo)) == 400)
    chk("5명이 안 되면 못 한다", code_of(lambda: GW.apply(sm[0])) == 409)
    chk("마스터가 신청한다", GW.apply(a[0]) is True and GW.entry(ga)["name"] == "가길드")
    chk("부마스터도 신청할 수 있다", GW.apply(b[1]) is True)
    GW.apply(c[0])
    chk("취소했다 다시 넣을 수 있다", GW.withdraw(c[1]) is True and GW.entry(gc) is None
        and GW.apply(c[0]) is True)
    st = GW.state(a[5])
    chk("화면: 신청 단계, 규칙의 수", st["phase"] == "apply" and st["entered"] and len(st["entries"]) == 3
        and st["total"] == 30 and st["tilesPer"] == 15 and st["need"] == 3 and st["shown"] == 3
        and st["can"] == {"apply": False, "team": True, "attack": False, "manage": False}, st["can"])

    print("\n=== 팀 짜기 ===")
    u = a[2]
    ids = mon_ids(u)
    extra = [give(u, sp, 80, seed=900 + i) for i, sp in enumerate(("TYRANITAR", "METAGROSS", "SALAMENCE",
                                                                    "SNORLAX", "LAPRAS"))]
    chk("일곱 마리는 안 된다", code_of(lambda: GW.set_team(u, "def", ids + extra)) == 400)
    pv = GW.set_team(u, "def", [extra[0], extra[1], ids[0]])
    chk("방어팀을 짠다 (레벨은 상한 50 으로 보인다)", [m["id"] for m in pv] == [extra[0], extra[1], ids[0]]
        and all(m["level"] == 50 for m in pv), pv)
    chk("남의 포켓몬은 안 된다", code_of(lambda: GW.set_team(u, "def", [mon_ids(a[3])[0]])) == 404)
    chk("같은 종 두 마리는 안 된다 (한카리아스 둘, 10/22)", code_of(lambda: GW.set_team(u, "atk", ids[:2])) == 409)
    # 판을 열 때 고정된 팀을 다시 다듬는다 - 규칙이 팀을 고정한 뒤에 생겼을 수 있다 (같은 종 · 유대)
    stone = give(u, "CHARIZARD", 80, seed=950)
    fixed = GW._mons(u, [ids[0], ids[1], stone])
    fixed[2]["held"] = "CHARIZARDITEX"
    ready = GW._ready(fixed)
    chk("  판을 열 때: 같은 종은 앞의 한 마리만", [m["id"] for m in ready] == [ids[0], stone], [m["id"] for m in ready])
    chk("  판을 열 때: 유대 안 마친 개체는 메가진화 못 한다 (bonded=False)", ready[1].get("bonded") is False, ready[1])
    db.run("INSERT INTO bond (pokemon_id, user_id, species, started_at, gym, kos, wild, done_at, stone, seen)"
           " VALUES (?,?,'CHARIZARD','2026-09-30',1,30,10,'2026-09-30','CHARIZARDITEX',1)", (stone, u))
    chk("  유대를 마쳤으면 bonded=True", GW._ready(fixed)[1].get("bonded") is True)
    chk("  AI 수비대 팀(id 없음)은 손대지 않는다", "bonded" not in GW._ready([{"species": "PIKACHU", "level": 50}])[0])
    db.run("DELETE FROM pokemon WHERE id=?", (stone,))
    db.run("DELETE FROM bond WHERE pokemon_id=?", (stone,))
    # 결과를 못 박을 사람들 (전쟁이 시작되기 전에 차려 둔다)
    #   weak   나길드. 잉어킹 Lv.1 한 마리뿐 - 이 사람이 지키는 칸은 반드시 뚫리고, 이 사람의 공격은 반드시 진다
    #   b[0]   나길드. 여섯 마리 - 미리보기에서 뒤의 셋이 가려지는지 본다
    weak = b[7]
    db.run("DELETE FROM pokemon WHERE user_id=?", (weak,))
    give(weak, "MAGIKARP", 1, slot=0)
    for i, sp in enumerate(("SNORLAX", "GENGAR", "LUCARIO", "GYARADOS")):
        give(b[0], sp, 60, slot=2 + i, seed=400 + i)
    # 같은 종은 한 팀에 한 마리만 나간다 (10/22) - 여섯 마리가 다 나가게 둘째 망나뇽을 보만다로
    db.run("UPDATE pokemon SET species='SALAMENCE' WHERE id=?", (mon_ids(b[0])[1],))

    print("\n=== 전략 기간이 시작되면 명단이 고정되고 지도가 나뉜다 ===")
    gd, dd = mkguild("라길드", 5)
    GW.apply(dd[0])
    db.run("DELETE FROM guild_member WHERE user_id IN (?,?)", (dd[3], dd[4]))
    chk("신청 기간에는 이웃 배치가 없다 (아무도 미리 모른다)", GW._meta("gw:%d:order" % season.SEASON) is None
        and GW.map_view(a[0])["cells"] == {})
    clock(at(days=3, minutes=1))
    st = GW.state(u)
    chk("시각이 되면 전략 단계, 짜 둔 팀이 그대로 실린다 (아직 고칠 수 있다)", st["phase"] == "plan"
        and not st["teams"]["def"]["fixed"] and st["can"]["team"]
        and [m["id"] for m in st["teams"]["def"]["mons"]] == [extra[0], extra[1], ids[0]], st["phase"])
    chk("사람이 빠져 5명이 안 된 길드는 못 나간다", GW.entry(gd)["locked"] == -1 and GW.fighters(gd) == [])
    counts = dict((g, sorted((r["attacks"] for r in GW.fighters(g)), reverse=True)) for g in (ga, gb, gc))
    chk("공격은 처음에 인원수로 나눠 둔다 (합 30)", counts[ga] == [2] * 15 and counts[gb] == [4] * 6 + [3] * 2
        and counts[gc] == [6] * 5, counts)
    S = season.SEASON
    rows = GW.tiles()
    chk("칸 45개, 길드마다 15칸", len(rows) == 45 and GW.tile_counts() == {ga: 15, gb: 15, gc: 15}, GW.tile_counts())
    gname = dict((g_, GW.entry(g_)["name"]) for g_ in (ga, gb, gc))
    chk("칸 이름은 '처음 주인 길드 n번' (1~15), 칸 자리는 겹치지 않는다",
        all(sorted(int(r["name"].rsplit(" ", 1)[1][:-1]) for r in rows if r["guild_id"] == g_) == list(range(1, 16))
            and all(r["name"].startswith(gname[g_] + " ") for r in rows if r["guild_id"] == g_) for g_ in (ga, gb, gc))
        and len(set(tuple(json.loads(r["codes"])[:2]) for r in rows)) == 45, rows[0]["name"])
    for g, people, kr, n_ai in ((ga, a, "15명", 0), (gb, b, "8명", 7), (gc, c, "5명", 10)):
        mine = [r for r in rows if r["guild_id"] == g]
        humans = [r["guard_user"] for r in mine if r["guard_user"] != GW.AI_GUARD]
        ai = [r for r in mine if r["guard_user"] == GW.AI_GUARD]
        chk("%s 길드: 한 사람이 한 칸씩, AI 수비대 %d칸" % (kr, n_ai),
            sorted(humans) == sorted(people) and len(ai) == n_ai
            and all(r["ai_team"] and r["ai_name"] for r in ai), (len(humans), len(ai)))
    team = json.loads(next(r for r in rows if r["guard_user"] == GW.AI_GUARD)["ai_team"])
    chk("AI 수비대 팀은 Lv.50, 개체값 31, 여섯 마리까지", team and all(m["level"] == 50 and set(m["ivs"].values()) == {31}
                                                       for m in team) and len(team) <= 6, team[:1])
    nb = GW.neighbors()
    frontier = dict((r["region"], sum(1 for x in nb[r["region"]] if GW.tile(x)["guild_id"] != r["guild_id"]))
                    for r in rows)
    strong = max(b, key=lambda x: pvp.team_power(json.loads(GW._row(x)["def_team"])))
    chk("방어팀이 센 사람이 남과 많이 맞닿은 칸에 선다", frontier[guard_of(strong)]
        == max(frontier[r["region"]] for r in rows if r["guild_id"] == gb), (frontier[guard_of(strong)],))
    chk("다시 나눠도 줄이 늘지 않는다", GW._deal(S) == 0 and len(GW.tiles()) == 45)
    order = json.loads(GW._meta("gw:%d:order" % S) or "[]")
    ring = sorted(GW.tiles(), key=lambda r: json.loads(r["codes"])[1])
    seen_order = []
    for r in ring:
        if r["home_guild"] not in seen_order:
            seen_order.append(r["home_guild"])
    chk("4일째(전략 기간 시작)에 뽑은 이웃 배치가 적혀 있고, 지도가 그 차례다 (못 나간 길드는 빠진다)",
        sorted(order) == sorted([ga, gb, gc]) and seen_order == order, (order, seen_order))
    chk("길드 채팅에 지도 알림", "지도가 나뉘었습니다" in db.q1(
        "SELECT body FROM guild_chat WHERE guild_id=? AND body LIKE '지도가 나뉘었습니다%'", (gb,))["body"])

    print("\n=== 전략 기간 ===")
    chk("공격은 아직 못 한다", code_of(lambda: GW.attack(a[0], lands(gb)[0])) == 409 and GW._row(a[0])["used"] == 0)
    chk("  칠 수 있는 칸이 없다", GW.map_view(a[3])["hit"] == [] and not GW.state(a[0])["can"]["attack"])
    chk("  길드장은 정할 수 있다 (공격 횟수·지킬 칸)", GW.state(a[0])["can"]["manage"] and not GW.state(a[3])["can"]["manage"])
    pv = GW.set_team(u, "def", [extra[2], extra[3]])
    chk("팀을 고치면 고정된 방어팀도 바뀐다 (전쟁에 그대로 나간다)", [m["id"] for m in pv] == [extra[2], extra[3]]
        and [m["id"] for m in json.loads(GW._row(u)["def_team"])] == [extra[2], extra[3]], pv)
    GW.set_team(u, "def", [extra[0], extra[1], ids[0]])
    chk("  되돌리면 되돌아온다, 지키는 칸은 그대로", [m["id"] for m in json.loads(GW._row(u)["def_team"])]
        == [extra[0], extra[1], ids[0]] and guard_of(u) is not None)

    print("\n=== 지도와 칸 ===")
    mv = GW.map_view(a[3])
    chk("지도: 칸마다 주인, 길드마다 색·칸 수, 원형 지도 그림", len(mv["cells"]) == 45 and mv["myGuild"] == ga
        and sorted(g_["tiles"] for g_ in mv["guilds"]) == [15, 15, 15] and bool(mv["mapDigest"])
        and sorted(g_["color"] for g_ in mv["guilds"]) == [0, 1, 2]
        and all(x["codes"] == [k] and x["name"] for k, x in mv["cells"].items())
        and mv["geo"] and sorted(x["code"] for x in mv["geo"]["sgg"]) == sorted(mv["cells"])
        and len(mv["geo"]["labels"]) == 3)
    again = GW.map_view(a[3], have=mv["mapDigest"])
    chk("  이미 가진 그림이면 다시 안 싣는다 (30초마다 묻는다)", again["geo"] is None
        and again["mapDigest"] == mv["mapDigest"], again.get("mapDigest"))
    chk("  맞닿음이 실린다", mv["adj"] and all(set(v) <= set(mv["cells"]) for v in mv["adj"].values()))
    mine_a = set(lands(ga))
    chk("  (전략 기간이라 아직 칠 수 있는 칸이 없다)", mv["hit"] == [], mv["hit"])
    chk("  내가 지키는 칸, AI 칸 표시", [k for k, x in mv["cells"].items() if x.get("me")] == [guard_of(a[3])]
        and sum(1 for x in mv["cells"].values() if x.get("ai")) == 17)
    chk("  방어팀은 지도에 실리지 않는다", all("team" not in x for x in mv["cells"].values()))
    front = sorted(r for r in lands(gb) if set(nb[r]) & mine_a)
    far = sorted(r for r in lands(gb) if not set(nb[r]) & mine_a)
    chk("가길드와 맞닿은 나길드 칸이 있다 (이어지는 검사에 쓴다)", bool(front) and bool(far), (len(front), len(far)))
    rb = guard_of(b[0])
    tv = GW.tile_view(a[3], rb)
    chk("남의 칸: 주인·지키는 사람", tv["guild"] == "나길드" and tv["guard"] == "나길드_00" and tv["mine"] is False
        and tv["ai"] is False and tv["need"] == 3 and tv["wins"] == 0)
    chk("  방어팀은 앞 3마리만 온다 (여섯 마리 중 셋은 수만)", [m["kr"] for m in tv["team"]] == ["망나뇽", "보만다", "잠만보"]
        and tv["size"] == 6 and tv["hidden"] == 3, (tv["team"], tv["hidden"]))
    raw = json.dumps(tv, ensure_ascii=False)
    chk("  가려진 셋은 응답 어디에도 없다", not any(w in raw for w in ("GENGAR", "LUCARIO", "GYARADOS", "팬텀",
                                                         "루카리오", "갸라도스")))
    chk("  기술·도구·포켓몬 번호는 안 보인다", all("moves" not in m and "held" not in m and "id" not in m
                                        for m in tv["team"]))
    chk("  아직은 어느 칸이든 '전략 기간' 이라고", GW.tile_view(a[3], far[0])["blocked"].startswith("아직 전략 기간"))
    own = GW.tile_view(b[3], rb)
    chk("우리 칸은 전부 보이고, 노리는 길드가 적힌다", own["mine"] and len(own["team"]) == 6 and own["hidden"] == 0
        and own["threats"] == [] and own["blocked"] and own["manager"] is False)
    # 규칙(같은 종 한 마리, 10/22) 전에 고정된 팀: 보이는 것도 판에 나가는 것과 같아야 한다
    old_def = GW._row(b[0])["def_team"]
    dup = json.loads(old_def)
    dup.insert(1, dict(dup[0]))
    db.run("UPDATE guild_war_team SET def_team=? WHERE season=? AND user_id=?",
           (json.dumps(dup), season.SEASON, b[0]))
    tv2 = GW.tile_view(a[3], rb)
    chk("  고정된 팀에 같은 종이 있으면 보기에서도 앞의 한 마리만",
        [m["kr"] for m in tv2["team"]] == ["망나뇽", "보만다", "잠만보"] and tv2["size"] == 6, (tv2["team"], tv2["size"]))
    mine_view = GW.state(b[0])["teams"]["def"]["mons"]
    chk("  내 팀 보기도", [m["kr"] for m in mine_view][:2] == ["망나뇽", "보만다"] and len(mine_view) == 6,
        [m["kr"] for m in mine_view])
    db.run("UPDATE guild_war_team SET def_team=? WHERE season=? AND user_id=?", (old_def, season.SEASON, b[0]))
    ai_tile = next(r for r in lands(gb) if GW.tile(r)["guard_user"] == GW.AI_GUARD)
    av = GW.tile_view(a[3], ai_tile)
    chk("AI 수비대 칸", av["ai"] is True and av["guard"].startswith("AI 수비대") and len(av["team"]) <= 3)
    chk("없는 칸은 404", code_of(lambda: GW.tile_view(a[3], "c99x")) == 404)

    print("\n=== 길드장: 배치 ===")
    chk("일반 길드원은 못 옮긴다", code_of(lambda: GW.place(b[3], weak, front[0])) == 403)
    chk("다른 길드 칸에는 못 둔다", code_of(lambda: GW.place(b[0], weak, lands(ga)[0])) == 409)
    old_weak, old_front = guard_of(weak), GW.tile(front[0])["guard_user"]
    chk("잉어킹을 가길드와 맞닿은 칸으로 옮긴다 (자리를 맞바꾸거나 AI 칸과 바꾼다)", GW.place(b[0], weak, front[0]) is True
        and guard_of(weak) == front[0], guard_of(weak))
    if old_front != GW.AI_GUARD:
        chk("  원래 있던 사람은 잉어킹의 칸으로", guard_of(old_front) == old_weak)
    else:
        chk("  잉어킹의 원래 칸은 AI 수비대 칸이 된다", GW.tile(old_weak)["guard_user"] == GW.AI_GUARD
            and GW.tile(old_weak)["ai_team"])
    chk("  AI 수비대 수는 그대로", sum(1 for r in GW.tiles() if r["guild_id"] == gb and r["guard_user"] == GW.AI_GUARD) == 7)
    chk("  길드원은 여전히 한 사람 한 칸", sorted(r["guard_user"] for r in GW.tiles()
                                       if r["guild_id"] == gb and r["guard_user"]) == sorted(b))

    print("\n=== 길드장: 공격 나누기 ===")
    chk("일반 길드원은 못 나눈다", code_of(lambda: GW.set_attacks(a[3], {a[3]: 5})) == 403)
    chk("합이 30을 넘으면 안 된다", code_of(lambda: GW.set_attacks(a[0], {a[0]: 20})) == 409)
    chk("0번은 안 된다 (한 사람 최소 1번)", code_of(lambda: GW.set_attacks(a[0], {a[5]: 0})) == 409)
    plan = dict((x, 1) for x in a)
    plan[a[0]], plan[a[1]] = 9, 8
    chk("길드장이 몰아준다 (9 + 8 + 13명 x 1 = 30)", GW.set_attacks(a[0], plan) > 0
        and GW._row(a[0])["attacks"] == 9 and sum(r["attacks"] for r in GW.fighters(ga)) == 30)
    chk("  길드원이 아니면 안 된다", code_of(lambda: GW.set_attacks(a[0], {b[0]: 1})) == 404)

    print("\n=== 전쟁이 시작되면 ===")
    db.run("UPDATE pokemon SET nickname=? WHERE id=?", ("고정확인", extra[0]))   # 전략 기간에 키운 것 (팀은 안 바꿈)
    before_war = json.loads(GW._row(u)["def_team"])[0].get("nickname")
    clock(at(days=7, minutes=1))
    st = GW.state(a[0])
    chk("팀은 전쟁이 시작되는 순간의 모습으로 다시 고정된다 (한 번만)", before_war != "고정확인"
        and json.loads(GW._row(u)["def_team"])[0].get("nickname") == "고정확인" and bool(GW._meta("gw:%d:fixed" % S)),
        (before_war, json.loads(GW._row(u)["def_team"])[0].get("nickname")))
    chk("이레 뒤에 전쟁 단계, 공격할 수 있고 길드장도 더는 못 바꾼다", st["phase"] == "war" and st["can"]["attack"]
        and st["can"]["manage"] is False, (st["phase"], st["can"]))
    chk("  공격 횟수는 못 바꾼다", code_of(lambda: GW.set_attacks(a[0], plan)) == 409)
    chk("  지키는 칸도 못 바꾼다", code_of(lambda: GW.place(b[0], weak, front[-1])) == 409)
    chk("  팀도 못 바꾼다", code_of(lambda: GW.set_team(u, "def", [ids[0]])) == 409
        and GW.state(u)["teams"]["def"]["fixed"] and not GW.state(u)["can"]["team"])
    mv = GW.map_view(a[3])
    chk("  칠 수 있는 칸 = 우리 칸과 맞닿은 남의 칸", set(mv["hit"]) == set(
        r for r in mv["cells"] if r not in mine_a and set(mv["adj"][r]) & mine_a) and mv["hit"], mv["hit"])
    chk("  맞닿지 않은 칸은 칠 수 없다고", GW.tile_view(a[3], far[0])["blocked"] == "우리 칸과 맞닿지 않았다")
    chk("  우리 칸은 우리 칸이라고", GW.tile_view(b[3], rb)["blocked"] == "우리 길드의 칸이다")

    print("\n=== 공격 ===")
    chk("길드전에 안 나간 사람은 못 친다", code_of(lambda: GW.attack(solo, front[0])) == 403
        and code_of(lambda: GW.attack(sm[0], front[0])) == 403)
    chk("우리 칸은 못 친다", code_of(lambda: GW.attack(a[0], lands(ga)[0])) == 409)
    chk("맞닿지 않은 칸은 못 친다", code_of(lambda: GW.attack(a[0], far[0])) == 409)
    chk("없는 칸", code_of(lambda: GW.attack(a[0], "c99x")) == 404)
    chk("  막혔을 때 공격권은 안 닳는다", GW._row(a[0])["used"] == 0)
    r = GW.attack(a[0], front[0])
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (r["id"],))
    atk = db.q1("SELECT * FROM guild_war_attack WHERE battle_id=?", (r["id"],))
    chk("관장 배틀 판이 열린다 (관장 배틀 창이 그대로 쓰는 꼴)", r["battle"]["trainer"]["name"] == "나길드_07"
        and r["battle"]["trainer"]["role"] == "[나길드]" and row["state"] == "active"
        and row["region"] == "gw:%d:%s" % (S, front[0]) and r["events"][0]["t"] == "intro", r["battle"]["trainer"])
    chk("  공격권 하나를 쓰고, 기록은 '진행 중'", GW._row(a[0])["used"] == 1 and atk["result"] == "pending"
        and atk["def_user"] == weak and atk["def_guild"] == gb)
    chk("  상대 방어팀은 처음 나온 것만 보인다", sum(1 for m in r["battle"]["foe"]["team"] if not m.get("hidden")) == 1)
    chk("  판이 끝나기 전에는 다른 칸을 못 친다", code_of(lambda: GW.attack(a[0], front[-1])) == 409)
    chk("  관장 도전도 못 한다 (한 사람 한 판)", code_of(lambda: gym_routes.start(
        next(iter(__import__("app.gym", fromlist=["gyms"]).gyms()["regions"])), ctx=me(a[0]))) == 409)
    chk("  관장 탭에는 길드전 판을 '진행 중' 으로 띄우지 않는다", gym_routes.overview(ctx=me(a[0]))["active"] is None)
    st = GW.state(a[0])
    chk("  길드전 화면에 '이어서 하기' 가 뜬다", st.get("battle", {}).get("id") == r["id"])
    # 그 판을 끝까지 (한카리아스 둘 vs 잉어킹)
    out = None
    for _ in range(40):
        rowx = db.q1("SELECT * FROM gym_battle WHERE id=?", (r["id"],))
        if rowx["state"] != "active":
            break
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(rowx["data"]))
        _d, k = tb._best(tb.me, tb.foe)
        out = gym_routes.act(r["id"], gym_routes.ActIn(kind="move", move=k), ctx=me(a[0]))
    a1_ = db.q1("SELECT * FROM guild_war_attack WHERE battle_id=?", (r["id"],))
    chk("이기면 '1승' 이 쌓인다 (아직 칸은 그대로)", a1_["result"] == "win" and GW.tile(front[0])["guild_id"] == gb
        and out["reward"]["war"]["wins"] == 1 and any("3승 중 1승" in x for x in out["reward"]["lines"]),
        out and out.get("reward"))
    chk("  경험치는 없다 (길드전)", "exp" not in out)
    chk("  지도와 칸에 우리 승수가 보인다", GW.map_view(a[3])["cells"][front[0]].get("wins") == 1
        and GW.tile_view(a[3], front[0])["wins"] == 1)
    chk("  지키는 쪽에는 노리는 길드가 보인다", GW.tile_view(b[2], front[0])["threats"] == [{"guild": "가길드", "wins": 1}])
    chk("  전쟁 중에는 지키는 사람을 못 바꾼다 (공격받은 칸은 잠김 표시)", code_of(lambda: GW.place(b[0], b[2], front[0])) == 409
        and GW.tile_view(b[0], front[0])["locked"] is True)
    out = fight(a[1], front[0], win=False)
    chk("기권하면 진 것 (승수는 그대로, 막은 쪽에 방어 1)", db.q1(
        "SELECT result FROM guild_war_attack WHERE atk_user=? ORDER BY id DESC", (a[1],))["result"] == "lose"
        and GW._wins(S, front[0], ga) == 1 and next(x for x in GW.scores() if x["guildId"] == gb)["defends"] == 1)
    fight(a[0], front[0])
    chk("둘째 승", GW._wins(S, front[0], ga) == 2 and GW.tile(front[0])["guild_id"] == gb)
    out = fight(a[1], front[0])
    t = GW.tile(front[0])
    chk("셋째 승: 길드원이 합쳐 같은 상대를 3번 이기면 칸이 넘어온다", t["guild_id"] == ga and t["taken_at"]
        and t["home_guild"] == gb and t["guard_user"] == a[1] and out["reward"]["war"]["took"] is True
        and any("점령" in x for x in out["reward"]["lines"]), dict(t))
    chk("  칸 수가 옮겨 간다", GW.tile_counts() == {ga: 16, gb: 14, gc: 15}, GW.tile_counts())
    chk("  넘어간 칸은 아무도 다시 못 뺏는다", code_of(lambda: GW.attack(b[0], front[0])) == 409
        and GW.tile_view(b[0], front[0])["blocked"] == "이미 주인이 바뀐 칸이다 (다시 못 뺏는다)")
    chk("  지도에 '점령' 으로", GW.map_view(a[3])["cells"][front[0]].get("taken") == 1)
    chat = db.q1("SELECT body FROM guild_chat WHERE guild_id=? AND body LIKE '길드전:%' ORDER BY id DESC LIMIT 1",
                 (gb,))["body"]
    chk("  빼앗긴 길드의 채팅에 남는다", "빼앗겼습니다" in chat and t["name"] in chat, chat)
    mine_a = set(lands(ga))
    chk("  뺏은 칸 덕에 새로 맞닿은 칸도 칠 수 있게 된다", set(GW.map_view(a[3])["hit"]) == set(
        r_ for r_ in GW.neighbors() if GW.tile(r_)["guild_id"] != ga and not GW.tile(r_)["taken_at"]
        and GW.neighbors()[r_] & mine_a))
    chk("  우리 칸이 늘어도 길드원은 늘지 않는다 (넘어온 칸은 이긴 사람 이름으로)", guard_of(a[1]) is not None)

    print("\n=== 길드원이 공격을 구경한다 (친선전과 같은 카드) ===")
    sent = []
    guild.listeners.append(lambda kind, target, payload: sent.append((kind, target, payload)))
    friendly.reset()
    watchers.reset()
    # 다길드 칸을 친다 - 나길드의 방어 기록(아래 순위 검사)이 지도 모양에 따라 달라지지 않게
    target = next(r_ for r_ in GW.map_view(a[4])["hit"] if GW.tile(r_)["guild_id"] == gc)
    tt = GW.tile(target)
    r = GW.attack(a[4], target)
    fid = GW.fight_id(r["id"])
    msgs = [p_["m"] for k, tg, p_ in sent if p_.get("t") == "chat" and tg == ga and p_["m"].get("card")]
    card = msgs[-1]["card"] if msgs else {}
    gname = GW.entry(tt["guild_id"])["name"]
    chk("공격이 열리면 **우리 길드 채팅에 관전 카드**가 놓인다 (친선전 카드와 같은 꼴 + 길드전 칸)",
        card.get("k") == "friendly" and card.get("s") == "fight" and card.get("mid") == fid
        and card["a"] == {"id": a[4], "name": "가길드_04"} and card["b"]["name"].startswith("[%s] " % gname)
        and card["war"]["name"] == tt["name"] and card["war"]["need"] == 3, card)
    chk("  막는 길드의 채팅에는 카드가 안 간다", not [1 for k, tg, p_ in sent if p_.get("t") == "chat" and tg == tt["guild_id"]
                                         and p_["m"].get("card")])
    pushes = [p_["fight"] for k, tg, p_ in sent if p_.get("t") == "friendly_fight" and tg == ga]
    f0 = pushes[-1] if pushes else {}
    chk("  첫 모습이 길드원에게 나간다 (두 쪽, 나와 있는 포켓몬, 누구 편도 아닌 글)", f0.get("id") == fid
        and f0.get("kind") == "guildwar" and f0["a"]["name"] == "가길드_04" and f0["b"]["mon"]["hp"] > 0
        and f0["events"][0]["text"] == "가길드_04 님과 %s 님의 승부!" % card["b"]["name"]
        and not any("상대" in (e.get("text") or "") for e in f0["events"]) and f0.get("card") == msgs[-1]["id"], f0.get("events"))
    flat = json.dumps(f0, ensure_ascii=False)
    chk("  참가자만 아는 것은 없다 (기술 목록·지닌 도구)", '"moves"' not in flat and '"held"' not in flat)
    chk("  진행 중 목록에 올라간다 (친선전 수에는 안 센다)", [x["id"] for x in friendly.view(ga)["fights"]] == [fid]
        and friendly.count(ga) == 0)
    v = friendly.watch(a[5], fid, True)
    chk("길드원이 보기 시작하면 1명 - 공격하는 사람의 판에 '관전 1명'", v["n"] == 1
        and gym_routes.current(ctx=me(a[4]))["watchers"] == 1, v)
    chk("  공격하는 사람은 자기 판을 구경하지 않는다", code_of(lambda: friendly._run(friendly.watch, a[4], fid, True)) == 409)
    del sent[:]
    rowx = db.q1("SELECT * FROM gym_battle WHERE id=?", (r["id"],))
    tbx = TB.TrainerBattle.load(deps.dex(), json.loads(rowx["data"]))
    out = gym_routes.act(r["id"], gym_routes.ActIn(kind="move", move=tbx._best(tbx.me, tbx.foe)[1]), ctx=me(a[4]))
    f1 = [p_["fight"] for k, tg, p_ in sent if p_.get("t") == "friendly_fight"]
    chk("턴이 돌 때마다 그 턴에 일어난 일이 나간다", f1 and f1[-1]["turn"] == 1 and f1[-1]["events"]
        and f1[-1]["watchers"] == 1 and out["watchers"] == 1, f1[-1:] and f1[-1]["events"][:2])
    del sent[:]
    gym_routes.act(r["id"], gym_routes.ActIn(kind="forfeit"), ctx=me(a[4]))
    last = [p_["fight"] for k, tg, p_ in sent if p_.get("t") == "friendly_fight"][-1]
    card2 = [p_["card"] for k, tg, p_ in sent if p_.get("t") == "card"][-1]
    chk("끝나면 결과가 나가고 카드가 결과로 바뀐다 (기권 = 막아냈다)", last["over"] is True and last["result"] == "b"
        and card2["s"] == "over" and card2["result"] == "b" and card2["war"]["took"] is False
        and card2["war"]["name"] == tt["name"] and friendly.view(ga)["fights"] == [], (last.get("result"), card2))
    chk("  센 구경꾼을 버린다", watchers.count(fid) == 0)
    r2 = GW.attack(a[6], next(r_ for r_ in GW.map_view(a[6])["hit"] if GW.tile(r_)["guild_id"] == gc))
    fid2 = GW.fight_id(r2["id"])
    old = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(seconds=config.GYM_BATTLE_TTL + 60)).isoformat()
    db.run("UPDATE gym_battle SET updated_at=? WHERE id=?", (old, r2["id"]))
    del sent[:]
    GW.expire(datetime.datetime.now(datetime.timezone.utc))
    card3 = [p_["card"] for k, tg, p_ in sent if p_.get("t") == "card"]
    chk("손 놓아 접힌 판도 카드를 닫는다 (진 것으로)", card3 and card3[-1]["s"] == "over" and card3[-1]["result"] == "b"
        and fid2 not in [x["id"] for x in friendly.view(ga)["fights"]], card3[-1:])

    print("\n=== 내 몫·길드가 받는 공격의 상한 ===")
    used = GW._row(a[0])["used"]
    db.run("UPDATE guild_war_team SET used=attacks WHERE season=? AND user_id=?", (S, a[0]))
    chk("내 몫을 다 쓰면 못 친다", code_of(lambda: GW.attack(a[0], front[-1])) == 409
        and GW.tile_view(a[0], front[-1])["blocked"] == "공격 횟수를 다 썼다")
    db.run("UPDATE guild_war_team SET used=? WHERE season=? AND user_id=?", (used, S, a[0]))
    n = GW._received(S, gb)
    for k in range(GW.TOTAL_ATTACKS - n):
        db.run("INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild,"
               " def_name, result, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (S, far[0], c[0], gc, "다길드_00", 0, gb, "AI 수비대", "lose", "2026-10-21T00:00:00+00:00"))
    chk("길드 하나는 30번까지만 받는다", GW._received(S, gb) == 30 and code_of(lambda: GW.attack(a[0], front[-1])) == 409
        and GW.tile_view(a[0], front[-1])["blocked"] == "이 길드는 더 받을 수 없다")
    db.run("DELETE FROM guild_war_attack WHERE atk_user=? AND battle_id IS NULL", (c[0],))

    print("\n=== 손 놓은 판은 진 것 ===")
    r = GW.attack(a[2], front[-1])
    old = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(seconds=config.GYM_BATTLE_TTL + 60)).isoformat()
    db.run("UPDATE gym_battle SET updated_at=? WHERE id=?", (old, r["id"]))
    GW.expire(datetime.datetime.now(datetime.timezone.utc))
    chk("시간이 지나면 판이 접히고 기록은 진 것", db.q1("SELECT state, result FROM gym_battle WHERE id=?", (r["id"],))["result"]
        == "expired" and db.q1("SELECT result FROM guild_war_attack WHERE battle_id=?", (r["id"],))["result"] == "lose")
    chk("  공격권은 돌아오지 않는다", GW._row(a[2])["used"] == 1)

    print("\n=== 순위 ===")
    table = GW.scores()
    chk("칸이 많은 길드가 위 (가길드 16칸 1위)", [x["guildId"] for x in table][0] == ga
        and [x["tiles"] for x in table] == sorted((x["tiles"] for x in table), reverse=True))
    by = dict((x["guildId"], x) for x in table)
    chk("  점수 = 칸 수, 뺏은·잃은 칸, 방어·승리가 실린다", by[ga]["score"] == 16 and by[ga]["taken"] == 1
        and by[gb]["lost"] == 1 and by[gb]["defends"] == 2 and by[ga]["wins"] == 3,
        dict((k, (by[g_][k] for g_ in (ga, gb)) and [by[g_][k] for g_ in (ga, gb)])
             for k in ("score", "taken", "lost", "defends", "wins")))
    keys = [(x["tiles"], x["defends"], x["wins"]) for x in table]
    chk("  같으면 방어 성공 -> 공격 승리 순", keys == sorted(keys, reverse=True), keys)
    st = GW.state(a[0])
    chk("화면: 내 공격권, 길드원(공격·지키는 칸), 받은 공격", st["attacks"]["total"] == 9 and len(st["mates"]) == 15
        and all("tile" in m for m in st["mates"]) and st["can"]["manage"] is False and st["received"] >= 0)
    lg = GW.log(b[3])
    chk("기록: 우리 길드가 낀 판, 어느 칸인지, 점령 여부", lg and lg[0]["id"] > lg[-1]["id"]
        and any(x["took"] for x in lg) and all(x["regionName"] for x in lg))

    print("\n=== 전쟁 중에 길드를 나가면 ===")
    left = c[4]
    kept = guard_of(left)
    db.run("DELETE FROM guild_member WHERE user_id=?", (left,))
    chk("남은 공격권은 사라진다", code_of(lambda: GW.attack(left, front[-1])) == 403)
    chk("지키던 칸은 남는다", guard_of(left) == kept and GW.tile_view(a[3], kept)["guardId"] == left)
    chk("나간 사람에게는 옛 길드의 방어팀도 남의 것처럼", GW.tile_view(left, lands(gc)[0])["mine"] is False
        and GW.map_view(left)["myGuild"] is None)

    print("\n=== 끝: 진행 중인 판은 진 것, 순위와 보상 ===")
    r = GW.attack(a[3], front[-1])
    coin0 = dict((x, guild.coin(x)) for x in a + b + c)
    clock(at(days=13, minutes=1))
    st = GW.state(a[0])
    chk("끝 단계가 되면 진행 중이던 판은 진 것으로 접는다", st["phase"] == "done"
        and db.q1("SELECT result FROM guild_war_attack WHERE battle_id=?", (r["id"],))["result"] == "lose"
        and db.q1("SELECT state FROM gym_battle WHERE id=?", (r["id"],))["state"] == "done")
    chk("  끝난 판은 더 둘 수 없다", code_of(lambda: gym_routes.act(r["id"], gym_routes.ActIn(kind="move", move="X"),
                                                         ctx=me(a[3]))) in (409, 410))
    chk("  끝난 뒤에는 못 친다", code_of(lambda: GW.attack(a[5], front[-1])) == 409)
    final = GW.scores()
    rank_of = dict((x["guildId"], x["rank"]) for x in final)
    ok = True
    for g, people in ((ga, a), (gb, b), (gc, c)):
        want = GW.coins_for(rank_of[g])
        hitters = set(x["atk_user"] for x in db.q("SELECT DISTINCT atk_user FROM guild_war_attack WHERE atk_guild=?", (g,)))
        for x in people:
            if guild.coin(x) - coin0[x] != (want if x in hitters else 0):
                ok = False
    chk("순위대로 길드 코인, 공격한 사람에게만", ok, [(x["name"], x["rank"]) for x in final])
    gifts = db.q("SELECT user_id FROM gift WHERE title=?", (GW.GIFT_TITLE % S,))
    top_hitters = set(x["atk_user"] for x in db.q("SELECT DISTINCT atk_user FROM guild_war_attack WHERE atk_guild=?",
                                                  (final[0]["guildId"],)))
    chk("1위 길드의 공격한 길드원에게 칭호 선물", set(g_["user_id"] for g_ in gifts) == top_hitters)
    n_gift = len(gifts)
    GW.settle()
    chk("두 번 돌려도 한 번만 준다", len(db.q("SELECT 1 FROM gift WHERE title=?", (GW.GIFT_TITLE % S,))) == n_gift)
    chk("끝난 뒤에도 순위표와 지도가 보인다", len(GW.state(solo)["ranking"]) == 3 and len(GW.map_view(solo)["cells"]) == 45
        and GW.map_view(solo)["hit"] == [])
    chk("길드 채팅에 결과 (몇 칸인지)", "칸)" in db.q1(
        "SELECT body FROM guild_chat WHERE guild_id=? ORDER BY id DESC LIMIT 1", (final[0]["guildId"],))["body"])

    print("\n=== 참가 길드가 하나뿐이면 ===")
    wipe()
    db.run("DELETE FROM gift")
    clock(at(hours=2))
    GW.apply(a[0])
    clock(at(days=3, minutes=5))
    mv = GW.map_view(a[1])
    chk("혼자면 15칸을 받고 칠 칸이 없다", len(mv["cells"]) == 15 and mv["hit"] == [], (len(mv["cells"]), mv["hit"]))
    clock(at(days=7, minutes=5))
    chk("  전쟁 중에도", GW.map_view(a[1])["hit"] == [])
    clock(at(days=13, minutes=5))
    c0 = guild.coin(a[0])
    GW.state(a[0])
    chk("싸움이 없었으니 보상도 없다", guild.coin(a[0]) == c0 and db.q1("SELECT COUNT(*) c FROM gift")["c"] == 0)

    print("\n=== 신청한 길드가 해산돼 있어도 ===")
    wipe()
    gx, xx = mkguild("없어질길드", 5)
    clock(at(hours=2))
    GW.apply(a[0])
    GW.apply(xx[0])
    GW.apply(b[0])
    db.run("DELETE FROM guild_member WHERE guild_id=?", (gx,))
    db.run("DELETE FROM guild WHERE id=?", (gx,))
    clock(at(days=3, minutes=5))
    try:
        st = GW.state(a[0])
    except Exception as e:                                    # noqa: BLE001
        st = repr(e)
    chk("전략 기간이 시작될 때 터지지 않는다", isinstance(st, dict) and st["phase"] == "plan", st if not isinstance(st, dict) else "")
    chk("해산된 길드는 빼고 두 길드가 15칸씩", GW.entry(gx)["locked"] == -1 and GW.tile_counts() == {ga: 15, gb: 15})
    # 한 길드를 고정하다 터지면 그 길드만 다음에 다시 한다
    wipe()
    clock(at(hours=2))
    GW.apply(a[0])
    GW.apply(b[0])
    clock(at(days=3, minutes=5))
    real = GW._lock_guild
    boom = {"n": 0}

    def flaky(s_, gid_, now_=None):
        if gid_ == ga and not boom["n"]:
            boom["n"] += 1
            raise RuntimeError("일부러 낸 오류")
        return real(s_, gid_, now_)
    GW._lock_guild = flaky
    GW._lock()
    chk("한 길드에서 터져도 다른 길드는 고정되고, 지도는 아직 안 나눈다", GW.entry(gb)["locked"] == 1
        and GW.entry(ga)["locked"] == 0 and GW.tile_counts() == {})
    GW._lock()
    GW._lock_guild = real
    chk("다음 요청에서 마저 고정하고 지도를 나눈다", GW.entry(ga)["locked"] == 1 and GW.tile_counts() == {ga: 15, gb: 15}
        and GW._lock() is False)
    used_before = sum(r["used"] for r in GW.fighters(ga))
    GW._lock_guild(S, ga)
    chk("다시 고정하게 되더라도 쓴 횟수·나눈 횟수는 그대로", sum(r["used"] for r in GW.fighters(ga)) == used_before
        and sum(r["attacks"] for r in GW.fighters(ga)) == 30)

    print("\n=== 두 요청이 겹쳐 고정할 때 (2026-10-20 운영: 9길드로 먼저 나눈 지도에 10번째가 포개졌다) ===")
    # 요청 A 가 길드를 하나씩 고정하는 사이 요청 B 가 들어와, A 가 고정 중이라 건너뛴 길드를 빼고 지도를 나눴다
    # (한 바퀴 27열). A 가 마지막 길드(건대취정)를 고정한 뒤 다시 나누자 이미 있는 칸은 그대로 두고 그 길드의 칸만
    # 30열 기준 27~29열에 넣어서, 화면은 그 15칸을 0~2열(동물농장) 위에 포개 그렸다.
    wipe()
    (g1, p1), (g2, p2), (g3, p3) = [mkguild("겹%d길드" % k, 5) for k in (1, 2, 3)]
    clock(at(hours=2))
    for m_ in (p1[0], p2[0], p3[0]):
        GW.apply(m_)
    clock(at(days=3, minutes=5))
    S = season.SEASON
    GW._mark("gw:%d:locked:%d" % (S, g3), GW._iso(at(days=3, minutes=5)))   # 요청 A 가 셋째 길드를 고정하는 중
    GW._lock()                                                              # 요청 B
    chk("다른 요청이 아직 고정 중인 길드가 있으면 지도를 안 나눈다", GW.entry(g1)["locked"] == 1
        and GW.entry(g2)["locked"] == 1 and GW.entry(g3)["locked"] == 0 and GW.tile_counts() == {}, GW.tile_counts())
    GW._lock_guild(S, g3)                                                   # 요청 A 가 마저 고정했다
    GW._lock()
    chk("다 고정된 뒤에 세 길드로 한 번에 나눈다", GW.tile_counts() == {g1: 15, g2: 15, g3: 15}, GW.tile_counts())
    totals = set(json.loads(r["codes"])[2] for r in GW.tiles())
    chk("  모든 칸의 한 바퀴 열 수가 같다 (세 길드 = 9열)", totals == {9}, totals)
    names_ = dict((e["guild_id"], e["name"]) for e in GW.entries(S))
    geo = GW.ring_geo(GW.tiles(), names_)
    centers = [tuple(x["center"]) for x in geo["sgg"]]
    chk("  칸 자리가 겹치지 않는다 · 이름표 자리도", len(set(centers)) == 45
        and len(set((lb["x"], lb["y"]) for lb in geo["labels"])) == 3)

    wipe()
    clock(at(hours=2))
    GW.apply(p1[0])
    GW.apply(p2[0])
    clock(at(days=3, minutes=10))
    GW._mark("gw:%d:locked:%d" % (S, g2), GW._iso(at(days=3, minutes=1)))   # 고정하던 서버가 죽어 표시만 남았다 (9분 전)
    GW._lock()
    GW._lock()
    chk("고정하다 멈춘 지 %d초가 넘은 표시는 낡은 것으로 보고 다시 고정해서 나눈다" % GW.STALE_LOCK_SEC,
        GW.entry(g2)["locked"] == 1 and GW.tile_counts() == {g1: 15, g2: 15}, (GW.entry(g2)["locked"], GW.tile_counts()))

    print("\n=== 이미 그렇게 꼬인 지도 (한 바퀴 열 수가 섞인 칸) - 운영 데이터는 그대로, 읽을 때 바로잡는다 ===")
    wipe()
    cells2, owner2, _per = GW.layout([ga, gb])                              # 두 길드로 먼저 나눈 6열
    rows_ = []
    for i, (cell, g_) in enumerate(zip(cells2, owner2)):
        rows_.append({"region": GW.cell_id(i), "codes": json.dumps(cell), "home_guild": g_})
    for k in range(GW.TILES_PER_GUILD):                                     # 나중에 끼어든 셋째 길드: 9열 기준 6~8열
        row, j = divmod(k, GW.RING_COLS)
        rows_.append({"region": GW.cell_id(30 + k), "codes": json.dumps([row, 6 + j, 9]), "home_guild": gc})
    geo = GW.ring_geo(rows_, {ga: "가", gb: "나", gc: "다"})
    centers = [tuple(x["center"]) for x in geo["sgg"]]
    chk("열 수가 섞여 있어도 가장 큰 열 수(9)로 그려 칸이 안 겹친다", len(set(centers)) == 45, len(set(centers)))
    chk("  이름표 셋이 다른 자리", len(set((lb["x"], lb["y"]) for lb in geo["labels"])) == 3, geo["labels"])
    adj = GW._cell_adj([json.loads(r["codes"]) for r in rows_])
    first_c = next(i for i, r in enumerate(rows_) if r["home_guild"] == gc and json.loads(r["codes"])[:2] == [0, 8])
    near = set(rows_[j]["home_guild"] for j in adj[first_c])
    chk("  이웃도 9열 고리로 센다 (셋째 길드의 끝 열은 첫 길드와 맞닿는다)", ga in near, near)

    print("\n=== 길드 탭의 점 ===")
    wipe()
    clock(at(hours=2))
    GW.apply(a[0])
    GW.apply(b[0])
    chk("신청 기간에는 할 일이 없다고 본다", GW.brief(a[2]) == {"phase": "apply", "real": "apply", "todo": False},
        GW.brief(a[2]))
    clock(at(days=3, minutes=5))
    GW.state(a[2])
    chk("전략 기간에는 칠 수 없으니 할 일이 없다고 본다", GW.brief(a[2])["todo"] is False and GW.brief(a[2])["real"] == "plan",
        GW.brief(a[2]))
    # 1.13.1 까지의 화면은 apply·war·done 일 때만 '길드전' 칸을 냈다 (전략 기간에 모두에게 칸이 사라졌다, 2026-10-20)
    chk("  옛 화면이 아는 단계로 보낸다 - 업데이트 안 한 길드원에게도 칸이 뜬다",
        GW.brief(a[2])["phase"] in ("apply", "war", "done"), GW.brief(a[2]))
    chk("  길드전 칸 안은 진짜 단계 (전략)", GW.state(a[2])["phase"] == "plan")
    clock(at(days=7, minutes=5))
    chk("전쟁 중에 공격이 남았으면 할 일이 있다", GW.brief(a[2]) == {"phase": "war", "real": "war", "todo": True},
        GW.brief(a[2]))
    db.run("UPDATE guild_war_team SET used=attacks WHERE user_id=?", (a[2],))
    chk("다 쓰면 없다", GW.brief(a[2]) == {"phase": "war", "real": "war", "todo": False})
    chk("길드가 없으면 없다", GW.brief(solo)["todo"] is False)

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
