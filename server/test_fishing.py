# -*- coding: utf-8 -*-
"""낚시 (시즌 7) 서버. 서버를 띄우지 않는다 - 임시 DB 에 모듈을 직접 붙인다 (test_stale_battle.py 와 같은 꼴).

    python server/test_fishing.py

못 박는 것 (Task 1 - 야생 끝내기 한 곳 · wild.src · 종 표 나누기):

  1. 야생이 끝나는 열 곳(볼 잡기 · 배틀 중 잡기 · 배틀 이김 · 다 쓰러짐 · 배틀이 도망으로 끝남 · 배틀에서 도망 ·
     도망 실패 뒤 상대가 떠남 · 볼 뒤 상대가 떠남 · 놓아주기 · 만료)이 모두 deps.end_wild 를 지난다.
     **낚시 야생(src='fish')은 풀숲 다음 시각(wild_state.next_at)을 건드리지 않는다.** 풀숲 야생은 지금과 똑같이
     다시 잡는다 (보통 간격, 풀숲인 채 놓친 것은 MISS_COOLDOWN 까지만). 통계 · 걸린 배틀 닫기는 둘 다 그대로.
  2. wild.src 칸 (MIGRATIONS, 기본 'grass'), 공개 모양(_wild_public)에 늘 "src".
  3. 풀숲 표(_make_grass)는 낚시가 열린 뒤에만 낚시 위주 종(FISH_ONLY)을 뺀다. 열리기 전(시즌 6)에는 지금 표 그대로.

못 박는 것 (Task 2 - 낚시 서버: fishing.py · fishing_routes.py · 표 · 카드 · 기록 · 정산):

  4. 열리기 전(시즌 6)에는 /api/fish* 404, /api/me 의 fish 는 None, 풀숲 돋기도 그대로 (던져 둔 줄이 있어도).
  5. 던지기 · 입질 열기 · 챔질(콕콕 경고 / 헛챔질 / 제때 / 완벽 / 늦음) · 거두기 - 시각은 서버가 요청을 받은 때.
     카드는 입질 전에 남은 초를 절대 안 준다. 두 번 챔질해도 야생은 한 마리.
  6. 입질 임박 · 입질 중 · 낚인 야생이 있으면 풀숲이 안 돋고(60초 뒤 다시), 풀숲 · 야생이 있으면 입질이 안 열린다.
  7. 잡으면 fish_catch 한 줄 + pokemon.fish_*; 낚시 야생은 도구 · 기술머신을 안 떨군다. 낚은 순간의 주로 센다.
  8. 순위 (한 사람 한 줄 · 배율 > 그램 > 먼저), 정산은 월 00:20 KST 뒤 한 번만, 입질 알림은 한 번만.
"""
import datetime
import json
import os
import random
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-fishing-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_FISH_FROM", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from common import battle as B                               # noqa: E402
from common import fishing as F                              # noqa: E402
from common import pokelogic as P                            # noqa: E402
from fastapi import HTTPException                            # noqa: E402

from app import battle_routes as BR                          # noqa: E402
from app import auth, config, db, deps, fishing, items, main, season   # noqa: E402
from app import fishing_routes as FR                         # noqa: E402
from app import housekeep, visit                             # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
PINNED = "2031-01-01T00:00:00+00:00"        # 풀숲 시계를 여기 박아 두고 바뀌는지 본다


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


_N = [0]


def mkuser(name=None):
    _N[0] += 1
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,30,0,'','','')",
        (name or "낚시꾼%d" % _N[0], b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot, moves):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True
    m["moves"] = list(moves)
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=1, slot=?, moves=? WHERE id=?", (slot, json.dumps(m["moves"]), pid))
    return pid


def mkwild(uid, src, species="MAGIKARP", level=2, moves=("SPLASH",), state="revealed", minutes=5):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(9), shiny_rate=10 ** 9)
    m["moves"] = list(moves)
    later = (datetime.datetime.now(UTC) + datetime.timedelta(minutes=minutes)).isoformat()
    return db.run("INSERT INTO wild (user_id, state, species, data, throws, created_at, expires_at, src)"
                  " VALUES (?,?,?,?,0,?,?,?)",
                  (uid, state, species, json.dumps(m), auth.now_iso(), later, src)).lastrowid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def pin(uid):
    db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET next_at=?", (uid, PINNED, PINNED))


def timer(uid):
    """(next_at, 지금부터 남은 초)"""
    r = db.q1("SELECT next_at FROM wild_state WHERE user_id=?", (uid,))
    at = r["next_at"] if r else None
    left = (auth.parse_iso(at) - datetime.datetime.now(UTC)).total_seconds() if at else None
    return at, left


def stat(uid, col):
    r = db.q1("SELECT %s FROM wild_state WHERE user_id=?" % col, (uid,))
    return (r[col] if r else 0) or 0


def gone(wid):
    return db.q1("SELECT id FROM wild WHERE id=?", (wid,)) is None


# ---------------------------------------------------------------- 끝나는 길 열 가지
def _strong(uid):
    """빠르고 센 선두 (이긴다 · 도망친다 · 잡는다)."""
    items.bag_add(uid, "MASTERBALL", 3)
    return mkmon(uid, "MEWTWO", 100, 0, ("SWIFT", "SPLASH"))


def p_field_catch(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    r = main.wild_catch(wid, main.CatchIn(ball="MASTERBALL"), ctx(uid))
    return wid, r.get("caught") is True, "caught"


def p_battle_catch(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    r = BR.throw_ball(bid, BR.BallIn(ball="MASTERBALL"), ctx(uid))
    return wid, r.get("caught") is True, "caught"


def p_battle_won(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    r = {}
    for _ in range(5):
        r = BR.use_move(bid, BR.MoveIn(move="SWIFT"), ctx(uid))
        if r["battle"]["result"]:
            break
    return wid, r["battle"]["result"] == "won", "wins"


def p_battle_lost(uid, src):
    mkmon(uid, "MAGIKARP", 2, 0, ("SPLASH",))            # 하나뿐인 약한 선두 - 다 쓰러진다
    wid = mkwild(uid, src, "MEWTWO", 100, ("SWIFT",))
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    r = {}
    for _ in range(5):
        r = BR.use_move(bid, BR.MoveIn(move="SPLASH"), ctx(uid))
        if r.get("allDown"):
            break
    return wid, r.get("allDown") is True, None


def p_battle_fled(uid, src):
    _strong(uid)
    wid = mkwild(uid, src, moves=("TELEPORT",))           # 상대가 순간이동으로 판을 끝낸다
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    r = BR.use_move(bid, BR.MoveIn(move="SPLASH"), ctx(uid))
    return wid, r["battle"]["result"] == "fled", None


def p_run(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    r = BR.run_away(bid, ctx(uid))
    return wid, r.get("escaped") is True, None


def p_run_then_foe_fled(uid, src):
    _strong(uid)
    wid = mkwild(uid, src, moves=("TELEPORT",))
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    real = B.Battle.try_run
    B.Battle.try_run = lambda self, attempts=1: False      # 도망은 실패하고, 상대 차례에 상대가 떠난다
    try:
        r = BR.run_away(bid, ctx(uid))
    finally:
        B.Battle.try_run = real
    return wid, r.get("escaped") is False and r["battle"]["result"] == "fled", None


def p_ball_then_foe_fled(uid, src):
    _strong(uid)
    wid = mkwild(uid, src, moves=("TELEPORT",))
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    real = P.catch_attempt
    P.catch_attempt = lambda *a, **k: (False, 0)           # 볼은 빠져나오고, 상대 차례에 상대가 떠난다
    try:
        r = BR.throw_ball(bid, BR.BallIn(ball="POKEBALL"), ctx(uid))
    finally:
        P.catch_attempt = real
    return wid, r.get("caught") is False and r["battle"]["result"] == "fled", None


def p_flee(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]          # 걸린 배틀도 같이 닫히는지 본다
    main.wild_flee(wid, ctx(uid))
    b = db.q1("SELECT state, result FROM battle WHERE id=?", (bid,))
    return wid, (b["state"], b["result"]) == ("done", "fled"), "fled"


def p_expired(uid, src):
    _strong(uid)
    wid = mkwild(uid, src)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    past = (datetime.datetime.now(UTC) - datetime.timedelta(minutes=1)).isoformat()
    db.run("UPDATE wild SET expires_at=? WHERE id=?", (past, wid))
    got = main._sweep(uid)
    b = db.q1("SELECT state, result FROM battle WHERE id=?", (bid,))
    return wid, got == [wid] and (b["state"], b["result"]) == ("done", "fled"), "fled"


PATHS = [
    ("볼로 잡기 (배틀 밖)", p_field_catch),
    ("배틀 중 볼로 잡기", p_battle_catch),
    ("배틀 이김", p_battle_won),
    ("배틀 다 쓰러짐", p_battle_lost),
    ("배틀이 도망으로 끝남 (상대 순간이동)", p_battle_fled),
    ("배틀에서 도망", p_run),
    ("도망 실패 뒤 상대가 떠남", p_run_then_foe_fled),
    ("볼 뒤 상대가 떠남", p_ball_then_foe_fled),
    ("놓아주기 (걸린 배틀도 닫힌다)", p_flee),
    ("만료 (_sweep, 걸린 배틀도 닫힌다)", p_expired),
]


def test_end_paths_keep_grass_timer():
    print("=== 야생이 끝나는 열 곳 - 낚시 야생은 풀숲 시계를 안 건드린다 ===")
    calls = []
    real_end = deps.end_wild

    def spy(uid, row, how):
        calls.append((row["id"], row["src"], how))
        return real_end(uid, row, how)
    deps.end_wild = spy
    try:
        for name, fn in PATHS:
            for src in ("grass", "fish"):
                uid = mkuser()
                pin(uid)
                before = dict((c, stat(uid, c)) for c in ("caught", "fled", "wins"))
                del calls[:]
                wid, ok, bumped = fn(uid, src)
                at, left = timer(uid)
                chk("%s [%s]: 길대로 끝났고 야생 행이 없다" % (name, src), ok and gone(wid), (ok, gone(wid)))
                chk("  deps.end_wild 를 한 번 지났다 (src=%s)" % src,
                    [c[:2] for c in calls] == [(wid, src)], calls)
                if bumped:
                    chk("  통계 %s +1 (지금처럼)" % bumped, stat(uid, bumped) == before[bumped] + 1,
                        (before[bumped], stat(uid, bumped)))
                if src == "fish":
                    chk("  풀숲 다음 시각 그대로", at == PINNED, at)
                else:
                    chk("  풀숲 다음 시각을 다시 잡았다 (보통 간격 %d~%d초, %.0f초)"
                        % (config.WILD_COOLDOWN_MIN, config.WILD_COOLDOWN_MAX, left or -1),
                        at != PINNED and config.WILD_COOLDOWN_MIN - 3 <= left <= config.WILD_COOLDOWN_MAX, at)
    finally:
        deps.end_wild = real_end

    print("\n=== 풀숲인 채(state='grass') 끝나면 지금처럼 MISS_COOLDOWN 까지만 ===")
    for name, how in (("놓아주기", "flee"), ("만료", "sweep")):
        uid = mkuser()
        pin(uid)
        wid = mkwild(uid, "grass", state="grass")
        if how == "flee":
            # 앱의 만료 타이머처럼 만료 뒤에 놓아준다 - 숨바꼭질(시즌 7)부터 만료 전에 이르게 놓아주면 보통 간격이다
            # (deps._truly_expired, server/test_hide.py test_early_flee)
            db.run("UPDATE wild SET expires_at=? WHERE id=?",
                   ((datetime.datetime.now(UTC) - datetime.timedelta(seconds=1)).isoformat(), wid))
            main.wild_flee(wid, ctx(uid))
        else:
            db.run("UPDATE wild SET expires_at=? WHERE id=?",
                   ((datetime.datetime.now(UTC) - datetime.timedelta(seconds=5)).isoformat(), wid))
            main._sweep(uid)
        at, left = timer(uid)
        chk("%s: 풀숲 %.0f초 뒤 (≤ %d)" % (name, left or -1, config.MISS_COOLDOWN),
            gone(wid) and at != PINNED and left <= config.MISS_COOLDOWN and stat(uid, "fled") == 1, (at, left))

    print("\n=== end_wild 를 바로 부른다 ===")
    uid = mkuser()
    pin(uid)
    row = db.q1("SELECT * FROM wild WHERE id=?", (mkwild(uid, "fish"),))
    deps.end_wild(uid, row, "wild_flee")
    chk("fish 행: 지우고 · 도망 +1 · 시계 그대로", gone(row["id"]) and stat(uid, "fled") == 1 and timer(uid)[0] == PINNED)
    row = db.q1("SELECT * FROM wild WHERE id=?", (mkwild(uid, "grass"),))
    deps.end_wild(uid, row, "battle")
    chk("grass 행 (배틀 끝): 통계는 안 건드리고 시계는 보통 간격",
        gone(row["id"]) and stat(uid, "fled") == 1 and stat(uid, "caught") == 0
        and config.WILD_COOLDOWN_MIN - 3 <= timer(uid)[1] <= config.WILD_COOLDOWN_MAX, timer(uid))
    pin(uid)
    old = {"id": 999999, "state": "revealed", "data": "{}"}            # src 칸을 모르는 행 (옛 꼴) = 풀숲
    deps.end_wild(uid, old, "battle")
    chk("src 를 모르는 행은 풀숲으로 본다", timer(uid)[0] != PINNED)
    try:
        deps.end_wild(uid, row, "bogus")
        chk("모르는 how 는 오류 (조용히 지나가지 않는다)", False)
    except KeyError:
        chk("모르는 how 는 오류 (조용히 지나가지 않는다)", True)


# ---------------------------------------------------------------- wild.src
def test_wild_src():
    print("\n=== wild.src 칸 · 공개 모양 ===")
    conn = db.connect()
    cols = dict((r["name"], r) for r in conn.execute("PRAGMA table_info(wild)").fetchall())
    chk("wild 에 src 칸이 있다 (MIGRATIONS)", "src" in cols and any(m[:2] == ("wild", "src") for m in db.MIGRATIONS))
    chk("  기본값은 'grass', 비지 않는다", cols.get("src") and cols["src"]["dflt_value"] == "'grass'"
        and cols["src"]["notnull"] == 1, dict(cols["src"]) if "src" in cols else None)
    uid = mkuser()
    t = datetime.datetime.now(UTC)
    wid = db.run("INSERT INTO wild (user_id, state, species, data, created_at, expires_at) VALUES (?,?,?,?,?,?)",
                 (uid, "grass", "PIDGEY", json.dumps({"species": "PIDGEY", "level": 3}), t.isoformat(),
                  (t + datetime.timedelta(seconds=90)).isoformat())).lastrowid
    row = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
    chk("src 없이 넣은 행(지금 풀숲)은 'grass'", row["src"] == "grass", row["src"])
    chk("_wild_public 에 src='grass' (숨긴 풀숲)", main._wild_public(row, False).get("src") == "grass")
    fid = mkwild(uid, "fish")
    pub = main._wild_public(db.q1("SELECT * FROM wild WHERE id=?", (fid,)), True)
    chk("_wild_public 에 src='fish' (드러낸 야생 · pokemon 포함)", pub.get("src") == "fish" and pub.get("pokemon"),
        sorted(pub))
    db.run("DELETE FROM wild WHERE user_id=?", (uid,))
    mkmon(uid, "PIDGEY", 5, 0, ("TACKLE",))
    out = main.wild_state(ctx(uid), force=True)
    chk("GET /api/wild 의 풀숲에도 src", out["wild"] and out["wild"].get("src") == "grass", out.get("wild"))


# ---------------------------------------------------------------- 풀숲 표 나누기
def test_grass_pool():
    print("\n=== 풀숲 표: 열린 뒤에만 낚시 위주 종을 뺀다 ===")
    real_season = season.SEASON
    d = deps.dex()
    uid = mkuser()
    mkmon(uid, "MEWTWO", 40, 0, ("SWIFT",))              # 파티 최저 Lv40 - 낚시 위주 종이 많이 나오는 표
    seen = []
    real_roll = d.roll_wild

    def spy(*a, **k):
        seen.append(k.get("exclude"))
        return real_roll(*a, **k)

    def grow(n):
        got = 0
        for _ in range(n):
            row = main._make_grass(uid)
            if row["species"] in F.FISH_ONLY:
                got += 1
            db.run("DELETE FROM wild WHERE id=?", (row["id"],))
        return got
    try:
        season.SEASON = config.FISH_FROM - 1
        chk("시즌 %d: 닫혀 있다 · grass_exclude 는 빈 것" % season.SEASON,
            not fishing.is_open() and fishing.grass_exclude() == frozenset())
        d.roll_wild = spy
        grow(30)
        chk("  _make_grass 가 빈 exclude 를 넘긴다 (지금 표 그대로)", seen and all(e == frozenset() for e in seen),
            set(map(len, (e or () for e in seen))))
        d.roll_wild = real_roll
        lo, hi, cap = main._wild_levels(uid)
        chk("  빈 exclude 표 = 예전 표 (같은 캐시 항목)", d.spawn_pool(hi, cap, None, frozenset())[0] is d.spawn_pool(hi, cap)[0])
        closed = grow(400)
        chk("  닫혀 있으면 풀숲에 낚시 위주 종이 나온다 (%d/400)" % closed, closed > 0, closed)

        season.SEASON = config.FISH_FROM
        del seen[:]
        chk("시즌 %d: 열렸다 · grass_exclude = FISH_ONLY" % season.SEASON,
            fishing.is_open() and fishing.grass_exclude() == F.FISH_ONLY)
        d.roll_wild = spy
        grow(30)
        chk("  _make_grass 가 FISH_ONLY 를 넘긴다", seen and all(e == F.FISH_ONLY for e in seen), len(seen))
        d.roll_wild = real_roll
        opened = grow(400)
        chk("  열리면 풀숲에 낚시 위주 종 0/400", opened == 0, opened)
        db.run("INSERT INTO wild_state (user_id, lure_type, lure_until) VALUES (?,?,?)"
               " ON CONFLICT(user_id) DO UPDATE SET lure_type=excluded.lure_type, lure_until=excluded.lure_until",
               (uid, "WATER", (datetime.datetime.now(UTC) + datetime.timedelta(hours=1)).isoformat()))
        water = grow(300)
        chk("  물 타입 스프레이를 켜도 0/300", water == 0, water)
    finally:
        d.roll_wild = real_roll
        season.SEASON = real_season


# ================================================================ Task 2 - 낚시 서버
KST = datetime.timezone(datetime.timedelta(hours=9))
CARD_KEYS = {"open", "state", "ready", "nibbleLeft", "strikeLeft", "bait", "baitLeft", "wait", "wild", "ballOptions"}


def rnow():
    return datetime.datetime.now(UTC)


def secs(n):
    return datetime.timedelta(seconds=n)


def fstate(uid):
    return db.q1("SELECT * FROM fish_state WHERE user_id=?", (uid,))


def at(s):
    return auth.parse_iso(s)


def urow(uid):
    return dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))


def angler():
    """낚시꾼 하나: 빠르고 센 선두 + 마스터볼 (잡기 · 이기기)."""
    uid = mkuser()
    _strong(uid)
    return uid


def refused(fn, *a, **k):
    """fishing.Refused 의 상태 번호. 안 막혔으면 None."""
    try:
        fn(*a, **k)
    except fishing.Refused as e:
        return e.status
    return None


def http_status(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return e.status_code
    return None


def to_bite(uid, bait=None, t=None):
    """10분 전에 던져 둔 것으로 하고 t 에 입질을 연다. (카드, 콕콕 끝, 쭉 끝)."""
    t = t or rnow()
    fishing.cast(uid, bait, now=t - secs(600))
    card = fishing.bite(uid, now=t)
    st = fstate(uid)
    return card, at(st["nibble_end"]), at(st["strike_end"])


def hook_after(uid, delay=1.0, bait=None):
    """던지기 -> 입질 -> 쭉이 되고 delay 초 뒤 챔질. hook 응답."""
    _c, ne, _se = to_bite(uid, bait)
    return fishing.hook(uid, urow(uid), hour=12, now=ne + secs(delay))


def wilds(uid):
    return db.q("SELECT * FROM wild WHERE user_id=?", (uid,))


def me_ctx(uid):
    c = ctx(uid)
    c["session"] = {"ip": "127.0.0.1", "expires_at": "2099-01-01T00:00:00+00:00", "token_hash": "x"}
    return c


class Season(object):
    """season.SEASON 을 잠깐 바꾼다."""

    def __init__(self, n):
        self.n = n

    def __enter__(self):
        self.old = season.SEASON
        season.SEASON = self.n

    def __exit__(self, *a):
        season.SEASON = self.old


def test_closed_before_season():
    print("\n=== 열리기 전(시즌 %d): 404 · 카드 None · 풀숲 그대로 ===" % (config.FISH_FROM - 1))
    with Season(config.FISH_FROM - 1):
        uid = angler()
        items.bag_add(uid, "ORANBERRY", 2)
        c = ctx(uid)
        chk("GET /api/fish 404", http_status(FR.fish_card, c) == 404)
        chk("POST /api/fish/cast 404", http_status(FR.fish_cast, FR.CastIn(bait="ORANBERRY"), c) == 404)
        chk("POST /api/fish/bite 404", http_status(FR.fish_bite, c) == 404)
        chk("POST /api/fish/hook 404", http_status(FR.fish_hook, FR.HookIn(hour=3), c) == 404)
        chk("POST /api/fish/reel 404", http_status(FR.fish_reel, c) == 404)
        chk("GET /api/fish/board 404", http_status(FR.fish_board, "this", c) == 404)
        chk("  열매는 그대로 (아무것도 안 했다)", items.bag_count(uid, "ORANBERRY") == 2)
        chk("fishing.card 는 None", fishing.card(uid) is None)
        chk("풀숲 표에서 빼는 종 없음 (지금 표 그대로)", fishing.grass_exclude() == frozenset())
        try:
            me = main._me_data(me_ctx(uid))
            chk("/api/me 의 fish 는 None (칸은 있다)", "fish" in me and me["fish"] is None, me.get("fish"))
        except Exception as e:                               # noqa: BLE001
            chk("/api/me 의 fish 는 None (칸은 있다)", False, repr(e))
        # 열리기 전에 던져 둔 줄이 (어떻게든) 남아 있어도 풀숲은 지금처럼 돋는다
        t = rnow()
        db.run("INSERT INTO fish_state (user_id, state, cast_at, bite_at) VALUES (?,?,?,?)",
               (uid, "cast", fishing.iso(t - secs(60)), fishing.iso(t + secs(30))))
        chk("holds_grass 는 거짓", fishing.holds_grass(uid) is False)
        db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", ((t - secs(5)).isoformat(), uid))
        db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?) ON CONFLICT(user_id) DO NOTHING",
               (uid, (t - secs(5)).isoformat()))
        out = main.wild_state(ctx(uid))
        chk("GET /api/wild: 때가 됐으면 풀숲이 돋는다 (낚시가 붙잡지 않는다)",
            out["wild"] and out["wild"]["src"] == "grass" and out["wild"]["state"] == "grass", out.get("wild"))
        n_meta = db.q1("SELECT COUNT(*) c FROM meta WHERE k LIKE 'fish:%'")["c"]
        chk("정산은 0 · meta 에 아무것도 안 적는다",
            fishing.settle(now=t + datetime.timedelta(days=8)) == 0
            and db.q1("SELECT COUNT(*) c FROM meta WHERE k LIKE 'fish:%'")["c"] == n_meta)
        pushed = []
        real_push = visit.push
        visit.push = lambda u, p: pushed.append((u, p))
        try:
            chk("입질 알림도 0", fishing.push_once(now=t + secs(60)) == 0 and not pushed, pushed)
        finally:
            visit.push = real_push
        db.run("DELETE FROM fish_state WHERE user_id=?", (uid,))
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))


def test_cast():
    print("\n=== 던지기 ===")
    uid = angler()
    items.bag_add(uid, "ORANBERRY", 3)
    items.bag_add(uid, "POMEGBERRY", 2)                    # 노력치 내리는 열매 (cat 'ev')
    items.bag_add(uid, "LEFTOVERS", 1)                     # 지닌 도구지만 열매가 아니다
    t = rnow()
    chk("노력치 열매는 미끼가 아니다 (400)", refused(fishing.cast, uid, "POMEGBERRY", now=t) == 400)
    chk("열매가 아닌 지닌 도구 (400)", refused(fishing.cast, uid, "LEFTOVERS", now=t) == 400)
    chk("없는 열매 (400)", refused(fishing.cast, uid, "SITRUSBERRY", now=t) == 400)
    chk("모르는 이름 (400)", refused(fishing.cast, uid, "NOPEBERRY", now=t) == 400)
    chk("  막힌 동안 아무것도 안 빠졌다", items.bag_count(uid, "POMEGBERRY") == 2 and items.bag_count(uid, "ORANBERRY") == 3
        and fstate(uid) is None)
    card = fishing.cast(uid, "oranberry", now=t)
    chk("idle -> cast", card["state"] == "cast" and fstate(uid)["state"] == "cast", card)
    chk("  카드 모양 (계약의 열 칸)", set(card) == CARD_KEYS and card["open"] is True, sorted(card))
    chk("  미끼 하나 빠짐 · 카드에 단 미끼와 남은 수", items.bag_count(uid, "ORANBERRY") == 2
        and card["bait"] == "ORANBERRY" and card["baitLeft"] == 2, (card["bait"], card["baitLeft"]))
    chk("  남은 초가 없다 · ready false", card["ready"] is False and card["nibbleLeft"] is None
        and card["strikeLeft"] is None and card["wait"] is None and card["wild"] is None, card)
    gap = (at(fstate(uid)["bite_at"]) - t).total_seconds()
    chk("  미끼 입질 %d~%d초 (%.0f)" % (config.FISH_BAIT_MIN, config.FISH_BAIT_MAX, gap),
        config.FISH_BAIT_MIN <= gap <= config.FISH_BAIT_MAX, gap)
    chk("  카드 어디에도 입질 시각이 없다", "bite" not in json.dumps(card).replace('"state"', ""), card)
    chk("두 번 던지기 409", refused(fishing.cast, uid, None, now=t + secs(1)) == 409
        and items.bag_count(uid, "ORANBERRY") == 2)
    chk("  라우트도 409", http_status(FR.fish_cast, FR.CastIn(), ctx(uid)) == 409)

    uid2 = angler()
    card = FR.fish_cast(FR.CastIn(bait=None), ctx(uid2))
    gap = (at(fstate(uid2)["bite_at"]) - rnow()).total_seconds()
    chk("미끼 없이 (라우트): 입질 %d~%d초 (%.0f) · bait null · baitLeft 0" % (config.FISH_BITE_MIN, config.FISH_BITE_MAX, gap),
        config.FISH_BITE_MIN - 2 <= gap <= config.FISH_BITE_MAX and card["bait"] is None and card["baitLeft"] == 0, card)
    chk("  라우트: 노력치 열매 400", http_status(FR.fish_cast, FR.CastIn(bait="POMEGBERRY"), ctx(angler())) == 400)

    uid3 = angler()
    real = config.MAX_BOX
    config.MAX_BOX = 1                                       # 선두 하나로 가득
    try:
        chk("상자 가득 409", refused(fishing.cast, uid3, None, now=t) == 409 and fstate(uid3) is None)
    finally:
        config.MAX_BOX = real


def test_bite_open():
    print("\n=== 입질 열기 ===")
    uid = angler()
    t = rnow()
    fishing.cast(uid, None, now=t)
    bite_at = at(fstate(uid)["bite_at"])
    card = fishing.bite(uid, now=t + secs(10))
    chk("입질 시각 전: state cast 그대로 · ready false", card["state"] == "cast" and card["ready"] is False
        and fstate(uid)["state"] == "cast", card)
    chk("  카드: 시각 1초 전 ready false / 1초 뒤 true",
        fishing.card(uid, now=bite_at - secs(1))["ready"] is False
        and fishing.card(uid, now=bite_at + secs(1))["ready"] is True)
    card = fishing.bite(uid, now=bite_at + secs(1))
    chk("시각 뒤: bite", card["state"] == "bite" and fstate(uid)["state"] == "bite", card)
    nl, sl = card["nibbleLeft"], card["strikeLeft"]
    chk("  nibbleLeft %.2f (%.0f~%.0f초)" % (nl or -1, config.FISH_NIBBLE_MIN, config.FISH_NIBBLE_MAX),
        nl is not None and config.FISH_NIBBLE_MIN <= nl <= config.FISH_NIBBLE_MAX, nl)
    chk("  strikeLeft %.2f ≈ nibbleLeft + %.0f (여유는 빼고)" % (sl or -1, config.FISH_STRIKE),
        sl is not None and abs(sl - (nl + config.FISH_STRIKE)) < 0.05, (nl, sl))
    chk("  bite 중 ready false", card["ready"] is False)
    again = fishing.bite(uid, now=bite_at + secs(2))
    chk("  bite 중 또 bite: 그대로 (새로 굴리지 않는다)", again["state"] == "bite"
        and abs(again["nibbleLeft"] - (nl - 1)) < 0.05, again)
    chk("idle 에서 bite 409", refused(fishing.bite, angler(), now=t) == 409)
    chk("  라우트도 409", http_status(FR.fish_bite, ctx(angler())) == 409)

    # 야생이 화면에 있으면 열지 않는다
    uid = angler()
    t = rnow()
    fishing.cast(uid, None, now=t - secs(600))
    wid = mkwild(uid, "grass", state="grass")
    card = fishing.bite(uid, now=t)
    chk("풀숲이 있으면 안 열림: state cast · ready · wait 'wild'",
        card["state"] == "cast" and card["ready"] is True and card["wait"] == "wild"
        and fstate(uid)["state"] == "cast", card)
    chk("  카드도 wait 'wild'", fishing.card(uid, now=t)["wait"] == "wild")
    db.run("DELETE FROM wild WHERE id=?", (wid,))
    card = fishing.bite(uid, now=t + secs(1))
    chk("  야생이 사라지면 열린다", card["state"] == "bite" and card["wait"] is None, card)


def test_hook_paths():
    print("\n=== 챔질 ===")
    seen_chance = []
    real_roll = F.roll_ratio

    def spy(rng, big):
        seen_chance.append(big)
        return real_roll(rng, big)
    F.roll_ratio = spy
    try:
        # 콕콕 중 첫 클릭 = 경고, 두 번째 = 헛챔질
        uid = angler()
        t = rnow()
        _c, ne, se = to_bite(uid, t=t)
        r = fishing.hook(uid, urow(uid), hour=12, now=t + secs(0.5))
        chk("콕콕 중 첫 클릭: early (경고만, 그대로 bite)", r["result"] == "early" and r["card"]["state"] == "bite"
            and fstate(uid)["state"] == "bite" and not wilds(uid), r)
        r = fishing.hook(uid, urow(uid), hour=12, now=t + secs(1))
        chk("같은 콕콕에 두 번째: spooked -> idle", r["result"] == "spooked" and r["card"]["state"] == "idle"
            and not wilds(uid), r)
        chk("  idle 에서 또 hook 409", refused(fishing.hook, uid, urow(uid), 12, now=t + secs(2)) == 409)

        # 쭉 안 (완벽)
        uid = angler()
        enc0 = stat(uid, "encounters")
        items.bag_add(uid, "ORANBERRY", 1)
        _c, ne, se = to_bite(uid, "ORANBERRY")
        del seen_chance[:]
        r = fishing.hook(uid, urow(uid), hour=12, now=ne + secs(1))
        ws = wilds(uid)
        chk("쭉 1초 뒤: hooked · perfect True", r["result"] == "hooked" and r.get("perfect") is True, r.get("result"))
        chk("  대물 확률 = 기본 + 미끼 + 완벽 (0.12)", seen_chance == [0.12], seen_chance)
        chk("  야생 행 하나 · src fish · revealed", len(ws) == 1 and ws[0]["src"] == "fish"
            and ws[0]["state"] == "revealed", [dict(w) for w in ws])
        if ws:
            left = (at(ws[0]["expires_at"]) - (ne + secs(1))).total_seconds()
            chk("  %d초 머문다 (%.0f)" % (config.WILD_TTL, left), abs(left - config.WILD_TTL) <= 1, left)
        w = r.get("wild") or {}
        pk = w.get("pokemon") or {}
        chk("  응답: src fish · 공개 모양 · ballOptions", r.get("src") == "fish" and w.get("src") == "fish"
            and w.get("id") == (ws[0]["id"] if ws else None) and isinstance(r.get("ballOptions"), list)
            and r["ballOptions"], sorted(r))
        sp = deps.dex().get(pk.get("species")) or {}
        chk("  물 타입", "WATER" in (sp.get("types") or ()), pk.get("species"))
        ratio = pk.get("fishRatio")
        chk("  fishG = round(kg x 1000 x fishRatio)", isinstance(pk.get("fishG"), int) and ratio
            and pk["fishG"] == F.grams(sp.get("kg", 0), ratio), (pk.get("fishG"), ratio, sp.get("kg")))
        chk("  fishSpecies · fishWeek · fishBadge", pk.get("fishSpecies") == pk.get("species")
            and pk.get("fishWeek") == F.week_key(ne + secs(1)) and pk.get("fishBadge") == F.badge(ratio),
            (pk.get("fishSpecies"), pk.get("fishWeek"), pk.get("fishBadge")))
        chk("  카드 hooked", r["card"]["state"] == "hooked")
        chk("  encounters +1 (챔질 때)", stat(uid, "encounters") == enc0 + 1, (enc0, stat(uid, "encounters")))
        sn = db.q1("SELECT caught FROM seen WHERE user_id=? AND species=?", (uid, pk.get("species")))
        chk("  도감 '봤다'", sn is not None and sn["caught"] == 0)
        chk("  hooked 에서 또 hook 409", refused(fishing.hook, uid, urow(uid), 12, now=ne + secs(2)) == 409
            and len(wilds(uid)) == 1)

        # 쭉 안이지만 완벽은 아님
        uid = angler()
        _c, ne, se = to_bite(uid)
        del seen_chance[:]
        r = fishing.hook(uid, urow(uid), hour=12, now=ne + secs(config.FISH_PERFECT + 1))
        chk("쭉 %.1f초 뒤: hooked · perfect False" % (config.FISH_PERFECT + 1),
            r["result"] == "hooked" and r["perfect"] is False and len(wilds(uid)) == 1, r.get("result"))
        chk("  대물 확률 = 기본만 (0.04)", seen_chance == [0.04], seen_chance)

        # 쭉이 끝난 뒤 여유 안 (서버 +5초)
        uid = angler()
        _c, ne, se = to_bite(uid)
        r = fishing.hook(uid, urow(uid), hour=12, now=se + secs(config.FISH_GRACE - 1))
        chk("쭉 끝 + %.0f초 (여유 안): hooked" % (config.FISH_GRACE - 1), r["result"] == "hooked", r.get("result"))

        # 늦음
        uid = angler()
        _c, ne, se = to_bite(uid)
        r = fishing.hook(uid, urow(uid), hour=12, now=se + secs(config.FISH_GRACE + 0.5))
        chk("쭉 + 여유 뒤: missed -> idle · 야생 없음", r["result"] == "missed" and r["card"]["state"] == "idle"
            and fstate(uid)["state"] == "idle" and not wilds(uid), r)
        chk("  카드는 여유가 지나면 (hook 이 안 와도) idle 로 읽힌다",
            fishing.card(angler_bitten(se_off=config.FISH_GRACE + 1))["state"] == "idle")
    finally:
        F.roll_ratio = real_roll


def angler_bitten(se_off):
    """쭉이 끝나고 se_off 초가 지난 낚시꾼 (카드를 지금 시각으로 읽는다)."""
    uid = angler()
    t = rnow() - secs(config.FISH_NIBBLE_MAX + config.FISH_STRIKE + se_off)
    to_bite(uid, t=t)
    return uid


def test_hook_twice_one_wild():
    print("\n=== 두 번 챔질 (스레드 둘이 같이) - 야생은 한 마리 ===")
    for name, lock_off in (("사람마다 잠금", False), ("잠금 없이 UPDATE 조건만", True)):
        uid = angler()
        t = rnow()
        fishing.cast(uid, None, now=t - secs(600))
        db.run("UPDATE fish_state SET state='bite', nibble_end=?, strike_end=? WHERE user_id=?",
               (fishing.iso(t - secs(1)), fishing.iso(t + secs(29)), uid))
        real_lock = fishing.user_lock
        if lock_off:
            import contextlib
            fishing.user_lock = lambda u: contextlib.nullcontext()
        gate = threading.Barrier(2)
        got = []

        def go():
            gate.wait()
            try:
                got.append(FR.fish_hook(FR.HookIn(hour=12), ctx(uid))["result"])
            except HTTPException as e:
                got.append(e.status_code)
            except Exception as e:                           # noqa: BLE001
                got.append(repr(e))
        try:
            th = [threading.Thread(target=go) for _ in range(2)]
            for x in th:
                x.start()
            for x in th:
                x.join(20)
        finally:
            fishing.user_lock = real_lock
        chk("%s: 하나는 hooked, 하나는 409" % name, sorted(map(str, got)) == ["409", "hooked"], got)
        chk("  야생 행은 하나", len(wilds(uid)) == 1, len(wilds(uid)))
    chk("user_lock 은 사람마다 같은 잠금 하나", fishing.user_lock(1) is fishing.user_lock(1)
        and fishing.user_lock(1) is not fishing.user_lock(2))


def test_grass_hold():
    print("\n=== 풀숲과 겹치지 않기 ===")

    def due(uid):
        pin(uid)
        db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", ((rnow() - secs(5)).isoformat(), uid))

    def grass_try(uid):
        due(uid)
        return main.wild_state(ctx(uid))

    # 입질 임박 (150초 안)
    uid = angler()
    t = rnow()
    fishing.cast(uid, None, now=t)
    db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?", (fishing.iso(t + secs(config.FISH_HOLD - 50)), uid))
    out = grass_try(uid)
    chk("입질 %d초 전: 풀숲 안 돋음 · nextInSeconds≈60 (%s)" % (config.FISH_HOLD - 50, out.get("nextInSeconds")),
        out["wild"] is None and not wilds(uid) and 55 <= (out.get("nextInSeconds") or 0) <= 60, out)
    db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?", (fishing.iso(rnow() - secs(30)), uid))
    out = grass_try(uid)
    chk("입질 시각이 지났는데 아직 안 열림 (ready): 풀숲 안 돋음", out["wild"] is None and not wilds(uid), out.get("wild"))
    db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?", (fishing.iso(rnow() + secs(config.FISH_HOLD + 60)), uid))
    out = grass_try(uid)
    chk("입질이 멀면 (%d초 뒤): 풀숲 돋음" % (config.FISH_HOLD + 60), out["wild"] and out["wild"]["src"] == "grass", out)
    db.run("DELETE FROM wild WHERE user_id=?", (uid,))

    # 입질 중
    uid = angler()
    to_bite(uid)
    out = grass_try(uid)
    chk("입질 중: 풀숲 안 돋음 · nextInSeconds≈60", out["wild"] is None and not wilds(uid)
        and 55 <= (out.get("nextInSeconds") or 0) <= 60, out)
    chk("  holds_grass 참", fishing.holds_grass(uid) is True)

    # 낚인 야생이 있다 (fish_state 와 상관없이)
    uid = angler()
    mkwild(uid, "fish")
    out = grass_try(uid)
    chk("낚인 야생이 있으면: 그 야생을 보이고 풀숲은 안 돋음", out["wild"] and out["wild"]["src"] == "fish"
        and len(wilds(uid)) == 1, out.get("wild"))
    chk("  holds_grass 참", fishing.holds_grass(uid) is True)

    # 낚시를 안 하는 사람은 그대로
    uid = angler()
    chk("낚시를 안 하면 holds_grass 거짓", fishing.holds_grass(uid) is False)
    out = grass_try(uid)
    chk("  풀숲 돋음", out["wild"] and out["wild"]["src"] == "grass", out.get("wild"))

    # 반대로 풀숲이 있으면 입질을 안 연다
    uid = angler()
    fishing.cast(uid, None, now=rnow() - secs(600))
    # 입질 시각을 '막 지남' 으로 박는다. 600초 전에 던지면 입질 시각이 120~420초 전이라 미루는 창(FISH_HOLD_LATE)
    # 밖일 수 있다 - 그때는 풀숲이 돋는 게 맞다 (test_grass_hold_late)
    db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?", (fishing.iso(rnow() - secs(30)), uid))
    out = grass_try(uid)
    chk("입질 준비 중이면 풀숲이 먼저 오지 않는다", out["wild"] is None)
    db.run("DELETE FROM fish_state WHERE user_id=?", (uid,))
    out = grass_try(uid)
    fishing.cast(uid, None, now=rnow() - secs(600))
    card = fishing.bite(uid)
    chk("풀숲이 있으면 bite 안 열림 (wait 'wild')", out["wild"] and card["state"] == "cast" and card["wait"] == "wild",
        card)

    # 동시에 두 번 물어도 풀숲은 하나 (잠금 안에서 다시 본다)
    uid = angler()
    due(uid)
    gate = threading.Barrier(3)

    def ask():
        gate.wait()
        main.wild_state(ctx(uid))
    th = [threading.Thread(target=ask) for _ in range(3)]
    for x in th:
        x.start()
    for x in th:
        x.join(20)
    chk("GET /api/wild 셋이 같이 와도 야생 행은 하나", len(wilds(uid)) == 1, len(wilds(uid)))


def test_grass_hold_late():
    print("\n=== 입질이 오래 안 열리면 풀숲은 다시 돋는다 (FISH_HOLD_LATE) ===")
    # 연못을 숨겼거나 · 다른 PC 거나 · 앱을 껐으면 아무도 입질을 안 연다. 그래도 풀숲을 영영 붙잡으면 안 된다
    late = getattr(config, "FISH_HOLD_LATE", None)
    chk("config.FISH_HOLD_LATE 기본 120초", late == 120, late)
    late = late or 120

    def grass_at(bite_off):
        """입질 시각을 지금 + bite_off 초로 박아 두고 풀숲 때가 된 낚시꾼. (uid, GET /api/wild)"""
        uid = angler()
        fishing.cast(uid, None, now=rnow() - secs(600))
        db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?", (fishing.iso(rnow() + secs(bite_off)), uid))
        pin(uid)
        db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", ((rnow() - secs(5)).isoformat(), uid))
        return uid, main.wild_state(ctx(uid))

    uid, out = grass_at(-3 * 3600)
    chk("입질 시각이 3시간 지났는데 아무도 안 열었다: 풀숲 돋음",
        out["wild"] and out["wild"]["src"] == "grass" and len(wilds(uid)) == 1, out.get("wild"))
    chk("  holds_grass 거짓", fishing.holds_grass(uid) is False)
    card = fishing.bite(uid)
    chk("  미뤄 둔 입질은 그 야생 뒤에서 기다린다 (cast · ready · wait 'wild')",
        card["state"] == "cast" and card["ready"] is True and card["wait"] == "wild", card)
    chk("  카드도 같다", fishing.card(uid)["wait"] == "wild")

    uid, out = grass_at(-(late + 30))
    chk("입질 시각이 %d초 지남 (창 밖): 풀숲 돋음" % (late + 30),
        out["wild"] and out["wild"]["src"] == "grass", out.get("wild"))

    uid, out = grass_at(-60)
    chk("입질 시각이 60초 지남 (앱이 곧 열 수 있다): 풀숲 안 돋음 · nextInSeconds≈60",
        out["wild"] is None and not wilds(uid) and 55 <= (out.get("nextInSeconds") or 0) <= 60, out)
    chk("  holds_grass 참", fishing.holds_grass(uid) is True)

    uid, out = grass_at(100)
    chk("입질 100초 전: 풀숲 안 돋음", out["wild"] is None and not wilds(uid), out.get("wild"))
    chk("  holds_grass 참", fishing.holds_grass(uid) is True)


def test_me_card_error():
    print("\n=== /api/me: 낚시 카드가 터지면 fish 칸을 뺀다 (None 은 '닫힘' 뿐) ===")
    # 앱은 me 에 fish 칸이 있을 때만 움직이고, None 이면 시즌이 닫힌 것으로 읽어 연못을 걷는다 - 입질 중에 걷히면 안 된다
    uid = angler()
    real = fishing.card

    def boom(*a, **k):
        raise RuntimeError("시험용 카드 실패")
    fishing.card = boom
    try:
        me = main._me_data(me_ctx(uid))
        chk("카드가 터지면 /api/me 에 fish 칸이 없다", "fish" not in me, me.get("fish"))
        chk("  나머지는 그대로 (동기화는 안 멈춘다)", "session" in me and "airraid" in me, sorted(me))
    except Exception as e:                                   # noqa: BLE001
        chk("카드가 터지면 /api/me 에 fish 칸이 없다", False, repr(e))
    finally:
        fishing.card = real
    me = main._me_data(me_ctx(uid))
    chk("열렸으면 fish 는 카드", me.get("fish") and me["fish"]["open"] is True, me.get("fish"))
    with Season(config.FISH_FROM - 1):
        me = main._me_data(me_ctx(uid))
        chk("열리기 전이면 fish 는 None (칸은 있다)", "fish" in me and me["fish"] is None, me.get("fish"))


def test_reel_refund():
    print("\n=== 거두기 ===")
    uid = angler()
    items.bag_add(uid, "ORANBERRY", 3)
    t = rnow()
    fishing.cast(uid, "ORANBERRY", now=t)
    chk("던지면 미끼 하나 빠짐", items.bag_count(uid, "ORANBERRY") == 2)
    card = fishing.reel(uid, now=t + secs(30))
    chk("cast 중 거두기: idle · 미끼 돌아옴", card["state"] == "idle" and items.bag_count(uid, "ORANBERRY") == 3
        and card["bait"] is None, card)
    card = FR.fish_reel(ctx(uid))
    chk("  idle 에서 또 거두기: 그대로 (오류 아님 · 두 번 안 돌려줌)", card["state"] == "idle"
        and items.bag_count(uid, "ORANBERRY") == 3, card)
    to_bite(uid, "ORANBERRY")
    chk("입질 열림 (미끼는 이미 빠짐)", items.bag_count(uid, "ORANBERRY") == 2)
    card = fishing.reel(uid)
    chk("bite 뒤 거두기: idle · 미끼 안 돌아옴", card["state"] == "idle" and items.bag_count(uid, "ORANBERRY") == 2, card)
    chk("  다시 던질 수 있다", fishing.cast(uid, None)["state"] == "cast")


def _drop_spies():
    calls = []

    def fake(tag):
        def f(*a, **k):
            calls.append(tag)
            return {"kr": tag, "label": tag, "id": tag}
        return f
    saved = (main._drop, main._drop_tm, BR._drop, BR._drop_tm)
    main._drop, main._drop_tm = fake("main._drop"), fake("main._drop_tm")
    BR._drop, BR._drop_tm = fake("BR._drop"), fake("BR._drop_tm")

    def undo():
        main._drop, main._drop_tm, BR._drop, BR._drop_tm = saved
    return calls, undo


def test_fish_catch_record():
    print("\n=== 잡으면 기록 · 떨굼 없음 ===")
    calls, undo = _drop_spies()
    try:
        for name, how in (("볼로 잡기 (배틀 밖)", "field"), ("배틀 중 잡기", "battle")):
            uid = angler()
            r = hook_after(uid)
            pk = r["wild"]["pokemon"]
            wid = r["wild"]["id"]
            enc = stat(uid, "encounters")
            del calls[:]
            if how == "field":
                got = main.wild_catch(wid, main.CatchIn(ball="MASTERBALL"), ctx(uid))
            else:
                bid = BR.start(wid, ctx(uid))["battle"]["id"]
                got = BR.throw_ball(bid, BR.BallIn(ball="MASTERBALL"), ctx(uid))
            rows = db.q("SELECT * FROM fish_catch WHERE user_id=?", (uid,))
            pid = (got.get("pokemon") or {}).get("id")
            chk("%s: 잡힘 · fish_catch 한 줄" % name, got.get("caught") is True and len(rows) == 1, len(rows))
            if rows:
                c = rows[0]
                chk("  주 · 종 · 그램 · 배율 · 이로치 · pokemon id", c["week"] == pk["fishWeek"]
                    and c["species"] == pk["fishSpecies"] and c["g"] == pk["fishG"]
                    and abs(c["ratio"] - pk["fishRatio"]) < 1e-9 and c["shiny"] == int(bool(pk.get("shiny")))
                    and c["pokemon_id"] == pid, dict(c))
            p = db.q1("SELECT * FROM pokemon WHERE id=?", (pid,))
            chk("  pokemon.fish_g · fish_ratio · fish_species", p and p["fish_g"] == pk["fishG"]
                and abs(p["fish_ratio"] - pk["fishRatio"]) < 1e-9 and p["fish_species"] == pk["fishSpecies"],
                dict(p) if p else None)
            want = {"g": pk["fishG"], "ratio": pk["fishRatio"], "species": pk["fishSpecies"],
                    "kr": deps.dex().name(pk["fishSpecies"])}
            chk("  공개 포켓몬에 fish dict", got["pokemon"].get("fish") == want
                and db.row_to_mon(p).get("fish") == want, got["pokemon"].get("fish"))
            chk("  떨굼 없음 (도구 · 기술머신 둘 다 안 굴림)", not calls and not got.get("drop") and not got.get("tmDrop"),
                calls)
            chk("  encounters 는 잡을 때 안 오른다 (챔질 때 이미)", stat(uid, "encounters") == enc)

        uid = angler()
        r = hook_after(uid)
        bid = BR.start(r["wild"]["id"], ctx(uid))["battle"]["id"]
        del calls[:]
        out = {}
        for _ in range(5):
            out = BR.use_move(bid, BR.MoveIn(move="SWIFT"), ctx(uid))
            if out["battle"]["result"]:
                break
        chk("배틀 이김 (낚시 야생): 떨굼 없음 · 기록 없음", out["battle"]["result"] == "won" and not calls
            and "drop" not in out and "tmDrop" not in out
            and not db.q("SELECT 1 FROM fish_catch WHERE user_id=?", (uid,)), (out["battle"]["result"], calls))

        # 견줌: 풀숲 야생은 지금처럼 굴린다
        uid = angler()
        wid = mkwild(uid, "grass")
        del calls[:]
        got = main.wild_catch(wid, main.CatchIn(ball="MASTERBALL"), ctx(uid))
        chk("견줌 - 풀숲 볼로 잡기: 떨굼을 굴린다 · 기록 없음 · fish 없음",
            calls == ["main._drop", "main._drop_tm"] and not db.q("SELECT 1 FROM fish_catch WHERE user_id=?", (uid,))
            and "fish" not in got["pokemon"], calls)
        for move in ("battle", "win"):
            uid = angler()
            wid = mkwild(uid, "grass")
            bid = BR.start(wid, ctx(uid))["battle"]["id"]
            del calls[:]
            if move == "battle":
                BR.throw_ball(bid, BR.BallIn(ball="MASTERBALL"), ctx(uid))
            else:
                for _ in range(5):
                    if BR.use_move(bid, BR.MoveIn(move="SWIFT"), ctx(uid))["battle"]["result"]:
                        break
            chk("견줌 - 풀숲 %s: 떨굼을 굴린다" % ("배틀 중 잡기" if move == "battle" else "배틀 이김"),
                calls == ["BR._drop", "BR._drop_tm"], calls)
    finally:
        undo()

    # store_caught 에 바로: fishWeek 가 없으면 지금 주로
    uid = mkuser()
    m = P.make_pokemon(deps.dex().get("MAGIKARP"), 5, random.Random(1), shiny_rate=10 ** 9)
    m.update({"fishG": 12345, "fishRatio": 1.2345, "fishSpecies": "MAGIKARP"})
    got, _where = BR.store_caught(uid, m, "POKEBALL")
    c = db.q1("SELECT * FROM fish_catch WHERE user_id=?", (uid,))
    chk("fishWeek 가 없으면 지금 주로 적는다", c and c["week"] == F.week_key(rnow()) and c["g"] == 12345, dict(c) if c else None)
    m2 = P.make_pokemon(deps.dex().get("MAGIKARP"), 5, random.Random(2), shiny_rate=10 ** 9)
    got2, _w = BR.store_caught(uid, m2, "POKEBALL")
    chk("보통 포켓몬: fish 없음 · 기록 안 늘어남", "fish" not in got2
        and db.q1("SELECT COUNT(*) c FROM fish_catch WHERE user_id=?", (uid,))["c"] == 1)


def test_card_hooked_recovers():
    print("\n=== 재시작한 앱이 낚인 야생을 되살린다 ===")
    uid = angler()
    r = hook_after(uid)
    wid = r["wild"]["id"]
    card = fishing.card(uid, urow(uid))
    chk("hooked 카드에 wild · ballOptions", card["state"] == "hooked" and card["wild"]
        and card["wild"]["id"] == wid and card["wild"]["src"] == "fish" and card["wild"].get("pokemon")
        and isinstance(card["ballOptions"], list) and card["ballOptions"], card)
    chk("  user_row 없이 불러도 (볼 수를 스스로 읽는다)", fishing.card(uid)["ballOptions"])
    try:
        me = main._me_data(me_ctx(uid))
        chk("/api/me 의 fish 도 hooked", me["fish"] and me["fish"]["state"] == "hooked"
            and me["fish"]["wild"]["id"] == wid, me.get("fish"))
    except Exception as e:                                   # noqa: BLE001
        chk("/api/me 의 fish 도 hooked", False, repr(e))
    g = FR.fish_card(ctx(uid))
    chk("GET /api/fish 도 같은 카드", g["state"] == "hooked" and g["wild"]["id"] == wid)
    chk("hooked 인 채 던지기 409", refused(fishing.cast, uid, None) == 409)
    main.wild_flee(wid, ctx(uid))
    card = fishing.card(uid, urow(uid))
    chk("야생이 사라지면 idle (따로 되돌리지 않아도)", card["state"] == "idle" and card["wild"] is None
        and card["ballOptions"] is None, card)
    chk("  다시 던질 수 있다", fishing.cast(uid, None)["state"] == "cast")

    uid = angler()
    r = hook_after(uid)
    db.run("UPDATE wild SET expires_at=? WHERE id=?", ((rnow() - secs(3)).isoformat(), r["wild"]["id"]))
    chk("만료된(아직 안 치운) 낚인 야생도 idle", fishing.card(uid)["state"] == "idle")


def _catch_row(uid, week, species, g, ratio, at_, shiny=0):
    db.run("INSERT INTO fish_catch (user_id, week, species, g, ratio, shiny, pokemon_id, at) VALUES (?,?,?,?,?,?,?,?)",
           (uid, week, species, g, ratio, shiny, None, at_))


def test_board():
    print("\n=== 주간 순위 ===")
    now = datetime.datetime(2027, 1, 13, 12, 0, tzinfo=KST)        # 수요일 - 이번 주 2027-01-11, 지난주 2027-01-04
    wk, last = "2027-01-11", "2027-01-04"
    a, b, c, d = mkuser("가낚시"), mkuser("나낚시"), mkuser("다낚시"), mkuser("라낚시")
    _catch_row(a, wk, "MAGIKARP", 13000, 1.30, "2027-01-11T01:00:00+00:00")
    _catch_row(a, wk, "GOLDEEN", 16000, 1.10, "2027-01-11T02:00:00+00:00")
    _catch_row(a, last, "GOLDEEN", 18000, 1.20, "2027-01-05T02:00:00+00:00")      # 지난주 - 내 기록에만
    _catch_row(b, wk, "WAILORD", 517400, 1.30, "2027-01-12T01:00:00+00:00", shiny=1)   # 같은 배율, 그램이 크다
    _catch_row(c, wk, "MAGIKARP", 13000, 1.30, "2027-01-11T03:00:00+00:00")       # a 와 같고 늦다
    _catch_row(d, wk, "FEEBAS", 6800, 0.92, "2027-01-11T00:30:00+00:00")
    _catch_row(d, wk, "FEEBAS", 7500, 1.01, "2027-01-12T00:30:00+00:00")
    out = fishing.board(a, "this", now=now)
    names = [(x["rank"], x["name"]) for x in out["top"]]
    chk("한 사람 한 줄 · 배율 > 그램 > 먼저", names == [(1, "나낚시"), (2, "가낚시"), (3, "다낚시"), (4, "라낚시")], names)
    t1 = out["top"][0]
    chk("  줄 모양 (rank name species num kr shiny g ratio at)",
        set(t1) >= {"rank", "name", "species", "num", "kr", "shiny", "g", "ratio", "at"}
        and t1["species"] == "WAILORD" and t1["num"] == 321 and t1["kr"] == deps.dex().name("WAILORD")
        and t1["shiny"] is True and t1["g"] == 517400, t1)
    chk("  라낚시는 그 주 가장 큰 것 (1.01)", out["top"][3]["ratio"] == 1.01, out["top"][3])
    chk("  week · weekStart · endsIn", out["week"] == wk and at(out["weekStart"]) == F.week_start_utc(wk)
        and out["endsIn"] == int((F.week_start_utc(wk) + datetime.timedelta(days=7) - now).total_seconds()),
        (out["week"], out["weekStart"], out["endsIn"]))
    chk("  me = 내 줄 (2위)", out["me"] and out["me"]["rank"] == 2 and out["me"]["name"] == "가낚시", out["me"])
    chk("  mine: 종마다 내 최대, 큰 순 (지난주 것 포함)",
        [(x["species"], x["ratio"]) for x in out["mine"]] == [("MAGIKARP", 1.30), ("GOLDEEN", 1.20)]
        and set(out["mine"][0]) >= {"species", "num", "kr", "g", "ratio", "at"}, out["mine"])
    chk("  낚은 적 없는 사람: me None · mine []", fishing.board(mkuser(), "this", now=now)["me"] is None
        and fishing.board(mkuser(), "this", now=now)["mine"] == [])

    # 지난주: 35명 - 30줄까지, last 는 지난주 1~3위
    people = [mkuser("지난주%02d" % i) for i in range(35)]
    for i, u in enumerate(people):
        _catch_row(u, last, "MAGIKARP", 10000 + i, 1.9 - i * 0.01, "2027-01-05T00:00:00+00:00")   # 가낚시의 1.20 보다 위
    out = fishing.board(people[32], "last", now=now)
    chk("week=last: 지난주 · 30줄 · endsIn 0", out["week"] == last and len(out["top"]) == 30 and out["endsIn"] == 0,
        (out["week"], len(out["top"]), out["endsIn"]))
    chk("  31위 밖이어도 me 는 내 자리 (33위)", out["me"] and out["me"]["rank"] == 33, out["me"])
    this = fishing.board(a, "this", now=now)
    chk("  이번 주 판의 last = 지난주 1~3위", [x["name"] for x in this["last"]] == ["지난주00", "지난주01", "지난주02"]
        and [x["rank"] for x in this["last"]] == [1, 2, 3], this["last"])
    chk("라우트: GET /api/fish/board", set(FR.fish_board("this", ctx(a))) >= {"week", "weekStart", "endsIn", "top",
                                                                         "me", "last", "mine"})


def test_week_boundary():
    print("\n=== 주 경계 - 일 23:59 낚아 월 00:05 잡기 ===")
    sun = datetime.datetime(2026, 11, 29, 23, 59, 0, tzinfo=KST)
    mon = datetime.datetime(2026, 11, 30, 0, 5, 0, tzinfo=KST)
    chk("(검사 준비) 두 시각은 다른 주", F.week_key(sun) == "2026-11-23" and F.week_key(mon) == "2026-11-30")
    uid = angler()
    fishing.cast(uid, None, now=sun - secs(600))
    fishing.bite(uid, now=sun - secs(config.FISH_NIBBLE_MAX + 1))
    r = fishing.hook(uid, urow(uid), hour=23, now=sun + secs(1))
    chk("일 23:59:01 챔질 - fishWeek 는 그 주", r["result"] == "hooked"
        and r["wild"]["pokemon"]["fishWeek"] == "2026-11-23", r.get("result"))
    db.run("UPDATE wild SET expires_at=? WHERE user_id=?", ((rnow() + secs(300)).isoformat(), uid))
    got = main.wild_catch(r["wild"]["id"], main.CatchIn(ball="MASTERBALL"), ctx(uid))
    c = db.q1("SELECT * FROM fish_catch WHERE user_id=?", (uid,))
    chk("월요일에 잡아도 지난주 기록", got.get("caught") and c and c["week"] == "2026-11-23", dict(c) if c else None)
    last = fishing.board(uid, "last", now=mon)
    this = fishing.board(uid, "this", now=mon)
    chk("  월 00:05 순위: 지난주 판에 있고 이번 주 판에는 없다",
        last["me"] and last["me"]["g"] == c["g"] and this["me"] is None, (last["me"], this["me"]))


def test_settle_once():
    print("\n=== 주간 정산 - 월 00:20 KST 뒤 한 번만 ===")
    wk = "2026-11-09"
    people = [mkuser("정산%02d" % i) for i in range(32)]
    for i, u in enumerate(people):
        _catch_row(u, wk, "MAGIKARP", 10000 + i, 1.9 - i * 0.01, "2026-11-10T00:00:00+00:00")
    _catch_row(people[0], wk, "GOLDEEN", 9000, 1.0, "2026-11-10T01:00:00+00:00")    # 한 사람 두 줄 - 한 번만 받는다
    start = F.week_start_utc("2026-11-16")

    def gifts():
        return dict((r["user_id"], (r["item_id"], r["count"], r["kind"])) for r in db.q(
            "SELECT * FROM gift WHERE user_id IN (%s)" % ",".join("?" * len(people)), people))
    chk("월 00:19: 정산 0 · 선물 없음", fishing.settle(now=start + datetime.timedelta(minutes=19)) == 0 and not gifts())
    chk("  정산 끝 표시도 아직", db.q1("SELECT 1 FROM meta WHERE k LIKE ?", ("fish:settled:%s" % wk,)) is None)
    n = fishing.settle(now=start + datetime.timedelta(minutes=21))
    g = gifts()
    chk("월 00:21: 30명에게 (%d)" % n, n == 30 and len(g) == 30, n)
    want = {}
    for i, u in enumerate(people[:30]):
        rank = i + 1
        want[u] = (("BIGNUGGET", 1) if rank == 1 else ("NUGGET", 2) if rank <= 3
                   else ("NUGGET", 1) if rank <= 10 else ("BIGPEARL", 1))
    chk("  보상 표대로 (1위 큰금구슬 1 · 2~3위 금구슬 2 · 4~10위 금구슬 1 · 11~30위 큰진주 1)",
        all(g.get(u, (None, None, None))[:2] == w and g[u][2] == "item" for u, w in want.items()),
        dict((u, g.get(u)) for u in people[:12]))
    chk("  31위 밖은 없다", people[30] not in g and people[31] not in g)
    chk("두 번 불러도 다시 안 준다", fishing.settle(now=start + datetime.timedelta(minutes=22)) == 0
        and fishing.settle(now=start + datetime.timedelta(hours=5)) == 0 and len(gifts()) == 30
        and db.q1("SELECT COUNT(*) c FROM gift WHERE user_id IN (%s)" % ",".join("?" * len(people)), people)["c"] == 30)
    db.run("DELETE FROM meta WHERE k=?", ("fish:settled:%s" % wk,))           # 도중에 끊겨 끝 표시만 없다
    chk("  끝 표시가 없어도 사람마다 표시가 있어 두 번 안 준다",
        fishing.settle(now=start + datetime.timedelta(minutes=30)) == 0
        and db.q1("SELECT COUNT(*) c FROM gift WHERE user_id IN (%s)" % ",".join("?" * len(people)), people)["c"] == 30)
    # 한 시간마다 도는 집안일이 정산을 부른다
    import inspect
    chk("housekeep 이 한 시간마다 fishing.settle 을 부른다", "fishing.settle()" in inspect.getsource(housekeep._loop))


def test_push_once():
    print("\n=== 입질 알림 - 한 번만 ===")
    t = rnow()
    ready, later = angler(), angler()
    fishing.cast(ready, None, now=t - secs(600))
    fishing.cast(later, None, now=t)
    db.run("UPDATE fish_state SET pushed=1 WHERE user_id NOT IN (?,?)", (ready, later))   # 앞 검사들이 남긴 줄은 치운다
    pushed = []
    real_push = visit.push
    visit.push = lambda u, p: pushed.append((u, p))
    try:
        n1 = fishing.push_once(now=t)
        chk("한 바퀴: 1번 · 입질 시각이 지난 사람에게만", n1 == 1 and pushed == [(ready, {"t": "fish", "s": "ready"})], pushed)
        chk("  pushed=1", fstate(ready)["pushed"] == 1 and fstate(later)["pushed"] == 0)
        del pushed[:]
        chk("두 바퀴째: 0", fishing.push_once(now=t + secs(5)) == 0 and not pushed, pushed)
        fishing.reel(ready, now=t)
        fishing.cast(ready, None, now=t - secs(600))
        chk("다시 던지면 다시 한 번", fishing.push_once(now=t + secs(10)) == 1 and pushed[-1][0] == ready, pushed)
    finally:
        visit.push = real_push
    import inspect
    chk("서버가 뜰 때 pusher 를 띄운다 (housekeep.start 곁)", "fishing.start_pusher()" in inspect.getsource(main._startup))


def task2():
    with Season(config.FISH_FROM):
        test_cast()
        test_bite_open()
        test_hook_paths()
        test_hook_twice_one_wild()
        test_grass_hold()
        test_grass_hold_late()
        test_me_card_error()
        test_reel_refund()
        test_fish_catch_record()
        test_card_hooked_recovers()
        test_board()
        test_week_boundary()
        test_settle_once()
        test_push_once()


def main_():
    db.init()
    test_wild_src()
    test_end_paths_keep_grass_timer()
    test_grass_pool()
    test_closed_before_season()
    task2()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
