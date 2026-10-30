# -*- coding: utf-8 -*-
"""길드전 시즌 5 — 조커 · 개인 기여 보상 (guild_war.py 의 '조커 · 개인 기여 보상', 게시판 #373 의견).

    python server/test_guild_war_v5.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. **조커**: 길드장이 전략 기간에만, 길드마다 3명까지 (넷째는 막힌다). AI 수비대 칸 · 남의 칸은 안 된다.
     사람에 붙는다 - 칸을 옮기면 따라간다. 일반 길드원은 못 한다.
  2. 남의 길드에는 조커 칸의 이름 · 방어팀이 응답에 아예 없다 ('???', 마릿수만). 우리 길드는 다 본다.
     지도에는 조커 칸 표시만 (누가 숨었는지는 없다). 그 조커와 붙어 본 길드에게만 보통 칸처럼 보인다.
     조커가 뺏어 지키게 된 칸도 가린다 (10/30 검토 - 거기서 숨긴 방어팀이 보였다).
  3. **기여 보상**: 이기면 20 · 조커를 이기면 40 · 공격 팀을 실제로 다 쓰러뜨려 막으면 지킨 사람에게 20 ·
     **기권 · 시간 초과로 막은 것은 0** (짠 길드끼리 기권해 주며 코인을 주고받지 못하게, 10/30 검토) ·
     AI 수비대가 막으면 아무도 안 받는다 · 한 시즌 300개까지 (넘치는 만큼은 잘린다).
  4. 시즌 4 에는 전부 꺼져 있다 (조커 409, 응답에 칸 없음, 이겨도 코인 그대로).
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

TMP = tempfile.mkdtemp(prefix="poket-gwar5-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import db, deps, guild, guild_war as GW, gym_routes, season   # noqa: E402
from common import pokelogic as P                             # noqa: E402
from common import trainer_battle as TB                       # noqa: E402

OK = FAIL = 0
T0 = GW.starts()
NAMES = {}


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


def mkuser(name, species, level, mons=2):
    uid = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid
    d = deps.dex()
    for i in range(mons):
        m = P.make_pokemon(d.get(species), level, random.Random(uid * 10 + i), shiny_rate=10 ** 9)
        pid = db.insert_mon(uid, m, "2026-01-01")
        db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=? WHERE id=?", (i, level, pid))
    NAMES[uid] = name
    return uid


def mkguild(name, n, species="GARCHOMP", level=60):
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
    GW._now = lambda: t
    gym_routes._now = lambda: t


def wipe():
    for t in ("guild_war_attack", "guild_war_tile", "guild_war_team", "guild_war_entry", "gym_battle",
              "guild_member", "guild", "guild_user", "guild_chat"):
        db.run("DELETE FROM %s" % t)
    db.run("DELETE FROM meta WHERE k LIKE 'gw:%'")


def me(uid):
    return {"user": {"id": uid}}


def tile_of(uid):
    r = db.q1("SELECT region FROM guild_war_tile WHERE season=? AND guard_user=? AND taken_at IS NULL",
              (season.SEASON, uid))
    return r["region"] if r else None


def fight(uid, region, win=True):
    """그 칸에 승부를 걸고 끝까지 둔다 (gym_routes.act 의 마지막 응답). win 이 아니면 바로 기권."""
    r = GW.attack(uid, region)
    bid = r["id"]
    if not win:
        return gym_routes.act(bid, gym_routes.ActIn(kind="forfeit"), ctx=me(uid))
    out = None
    for _ in range(120):
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


def last_attack(uid):
    return db.q1("SELECT * FROM guild_war_attack WHERE atk_user=? ORDER BY id DESC LIMIT 1", (uid,))


def setup():
    """세 길드 (고리라 서로 다 이웃). 가길드는 약한 포켓몬이라 공격이 이긴다. 전략 기간에 둔다."""
    wipe()
    ga, a = mkguild("가길드%d" % season.SEASON, 5, species="MAGIKARP", level=5)
    gb, b = mkguild("나길드%d" % season.SEASON, 5)
    gc, c = mkguild("다길드%d" % season.SEASON, 5)
    clock(at(hours=1))
    for m in (a[0], b[0], c[0]):
        GW.apply(m)
    clock(at(days=3, hours=1))
    GW._lock(at(days=3, hours=1))
    return (ga, a), (gb, b), (gc, c)


def v5():
    season.SEASON = 5
    (ga, a), (gb, b), (gc, c) = setup()
    s = season.SEASON
    adj = GW.neighbors(s)
    land = dict((g, set(r["region"] for r in GW.tiles(s) if r["guild_id"] == g)) for g in (gb, gc))
    # 가길드의 사람 칸 가운데 나·다 길드와 맞닿은 것 - 둘 이상 맞닿은 쪽이 공격한다
    near = dict((g, [u for u in a if tile_of(u) and adj[tile_of(u)] & land[g]]) for g in (gb, gc))
    xg, yg = (gb, gc) if len(near[gb]) >= len(near[gc]) else (gc, gb)
    x = b if xg == gb else c
    y = c if xg == gb else b
    jk, plain = near[xg][0], near[xg][1]
    others = [u for u in a if u not in (jk, plain)]
    chk("준비: 공격할 길드와 맞닿은 가길드 사람 칸이 둘 이상", len(near[xg]) >= 2, near)

    print("=== 1. 조커 정하기 (전략 기간) ===")
    chk("일반 길드원은 못 한다 (403)", code_of(lambda: GW.set_joker(a[3], tile_of(jk), True)) == 403)
    chk("길드장이 숨긴다", GW.set_joker(a[0], tile_of(jk), True) is True and GW.joker_count(ga) == 1)
    chk("  같은 것을 또 누르면 아무 일 없음", GW.set_joker(a[0], tile_of(jk), True) is False)
    chk("부마스터도 된다 (둘째·셋째)", GW.set_joker(a[1], tile_of(others[0]), True)
        and GW.set_joker(a[0], tile_of(others[1]), True) and GW.joker_count(ga) == 3)
    chk("넷째는 막힌다 (409, 길드마다 3명)", code_of(lambda: GW.set_joker(a[0], tile_of(others[2]), True)) == 409
        and GW.joker_count(ga) == 3)
    chk("풀면 자리가 난다", GW.set_joker(a[0], tile_of(others[1]), False) and GW.joker_count(ga) == 2)
    ai = db.q1("SELECT region FROM guild_war_tile WHERE season=? AND guild_id=? AND guard_user=0", (s, ga))
    chk("AI 수비대 칸은 안 된다 (409)", ai and code_of(lambda: GW.set_joker(a[0], ai["region"], True)) == 409)
    chk("남의 길드 칸은 안 된다 (409)", code_of(lambda: GW.set_joker(a[0], tile_of(x[2]), True)) == 409)
    # 사람에 붙는다: 조커(jk)를 others[2] 의 칸으로 옮기면 표시가 따라간다
    was, there = tile_of(jk), tile_of(others[2])
    GW.place(a[0], jk, there)
    marks = set(k for k, v in GW.map_view(x[0])["cells"].items() if v.get("joker"))
    chk("칸을 옮기면 조커가 따라간다", tile_of(jk) == there and there in marks and was not in marks, marks)
    GW.place(a[0], jk, was)
    jt = tile_of(jk)
    chk("  되돌려 놓음", jt == was)

    print("\n=== 2. 보이는 것 ===")
    v = GW.tile_view(x[0], jt)
    blob = json.dumps(v, ensure_ascii=False)
    chk("남의 길드: 지키는 쪽 '???' · 방어팀 없음 · 마릿수만", v["guard"] == "???" and v["guardId"] is None
        and v["team"] == [] and v["hidden"] == v["size"] and v["size"] >= 1 and v["joker"] and v["jokerHidden"], v)
    chk("  이름 · 종이 응답 어디에도 없다", NAMES[jk] not in blob and "MAGIKARP" not in blob and "잉어킹" not in blob)
    v = GW.tile_view(a[4], jt)
    chk("우리 길드: 이름 · 방어팀이 다 보인다 (조커 표시는 있다)", v["guard"] == NAMES[jk] and v["team"]
        and v["joker"] and not v["jokerHidden"], v)
    v = GW.tile_view(a[0], jt)
    chk("길드장: 조커 수 2/3", v.get("jokerCount") == 2 and v.get("jokerMax") == 3 and v.get("manager"), v)
    v = GW.tile_view(x[0], tile_of(plain))
    chk("조커가 아닌 칸은 그대로 (이름 · 앞 3마리)", v["guard"] == NAMES[plain] and v["team"] and not v["joker"], v)
    cells = GW.map_view(x[0])["cells"]
    marks = sorted(k for k, c_ in cells.items() if c_.get("joker"))
    chk("지도: 조커 칸 둘만 표시 · 누가인지는 없다", marks == sorted([jt, tile_of(others[0])])
        and all(set(cells[k]) <= {"codes", "g", "name", "joker", "me", "wins", "ai", "taken"} for k in marks), marks)
    st = GW.state(a[0])
    chk("길드전 화면: 조커 최대 3 · 길드원 표시 · 기여 보상 안내", st.get("jokerMax") == 3
        and sorted(m["userId"] for m in st["mates"] if m.get("joker")) == sorted([jk, others[0]])
        and st.get("contrib") == {"win": 20, "joker": 20, "defend": 20, "max": 300, "earned": 0}, st.get("contrib"))
    solo = mkuser("길드없음5", "GARCHOMP", 60)
    chk("  길드가 없어도 규칙 칸에 조커 수", GW.state(solo).get("jokerMax") == 3)
    # 공격하는 길드에도 조커 하나 (x[3]) - 나중에 가길드 칸을 뺏어 지키게 된다
    chk("공격하는 길드도 조커를 둔다", GW.set_joker(x[0], tile_of(x[3]), True) and GW.joker_count(xg) == 1)

    print("\n=== 3. 전쟁: 기여 보상 ===")
    clock(at(days=7, hours=1))
    pr = tile_of(plain)
    chk("전쟁이 시작되면 조커를 못 바꾼다 (409)", code_of(lambda: GW.set_joker(a[0], jt, False)) == 409)
    c0 = guild.coin(x[0])
    out = fight(x[0], tile_of(plain))
    r = last_attack(x[0])
    lines = ((out or {}).get("reward") or {}).get("lines") or []
    chk("이기면 20개 (바로)", r["result"] == "win" and r["coins"] == 20 and guild.coin(x[0]) == c0 + 20
        and GW._earned(s, x[0]) == 20, (r["result"], r["coins"]))
    chk("  결과 창 줄에 적힌다", any("기여 보상: 길드 코인 20개" in ln for ln in lines), lines)
    c1 = guild.coin(x[1])
    fight(x[1], jt)
    r = last_attack(x[1])
    chk("조커를 이기면 40개", r["result"] == "win" and r["coins"] == 40 and guild.coin(x[1]) == c1 + 40,
        (r["result"], r["coins"]))
    chk("한 번 붙어 본 길드에는 보통 칸처럼 보인다", GW.tile_view(x[2], jt)["guard"] == NAMES[jk]
        and not GW.tile_view(x[2], jt)["jokerHidden"])
    chk("  안 붙어 본 길드에는 여전히 '???'", GW.tile_view(y[0], jt)["guard"] == "???")
    d0 = guild.coin(jk)
    fight(x[2], jt, win=False)
    r = last_attack(x[2])
    chk("기권으로 막은 것은 지킨 사람도 0개 (짜고 주고받기 막기)", r["result"] == "lose" and r["def_coins"] == 0
        and r["coins"] == 0 and guild.coin(jk) == d0 and GW._earned(s, jk) == 0, (r["result"], r["def_coins"]))
    # 시간이 지나 접힌 판도 공격한 쪽에서는 진 것이지만, 지킨 사람은 안 받는다
    GW.attack(x[4], jt)
    r = last_attack(x[4])
    db.run("UPDATE gym_battle SET updated_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", r["battle_id"]))
    GW.expire(at(days=7, hours=2))
    r = last_attack(x[4])
    chk("시간 초과로 막은 것도 0개", r["result"] == "lose" and r["def_coins"] == 0 and guild.coin(jk) == d0,
        (r["result"], r["def_coins"]))
    # 진짜로 막아 낸 판: 약한 가길드가 공격하다 다 쓰러진다 -> 지킨 사람이 받는다
    hit = [h for h in GW.map_view(a[4])["hit"] if GW.tile(h, s)["guild_id"] == xg]
    who = [h for h in hit if GW.tile(h, s)["guard_user"] in x]
    ai_hit = [h for h in hit if GW.tile(h, s)["guard_user"] == 0]
    chk("준비: 가길드와 맞닿은 공격 길드의 사람 칸 · AI 칸", who and ai_hit, hit)
    g = GW.tile(who[0], s)["guard_user"]
    e0, w0 = guild.coin(g), GW._earned(s, g)
    fight(a[4], who[0])
    r = last_attack(a[4])
    chk("공격 팀을 다 쓰러뜨려 막으면 지킨 사람에게 20개", r["result"] == "lose" and r["def_coins"] == 20
        and guild.coin(g) == e0 + 20 and GW._earned(s, g) == w0 + 20, (r["result"], r["def_coins"]))
    before = dict((u, guild.coin(u)) for u in a + x)
    fight(a[3], ai_hit[0])
    r = last_attack(a[3])
    chk("AI 수비대가 막으면 아무도 안 받는다", r["result"] == "lose" and r["def_coins"] == 0 and r["coins"] == 0
        and all(guild.coin(u) == before[u] for u in before), r["result"])
    # 상한: 290개 받은 사람이 이기면 10개만, 그다음은 0개
    db.run("UPDATE guild_war_team SET earned=290 WHERE season=? AND user_id=?", (s, x[3]))
    c3 = guild.coin(x[3])
    fight(x[3], tile_of(plain))
    r = last_attack(x[3])
    chk("상한 300 - 넘치는 만큼은 잘린다 (10개)", r["coins"] == 10 and guild.coin(x[3]) == c3 + 10
        and GW._earned(s, x[3]) == 300, (r["coins"], GW._earned(s, x[3])))
    out = fight(x[3], tile_of(plain) or jt)
    r = last_attack(x[3])
    lines = ((out or {}).get("reward") or {}).get("lines") or []
    chk("  다 채우면 0개 · 결과 창에 상한이라고 적는다", r["result"] == "win" and r["coins"] == 0
        and guild.coin(x[3]) == c3 + 10 and any("상한" in ln for ln in lines), (r["coins"], lines))
    chk("상태: 내가 받은 기여 보상", GW.state(x[3])["contrib"]["earned"] == 300)
    t = GW.tile(pr, s)
    chk("준비: 공격 길드의 조커(x[3])가 셋째 승으로 칸을 가져왔다", t["taken_at"] and t["guard_user"] == x[3], dict(t))
    fought = db.q1("SELECT 1 FROM guild_war_attack WHERE season=? AND def_user=? AND atk_guild=?", (s, x[3], yg))
    v = GW.tile_view(y[0], pr)
    blob = json.dumps(v, ensure_ascii=False)
    chk("조커가 뺏어 지키는 칸도 남에게는 '???' (숨긴 방어팀이 안 드러난다)", not fought and v["guard"] == "???"
        and v["team"] == [] and v["jokerHidden"] and NAMES[x[3]] not in blob and "GARCHOMP" not in blob, v)
    chk("  우리 길드에는 보인다", GW.tile_view(x[1], pr)["guard"] == NAMES[x[3]])


def v4():
    print("\n=== 4. 시즌 4 에는 꺼져 있다 ===")
    season.SEASON = 4
    (ga, a), (gb, b), (gc, c) = setup()
    s = season.SEASON
    chk("조커를 못 정한다 (409)", code_of(lambda: GW.set_joker(a[0], tile_of(a[2]), True)) == 409)
    v = GW.tile_view(b[0], tile_of(a[2]))
    chk("칸 응답에 조커 칸이 없다", "joker" not in v and "jokerHidden" not in v and v["guard"] == NAMES[a[2]], v)
    st = GW.state(a[0])
    chk("길드전 화면에 조커 · 기여 보상이 없다 (칸 자체가 없다)", "jokerMax" not in st and "contrib" not in st
        and not any("joker" in m for m in st.get("mates") or []))
    clock(at(days=7, hours=1))
    hit = [h for h in GW.map_view(b[0])["hit"] if GW.tile(h, s)["guard_user"] in a]
    c0 = guild.coin(b[0])
    fight(b[0], hit[0])
    r = last_attack(b[0])
    chk("이겨도 기여 보상이 없다", r["result"] == "win" and r["coins"] == 0 and guild.coin(b[0]) == c0,
        (r["result"], r["coins"]))


def main():
    db.init()
    cols = dict((t, set(r["name"] for r in db.q("PRAGMA table_info(%s)" % t)))
                for t in ("guild_war_team", "guild_war_attack"))
    chk("새 칸이 있다 (joker · earned · coins · def_coins)", {"joker", "earned"} <= cols["guild_war_team"]
        and {"coins", "def_coins"} <= cols["guild_war_attack"], cols)
    real = season.SEASON
    try:
        v5()
        v4()
    finally:
        season.SEASON = real
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
