# -*- coding: utf-8 -*-
"""길드전 1:1 맞대결 (시즌 6 부터 - 11/14 사용자 "길드전은 시즌 6부터") - guild_war_match.py · guild_war.py 의 갈래 · 경로.

    .venv-server/bin/python server/test_guild_war_match.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 판은 진짜로 둔다 (한카리아스 길드가 잉어킹 길드를 친다) -
승패를 맞춰야 하는 곳만 공격 줄을 바로 넣는다. 못 박는 것:

  1. 매칭(pairing): 2곳 짝 · 3곳 삼각형 · 짝수 · 홀수(삼각형 하나) · 시즌 5 실제 명단 · 같은 입력 같은 결과 ·
     같은 인원이면 지난 시즌 상대를 피한다 · 출전 상한(cap_of).
  2. 별: 이김(절반 남김 ★★★ / 아님 ★★) · 짐(절반 쓰러뜨림 ★ / 아님 없음) · 비김 · 기권.
  3. 전략 기간: 상대가 정해지고(pair 줄 · 채팅) 한 사람 2번 · 상대 명단은 앞 3마리 · 아직 못 친다 · 조커는 '???' 와
     음수 자리 표시 · 지도 길(map · tile · attacks · guard)은 409.
  4. 전쟁: 진짜 판 이김 → 별 · 쓰러뜨린 수 · 별 코인 · 결과 줄 · 채팅 · 같은 사람 두 번 막힘 · 가려진 조커를 음수로
     친다 → 그 뒤로는 보인다 · 3번째 막힘 · 우리 길드 사람 막힘 · 기권은 별 0, 지킨 사람 코인 없음 · 손 놓은 판은
     시간이 지나 진 것으로 (판에서 쓰러뜨린 수를 센다).
  5. 삼각형 + 출전 상한: 8 · 5 · 5 길드 → 상한 6, 약한 2명 쉼 · 쉬는 사람은 못 치고 명단에 없다 · 길드장이 바꾼다
     (수가 안 맞으면 409) · 승패는 '내가 칠 길드에게서' 대 '나를 친 길드가 나에게서' (2승 1패).
  6. 결산 (보상 = 길드 코인만, 11/12): 판마다 별 코인 ★20 · ★★40 · ★★★60 (+조커 20 · 막기 20) · 결산은 공격한 사람에게
     이김 100 · 비김 60 · 짐 30 · 순위 보상(꾸미기 · 칭호 · 뽑기권) 없음 · 이번 시즌 맞대결 목록 · 한 번만.
  7. 시즌 5 는 지도전 그대로 (pair 줄 없음 · 칸이 나뉜다 · 맞대결 판 409).
"""
import datetime
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="poket-gwmatch-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import config, db, deps, guild, guild_war as GW, guild_war_match as GM, gym_routes, season   # noqa: E402
from common import pokelogic as P                             # noqa: E402
from common import trainer_battle as TB                       # noqa: E402

OK = FAIL = 0
NAMES = {}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# ---------------------------------------------------------------- 도우미
def mkuser(name, species="GARCHOMP", level=60, mons=2):
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


def mkguild(name, n, species="GARCHOMP", level=60, weak=()):
    """n 명짜리 길드. 첫 사람이 마스터, 둘째가 부마스터. weak 자리는 잉어킹 Lv.5 (방어팀 전력이 약하다)."""
    ids = [mkuser("%s_%02d" % (name, i), "MAGIKARP" if i in weak else species, 5 if i in weak else level)
           for i in range(n)]
    gid = db.run("INSERT INTO guild (name, intro, join_mode, master_id, created_at) VALUES (?,?,?,?,?)",
                 (name, "", "open", ids[0], "2026-10-01T00:00:00+00:00")).lastrowid
    for i, uid in enumerate(ids):
        role = "master" if i == 0 else ("sub" if i == 1 else "member")
        db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
               (uid, gid, role, "2026-10-01T00:%02d:00+00:00" % i))
    return gid, ids


def at(days=0, hours=0, minutes=0):
    return (GW.starts() + datetime.timedelta(days=days, hours=hours, minutes=minutes)).astimezone(
        datetime.timezone.utc)


def clock(t):
    GW._now = lambda: t
    gym_routes._now = lambda: t


def wipe():
    for t in ("guild_war_attack", "guild_war_tile", "guild_war_team", "guild_war_entry", "guild_war_pair",
              "gym_battle", "guild_member", "guild", "guild_user", "guild_chat", "gift"):
        db.run("DELETE FROM %s" % t)
    db.run("DELETE FROM meta WHERE k LIKE 'gw:%'")


def me(uid):
    return {"user": {"id": uid}}


def code_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def fight(uid, target, how="win"):
    """1:1 공격을 걸고 끝까지 둔다. win = 가장 아픈 기술로 싸운다 · forfeit = 바로 기권 · leave = 열어 두고 손 놓는다."""
    r = GM.attack(uid, target)
    bid = r["id"]
    if how == "forfeit":
        return r, gym_routes.act(bid, gym_routes.ActIn(kind="forfeit"), ctx=me(uid))
    if how == "leave":
        return r, None
    out = None
    for _ in range(150):
        row = db.q1("SELECT * FROM gym_battle WHERE id=?", (bid,))
        if row["state"] != "active":
            break
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(row["data"]))
        if tb.need_switch:
            out = gym_routes.act(bid, gym_routes.ActIn(kind="switch", slot=tb.valid_switches()[0]), ctx=me(uid))
        else:
            _d, k = tb._best(tb.me, tb.foe)
            out = gym_routes.act(bid, gym_routes.ActIn(kind="move", move=k or tb.bt.usable(tb.me)[0]), ctx=me(uid))
    return r, out


def last_attack(uid):
    return db.q1("SELECT * FROM guild_war_attack WHERE atk_user=? ORDER BY id DESC LIMIT 1", (uid,))


def put(s, atk, agid, dfn, dgid, stars, kos, size=2, res=None):
    """끝난 공격 줄을 바로 넣는다 (승패를 맞춰야 할 때)."""
    res = res or ("win" if stars >= 2 else "lose")
    when = GW._iso(at(days=8))
    db.run("INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild, def_name,"
           " result, created_at, ended_at, stars, kos, def_size) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (s, "u%d" % dfn, atk, agid, NAMES.get(atk, "?"), dfn, dgid, NAMES.get(dfn, "?"), res, when, when,
            stars, kos, size))


def coin(uid):
    return guild.coin(uid)


def chat(gid):
    return [r["body"] for r in db.q("SELECT body FROM guild_chat WHERE guild_id=? ORDER BY id", (gid,))]


def to_war(gs, s=6):
    """신청 → 전략 기간(명단 고정 · 상대 정하기). gs = [(길드, 사람들)]"""
    clock(at(hours=1))
    for gid, ids in gs:
        GW.apply(ids[0])
    t = at(days=3, hours=1)
    clock(t)
    GW._lock(t)


# ---------------------------------------------------------------- 1 · 2. 순수
def pure_part():
    print("=== 1. 매칭 ===")
    sizes = lambda groups: [[x[1] for x in g] for g in groups]          # noqa: E731
    gids = lambda groups: [[x[0] for x in g] for g in groups]           # noqa: E731
    chk("1곳이면 없음", GM.pairing([(1, 10, 5.0)]) == [])
    g = GM.pairing([(1, 10, 5.0), (2, 8, 5.0)])
    chk("2곳 = 짝 하나", sizes(g) == [[10, 8]], sizes(g))
    g = GM.pairing([(1, 10, 5.0), (2, 8, 5.0), (3, 9, 5.0)])
    chk("3곳 = 삼각형 하나 (큰 순)", sizes(g) == [[10, 9, 8]], sizes(g))
    g = GM.pairing([(1, 15, 1.0), (2, 14, 1.0), (3, 10, 1.0), (4, 9, 1.0)])
    chk("짝수 = 이웃끼리 짝 (15·14 · 10·9)", sizes(g) == [[15, 14], [10, 9]], sizes(g))
    s5 = [(10 + i, n, 1.0 + i) for i, n in enumerate([15, 15, 15, 14, 13, 11, 11, 11, 9, 8, 5])]
    g = GM.pairing(s5)
    chk("시즌 5 실제 명단(11곳): 삼각형 15·15·15 + 14·13 · 11·11 · 11·9 · 8·5",
        sorted(sizes(g), key=lambda x: (-len(x), -x[0])) == [[15, 15, 15], [14, 13], [11, 11], [11, 9], [8, 5]],
        sizes(g))
    chk("  삼각형은 하나", sum(1 for x in g if len(x) == 3) == 1)
    chk("  같은 입력이면 같은 결과", GM.pairing(list(reversed(s5))) == g)
    four = [(1, 10, 4.0), (2, 10, 3.0), (3, 10, 2.0), (4, 10, 1.0)]
    g = GM.pairing(four)
    chk("같은 인원이면 전력 가까운 쪽끼리 (1·2 · 3·4)", sorted(sorted(x) for x in gids(g)) == [[1, 2], [3, 4]], gids(g))
    g = GM.pairing(four, {1: {2}, 2: {1}})
    chk("지난 시즌 1·2 가 붙었으면 피한다", all(sorted(x) != [1, 2] for x in gids(g)), gids(g))
    g = GM.pairing([(1, 8, 5.0), (2, 6, 1.0), (3, 6, 3.0), (4, 5, 4.0)])
    chk("인원 차가 같으면 이웃이 아닌 짝도 견준다 (8·5 + 6·6 = 차 3, 전력 차 3 < 8·6 + 6·5 의 5) - 검토 4",
        sorted(sorted(x) for x in gids(g)) == [[1, 4], [2, 3]], gids(g))
    g = GM.pairing([(1, 12, 1.0), (2, 10, 1.0)], {1: {2}})
    chk("  피할 수 없으면(둘뿐) 그대로 붙는다", gids(g) == [[1, 2]], gids(g))
    chk("상한: 8 대 5 = 6 · 11 대 9 = 없음 · 15 대 13 = 없음 · 같으면 없음",
        (GM.cap_of([8, 5]), GM.cap_of([11, 9]), GM.cap_of([15, 13]), GM.cap_of([5, 5]), GM.cap_of([8, 5, 5]))
        == (6, None, None, None, 6),
        (GM.cap_of([8, 5]), GM.cap_of([11, 9]), GM.cap_of([15, 13]), GM.cap_of([5, 5])))

    print("\n=== 2. 별 ===")
    cases = [(("won", 6, 6, 3, 6), 3, "이기고 절반 남김"), (("won", 6, 6, 2, 6), 2, "이겼지만 절반 아래"),
             (("won", 2, 2, 1, 2), 3, "2마리 팀이 1마리 남김"), (("lost", 3, 6, 0, 6), 1, "졌지만 절반 쓰러뜨림"),
             (("lost", 2, 6, 0, 6), 0, "절반 못 쓰러뜨림"), (("lost", 3, 5, 0, 5), 1, "5마리 중 3"),
             (("lost", 2, 5, 0, 5), 0, "5마리 중 2"), (("draw", 3, 6, 1, 6), 1, "비김 = 진 것처럼"),
             (("forfeit", 0, 6, 6, 6), 0, "바로 기권"), (("expired", 4, 6, 2, 6), 1, "시간 초과도 쓰러뜨린 만큼")]
    for args, want, what in cases:
        chk("%s → %d" % (what, want), GM.stars(*args) == want, GM.stars(*args))


# ---------------------------------------------------------------- 3 · 4. 1:1
def pair_part():
    print("\n=== 3. 전략 기간 (시즌 6, 6명 vs 5명) ===")
    season.SEASON = 6
    s = 6
    wipe()
    g1, A = mkguild("강한길드", 6)
    g2, B = mkguild("약한길드", 5, species="MAGIKARP", level=5)
    to_war([(g1, A), (g2, B)])
    p1, p2 = GM.pair_of(g1, s), GM.pair_of(g2, s)
    chk("상대가 정해졌다 (1:1 - 칠 길드 = 치는 길드)", p1 and p2 and p1["target_guild"] == g2 and p1["from_guild"] == g2
        and p2["target_guild"] == g1 and p1["kind"] == "pair" and p1["cap"] is None, dict(p1) if p1 else None)
    chk("  지도는 안 나뉜다", not db.q1("SELECT 1 FROM guild_war_tile WHERE season=?", (s,)))
    chk("  출전한 사람마다 2번", set(r["attacks"] for r in GW.fighters(g1, s)) == {2}
        and set(r["attacks"] for r in GW.fighters(g2, s)) == {2})
    chk("  채팅에 상대 · 2번", any("[약한길드] (5명)" in x and "2번씩" in x for x in chat(g1)), chat(g1)[-2:])
    st = GW.state(A[3])
    chk("state: mode match · each 2 · 상대 · 앞섬 even", st.get("mode") == "match" and st.get("each") == 2
        and st["match"]["target"]["name"] == "약한길드" and st["match"]["lead"] == "even"
        and st["match"]["result"] is None, st.get("match"))
    chk("  보상은 코인만: coinRules 별 20/40/60 · 조커 20 · 막기 20 · 상한 300 · 결산 100/60/30 · 순위 보상 줄 없음",
        st["coinRules"] == {"stars": [20, 40, 60], "joker": 20, "defend": 20, "max": 300,
                            "result": {"win": 100, "draw": 60, "lose": 30}}
        and st["rewards"] == [] and st["tmActive"] is None and st["ranking"] == [], st.get("coinRules"))
    chk("  이번 시즌 맞대결: 우리 판 하나 (두 길드)", len(st["matches"]) == 1 and st["matches"][0]["ours"]
        and sorted(x["name"] for x in st["matches"][0]["guilds"]) == ["강한길드", "약한길드"]
        and st["matches"][0]["final"] is False, st.get("matches"))
    chk("  우리 명단 6명 (쉬는 사람 없음 · 출전 상한 없음)", len(st["mates"]) == 6
        and not any(x["bench"] for x in st["mates"]) and st["can"]["roster"] is False)
    chk("지도 길은 409 (map · tile · attacks · guard · 옛 공격)",
        all((code_of(f) or (0,))[0] == 409 for f in (
            lambda: GW.map_view(A[0]), lambda: GW.tile_view(A[0], "c00"), lambda: GW.set_attacks(A[0], {}),
            lambda: GW.place(A[0], A[1], "c00"), lambda: GW.attack(A[0], "c00"))))
    chk("조커: 쉬지 않는 길드원을 숨긴다", GM.set_joker(B[0], B[2], True) is True)
    chk("  일반 길드원은 못 한다", (code_of(lambda: GM.set_joker(B[3], B[4], True)) or (0,))[0] == 403)
    mv = GM.match_view(A[0])
    foes = mv["foes"]
    hid = [f for f in foes if f["hidden"]]
    chk("맞대결 판: 칠 상대 5명 · 앞 3마리만 (2마리 팀이면 다)", len(foes) == 5
        and all(len(f["team"]) + f["more"] == f["size"] for f in foes), [(f["name"], f["size"]) for f in foes])
    chk("  조커는 이름 '???' · 포켓몬 없음 · 음수 자리 표시 · 진짜 번호는 응답 어디에도 없다",
        len(hid) == 1 and hid[0]["name"] == "???" and hid[0]["team"] == [] and hid[0]["userId"] < 0
        and B[2] not in [v for v in hid[0].values() if isinstance(v, int)], hid)
    chk("  아직 전략 기간이라 못 친다", all(not f["can"] and "전략 기간" in f["why"] for f in foes))
    chk("  우리 명단(지키는 쪽) 6명", len(mv["ours"]) == 6 and mv["kind"] == "pair")

    print("\n=== 4. 전쟁 ===")
    t = at(days=7, hours=1)
    clock(t)
    GW._lock(t)
    r, out = fight(A[0], B[3])
    a = last_attack(A[0])
    # 같은 종은 팀에 한 마리 (pvp.restrict) - 한카리아스 둘 · 잉어킹 둘인 팀은 한 마리씩 나간다
    chk("진짜 판 이김 → 별 3 (내 팀 다 남김) · 쓰러뜨린 1/1", a["result"] == "win" and a["stars"] == 3 and a["kos"] == 1
        and a["def_size"] == 1, dict(a))
    rw = (out or {}).get("reward") or {}
    chk("  결과 창: war.mode match · 별 3 · 줄에 ★★★", rw.get("war", {}).get("mode") == "match"
        and rw["war"]["stars"] == 3 and any("★★★" in x for x in rw.get("lines", [])), rw)
    chk("  별 코인 60 (★★★)", a["coins"] == 60 and coin(A[0]) == 60 and rw["war"].get("coins") == 60, (a["coins"], coin(A[0])))
    chk("  결과 줄에 길드 코인 60개", any("길드 코인 60개" in x for x in rw.get("lines", [])), rw.get("lines"))
    chk("  공격 시작 응답의 war.mode match", r.get("war", {}).get("mode") == "match", r.get("war"))
    chk("  우리 채팅에 ★★★", any("★★★" in x and B[3] and "약한길드" in x for x in chat(g1)), chat(g1)[-1:])
    c = code_of(lambda: GM.attack(A[0], B[3]))
    chk("같은 사람을 두 번 칠 수 없다", c and c[0] == 409 and "이미 한 번" in c[1], c)
    c = code_of(lambda: GM.attack(A[0], A[1]))
    chk("우리 길드 사람은 못 친다", c and c[0] == 409 and "출전 명단이 아니다" in c[1], c)
    hid_id = [f for f in GM.match_view(A[0])["foes"] if f["hidden"]][0]["userId"]
    r, out = fight(A[0], hid_id)
    a = last_attack(A[0])
    chk("가려진 조커를 음수 자리 표시로 친다 → 진짜 그 사람", a["def_user"] == B[2] and a["result"] == "win", dict(a))
    chk("  조커를 이기면 +20 (★★★ 60 + 20 = 80)", a["coins"] == 80 and coin(A[0]) == 140, (a["coins"], coin(A[0])))
    mv = GM.match_view(A[1])
    seen = [f for f in mv["foes"] if f["userId"] == B[2]]
    chk("  한 번 붙어 본 조커는 보인다 (이름 · 포켓몬)", seen and not seen[0]["hidden"] and seen[0]["name"] == NAMES[B[2]]
        and seen[0]["team"], seen)
    c = code_of(lambda: GM.attack(A[0], B[4]))
    chk("3번째는 막힌다 (공격 횟수를 다 썼다)", c and c[0] == 409 and "다 썼다" in c[1], c)
    chk("  판에서 '내가 친' 표시 · 나는 이제 아무도 못 친다", all(not f["can"] for f in GM.match_view(A[0])["foes"])
        and sum(1 for f in GM.match_view(A[0])["foes"] if f["mine"]) == 2)
    # 약한 길드의 반격: 기권 (별 0, 지킨 사람 코인 없음)
    fight(B[0], A[0], "forfeit")
    a = last_attack(B[0])
    chk("기권 → 짐 · 별 0 · 코인 없음 (공격한 사람 · 지킨 사람 둘 다)", a["result"] == "lose" and a["stars"] == 0
        and a["coins"] == 0 and a["def_coins"] == 0 and coin(B[0]) == 0 and coin(A[0]) == 140, dict(a))
    # 손 놓은 판: 시간이 지나 진 것으로
    fight(B[1], A[1], "leave")
    later = t + datetime.timedelta(seconds=config.GYM_BATTLE_TTL + 60)
    clock(later)
    GW.expire(later)
    a = last_attack(B[1])
    chk("손 놓은 판은 시간이 지나 짐 · 별이 적힌다 (0)", a["result"] == "lose" and a["stars"] == 0 and a["def_size"] == 1,
        dict(a))
    st = GW.state(A[2])
    m = st["match"]
    chk("성적: 우리 별 6/15 (40%) · 상대 0/18 · 우리가 앞섬", m["us"]["stars"] == 6 and m["us"]["max"] == 15
        and m["us"]["pct"] == 40.0 and m["them"]["stars"] == 0 and m["them"]["max"] == 18 and m["lead"] == "us", m)
    chk("  남은 공격: 우리 12번 중 2번 씀 → 10 · 상대 10번 중 2번 → 8",
        m["us"]["attacks"] == 2 and m["us"]["left"] == 10 and m["them"]["attacks"] == 2 and m["them"]["left"] == 8, m)
    me0 = [x for x in st["mates"] if x["userId"] == A[0]][0]
    chk("  명단: A0 별 6 · 2승", me0["stars"] == 6 and me0["wins"] == 2, me0)
    ours = dict((x["userId"], x) for x in GM.match_view(A[2])["ours"])
    chk("  우리 명단: A0 은 기권 한 번 막아 냄 · A1 은 시간 초과 한 번", ours[A[0]]["defends"] == 1
        and ours[A[1]]["tries"] == 1 and ours[A[0]]["worst"]["stars"] == 0, ours[A[0]])
    lg = GW.log(A[0])
    chk("기록: mode match · 별 · 이름", lg and lg[0].get("mode") == "match" and "stars" in lg[0]
        and lg[-1]["regionName"] == NAMES[B[3]], lg[-1] if lg else None)

    print("\n=== 6. 결산 (1:1) ===")
    end = at(days=13, hours=1)
    clock(end)
    GW.state(A[0])                                            # 결산은 화면을 열 때 돈다
    rows = dict((r["guildId"], r) for r in GW.scores(s))
    chk("결과: 강한길드 승리 · 약한길드 패배 (순위 칸 없음)", rows[g1]["result"] == "win" and rows[g2]["result"] == "lose"
        and "rank" not in rows[g1], rows)
    chk("결산 코인: 공격한 A0 +100 (판 140 + 100 = 240) · 진 길드에서 공격한 B0 · B1 +30",
        coin(A[0]) == 240 and coin(B[0]) == 30 and coin(B[1]) == 30, (coin(A[0]), coin(B[0]), coin(B[1])))
    chk("  공격 안 한 A5 는 없음", coin(A[5]) == 0, coin(A[5]))
    chk("  선물(꾸미기 · 칭호 · 뽑기권)은 하나도 없다", not db.q1("SELECT 1 FROM gift"),
        [dict(x) for x in db.q("SELECT user_id, kind, item_id FROM gift")])
    chk("  순위가 안 적힌다 (rank NULL) · score = 별", db.q1("SELECT rank, score FROM guild_war_entry WHERE season=? AND"
                                                     " guild_id=?", (s, g1))["rank"] is None)
    chk("  결산 채팅: 별 % · 승리 · 코인 100개", any("별 40.0%" in x and "승리" in x and "길드 코인 100개" in x
                                              for x in chat(g1)), chat(g1)[-1:])
    st = GW.state(A[0])
    chk("  끝난 뒤 맞대결 목록은 final", st["matches"] and st["matches"][0]["final"] is True)
    chk("  state.contrib.settled = 실제로 받은 결산 코인 (A0 100 · B0 30 · 공격 안 한 A5 0)",
        st["contrib"].get("settled") == 100 and GW.state(B[0])["contrib"].get("settled") == 30
        and GW.state(A[5])["contrib"].get("settled") == 0, st["contrib"])
    GW.settle(end)
    db.run("DELETE FROM meta WHERE k=?", ("gw:%d:settled" % s,))
    GW.settle(end)
    chk("두 번 돌려도(끝 표시를 지워도) 한 번", coin(A[0]) == 240 and coin(B[0]) == 30, (coin(A[0]), coin(B[0])))


# ---------------------------------------------------------------- 5. 삼각형 + 출전 상한
def tri_part():
    print("\n=== 5. 삼각형 + 출전 상한 (8 · 5 · 5) ===")
    season.SEASON = 6
    s = 6
    wipe()
    g1, A = mkguild("여덟", 8, weak=(6, 7))                   # 6 · 7 번은 방어팀이 약하다 → 쉰다
    g2, B = mkguild("다섯가", 5)
    g3, C = mkguild("다섯나", 5)
    to_war([(g1, A), (g2, B), (g3, C)])
    ps = dict((g, GM.pair_of(g, s)) for g in (g1, g2, g3))
    chk("삼각형: 셋 다 kind tri · 칠 길드와 치는 길드가 다르다 · 한 바퀴",
        all(p["kind"] == "tri" and p["target_guild"] != p["from_guild"] for p in ps.values())
        and set(p["target_guild"] for p in ps.values()) == {g1, g2, g3}
        and all(ps[p["target_guild"]]["from_guild"] == g for g, p in ps.items()), dict((g, dict(p)) for g, p in ps.items()))
    chk("  상한 6 (5 x 1.2)", all(p["cap"] == 6 for p in ps.values()))
    bench = set(r["user_id"] for r in GW.fighters(g1, s) if r["bench"])
    chk("  여덟 길드: 방어팀이 약한 2명(6 · 7번)이 쉰다 · 공격 0", bench == {A[6], A[7]}
        and all(r["attacks"] == 0 for r in GW.fighters(g1, s) if r["bench"]), bench)
    chk("  채팅에 칠 길드 · 치는 길드 · 쉬는 사람", any("돌아가며" in x and "쉽니다" in x for x in chat(g1)), chat(g1)[-1:])
    src0 = GM.pair_of(g1, s)["from_guild"]
    chk("  치는 길드 채팅의 상대 인원은 실제로 나오는 6명 (쉬는 사람 빼고) - 검토 7",
        any("[여덟] (6명)" in x for x in chat(src0)), [x for x in chat(src0) if "여덟" in x])
    st = GW.state(A[0])
    chk("  길드장에게 출전 명단 고르기 · 일반 길드원은 아님", st["can"]["roster"] is True
        and GW.state(A[3])["can"]["roster"] is False)
    c = code_of(lambda: GM.set_roster(A[0], [A[7]]))
    chk("  쉴 사람 수가 안 맞으면 409 (2명이어야)", c and c[0] == 409 and "2명" in c[1], c)
    chk("  바꾼다: 5 · 7번이 쉬고 6번이 나간다", GM.set_roster(A[0], [A[5], A[7]]) is True
        and set(r["user_id"] for r in GW.fighters(g1, s) if r["bench"]) == {A[5], A[7]}
        and GW._row(A[6], s)["attacks"] == 2 and GW._row(A[5], s)["attacks"] == 0)
    c = code_of(lambda: GM.set_joker(A[0], A[5], True))
    chk("  쉬는 사람은 조커로 못 숨긴다", c and c[0] == 409, c)
    src = ps[g1]["from_guild"]
    src_ids = B if src == g2 else C
    foes = GM.match_view(src_ids[0])["foes"]
    chk("  여덟 길드를 치는 길드에게 상대 명단은 6명 (쉬는 사람 없음)", len(foes) == 6
        and A[5] not in [f["userId"] for f in foes], len(foes))
    t = at(days=7, hours=1)
    clock(t)
    GW._lock(t)
    c = code_of(lambda: GM.attack(A[5], (B if ps[g1]["target_guild"] == g2 else C)[0]))
    chk("  쉬는 사람은 못 친다 (403)", c and c[0] == 403, c)
    # 승패: 칠 길드에게서 얻은 % 대 나를 친 길드가 나에게서 얻은 %
    tg = dict((g, ps[g]["target_guild"]) for g in (g1, g2, g3))
    people = {g1: [x for x in A if x not in (A[5], A[7])], g2: B, g3: C}
    want_pct = {g1: 0.5, g2: 0.3, g3: 0.4}
    for g in (g1, g2, g3):
        foes_ = people[tg[g]]
        need = round(want_pct[g] * 3 * len(foes_))
        k = 0
        for d in foes_:
            give = min(3, need - k)
            if give <= 0:
                break
            put(s, people[g][0], g, d, tg[g], give, 1)
            k += give
    res = dict((g, GM.outcome(s, g)[2]) for g in (g1, g2, g3))
    chk("  2승 1패 (여덟 50% 대 40% 승 · 칠 30% 대 50% 패 · 40% 대 30% 승)",
        sorted(res.values()) == ["lose", "win", "win"] and res[g1] == "win", res)
    ms = GW.state(A[0])["matches"]
    chk("  맞대결 목록: 삼각형 하나 (세 길드)", len(ms) == 1 and ms[0]["kind"] == "tri" and len(ms[0]["guilds"]) == 3, ms)
    print("\n=== 7. 시즌 5 는 지도전 그대로 ===")
    season.SEASON = 5
    wipe()
    h1, X = mkguild("육가", 5)
    h2, Y = mkguild("육나", 5)
    to_war([(h1, X), (h2, Y)])
    st5 = GW.state(X[0])
    chk("pair 줄 없음 · 칸이 나뉜다 · 공격은 길드 합 30번을 인원수로 (5명 6번씩) · state 에 mode 없음",
        not db.q1("SELECT 1 FROM guild_war_pair WHERE season=5")
        and db.q1("SELECT COUNT(*) c FROM guild_war_tile WHERE season=5")["c"] == 30
        and set(r["attacks"] for r in GW.fighters(h1, 5)) == {6} and "mode" not in st5 and st5["total"] == 30,
        (st5.get("total"), [r["attacks"] for r in GW.fighters(h1, 5)]))
    chk("  맞대결 판은 없다 (match_mode False)", GW.match_mode() is False)


# ---------------------------------------------------------------- 8. 검토 (11/12) 에서 나온 것
def review_part():
    print("\n=== 8. 검토에서 나온 것 ===")
    season.SEASON = 6
    s = 6
    wipe()
    gs = [mkguild("검%d" % i, 5) for i in range(4)]
    clock(at(hours=1))
    for gid, ids in gs:
        GW.apply(ids[0])
    t = at(days=3, hours=1)
    clock(t)
    GW._lock(t)
    plan = GM._plan(s)
    # 짜임을 적은 뒤 줄을 넣다가 끊긴 셈: 줄 · 끝 표시를 지우고, 그사이 한 사람의 방어팀이 약해진다
    db.run("DELETE FROM guild_war_pair WHERE season=?", (s,))
    db.run("DELETE FROM meta WHERE k=?", ("gw:%d:locked" % s,))
    db.run("UPDATE guild_war_team SET def_team=? WHERE season=? AND user_id=?", (json.dumps([]), s, gs[0][1][0]))
    GW._lock(t)
    ps = dict((g, GM.pair_of(g, s)) for g, _ids in gs)
    chk("끊긴 뒤 팀이 바뀌어도 적어 둔 짜임 그대로 (모든 길드가 한 길드에게만 맞는다) - 검토 1",
        all(ps.values()) and sorted(p["from_guild"] for p in ps.values()) == sorted(g for g, _ids in gs)
        and GM._plan(s) == plan and len(plan) == 2, dict((g, dict(p) if p else None) for g, p in ps.items()))
    chk("  상대 발표 채팅은 길드마다 한 번", all(sum(1 for x in chat(g) if "상대가 정해졌습니다" in x) == 1 for g, _i in gs))
    (g1, A) = gs[0]
    g2 = ps[g1]["target_guild"]
    B = [ids for g, ids in gs if g == g2][0]
    GM.set_joker(B[0], B[1], True)
    GM.set_joker(B[0], B[3], True)
    foes = GM.match_view(A[0])["foes"]
    chk("가려진 조커는 명단 맨 끝 (번호 차례 사이에 안 낀다) - 검토 2",
        [f["hidden"] for f in foes] == [False, False, False, True, True], [f["hidden"] for f in foes])
    t = at(days=7, hours=1)
    clock(t)
    GW._lock(t)
    out = GM.attack(A[0], B[0])                              # 판 하나를 열어 둔 채 찔러 본다
    c1, c2 = code_of(lambda: GM.attack(A[0], B[1])), code_of(lambda: GM.attack(A[0], A[2]))
    chk("  판이 열린 채: 조커 번호 · 명단 밖 번호가 같은 글 - 검토 2", c1 == c2 and "끝나지 않은 승부" in c1[1], (c1, c2))
    gym_routes.act(out["id"], gym_routes.ActIn(kind="forfeit"), ctx=me(A[0]))
    c1, c2 = code_of(lambda: GM.attack(A[0], B[1])), code_of(lambda: GM.attack(A[0], 999999))
    chk("  조커의 진짜 번호는 명단 밖과 같은 글 (출전 명단이 아니다)", c1 == c2 and "출전 명단이 아니다" in c1[1], (c1, c2))
    c = code_of(lambda: GM.attack(A[0], -3))
    chk("  없는 자리 표시는 '다시 불러와 주세요' (엉뚱한 사람을 안 친다) - 검토 3", c and c[0] == 409
        and "다시 불러와" in c[1], c)
    c = code_of(lambda: GM.attack(A[0], 10 ** 30))
    chk("  아주 큰 번호는 400 (500 이 아니다) - 검토 6", c and c[0] == 400, c)
    h = [f for f in GM.match_view(A[0])["foes"] if f["hidden"]][0]["userId"]
    GM.attack(A[0], h)
    a = last_attack(A[0])
    chk("  자리 표시로 친 사람은 조커", a["def_user"] in (B[1], B[3]), dict(a))
    gym_routes.act(a["battle_id"], gym_routes.ActIn(kind="forfeit"), ctx=me(A[0]))
    c = code_of(lambda: GM.attack(A[1], h))
    chk("  한 번 붙어 본 조커의 옛 자리 표시는 '다시 불러와 주세요'", c and c[0] == 409 and "다시 불러와" in c[1], c)
    c1, c2 = code_of(lambda: GM.attack(A[0], B[3])), code_of(lambda: GM.attack(A[0], 999999))
    chk("  공격을 다 쓴 뒤: 조커 · 명단 밖이 같은 글 (공격 횟수를 다 썼다) - 검토 2", c1 == c2 and "다 썼다" in c1[1],
        (c1, c2))
    r = [x for x in GW.scores(s) if x["guildId"] == g1][0]
    chk("성적 줄에 우리를 친 길드 이름(from) - 검토 8", r.get("from") == GM._gname(ps[g1]["from_guild"], s), r)
    st = GW.state(A[0])
    chk("  맞대결 목록: 짝 둘 · 우리 판이 맨 위 · 1:1 이면 from = vs", len(st["matches"]) == 2 and st["matches"][0]["ours"]
        and not st["matches"][1]["ours"]
        and all(x["from"] == x["vs"] for m in st["matches"] for x in m["guilds"]), st["matches"])


def main():
    db.init()
    real = season.SEASON
    try:
        pure_part()
        pair_part()
        tri_part()
        review_part()
    finally:
        season.SEASON = real
    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
