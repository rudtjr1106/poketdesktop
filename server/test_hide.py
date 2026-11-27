# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7) 서버. 서버를 띄우지 않는다 - 임시 DB 에 모듈을 직접 붙인다 (test_fishing.py 와 같은 꼴).

    python server/test_hide.py

못 박는 것 (design-notes/2026-11-27-hide-and-seek-plan.md Task 1):

  test_closed          시즌 6: hide=1 이어도 숨기지 않는다. 풀숲은 바이트 단위로 지금과 같다 (같은 씨앗 = 같은 풀숲).
  test_no_flag         hide 를 안 보내면(옛 앱 · 끈 사람) 1000번 돋워도 숨은 포켓몬 0.
  test_chance          hide=1 로 많이 돋우면 약 4.2% (하루 8시간 약 3번).
  test_skip            이벤트 볼 · 업적 종 · 타입 스프레이 · 버닝 · 낚시 줄을 던져 둠이면 숨기지 않는다 (평소 풀숲).
  test_pool            숨은 포켓몬의 약 절반이 숨는 종(HIDERS), 낚시 위주 종 없음, 레벨 = 풀숲, 할로윈 가중 없음.
  test_hidden_ability  숨은 포켓몬 숨겨진 특성 ≈ 1/4 (있는 종만 센다), 풀숲은 ≈ 1/128, 이로치 확률은 그대로.
  test_peek            숨은 행은 공개 전에 peek{num, form} 만 - 종 · 특성 · 이로치 · 레벨 없음. 보통 풀숲엔 peek 없음.
  test_ttl_and_next    expiresIn 240, 다음 풀숲 240+쿨다운, 못 찾고 만료 → 10초 뒤, 찾고 잡으면 보통 쿨다운.
  test_early_flee      공개 전 이른 도망(flee)은 보통 쿨다운, 진짜 만료(만료 5초 전부터) 뒤 도망은 짧게 - 풀숲 · 숨은 것 둘 다.
  test_reveal_catch    숨은 행 reveal → 평소 야생 (잡기 · 배틀 그대로, 도구를 떨군다).
"""
import datetime
import inspect
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-hide-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
for _k in ("POKET_HIDE_FROM", "POKET_HIDE_CHANCE", "POKET_HIDE_TTL", "POKET_FISH_FROM", "POKET_SHINY_RATE",
           "POKET_WILD_COOLDOWN_MIN", "POKET_WILD_COOLDOWN_MAX", "POKET_MISS_COOLDOWN", "POKET_GRASS_TTL"):
    os.environ.pop(_k, None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from common import fishing as F                              # noqa: E402
from common import hide as H                                 # noqa: E402
from common import pokelogic as P                            # noqa: E402

from app import battle_routes as BR                          # noqa: E402
from app import achievements, boosts, config, db, deps, fishing, halloween, items, main, season   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
PAST = "2000-01-01T00:00:00+00:00"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# ---------------------------------------------------------------- 도우미
class Patch(object):
    """(객체, 이름, 값) 들을 잠깐 바꾼다."""

    def __init__(self, *triples):
        self.t = triples

    def __enter__(self):
        self.old = [(o, n, getattr(o, n)) for o, n, _v in self.t]
        for o, n, v in self.t:
            setattr(o, n, v)
        return self

    def __exit__(self, *a):
        for o, n, v in reversed(self.old):
            setattr(o, n, v)


class Season(Patch):
    def __init__(self, n):
        Patch.__init__(self, (season, "SEASON", n))


def OPEN():
    return Season(config.HIDE_FROM)


def SURE():
    """숨길 수 있으면 반드시 숨긴다 - 막혀야 할 때 막혔는지 또렷이 보이게. 이벤트 '가끔' 은 끈다 (흔들리지 않게)."""
    return Patch((config, "HIDE_CHANCE", 1.0), (config, "EVENT_RESPAWN", 0.0))


def seeded(n):
    """서버 RNG(SystemRandom)를 씨앗 있는 것으로 - 숫자를 세는 검사가 흔들리지 않게."""
    return Patch((main, "RNG", random.Random(n)))


_N = [0]


def mkuser():
    _N[0] += 1
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,30,0,'','','')",
        ("숨바꼭질%d" % _N[0], b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot=0, moves=("TACKLE",)):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True
    m["moves"] = list(moves)
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=1, slot=?, moves=? WHERE id=?", (slot, json.dumps(m["moves"]), pid))
    return pid


def player(level=20):
    """파티 최저 레벨이 level 인 사람 (풀숲 레벨 = level)."""
    uid = mkuser()
    mkmon(uid, "PIDGEOTTO", level, 0, ("TACKLE", "GUST"))
    return uid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def now():
    return main.now()


def mkwild(uid, src, state="grass", secs=60, species="PIDGEY", level=5):
    """야생 행 하나 - secs 초 뒤 만료 (음수면 이미 지났다)."""
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(9), shiny_rate=10 ** 9)
    t = now()
    return db.run("INSERT INTO wild (user_id, state, species, data, throws, created_at, expires_at, src)"
                  " VALUES (?,?,?,?,0,?,?,?)",
                  (uid, state, species, json.dumps(m), main.iso(t),
                   main.iso(t + datetime.timedelta(seconds=secs)), src)).lastrowid


def due(uid):
    """있던 야생은 치우고 다음 풀숲 시각을 지난 때로 - 다음 GET /api/wild 가 돋운다."""
    db.run("DELETE FROM wild WHERE user_id=?", (uid,))
    db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET next_at=?", (uid, PAST, PAST))


def grow_api(uid, hide=None):
    """GET /api/wild 로 풀숲 차례 하나. hide=None 이면 옛 앱처럼 인자를 아예 안 보낸다. 공개 모양(wild)을 준다."""
    due(uid)
    kw = {} if hide is None else {"hide": hide}
    return main.wild_state(ctx(uid), **kw)["wild"]


def grow(uid, hide=None):
    """_make_grass 를 바로 (숫자를 세는 검사용 - 빠르다). 만든 행을 주고 지운다."""
    kw = {} if hide is None else {"hide": hide}
    row = main._make_grass(uid, **kw)
    db.run("DELETE FROM wild WHERE id=?", (row["id"],))
    return row


def src_of(row):
    return row["src"]


def timer(uid):
    """다음 풀숲까지 남은 초."""
    r = db.q1("SELECT next_at FROM wild_state WHERE user_id=?", (uid,))
    return (main.auth.parse_iso(r["next_at"]) - datetime.datetime.now(UTC)).total_seconds()


def stat(uid, col):
    r = db.q1("SELECT %s FROM wild_state WHERE user_id=?" % col, (uid,))
    return (r[col] if r else 0) or 0


def normal_gap(left, base=0):
    """보통 간격 (5~7분) 안인가 - base 는 앞에 더한 초 (숨은 포켓몬이 떠 있는 240초)."""
    return base + config.WILD_COOLDOWN_MIN - 3 <= left <= base + config.WILD_COOLDOWN_MAX + 1


# ---------------------------------------------------------------- 검사
def test_config():
    print("=== 수치 · 인자 ===")
    chk("HIDE_FROM = 7", config.HIDE_FROM == 7, getattr(config, "HIDE_FROM", None))
    chk("HIDE_CHANCE = 0.042", config.HIDE_CHANCE == 0.042, getattr(config, "HIDE_CHANCE", None))
    chk("HIDE_TTL = 240", config.HIDE_TTL == 240, getattr(config, "HIDE_TTL", None))
    chk("HIDE_MISS_NEXT = 10", config.HIDE_MISS_NEXT == 10, getattr(config, "HIDE_MISS_NEXT", None))
    # 부지런히 잡는 사람의 풀숲 한 바퀴 ≈ 400초 (설계) - 8시간이면 72바퀴 x 0.042 ≈ 3번
    per_day = 8 * 3600 / 400.0 * config.HIDE_CHANCE
    chk("하루 8시간에 약 3번 (%.2f)" % per_day, 2.7 <= per_day <= 3.3, per_day)
    sig = inspect.signature(main.wild_state)
    chk("GET /api/wild 에 hide 인자 (기본 거짓)", "hide" in sig.parameters and sig.parameters["hide"].default is False,
        str(sig))
    sig = inspect.signature(main._make_grass)
    chk("_make_grass(uid, hide=False)", "hide" in sig.parameters and sig.parameters["hide"].default is False, str(sig))
    with Season(config.HIDE_FROM - 1):
        chk("시즌 %d: 닫혀 있다" % season.SEASON, main._hide_open() is False)
    with OPEN():
        chk("시즌 %d: 열렸다" % season.SEASON, main._hide_open() is True)


def test_closed():
    print("\n=== 시즌 %d (열리기 전): hide=1 이어도 숨기지 않는다 · 풀숲은 바이트 단위로 같다 ===" % (config.HIDE_FROM - 1))
    uid = player()
    with Season(config.HIDE_FROM - 1), SURE():
        got = [grow_api(uid, True) for _ in range(120)]
        chk("GET /api/wild?hide=1 120번: 숨은 포켓몬 0", all(w and w["src"] == "grass" for w in got),
            [w["src"] for w in got if w and w["src"] != "grass"][:3])
        chk("  peek 도 없다", not [w for w in got if "peek" in w])
        rows = [db.q1("SELECT * FROM wild WHERE user_id=?", (uid,))]
        r = rows[0]
        life = (main.auth.parse_iso(r["expires_at"]) - main.auth.parse_iso(r["created_at"])).total_seconds()
        chk("  만료는 풀숲 그대로 (%d초)" % config.GRASS_TTL, life == config.GRASS_TTL, life)

        def run(hide):
            out = []
            with seeded(77):
                for _ in range(80):
                    row = grow(uid, hide)
                    out.append((row["species"], row["data"], row["src"]))
            return out
        a, b, c = run(True), run(False), run(None)
        chk("같은 씨앗이면 hide=1 · hide=0 · 인자 없음이 똑같은 풀숲 80개 (RNG 를 한 번도 더 안 쓴다)", a == b == c,
            [i for i, (x, y) in enumerate(zip(a, b)) if x != y][:3])


def test_no_flag():
    print("\n=== hide 를 안 보내면 숨은 포켓몬 0 (옛 앱 · 숨바꼭질 끈 사람) ===")
    uid = player()
    with OPEN(), SURE():
        n = sum(1 for _ in range(1000) if src_of(grow(uid)) == "hide")
        chk("_make_grass(uid) 1000번: 0", n == 0, n)
        n = sum(1 for _ in range(1000) if src_of(grow(uid, False)) == "hide")
        chk("_make_grass(uid, hide=False) 1000번: 0", n == 0, n)
        got = [grow_api(uid) for _ in range(40)]
        chk("GET /api/wild (인자 없음) 40번: 0", all(w["src"] == "grass" and "peek" not in w for w in got))
        got = [grow_api(uid, False) for _ in range(40)]
        chk("GET /api/wild?hide=0 40번: 0", all(w["src"] == "grass" for w in got))
        got = [grow_api(uid, True) for _ in range(20)]
        chk("  (대조) hide=1 이면 반드시 숨는 설정에서 20번 다 숨는다", all(w["src"] == "hide" for w in got),
            [w["src"] for w in got])


def test_chance():
    print("\n=== hide=1 로 많이 돋우면 약 %.1f%% ===" % (100 * config.HIDE_CHANCE))
    uid = player()
    with OPEN(), seeded(42):
        n, N = 0, 4000
        for _ in range(N):
            if src_of(grow(uid, True)) == "hide":
                n += 1
        rate = n / float(N)
        chk("%d번 중 %d번 = %.2f%% (3.1~5.4%%)" % (N, n, 100 * rate), 0.031 <= rate <= 0.054, rate)


def test_skip():
    print("\n=== 숨기지 않는 때: 이벤트 볼 · 업적 종 · 타입 스프레이 · 버닝 · 낚시 줄 ===")
    with OPEN(), SURE():
        uid = player()
        chk("(대조) 아무것도 없으면 숨는다", grow_api(uid, True)["src"] == "hide")

        items.bag_add(uid, config.EVENT_BALL, 1)
        w = [grow_api(uid, True) for _ in range(5)]
        row = db.q1("SELECT * FROM wild WHERE user_id=?", (uid,))
        chk("이벤트 볼을 가졌으면 이벤트 포켓몬 풀숲 (숨지 않는다)",
            all(x["src"] == "grass" for x in w) and row["species"] == config.EVENT_SPECIES, (row["species"], w[-1]))
        items.bag_take(uid, config.EVENT_BALL, 1)
        chk("  볼을 다 쓰면 다시 숨는다", grow_api(uid, True)["src"] == "hide")

        def unlock(u, rng):
            return P.make_pokemon(deps.dex().get("NIHILEGO"), 50, rng, shiny_rate=config.SHINY_RATE)
        with Patch((achievements, "unlock_mon", unlock)):
            w = [grow_api(uid, True) for _ in range(5)]
            row = db.q1("SELECT * FROM wild WHERE user_id=?", (uid,))
            chk("업적으로 풀린 종이 나올 차례면 숨지 않는다", all(x["src"] == "grass" for x in w)
                and row["species"] == "NIHILEGO", (row["species"], w[-1]))

        boosts.lure(uid, "GHOST", 60)
        w = [grow_api(uid, True) for _ in range(30)]
        chk("타입 스프레이가 켜져 있으면 30번 다 평소 풀숲", all(x["src"] == "grass" for x in w),
            [x["src"] for x in w if x["src"] != "grass"])
        db.run("UPDATE wild_state SET lure_until=NULL, lure_type=NULL WHERE user_id=?", (uid,))
        chk("  스프레이가 끝나면 다시 숨는다", grow_api(uid, True)["src"] == "hide")

        boosts.burn(uid, 60, random.Random(1))
        w = [grow_api(uid, True) for _ in range(30)]
        chk("버닝 부스터가 켜져 있으면 30번 다 평소 풀숲", all(x["src"] == "grass" for x in w),
            [x["src"] for x in w if x["src"] != "grass"])
        db.run("UPDATE wild_state SET burn_until=NULL WHERE user_id=?", (uid,))
        chk("  버닝이 끝나면 다시 숨는다", grow_api(uid, True)["src"] == "hide")

        chk("낚시가 열려 있다 (시즌 %d)" % season.SEASON, fishing.is_open())
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))
        fishing.cast(uid)                    # 입질은 3~8분 뒤 - 풀숲은 미루지 않는다 (holds_grass 거짓)
        chk("  줄을 던져 두면 line_cast 참", fishing.line_cast(uid) is True)
        w = [grow_api(uid, True) for _ in range(10)]
        chk("낚시 줄을 던져 둔 동안 (cast) 풀숲은 돋되 숨지 않는다", all(x and x["src"] == "grass" for x in w),
            [x and x["src"] for x in w])
        t = datetime.datetime.now(UTC)
        db.run("UPDATE fish_state SET state='bite', nibble_end=?, strike_end=? WHERE user_id=?",
               (fishing.iso(t + datetime.timedelta(seconds=3)), fishing.iso(t + datetime.timedelta(seconds=30)), uid))
        chk("  입질 중 (bite) 도 line_cast 참", fishing.line_cast(uid) is True)
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))
        chk("  입질 중에 풀숲을 만들어도 숨지 않는다", all(src_of(grow(uid, True)) == "grass" for _ in range(10)))
        # 아무도 안 여는 줄: 입질 시각이 FISH_HOLD_LATE 넘게 지났으면 숨바꼭질을 막지 않는다 (검토 11/27 - 영영 꺼지던 것)
        old = fishing.iso(t - datetime.timedelta(seconds=config.FISH_HOLD_LATE + 60))
        db.run("UPDATE fish_state SET state='cast', bite_at=? WHERE user_id=?", (old, uid))
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))
        chk("  입질 시각이 한참 지난 줄(아무도 안 엶)은 line_cast 거짓 · 숨는다",
            fishing.line_cast(uid) is False and grow_api(uid, True)["src"] == "hide")
        db.run("UPDATE fish_state SET bite_at=? WHERE user_id=?",
               (fishing.iso(t - datetime.timedelta(seconds=30)), uid))
        chk("  막 지난 줄(곧 앱이 엶)은 아직 참", fishing.line_cast(uid) is True)
        db.run("UPDATE fish_state SET state='idle' WHERE user_id=?", (uid,))
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))
        chk("  줄을 거두면 line_cast 거짓 · 다시 숨는다",
            fishing.line_cast(uid) is False and grow_api(uid, True)["src"] == "hide")
    with Season(config.FISH_FROM - 1), Patch((config, "HIDE_FROM", config.FISH_FROM - 1)):
        db.run("UPDATE fish_state SET state='cast' WHERE user_id=?", (uid,))
        chk("낚시가 닫혀 있으면 남은 줄은 없는 것 (line_cast 거짓)", fishing.line_cast(uid) is False)
        db.run("DELETE FROM fish_state WHERE user_id=?", (uid,))


def test_pool():
    print("\n=== 숨은 포켓몬의 종: 절반은 숨는 종 · 낚시 위주 종 없음 · 레벨 = 풀숲 · 할로윈 가중 없음 ===")
    uid = player(20)
    d = deps.dex()
    lo, hi, cap = main._wild_levels(uid)
    calls = []

    def spy():
        calls.append(1)
        return (("GHOST",), 8)
    with OPEN(), SURE(), seeded(5), Patch((halloween, "spawn_boost", spy)):
        rows = [grow(uid, True) for _ in range(1200)]
        mons = [json.loads(r["data"]) for r in rows]
        chk("1200번 다 숨은 포켓몬 (src='hide', state='grass')",
            all(r["src"] == "hide" and r["state"] == "grass" for r in rows))
        base, _c, total = d.spawn_pool(hi, cap, None, fishing.grass_exclude())
        p = sum(s.get("weight", 0) for s in base if s["internal"] in H.HIDERS) / float(total)
        want = H.HIDE_SHARE + (1 - H.HIDE_SHARE) * p
        got = sum(1 for m in mons if m["species"] in H.HIDERS) / float(len(mons))
        chk("숨는 종 몫 %.3f ≈ %.3f (절반 + 평소 표의 숨는 종)" % (got, want), abs(got - want) < 0.05, (got, want))
        chk("낚시 위주 종 없음", not [m["species"] for m in mons if m["species"] in F.FISH_ONLY])
        chk("레벨 = 풀숲 (Lv%d~%d)" % (lo, hi), all(lo <= m["level"] <= hi for m in mons),
            sorted(set(m["level"] for m in mons)))
        chk("할로윈 가중을 부르지 않는다 (숨는 차례 1200번에 0번)", not calls, len(calls))
        g = [grow(uid, False) for _ in range(5)]
        chk("  (대조) 평소 풀숲은 할로윈을 부른다", calls and all(r["src"] == "grass" for r in g), len(calls))


def test_hidden_ability():
    print("\n=== 숨겨진 특성: 숨은 포켓몬 ≈ 1/4, 풀숲 ≈ 1/128 · 이로치는 그대로 ===")
    uid = player(20)
    d = deps.dex()
    with OPEN(), SURE(), seeded(9):
        mons = [json.loads(grow(uid, True)["data"]) for _ in range(1500)]
        has = [m for m in mons if d.get(m["species"]).get("hidden")]
        rate = sum(1 for m in has if m["hiddenAbility"]) / float(len(has))
        chk("숨은 포켓몬 (숨겨진 특성이 있는 종 %d마리) %.3f ≈ 0.25" % (len(has), rate), 0.20 <= rate <= 0.30, rate)
        chk("  숨겨진 특성이 없는 종은 평소 특성",
            all(not m["hiddenAbility"] for m in mons if not d.get(m["species"]).get("hidden")))
        grass = [json.loads(grow(uid, False)["data"]) for _ in range(3000)]
        has = [m for m in grass if d.get(m["species"]).get("hidden")]
        rate2 = sum(1 for m in has if m["hiddenAbility"]) / float(len(has))
        chk("풀숲 (%d마리) %.4f ≈ 1/128 (≤ 0.02)" % (len(has), rate2), rate2 <= 0.02, rate2)
    with OPEN(), SURE(), seeded(10), Patch((config, "SHINY_RATE", 2)):
        a = sum(1 for _ in range(400) if json.loads(grow(uid, True)["data"])["shiny"]) / 400.0
        b = sum(1 for _ in range(400) if json.loads(grow(uid, False)["data"])["shiny"]) / 400.0
        chk("이로치 확률은 SHINY_RATE 그대로 (1/2 로 두면 숨은 것 %.2f · 풀숲 %.2f)" % (a, b),
            0.4 <= a <= 0.6 and 0.4 <= b <= 0.6, (a, b))


PUBLIC_KEYS = {"id", "state", "throws", "expiresAt", "createdAt", "expiresIn", "src", "bloom"}


def test_peek():
    print("\n=== 공개 전 peek: {num, form} 만 ===")
    uid = player(20)
    d = deps.dex()
    with OPEN(), SURE():
        w = grow_api(uid, True)
        row = db.q1("SELECT * FROM wild WHERE id=?", (w["id"],))
        mon = json.loads(row["data"])
        sp = d.get(mon["species"])
        chk("숨은 행: src='hide', state='grass'", w["src"] == "hide" and w["state"] == "grass", w)
        chk("  공개 모양 칸 = 평소 칸 + peek", set(w) == PUBLIC_KEYS | {"peek"}, sorted(w))
        chk("  peek = {num, form} 뿐", isinstance(w.get("peek"), dict) and set(w["peek"]) == {"num", "form"}, w.get("peek"))
        chk("  num 은 그 종의 도감 번호 (int), form 은 None (야생은 폼이 없다)",
            w["peek"]["num"] == sp["num"] and isinstance(w["peek"]["num"], int) and w["peek"]["form"] is None,
            (w["peek"], sp["num"]))
        txt = json.dumps(w, ensure_ascii=False)
        leak = [k for k in ("pokemon", "species", "ability", "hiddenAbility", "shiny", "level", "nature",
                            mon["species"], sp["kr"]) if k in txt]
        chk("  종 이름 · 특성 · 이로치 · 레벨 없음", not leak, leak)
        g = grow_api(uid, False)
        chk("보통 풀숲엔 peek 없음 (칸도 그대로)", "peek" not in g and set(g) == PUBLIC_KEYS, sorted(g))
        w = grow_api(uid, True)                  # (위의 보통 풀숲을 돋우며 앞의 숨은 행은 치웠다)
        r = main.wild_reveal(w["id"], ctx(uid))
        chk("드러낸 뒤에는 peek 없음 · pokemon 있음 (src 는 hide 그대로)",
            "peek" not in r["wild"] and r["wild"].get("pokemon") and r["wild"]["src"] == "hide", sorted(r["wild"]))
        fid = mkwild(uid, "fish", "revealed")
        f = main._wild_public(db.q1("SELECT * FROM wild WHERE id=?", (fid,)), True)
        chk("낚은 야생에도 peek 없음", "peek" not in f)
        db.run("DELETE FROM wild WHERE user_id=?", (uid,))


def test_ttl_and_next():
    print("\n=== 만료 240초 · 다음 풀숲 240+쿨다운 · 놓치면 10초 · 잡으면 보통 ===")
    uid = player(20)
    items.bag_add(uid, "MASTERBALL", 5)
    with OPEN(), SURE():
        w = grow_api(uid, True)
        row = db.q1("SELECT * FROM wild WHERE id=?", (w["id"],))
        life = (main.auth.parse_iso(row["expires_at"]) - main.auth.parse_iso(row["created_at"])).total_seconds()
        chk("expiresIn ≈ 240 (%s) · 행의 수명 %d초" % (w["expiresIn"], life),
            config.HIDE_TTL - 2 <= w["expiresIn"] <= config.HIDE_TTL and life == config.HIDE_TTL, (w["expiresIn"], life))
        left = timer(uid)
        chk("다음 풀숲 예약 = 240 + 보통 간격 (%.0f초)" % left, normal_gap(left, config.HIDE_TTL), left)

        fled = stat(uid, "fled")
        db.run("UPDATE wild SET expires_at=? WHERE id=?", (main.iso(now() - datetime.timedelta(seconds=1)), w["id"]))
        gone = main._sweep(uid)
        left = timer(uid)
        chk("못 찾고 만료 (_sweep): 다음 풀숲 %.0f초 뒤 (≤ %d)" % (left, config.HIDE_MISS_NEXT),
            gone == [w["id"]] and config.HIDE_MISS_NEXT - 3 <= left <= config.HIDE_MISS_NEXT, (gone, left))
        chk("  도망 +1 (지금 풀숲처럼)", stat(uid, "fled") == fled + 1)

        w = grow_api(uid, True)
        db.run("UPDATE wild SET expires_at=? WHERE id=?", (main.iso(now() - datetime.timedelta(seconds=2)), w["id"]))
        main.wild_flee(w["id"], ctx(uid))
        left = timer(uid)
        chk("만료 뒤 앱의 놓아주기 (flee): %.0f초 뒤 (≤ %d)" % (left, config.HIDE_MISS_NEXT),
            config.HIDE_MISS_NEXT - 3 <= left <= config.HIDE_MISS_NEXT, left)

        w = grow_api(uid, True)
        main.wild_reveal(w["id"], ctx(uid))
        c = main.wild_catch(w["id"], main.CatchIn(ball="MASTERBALL"), ctx(uid))
        left = timer(uid)
        chk("찾고 잡으면 보통 간격 (%.0f초)" % left, c.get("caught") is True and normal_gap(left), (c.get("caught"), left))

        w = grow_api(uid, True)
        main.wild_reveal(w["id"], ctx(uid))
        db.run("UPDATE wild SET expires_at=? WHERE id=?", (main.iso(now() - datetime.timedelta(seconds=1)), w["id"]))
        main._sweep(uid)
        left = timer(uid)
        chk("찾은 뒤 시간이 다 되어 도망가면 보통 간격 (%.0f초 - 찾은 것은 놓친 것이 아니다)" % left, normal_gap(left), left)


def test_early_flee():
    print("\n=== 공개 전 이른 도망은 보통 간격 · 진짜 만료 뒤 도망만 짧게 (풀숲 · 숨은 것 둘 다) ===")
    cases = (
        # (이름, src, state, 만료까지 초, 기대: 'normal' / 상한 초)
        ("풀숲 60초 남기고 도망", "grass", "grass", 60, "normal"),
        ("풀숲 만료 3초 전 도망 (5초 여유 안)", "grass", "grass", 3, config.MISS_COOLDOWN),
        ("풀숲 만료 1초 뒤 도망", "grass", "grass", -1, config.MISS_COOLDOWN),
        ("숨은 것 200초 남기고 도망", "hide", "grass", 200, "normal"),
        ("숨은 것 만료 3초 전 도망", "hide", "grass", 3, config.HIDE_MISS_NEXT),
        ("숨은 것 만료 1초 뒤 도망", "hide", "grass", -1, config.HIDE_MISS_NEXT),
        ("드러낸 풀숲 야생 30초 남기고 도망 (지금처럼 보통)", "grass", "revealed", 30, "normal"),
        ("드러낸 숨은 야생 만료 뒤 도망 (찾았으니 보통)", "hide", "revealed", -1, "normal"),
    )
    for name, src, state, secs, want in cases:
        uid = player(20)
        wid = mkwild(uid, src, state, secs)
        main.wild_flee(wid, ctx(uid))
        left = timer(uid)
        gone = db.q1("SELECT id FROM wild WHERE id=?", (wid,)) is None
        if want == "normal":
            chk("%s: 보통 간격 (%.0f초)" % (name, left), gone and normal_gap(left), left)
        else:
            chk("%s: %.0f초 (≤ %d)" % (name, left, want), gone and want - 3 <= left <= want, left)
    uid = player(20)
    wid = mkwild(uid, "hide", "grass", 100)
    row = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
    deps.end_wild(uid, row, "wild_expired")
    chk("end_wild 'wild_expired' 를 이르게 불러도 만료 시각 전이면 보통 간격", normal_gap(timer(uid)), timer(uid))
    pin = "2031-01-01T00:00:00+00:00"
    db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", (pin, uid))
    row = db.q1("SELECT * FROM wild WHERE id=?", (mkwild(uid, "fish", "revealed", -1),))
    deps.end_wild(uid, row, "wild_expired")
    chk("낚은 야생은 지금처럼 풀숲 시계를 안 건드린다",
        db.q1("SELECT next_at FROM wild_state WHERE user_id=?", (uid,))["next_at"] == pin)


def test_reveal_catch():
    print("\n=== 숨은 행 reveal → 평소 야생 (잡기 · 배틀 · 떨굼 그대로) ===")
    uid = player(20)
    items.bag_add(uid, "MASTERBALL", 5)
    with OPEN(), SURE(), Patch((config, "DROP_ON_CATCH", 1.0)):
        w = grow_api(uid, True)
        r = main.wild_reveal(w["id"], ctx(uid))
        pub = r["wild"]
        chk("reveal: state='revealed' · pokemon · 야생 60초", pub["state"] == "revealed" and pub.get("pokemon")
            and pub["expiresIn"] <= config.WILD_TTL and pub["pokemon"].get("info"), sorted(pub))
        chk("  pokemon 에 hiddenAbility 가 실린다 (앱이 '숨겨진 특성!')", "hiddenAbility" in pub["pokemon"])
        chk("  볼 목록도 그대로", isinstance(r.get("ballOptions"), list) and r["ballOptions"])
        before = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
        c = main.wild_catch(w["id"], main.CatchIn(ball="MASTERBALL"), ctx(uid))
        after = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
        chk("배틀 밖 볼로 잡기 · 한 마리 늘었다", c.get("caught") is True and after == before + 1, (c.get("caught"), after))
        chk("  도구를 떨군다 (낚은 것과 달리)", c.get("drop") is not None, c.get("drop"))

        w = grow_api(uid, True)
        main.wild_reveal(w["id"], ctx(uid))
        b = BR.start(w["id"], ctx(uid))
        bid = b["battle"]["id"]
        chk("배틀을 건다", bid and b["battle"].get("result") in (None, ""), b["battle"].get("result"))
        t = BR.throw_ball(bid, BR.BallIn(ball="MASTERBALL"), ctx(uid))
        chk("  배틀 중 볼로 잡기", t.get("caught") is True, t.get("caught"))
        chk("  야생 행이 없고 다음 풀숲은 보통 간격 (%.0f초)" % timer(uid),
            db.q1("SELECT id FROM wild WHERE id=?", (w["id"],)) is None and normal_gap(timer(uid)), timer(uid))
        w = grow_api(uid, True)
        r1 = main.wild_reveal(w["id"], ctx(uid))
        r2 = main.wild_reveal(w["id"], ctx(uid))
        chk("두 번 reveal 해도 같은 야생 (평소처럼)", r2["wild"]["state"] == "revealed"
            and r1["wild"]["pokemon"]["species"] == r2["wild"]["pokemon"]["species"])


def main_():
    db.init()
    for t in (test_config, test_closed, test_no_flag, test_chance, test_skip, test_pool, test_hidden_ability,
              test_peek, test_ttl_and_next, test_early_flee, test_reveal_catch):
        try:
            t()
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            chk("%s 이 끝까지 돈다" % t.__name__, False, repr(e))
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
