# -*- coding: utf-8 -*-
"""길드전 결산 보상 개편 (2.0.2) - guild_war.py 의 TM_TICKET · TM_RANK · TM_ACTIVE_WINS · TM_ACTIVE · _tm_reward.

    .venv-server/bin/python server/test_gw_rewards.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 판은 두 개만 진짜로 둔다 (약한 길드를 이긴 판 하나 · 바로 기권한
판 하나). 나머지 공격은 guild_war_attack 줄을 바로 넣고, 순위는 칸을 옮겨 정해 둔다 (칸 수가 순위의 첫째 잣대).
못 박는 것:

  1. 시즌 5 결산: 순위마다(1 · 2 · 3 · 그 밖) 공격에서 **이긴** 사람은 랜덤 기술머신 뽑기권(RANKTICKETTM) 선물
     (kind item)을 TM_RANK 장수만큼. 이긴 판이 없는(기권 · 진 판만) 사람은 뽑기권 0 - 코인 · 꾸미기는 받는다.
     공격 안 한 사람은 아무것도 없다.
  2. 공격에서 TM_ACTIVE_WINS 번 이상 이기면 순위와 상관없이 TM_ACTIVE 장 더 (그 밖 순위도). 하나 모자라면 없다.
     더 많이 이겨도 TM_ACTIVE 장.
  3. 한 사람에게 뽑기권 선물은 **한 줄** (순위 몫 + 활약 몫을 합쳐) · 제목은 칭호 선물(GIFT_TITLE)과 다르다.
  4. 결산을 두 번 돌려도 한 번 · 끝 표시를 지우고 다시 돌아도(도중에 끊긴 셈) 사람마다 한 번.
  5. 선물을 받으면(items.gift_claim) 가방에 그 장수가 들어간다.
  6. 순위 묶음을 이미 **다** 가진 사람은 꾸미기로 참가 묶음 선택권(PICK) · 일부만 가졌으면 묶음 그대로.
  7. 결산 채팅에 뽑기권 안내 (순위 몫 · 활약 몫).
  8. state() 의 rewards[i].deco · tm 과 tmActive (시즌 5). 안내서(docs/guide)의 수와 같다.
  9. 시즌 4: state() 에 그 칸이 없고 (rank · coins 만, tmActive None) 뽑기권 선물도 꾸미기도 없다 - 코인은 그대로.
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

TMP = tempfile.mkdtemp(prefix="poket-gwrew-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, deco, deps, guild, guild_war as GW, gym_routes, items, season   # noqa: E402
from common import deco as C                                  # noqa: E402
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


def mkguild(name, n=5, species="GARCHOMP", level=60):
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
    # 관장 배틀 쪽 시계도 같이 (test_guild_war 의 날짜 폭탄 - 진짜 날짜가 검사 속 전쟁 기간을 지나면 판이 곧바로 접힌다)
    GW._now = lambda: t
    gym_routes._now = lambda: t


def wipe():
    for t in ("guild_war_attack", "guild_war_tile", "guild_war_team", "guild_war_entry", "gym_battle",
              "guild_member", "guild", "guild_user", "guild_chat", "gift", "deco_owned"):
        db.run("DELETE FROM %s" % t)
    db.run("DELETE FROM meta WHERE k LIKE 'gw:%'")


def me(uid):
    return {"user": {"id": uid}}


def fight(uid, region, win=True):
    """그 칸에 승부를 걸고 끝까지 둔다. win 이면 가장 아픈 기술로 싸우고, 아니면 바로 기권한다."""
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


def hit(uid, gid, dgid, res, n=1):
    """공격 줄을 바로 넣는다 (끝난 판). 칸은 상대 길드의 아무 칸 - 칸이 넘어가지는 않는다 (_finish 를 안 거친다)."""
    s = season.SEASON
    region = db.q1("SELECT region FROM guild_war_tile WHERE season=? AND guild_id=? ORDER BY region LIMIT 1",
                   (s, dgid))["region"]
    when = GW._iso(at(days=8))
    for _ in range(n):
        db.run("INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild,"
               " def_name, result, took, created_at, ended_at) VALUES (?,?,?,?,?,0,?,?,?,0,?,?)",
               (s, region, uid, gid, NAMES[uid], dgid, "AI 수비대", res, when, when))


def move_tiles(src, give):
    """src 길드의 칸을 다른 길드들에게 옮겨 순위를 정해 둔다. give = {길드: 칸 수}."""
    s = season.SEASON
    pool = [r["region"] for r in db.q("SELECT region FROM guild_war_tile WHERE season=? AND guild_id=?"
                                      " ORDER BY region", (s, src))]
    for gid, k in give.items():
        for _ in range(k):
            db.run("UPDATE guild_war_tile SET guild_id=?, taken_at=? WHERE season=? AND region=?",
                   (gid, GW._iso(at(days=9)), s, pool.pop()))


def wins_of(uid):
    return db.q1("SELECT COUNT(*) n FROM guild_war_attack WHERE season=? AND atk_user=? AND result='win'",
                 (season.SEASON, uid))["n"]


def attacked(uid):
    return bool(db.q1("SELECT 1 FROM guild_war_attack WHERE season=? AND atk_user=?", (season.SEASON, uid)))


def tm_rows(uid):
    return db.q("SELECT * FROM gift WHERE user_id=? AND kind='item' AND item_id=?", (uid, GW.TM_TICKET))


def tm_of(uid):
    return sum(int(r["count"]) for r in tm_rows(uid))


def deco_rows(uid):
    return db.q("SELECT * FROM gift WHERE user_id=? AND kind='deco'", (uid,))


def deco_of(uid):
    rows = deco_rows(uid)
    return rows[0]["item_id"] if len(rows) == 1 else [r["item_id"] for r in rows]


def want_tm(rank, wins):
    """그 순위 · 승수면 받아야 할 뽑기권 장수 (규칙을 이 검사에서 따로 적은 것)."""
    if not wins:
        return 0
    return GW.TM_RANK.get(rank, 0) + (GW.TM_ACTIVE if wins >= GW.TM_ACTIVE_WINS else 0)


def end_chat(gid):
    r = db.q1("SELECT body FROM guild_chat WHERE guild_id=? AND body LIKE '길드전이 끝났습니다%' ORDER BY id DESC LIMIT 1",
              (gid,))
    return r["body"] if r else ""


def counts():
    """다시 돌렸을 때 안 바뀌어야 할 것들."""
    return (db.q1("SELECT COUNT(*) n FROM gift")["n"],
            db.q1("SELECT COALESCE(SUM(count), 0) n FROM gift WHERE item_id=?", (GW.TM_TICKET,))["n"],
            db.q1("SELECT COALESCE(SUM(coin), 0) n FROM guild_user")["n"],
            db.q1("SELECT COUNT(*) n FROM guild_chat WHERE body LIKE '길드전이 끝났습니다%'")["n"])


# 화면(client/test_gw_reward_line.py)이 받는 꼴과 같다 - 서버가 바뀌면 둘 다 고친다
V5_REWARDS = [{"rank": 1, "coins": 300, "deco": "금관 · 금빛 별가루 · 발밑 빛", "tm": 2},
              {"rank": 2, "coins": 200, "deco": "은관 · 은빛 별가루", "tm": 1},
              {"rank": 3, "coins": 150, "deco": "동관 · 동빛 별가루", "tm": 1},
              {"rank": None, "coins": 50, "deco": "참가 묶음 선택권", "tm": 0}]
V4_REWARDS = [{"rank": 1, "coins": 300}, {"rank": 2, "coins": 200}, {"rank": 3, "coins": 150},
              {"rank": None, "coins": 50}]


# ---------------------------------------------------------------- 규칙의 수
def rules_part():
    print("=== 규칙의 수 · 도구 · 안내서 ===")
    chk("순위 몫 1위 2 · 2위 1 · 3위 1, 활약 = 3승 이상 1장 (사용자 결정 2.0.2)",
        (GW.TM_RANK, GW.TM_ACTIVE_WINS, GW.TM_ACTIVE) == ({1: 2, 2: 1, 3: 1}, 3, 1),
        (GW.TM_RANK, GW.TM_ACTIVE_WINS, GW.TM_ACTIVE))
    it = items.get(GW.TM_TICKET) or {}
    chk("주는 것은 **랜덤** 뽑기권 (타입 확정은 랭크 챔피언 것으로 남긴다)", GW.TM_TICKET == "RANKTICKETTM"
        and (it.get("effect") or {}).get("kind") == "tmticket" and not it["effect"].get("pickType")
        and it.get("kr") == "랜덤 기술머신 뽑기권", it)
    chk("  팔 수 없고 상점에 없다 (돈벌이가 안 된다)", items.sell_price(GW.TM_TICKET) <= 0
        and not it.get("buyable") and it.get("custom") is True, it)
    with open(os.path.join(ROOT, "docs", "guide", "index.html"), encoding="utf-8") as f:
        guide = f.read()
    rank_txt = "1위 길드 %d장 · 2위 %d장 · 3위 %d장" % (GW.TM_RANK[1], GW.TM_RANK[2], GW.TM_RANK[3])
    act_txt = "%d번 이상 이기면 활약 보상으로 %d장" % (GW.TM_ACTIVE_WINS, GW.TM_ACTIVE)
    chk("안내서의 수가 서버와 같다 ('%s' · '%s')" % (rank_txt, act_txt), rank_txt in guide and act_txt in guide)
    chk("  안내서: 이긴 길드원만 받는다 · 다 가진 묶음은 선택권", "한 번이라도 이긴 길드원만" in guide
        and "순위 묶음을 이미 다 가진 사람" in guide)
    chk("tm_text: 1위는 순위 몫 + 활약 몫, 그 밖은 활약 몫만",
        "뽑기권 2장도" in GW.tm_text(1) and "활약 보상으로 1장" in GW.tm_text(1)
        and "장도 드립니다" not in GW.tm_text(4) and "활약 보상으로 랜덤 기술머신 뽑기권 1장을" in GW.tm_text(4)
        and "더" not in GW.tm_text(4),
        (GW.tm_text(1), GW.tm_text(4)))


# ---------------------------------------------------------------- 시즌 5 결산
def v5_part():
    print("\n=== 시즌 5: 준비 (다섯 길드, 진짜 판 둘 + 넣은 공격 줄) ===")
    season.SEASON = 5
    s = season.SEASON
    wipe()
    g1, A = mkguild("일길드", 5)
    g2, B = mkguild("이길드", 5)
    g3, Q = mkguild("삼길드", 5)
    g4, D = mkguild("사길드", 5)
    g5, E = mkguild("오길드", 5, species="MAGIKARP", level=5)      # 약한 길드 - 진짜 판 하나를 반드시 이기게
    gids = (g1, g2, g3, g4, g5)
    clock(at(hours=1))
    for gid, ids in ((g1, A), (g2, B), (g3, Q), (g4, D), (g5, E)):
        GW.apply(ids[0])
    GW._mark("gw:%d:order" % s, json.dumps([g1, g5, g2, g3, g4]))   # 이웃 차례 - 일길드 옆에 오길드
    clock(at(days=3, hours=1))
    GW._lock(at(days=3, hours=1))
    chk("다섯 길드가 15칸씩", GW.tile_counts() == dict((g, 15) for g in gids), GW.tile_counts())
    clock(at(days=7, hours=1))
    GW._lock(at(days=7, hours=1))

    # 진짜 판 1: 일길드 A[0] 이 오길드 칸을 이긴다 (AI 수비대 칸이면 오길드 사람의 잉어킹 팀으로 바꿔 둔다)
    land5 = set(r["region"] for r in GW.tiles(s) if r["guild_id"] == g5)
    target = [h for h in GW.map_view(A[0])["hit"] if h in land5][0]
    t = GW.tile(target, s)
    if t["guard_user"] == GW.AI_GUARD:
        weak = db.q1("SELECT def_team FROM guild_war_team WHERE season=? AND user_id=?", (s, E[0]))["def_team"]
        db.run("UPDATE guild_war_tile SET ai_team=? WHERE season=? AND region=?", (weak, s, target))
    fight(A[0], target, win=True)
    chk("진짜 판: A[0] 이 이겼다 (result=win 줄)", (last_attack(A[0]) or {})["result"] == "win", dict(last_attack(A[0])))
    # 진짜 판 2: A[2] 는 판 하나를 열고 바로 기권 - '공격한 사람' 이지만 이긴 판은 없다
    fight(A[2], GW.map_view(A[2])["hit"][0], win=False)
    chk("진짜 판: A[2] 는 기권 (result=lose 줄)", (last_attack(A[2]) or {})["result"] == "lose", dict(last_attack(A[2])))

    # 넣는 공격 줄
    #   일길드(1위)  A0 진짜 1승 · A1 3승 · A2 기권만 · A3 공격 안 함 · A4 2승 1패 (1위 묶음을 이미 다 가졌다)
    #   이길드(2위)  B0 1승 · B1 3승 · B2 패만
    #   삼길드(3위)  Q0 1승 · Q1 패만 (3위 묶음을 다 가졌다) · Q2 1승 (동관만 가졌다)
    #   사길드(4위)  D0 1승 · D1 3승 · D2 5승
    #   오길드(5위)  E0 패만 · E1 3승
    hit(A[1], g1, g5, "win", 3)
    hit(A[4], g1, g5, "win", 2)
    hit(A[4], g1, g5, "lose")
    hit(B[0], g2, g3, "win")
    hit(B[1], g2, g3, "win", 3)
    hit(B[2], g2, g3, "lose")
    hit(Q[0], g3, g4, "win")
    hit(Q[1], g3, g4, "lose")
    hit(Q[2], g3, g4, "win")
    hit(D[0], g4, g1, "win")
    hit(D[1], g4, g1, "win", 3)
    hit(D[2], g4, g1, "win", 5)
    hit(E[0], g5, g1, "lose")
    hit(E[1], g5, g2, "win", 3)
    deco.grant(A[4], "bundle:rank1", s)
    deco.grant(Q[1], "bundle:rank3", s)
    deco.grant(Q[2], "crown_bronze", s)
    move_tiles(g5, {g1: 4, g2: 2, g3: 1})                          # 19 · 17 · 16 · 15 · 8칸
    rank_of = dict((r["guildId"], r["rank"]) for r in GW.scores(s))
    chk("순위는 칸 수대로 1 · 2 · 3 · 4 · 5", [rank_of[g] for g in gids] == [1, 2, 3, 4, 5], rank_of)

    st = GW.state(A[0])
    chk("state(): rewards 에 deco · tm (시즌 5)", st["rewards"] == V5_REWARDS, st["rewards"])
    chk("  tmActive = {wins: 3, count: 1}", st["tmActive"] == {"wins": GW.TM_ACTIVE_WINS, "count": GW.TM_ACTIVE},
        st.get("tmActive"))
    chk("  deco 글은 DECO_RANK_KR · 그 밖은 PICK 이름과 같다",
        [r["deco"] for r in st["rewards"]] == [GW.DECO_RANK_KR[1], GW.DECO_RANK_KR[2], GW.DECO_RANK_KR[3], C.PICK_KR])

    people = [(g, u) for g, ids in ((g1, A), (g2, B), (g3, Q), (g4, D), (g5, E)) for u in ids]
    coin0 = dict((u, guild.coin(u)) for _g, u in people)
    end = at(days=13, hours=1)
    clock(end)
    db.run("DELETE FROM gift")
    chk("결산이 돈다", GW.settle(end) is True)

    print("\n=== 시즌 5: 뽑기권 (순위 몫 + 활약 몫) ===")
    bad = []
    for g, u in people:
        r = rank_of[g]
        want_c = GW.coins_for(r) if attacked(u) else 0
        if tm_of(u) != want_tm(r, wins_of(u)) or guild.coin(u) - coin0[u] != want_c:
            bad.append((NAMES[u], r, wins_of(u), tm_of(u), guild.coin(u) - coin0[u]))
    chk("모든 사람: 뽑기권 = 순위 몫(이겼으면) + 활약 몫(3승 이상), 코인 = 순위 코인(공격했으면)", not bad, bad)
    chk("1위 A0 (진짜 판 1승) = 2장", tm_of(A[0]) == 2, tm_of(A[0]))
    chk("1위 A1 (3승) = 2 + 활약 1 = 3장", tm_of(A[1]) == 3, tm_of(A[1]))
    chk("1위 A4 (2승 1패 - 활약에 하나 모자람) = 2장", tm_of(A[4]) == 2, tm_of(A[4]))
    chk("1위 A2 (기권만): 뽑기권 없음 · 코인 300 · 꾸미기 1위 묶음 · 칭호",
        tm_rows(A[2]) == [] and guild.coin(A[2]) - coin0[A[2]] == 300 and deco_of(A[2]) == "bundle:rank1"
        and db.q1("SELECT 1 FROM gift WHERE user_id=? AND kind='title'", (A[2],)) is not None,
        (tm_of(A[2]), guild.coin(A[2]) - coin0[A[2]], deco_of(A[2])))
    chk("1위 A3 (공격 안 함): 선물 · 코인 아무것도 없다",
        db.q("SELECT * FROM gift WHERE user_id=?", (A[3],)) == [] and guild.coin(A[3]) == coin0[A[3]])
    chk("2위 B0 1승 = 1장 · B1 3승 = 2장 · B2 패만 = 0 (코인 200)",
        (tm_of(B[0]), tm_of(B[1]), tm_of(B[2])) == (1, 2, 0) and guild.coin(B[2]) - coin0[B[2]] == 200,
        (tm_of(B[0]), tm_of(B[1]), tm_of(B[2])))
    chk("3위 Q0 1승 = 1장 · Q2 1승 = 1장 · Q1 패만 = 0", (tm_of(Q[0]), tm_of(Q[2]), tm_of(Q[1])) == (1, 1, 0),
        (tm_of(Q[0]), tm_of(Q[2]), tm_of(Q[1])))
    chk("그 밖(4위) D0 1승 = 줄 없음 (순위 몫 0)", tm_rows(D[0]) == [], tm_of(D[0]))
    chk("그 밖(4위) D1 3승 = 활약 1장 · D2 5승도 1장", (tm_of(D[1]), tm_of(D[2])) == (1, 1), (tm_of(D[1]), tm_of(D[2])))
    chk("그 밖(5위) E1 3승 = 1장 · E0 패만 = 0 (코인 50)", tm_of(E[1]) == 1 and tm_rows(E[0]) == []
        and guild.coin(E[0]) - coin0[E[0]] == 50, (tm_of(E[1]), tm_of(E[0])))

    print("\n=== 시즌 5: 선물 줄 ===")
    many = [(NAMES[u], len(tm_rows(u))) for _g, u in people if len(tm_rows(u)) > 1]
    chk("한 사람에게 뽑기권 선물은 한 줄 (순위 몫 + 활약 몫을 합쳐서)", not many and len(tm_rows(A[1])) == 1
        and tm_rows(A[1])[0]["count"] == 3, many)
    tm_all = db.q("SELECT * FROM gift WHERE item_id=?", (GW.TM_TICKET,))
    chk("  뽑기권 줄은 kind item · 제목은 칭호 선물(GIFT_TITLE)과 다르다", tm_all and all(
        r["kind"] == "item" and r["title"] != GW.GIFT_TITLE % s and "기술머신" in r["title"] for r in tm_all),
        sorted(set((r["kind"], r["title"]) for r in tm_all)))
    titled = db.q("SELECT user_id, kind FROM gift WHERE title=?", (GW.GIFT_TITLE % s,))
    chk("  GIFT_TITLE 제목은 칭호 줄뿐 - 1위 길드의 공격한 사람 (A0 · A1 · A2 · A4)",
        all(r["kind"] == "title" for r in titled) and set(r["user_id"] for r in titled) == {A[0], A[1], A[2], A[4]},
        [(NAMES[r["user_id"]], r["kind"]) for r in titled])
    msg = tm_rows(A[1])[0]["message"]
    chk("  글: 장수 · 순위 몫 · 활약 몫", "뽑기권 3장" in msg and "1위 보상 2장" in msg
        and "활약 보상(공격 3승 이상) 1장" in msg and "[일길드]" in msg, msg)
    msg = tm_rows(D[1])[0]["message"]
    chk("  그 밖 순위의 글은 활약 몫만", "뽑기권 1장" in msg and "활약 보상" in msg and "위 보상" not in msg, msg)

    print("\n=== 시즌 5: 꾸미기 (다 가진 묶음은 선택권) ===")
    chk("1위 A4: 1위 묶음을 이미 다 가졌다 -> 참가 묶음 선택권", deco_of(A[4]) == C.PICK
        and "이미 다 가지고" in deco_rows(A[4])[0]["message"], (deco_of(A[4]), deco_rows(A[4])))
    chk("3위 Q1: 3위 묶음을 다 가졌다 (진 판만이어도) -> 선택권", deco_of(Q[1]) == C.PICK, deco_of(Q[1]))
    chk("3위 Q2: 동관만 가졌다 -> 묶음 그대로", deco_of(Q[2]) == "bundle:rank3", deco_of(Q[2]))
    chk("그 밖은 원래대로 선택권, 1 · 2위의 다른 사람은 그 묶음",
        all(deco_of(u) == C.PICK for u in D[:3] + E[:2]) and deco_of(A[0]) == deco_of(A[1]) == "bundle:rank1"
        and all(deco_of(u) == "bundle:rank2" for u in B[:3]) and deco_of(Q[0]) == "bundle:rank3",
        [(NAMES[u], deco_of(u)) for u in A + B + Q + D + E])
    chk("  공격 안 한 사람은 꾸미기도 없다", all(deco_rows(u) == [] for u in (A[3], B[3], B[4], Q[3], D[3], E[2])))

    print("\n=== 시즌 5: 결산 채팅 ===")
    body1, body2, body4 = end_chat(g1), end_chat(g2), end_chat(g4)
    chk("1위 길드: 뽑기권 2장 + 활약 안내", "랜덤 기술머신 뽑기권 2장도" in body1 and "활약 보상으로 1장" in body1
        and body1.endswith(GW.tm_text(1)), body1)
    chk("2위 길드: 뽑기권 1장", "뽑기권 1장도" in body2 and body2.endswith(GW.tm_text(2)), body2)
    chk("그 밖 길드: 활약 안내만", "장도 드립니다" not in body4 and "활약 보상으로 랜덤 기술머신 뽑기권 1장을" in body4
        and body4.endswith(GW.tm_text(4)), body4)
    chk("  칭호 바꾸는 곳은 마이페이지", "마이페이지" in db.q1(
        "SELECT message FROM gift WHERE user_id=? AND kind='title'", (A[0],))["message"])

    print("\n=== 시즌 5: 다시 돌려도 한 번 ===")
    before = counts()
    chk("두 번째 결산은 안 돈다", GW.settle(end) is False and counts() == before, (before, counts()))
    db.run("DELETE FROM meta WHERE k=?", ("gw:%d:settled" % s,))
    GW.settle(end)
    chk("  끝 표시를 지우고 다시 돌아도(도중에 끊긴 셈) 사람마다 한 번", counts() == before, (before, counts()))
    GW.state(A[0])
    chk("  화면을 열어도(state 가 settle 을 부른다) 그대로", counts() == before)

    print("\n=== 시즌 5: 선물을 받으면 가방에 ===")
    got = items.gift_claim(A[1])
    tm_got = [x for x in got if x["kind"] == "item" and x["item"] == GW.TM_TICKET]
    chk("A1 이 받으면 뽑기권 3장이 가방에", items.bag_count(A[1], GW.TM_TICKET) == 3 and len(tm_got) == 1
        and tm_got[0]["count"] == 3 and tm_got[0]["name"] == "랜덤 기술머신 뽑기권"
        and "기술머신" in tm_got[0]["title"], (items.bag_count(A[1], GW.TM_TICKET), got))
    chk("  칭호 · 꾸미기도 같이 받는다", {"title", "deco", "item"} <= set(x["kind"] for x in got)
        and {"crown_gold", "fx_stars_gold", "fx_glow"} <= set(deco.owned(A[1])), [x["kind"] for x in got])
    items.gift_claim(A[4])
    chk("A4 는 뽑기권 2장 + 선택권 하나", items.bag_count(A[4], GW.TM_TICKET) == 2
        and deco.owned(A[4]).get(C.PICK) == 1, (items.bag_count(A[4], GW.TM_TICKET), deco.owned(A[4])))
    items.gift_claim(Q[2])
    chk("Q2 는 뽑기권 1장 + 3위 묶음 (동관 · 동빛 별가루)", items.bag_count(Q[2], GW.TM_TICKET) == 1
        and {"crown_bronze", "fx_stars_bronze"} <= set(deco.owned(Q[2])), deco.owned(Q[2]))
    items.gift_claim(D[0])
    chk("D0 (그 밖 1승) 은 가방에 뽑기권이 없다", items.bag_count(D[0], GW.TM_TICKET) == 0)
    chk("  다시 받으면 없다", items.gift_claim(A[1]) == [] and items.bag_count(A[1], GW.TM_TICKET) == 3)


# ---------------------------------------------------------------- 시즌 4
def v4_part():
    print("\n=== 시즌 4: 뽑기권 · 꾸미기 없음, 화면 칸도 없음 ===")
    season.SEASON = 4
    s = season.SEASON
    wipe()
    h1, X = mkguild("사시즌가", 5)
    h2, Y = mkguild("사시즌나", 5)
    clock(at(hours=1))
    GW.apply(X[0])
    GW.apply(Y[0])
    clock(at(days=3, hours=1))
    GW._lock(at(days=3, hours=1))
    clock(at(days=7, hours=1))
    GW._lock(at(days=7, hours=1))
    hit(X[0], h1, h2, "win", 3)
    hit(X[1], h1, h2, "lose")
    hit(Y[0], h2, h1, "win", 4)
    move_tiles(h2, {h1: 1})
    st = GW.state(X[0])
    chk("state(): rewards 는 rank · coins 만 (옛 꼴)", st["rewards"] == V4_REWARDS, st["rewards"])
    chk("  tmActive 는 None", "tmActive" in st and st["tmActive"] is None, st.get("tmActive"))
    coin0 = dict((u, guild.coin(u)) for u in X + Y)
    end = at(days=13, hours=1)
    clock(end)
    db.run("DELETE FROM gift")
    GW.settle(end)
    rank_of = dict((r["guildId"], r["rank"]) for r in GW.scores(s))
    chk("순위 (칸 16 · 14)", (rank_of[h1], rank_of[h2]) == (1, 2), rank_of)
    chk("뽑기권 선물이 없다 (3승 · 4승이어도)",
        db.q1("SELECT COUNT(*) n FROM gift WHERE item_id=?", (GW.TM_TICKET,))["n"] == 0)
    chk("  꾸미기 선물도 없다", db.q1("SELECT COUNT(*) n FROM gift WHERE kind='deco'")["n"] == 0)
    chk("  코인은 그대로 (1위 300 · 2위 200, 공격한 사람만)",
        (guild.coin(X[0]) - coin0[X[0]], guild.coin(X[1]) - coin0[X[1]], guild.coin(Y[0]) - coin0[Y[0]],
         guild.coin(X[2]) - coin0[X[2]]) == (300, 300, 200, 0),
        [guild.coin(u) - coin0[u] for u in (X[0], X[1], Y[0], X[2])])
    chk("  1위 칭호는 그대로", set(r["user_id"] for r in db.q("SELECT user_id FROM gift WHERE kind='title'"))
        == {X[0], X[1]})
    chk("  결산 채팅에 뽑기권 · 꾸미기 얘기가 없다", end_chat(h1) and "뽑기권" not in end_chat(h1)
        and "꾸미기" not in end_chat(h1) and "뽑기권" not in end_chat(h2), end_chat(h1))
    st = GW.state(X[0])
    chk("  끝난 뒤의 state() 도 옛 꼴", st["phase"] == "done" and st["rewards"] == V4_REWARDS
        and st["tmActive"] is None, (st["phase"], st["rewards"]))


def main():
    db.init()
    real = season.SEASON
    try:
        rules_part()
        v5_part()
        v4_part()
    finally:
        season.SEASON = real
    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
