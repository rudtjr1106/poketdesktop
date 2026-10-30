# -*- coding: utf-8 -*-
"""꾸미기 (버전 2) 서버 검사 - 위치 점 · 가진 것 · 끼우기 · 선물 · 길드전 순위 보상.

    python server/test_deco.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다 (길드전 도우미는 test_guild_war_v5 의 것을 빌린다).

  1. 위치 점 (walkpts): Offsets 그림의 검정 = 머리, 초록 = 몸 가운데, 없는 칸은 null. 칸보다 작으면 ValueError.
  2. meta 에 싣기 (main._put_points · _backfill_points): 받으면 pts=1, 404 면 pts=0 (다시 안 묻는다),
     끊기면 아무것도 안 적고 한동안 다시 안 묻는다. 옛 meta 는 시트를 다시 안 받고 점만 붙여 파일에 적는다.
     색만 입힌 이로치는 보통 meta 의 점을 그대로 쓴다.
  3. 가진 것 (deco.grant · pick): 묶음 · 하나 · 선택권. 장식은 겹쳐 안 쌓이고 선택권만 쌓인다. 선택권으로 참가 묶음만
     고를 수 있고, 없으면 409.
  4. 끼우기 (deco.equip): 모르는 것 404 · 남의 포켓몬 404 · 안 가진 것 409. **장식 하나는 한 마리만** - 다른 포켓몬에
     끼우면 먼저 쓰던 포켓몬에서 빠진다. 같은 칸은 바꿔 낀다. 빼기. 포켓몬 응답 · 놀러 가기 파티에 deco 가 실린다.
  5. 선물 (items.gift_claim kind 'deco'): 묶음 · 선택권을 지급하고 이름을 준다. 모르는 것은 안 준다.
  6. 길드전 결산 (시즌 5): 1 · 2 · 3위 길드의 공격한 사람에게 순위 묶음, 그 밖의 길드는 선택권 - 선물함으로 한 번만.
     공격 안 한 사람은 없다. 시즌 4 에는 꾸미기를 안 준다.
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import test_guild_war_v5 as T5                                 # noqa: E402  (임시 DB · 길드 도우미)

from fastapi import HTTPException                              # noqa: E402

from app import db, deco, guild_war as GW, items, main, pngmini, season, visit, walkpts  # noqa: E402
from common import deco as C                                   # noqa: E402

OK = FAIL = 0


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


# ---------------------------------------------------------------- 1 · 2. 위치 점
FW, FH = 8, 6


def offsets_png(missing_head=()):
    """2행 x 3칸. 칸 (r, c) 의 머리 = (c + 1, r + 1), 몸 가운데 = (4, 3 + r). missing_head 의 칸은 머리가 없다."""
    w, h = FW * 3, FH * 2
    rows = [bytearray(w * 4) for _ in range(h)]

    def put(x, y, rgb):
        rows[y][x * 4:x * 4 + 4] = bytes(rgb) + b"\xff"
    for r in range(2):
        for c in range(3):
            if (r, c) not in missing_head:
                put(c * FW + c + 1, r * FH + r + 1, (0, 0, 0))
            put(c * FW + 4, r * FH + 3 + r, (0, 255, 0))
            put(c * FW + 6, r * FH + 1, (255, 0, 0))            # 손 - 안 쓴다
    return pngmini.write_rgba(w, h, rows)


def points_part():
    print("\n=== 1. 위치 점 (walkpts) ===")
    got = walkpts.points(offsets_png(missing_head={(1, 2)}), FW, FH)
    chk("머리 = 검정 점 (칸 안 좌표)", got["head"][0] == [[1, 1], [2, 1], [3, 1]] and got["head"][1][:2] == [[1, 2], [2, 2]],
        got["head"])
    chk("  없는 칸은 null", got["head"][1][2] is None, got["head"][1])
    chk("몸 가운데 = 초록 점", got["center"][1] == [[4, 4], [4, 4], [4, 4]], got["center"])
    cut = walkpts.points(offsets_png(), FW, FH, rows=1, frames=2)
    chk("rows · frames 로 자른다", len(cut["head"]) == 1 and len(cut["head"][0]) == 2, cut)
    try:
        walkpts.points(offsets_png(), 40, 40)
        bad = None
    except ValueError as e:
        bad = e
    chk("칸보다 작은 그림이면 ValueError", bad is not None)

    print("\n=== 2. meta 에 싣기 (_put_points · _backfill_points) ===")
    m = {"frameW": FW, "frameH": FH}
    chk("받으면 pts=1 과 점", main._put_points(m, offsets_png) and m["pts"] == 1 and m["head"][0][0] == [1, 1], m)

    def gone():
        raise urllib.error.HTTPError("u", 404, "nf", None, None)

    def cut_off():
        raise urllib.error.URLError("끊김")
    m = {"frameW": FW, "frameH": FH}
    chk("Offsets 가 없으면(404) pts=0 - 다시 안 묻는다", main._put_points(m, gone) and m == dict(m, pts=0)
        and "head" not in m, m)
    m = {"frameW": FW, "frameH": FH}
    chk("끊기면 아무것도 안 적는다", main._put_points(m, cut_off) is False and "pts" not in m, m)

    # 옛 meta 에 점 붙이기 - GitHub 대신 가짜 urlopen
    xml = ("<AnimData><Anims><Anim><Name>Walk</Name><FrameWidth>%d</FrameWidth><FrameHeight>%d</FrameHeight>"
           "<Durations><Duration>8</Duration><Duration>8</Duration><Duration>8</Duration></Durations></Anim>"
           "<Anim><Name>Idle</Name><CopyOf>Walk</CopyOf></Anim></Anims></AnimData>" % (FW, FH)).encode()
    asked = []

    class Resp(object):
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=None):
        asked.append(url.rsplit("/", 1)[-1])
        if url.endswith("AnimData.xml"):
            return Resp(xml)
        if url.endswith("Walk-Offsets.png"):
            return Resp(offsets_png())
        raise urllib.error.HTTPError(url, 404, "nf", None, None)
    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        path = os.path.join(T5.TMP, "Idle.json")
        old = {"ok": True, "frameW": FW, "frameH": FH, "rows": 2, "durations": [8, 8, 8], "src": "pmd"}
        main._PTS_TRIED.clear()
        got = main._backfill_points(25, "Idle", False, dict(old), path)
        chk("옛 meta 에 점을 붙인다 (CopyOf 를 따라 Walk-Offsets)", got.get("pts") == 1 and got["head"][0][0] == [1, 1]
            and asked == ["AnimData.xml", "Walk-Offsets.png"], (asked, got.get("pts")))
        with open(path) as f:
            chk("  파일에 적는다 (시트 칸은 그대로)", json.load(f).get("pts") == 1)
        asked[:] = []
        xml_no = xml.replace(b"<Name>Idle</Name>", b"<Name>Sleep</Name>")
        xml_holder = [xml_no]

        def fake2(url, timeout=None):
            asked.append(url.rsplit("/", 1)[-1])
            if url.endswith("AnimData.xml"):
                return Resp(xml_holder[0])
            raise urllib.error.URLError("끊김")
        urllib.request.urlopen = fake2
        got = main._backfill_points(26, "Idle", False, dict(old), os.path.join(T5.TMP, "x.json"))
        chk("못 붙이면 그대로 돌려준다", "pts" not in got, got)
        n = len(asked)
        main._backfill_points(26, "Idle", False, dict(old), os.path.join(T5.TMP, "x.json"))
        chk("  한동안은 다시 안 묻는다 (GitHub 를 요청마다 두드리지 않게)", len(asked) == n, asked)
    finally:
        urllib.request.urlopen = real
    # 색만 입힌 이로치: 보통 meta 의 점을 쓴다
    real_meta = main._anim_meta
    main._anim_meta = lambda num, name, shiny=False: {"ok": True, "pts": 1, "head": [[[2, 2]]], "center": [[[3, 3]]]}
    try:
        main._PTS_TRIED.clear()
        got = main._backfill_points(27, "Walk", True, {"ok": True, "recolor": True, "src": "pmd"},
                                    os.path.join(T5.TMP, "s.json"))
    finally:
        main._anim_meta = real_meta
    chk("색만 입힌 이로치는 보통 meta 의 점을 쓴다", got.get("pts") == 1 and got["head"] == [[[2, 2]]], got)

    # 한꺼번에 둘까지만 GitHub 에 다녀온다 - 자리가 없으면 점 없이 바로
    main._PTS_TRIED.clear()
    main._PTS_SEM.acquire()
    main._PTS_SEM.acquire()
    try:
        asked[:] = []
        urllib.request.urlopen = fake_urlopen
        got = main._backfill_points(28, "Walk", False, dict(old), os.path.join(T5.TMP, "busy.json"))
    finally:
        urllib.request.urlopen = real
        main._PTS_SEM.release()
        main._PTS_SEM.release()
    chk("늦은 점 붙이기는 둘까지 - 자리가 없으면 안 묻고 점 없이 돌려준다 (다음에 다시)",
        not asked and "pts" not in got and (28, "Walk", False) not in main._PTS_TRIED, (asked, got))

    # 이로치 폴더에 Offsets 만 없으면 받아 둔 보통 meta 의 점을 빌린다
    main.WALK_DIR = os.path.join(T5.TMP, "walk")             # 임시 폴더에 (운영 경로 /data 를 안 건드린다)
    npath = main._anim_paths(29, "Walk")[1]
    os.makedirs(os.path.dirname(npath), exist_ok=True)
    with open(npath, "w") as f:
        json.dump(dict(old, pts=1, head=[[[5, 5]]], center=[[[6, 6]]]), f)
    m = dict(old, pts=0)
    chk("이로치 Offsets 가 없으면(404) 보통 meta 의 점을 빌린다", main._points_from_normal(29, "Walk", m)
        and m["pts"] == 1 and m["head"] == [[[5, 5]]], m)
    m = dict(old, frameW=FW + 1, pts=0)
    chk("  칸이 다르면 안 빌린다", not main._points_from_normal(29, "Walk", m) and m["pts"] == 0, m)


# ---------------------------------------------------------------- 3 · 4 · 5
def own_part():
    print("\n=== 3. 가진 것 (grant · pick) ===")
    u = T5.mkuser("꾸미기_가", "PIKACHU", 30)
    got = deco.grant(u, "bundle:rank1", 5)
    chk("묶음을 주면 셋 다 갖는다 (이름 목록)", got == ["금관", "금빛 별가루", "발밑 빛"]
        and set(deco.owned(u)) == {"crown_gold", "fx_stars_gold", "fx_glow"}, (got, deco.owned(u)))
    deco.grant(u, "bundle:rank1", 6)
    chk("  두 번 받아도 장식은 하나", deco.owned(u)["crown_gold"] == 1, deco.owned(u))
    chk("모르는 것은 안 준다", deco.grant(u, "bundle:없는것") == [] and deco.grant(u, "crown_rainbow") == [])
    deco.grant(u, C.PICK)
    deco.grant(u, C.PICK)
    chk("선택권은 쌓인다", deco.owned(u)[C.PICK] == 2, deco.owned(u))
    chk("순위 묶음은 선택권으로 못 고른다 (400)", code_of(lambda: deco.pick(u, "rank1")) == 400)
    got = deco.pick(u, "join_flower")
    chk("선택권으로 참가 묶음을 고른다", got == ["꽃핀", "꽃잎"] and deco.owned(u)[C.PICK] == 1
        and "flower" in deco.owned(u), (got, deco.owned(u)))
    deco.pick(u, "join_bow")
    chk("  다 쓰면 목록에서 빠진다", C.PICK not in deco.owned(u), deco.owned(u))
    chk("  없으면 409", code_of(lambda: deco.pick(u, "join_pearls")) == 409)
    st = deco.state(u)
    chk("창에 줄 것: 13개 · 가진 표시 · 선택권 0 · 고를 묶음 셋", len(st["items"]) == 13 and st["picks"] == 0
        and len(st["choices"]) == 3 and sum(1 for i in st["items"] if i["owned"]) == 7, st["picks"])

    print("\n=== 4. 끼우기 (equip) ===")
    p1, p2 = [r["id"] for r in db.q("SELECT id FROM pokemon WHERE user_id=? ORDER BY id", (u,))]
    other = T5.mkuser("꾸미기_나", "EEVEE", 30)
    op = db.q1("SELECT id FROM pokemon WHERE user_id=?", (other,))["id"]
    chk("모르는 꾸미기는 404", code_of(lambda: deco.equip(u, p1, "crown_rainbow")) == 404)
    chk("남의 포켓몬은 404", code_of(lambda: deco.equip(u, op, "crown_gold")) == 404)
    chk("안 가진 것은 409", code_of(lambda: deco.equip(u, p1, "pearls")) == 409)
    w = deco.equip(u, p1, "crown_gold")
    w = deco.equip(u, p1, "fx_stars_gold")
    chk("칸마다 하나씩 같이 쓴다", w == {"head": "crown_gold", "trail": "fx_stars_gold"}, w)
    w2 = deco.equip(u, p2, "crown_gold")
    chk("다른 포켓몬에 끼우면 먼저 쓰던 포켓몬에서 빠진다", w2 == {"head": "crown_gold"}
        and deco.equipped(u)[p1] == {"trail": "fx_stars_gold"}, deco.equipped(u))
    deco.equip(u, p1, "fx_paw")
    chk("같은 칸은 바꿔 낀다 (별가루 -> 발자국)", deco.equipped(u)[p1] == {"trail": "fx_paw"}, deco.equipped(u))
    chk("빼기", deco.equip(u, p1, "fx_paw", on=False) == {} and p1 not in deco.equipped(u), deco.equipped(u))
    chk("  끼우지 않은 것을 빼도 그대로", deco.equip(u, p1, "bow", on=False) == {})
    row = db.q1("SELECT * FROM pokemon WHERE id=?", (p2,))
    chk("포켓몬 응답에 deco 가 실린다", db._row_to_mon(row).get("deco") == {"head": "crown_gold"}, dict(row))
    db.run("UPDATE pokemon SET deco=? WHERE id=?", ("{망가짐", p1))
    chk("  망가진 칸은 빈 것으로", db._row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (p1,)))["deco"] == {})
    st = deco.state(u)
    chk("창에 줄 것: 누가 쓰나", dict((i["key"], i["wornBy"]) for i in st["items"])["crown_gold"] == p2
        and st["worn"] == {str(p2): {"head": "crown_gold"}}, st["worn"])
    party = visit._clean_party([{"id": p2, "num": 25, "deco": {"hair": "bow"}},
                                {"id": p1, "num": 25, "deco": {"head": "crown_gold", "aura": "fx_glow"}},
                                {"id": op, "num": 133, "deco": {"head": "crown_gold"}}], u)
    chk("놀러 가기 파티의 꾸미기는 보낸 값이 아니라 서버의 것 (안 쓴 것 · 남의 포켓몬은 없다)",
        [x.get("deco") for x in party] == [{"head": "crown_gold"}, None, None], party)
    chk("  주인을 모르면 꾸미기를 안 싣는다", "deco" not in visit._clean_party([{"id": p2, "num": 25,
                                                                          "deco": {"head": "crown_gold"}}])[0])
    chk("  놀러 간 포켓몬(손님)도 쓰고 간다", visit._public_mon(db._row_to_mon(row))["deco"] == {"head": "crown_gold"})
    chk("아주 큰 번호 · 0 · 글자는 404 (500 이 아니다)",
        [code_of(lambda v=v: deco.equip(u, v, "crown_gold")) for v in (2 ** 63, 0, "x")] == [404, 404, 404])

    # 동시에 끼우기: 같은 금관을 두 마리에 번갈아 - 끝나면 한 마리만 쓰고 있다
    import threading
    deco.grant(u, "bundle:rank3")
    errs = []

    def hammer(i):
        try:
            for j in range(15):
                deco.equip(u, (p1, p2)[(i + j) % 2], "crown_bronze")
                deco.equip(u, (p1, p2)[(i + j + 1) % 2], "fx_stars_bronze")
        except Exception as e:                              # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=hammer, args=(i,)) for i in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    eq = deco.equipped(u)
    wearing = [pid for pid, d in eq.items() if d.get("head") == "crown_bronze"]
    stars = [pid for pid, d in eq.items() if d.get("trail") == "fx_stars_bronze"]
    chk("동시에 끼워도 장식 하나는 한 마리만 (겹쳐 쓰지 않는다)", not errs and len(wearing) == 1 and len(stars) == 1,
        (errs[:1], eq))

    print("\n=== 5. 선물 (gift_claim kind 'deco') ===")
    g = T5.mkuser("꾸미기_다", "PIKACHU", 30)
    for what in ("bundle:rank2", C.PICK, "crown_rainbow"):
        db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at) VALUES (?,?,?,?,?,?,?)",
               (g, "deco", what, 1, "t", "m", "2026-10-30T00:00:00+00:00"))
    out = items.gift_claim(g)
    chk("묶음 · 선택권을 지급하고 이름을 준다", [x["name"] for x in out] == ["은관 · 은빛 별가루", C.PICK_KR]
        and set(deco.owned(g)) == {"crown_silver", "fx_stars_silver", C.PICK}, (out, deco.owned(g)))
    chk("  모르는 것은 안 준다 · 다시 받으면 없다", items.gift_claim(g) == [])


# ---------------------------------------------------------------- 6. 길드전 결산
def war(sea):
    season.SEASON = sea
    T5.wipe()
    gs = [T5.mkguild("꾸%d길드%d" % (sea, i), 5) for i in range(4)]
    T5.clock(T5.at(hours=1))
    for _g, ids in gs:
        GW.apply(ids[0])
    T5.clock(T5.at(days=3, hours=1))
    GW._lock(T5.at(days=3, hours=1))
    T5.clock(T5.at(days=7, hours=1))
    for _g, ids in gs:
        hit = GW.map_view(ids[0])["hit"]
        T5.fight(ids[0], hit[0], win=False)          # 한 번 공격하고 기권 - '공격한 사람' 이 된다
    end = None
    for d in range(8, 20):
        if GW.phase(T5.at(days=d, hours=1))[0] == "done":
            end = T5.at(days=d, hours=1)
            break
    T5.clock(end)
    db.run("DELETE FROM gift")
    GW.settle(end)
    ranks = dict((r["guildId"], r["rank"]) for r in GW.scores(season.SEASON))
    return gs, ranks, end


def war_part():
    print("\n=== 6. 길드전 결산 (시즌 5) ===")
    gs, ranks, end = war(5)
    want = {1: "bundle:rank1", 2: "bundle:rank2", 3: "bundle:rank3", 4: C.PICK}
    got = {}
    for gid, ids in gs:
        rows = db.q("SELECT user_id, item_id FROM gift WHERE kind='deco' AND user_id IN (%s)"
                    % ",".join(str(i) for i in ids))
        got[ranks[gid]] = rows
    chk("순위마다 공격한 사람 한 명에게 그 묶음 (4위는 선택권)",
        all(len(got[r]) == 1 and got[r][0]["item_id"] == want[r] for r in want), dict((r, [x["item_id"] for x in v])
                                                                                    for r, v in got.items()))
    chk("  공격 안 한 사람은 없다", all(got[ranks[gid]][0]["user_id"] == ids[0] for gid, ids in gs))
    chat = db.q1("SELECT body FROM guild_chat WHERE guild_id=? ORDER BY id DESC LIMIT 1",
                 ([g for g, r in ranks.items() if r == 1][0],))
    chk("  길드 채팅 안내에 꾸미기가 나온다", chat and "꾸미기 보상" in chat["body"], chat)
    n = db.q1("SELECT COUNT(*) AS n FROM gift WHERE kind='deco'")["n"]
    GW.settle(end)
    chk("  결산을 다시 돌려도 한 번만", db.q1("SELECT COUNT(*) AS n FROM gift WHERE kind='deco'")["n"] == n)
    winner = got[1][0]["user_id"]
    items.gift_claim(winner)
    chk("  1위가 받으면 금관 · 금빛 별가루 · 발밑 빛", {"crown_gold", "fx_stars_gold", "fx_glow"} <= set(deco.owned(winner)),
        deco.owned(winner))

    print("\n=== 6-2. 시즌 4 에는 꾸미기를 안 준다 ===")
    gs, ranks, end = war(4)
    chk("꾸미기 선물이 없다", db.q1("SELECT COUNT(*) AS n FROM gift WHERE kind='deco'")["n"] == 0)
    chk("  코인 보상은 그대로 나간다", any(db.q("SELECT 1 FROM meta WHERE k LIKE ?", ("gw:4:paid:%",))))


def main_():
    db.init()
    cols = set(r["name"] for r in db.q("PRAGMA table_info(pokemon)"))
    chk("pokemon.deco 칸 · deco_owned 표가 있다", "deco" in cols and db.q("PRAGMA table_info(deco_owned)"), cols)
    real = season.SEASON
    try:
        points_part()
        own_part()
        war_part()
    finally:
        season.SEASON = real
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
