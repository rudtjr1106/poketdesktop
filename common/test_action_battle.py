# -*- coding: utf-8 -*-
"""액션 배틀 판 검사.

    python common/test_action_battle.py

서버도 DB 도 없이 common/action_battle.py 만 굴린다. 판 시계는 step() 한 번이 TICK (1/30초).

제일 중요한 것.
  · **걸어서 비키는 것이 명중률이다.** 예고(광선 · 내려찍기)를 보고 비키면 안 맞는다. 피하기(대시 · 무적)는 없다
    (2026-11-19 '너무 사기다') - 'dodge' 를 눌러도 아무 일 없다. 회피 랭크는 걷는 빠르기 (한 랭크 6%, ±36%).
  · **상대에게 숨기는 것.** 상대 F 에 체력 · 쿨타임 · PP 가 없고, 상대 팀 보기에 기술 · 도구가 없다.
  · **같은 시드 · 같은 입력 = 같은 판.**
  · **판 길이.** 마주 보고 기술만 쏟아붓는 봇끼리 한 마리를 쓰러뜨리는 데 4~30초 (DAMAGE_SCALE 0.42),
    3 대 3 한 판은 FIGHT_SEC (120초) 안에 쓰러뜨려 끝난다 (2026-11-19 '루즈하다' → 0.3 · 8~60초 · 180초에서 줄였다).
  · **손맛.** 맞으면 잠깐 경직 (하던 준비는 안 끊긴다, 1초에 0.35초까지) · 탄도 조금 민다 · 근접은 70 민다.
"""
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import action_battle as AB                # noqa: E402
from common import action_moves as AM                 # noqa: E402
from common import attackfx as AF                     # noqa: E402
from common import pokelogic as P                     # noqa: E402

DEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "server", "data", "pokedex.json")
OK = FAIL = 0
DEX = None
SEQ = [0]


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


# ---------------------------------------------------------------- 도우미
def mon(species, moves):
    """Lv.80 으로 만든다 - 판이 50 으로 맞추는지도 같이 본다."""
    m = P.make_pokemon(DEX.get(species), 80, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    m["moves"] = list(moves)
    return m


def battle(a, b, seed=7, **kw):
    """a, b = [(종, [기술..]), ...]."""
    kw.setdefault("pick_sec", 1)
    kw.setdefault("ready_sec", 0.5)
    return AB.ActionBattle(DEX, [mon(*x) for x in a], [mon(*x) for x in b], seed, names=("가", "나"), **kw)


def fight(a, b, **kw):
    """고르기(앞에서부터) · 준비를 지나 싸움이 막 시작한 판. a 는 왼쪽 (500, 450), b 는 오른쪽 (900, 450)."""
    return start(battle(a, b, **kw))


def start(ab):
    """battle() 로 만든 판을 싸움 시작까지 (그 전에 팀 dict 를 고쳐 둘 수 있다 - 도구 ...)."""
    for w in ("a", "b"):
        ab.pick(w, list(range(min(AB.TEAM, len(ab.sides[w].team)))))
    while ab.phase != "fight":
        ab.step()
    place(ab, "a", 500, 450)
    place(ab, "b", 900, 450)
    ab.drain_events()
    return ab


def seq():
    SEQ[0] += 1
    return SEQ[0]


def run(ab, sec):
    out = []
    for _ in range(int(round(sec / AB.TICK))):
        ab.step()
        out.extend(ab.drain_events())
    return out


def run_until(ab, cond, sec=5.0):
    out = []
    for _ in range(int(round(sec / AB.TICK))):
        ab.step()
        out.extend(ab.drain_events())
        if cond(out):
            break
    return out


def press(ab, w, key):
    ab.press(w, key, seq())


def walk(ab, w, x, y):
    ab.set_move(w, x, y, seq())


def place(ab, w, x, y):
    s = ab.sides[w]
    s.x, s.y = float(x), float(y)


def of(evs, name, **kw):
    return [e for e in evs if e["e"] == name and all(e.get(k) == v for k, v in kw.items())]


def me(ab, w):
    return ab.snapshot(w)["f"][w]


# ---------------------------------------------------------------- 고르기 · 단계
def t_pick():
    print("== 고르기")
    team5 = [("PIKACHU", ["THUNDERSHOCK"]), ("EEVEE", ["TACKLE"]), ("PIDGEY", ["GUST"]), ("RATTATA", ["TACKLE"]),
             ("ZUBAT", ["BITE"])]
    ab = battle(team5, [("SNORLAX", ["TACKLE"]), ("ONIX", ["TACKLE"])])
    chk("처음은 고르기", ab.phase == "pick")
    chk("같은 칸 두 번은 안 된다", not ab.pick("a", [0, 0, 1]))
    chk("셋을 골라야 한다", not ab.pick("a", [0, 1]))
    chk("없는 칸은 안 된다", not ab.pick("a", [0, 1, 9]))
    chk("서로 다른 셋은 된다", ab.pick("a", [4, 2, 0]))
    chk("두 번째 고르기는 안 된다", not ab.pick("a", [1, 2, 3]))
    s = ab.snapshot("b")
    chk("고르기 중엔 누가 골랐는지만 보인다", s["pick"] == {"a": True, "b": False} and s["f"] == {}, s["pick"])
    chk("팀이 셋보다 적으면 전부", ab.pick("b", [1, 0]))
    ev = run(ab, AB.TICK)
    chk("둘 다 고르면 바로 준비", ab.phase == "ready" and of(ev, "phase", ph="ready"), ab.phase)
    team = me(ab, "a")["team"]
    chk("고른 순서대로 나선다 (slot 은 원래 팀 칸)", [x["slot"] for x in team] == [4, 2, 0], team)
    chk("첫째가 나와 있다", me(ab, "a")["i"] == 0 and me(ab, "b")["i"] == 0)
    chk("고르기가 끝나면 못 바꾼다", not ab.pick("b", [0]))
    ev = run(ab, 0.5)
    chk("준비가 끝나면 싸움", ab.phase == "fight" and of(ev, "phase", ph="fight"), ab.phase)

    ab = battle(team5, team5, pick_sec=1)
    ab.pick("b", [3, 1, 0])
    run(ab, 0.9)
    chk("시간 안엔 기다린다", ab.phase == "pick")
    run(ab, 0.2)
    chk("안 고르면 앞 3마리", [x["slot"] for x in me(ab, "a")["team"]] == [0, 1, 2], me(ab, "a")["team"])
    chk("고른 쪽은 고른 그대로", [x["slot"] for x in me(ab, "b")["team"]] == [3, 1, 0])
    chk("레벨은 50 으로 맞춘다", all(m.f.level == AB.LEVEL for m in ab.sides["a"].mons))


# ---------------------------------------------------------------- 이동
def t_walk():
    print("== 이동 · 벽")
    ab = fight([("SNORLAX", ["TACKLE"])], [("PIDGEY", ["GUST"])])
    s = ab.sides["a"]
    want = 180 + 0.9 * max(20, min(250, s.mon.f.stat("spe")))
    place(ab, "a", 300, 200)
    place(ab, "b", 1300, 800)
    walk(ab, "a", 1, 0)
    x0 = s.x
    run(ab, 1.0)
    chk("이동 속도 = 180 + 0.9 × 스피드", abs((s.x - x0) - want) < 1.0, (s.x - x0, want))
    chk("내 F 에 걷는 빠르기 (예측용)", abs(me(ab, "a")["spd"] - want) < 0.11, (me(ab, "a")["spd"], want))
    chk("걷는 모습 · 오른쪽을 본다", me(ab, "a")["st"] == "walk" and me(ab, "a")["d"] == 2, me(ab, "a"))
    walk(ab, "a", 1, 1)
    x0, y0 = s.x, s.y
    run(ab, 0.5)
    chk("대각선도 같은 빠르기 (길이 1 로 줄인다)", abs(math.hypot(s.x - x0, s.y - y0) - want * 0.5) < 1.0)
    chk("오른아래를 본다", me(ab, "a")["d"] == 1, me(ab, "a")["d"])
    s.mon.f.status = "paralysis"
    chk("마비면 느리다 (Fighter.stat)", me(ab, "a")["spd"] < want, me(ab, "a")["spd"])
    s.mon.f.status = None
    place(ab, "a", 60, 60)
    walk(ab, "a", -1, -1)
    run(ab, 0.5)
    chk("벽에 막힌다 (왼 · 위)", s.x == AB.BODY_R and s.y == AB.BODY_R, (s.x, s.y))
    place(ab, "a", AB.ARENA_W - 40, AB.ARENA_H - 40)
    walk(ab, "a", 1, 1)
    run(ab, 0.5)
    chk("벽에 막힌다 (오른 · 아래)", s.x == AB.ARENA_W - AB.BODY_R and s.y == AB.ARENA_H - AB.BODY_R, (s.x, s.y))
    walk(ab, "a", 0, 0)
    run(ab, AB.TICK)
    chk("멈추면 서 있다", me(ab, "a")["st"] == "idle")

    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "a", 800, 450)
    place(ab, "b", 820, 450)
    run(ab, AB.TICK)
    a, b = ab.sides["a"], ab.sides["b"]
    chk("몸끼리는 겹치지 않는다", math.hypot(a.x - b.x, a.y - b.y) >= 2 * AB.BODY_R - 0.01,
        math.hypot(a.x - b.x, a.y - b.y))


# ---------------------------------------------------------------- 맞기 · 비키기
def t_shot():
    print("== 탄")
    ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["TACKLE"])])
    press(ab, "a", "m0")
    ev = run(ab, AB.TICK)
    c = of(ev, "cast", w="a")
    chk("cast 이벤트 (꼴 · 타입 · 모양 · 각)", c and c[0]["kind"] == "proj" and c[0]["k"] == "WATERGUN"
        and c[0]["ty"] == "WATER" and c[0]["sty"] == "jet" and c[0]["m"] == 0 and c[0]["ang"] == 0, c)
    chk("준비 중", me(ab, "a")["st"] == "wind" and me(ab, "a")["sm"] == 0, me(ab, "a"))
    ev = run(ab, 1.5)
    hits = of(ev, "hit", w="a", v="b")
    chk("탄이 맞으면 체력이 준다", hits and hits[0]["dmg"] > 0 and hits[0]["hpr"] < 1000, hits)
    chk("맞은 쪽 hpr 도 준다", me(ab, "a")["hpr"] == 1000 and ab.snapshot("a")["f"]["b"]["hpr"] < 1000)
    chk("내 체력은 정확히", me(ab, "b")["hp"] == ab.sides["b"].mon.f.hp < ab.sides["b"].mon.f.maxhp)
    chk("PP 하나 썼다", me(ab, "a")["pp"] == [AM.kit(DEX, "WATERGUN")["pp"] - 1], me(ab, "a")["pp"])
    chk("맞은 탄은 사라진다", ab.snapshot("a")["p"] == [])
    dmg = hits[0]["dmg"]
    f_a, f_b = ab.sides["a"].mon.f, ab.sides["b"].mon.f
    chk("데미지는 본가 공식 × %.2f 언저리" % AB.DAMAGE_SCALE, 1 <= dmg <= f_b.maxhp * 0.4 * AB.DAMAGE_SCALE,
        (dmg, f_b.maxhp, f_a.stat("spa")))


def t_no_dodge():
    print("== 피하기는 없다 (2026-11-19 '너무 사기다' - 걷기 · 교체로만 비킨다)")
    chk("KEYS 에 dodge 가 없다 · DODGE_ 상수도 없다", "dodge" not in AB.KEYS and not [k for k in dir(AB) if "DODGE" in k],
        AB.KEYS)

    def shoot(dodge):
        """탄이 다가올 때 b 가 왼쪽(탄 쪽)으로 걸으며 dodge 를 누른다 (dodge=False 면 걷기만)."""
        ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["TACKLE"])])
        b = ab.sides["b"]
        press(ab, "a", "m0")
        evs = run_until(ab, lambda _: ab.shots and ab.shots[0].x >= b.x - 110, 2.0)
        walk(ab, "b", -1, 0)
        if dodge:
            press(ab, "b", "dodge")
        evs += run(ab, AB.TICK)
        f = me(ab, "b")
        evs += run(ab, 0.8)
        return ab, evs, f

    ab0, ev0, f0 = shoot(False)
    ab1, ev1, f1 = shoot(True)
    b0, b1 = ab0.sides["b"], ab1.sides["b"]
    chk("press('dodge') 는 버린다: 이벤트가 안 누른 판과 같다 (dodge 이벤트 없음)", ev1 == ev0 and not of(ev1, "dodge"),
        [e["e"] for e in ev1])
    chk("  다음 틱의 내 F 도 같다 (걷기 그대로 · 무적 없음 · st walk)", f1 == f0 and f1["st"] == "walk" and not f1["inv"],
        (f0, f1))
    chk("  움직임도 같다 (밀려남 없음)", (b1.x, b1.y) == (b0.x, b0.y) and b1.push is None, ((b0.x, b0.y), (b1.x, b1.y)))
    chk("  무적으로 지나가지 않고 맞는다", of(ev1, "hit", v="b"), [e["e"] for e in ev1])

    ab = fight([("BLASTOISE", ["WATERGUN", "TACKLE"])], [("SNORLAX", ["TACKLE"])])
    a = ab.sides["a"]
    press(ab, "a", "m0")
    run_until(ab, lambda _: a.cast is not None and a.cast.stage == "rec", 2.0)
    press(ab, "a", "m1")
    press(ab, "a", "dodge")
    chk("  들고 있던 키를 dodge 가 덮지 않는다", a.buf is not None and a.buf[0] == "m1", a.buf)
    c = a.cast
    run(ab, AB.TICK)
    chk("  회복을 끊지 않는다", a.cast is c and me(ab, "a")["st"] == "rec", me(ab, "a")["st"])
    run(ab, 2.0)
    x0, y0 = a.x, a.y
    press(ab, "a", "dodge")
    ev = run(ab, 0.3)
    chk("  아무것도 안 할 때 눌러도 아무 일 없다", not ev and me(ab, "a")["st"] == "idle" and a.buf is None
        and (a.x, a.y) == (x0, y0), (ev, me(ab, "a")["st"], a.buf))

    ab = fight(TEAM_A, TEAM_B, seed=4)
    sts, keys, ev = set(), set(), []
    for _ in range(int(20 / AB.TICK)):
        if ab.phase == "over":
            break
        bot(ab, "a", ab.tick)
        bot(ab, "b", ab.tick + 1)
        if ab.tick % 5 == 0:
            ab.press("a", "dodge", ab.tick)
            ab.press("b", "dodge", ab.tick)
        ab.step()
        ev += ab.drain_events()
        for w in ("a", "b"):
            for f in ab.snapshot(w)["f"].values():
                sts.add(f["st"])
                keys |= set(f)
    chk("dodge 를 섞어 누르는 봇 판 20초: st dodge · dcd · dodge 이벤트가 한 번도 없다",
        "dodge" not in sts and "dcd" not in keys and not of(ev, "dodge") and of(ev, "hit"), (sorted(sts), sorted(keys)))


def t_eva_walk():
    print("== 회피 랭크 = 걷는 빠르기 (한 랭크 %d%%, ±6 에서 멈춘다) · 명중 랭크 = 탄 빠르기" % round(AB.EVA_WALK * 100))

    def walked(eva):
        ab = fight([("SNORLAX", ["TACKLE"])], [("PIDGEY", ["GUST"])])
        s = ab.sides["a"]
        s.mon.f.stages["eva"] = eva
        place(ab, "a", 300, 200)
        place(ab, "b", 1300, 800)
        walk(ab, "a", 1, 0)
        x0 = s.x
        run(ab, 1.0)
        return s.x - x0, me(ab, "a")["spd"], 180 + 0.9 * max(20, min(250, s.mon.f.stat("spe")))

    base, _, plain = walked(0)
    chk("회피 0: 그대로 (180 + 0.9 × 스피드)", abs(base - plain) < 1.0, (base, plain))
    for eva, mult in ((2, 1.12), (-2, 0.88), (6, 1.36), (-6, 0.64), (9, 1.36), (-9, 0.64)):
        d, spd, _ = walked(eva)
        chk("회피 %+d: 걷는 빠르기 × %.2f (%.1f / %.1f)" % (eva, mult, d, base),
            abs(d - base * mult) < 1.0 and abs(spd - plain * mult) < 0.06, (d, base * mult, spd, plain * mult))

    ab = fight([("SNORLAX", ["DOUBLETEAM", "MINIMIZE"])], [("PIDGEY", ["GUST"])])
    s = ab.sides["a"]
    v0 = ab._walk_speed(s)
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    chk("그림자분신(회피 +1)을 쓰면 6% 빨리 걷는다", of(ev, "stat", w="a", st="eva", d=1)
        and abs(ab._walk_speed(s) - v0 * 1.06) < 1e-6, (ab._walk_speed(s), v0))
    for _ in range(3):
        press(ab, "a", "m1")
        run(ab, AM.kit(DEX, "MINIMIZE")["cd"] + 0.6)
    chk("  작아지기를 거듭 써도 +6 (36%) 에서 멈춘다", s.mon.f.stages["eva"] == 6
        and abs(ab._walk_speed(s) - v0 * 1.36) < 1e-6, (s.mon.f.stages["eva"], ab._walk_speed(s) / v0))

    for acc, mult in ((0, 1.0), (2, 5 / 3.0)):
        ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["TACKLE"])])
        ab.sides["a"].mon.f.stages["acc"] = acc
        press(ab, "a", "m0")
        run_until(ab, lambda _: ab.shots, 2.0)
        v = math.hypot(ab.shots[0].vx, ab.shots[0].vy) if ab.shots else 0
        chk("명중 %+d: 탄 빠르기 × %.2f (그대로)" % (acc, mult), abs(v - AM.kit(DEX, "WATERGUN")["speed"] * mult) < 0.01,
            v)


# ---------------------------------------------------------------- 쿨타임 · PP · 버퍼
def t_cooldown():
    print("== 쿨타임 · PP · 버퍼")
    ab = fight([("BLASTOISE", ["HYDROPUMP", "WATERGUN"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 1500, 100)
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    chk("(한 번 나갔다)", len(of(ev, "cast", w="a")) == 1)
    cd = me(ab, "a")["cd"][0]
    chk("쿨타임이 보인다", 0 < cd <= AM.kit(DEX, "HYDROPUMP")["cd"], cd)
    press(ab, "a", "m0")
    ev = run(ab, 0.5)
    chk("쿨타임 동안 다시 안 나간다", not of(ev, "cast"))
    run(ab, cd)
    press(ab, "a", "m0")
    ev = run(ab, AB.TICK)
    chk("쿨타임이 지나면 나간다", of(ev, "cast", k="HYDROPUMP"))
    run(ab, 4.0)

    ab.sides["a"].mon.pp[0] = 0
    ab.sides["a"].mon.ready[0] = 0.0
    press(ab, "a", "m0")
    ev = run(ab, 0.5)
    chk("PP 0 이면 안 나간다", not of(ev, "cast"))
    press(ab, "a", "m1")
    ev = run(ab, AB.TICK)
    chk("다른 기술은 나간다", of(ev, "cast", k="WATERGUN"))
    run(ab, 4.0)
    ab.sides["a"].mon.pp[1] = 0
    press(ab, "a", "m0")
    ev = run(ab, AB.TICK)
    chk("다 떨어지면 발버둥", of(ev, "cast", k="STRUGGLE", m=0), of(ev, "cast"))
    run(ab, 1.0)
    press(ab, "a", "m1")
    ev = run(ab, 0.5)
    chk("발버둥은 칸을 바꿔도 대기가 같다", not of(ev, "cast") and me(ab, "a")["cd"][1] > 0, me(ab, "a")["cd"])

    ab = fight([("SNORLAX", ["TACKLE"])], [("GENGAR", ["LICK"])])
    place(ab, "b", 580, 450)
    ab.sides["a"].mon.pp[0] = 0
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    hit = of(ev, "hit", v="b", k="STRUGGLE")
    chk("발버둥은 타입이 없어 고스트도 친다", hit and hit[0]["dmg"] > 0 and of(ev, "hit", v="a", w="a"), ev)

    ab = fight([("SNORLAX", ["TACKLE", "BODYSLAM"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 1500, 100)
    tackle = AM.kit(DEX, "TACKLE")
    busy = tackle["wind"] + tackle["act"] + tackle["rec"]
    press(ab, "a", "m0")
    run(ab, 2 * AB.TICK)
    press(ab, "a", "m1")
    ev = run(ab, busy + 0.3)
    chk("바쁠 때 누른 키는 0.25초 지나면 버린다", not of(ev, "cast", k="BODYSLAM"))
    run(ab, 3.0)
    press(ab, "a", "m0")
    run(ab, busy - 0.15)
    press(ab, "a", "m1")
    ev = run(ab, 0.3)
    chk("끝나기 직전에 누른 키는 들고 있다가 쓴다", of(ev, "cast", k="BODYSLAM"))


# ---------------------------------------------------------------- 상태이상
def status_on(move, target=("SNORLAX", ["TACKLE", "BODYSLAM"])):
    ab = fight([("GENGAR", [move, "THUNDERBOLT"])], [target])
    place(ab, "b", 800, 450)
    press(ab, "a", "m0")
    ev = run_until(ab, lambda e: of(e, "status", w="b") or of(e, "txt", w="b"), 3.0)
    return ab, ev


def t_status():
    print("== 상태이상")
    ab, ev = status_on("WILLOWISP")
    chk("도깨비불 → 화상", of(ev, "status", w="b", s="brn") and me(ab, "b")["s"] == "brn", ev)
    f = ab.sides["b"].mon.f
    hp0 = f.hp
    ev = run(ab, 1.9)
    chk("2초 안엔 안 깎인다", f.hp == hp0, (hp0, f.hp))
    ev = run(ab, 0.2)
    chip = of(ev, "hit", v="b", k="brn")
    chk("2초마다 최대 체력 1/32", chip and hp0 - f.hp == f.maxhp // 32 and chip[0]["dmg"] == f.maxhp // 32,
        (hp0 - f.hp, f.maxhp // 32, chip))
    run(ab, 2.0)
    chk("또 2초 뒤 또 깎인다", hp0 - f.hp == 2 * (f.maxhp // 32))

    ab, ev = status_on("WILLOWISP", ("CHARMANDER", ["SCRATCH"]))
    chk("불꽃 타입은 화상에 안 걸린다 ('효과가 없는 것 같다')", not of(ev, "status")
        and of(ev, "txt", w="b", msg="효과가 없는 것 같다..."), ev)
    ab, ev = status_on("WILLOWISP")
    press(ab, "a", "m0")
    ab.sides["a"].mon.ready[0] = 0.0
    ev = run_until(ab, lambda e: of(e, "txt", w="b"), 3.0)
    chk("이미 상태이상이면 '실패했다'", of(ev, "txt", w="b", msg="하지만 실패했다!"), ev)
    ab, ev = status_on("TOXIC", ("STEELIX", ["TACKLE"]))
    chk("강철 타입은 독에 안 걸린다", not of(ev, "status"), ev)
    ab, ev = status_on("THUNDERWAVE", ("GOLEM", ["TACKLE"]))
    chk("땅 타입에게 전기자석파는 효과가 없다", not of(ev, "status"), ev)
    ab, ev = status_on("SPORE", ("BULBASAUR", ["TACKLE"]))
    chk("풀 타입에게 가루는 안 통한다", not of(ev, "status"), ev)

    ab, ev = status_on("TOXIC")
    f = ab.sides["b"].mon.f
    hp0 = f.hp
    run(ab, 2.05)
    d1 = hp0 - f.hp
    run(ab, 2.0)
    d2 = hp0 - f.hp - d1
    chk("맹독은 점점 세다 (n/48)", me(ab, "b")["s"] == "tox" and d1 == f.maxhp // 48 and d2 == 2 * f.maxhp // 48,
        (d1, d2, f.maxhp))

    ab, ev = status_on("HYPNOSIS")
    chk("최면술 → 잠듦", me(ab, "b")["s"] == "slp" and me(ab, "b")["st"] == "sleep", me(ab, "b"))
    b = ab.sides["b"]
    x0 = b.x
    walk(ab, "b", -1, 0)
    press(ab, "b", "m0")
    ev = run(ab, 0.5)
    chk("잠든 동안 못 움직이고 못 쓴다", b.x == x0 and not of(ev, "cast", w="b"), (x0, b.x))
    ev = run_until(ab, lambda e: of(e, "cure", w="b"), 3.0)
    chk("2~3초 뒤 깬다", of(ev, "cure", w="b", s="slp") and me(ab, "b")["s"] is None)

    ab, ev = status_on("HYPNOSIS")
    run(ab, 0.7)
    press(ab, "a", "m1")
    ev = run_until(ab, lambda e: of(e, "hit", v="b"), 2.0)
    t_hit = ab.t
    ev = run_until(ab, lambda e: of(e, "cure", w="b"), 2.0)
    chk("맞으면 0.6초 뒤 깬다", of(ev, "cure", s="slp") and ab.t - t_hit <= 0.6 + 2 * AB.TICK, ab.t - t_hit)

    ab, ev = status_on("CONFUSERAY")
    chk("이상한빛 → 혼란 (c)", "cnf" in me(ab, "b")["c"], me(ab, "b")["c"])
    b = ab.sides["b"]
    x0 = b.x
    walk(ab, "b", 1, 0)
    run(ab, 0.5)
    chk("혼란이면 이동이 반대", b.x < x0, (x0, b.x))
    ev = run_until(ab, lambda e: of(e, "cure", w="b", s="cnf"), 6.5)
    chk("4~6초 뒤 풀린다", of(ev, "cure", s="cnf") and "cnf" not in me(ab, "b")["c"])

    ab, ev = status_on("LEECHSEED")
    a, b = ab.sides["a"].mon.f, ab.sides["b"].mon.f
    a.hp = a.maxhp // 2
    hb, ha = b.hp, a.hp
    ev = run(ab, 2.1)
    chk("씨뿌리기: 2초마다 빨아서 상대가 먹는다", hb - b.hp == b.maxhp // 24 and a.hp - ha == b.maxhp // 24
        and of(ev, "heal", w="a"), (hb - b.hp, a.hp - ha, b.maxhp // 24))

    ab = fight([("ARCANINE", ["FAKEOUT"])], [("SNORLAX", ["HYPERBEAM"])])
    place(ab, "a", 650, 450)
    press(ab, "b", "m0")
    run(ab, 2 * AB.TICK)
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    chk("풀죽음: 준비가 끊기고 휘청", of(ev, "status", w="b", s="flinch") and not of(ev, "hit", v="a"),
        [e["e"] for e in ev])


# ---------------------------------------------------------------- 힘겨루기
def t_clash():
    print("== 힘겨루기")
    ab = fight([("BLASTOISE", ["WATERGUN"])], [("BLASTOISE", ["WATERGUN"])])
    place(ab, "a", 300, 450)
    place(ab, "b", 1300, 450)
    press(ab, "a", "m0")
    press(ab, "b", "m0")
    ev = run(ab, 2.0)
    chk("비슷한 탄끼리는 둘 다 터진다", of(ev, "clash") and not of(ev, "hit") and not ab.shots, ev)

    ab = fight([("BLASTOISE", ["HYDROPUMP"])], [("BLASTOISE", ["WATERGUN"])])
    place(ab, "a", 400, 450)
    place(ab, "b", 1100, 450)
    press(ab, "a", "m0")
    press(ab, "b", "m0")
    ev = run_until(ab, lambda e: of(e, "clash"), 2.0)
    chk("센 탄이 이긴다", of(ev, "clash") and len(ab.shots) == 1 and ab.shots[0].o == "a", ab.shots)
    chk("센 쪽 위력 − 약한 쪽 × 0.5", ab.shots and ab.shots[0].power == 110 - 40 * 0.5,
        ab.shots and ab.shots[0].power)
    ev = run(ab, 2.0)
    chk("이긴 탄은 계속 날아가 맞는다", of(ev, "hit", v="b") and not of(ev, "hit", v="a"))

    ab = fight([("BLASTOISE", ["ICEBEAM"])], [("BLASTOISE", ["WATERGUN"])])
    place(ab, "a", 300, 450)
    place(ab, "b", 1300, 450)
    press(ab, "b", "m0")
    run(ab, 0.3)
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    chk("광선은 지나는 탄을 지운다", of(ev, "clash") and not of(ev, "hit", v="a") and of(ev, "hit", v="b"),
        [e["e"] for e in ev])

    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "a", 770, 450)
    place(ab, "b", 830, 450)
    press(ab, "a", "m0")
    press(ab, "b", "m0")
    ev = run(ab, 0.6)
    a, b = ab.sides["a"], ab.sides["b"]
    chk("근접끼리 맞부딪히면 튕긴다 (데미지 없음)", of(ev, "clash") and not of(ev, "hit"), [e["e"] for e in ev])
    chk("둘 다 140 씩 밀려난다", b.x - a.x >= 60 + 2 * AB.CLASH_PUSH - 10, b.x - a.x)


# ---------------------------------------------------------------- 예고
def t_telegraph():
    print("== 예고 (광선 · 내려찍기)")
    for move, kind in (("ICEBEAM", "beam"), ("THUNDER", "tele"), ("HEATWAVE", "cone"), ("EARTHQUAKE", "ring")):
        ab = fight([("ARCEUS", [move])], [("SNORLAX", ["TACKLE"])])
        place(ab, "b", 760, 450)
        press(ab, "a", "m0")
        run(ab, 2 * AB.TICK)
        z = [x for x in ab.snapshot("b")["z"] if x["o"] == "a"]
        snap = ab.snapshot("b")
        chk("%s: 준비 동안 상대에게 장판이 보인다 (%s)" % (move, kind),
            z and z[0]["kind"] == kind and z[0]["t0"] <= snap["ts"] < z[0]["t1"] and z[0]["k"] == move, z)
        ev = run(ab, 2.0)
        chk("%s: 서 있으면 맞는다" % move, of(ev, "hit", v="b"))

    ab = fight([("ARCEUS", ["HEATWAVE"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 500, 200)
    press(ab, "a", "m0")
    ev = run(ab, 2 * AB.TICK)
    z = ab.snapshot("b")["z"][0]
    kt = AM.kit(DEX, "HEATWAVE")
    chk("각은 라디안 (위쪽 = -π/2) · 부채꼴 w 는 끝 너비", of(ev, "cast")[0]["ang"] == round(-math.pi / 2, 3)
        and z["ang"] == round(-math.pi / 2, 3)
        and abs(2 * math.degrees(math.atan2(z["w"] / 2, z["len"])) - kt["spread"]) < 0.5, (z, of(ev, "cast")))

    for move in ("ICEBEAM", "THUNDER"):
        ab = fight([("ARCEUS", [move])], [("JOLTEON", ["TACKLE"])])
        press(ab, "a", "m0")
        run(ab, 2 * AB.TICK)
        walk(ab, "b", 0, 1)
        ev = run(ab, 2.0)
        chk("%s: 예고를 보고 비키면 안 맞는다" % move, not of(ev, "hit", v="b"), of(ev, "hit"))

    ab = fight([("ARCEUS", ["ICEBEAM"])], [("SNORLAX", ["FAKEOUT"])])
    place(ab, "b", 650, 450)
    press(ab, "a", "m0")
    run(ab, 2 * AB.TICK)
    press(ab, "b", "m0")
    run(ab, 0.5)
    chk("준비가 끊기면 예고도 사라진다", not [z for z in ab.snapshot("b")["z"] if z["o"] == "a"],
        ab.snapshot("b")["z"])


# ---------------------------------------------------------------- 꼴마다
def t_kinds():
    print("== 꼴마다")
    ab = fight([("ARCANINE", ["EXTREMESPEED"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "a", 500, 450)
    place(ab, "b", 950, 450)
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    chk("돌진: 길게 달려가 친다", of(ev, "hit", v="b") and ab.sides["a"].x > 850, ab.sides["a"].x)

    ab = fight([("PIDGEOT", ["FLY"])], [("SNORLAX", ["TACKLE"])])
    press(ab, "a", "m0")
    run(ab, 2 * AB.TICK)
    chk("공중날기: 준비 동안 숨는다 (안 맞는다)", me(ab, "a")["st"] == "hide", me(ab, "a")["st"])
    ev = run(ab, 1.5)
    a, b = ab.sides["a"], ab.sides["b"]
    chk("상대 자리에 내려찍는다", of(ev, "hit", v="b") and math.hypot(a.x - b.x, a.y - b.y) < 100,
        (a.x, b.x))

    ab = fight([("SCIZOR", ["SWORDSDANCE"])], [("SNORLAX", ["TACKLE"])])
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    chk("칼춤: 공격 +2", of(ev, "stat", w="a", st="atk", d=2) and me(ab, "a")["stg"] == {"atk": 2}, me(ab, "a"))

    ab = fight([("ALAKAZAM", ["RECOVER"])], [("SNORLAX", ["TACKLE"])])
    f = ab.sides["a"].mon.f
    f.hp = f.maxhp // 4
    press(ab, "a", "m0")
    ev = run(ab, 1.2)
    chk("HP회복: 절반 회복", of(ev, "heal", w="a") and f.hp == f.maxhp // 4 + f.maxhp // 2, (f.hp, f.maxhp))

    ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["PROTECT"])])
    b = ab.sides["b"]
    press(ab, "a", "m0")
    run_until(ab, lambda _: ab.shots and ab.shots[0].x >= b.x - 200, 2.0)
    press(ab, "b", "m0")
    ev = run(ab, 0.8)
    chk("방어: 막는다", of(ev, "guard", w="b") and not of(ev, "hit", v="b"), [e["e"] for e in ev])

    ab = fight([("MACHAMP", ["TACKLE"])], [("SNORLAX", ["COUNTER"])])
    place(ab, "a", 830, 450)
    press(ab, "b", "m0")
    run(ab, 2 * AB.TICK)
    press(ab, "a", "m0")
    ev = run(ab, 0.8)
    chk("카운터: 받은 만큼 되돌린다", of(ev, "counter", w="b") and of(ev, "hit", v="a", w="b")
        and not of(ev, "hit", v="b"), [e["e"] for e in ev])

    ab = fight([("GOLEM", ["STEALTHROCK"])], [("CHARIZARD", ["TACKLE"])])
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    z = [x for x in ab.snapshot("b")["z"] if x["kind"] == "haz"]
    hit = of(ev, "hit", v="b", k="STEALTHROCK")
    f = ab.sides["b"].mon.f
    chk("스텔스록: 발밑 함정이 터진다 (리자몽 4배 → 절반)", hit and hit[0]["dmg"] == f.maxhp * 4 // 8 and not z,
        (hit, z))

    ab = fight([("GOLEM", ["EXPLOSION"])], [("SNORLAX", ["TACKLE"]), ("PIDGEY", ["GUST"])])
    place(ab, "b", 700, 450)
    press(ab, "a", "m0")
    ev = run(ab, 2.0)
    chk("대폭발: 둘레를 치고 쓰러진다", of(ev, "hit", v="b") and of(ev, "ko", w="a"), [e["e"] for e in ev])
    chk("(내 마지막이라 진다)", ab.result == {"winner": "b", "reason": "ko"}, ab.result)

    ab = fight([("TYRANITAR", ["SANDSTORM", "STONEEDGE"])], [("SNORLAX", ["TACKLE"])])
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    chk("모래바람: 판 전체 날씨 (글씨로 알린다)", ab.field.weather == "sand" and of(ev, "txt"), ab.field.weather)
    run(ab, AB.FIELD_SEC)
    chk("시간이 지나면 그친다", ab.field.weather is None)

    ab = fight([("ALAKAZAM", ["REFLECT"])], [("MACHAMP", ["BRICKBREAK"])])
    press(ab, "a", "m0")
    run(ab, 1.0)
    chk("리플렉터: 장막 (c scr)", "scr" in me(ab, "a")["c"], me(ab, "a")["c"])


# ---------------------------------------------------------------- 근접 · 돌진: 달려들며 길 위를 친다
def act_path(ab, w, sec=1.5):
    """발동(act) 동안 움직인 길: (처음 자리, 끝 자리, 이벤트). 발동이 시작한 틱의 걸음부터 끝난 틱 전까지."""
    s = ab.sides[w]
    ev, p0 = [], None
    for _ in range(int(round(sec / AB.TICK))):
        before = (s.x, s.y)
        ab.step()
        ev.extend(ab.drain_events())
        acting = s.cast is not None and s.cast.stage == "act"
        if p0 is None and acting:
            p0 = before
        elif p0 is not None and not acting:
            return p0, before, ev
    return p0, (s.x, s.y), ev


def rush(a_move, a_xy, b_xy, hold=(0, 0), a_mon="GARCHOMP", keep=False, sec=1.2):
    """a 가 hold 를 누른 채 기술을 쓴다 (keep 이 아니면 쓰기 시작한 다음 손을 뗀다). (판, 쓴 자리, 이벤트)."""
    ab = fight([(a_mon, [a_move])], [("SNORLAX", ["TACKLE"])])
    place(ab, "a", *a_xy)
    place(ab, "b", *b_xy)
    walk(ab, "a", *hold)
    press(ab, "a", "m0")
    ev = run(ab, AB.TICK)
    s = ab.sides["a"]
    at = (s.x, s.y)
    if not keep:
        walk(ab, "a", 0, 0)
    return ab, at, ev + run(ab, sec)


def t_rush():
    print("== 근접 · 돌진: 누르는 쪽으로 달려들며 길 위를 친다")
    kt = AM.kit(DEX, "DRAGONCLAW")
    reach = kt["w"] / 2.0 + AB.BODY_R

    ab, (x0, y0), ev = rush("DRAGONCLAW", (500, 450), (500, 250), hold=(1, 0))
    a = ab.sides["a"]
    c = of(ev, "cast", w="a")
    chk("근접: 누르고 있는 쪽으로 달려든다 (오른쪽 · 상대는 위)", c and c[0]["ang"] == 0 and not of(ev, "hit", v="b"),
        (c, [e["e"] for e in ev]))
    chk("  달려든 거리 = range (%s)" % kt["range"], abs(a.x - x0 - kt["range"]) < 0.5 and a.y == y0,
        (a.x - x0, a.y - y0))
    chk("  cast 에 len · r (근접 r = w/2)", c and c[0]["len"] == kt["range"] and c[0]["r"] == kt["w"] / 2.0, c)

    ab, (x0, y0), ev = rush("DRAGONCLAW", (500, 450), (500, 250))
    a, b = ab.sides["a"], ab.sides["b"]
    c = of(ev, "cast", w="a")
    hit = of(ev, "hit", v="b", k="DRAGONCLAW")
    chk("가만히 있으면 상대 쪽으로 달려든다", c and c[0]["ang"] == round(-math.pi / 2, 3), c)
    chk("  맞히면 그 자리에서 멈춘다 (몸을 뚫고 지나가지 않는다)", len(hit) == 1 and a.x == 500
        and abs(a.y - (250 + reach)) < 0.5, (hit, a.y, 250 + reach))
    chk("  맞은 쪽은 기술 방향으로 %d 밀려난다 (무적 없음)" % AB.BUMP_DIST,
        abs((250 - b.y) - AB.BUMP_DIST) < 0.5 and b.x == 500 and not me(ab, "b")["inv"], (b.x, b.y))

    for off, want in ((70, True), (140, False)):
        ab, _, ev = rush("DRAGONCLAW", (500, 450), (650, 450 - off), hold=(1, 0))
        chk("근접 길에서 옆으로 %d 떨어진 상대는 %s" % (off, "맞는다" if want else "안 맞는다"),
            bool(of(ev, "hit", v="b")) == want and of(ev, "cast", w="a")[0]["ang"] == 0, [e["e"] for e in ev])

    ab, (x0, y0), ev = rush("DRAGONCLAW", (100, 450), (1300, 450), hold=(-1, 0))
    a = ab.sides["a"]
    c = of(ev, "cast", w="a")[0]
    chk("벽에서 멈춘다", a.x == AB.BODY_R and a.y == y0, (a.x, a.y))
    chk("  cast len 은 벽까지 줄인 길이", abs(c["len"] - (c["x"] - AB.BODY_R)) < 0.15, c)
    ab, (x0, y0), ev = rush("DRAGONCLAW", (100, 60), (1300, 450), hold=(-1, -1))
    a = ab.sides["a"]
    chk("  비스듬히 벽에 닿으면 미끄러지지 않고 그 자리에서", a.y == AB.BODY_R and abs(a.x - (x0 - (y0 - AB.BODY_R))) < 0.5,
        (a.x, a.y, x0, y0))

    ab = fight([("GARCHOMP", ["DRAGONCLAW"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 1300, 800)
    walk(ab, "a", 1, 0)
    press(ab, "a", "m0")
    run(ab, AB.TICK)
    walk(ab, "a", 0, 1)
    (px, py), (qx, qy), _ = act_path(ab, "a")
    chk("달려드는 동안엔 방향키로 못 꺾는다", qy == py and abs(qx - px - kt["range"]) < 0.5, (qx - px, qy - py))
    slow = kt["lock"] * ab._walk_speed(ab.sides["a"]) * (kt["wind"] + AB.TICK)
    chk("  준비 중엔 천천히 걸린다 (%.2f)" % kt["lock"], kt["lock"] == 0.35 and 450 < py <= 450 + slow + 0.5,
        (py - 450, slow))

    ab, _, ev = rush("DRAGONCLAW", (500, 200), (500, 40))
    chk("밀려나도 벽을 넘지 않는다", of(ev, "hit", v="b") and ab.sides["b"].y == AB.BODY_R, ab.sides["b"].y)

    # 앞으로 달려 나가면 등 뒤는 안 맞는다 (붙어 있던 상대에게서 떨어지려고 쓸 수 있다)
    ab, (x0, y0), ev = rush("DRAGONCLAW", (500, 450), (440, 450), hold=(1, 0))
    a = ab.sides["a"]
    chk("등 뒤에 붙은 상대는 안 맞는다", not of(ev, "hit", v="b"), [e["e"] for e in ev])
    chk("  그 상대 때문에 멈추지도 않는다 (range 다 달린다)", abs(a.x - x0 - kt["range"]) < 0.5, a.x - x0)
    ab, _, ev = rush("DRAGONCLAW", (500, 450), (500, 380), hold=(1, 0))
    chk("  바로 옆(몸 반 안쪽 뒤)은 길에 닿으니 맞는다", of(ev, "hit", v="b"), [e["e"] for e in ev])

    ab, _, ev = rush("AERIALACE", (500, 450), (700, 450), hold=(-1, 0), a_mon="PIDGEOT", keep=True)
    c = of(ev, "cast", w="a")
    chk("제비반환(반드시 맞음)은 뒤로 걸어도 상대를 노린다", c and c[0]["ang"] == 0 and of(ev, "hit", v="b"),
        (c, [e["e"] for e in ev]))

    ab, _, ev = rush("DOUBLEKICK", (500, 450), (650, 450), a_mon="HITMONLEE")
    b = ab.sides["b"]
    hits = of(ev, "hit", v="b", k="DOUBLEKICK")
    chk("연속 근접(두번치기): 붙어 있으면 두 대 다 맞는다", len(hits) == 2, [e["e"] for e in ev])
    chk("  마지막 대에만 밀려난다 (한 번 %d)" % AB.BUMP_DIST, abs(b.x - 650 - AB.BUMP_DIST) < 0.5, b.x)
    ab = fight([("HITMONLEE", ["DOUBLEKICK"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 650, 450)
    press(ab, "a", "m0")
    ev = run_until(ab, lambda e: of(e, "hit", v="b"), 1.0)
    walk(ab, "b", 1, 0)
    ev += run(ab, 1.0)
    chk("  첫 대 뒤 걸어 나가도 경직 때문에 둘째 대도 맞는다", len(of(ev, "hit", v="b", k="DOUBLEKICK")) == 2,
        [e["e"] for e in ev])
    ab = fight([("HITMONLEE", ["DOUBLEKICK"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 650, 450)
    press(ab, "a", "m0")
    ev = run_until(ab, lambda e: of(e, "hit", v="b"), 1.0)
    place(ab, "b", 1000, 450)
    ev += run(ab, 1.0)
    chk("  멀어지면 남은 대는 안 맞는다", len(of(ev, "hit", v="b", k="DOUBLEKICK")) == 1, [e["e"] for e in ev])
    ab = fight([("SNORLAX", ["TACKLE"])], [("GENGAR", ["LICK"])])
    place(ab, "b", 650, 450)
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    hit = of(ev, "hit", v="b", k="TACKLE")
    chk("  상성 0 이면 안 밀리고 경직도 없다", hit and hit[0]["eff"] == 0 and ab.sides["b"].x == 650
        and not ab.sides["b"].hs, (hit, ab.sides["b"].x))

    ek = AM.kit(DEX, "EXTREMESPEED")
    for off, want in ((75, True), (95, False)):
        ab, _, ev = rush("EXTREMESPEED", (500, 300), (500 + off, 600), hold=(0, 1), a_mon="ARCANINE")
        c = of(ev, "cast", w="a")
        chk("돌진도 누르는 쪽으로 · 길에서 %d 떨어진 상대는 %s (몸 둘 + %d)" % (off, "맞는다" if want else "안 맞는다",
                                                                  AB.DASH_REACH),
            c and c[0]["ang"] == round(math.pi / 2, 3) and bool(of(ev, "hit", v="b")) == want, (c, of(ev, "hit")))
    chk("  돌진 cast 에 len · r (r = %d)" % AB.DASH_REACH, c and c[0]["len"] == ek["range"]
        and c[0]["r"] == AB.DASH_REACH, c)
    ab, _, ev = rush("WATERGUN", (500, 450), (900, 450), a_mon="BLASTOISE")
    c = of(ev, "cast", w="a")
    chk("  날리기 cast 에는 len · r 이 없다", c and "len" not in c[0] and "r" not in c[0], c)

    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "a", 700, 450)
    place(ab, "b", 760, 450)
    walk(ab, "a", -1, 0)
    walk(ab, "b", 1, 0)
    press(ab, "a", "m0")
    press(ab, "b", "m0")
    ev = run(ab, AB.TICK)
    walk(ab, "a", 0, 0)
    walk(ab, "b", 0, 0)
    ev += run(ab, 1.0)
    chk("서로 등지고 달려들면 맞부딪히지 않는다", not of(ev, "clash"), [e["e"] for e in ev])


# ---------------------------------------------------------------- 손맛: 경직 · 탄 밀림
def stun_len(hit):
    return AB.HITSTUN_BIG if (hit["crit"] or hit["eff"] >= 2) else AB.HITSTUN_SEC


def t_feel():
    print("== 손맛: 맞으면 경직 · 탄도 민다")
    ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["TACKLE"])])
    b = ab.sides["b"]
    press(ab, "a", "m0")
    ev = run_until(ab, lambda e: of(e, "hit", v="b"), 2.0)
    hit = of(ev, "hit", v="b")[0]
    t_hit, want = ab.t, stun_len(hit)
    f = me(ab, "b")
    chk("기술에 맞으면 경직 (st stun · 못 걷는다 · 무적 없음)", f["st"] == "stun" and f["spd"] == 0 and not f["inv"], f)
    chk("  경직 길이 %.2f초 (급소 · 효과가 굉장하면 %.2f)" % (AB.HITSTUN_SEC, AB.HITSTUN_BIG),
        b.hs and abs(b.hs[-1][0] - t_hit) < 1e-9 and abs(b.hs[-1][1] - (t_hit + want)) < 1e-9, (b.hs, t_hit, want))
    walk(ab, "b", 0, 1)
    press(ab, "b", "m0")
    y0, casts, n = b.y, [], 0
    while ab.t + AB.TICK + 1e-9 < t_hit + want:         # 다음 틱도 아직 경직
        casts += of(run(ab, AB.TICK), "cast", w="b")
        n += 1
    chk("  경직 동안(%d틱)엔 못 걷고 못 쓴다 (누른 키는 들고 있다)" % n, n >= 2 and b.y == y0 and not casts,
        (n, b.y, y0, casts))
    ev = run(ab, AB.TICK)
    chk("  풀리면 바로 걷고 들고 있던 키를 쓴다", b.y > y0 and of(ev, "cast", w="b", k="TACKLE"), (b.y, y0, ev))
    chk("탄에 맞으면 탄이 날던 쪽으로 %d 밀린다" % AB.SHOT_PUSH, abs(b.x - 900 - AB.SHOT_PUSH) < 0.5, b.x)

    # 준비 중에 맞아도 준비는 안 끊긴다 (끊는 것은 풀죽음)
    ab = fight([("BLASTOISE", ["WATERGUN"])], [("LAPRAS", ["ICEBEAM"])])
    b = ab.sides["b"]
    press(ab, "a", "m0")
    run_until(ab, lambda _: ab.shots and ab.shots[0].x >= b.x - 150, 2.0)
    press(ab, "b", "m0")
    ev = run_until(ab, lambda e: of(e, "hit", v="b"), 1.0)
    f = me(ab, "b")
    chk("준비 중에 맞으면: 보이기는 stun · 쓰던 칸은 그대로", of(ev, "hit", v="b") and f["st"] == "stun" and f["sm"] == 0
        and b.cast is not None and b.cast.stage == "wind", (f, [e["e"] for e in ev]))
    ev = run(ab, 1.5)
    chk("  준비는 안 끊기고 광선이 나간다", of(ev, "hit", v="a", k="ICEBEAM"), [e["e"] for e in ev])

    # 겹쳐 맞으면 새로 잴 뿐 더하지 않는다 · 1초에 0.35초까지
    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    b = ab.sides["b"]
    ab._hitstun(b, AB.HITSTUN_SEC)
    ab._hitstun(b, AB.HITSTUN_SEC)
    chk("같은 때 두 번 맞아도 한 번 길이", len(b.hs) == 1 and abs(b.hs[0][1] - b.hs[0][0] - AB.HITSTUN_SEC) < 1e-9, b.hs)
    t0 = ab.t
    run(ab, AB.TICK)
    ab._hitstun(b, AB.HITSTUN_SEC)
    chk("  조금 뒤 또 맞으면 끝만 그때부터 다시 잰다", len(b.hs) == 1
        and abs(b.hs[0][1] - (t0 + AB.TICK + AB.HITSTUN_SEC)) < 1e-9, (b.hs, t0))
    ab._hitstun(b, 0.05)
    chk("  짧은 것은 남은 경직을 줄이지 않는다", abs(b.hs[0][1] - (t0 + AB.TICK + AB.HITSTUN_SEC)) < 1e-9, b.hs)

    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    b = ab.sides["b"]
    spans, held, t0 = {}, 0, ab.t
    for _ in range(int(round(3.0 / AB.TICK))):
        ab._hitstun(b, AB.HITSTUN_BIG)              # 틱마다 맞는다 (가장 나쁜 연속기)
        for a0, a1 in b.hs:
            spans[round(a0, 6)] = max(a1, spans.get(round(a0, 6), 0.0))
        run(ab, AB.TICK)
        held += ab._staggered(b)
    worst = 0.0
    for k in range(int(3.0 / 0.01)):
        w0 = t0 + k * 0.01
        worst = max(worst, sum(max(0.0, min(a1, w0 + AB.HITSTUN_WINDOW) - max(a0, w0)) for a0, a1 in spans.items()))
    chk("틱마다 맞아도 어느 1초 창에서든 경직 합 %.2f초 이하 (가장 무거운 창 %.3f)" % (AB.HITSTUN_CAP, worst),
        AB.HITSTUN_CAP - 0.02 <= worst <= AB.HITSTUN_CAP + 1e-6, worst)
    chk("  끝없이 묶이지 않는다 (3초 중 움직일 수 있던 틱 %d / %d)" % (90 - held, 90), held <= 0.4 * 90, held)

    # 경직은 기술 데미지만: 화상 · 상성 0 · 막음은 경직도 밀림도 없다
    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    b = ab.sides["b"]
    ab._inflict(b, "burn", ab.sides["a"].mon)
    ev = run_until(ab, lambda e: of(e, "hit", v="b", k="brn"), 2.5)
    chk("화상으로 깎여도 경직이 없다", of(ev, "hit", v="b", k="brn") and not b.hs and me(ab, "b")["st"] != "stun", b.hs)

    ab = fight([("PIKACHU", ["THUNDERSHOCK"])], [("GOLEM", ["TACKLE"])])
    b = ab.sides["b"]
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    hit = of(ev, "hit", v="b")
    chk("상성 0 인 탄은 안 밀고 경직도 없다", hit and hit[0]["eff"] == 0 and b.x == 900 and not b.hs, (hit, b.x, b.hs))

    ab = fight([("BLASTOISE", ["WATERGUN"])], [("SNORLAX", ["PROTECT"])])
    b = ab.sides["b"]
    press(ab, "a", "m0")
    run_until(ab, lambda _: ab.shots and ab.shots[0].x >= b.x - 200, 2.0)
    press(ab, "b", "m0")
    ev = run(ab, 0.8)
    chk("방어로 막으면 안 밀고 경직도 없다", of(ev, "guard", w="b") and b.x == 900 and not b.hs, (b.x, b.hs))

    ab = fight([("BRELOOM", ["BULLETSEED"])], [("SNORLAX", ["TACKLE"])])
    b = ab.sides["b"]
    place(ab, "b", 640, 450)
    press(ab, "a", "m0")
    ev = run(ab, 1.0)
    hits = of(ev, "hit", v="b", k="BULLETSEED")
    chk("연발이 한꺼번에 맞아도 한 번만 민다 (%d발 맞음 · 마지막 발의 쪽으로)" % len(hits), len(hits) >= 2
        and abs(math.hypot(b.x - 640, b.y - 450) - AB.SHOT_PUSH) < 0.5 and b.x > 640, (len(hits), b.x, b.y))


# ---------------------------------------------------------------- 대가 (체력을 깎는 기술 · 풍선)
def t_costs():
    print("== 대가 (체력을 깎는 기술 · 풍선)")

    def boost(move, hp, atk=0):
        """짜랑고우거(Lv.50 체력 150)가 체력 hp(최대) 에서 move 를 쓴다."""
        ab = fight([("KOMMOO", [move])], [("SNORLAX", ["TACKLE"])])
        place(ab, "b", 1500, 100)
        m = ab.sides["a"].mon
        m.f.hp, m.f.stages["atk"] = hp(m.f.maxhp), atk
        hp0 = m.f.hp
        press(ab, "a", "m0")
        return ab, m, hp0, run(ab, 1.0)

    for move, hp in (("BELLYDRUM", lambda mx: mx // 2), ("FILLETAWAY", lambda mx: mx // 2),
                     ("CLANGOROUSSOUL", lambda mx: mx // 3)):
        ab, m, hp0, ev = boost(move, hp)
        chk("%s: 체력이 모자라면 실패 (스스로 쓰러지지 않는다)" % move,
            of(ev, "cast", w="a", k=move) and of(ev, "txt", w="a", msg="하지만 실패했다!") and not of(ev, "ko")
            and not of(ev, "stat") and m.f.hp == hp0 and not m.ko, (m.f.hp, hp0, [e["e"] for e in ev]))
        chk("%s: 실패해도 PP · 대기는 쓴 채로 (본가처럼)" % move,
            m.pp[0] == AM.kit(DEX, move)["pp"] - 1 and me(ab, "a")["cd"][0] > 0, (m.pp, me(ab, "a")["cd"]))
    ab, m, hp0, ev = boost("BELLYDRUM", lambda mx: mx // 2 + 1)
    chk("배북: 절반보다 많으면 절반을 깎고 공격 최대", of(ev, "stat", w="a", st="atk", d=6)
        and hp0 - m.f.hp == m.f.maxhp // 2 and m.f.hp == 1 and not m.ko, (hp0, m.f.hp, [e["e"] for e in ev]))
    order = [e["e"] for e in ev if e["e"] in ("hit", "stat")]
    chk("배북: 깎고 나서 올린다 (본가 순서)", order == ["hit", "stat"], order)
    ab, m, hp0, ev = boost("BELLYDRUM", lambda mx: mx, atk=6)
    chk("배북: 공격이 이미 최대면 실패", of(ev, "txt", w="a", msg="하지만 실패했다!") and m.f.hp == hp0, ev)
    ab, m, hp0, ev = boost("CLANGOROUSSOUL", lambda mx: mx // 3 + 1)
    chk("소울비트: 1/3 보다 많으면 1/3 을 깎고 다 올린다", len(of(ev, "stat", w="a", d=1)) == 5
        and hp0 - m.f.hp == m.f.maxhp // 3 and not m.ko, (hp0, m.f.hp, [e["e"] for e in ev]))
    ab, m, hp0, ev = boost("FILLETAWAY", lambda mx: mx)
    chk("살을깎다: 절반을 한 번만 깎는다", hp0 - m.f.hp == m.f.maxhp // 2 and len(of(ev, "stat", w="a", d=2)) == 3,
        (hp0, m.f.hp))

    # 풍선: 땅 기술 · 압정이 안 닿다가 데미지를 받으면 터진다 (함정 · 독 · 반동으로는 안 터진다)
    ab = battle([("GARCHOMP", ["EARTHQUAKE", "TACKLE", "SPIKES"])], [("HEATRAN", ["TACKLE"])])
    ab.sides["b"].team[0]["held"] = "AIRBALLOON"
    start(ab)
    place(ab, "b", 570, 450)
    f = ab.sides["b"].mon.f
    press(ab, "a", "m2")
    ev = run(ab, 1.5)
    chk("(풍선) 압정이 발밑에 깔렸다", [z for z in ab.zones if z.kind == "haz" and z.k == "SPIKES"], ab.zones)
    press(ab, "a", "m0")
    ev += run(ab, 1.5)
    eq = of(ev, "hit", v="b", k="EARTHQUAKE")
    chk("풍선: 지진이 안 닿는다 · 압정도 안 밟는다", eq and eq[0]["dmg"] == 0 and f.hp == f.maxhp and not f.used
        and not of(ev, "hit", k="SPIKES"), (eq, f.hp, f.used))
    press(ab, "a", "m1")
    ev = run(ab, 1.0)
    chk("풍선: 데미지를 받으면 터진다", of(ev, "hit", v="b", k="TACKLE") and f.used
        and of(ev, "txt", w="b", msg="풍선이 터졌다!"), [e["e"] for e in ev])
    chk("풍선: 터지면 압정을 밟는다", of(ev, "hit", v="b", k="SPIKES"), [e["e"] for e in ev])
    run(ab, AM.kit(DEX, "EARTHQUAKE")["cd"])
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    eq = of(ev, "hit", v="b", k="EARTHQUAKE")
    chk("풍선: 터진 뒤엔 지진이 닿는다", eq and eq[0]["dmg"] > 0, eq)

    ab = battle([("HEATRAN", ["TACKLE"])], [("SNORLAX", ["COUNTER"])])
    ab.sides["a"].team[0]["held"] = "AIRBALLOON"
    start(ab)
    place(ab, "a", 830, 450)
    press(ab, "b", "m0")
    run(ab, 2 * AB.TICK)
    press(ab, "a", "m0")
    ev = run(ab, 0.8)
    chk("풍선: 카운터로 되돌려 받아도 터진다", of(ev, "hit", v="a", w="b") and ab.sides["a"].mon.f.used
        and of(ev, "txt", w="a", msg="풍선이 터졌다!"), [e["e"] for e in ev])
    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    m = ab.sides["a"].mon
    m.f.held = "AIRBALLOON"
    ab._inflict(ab.sides["a"], "burn", ab.sides["b"].mon)
    run(ab, 2.1)
    chk("풍선: 화상으로 깎여도 안 터진다", m.f.hp < m.f.maxhp and not m.f.used, (m.f.hp, m.f.used))

    # 체력 절반을 치르는 공격 (빅뱅 · 철거빔 · 클로로블래스트) - 본가 50% × DAMAGE_SCALE
    def half(move, near):
        ab = fight([("MEW", [move])], [("BLISSEY", ["TACKLE"])])
        place(ab, "b", 700 if near else 1500, 450 if near else 60)
        f = ab.sides["a"].mon.f
        press(ab, "a", "m0")
        ev = run(ab, 2.5)
        return f, ev, max(1, int(math.ceil(f.maxhp / 2.0) * AB.DAMAGE_SCALE))

    for move in ("MINDBLOWN", "STEELBEAM", "CHLOROBLAST"):
        f, ev, cost = half(move, True)
        mine = of(ev, "hit", v="a", w="a", k=move)
        chk("%s: 맞히면 내 체력도 깎인다" % move, of(ev, "hit", v="b", k=move) and f.maxhp - f.hp == cost
            and mine and mine[0]["dmg"] == cost, (f.hp, f.maxhp, cost, [e["e"] for e in ev]))
    for move, paid in (("MINDBLOWN", True), ("STEELBEAM", True), ("CHLOROBLAST", False)):
        f, ev, cost = half(move, False)
        chk("%s: 빗나가면 %s" % (move, "그래도 깎인다 (본가처럼)" if paid else "안 깎인다"),
            not of(ev, "hit", v="b") and f.maxhp - f.hp == (cost if paid else 0), (f.hp, f.maxhp, cost))

    # 목숨걸기: 맞히면 쓴 쪽이 쓰러진다 (데미지는 내 체력 × DAMAGE_SCALE - 대폭발처럼 줄인 그대로)
    ab = fight([("MEW", ["FINALGAMBIT"]), ("PIDGEY", ["GUST"])], [("SNORLAX", ["TACKLE"])])
    f = ab.sides["a"].mon.f
    hp0 = f.hp
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    hit = of(ev, "hit", v="b", k="FINALGAMBIT")
    chk("목숨걸기: 맞히면 쓰러진다", hit and hit[0]["dmg"] == int(round(hp0 * AB.DAMAGE_SCALE))
        and of(ev, "ko", w="a", i=0) and of(ev, "need", w="a") and ab.sides["a"].mons[0].ko,
        (hit, [e["e"] for e in ev]))
    ab = fight([("MEW", ["FINALGAMBIT"])], [("GENGAR", ["LICK"])])
    press(ab, "a", "m0")
    ev = run(ab, 1.5)
    chk("목숨걸기: 고스트에게는 안 통하고 안 쓰러진다", of(ev, "hit", v="b", k="FINALGAMBIT") and not of(ev, "ko")
        and not ab.sides["a"].mon.ko, [e["e"] for e in ev])
    ab = fight([("MEW", ["FINALGAMBIT"])], [("SNORLAX", ["TACKLE"])])
    place(ab, "b", 1500, 60)
    press(ab, "a", "m0")
    ev = run(ab, 2.5)
    chk("목숨걸기: 빗나가면 안 쓰러진다", not of(ev, "ko") and not ab.sides["a"].mon.ko, [e["e"] for e in ev])


# ---------------------------------------------------------------- 교체 · 쓰러짐 · 끝
def t_switch():
    print("== 교체")
    ab = fight([("PIKACHU", ["THUNDERSHOCK"]), ("SNORLAX", ["TACKLE"]), ("PIDGEY", ["GUST"])],
               [("RATTATA", ["TACKLE"])])
    ab.sides["a"].mon.f.stages["atk"] = 2
    press(ab, "a", "sw1")
    run(ab, 2 * AB.TICK)
    chk("교체 중", me(ab, "a")["st"] == "swap" and me(ab, "a")["i"] == 0, me(ab, "a"))
    ev = run(ab, AB.SWITCH_SEC)
    chk("0.6초 뒤 바뀐다", of(ev, "swap", w="a", fr=0, to=1) and me(ab, "a")["i"] == 1, ev)
    chk("나온 순간 무적", me(ab, "a")["inv"])
    chk("교체 대기 6초", AB.SWITCH_CD - 1 < me(ab, "a")["scd"] <= AB.SWITCH_CD, me(ab, "a")["scd"])
    press(ab, "a", "sw0")
    ev = run(ab, 1.0)
    chk("대기 중엔 못 바꾼다", not of(ev, "swap"))
    run(ab, AB.SWITCH_CD)
    press(ab, "a", "sw0")
    ev = run(ab, 1.0)
    chk("대기가 지나면 바꾼다", of(ev, "swap", to=0))
    chk("물러나면 랭크가 풀린다", ab.sides["a"].mon.f.stages["atk"] == 0)
    chk("무적은 1초", not me(ab, "a")["inv"] or ab.sides["a"].inv_until - ab.t <= AB.SPAWN_PROTECT)


def t_faint():
    print("== 쓰러짐 · 끝")
    ab = fight([("BLASTOISE", ["HYDROPUMP"])],
               [("PIDGEY", ["GUST"]), ("RATTATA", ["TACKLE"]), ("SPEAROW", ["PECK"])])
    ab.sides["b"].mon.f.hp = 1
    press(ab, "a", "m0")
    ev = run_until(ab, lambda e: of(e, "ko"), 3.0)
    chk("쓰러짐 → ko · need", of(ev, "ko", w="b", i=0) and of(ev, "need", w="b"), [e["e"] for e in ev])
    chk("내 F 에 need", me(ab, "b")["need"] and me(ab, "b")["st"] == "ko")
    chk("상대 F 에는 need 가 없다", "need" not in ab.snapshot("a")["f"]["b"])
    chk("팀 칸에 쓰러짐", ab.snapshot("a")["f"]["b"]["team"][0]["ko"])
    ev = run(ab, AB.KO_PICK_SEC - 0.2)
    chk("5초 안엔 기다린다", not of(ev, "swap"))
    ev = run(ab, 0.3)
    chk("5초 지나면 앞에서부터 나온다", of(ev, "swap", w="b", fr=0, to=1) and not me(ab, "b")["need"])
    chk("제자리에서 · 무적으로", (ab.sides["b"].x, ab.sides["b"].y) == AB.SPAWN["b"] and me(ab, "b")["inv"])
    run(ab, 4.0)
    ab.sides["b"].mon.f.hp = 1
    place(ab, "b", 900, 450)
    press(ab, "a", "m0")
    run_until(ab, lambda e: of(e, "ko"), 3.0)
    press(ab, "b", "sw2")
    ev = run(ab, AB.TICK)
    chk("쓰러진 뒤 고르면 바로", of(ev, "swap", w="b", to=2), ev)
    chk("남은 수", ab.left("a") == 1 and ab.left("b") == 1)

    ab = fight([("BLASTOISE", ["HYDROPUMP"])], [("PIDGEY", ["GUST"])])
    ab.sides["b"].mon.f.hp = 1
    press(ab, "a", "m0")
    ev = run(ab, 2.0)
    chk("셋 다 쓰러지면 끝 (over)", of(ev, "over", winner="a", reason="ko") and of(ev, "phase", ph="over"), ev)
    chk("result", ab.result == {"winner": "a", "reason": "ko"} and ab.phase == "over")
    n = ab.tick
    ab.step()
    chk("끝난 판은 안 굴러간다", ab.tick == n)

    ab = fight([("SNORLAX", ["TACKLE"]), ("PIDGEY", ["GUST"])], [("SNORLAX", ["TACKLE"])], fight_sec=2)
    ab.sides["a"].mon.f.hp = 1
    ev = run(ab, 2.1)
    chk("시간 끝: 남은 마리 수가 먼저", ab.result == {"winner": "a", "reason": "timeout"}, ab.result)
    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])], fight_sec=2)
    ab.sides["a"].mon.f.hp -= 10
    run(ab, 2.1)
    chk("시간 끝: 그다음 체력 비율", ab.result == {"winner": "b", "reason": "timeout"}, ab.result)
    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])], fight_sec=2)
    run(ab, 2.1)
    chk("시간 끝: 같으면 무승부", ab.result == {"winner": "draw", "reason": "timeout"}, ab.result)
    chk("싸운 초 (전적용)", ab.fight_secs() == 2, ab.fight_secs())
    run(ab, 1.0)
    chk("  끝난 뒤엔 늘지 않는다", ab.fight_secs() == 2, ab.fight_secs())
    chk("싸움 전에 끝난 판은 0", battle([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])]).fight_secs() == 0)

    ab = fight([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    ab.forfeit("a")
    ev = ab.drain_events()
    chk("기권하면 상대 승", ab.result == {"winner": "b", "reason": "forfeit"} and of(ev, "over", winner="b"))
    ab = battle([("SNORLAX", ["TACKLE"])], [("SNORLAX", ["TACKLE"])])
    ab.forfeit("b")
    chk("고르기 중에도 기권", ab.result == {"winner": "a", "reason": "forfeit"} and ab.phase == "over")


# ---------------------------------------------------------------- 보이는 것
def t_views():
    print("== intro · snapshot")
    ab = fight([("PIKACHU", ["THUNDERBOLT", "BATONPASS"])], [("CHARIZARD", ["FLAMETHROWER"])])
    ab.sides["a"].team[0]["held"] = "LIGHTBALL"
    hi = ab.intro("a")
    chk("hello 모양", hi["t"] == "hello" and hi["you"] == "a" and hi["arena"] == [1600, 900]
        and hi["names"] == {"a": "가", "b": "나"} and hi["limits"]["koPick"] == AB.KO_PICK_SEC, hi)
    mine, foe = hi["teams"]["a"][0], hi["teams"]["b"][0]
    chk("내 팀 보기: 기술 · 도구 · 체력", mine["lv"] == 50 and mine["mhp"] > 0 and mine["item"]
        and [m["key"] for m in mine["moves"]] == ["THUNDERBOLT", "BATONPASS"], mine)
    mv = mine["moves"][1]
    chk("기술 칸 모양 (회색 칸 + 까닭)", set(mv) == {"key", "kr", "type", "cat", "power", "pp", "kind", "ok", "why",
                                               "desc", "sty", "cd", "range"} and not mv["ok"] and mv["why"], mv)
    chk("상대 팀 보기엔 기술 · 도구 · 체력이 없다", set(foe) == {"key", "num", "kr", "shiny", "tint", "types"}, foe)
    chk("종 · 번호 · 타입", foe["key"] == "CHARIZARD" and foe["num"] == 6 and foe["types"] == ["FIRE", "FLYING"])
    json.dumps(hi)

    s = ab.snapshot("a")
    chk("snapshot 모양", s["t"] == "s" and s["ph"] == "fight" and s["n"] == ab.tick and set(s["f"]) == {"a", "b"},
        sorted(s))
    hidden = {"hp", "mhp", "cd", "pp", "scd", "spd", "need"}
    chk("내 F 에는 체력 · 쿨타임 · PP (피하기 대기 dcd 는 없다)", hidden == set(s["f"]["a"]) - set(s["f"]["b"])
        and "dcd" not in s["f"]["a"], sorted(s["f"]["a"]))
    chk("상대 F 에는 없다", not (hidden & set(s["f"]["b"])), sorted(s["f"]["b"]))
    chk("공통 F 열쇠", {"i", "x", "y", "d", "st", "sm", "sp", "s", "c", "stg", "inv", "hpr", "team"}
        <= set(s["f"]["b"]), sorted(s["f"]["b"]))

    ab2 = fight([("PIKACHU", ["THUNDERBOLT"]), ("EEVEE", ["TACKLE"]), ("PIDGEY", ["GUST"])],
                [("RATTATA", ["TACKLE"])])
    chk("상대 팀 칸: 안 나온 마리의 slot 은 숨긴다", [x["slot"] for x in ab2.snapshot("b")["f"]["a"]["team"]]
        == [0, None, None] and [x["slot"] for x in me(ab2, "a")["team"]] == [0, 1, 2])
    press(ab2, "a", "sw2")
    run(ab2, 1.0)
    chk("나온 마리는 보인다", [x["slot"] for x in ab2.snapshot("b")["f"]["a"]["team"]] == [0, None, 2])

    press(ab, "a", "m0")
    press(ab, "b", "m0")
    run(ab, 0.45)
    s = ab.snapshot("b")
    text = json.dumps(s, separators=(",", ":"))
    chk("JSON 으로 나간다", json.loads(text) == s)
    bad = []

    def look(v, key=""):
        if isinstance(v, dict):
            for k, x in v.items():
                look(x, k)
        elif isinstance(v, list):
            for x in v:
                look(x, key)
        elif isinstance(v, float):
            places = 3 if key in ("ts", "t0", "t1", "ang") else 1
            if round(v, places) != v:
                bad.append((key, v))
    look(s)
    chk("소수는 한 자리 (시각 · 각은 세 자리)", not bad, bad[:5])
    chk("탄 모양", s["p"] and set(s["p"][0]) == {"id", "o", "k", "ty", "sty", "x", "y", "vx", "vy", "r"}, s["p"])
    chk("장판 모양", s["z"] and set(s["z"][0]) == {"id", "o", "k", "ty", "sty", "kind", "x", "y", "r", "ang", "len",
                                                  "w", "t0", "t1"}, s["z"])
    walk(ab, "a", 0, 1)
    chk("ack 는 받은 것 중 가장 큰 seq", ab.snapshot("a")["ack"] == SEQ[0])


# ---------------------------------------------------------------- 같은 판 · 판 길이 · 빠르기
def bot(ab, w, k):
    """상대 쪽으로 걸어가 붙으면 서서 기술을 돌려 쓴다."""
    s, o = ab.sides[w], ab.sides["b" if w == "a" else "a"]
    dx, dy = o.x - s.x, o.y - s.y
    d = math.hypot(dx, dy) or 1.0
    if d > 130:
        ab.set_move(w, dx / d, dy / d, k)
    else:
        ab.set_move(w, 0, 0, k)
    if s.need_until is not None:
        ab.press(w, "sw%d" % next(i for i, m in enumerate(s.mons) if not m.ko), k)
    else:
        ab.press(w, "m%d" % (k % 4), k)


def play(ab, sec):
    lines = []
    for _ in range(int(round(sec / AB.TICK))):
        if ab.phase == "over":
            break
        bot(ab, "a", ab.tick)
        bot(ab, "b", ab.tick + 1)
        ab.step()
        lines.append(json.dumps([ab.snapshot("a"), ab.snapshot("b"), ab.drain_events()], sort_keys=True))
    return lines


TEAM_A = [("GARCHOMP", ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "FIREFANG"]),
          ("GENGAR", ["SHADOWBALL", "SLUDGEBOMB", "THUNDERBOLT", "HYPNOSIS"]),
          ("BLASTOISE", ["SURF", "ICEBEAM", "DARKPULSE", "PROTECT"])]
TEAM_B = [("METAGROSS", ["METEORMASH", "ZENHEADBUTT", "BULLETPUNCH", "EARTHQUAKE"]),
          ("CHARIZARD", ["FLAMETHROWER", "AIRSLASH", "DRAGONPULSE", "ROOST"]),
          ("VENUSAUR", ["GIGADRAIN", "SLUDGEBOMB", "SLEEPPOWDER", "LEECHSEED"])]


def t_same():
    print("== 같은 시드 · 같은 입력 = 같은 판")
    one = play(fight(TEAM_A, TEAM_B, seed=11), 25)
    two = play(fight(TEAM_A, TEAM_B, seed=11), 25)
    chk("snapshot · 이벤트 줄이 한 글자도 같다 (%d틱)" % len(one), one == two)
    hits = sum(line.count('"e": "hit"') for line in one)
    chk("(그동안 실제로 맞았다)", hits > 5, hits)


def ko_time(a, b, seed):
    ab = fight([a], [b], seed=seed)
    place(ab, "a", 400, 450)
    place(ab, "b", 1200, 450)
    t0 = ab.t
    for _ in range(int(90 / AB.TICK)):
        bot(ab, "a", ab.tick)
        bot(ab, "b", ab.tick + 1)
        ab.step()
        if of(ab.drain_events(), "ko"):
            return ab.t - t0
    return None


def t_length():
    print("== 판 길이 (봇끼리 한 마리 쓰러뜨리기 4~30초 · 3 대 3 은 %d초 안에, DAMAGE_SCALE %.2f)"
          % (AB.FIGHT_SEC, AB.DAMAGE_SCALE))
    pairs = [
        (("SNORLAX", ["BODYSLAM", "CRUNCH", "EARTHQUAKE", "HEAVYSLAM"]),
         ("SNORLAX", ["BODYSLAM", "CRUNCH", "EARTHQUAKE", "HEAVYSLAM"])),
        (("PIKACHU", ["THUNDERBOLT", "QUICKATTACK", "IRONTAIL", "THUNDERWAVE"]),
         ("EEVEE", ["TACKLE", "BITE", "QUICKATTACK", "SWIFT"])),
        (("MACHAMP", ["CROSSCHOP", "KNOCKOFF", "BULLETPUNCH", "BULKUP"]),
         ("DRAGONITE", ["DRAGONCLAW", "EXTREMESPEED", "FIREPUNCH", "DRAGONDANCE"])),
        (("SYLVEON", ["MOONBLAST", "HYPERVOICE", "SWIFT", "CALMMIND"]),
         ("ESPEON", ["PSYCHIC", "DAZZLINGGLEAM", "SWIFT", "MORNINGSUN"])),
    ]
    for a, b in pairs:
        times = [ko_time(a, b, seed) for seed in (1, 2, 3)]
        chk("%s vs %s: 한 마리 4~30초 %s" % (a[0], b[0], [t and round(t, 1) for t in times]),
            all(t is not None and 4 <= t <= 30 for t in times), times)
    for seed in (1, 2, 3):
        ab = fight(TEAM_A, TEAM_B, seed=seed, fight_sec=AB.FIGHT_SEC)
        t0 = ab.t
        play(ab, AB.FIGHT_SEC + 1)
        chk("3 대 3 (seed %d): %d초 안에 쓰러뜨려 끝난다 (%.1f초)" % (seed, AB.FIGHT_SEC, ab.t - t0),
            ab.result is not None and ab.result["reason"] == "ko", ab.result)


def t_every_move():
    print("== 920기술 전부 판에서 써 본다 (넷씩)")
    keys = sorted(DEX.moves)
    broken, used = [], set()
    for i in range(0, len(keys), 4):
        four = sorted(keys[i:i + 4], key=lambda k: k in AF.SELF_KO or k == "FINALGAMBIT")    # 쓰고 쓰러지는 것은 맨 나중에
        try:
            ab = fight([("MEW", four)], [("SNORLAX", ["TACKLE"]), ("PIDGEY", ["GUST"])], seed=i)
            place(ab, "b", 760, 450)
            for k in range(4):
                press(ab, "a", "m%d" % k)
                for e in run(ab, 2.5):
                    if e["e"] == "cast" and e["w"] == "a":
                        used.add(e["k"])
            json.dumps(ab.snapshot("a"))
            sane = all(0 <= m.f.hp <= m.f.maxhp for s in ab.sides.values() for m in s.mons)
            inside = all(AB.BODY_R <= s.x <= AB.ARENA_W - AB.BODY_R and AB.BODY_R <= s.y <= AB.ARENA_H - AB.BODY_R
                         for s in ab.sides.values())
            if not (sane and inside):
                broken.append((four, "hp/자리"))
        except Exception as ex:                                 # noqa: BLE001
            broken.append((four, repr(ex)))
    chk("어느 기술도 판을 멈추지 않는다", not broken, broken[:3])
    usable = [k for k in keys if AM.kit(DEX, k)["ok"]]
    missed = [k for k in usable if k not in used]
    chk("쓸 수 있는 기술은 다 나갔다 (%d개)" % len(usable), not missed, missed[:10])


def t_speed():
    print("== 빠르기 (판 하나 step 1ms 아래)")
    ab = fight(TEAM_A, TEAM_B, seed=5)
    spent, n = 0.0, 0
    for _ in range(int(60 / AB.TICK)):
        if ab.phase == "over":
            break
        bot(ab, "a", ab.tick)
        bot(ab, "b", ab.tick + 1)
        t0 = time.perf_counter()
        ab.step()
        spent += time.perf_counter() - t0
        n += 1
        ab.drain_events()
    per = spent / max(1, n) * 1000
    t0 = time.perf_counter()
    for _ in range(300):
        ab.snapshot("a")
    snap = (time.perf_counter() - t0) / 300 * 1000
    print("     step 평균 %.3f ms (%d틱) · snapshot %.3f ms" % (per, n, snap))
    chk("step 평균 1ms 아래", per < 1.0, per)


def main():
    global DEX
    DEX = P.Pokedex.load(DEX_PATH)
    t_pick()
    t_walk()
    t_shot()
    t_no_dodge()
    t_eva_walk()
    t_cooldown()
    t_status()
    t_clash()
    t_telegraph()
    t_kinds()
    t_rush()
    t_feel()
    t_costs()
    t_switch()
    t_faint()
    t_views()
    t_same()
    t_length()
    t_every_move()
    t_speed()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
