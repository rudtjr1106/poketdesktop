# -*- coding: utf-8 -*-
"""우격다짐 검사 — 엔진만. 서버 없이 돈다.

    python common/test_sheerforce.py

우격다짐은 **부가효과(쇼다운의 secondary)가 있는 기술**의 위력을 1.3배로 올리고 그 부가효과를 지운다.
생명의구슬 반동도 없다. 기술 자체의 효과(쇼다운의 self · 주 효과)는 건드리지 않는다:

  · 인파이트 · 용성군 · 오버히트처럼 **자기 능력을 내리는 것**은 부가효과가 아니다 - 위력도 그대로, 하락도 그대로.
    파워업펀치 · 니트로차지처럼 부가효과로 자기 능력을 올리는 것은 우격다짐을 받는다 (오르지는 않는다).
  · 쑥쑥봄버의 씨뿌리기, 조이기류의 묶기, 사우전드웨이브의 묶기는 주 효과다.
  · 앵커샷 · 그림자꿰매기의 묶기는 부가효과다 - 우격다짐 · 인분 · 은밀망토가 지운다.
  · 엔진이 기술마다 따로 거는 부가효과(트라이어택 · 소금절이 · 시럽봄 · 암석액스의 바위 ...)도 같다.
  · 우격다짐이 붙으면 '맞힌 뒤' 효과가 안 움직인다 (쇼다운 suppressingSecondaries): 생명의구슬 · 조개껍질방울 ·
    목스프레이 · 레드카드 · 탈출버튼 · 악키 · 타라프열매 · 발끈 · 분노의껍질 · 변색 · 나쁜손버릇 · 위기회피 · 도망태세,
    고속스핀류의 장판 치우기, 옛노래의 폼 바꾸기, 열탕류가 얼음을 녹이는 것.
  · 일렉트릭샷 · 지휘는 부가효과가 없는데 위력만 오른다 (쇼다운 hasSheerForceBoost - 생명의구슬 반동은 든다).

같이 맞춘 부가효과 판정: 비밀의힘은 필드마다 효과가 다르고, 오리진즈슈퍼노바는 사이코필드를 깔고(자기 쪽 부가효과라
우격다짐만 지운다), 왕의징표석 · 예리한이빨의 풀죽음도 부가효과다 (인분 · 은밀망토 · 정신력 · 대타가 막는다).

어느 기술에 부가효과가 있는지는 도감을 만들 때 쇼다운 자료로 적어 둔다 (pokedex.json 의 sec,
tools/build_pokedex.secondary_from_showdown). 11/19 게시판 #664 검토에서 찾았다.
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import abilities as A           # noqa: E402
from common import battle as B              # noqa: E402
from common import test_abilities2 as T     # noqa: E402

OK = FAIL = 0
DEX = T.DEX
mon, use, est, texts = T.mon, T.use, T.est, T.texts

# 쇼다운에서 secondary 가 없고 self 로 자기 능력을 내리는 공격기 (도감에서는 statSelf · statChance 100)
SELF_DROP = ("ARMORCANNON", "CLANGINGSCALES", "CLOSECOMBAT", "DRACOMETEOR", "DRAGONASCENT", "FLEURCANNON",
             "HAMMERARM", "HEADLONGRUSH", "HYPERSPACEFURY", "ICEHAMMER", "LEAFSTORM", "MAKEITRAIN",
             "OVERHEAT", "PSYCHOBOOST", "SPINOUT", "SUPERPOWER", "VCREATE")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pair(key, ability="SHEERFORCE", foe_ability="PRESSURE", held=None, foe_held=None, user="NIDOKING", foe="SNORLAX"):
    return T.fight(mon(user, 50, [key], ability=ability, held=held),
                   mon(foe, 50, ["TACKLE"], ability=foe_ability, held=foe_held))


def ratio(key, user="NIDOKING", foe="SNORLAX"):
    """우격다짐 / 우격다짐 없음 (같은 포켓몬, 특성만 다르다) 의 데미지 비."""
    _bt, me, tg = pair(key, user=user, foe=foe)
    _bt0, me0, tg0 = pair(key, ability="PRESSURE", user=user, foe=foe)
    return est(me, tg, key) / float(est(me0, tg0, key))


def land(bt, key, ok, tries=20):
    """맞을 때까지 쓴다 (명중 90 짜리). ok(ev) 가 참이면 그 ev 를 돌려준다."""
    for _ in range(tries):
        ev = use(bt, "me", key)
        if ok(ev):
            return ev
    return None


def hit(ev):
    return any(e.get("t") == "hit" for e in ev)


def t_dex_flag():
    print("-- 도감: 쇼다운에 부가효과가 있나 (sec)")
    spec = importlib.util.spec_from_file_location("build_pokedex", os.path.join(ROOT, "tools", "build_pokedex.py"))
    bp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bp)
    f = getattr(bp, "secondary_from_showdown", None)
    chk("build_pokedex.secondary_from_showdown 이 있다", f is not None)
    if f is not None:
        for label, v, want in (("secondary 가 있다 (파워업펀치)", {"secondary": {"chance": 100, "self": {"boosts": {"atk": 1}}}}, True),
                               ("secondaries 가 있다 (불꽃엄니)", {"secondaries": [{"chance": 10, "status": "brn"}]}, True),
                               ("빈 secondary 도 있는 것이다 (암석액스)", {"secondary": {}}, True),
                               ("self 만 있다 (인파이트)", {"self": {"boosts": {"def": -1, "spd": -1}}}, False),
                               ("아무것도 없다 (쑥쑥봄버)", {}, False),
                               ("secondary 가 null", {"secondary": None}, False)):
            chk("  %s -> %s" % (label, want), f(v) is want, f(v))
    moves = DEX.raw["moves"]
    for k, want in (("CLOSECOMBAT", False), ("POWERUPPUNCH", True), ("SAPPYSEED", False), ("ANCHORSHOT", True),
                    ("SPIRITSHACKLE", True), ("THOUSANDWAVES", False), ("FLAMETHROWER", True), ("EARTHQUAKE", False),
                    ("WRAP", False), ("BITE", True), ("STONEAXE", True)):
        chk("  %s 의 sec 는 %s" % (k, want), moves[k].get("sec") is want, moves[k].get("sec"))
    attacks = [k for k, m in moves.items() if m.get("cat") != "status"]
    flagged = [k for k in attacks if isinstance(moves[k].get("sec"), bool)]
    chk("  쇼다운에 있는 공격기에는 다 적혀 있다 (Z기술만 빠진다)", len(attacks) - len(flagged) < 60,
        (len(attacks), len(flagged)))
    bad = [k for k in flagged if moves[k]["sec"] is False and A.has_secondary(moves[k])]
    chk("sec 가 False 인 공격기는 우격다짐을 안 받는다", not bad, bad)
    bad = [k for k in flagged if moves[k]["sec"] is True and not A.has_secondary(moves[k])]
    chk("sec 가 True 인 공격기는 다 우격다짐을 받는다 (부가효과를 엔진이 따로 거는 것도)", not bad, bad)
    boost = sorted(k for k, m in moves.items() if m.get("sfBoost"))
    chk("위력만 오르는 것(쇼다운 hasSheerForceBoost)은 일렉트릭샷 · 지휘", boost == ["ELECTROSHOT", "ORDERUP"], boost)


def t_self_drop():
    print("-- 자기 능력을 내리는 기술 (인파이트 · 용성군 ...)")
    bad = [k for k in SELF_DROP if A.has_secondary(DEX.move(k))]
    chk("%d개 다 우격다짐 대상이 아니다" % len(SELF_DROP), not bad, bad)
    for k in ("CLOSECOMBAT", "DRACOMETEOR", "VCREATE"):
        r = ratio(k)
        chk("  %s: 위력이 그대로다" % k, abs(r - 1.0) < 0.01, r)
    bt, me, foe = pair("CLOSECOMBAT")
    land(bt, "CLOSECOMBAT", hit)
    chk("우격다짐이어도 인파이트를 쓰면 방어 · 특수방어가 떨어진다",
        me.stages["def"] == -1 and me.stages["spd"] == -1, me.stages)
    bt, me, foe = pair("DRACOMETEOR", user="GARCHOMP")
    land(bt, "DRACOMETEOR", hit)
    chk("  용성군은 특수공격 -2", me.stages["spa"] == -2, me.stages)
    bt, me, foe = pair("CLOSECOMBAT", foe_ability="SHIELDDUST")
    land(bt, "CLOSECOMBAT", hit)
    chk("  상대가 인분이어도 내 하락은 그대로", me.stages["def"] == -1, me.stages)

    print("-- 부가효과로 자기 능력을 올리는 기술은 우격다짐 대상이다 (본가)")
    for k in ("POWERUPPUNCH", "FLAMECHARGE"):
        chk("  %s: 대상" % k, A.has_secondary(DEX.move(k)))
        r = ratio(k)
        chk("  %s: 위력 1.3배" % k, abs(r - 1.3) < 0.03, r)
    bt, me, foe = pair("POWERUPPUNCH")
    land(bt, "POWERUPPUNCH", hit)
    chk("  우격다짐이면 파워업펀치로 공격이 안 오른다 (지워진다)", me.stages["atk"] == 0, me.stages)
    bt, me, foe = pair("POWERUPPUNCH", ability="PRESSURE")
    land(bt, "POWERUPPUNCH", hit)
    chk("  우격다짐이 아니면 오른다", me.stages["atk"] == 1, me.stages)


def t_life_orb():
    print("-- 생명의구슬")
    bt, me, foe = pair("FLAMETHROWER", held="LIFEORB")
    ev = land(bt, "FLAMETHROWER", hit)
    chk("우격다짐이 붙은 기술(화염방사)은 반동이 없다", me.hp == me.maxhp and "생명의구슬" not in texts(ev or []),
        (me.hp, me.maxhp, texts(ev or [])))
    for k in ("EARTHQUAKE", "CLOSECOMBAT"):
        bt, me, foe = pair(k, held="LIFEORB")
        land(bt, k, hit)
        chk("  우격다짐이 안 붙는 기술(%s)은 반동이 든다" % k, me.maxhp - me.hp == me.maxhp // 10, (me.hp, me.maxhp))
    bt, me, foe = pair("FLAMETHROWER", ability="PRESSURE", held="LIFEORB")
    land(bt, "FLAMETHROWER", hit)
    chk("  우격다짐이 아니면 화염방사도 반동이 든다", me.maxhp - me.hp == me.maxhp // 10, (me.hp, me.maxhp))
    bt, me, foe = pair("FLAMETHROWER", held="LIFEORB")
    me.ability_on = foe.ability_on = False
    land(bt, "FLAMETHROWER", hit)
    chk("  특성이 꺼진 판이면 반동이 든다", me.maxhp - me.hp == me.maxhp // 10, (me.hp, me.maxhp))


def t_sappy_seed():
    print("-- 쑥쑥봄버 (쇼다운에 secondary 가 없다)")
    chk("우격다짐 대상이 아니다", not A.has_secondary(DEX.move("SAPPYSEED")))
    r = ratio("SAPPYSEED")
    chk("  위력이 그대로다", abs(r - 1.0) < 0.01, r)
    bt, me, foe = pair("SAPPYSEED")
    land(bt, "SAPPYSEED", hit)
    chk("  우격다짐이어도 씨앗을 심는다", foe.seeded, foe.seeded)


def t_trap_secondary():
    print("-- 앵커샷 · 그림자꿰매기 (묶기가 부가효과다)")
    tg = "SLOWBRO"                                   # 그림자꿰매기가 노말(잠만보)에게는 안 맞는다
    for k, user in (("ANCHORSHOT", "DHELMISE"), ("SPIRITSHACKLE", "DECIDUEYE")):
        chk("%s: 우격다짐 대상" % k, A.has_secondary(DEX.move(k)))
        r = ratio(k, user=user, foe=tg)
        chk("  위력 1.3배", abs(r - 1.3) < 0.03, r)
        bt, me, foe = pair(k, user=user, foe=tg)
        land(bt, k, hit)
        chk("  우격다짐이면 묶지 않는다", not foe.cond.get("trapped"), foe.cond.get("trapped"))
        bt, me, foe = pair(k, ability="PRESSURE", user=user, foe=tg)
        land(bt, k, hit)
        chk("  우격다짐이 아니면 묶는다", foe.cond.get("trapped") == "me", foe.cond.get("trapped"))
        bt, me, foe = pair(k, ability="PRESSURE", foe_ability="SHIELDDUST", user=user, foe=tg)
        land(bt, k, hit)
        chk("  상대가 인분이면 안 묶인다", not foe.cond.get("trapped"), foe.cond.get("trapped"))
        bt, me, foe = pair(k, ability="MOLDBREAKER", foe_ability="SHIELDDUST", user=user, foe=tg)
        land(bt, k, hit)
        chk("  틀깨기는 인분을 무시하고 묶는다", foe.cond.get("trapped") == "me", foe.cond.get("trapped"))
        bt, me, foe = pair(k, ability="PRESSURE", foe_held="COVERTCLOAK", user=user, foe=tg)
        land(bt, k, hit)
        chk("  상대가 은밀망토면 안 묶인다", not foe.cond.get("trapped"), foe.cond.get("trapped"))
        bt, me, foe = pair(k, ability="PRESSURE", foe_held="COVERTCLOAK", user=user, foe=tg)
        me.ability_on = foe.ability_on = False
        land(bt, k, hit)
        chk("  특성이 꺼진 판에서도 은밀망토는 막는다", not foe.cond.get("trapped"), foe.cond.get("trapped"))

    print("-- 사우전드웨이브 (묶기가 주 효과다 - 그대로)")
    chk("우격다짐 대상이 아니다", not A.has_secondary(DEX.move("THOUSANDWAVES")))
    r = ratio("THOUSANDWAVES", user="ZYGARDE")
    chk("  위력이 그대로다", abs(r - 1.0) < 0.01, r)
    for ab, fab, fheld, label in (("SHEERFORCE", "PRESSURE", None, "우격다짐이어도"),
                                  ("PRESSURE", "SHIELDDUST", None, "상대가 인분이어도"),
                                  ("PRESSURE", "PRESSURE", "COVERTCLOAK", "상대가 은밀망토여도")):
        bt, me, foe = pair("THOUSANDWAVES", ability=ab, foe_ability=fab, foe_held=fheld, user="ZYGARDE")
        land(bt, "THOUSANDWAVES", hit)
        chk("  %s 묶는다" % label, foe.cond.get("trapped") == "me", foe.cond.get("trapped"))


def label(ab):
    return "우격다짐" if ab == "SHEERFORCE" else "우격다짐 아님"


def switcher(bt, foe_team=False):
    asked = []
    bt.switcher = lambda who, mode, ev, key, state=None: asked.append((who, mode)) or True
    if foe_team:
        bt.teams = {"me": [bt.me], "foe": [bt.foe, B.Fighter(DEX, mon("SNORLAX", 50))]}
    return asked


def t_after_hit():
    print("-- 우격다짐이 붙으면 '맞힌 뒤' 효과가 안 움직인다")
    for ab in ("SHEERFORCE", "PRESSURE"):
        on = ab != "SHEERFORCE"                       # 효과가 움직여야 하나
        bt, me, foe = pair("FLAMETHROWER", ability=ab, held="SHELLBELL")
        me.hp = me.maxhp // 2
        hp = me.hp
        land(bt, "FLAMETHROWER", hit)
        chk("조개껍질방울 (%s 화염방사): 회복 %s" % (label(ab), on), (me.hp > hp) is on, (hp, me.hp))

        bt, me, foe = pair("BUGBUZZ", ability=ab, held="THROATSPRAY")
        land(bt, "BUGBUZZ", hit)
        chk("목스프레이 (%s 벌레의야단법석): 특수공격 +1 %s" % (label(ab), on), (me.stages["spa"] == 1) is on, me.stages)

        for item, want in (("REDCARD", [("me", "drag")]), ("EJECTBUTTON", [("foe", "out")])):
            bt, me, foe = pair("FLAMETHROWER", ability=ab, foe_held=item)
            asked = switcher(bt)
            land(bt, "FLAMETHROWER", hit)
            chk("%s (%s 화염방사): 교체 %s" % (item, label(ab), on), asked == (want if on else []), asked)

        for item, key, stat in (("KEEBERRY", "FIREPUNCH", "def"), ("MARANGABERRY", "FLAMETHROWER", "spd")):
            bt, me, foe = pair(key, ability=ab, foe_held=item)
            land(bt, key, hit)
            chk("%s (%s %s): 먹는다 %s" % (item, label(ab), key, on), (foe.stages[stat] == 1) is on, foe.stages)

        for fab, stat in (("BERSERK", "spa"), ("ANGERSHELL", "atk")):
            bt, me, foe = pair("FLAMETHROWER", ability=ab, foe_ability=fab)
            foe.hp = foe.maxhp // 2 + 5
            land(bt, "FLAMETHROWER", hit)
            chk("%s (%s 화염방사로 절반 아래): %s +1 %s" % (fab, label(ab), stat, on),
                (foe.stages[stat] == 1) is on, (foe.stages, foe.hp, foe.maxhp))

        bt, me, foe = pair("FLAMETHROWER", ability=ab, foe_ability="COLORCHANGE")
        land(bt, "FLAMETHROWER", hit)
        chk("변색 (%s 화염방사): 불꽃 타입이 된다 %s" % (label(ab), on), (foe.types() == ["FIRE"]) is on, foe.types())

        bt, me, foe = pair("FIREPUNCH", ability=ab, held="LEFTOVERS", foe_ability="PICKPOCKET")
        land(bt, "FIREPUNCH", hit)
        chk("나쁜손버릇 (%s 불꽃펀치): 도구를 훔친다 %s" % (label(ab), on), (foe.held == "LEFTOVERS") is on,
            (me.held, foe.held))

        for fab in ("EMERGENCYEXIT", "WIMPOUT"):
            bt, me, foe = pair("FLAMETHROWER", ability=ab, foe_ability=fab)
            asked = switcher(bt, foe_team=True)
            foe.hp = foe.maxhp // 2 + 5
            land(bt, "FLAMETHROWER", hit)
            chk("%s (%s 화염방사로 절반 아래): 물러난다 %s" % (fab, label(ab), on),
                (asked == [("foe", "out")]) is on, asked)

    print("-- 부가효과가 없는 기술이면 우격다짐이어도 그대로 움직인다")
    bt, me, foe = pair("EARTHQUAKE", foe_held="REDCARD")
    asked = switcher(bt)
    land(bt, "EARTHQUAKE", hit)
    chk("레드카드 (우격다짐 지진): 끌려 나간다", asked == [("me", "drag")], asked)
    bt, me, foe = pair("EARTHQUAKE", foe_ability="BERSERK")
    foe.hp = foe.maxhp // 2 + 5
    land(bt, "EARTHQUAKE", hit)
    chk("발끈 (우격다짐 지진): 특수공격 +1", foe.stages["spa"] == 1, foe.stages)
    bt, me, foe = pair("BOOMBURST", held="THROATSPRAY")
    land(bt, "BOOMBURST", hit)
    chk("목스프레이 (우격다짐 폭음파 - 부가효과 없음): 특수공격 +1", me.stages["spa"] == 1, me.stages)


def tries(key, ability="SHEERFORCE", foe_ability="PRESSURE", foe_held=None, n=40, prep=None, user="NIDOKING"):
    """n 번 새로 맞혀 상대에게 남은 것을 모은다 (prep 으로 맞기 전 상태를 만든다)."""
    out = []
    bt, me, foe = pair(key, ability=ability, foe_ability=foe_ability, foe_held=foe_held, user=user)
    for _ in range(n):
        foe.hp, foe.status = foe.maxhp, None
        foe.cond.clear()
        if prep:
            prep(bt, me, foe)
        land(bt, key, hit)
        out.append((foe.status, dict(foe.cond)))
    return out


def t_special_secondaries():
    print("-- 엔진이 따로 거는 부가효과 (쇼다운 secondary)")
    for k in ("TRIATTACK", "SECRETPOWER", "DIRECLAW", "ALLURINGVOICE", "EERIESPELL", "PSYCHICNOISE", "SALTCURE",
              "SYRUPBOMB", "SPARKLINGARIA", "STONEAXE", "CEASELESSEDGE"):
        r = ratio(k)
        chk("%s: 우격다짐이면 위력 1.3배" % k, abs(r - 1.3) < 0.03, r)

    print("-- 트라이어택: 20% 로 화상 · 마비 · 얼음 중 하나 (전에는 아예 안 걸렸다)")
    got = [st for st, _c in tries("TRIATTACK", ability="PRESSURE", n=150)]
    seen = set(x for x in got if x)
    chk("우격다짐이 아니면 걸린다 (셋 다 나온다)", seen == {"burn", "paralysis", "freeze"}, (seen, sum(1 for x in got if x)))
    chk("  대략 20%", 15 <= sum(1 for x in got if x) <= 50, sum(1 for x in got if x))
    for ab, fab, held, label_ in (("SHEERFORCE", "PRESSURE", None, "우격다짐"), ("PRESSURE", "SHIELDDUST", None, "인분"),
                                  ("PRESSURE", "PRESSURE", "COVERTCLOAK", "은밀망토")):
        got = [st for st, _c in tries("TRIATTACK", ability=ab, foe_ability=fab, foe_held=held, n=60)]
        chk("  %s(이)면 안 걸린다" % label_, not any(got), got)

    for k, pct in (("DIRECLAW", 50), ("SECRETPOWER", 30)):
        got = [st for st, _c in tries(k, ability="PRESSURE", n=60)]
        chk("%s: 우격다짐이 아니면 걸린다" % k, any(got), got)
        for ab, fab, held, label_ in (("SHEERFORCE", "PRESSURE", None, "우격다짐"), ("PRESSURE", "SHIELDDUST", None, "인분"),
                                      ("PRESSURE", "PRESSURE", "COVERTCLOAK", "은밀망토")):
            got = [st for st, _c in tries(k, ability=ab, foe_ability=fab, foe_held=held, n=40)]
            chk("  %s: %s(이)면 안 걸린다" % (k, label_), not any(got), got)
    got = [st for st, _c in tries("DIRECLAW", ability="SERENEGRACE", n=20)]
    chk("페이탈클로: 하늘의은총이면 두 배 (50% -> 늘)", all(got), got)

    def burned(bt, me, foe):
        foe.status = "burn"

    def rose(bt, me, foe):
        foe.cond["rose"] = True

    def spelled(bt, me, foe):
        foe.cond["lastMove"] = "TACKLE"
        foe.pp["TACKLE"] = 30

    cases = (("SALTCURE", None, lambda st, c: bool(c.get("saltcure"))),
             ("SYRUPBOMB", None, lambda st, c: bool(c.get("syrup"))),
             ("PSYCHICNOISE", None, lambda st, c: bool(c.get("healblock"))),
             ("SPARKLINGARIA", burned, lambda st, c: st != "burn"),
             ("ALLURINGVOICE", rose, lambda st, c: bool(c.get("confused"))),
             ("BURNINGJEALOUSY", rose, lambda st, c: st == "burn"))
    for k, prep, took in cases:
        got = tries(k, ability="PRESSURE", n=3, prep=prep)
        chk("%s: 우격다짐이 아니면 걸린다" % k, all(took(st, c) for st, c in got), got)
        for ab, fab, held, label_ in (("SHEERFORCE", "PRESSURE", None, "우격다짐"), ("PRESSURE", "SHIELDDUST", None, "인분"),
                                      ("PRESSURE", "PRESSURE", "COVERTCLOAK", "은밀망토")):
            got = tries(k, ability=ab, foe_ability=fab, foe_held=held, n=3, prep=prep)
            chk("  %s: %s(이)면 안 걸린다" % (k, label_), not any(took(st, c) for st, c in got), got)
    for ab, fab, want in (("PRESSURE", "PRESSURE", True), ("SHEERFORCE", "PRESSURE", False), ("PRESSURE", "SHIELDDUST", False)):
        bt, me, foe = pair("EERIESPELL", ability=ab, foe_ability=fab)
        spelled(bt, me, foe)
        land(bt, "EERIESPELL", hit)
        chk("섬뜩한주문 (%s, 상대 %s): PP 3 줄인다 %s" % (label(ab), fab, want), (foe.pp["TACKLE"] == 27) is want, foe.pp)

    print("-- 우격다짐만 지우는 것 (인분 · 은밀망토와는 상관없다)")
    for k, hz in (("STONEAXE", "stealthrock"), ("CEASELESSEDGE", "spikes")):
        for ab, fab, want in (("PRESSURE", "PRESSURE", True), ("SHEERFORCE", "PRESSURE", False),
                              ("PRESSURE", "SHIELDDUST", True)):
            bt, me, foe = pair(k, ability=ab, foe_ability=fab)
            land(bt, k, hit)
            chk("%s (%s, 상대 %s): 상대 진영에 깔린다 %s" % (k, label(ab), fab, want),
                bool(bt.field.side("foe").get(hz)) is want, bt.field.side("foe"))
    for k in ("RAPIDSPIN", "MORTALSPIN"):
        for ab, want in (("PRESSURE", True), ("SHEERFORCE", False)):
            bt, me, foe = pair(k, ability=ab)
            bt.field.side("me")["spikes"] = 1
            me.seeded = True
            land(bt, k, hit)
            chk("%s (%s): 내 진영의 압정 · 씨앗을 치운다 %s" % (k, label(ab), want),
                (not bt.field.side("me").get("spikes") and not me.seeded) is want, (bt.field.side("me"), me.seeded))
    for ab, want in (("PRESSURE", True), ("SHEERFORCE", False)):
        bt, me, foe = pair("RELICSONG", ability=ab, user="MELOETTA")
        land(bt, "RELICSONG", hit)
        chk("옛노래 (%s 메로엣타): 스텝폼이 된다 %s" % (label(ab), want), bool(me.cond.get("pirouette")) is want, me.cond)
    for k, ab, want in (("SCALD", "PRESSURE", True), ("SCALD", "SHEERFORCE", False), ("FLAMETHROWER", "SHEERFORCE", True)):
        bt, me, foe = pair(k, ability=ab)
        foe.status = "freeze"
        land(bt, k, hit)
        chk("얼음 (%s %s): 녹는다 %s" % (label(ab), k, want), (foe.status != "freeze") is want, foe.status)


def t_boost_only():
    print("-- 일렉트릭샷 · 지휘: 위력만 오른다 (부가효과가 없다)")
    for k in ("ELECTROSHOT", "ORDERUP"):
        r = ratio(k)
        chk("%s: 우격다짐이면 위력 1.3배" % k, abs(r - 1.3) < 0.03, r)
    bt, me, foe = pair("ORDERUP", held="LIFEORB")
    land(bt, "ORDERUP", hit)
    chk("  지휘는 생명의구슬 반동이 든다 (우격다짐이 '붙은' 기술은 아니다)", me.maxhp - me.hp == me.maxhp // 10,
        (me.hp, me.maxhp))


class Fixed(random.Random):
    """random() 이 늘 같은 값 - 확률 판정을 한 줄로 가른다 (uniform 도 이것을 쓴다)."""
    def __init__(self, v):
        random.Random.__init__(self, 1)
        self.v = v

    def random(self):
        return self.v


def t_secret_power():
    print("-- 비밀의힘: 필드마다 부가효과가 다르다 (30%)")

    def field(t):
        def prep(bt, me, foe):
            bt.field.terrain, bt.field.terrain_turns = t, 5
            for st in foe.stages:
                foe.stages[st] = 0
        return prep

    for t, want in ((None, "paralysis"), ("electric", "paralysis"), ("grassy", "sleep")):
        got = set(st for st, _c in tries("SECRETPOWER", ability="PRESSURE", n=40, prep=field(t)) if st)
        chk("%s 필드: %s 만" % (t or "필드 없음", want), got == {want}, got)
    for t, stat in (("misty", "spa"), ("psychic", "spe")):
        bt, me, foe = pair("SECRETPOWER", ability="PRESSURE")
        bt.rng = Fixed(0.1)
        field(t)(bt, me, foe)
        land(bt, "SECRETPOWER", hit)
        chk("%s 필드: 상대 %s -1 (상태이상은 아니다)" % (t, stat), foe.stages[stat] == -1 and not foe.status,
            (foe.stages, foe.status))
        for ab, fab, label_ in (("SHEERFORCE", "PRESSURE", "우격다짐"), ("PRESSURE", "SHIELDDUST", "인분")):
            bt, me, foe = pair("SECRETPOWER", ability=ab, foe_ability=fab)
            bt.rng = Fixed(0.1)
            field(t)(bt, me, foe)
            land(bt, "SECRETPOWER", hit)
            chk("  %s 필드 · %s(이)면 안 떨어진다" % (t, label_), foe.stages[stat] == 0, foe.stages)


def t_genesis_supernova():
    print("-- 오리진즈슈퍼노바 (뮤Z): 맞히면 사이코필드 - 자기 쪽 부가효과라 인분 · 은밀망토와는 상관없다")

    def z(ability="SYNCHRONIZE", foe_ability="PRESSURE", foe_held=None):
        bt, me, foe = T.fight(mon("MEW", 50, ["PSYCHIC"], ability=ability, held="MEWNIUMZ"),
                              mon("SNORLAX", 50, ["TACKLE"], ability=foe_ability, held=foe_held))
        bt.z_want["me"] = "PSYCHIC"
        ev = use(bt, "me", "PSYCHIC")
        return bt, ev

    for ab, fab, held, want in (("SYNCHRONIZE", "PRESSURE", None, True), ("SYNCHRONIZE", "SHIELDDUST", None, True),
                                ("SYNCHRONIZE", "PRESSURE", "COVERTCLOAK", True), ("SHEERFORCE", "PRESSURE", None, False)):
        bt, ev = z(ab, fab, held)
        chk("뮤 %s · 상대 %s %s: 사이코필드 %s" % (ab, fab, held or "", want), (bt.field.terrain == "psychic") is want,
            (bt.field.terrain, texts(ev)))
    chk("  우격다짐 대상이다 (쇼다운 secondary)", A.has_secondary(DEX.move("GENESISSUPERNOVA")))


def t_kings_rock():
    print("-- 왕의징표석 · 예리한이빨: 10% 풀죽음도 부가효과다")

    def flinched(key="TACKLE", ability="PRESSURE", foe_ability="PRESSURE", held="KINGSROCK", foe_held=None, v=0.05,
                 sub=False):
        bt, me, foe = pair(key, ability=ability, foe_ability=foe_ability, held=held, foe_held=foe_held)
        bt.rng = Fixed(v)
        if sub:
            foe.cond["sub"] = foe.maxhp
            use(bt, "me", key)                  # 대타가 맞으면 'hit' 가 없다 - 한 번만 (명중 100 · 고정 난수라 맞는다)
            return bool(foe.flinched)
        land(bt, key, hit)
        return bool(foe.flinched)

    chk("10% 안이면 풀죽는다 (바탕)", flinched())
    chk("  예리한이빨도 같다", flinched(held="RAZORFANG"))
    chk("  10% 밖이면 안 풀죽는다", not flinched(v=0.15))
    chk("인분이면 안 풀죽는다", not flinched(foe_ability="SHIELDDUST"))
    chk("  틀깨기는 인분을 무시한다", flinched(ability="MOLDBREAKER", foe_ability="SHIELDDUST"))
    chk("은밀망토면 안 풀죽는다 (전과 같다)", not flinched(foe_held="COVERTCLOAK"))
    chk("정신력이면 안 풀죽는다", not flinched(foe_ability="INNERFOCUS"))
    chk("  틀깨기는 정신력을 무시한다", flinched(ability="MOLDBREAKER", foe_ability="INNERFOCUS"))
    chk("대타가 맞으면 안 풀죽는다", not flinched(sub=True))
    chk("하늘의은총이면 20% (0.15 에서 풀죽는다)", flinched(ability="SERENEGRACE", v=0.15))
    chk("우격다짐 · 스톤샤워(풀죽음 30%가 지워진다): 왕의징표석의 10% 는 붙는다 (쇼다운 - 지운 뒤에 붙인다)",
        flinched(key="ROCKSLIDE", ability="SHEERFORCE"))
    chk("  우격다짐이어도 10% 밖이면 안 풀죽는다", not flinched(key="ROCKSLIDE", ability="SHEERFORCE", v=0.15))
    n_plain = n_stench = 0
    for i in range(600):
        for ab in ("PRESSURE", "STENCH"):
            bt, me, foe = pair("TACKLE", ability=ab, held="KINGSROCK")
            bt.rng = random.Random(1000 + i)
            land(bt, "TACKLE", hit)
            if ab == "STENCH":
                n_stench += bool(foe.flinched)
            else:
                n_plain += bool(foe.flinched)
    chk("악취 + 왕의징표석: 10% 하나만 (두 번 굴리지 않는다)", n_stench < 90, (n_stench, n_plain))


def t_still_works():
    print("-- 원래 되던 것 (그대로)")
    for k in ("FLAMETHROWER", "ICEBEAM", "BITE", "ROCKSLIDE"):
        r = ratio(k)
        chk("%s: 위력 1.3배" % k, abs(r - 1.3) < 0.03, r)
    for k in ("EARTHQUAKE", "TACKLE"):
        r = ratio(k)
        chk("%s: 부가효과가 없으면 그대로" % k, abs(r - 1.0) < 0.01, r)


def main():
    t_dex_flag()
    t_self_drop()
    t_life_orb()
    t_sappy_seed()
    t_trap_secondary()
    t_after_hit()
    t_special_secondaries()
    t_boost_only()
    t_secret_power()
    t_genesis_supernova()
    t_kings_rock()
    t_still_works()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
