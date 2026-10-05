# -*- coding: utf-8 -*-
"""기술에 붙은 고유 효과 검사 (1.9.2) — 설명에는 있는데 엔진이 안 하던 것들. 서버 없이 돈다.

    python common/test_attackfx.py

제보 둘에서 시작했다.

  · 레이드에서 콜로솔트의 **소금절이**를 썼는데 "소금에 절여지고 있다" 가 안 뜬다
  · 지가르데의 **사우전드애로**가 떠 있는 포켓몬을 못 맞힌다
  · 두드리짱의 **거대해머**를 매 턴 쓴다 (본가는 연달아 못 쓴다)

셋 다 도감 자료(위력·명중·부가효과 확률)에 안 담기는 규칙이라 빠져 있었다. 같은
이유로 빠진 것을 배울 수 있는 기술 전부에서 훑어 채웠고, 여기서 하나씩 못 박는다.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import abilities as A           # noqa: E402
from common import attackfx as AF           # noqa: E402
from common import battle as B              # noqa: E402
from common import field as FD              # noqa: E402
from common import movecalc as MC           # noqa: E402
from common import pokelogic as P           # noqa: E402
from common import statusmoves as SM        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def load_dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


DEX = load_dex()


def mon(species, level=50, moves=("TACKLE",), held=None, ability=None, gender=None):
    m = P.make_pokemon(DEX.get(species), level, random.Random(1), shiny_rate=10 ** 9,
                       ivs=dict((s, 31) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    if ability:
        m["ability"] = ability
    if gender:
        m["gender"] = gender
    return m


def fight(a, b, seed=1, abilities=True):
    me, foe = B.Fighter(DEX, a), B.Fighter(DEX, b)
    me.ability_on = foe.ability_on = abilities
    return B.Battle(DEX, me, foe, random.Random(seed), ai="trainer"), me, foe


def use(bt, who, key):
    ev = []
    user, target = (bt.me, bt.foe) if who == "me" else (bt.foe, bt.me)
    bt._use(who, user, target, key, ev)
    return ev


def eot(bt):
    ev = []
    bt._end_of_turn(ev)
    return ev


def texts(ev):
    return " | ".join(e.get("text", "") for e in ev if e.get("text"))


def hits(ev):
    return [e["damage"] for e in ev if e.get("t") == "hit"]


def est(bt, user, target, key):
    d, _c, _e = B.damage(DEX, DEX.move(key), user, target, B.EST_RNG, crit=False)
    return d


# ---------------------------------------------------------------- 1. 제보
def t_reports():
    print("-- 제보: 소금절이")
    bt, me, foe = fight(mon("GARGANACL", 60, ["SALTCURE"]), mon("SNORLAX", 60))
    ev = use(bt, "me", "SALTCURE")
    chk("맞으면 소금에 절여진다", foe.cond.get("saltcure") and "소금에 절여졌다" in texts(ev), texts(ev))
    hp = foe.hp
    ev = eot(bt)
    chk("턴마다 최대 체력의 1/8", hp - foe.hp == foe.maxhp // 8 and "소금절이" in texts(ev),
        (hp - foe.hp, foe.maxhp // 8, texts(ev)))
    bt, me, foe = fight(mon("GARGANACL", 60, ["SALTCURE"]), mon("BLASTOISE", 60))
    use(bt, "me", "SALTCURE")
    hp = foe.hp
    eot(bt)
    chk("물·강철 타입은 1/4", hp - foe.hp == foe.maxhp // 4, (hp - foe.hp, foe.maxhp // 4))
    bt, me, foe = fight(mon("GARGANACL", 60, ["SALTCURE"]), mon("CLEFABLE", 60, ability="MAGICGUARD"))
    use(bt, "me", "SALTCURE")
    hp = foe.hp
    eot(bt)
    chk("매직가드는 안 깎인다", foe.hp == hp, (hp, foe.hp))
    bt, me, foe = fight(mon("GARGANACL", 60, ["SALTCURE"]), mon("SNORLAX", 60))
    foe.cond["sub"] = 50
    use(bt, "me", "SALTCURE")
    chk("대타가 맞았으면 안 절여진다", not foe.cond.get("saltcure"))
    vol = B.Fighter(DEX, mon("SNORLAX", 60))
    vol.cond["saltcure"] = True
    f2 = B.Fighter(DEX, mon("SNORLAX", 60))
    f2.load_volatile(json.loads(json.dumps(vol.volatile())))
    chk("저장했다 되살려도 남는다 (턴마다 잤다 깨는 배틀)", f2.cond.get("saltcure") is True)

    print("-- 제보: 사우전드애로")
    bt, me, foe = fight(mon("ZYGARDE", 60, ["THOUSANDARROWS", "EARTHQUAKE"]), mon("PIDGEOT", 60))
    ev = use(bt, "me", "EARTHQUAKE")
    chk("지진은 비행 타입에게 안 맞는다", not hits(ev) and "효과가 없는" in texts(ev), texts(ev))
    ev = use(bt, "me", "THOUSANDARROWS")
    chk("사우전드애로는 맞는다", hits(ev) and hits(ev)[0] > 0, texts(ev))
    chk("  효과는 보통이다 (굉장하지도 별로이지도 않다)", "굉장" not in texts(ev) and "별로" not in texts(ev), texts(ev))
    chk("  맞으면 땅으로 떨어진다", foe.cond.get("smackdown") and "땅으로 떨어졌다" in texts(ev), texts(ev))
    foe.hp = foe.maxhp
    ev = use(bt, "me", "EARTHQUAKE")
    chk("  그 뒤로는 지진도 맞는다", hits(ev) and hits(ev)[0] > 0, texts(ev))
    bt, me, foe = fight(mon("ZYGARDE", 60, ["THOUSANDARROWS", "EARTHQUAKE"]),
                        mon("BRONZONG", 100, ability="LEVITATE"))
    ev = use(bt, "me", "THOUSANDARROWS")
    chk("부유도 맞힌다", hits(ev) and hits(ev)[0] > 0, texts(ev))
    foe.hp = foe.maxhp
    ev = use(bt, "me", "EARTHQUAKE")
    chk("  떨어진 뒤에는 지진도 맞는다", hits(ev) and hits(ev)[0] > 0, texts(ev))
    bt, me, foe = fight(mon("ZYGARDE", 60, ["THOUSANDARROWS"]), mon("MAGNEZONE", 60))
    foe.cond["magnetrise"] = 5
    ev = use(bt, "me", "THOUSANDARROWS")
    chk("전자부유도 맞히고 떨어뜨린다", hits(ev) and not foe.cond.get("magnetrise"), (texts(ev), foe.cond))
    bt, me, foe = fight(mon("ZYGARDE", 60, ["THOUSANDARROWS"]), mon("SNORLAX", 60))
    ev = use(bt, "me", "THOUSANDARROWS")
    chk("땅에 있던 상대에게는 떨어졌다는 말이 없다", "떨어졌다" not in texts(ev), texts(ev))

    print("-- 제보: 거대해머는 연달아 못 쓴다")
    bt, me, foe = fight(mon("TINKATON", 60, ["GIGATONHAMMER", "TACKLE"]), mon("SNORLAX", 60))
    ev = use(bt, "me", "GIGATONHAMMER")
    chk("처음에는 나간다", hits(ev), texts(ev))
    chk("바로 다음 턴에는 칸이 막힌다", "연달아" in (SM.restricted(bt, me, "GIGATONHAMMER") or ""),
        SM.restricted(bt, me, "GIGATONHAMMER"))
    chk("  AI 도 안 고른다", bt.usable(me) == ["TACKLE"], bt.usable(me))
    ev = use(bt, "me", "GIGATONHAMMER")
    chk("  억지로 보내도 안 나간다", not hits(ev) and "연달아" in texts(ev), texts(ev))
    use(bt, "me", "TACKLE")
    chk("다른 기술을 쓰고 나면 다시 쓸 수 있다", SM.restricted(bt, me, "GIGATONHAMMER") is None)
    ev = use(bt, "me", "GIGATONHAMMER")
    chk("  나간다", hits(ev), texts(ev))
    bt, me, foe = fight(mon("TINKATON", 60, ["GIGATONHAMMER"]), mon("SNORLAX", 60))
    use(bt, "me", "GIGATONHAMMER")
    chk("기술이 그것뿐이면 막지 않는다 (몸부림만 남지 않게)", SM.restricted(bt, me, "GIGATONHAMMER") is None)


# ---------------------------------------------------------------- 2. 쓰고 나면
def t_after_use():
    print("-- 반동 턴 (파괴광선·기가임팩트 ...)")
    for k in ("HYPERBEAM", "GIGAIMPACT", "HYDROCANNON", "FRENZYPLANT", "BLASTBURN", "ROCKWRECKER"):
        chk("%s 에는 반동 표시가 있다" % k, "recharge" in SM.flags(DEX.move(k)), DEX.move(k).get("flags"))
    bt, me, foe = fight(mon("SNORLAX", 50, ["HYPERBEAM", "TACKLE"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "HYPERBEAM")
    chk("맞히면 다음 턴에 쉰다", hits(ev) and me.cond.get("recharge"), me.cond)
    ev = use(bt, "me", "TACKLE")
    chk("  다음 턴: 못 움직인다", not hits(ev) and "반동으로" in texts(ev), texts(ev))
    ev = use(bt, "me", "TACKLE")
    chk("  그다음 턴: 움직인다", hits(ev), texts(ev))
    bt, me, foe = fight(mon("SNORLAX", 50, ["HYPERBEAM"]), mon("GENGAR", 50))
    ev = use(bt, "me", "HYPERBEAM")
    chk("안 맞았으면(무효) 안 쉰다", not me.cond.get("recharge"), (texts(ev), me.cond))
    f2 = B.Fighter(DEX, mon("SNORLAX", 50))
    f2.load_volatile(json.loads(json.dumps({"cond": {"recharge": True}})))
    chk("저장했다 되살려도 쉰다", f2.cond.get("recharge") is True)

    print("-- 쓰면 쓰러진다 (대폭발·자폭·미스트버스트·추억의선물)")
    for k in ("EXPLOSION", "SELFDESTRUCT", "MISTYEXPLOSION"):
        bt, me, foe = fight(mon("ELECTRODE", 50, [k]), mon("SNORLAX", 50))
        ev = use(bt, "me", k)
        chk("%s: 때리고 쓴 쪽이 쓰러진다" % k, hits(ev) and me.hp == 0 and "쓰러졌다" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("ELECTRODE", 50, ["EXPLOSION"]), mon("GENGAR", 50))
    ev = use(bt, "me", "EXPLOSION")
    chk("대폭발: 안 통해도(고스트) 쓴 쪽은 쓰러진다", not hits(ev) and me.hp == 0, texts(ev))
    bt, me, foe = fight(mon("ELECTRODE", 50, ["EXPLOSION"]), mon("GOLDUCK", 50, ability="DAMP"))
    ev = use(bt, "me", "EXPLOSION")
    chk("습기가 있으면 터지지도 쓰러지지도 않는다", me.hp == me.maxhp and foe.hp == foe.maxhp, texts(ev))
    bt, me, foe = fight(mon("ELECTRODE", 50, ["EXPLOSION"]), mon("SNORLAX", 50))
    foe.hp = 1
    ev = use(bt, "me", "EXPLOSION")
    chk("둘 다 쓰러지면 상대가 쓰러진 것으로 끝난다 (이김)", bt.over and bt.result == "won", (bt.over, bt.result))
    chk("  쓰러졌다는 말은 한 마리에 한 번씩", sum(1 for e in ev if e.get("t") == "faint") == 2,
        [e for e in ev if e.get("t") == "faint"])
    bt, me, foe = fight(mon("GENGAR", 50, ["MEMENTO"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "MEMENTO")
    chk("추억의선물: 상대의 공격·특수공격을 크게 내리고 쓰러진다",
        foe.stages["atk"] == -2 and foe.stages["spa"] == -2 and me.hp == 0, (foe.stages, me.hp))

    print("-- 쓰면 체력 절반을 잃는다 (깜짝헤드·철제광선)")
    for k in ("MINDBLOWN", "STEELBEAM"):
        bt, me, foe = fight(mon("ELECTRODE", 50, [k]), mon("SNORLAX", 50))
        ev = use(bt, "me", k)
        chk("%s: 올림한 절반" % k, me.maxhp - me.hp == (me.maxhp + 1) // 2, (me.hp, me.maxhp, texts(ev)))
    bt, me, foe = fight(mon("CLEFABLE", 50, ["STEELBEAM"], ability="MAGICGUARD"), mon("SNORLAX", 50))
    use(bt, "me", "STEELBEAM")
    chk("매직가드는 안 깎인다", me.hp == me.maxhp, me.hp)

    print("-- 빗나가면 다친다 (무릎차기·점프킥·발꿈치찍기·썬더다이브)")
    for k in sorted(AF.CRASH):
        bt, me, foe = fight(mon("LUCARIO", 50, [k]), mon("SNORLAX", 50))
        foe.cond["protect"] = "PROTECT"
        ev = use(bt, "me", k)
        chk("%s: 막히면 최대 체력의 절반" % k, me.maxhp - me.hp == me.maxhp // 2, (me.hp, me.maxhp, texts(ev)))
    bt, me, foe = fight(mon("LUCARIO", 50, ["HIGHJUMPKICK"]), mon("GENGAR", 50))
    ev = use(bt, "me", "HIGHJUMPKICK")
    chk("무릎차기: 고스트에게 안 통해도 다친다", me.hp < me.maxhp and "부딪쳤다" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("LUCARIO", 50, ["HIGHJUMPKICK"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "HIGHJUMPKICK")
    chk("  맞으면 안 다친다", hits(ev) and me.hp == me.maxhp, texts(ev))
    bt, me, foe = fight(mon("LUCARIO", 50, ["HIGHJUMPKICK"]), mon("SNORLAX", 50))
    me.status, me.sleep_turns = "sleep", 3
    ev = use(bt, "me", "HIGHJUMPKICK")
    chk("  잠들어 못 쓴 것은 빗나간 것이 아니다", me.hp == me.maxhp, texts(ev))


# ---------------------------------------------------------------- 3. 쓸 수 있을 때
def t_conditions():
    print("-- 쓸 수 있는 조건")
    bt, me, foe = fight(mon("GENGAR", 50, ["DREAMEATER"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "DREAMEATER")
    chk("꿈먹기: 깨어 있는 상대에게는 실패", not hits(ev) and "실패" in texts(ev), texts(ev))
    foe.status, foe.sleep_turns = "sleep", 3
    ev = use(bt, "me", "DREAMEATER")
    chk("  잠든 상대에게는 들어가고 회복한다", hits(ev), texts(ev))

    bt, me, foe = fight(mon("ABSOL", 50, ["SUCKERPUNCH"]), mon("SNORLAX", 50, ["TACKLE", "GROWL"]))
    bt.begin_turn()
    bt.pending = {"me": "SUCKERPUNCH", "foe": "GROWL"}
    ev = use(bt, "me", "SUCKERPUNCH")
    chk("기습: 상대가 변화기를 쓰려 하면 실패", not hits(ev) and "실패" in texts(ev), texts(ev))
    bt.begin_turn()
    bt.pending = {"me": "SUCKERPUNCH", "foe": "TACKLE"}
    ev = use(bt, "me", "SUCKERPUNCH")
    chk("  공격하려 하면 들어간다", hits(ev), texts(ev))
    bt.begin_turn()
    bt.pending = {"me": "SUCKERPUNCH", "foe": None}
    ev = use(bt, "me", "SUCKERPUNCH")
    chk("  상대가 교체했으면 실패", not hits(ev), texts(ev))
    bt.begin_turn()
    bt.pending = {"me": "SUCKERPUNCH", "foe": "TACKLE"}
    use(bt, "foe", "TACKLE")
    ev = use(bt, "me", "SUCKERPUNCH")
    chk("  상대가 이미 움직였으면 실패", not hits(ev), texts(ev))
    bt.begin_turn()
    ev = use(bt, "me", "SUCKERPUNCH")
    chk("  상대가 뭘 할지 모르는 판(레이드)에서는 그냥 나간다", hits(ev), texts(ev))
    bt, me, foe = fight(mon("ABSOL", 50, ["SUCKERPUNCH"]), mon("SNORLAX", 50, ["TACKLE", "GROWL"]))
    ev = bt.take_turn("SUCKERPUNCH")
    chk("기습: 진짜 한 턴에서도 판정이 선다 (상대가 고른 것을 본다)",
        ("실패" in texts(ev)) == (not MC.attacks(DEX.move(bt.pending.get("foe")))), (bt.pending, texts(ev)))

    bt, me, foe = fight(mon("MACHAMP", 50, ["FOCUSPUNCH"]), mon("SNORLAX", 50))
    bt.begin_turn()
    use(bt, "foe", "TACKLE")
    ev = use(bt, "me", "FOCUSPUNCH")
    chk("힘껏펀치: 쓰기 전에 맞으면 실패", not hits(ev) and "집중" in texts(ev), texts(ev))
    bt.begin_turn()
    ev = use(bt, "me", "FOCUSPUNCH")
    chk("  안 맞았으면 나간다", hits(ev), texts(ev))

    bt, me, foe = fight(mon("EEVEE", 50, ["LASTRESORT", "TACKLE", "GROWL"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "LASTRESORT")
    chk("비장의무기: 다른 기술을 다 쓰기 전에는 실패", not hits(ev), texts(ev))
    use(bt, "me", "TACKLE")
    ev = use(bt, "me", "LASTRESORT")
    chk("  하나 남았어도 실패", not hits(ev), texts(ev))
    use(bt, "me", "GROWL")
    ev = use(bt, "me", "LASTRESORT")
    chk("  다 쓴 뒤에는 나간다", hits(ev), texts(ev))

    bt, me, foe = fight(mon("GENGAR", 50, ["POLTERGEIST"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "POLTERGEIST")
    chk("폴터가이스트: 도구가 없는 상대에게는 실패", not hits(ev), texts(ev))
    bt, me, foe = fight(mon("GENGAR", 50, ["POLTERGEIST"]), mon("MACHAMP", 50, held="LEFTOVERS"))
    ev = use(bt, "me", "POLTERGEIST")
    chk("  도구가 있으면 들어간다", hits(ev), texts(ev))

    bt, me, foe = fight(mon("SNORLAX", 50, ["BELCH"], held="SITRUSBERRY"), mon("MACHAMP", 50))
    ev = use(bt, "me", "BELCH")
    chk("트림: 나무열매를 먹기 전에는 실패", not hits(ev), texts(ev))
    me.hp = me.maxhp // 3
    ev = []
    B.H.check_hp(bt, me, "me", ev)
    chk("  열매를 먹었다", me.cond.get("ateBerry"), (texts(ev), me.cond))
    ev = use(bt, "me", "BELCH")
    chk("  먹은 뒤에는 나간다", hits(ev), texts(ev))

    bt, me, foe = fight(mon("ARCANINE", 50, ["BURNUP"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "BURNUP")
    chk("불사르기: 때리고 불꽃 타입을 잃는다", hits(ev) and "FIRE" not in me.types(), (me.types(), texts(ev)))
    ev = use(bt, "me", "BURNUP")
    chk("  불꽃이 아니면 실패", not hits(ev), texts(ev))
    bt, me, foe = fight(mon("PAWMOT", 50, ["DOUBLESHOCK"]), mon("SNORLAX", 50))
    use(bt, "me", "DOUBLESHOCK")
    chk("전광쌍격: 전기 타입을 잃는다", me.types() == ["FIGHTING"], me.types())

    bt, me, foe = fight(mon("GENGAR", 50, ["CAPTIVATE"], gender="M"), mon("SNORLAX", 50, gender="M"))
    ev = use(bt, "me", "CAPTIVATE")
    chk("유혹: 같은 성별에게는 실패", foe.stages["spa"] == 0, texts(ev))
    bt, me, foe = fight(mon("GENGAR", 50, ["CAPTIVATE"], gender="M"), mon("SNORLAX", 50, gender="F"))
    use(bt, "me", "CAPTIVATE")
    chk("  다른 성별이면 특수공격이 크게 떨어진다", foe.stages["spa"] == -2, foe.stages)
    bt, me, foe = fight(mon("ARBOK", 50, ["VENOMDRENCH"]), mon("SNORLAX", 50))
    use(bt, "me", "VENOMDRENCH")
    chk("베놈트랩: 독이 아닌 상대에게는 실패", foe.stages["atk"] == 0, foe.stages)
    foe.status = "poison"
    use(bt, "me", "VENOMDRENCH")
    chk("  독 상태면 셋이 떨어진다", (foe.stages["atk"], foe.stages["spa"], foe.stages["spe"]) == (-1, -1, -1),
        foe.stages)
    bt, me, foe = fight(mon("MACHAMP", 50, ["COACHING"]), mon("SNORLAX", 50))
    use(bt, "me", "COACHING")
    chk("코칭: 같은 편이 없으면 실패 (내 능력이 오르지 않는다)", me.stages["atk"] == 0, me.stages)
    bt, me, foe = fight(mon("KLINKLANG", 50, ["GEARUP"], ability="CLEARBODY"), mon("SNORLAX", 50))
    use(bt, "me", "GEARUP")
    chk("어시스트기어: 플러스·마이너스가 아니면 실패", me.stages["atk"] == 0, me.stages)
    bt, me, foe = fight(mon("KLINKLANG", 50, ["GEARUP"], ability="PLUS"), mon("SNORLAX", 50))
    use(bt, "me", "GEARUP")
    chk("  플러스면 오른다", me.stages["atk"] == 1 and me.stages["spa"] == 1, me.stages)


# ---------------------------------------------------------------- 4. 어느 능력치로
def t_stats():
    print("-- 어느 능력치로 세는가")
    bt, me, foe = fight(mon("SHUCKLE", 50, ["BODYPRESS", "TACKLE"]), mon("SNORLAX", 50))
    a, d = me.stat("atk"), me.stat("def")
    chk("바디프레스: 방어가 높으면 세다 (방어로 때린다)",
        d > a * 5 and est(bt, me, foe, "BODYPRESS") > est(bt, me, foe, "TACKLE") * 8,
        (a, d, est(bt, me, foe, "BODYPRESS"), est(bt, me, foe, "TACKLE")))
    me.stages["def"] = 2
    up = est(bt, me, foe, "BODYPRESS")
    me.stages["def"] = 0
    chk("  방어 랭크도 따라간다", up > est(bt, me, foe, "BODYPRESS") * 1.8, (up, est(bt, me, foe, "BODYPRESS")))

    bt, me, foe = fight(mon("BLISSEY", 50, ["FOULPLAY"]), mon("MACHAMP", 50))
    weak = est(bt, me, foe, "FOULPLAY")
    foe.stages["atk"] = 2
    chk("속임수: 상대의 공격이 오르면 더 아프다", est(bt, me, foe, "FOULPLAY") > weak * 1.8,
        (weak, est(bt, me, foe, "FOULPLAY")))
    me.stages["atk"] = -6
    chk("  내 공격 랭크는 상관없다", est(bt, me, foe, "FOULPLAY") > weak * 1.8)

    bt, me, foe = fight(mon("ALAKAZAM", 50, ["PSYSHOCK", "PSYCHIC"]), mon("BLISSEY", 50))
    chk("사이코쇼크: 특수방어가 높고 방어가 낮은 상대에게 더 아프다",
        foe.stat("spd") > foe.stat("def") * 3 and est(bt, me, foe, "PSYSHOCK") > est(bt, me, foe, "PSYCHIC") * 2,
        (foe.stat("def"), foe.stat("spd"), est(bt, me, foe, "PSYSHOCK"), est(bt, me, foe, "PSYCHIC")))
    chk("사이코브레이크·신비의칼도 방어로 받는다", {"PSYSTRIKE", "SECRETSWORD"} <= AF.HITS_DEF)

    bt, me, foe = fight(mon("MACHAMP", 50, ["PHOTONGEYSER"]), mon("SNORLAX", 50))
    chk("포톤가이저: 공격이 높으면 물리로 친다", AF.physical(DEX.move("PHOTONGEYSER"), me, foe) is True)
    bt2, me2, foe2 = fight(mon("ALAKAZAM", 50, ["PHOTONGEYSER"]), mon("SNORLAX", 50))
    chk("  특수공격이 높으면 특수로 친다", AF.physical(DEX.move("PHOTONGEYSER"), me2, foe2) is False)
    bt.field.side("foe")["reflect"] = 5
    with_wall = est(bt, me, foe, "PHOTONGEYSER")
    bt.field.side("foe").pop("reflect")
    chk("  물리로 칠 때는 리플렉터에 막힌다", with_wall * 1.8 < est(bt, me, foe, "PHOTONGEYSER"),
        (with_wall, est(bt, me, foe, "PHOTONGEYSER")))

    bt, me, foe = fight(mon("COBALION", 50, ["SACREDSWORD", "CLOSECOMBAT"]), mon("SNORLAX", 50))
    base = est(bt, me, foe, "SACREDSWORD")
    foe.stages["def"] = 6
    chk("성스러운칼: 상대의 방어 랭크를 무시한다", est(bt, me, foe, "SACREDSWORD") == base,
        (base, est(bt, me, foe, "SACREDSWORD")))
    chk("  보통 기술은 줄어든다", est(bt, me, foe, "CLOSECOMBAT") < base)
    foe.stages["def"] = 0
    foe.stages["eva"] = 6
    n = sum(1 for s in range(60)
            if B.accuracy_check(DEX, DEX.move("SACREDSWORD"), me, foe, random.Random(s)))
    chk("  회피 랭크도 무시한다", n == 60, n)
    chk("야금야금·DD래리어트도 같다", {"CHIPAWAY", "DARKESTLARIAT"} <= AF.IGNORE_STAGES)

    print("-- 급소는 맞는 쪽의 방어 '상승' 을 무시한다")
    bt, me, foe = fight(mon("MACHAMP", 50, ["TACKLE"]), mon("SNORLAX", 50), abilities=False)
    plain, _c, _e = B.damage(DEX, DEX.move("TACKLE"), me, foe, B.EST_RNG, crit=True)
    foe.stages["def"] = 6
    up, _c, _e = B.damage(DEX, DEX.move("TACKLE"), me, foe, B.EST_RNG, crit=True)
    chk("방어를 +6 해도 급소 데미지는 그대로", up == plain, (plain, up))
    foe.stages["def"] = -6
    down, _c, _e = B.damage(DEX, DEX.move("TACKLE"), me, foe, B.EST_RNG, crit=True)
    chk("방어가 내려가 있으면 급소가 더 아프다 (예전에는 없던 일로 했다)", down > plain * 2, (plain, down))

    print("-- 상성")
    bt, me, foe = fight(mon("HAWLUCHA", 50, ["FLYINGPRESS"]), mon("BRELOOM", 50))
    _d, _c, e = B.damage(DEX, DEX.move("FLYINGPRESS"), me, foe, B.EST_RNG, crit=False)
    chk("플라잉프레스: 풀/격투에게 격투(1) x 비행(4) = 4배", e == 4.0, e)
    bt, me, foe = fight(mon("HAWLUCHA", 50, ["FLYINGPRESS"]), mon("GENGAR", 50))
    _d, _c, e = B.damage(DEX, DEX.move("FLYINGPRESS"), me, foe, B.EST_RNG, crit=False)
    chk("  고스트에게는 안 통한다", e == 0.0, e)
    bt, me, foe = fight(mon("KORAIDON", 50, ["COLLISIONCOURSE"]), mon("SNORLAX", 50))
    se = est(bt, me, foe, "COLLISIONCOURSE")
    foe.types_override = ["WATER"]
    neutral = est(bt, me, foe, "COLLISIONCOURSE")
    chk("엑셀브레이크: 효과가 굉장하면 2배보다 더 세다 (x1.33)",
        abs(se / float(neutral) - 2.0 * 5461 / 4096.0) < 0.05, (se, neutral))


# ---------------------------------------------------------------- 5. 위력
def t_power():
    print("-- 위력이 달라지는 기술")

    def pw(k, user, target):
        return AF.power(k, DEX.move(k)["power"], DEX.move(k), user, target)

    bt, me, foe = fight(mon("OVERQWIL", 50, ["BARBBARRAGE"]), mon("SNORLAX", 50))
    chk("독침천발: 보통 60", pw("BARBBARRAGE", me, foe) == 60)
    foe.status = "poison"
    chk("  독 상태면 두 배", pw("BARBBARRAGE", me, foe) == 120)

    bt, me, foe = fight(mon("OBSTAGOON", 50, ["LASHOUT", "TACKLE"]), mon("SNORLAX", 50, ["GROWL"]))
    bt.begin_turn()
    chk("분풀이: 보통 75", pw("LASHOUT", me, foe) == 75)
    use(bt, "foe", "GROWL")
    chk("  그 턴에 능력이 떨어졌으면 두 배", pw("LASHOUT", me, foe) == 150, me.cond)
    bt.begin_turn()
    chk("  다음 턴에는 다시 보통", pw("LASHOUT", me, foe) == 75, me.cond)

    bt, me, foe = fight(mon("MAMOSWINE", 50, ["STOMPINGTANTRUM", "EARTHQUAKE"]), mon("PIDGEOT", 50))
    use(bt, "me", "EARTHQUAKE")
    chk("분함의발구르기: 앞 기술이 안 통했으면 두 배", pw("STOMPINGTANTRUM", me, foe) == 150, me.cond)
    foe.types_override = ["NORMAL"]
    use(bt, "me", "EARTHQUAKE")
    chk("  앞 기술이 맞았으면 보통", pw("STOMPINGTANTRUM", me, foe) == 75, me.cond)
    chk("열불내기도 같다", pw("TEMPERFLARE", me, foe) == 75)

    bt, me, foe = fight(mon("SCIZOR", 50, ["FURYCUTTER", "TACKLE"]), mon("SNORLAX", 100))
    got = []
    for _ in range(4):
        got.append(pw("FURYCUTTER", me, foe))
        use(bt, "me", "FURYCUTTER")
    chk("연속자르기: 40 -> 80 -> 160 -> 160", got == [40, 80, 160, 160], got)
    use(bt, "me", "TACKLE")
    chk("  다른 기술을 쓰면 처음으로", pw("FURYCUTTER", me, foe) == 40)
    bt, me, foe = fight(mon("GOLEM", 50, ["ROLLOUT"]), mon("SNORLAX", 100))
    got = []
    for _ in range(6):
        got.append(pw("ROLLOUT", me, foe))
        use(bt, "me", "ROLLOUT")
    chk("구르기: 30 60 120 240 480, 다섯 번이면 처음으로", got == [30, 60, 120, 240, 480, 30], got)
    bt, me, foe = fight(mon("EXPLOUD", 50, ["ECHOEDVOICE"]), mon("SNORLAX", 100))
    got = []
    for _ in range(6):
        got.append(pw("ECHOEDVOICE", me, foe))
        use(bt, "me", "ECHOEDVOICE")
    chk("에코보이스: 40 80 120 160 200 200", got == [40, 80, 120, 160, 200, 200], got)

    bt, me, foe = fight(mon("ANNIHILAPE", 50, ["RAGEFIST"]), mon("SNORLAX", 50, ["BITE"]))
    chk("분노의주먹: 보통 50", pw("RAGEFIST", me, foe) == 50)
    for _ in range(3):
        use(bt, "foe", "BITE")
    chk("  세 대 맞으면 200", pw("RAGEFIST", me, foe) == 200, me.cond)
    me.cond["hitsTaken"] = 6
    chk("  여섯 대 넘게는 안 오른다 (350)", pw("RAGEFIST", me, foe) == 350)

    bt, me, foe = fight(mon("STOUTLAND", 50, ["RETALIATE"]), mon("SNORLAX", 50))
    bt.begin_turn()
    chk("원수갚기: 보통 70", pw("RETALIATE", me, foe) == 70)
    bt._note_fall("me")
    bt.begin_turn()
    chk("  앞 턴에 같은 편이 쓰러졌으면 두 배", pw("RETALIATE", me, foe) == 140, bt.field.sides)
    bt.begin_turn()
    chk("  한 턴 지나면 보통", pw("RETALIATE", me, foe) == 70)
    f2 = FD.Field.load(json.loads(json.dumps(bt.field.dump())))
    chk("  판을 저장했다 되살려도 턴 수가 남는다", f2.clock == bt.field.clock and f2.side("me").get("fellAt") is not None)

    bt, me, foe = fight(mon("WEAVILE", 50, ["TRIPLEAXEL"], ability="NOGUARD"), mon("SNORLAX", 100))
    ev = use(bt, "me", "TRIPLEAXEL")
    h = hits(ev)
    chk("트리플악셀: 세 번 맞고 갈수록 세다", len(h) == 3 and h[0] < h[1] < h[2], h)
    bt, me, foe = fight(mon("TINKATON", 50, ["GRAVAPPLE"]), mon("SNORLAX", 50))
    chk("G의힘: 보통 80", pw("GRAVAPPLE", me, foe) == 80)
    bt.field.rooms["gravity"] = 5
    chk("  중력이 있으면 1.5배", pw("GRAVAPPLE", me, foe) == 120)

    bt, me, foe = fight(mon("PIKACHU", 50, ["CHARGE", "THUNDERSHOCK", "TACKLE"]), mon("SNORLAX", 50))
    plain = est(bt, me, foe, "THUNDERSHOCK")
    ev = use(bt, "me", "CHARGE")
    chk("충전: 특수방어가 오르고 전기를 모은다", me.stages["spd"] == 1 and me.cond.get("charged"), texts(ev))
    chk("  다음 전기 기술이 두 배", est(bt, me, foe, "THUNDERSHOCK") >= plain * 2 - 2, (plain, est(bt, me, foe, "THUNDERSHOCK")))
    chk("  다른 타입은 그대로", est(bt, me, foe, "TACKLE") == est(*fight(mon("PIKACHU", 50), mon("SNORLAX", 50)), "TACKLE"))
    use(bt, "me", "THUNDERSHOCK")
    chk("  한 번 쓰면 풀린다", not me.cond.get("charged"), me.cond)


# ---------------------------------------------------------------- 6. 맞힌 뒤
def t_after_hit():
    print("-- 맞힌 뒤의 효과")
    bt, me, foe = fight(mon("SCIZOR", 50, ["FALSESWIPE"]), mon("PIDGEY", 5))
    ev = use(bt, "me", "FALSESWIPE")
    chk("칼등치기: 한참 센 공격이어도 1 을 남긴다", foe.hp == 1 and not bt.over, (foe.hp, texts(ev)))
    ev = use(bt, "me", "FALSESWIPE")
    chk("  체력 1 인 상대는 더 안 깎인다", foe.hp == 1 and not bt.over, foe.hp)

    bt, me, foe = fight(mon("DHELMISE", 50, ["ANCHORSHOT"]), mon("SNORLAX", 50))
    use(bt, "me", "ANCHORSHOT")
    chk("앵커샷: 맞으면 못 도망간다", SM.trapped(bt, foe), foe.cond)
    bt, me, foe = fight(mon("DHELMISE", 50, ["ANCHORSHOT"]), mon("GENGAR", 50))
    foe.types_override = ["GHOST", "POISON"]
    use(bt, "me", "ANCHORSHOT")
    chk("  고스트는 안 걸린다", not SM.trapped(bt, foe))
    chk("그림자꿰매기·사우전드웨이브도 같다", {"SPIRITSHACKLE", "THOUSANDWAVES"} <= AF.TRAP_HIT)
    bt, me, foe = fight(mon("DREDNAW", 50, ["JAWLOCK"]), mon("SNORLAX", 50))
    use(bt, "me", "JAWLOCK")
    chk("물고버티기: 둘 다 못 도망간다", SM.trapped(bt, foe) and SM.trapped(bt, me), (me.cond, foe.cond))

    bt, me, foe = fight(mon("WEEZING", 50, ["CLEARSMOG"]), mon("SNORLAX", 50))
    foe.stages.update({"atk": 6, "def": -2})
    use(bt, "me", "CLEARSMOG")
    chk("클리어스모그: 능력 변화를 되돌린다", not any(foe.stages.values()), foe.stages)

    bt, me, foe = fight(mon("ARCANINE", 50, ["BURNINGJEALOUSY"]), mon("SNORLAX", 50, ["SWORDSDANCE"]))
    bt.begin_turn()
    use(bt, "me", "BURNINGJEALOUSY")
    chk("질투의불꽃: 능력이 안 오른 상대는 안 데인다 (예전에는 늘 데였다)", foe.status is None, foe.status)
    bt.begin_turn()
    use(bt, "foe", "SWORDSDANCE")
    use(bt, "me", "BURNINGJEALOUSY")
    chk("  그 턴에 능력이 오른 상대는 화상", foe.status == "burn", (foe.status, foe.cond))
    bt, me, foe = fight(mon("PRIMARINA", 50, ["ALLURINGVOICE"]), mon("SNORLAX", 50, ["SWORDSDANCE"]))
    bt.begin_turn()
    use(bt, "foe", "SWORDSDANCE")
    use(bt, "me", "ALLURINGVOICE")
    chk("매혹의보이스: 그 턴에 능력이 오른 상대는 혼란", foe.cond.get("confused"), foe.cond)

    bt, me, foe = fight(mon("WEAVILE", 50, ["THIEF"]), mon("SNORLAX", 50, held="LEFTOVERS"))
    ev = use(bt, "me", "THIEF")
    chk("도둑질: 도구를 빼앗아 내가 쓴다", me.held == "LEFTOVERS" and foe.held is None, (me.held, foe.held, texts(ev)))
    f2 = B.Fighter(DEX, me.mon)
    f2.load_volatile(json.loads(json.dumps(me.volatile())))
    chk("  저장했다 되살려도 빼앗은 도구가 남는다", f2.held == "LEFTOVERS", f2.held)
    f3 = B.Fighter(DEX, foe.mon)
    f3.load_volatile(json.loads(json.dumps(foe.volatile())))
    chk("  빼앗긴 쪽은 없는 채로", f3.held is None, f3.held)
    bt, me, foe = fight(mon("WEAVILE", 50, ["THIEF"], held="CHARCOAL"), mon("SNORLAX", 50, held="LEFTOVERS"))
    use(bt, "me", "THIEF")
    chk("  내가 도구를 지녔으면 못 훔친다", me.held == "CHARCOAL" and foe.held == "LEFTOVERS")
    bt, me, foe = fight(mon("WEAVILE", 50, ["COVET"]), mon("MUK", 50, held="LEFTOVERS", ability="STICKYHOLD"))
    use(bt, "me", "COVET")
    chk("  점착은 안 빼앗긴다", foe.held == "LEFTOVERS")

    bt, me, foe = fight(mon("SCIZOR", 50, ["BUGBITE"]), mon("SNORLAX", 50, held="SITRUSBERRY"))
    me.hp = 10
    ev = use(bt, "me", "BUGBITE")
    chk("벌레먹기: 상대의 열매를 먹어 내가 회복한다", me.hp > 10 and foe.held is None, (me.hp, texts(ev)))
    chk("  내 도구 자리는 그대로 비어 있다", me.held is None and me.cond.get("ateBerry"))
    bt, me, foe = fight(mon("ARCANINE", 50, ["INCINERATE"]), mon("SNORLAX", 50, held="SITRUSBERRY"))
    ev = use(bt, "me", "INCINERATE")
    chk("불태우기: 상대의 열매가 타 버린다", foe.held is None and "타 버렸다" in texts(ev), texts(ev))
    foe.hp = foe.maxhp // 4
    ev = []
    B.H.check_hp(bt, foe, "foe", ev)
    chk("  탄 열매는 못 먹는다", foe.hp == foe.maxhp // 4, texts(ev))

    bt, me, foe = fight(mon("BEEDRILL", 50, ["FELLSTINGER"]), mon("PIDGEY", 5))
    use(bt, "me", "FELLSTINGER")
    chk("마지막일침: 쓰러뜨리면 공격이 3랭크 오른다", me.stages["atk"] == 3, me.stages)
    bt, me, foe = fight(mon("GARCHOMP", 50, ["SCALESHOT"]), mon("SNORLAX", 100))
    use(bt, "me", "SCALESHOT")
    chk("스케일샷: 스피드가 오르고 방어가 떨어진다", (me.stages["spe"], me.stages["def"]) == (1, -1), me.stages)
    bt, me, foe = fight(mon("KLEAVOR", 50, ["STONEAXE"]), mon("SNORLAX", 100))
    ev = use(bt, "me", "STONEAXE")
    chk("암석액스: 상대 쪽에 뾰족한 바위가 깔린다", bt.field.side("foe").get("stealthrock") == 1, bt.field.sides)
    bt, me, foe = fight(mon("OGERPON", 50, ["SYRUPBOMB"]), mon("SNORLAX", 100))
    use(bt, "me", "SYRUPBOMB")
    spe0 = foe.stages["spe"]
    for _ in range(4):
        eot(bt)
    chk("시럽봄: 세 턴 동안 턴마다 스피드가 떨어진다", spe0 - foe.stages["spe"] == 3 and not foe.cond.get("syrup"),
        (spe0, foe.stages["spe"], foe.cond))
    bt, me, foe = fight(mon("MAROWAK", 50, ["SPECTRALTHIEF"]), mon("MACHAMP", 100))
    foe.stages.update({"atk": 2, "spe": 1, "def": -1})
    use(bt, "me", "SPECTRALTHIEF")
    chk("섀도스틸: 올라간 능력만 빼앗는다",
        (me.stages["atk"], me.stages["spe"]) == (2, 1) and (foe.stages["atk"], foe.stages["def"]) == (0, -1),
        (me.stages, foe.stages))
    bt, me, foe = fight(mon("MAROWAK", 50, ["SPECTRALTHIEF"]), mon("SNORLAX", 100))
    foe.stages["atk"] = 2
    use(bt, "me", "SPECTRALTHIEF")
    chk("  안 통하는 상대(노말)에게서는 못 빼앗는다", foe.stages["atk"] == 2 and me.stages["atk"] == 0,
        (me.stages, foe.stages))
    bt, me, foe = fight(mon("GENGAR", 50, ["EERIESPELL"]), mon("SNORLAX", 100, ["TACKLE"]))
    use(bt, "foe", "TACKLE")
    pp = foe.pp["TACKLE"]
    use(bt, "me", "EERIESPELL")
    chk("섬뜩한주문: 마지막에 쓴 기술의 PP 가 3 준다", pp - foe.pp["TACKLE"] == 3, (pp, foe.pp))
    bt, me, foe = fight(mon("EXPLOUD", 50, ["PSYCHICNOISE"]), mon("BLISSEY", 100, ["SOFTBOILED"]))
    use(bt, "me", "PSYCHICNOISE")
    chk("사이코노이즈: 두 턴 동안 회복할 수 없다", foe.cond.get("healblock") == 2
        and "회복봉인" in (SM.restricted(bt, foe, "SOFTBOILED") or ""), foe.cond)
    bt, me, foe = fight(mon("PRIMARINA", 50, ["SPARKLINGARIA"]), mon("SNORLAX", 100))
    foe.status = "burn"
    use(bt, "me", "SPARKLINGARIA")
    chk("물거품아리아: 맞은 상대의 화상이 낫는다", foe.status is None)
    bt, me, foe = fight(mon("BAXCALIBUR", 50, ["GLAIVERUSH", "TACKLE"]), mon("SNORLAX", 100, ["TACKLE"]))
    plain = est(bt, foe, me, "TACKLE")
    use(bt, "me", "GLAIVERUSH")
    chk("대검돌격: 다음 내 차례까지 받는 데미지가 두 배", est(bt, foe, me, "TACKLE") >= plain * 2 - 2,
        (plain, est(bt, foe, me, "TACKLE")))
    foe.stages["acc"] = -6
    chk("  반드시 맞는다", all(B.accuracy_check(DEX, DEX.move("TACKLE"), foe, me, random.Random(s))
                         for s in range(30)))
    use(bt, "me", "TACKLE")
    chk("  내가 다음 기술을 쓰면 풀린다", not me.cond.get("glaive") and est(bt, foe, me, "TACKLE") == plain)


# ---------------------------------------------------------------- 7. 맹독
def t_toxic():
    print("-- 맹독: 턴마다 커진다")
    bt, me, foe = fight(mon("ARBOK", 50, ["TOXIC"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "TOXIC")
    chk("맹독이라고 알린다 (상태는 독으로 다룬다)", foe.status == "poison" and foe.cond.get("toxic") == 1
        and "맹독 상태" in texts(ev), (foe.status, foe.cond, texts(ev)))
    lost = []
    for _ in range(4):
        hp = foe.hp
        eot(bt)
        lost.append(hp - foe.hp)
    m = foe.maxhp
    chk("1/16, 2/16, 3/16, 4/16", lost == [m // 16, m * 2 // 16, m * 3 // 16, m * 4 // 16], (lost, m))
    bt, me, foe = fight(mon("ARBOK", 50, ["POISONSTING"]), mon("SNORLAX", 50))
    foe.status = "poison"
    hp = foe.hp
    eot(bt)
    chk("그냥 독은 늘 1/8", hp - foe.hp == foe.maxhp // 8, hp - foe.hp)
    bt, me, foe = fight(mon("ARBOK", 50, ["TOXIC"]), mon("MUK", 50))
    use(bt, "me", "TOXIC")
    chk("독 타입은 안 걸린다", foe.status is None)
    bt, me, foe = fight(mon("ARBOK", 50, ["TOXIC"]), mon("SNORLAX", 50, held="PECHABERRY"))
    use(bt, "me", "TOXIC")
    chk("복숭열매로 낫는다 (독으로 다루므로)", foe.status is None, foe.status)
    bt, me, foe = fight(mon("ARBOK", 50, ["TOXIC"]), mon("BRELOOM", 50, ability="POISONHEAL"))
    foe.types_override = ["FIGHTING"]
    use(bt, "me", "TOXIC")
    foe.hp = foe.maxhp // 2
    hp = foe.hp
    eot(bt)
    chk("포이즌힐은 맹독이어도 회복한다", foe.hp > hp, (hp, foe.hp))
    bt, me, foe = fight(mon("SNORLAX", 50, held="TOXICORB"), mon("SNORLAX", 50))
    eot(bt)
    chk("맹독구슬은 맹독으로 건다", me.status == "poison" and me.cond.get("toxic"), (me.status, me.cond))
    bt, me, foe = fight(mon("SNORLAX", 50), mon("SNORLAX", 50))
    bt.field.side("me")["toxicspikes"] = 2
    ev = []
    SM.enter(bt, "me", ev)
    chk("독압정 두 겹은 맹독", me.cond.get("toxic") == 1, (me.status, me.cond))
    bt.field.side("foe")["toxicspikes"] = 1
    SM.enter(bt, "foe", ev)
    chk("  한 겹은 그냥 독", foe.status == "poison" and not foe.cond.get("toxic"), (foe.status, foe.cond))
    bt, me, foe = fight(mon("PECHARUNT", 50, ["TACKLE"], ability="TOXICCHAIN"), mon("SNORLAX", 50))
    for s in range(40):
        bt.rng = random.Random(s)
        foe.status = None
        foe.cond.pop("toxic", None)
        foe.hp = foe.maxhp
        use(bt, "me", "TACKLE")
        if foe.status:
            break
    hp = foe.hp
    eot(bt)
    chk("독사슬로 건 맹독도 이제 깎인다 (예전에는 아무 일도 없었다)",
        foe.status == "poison" and foe.cond.get("toxic") and foe.hp < hp, (foe.status, foe.cond, hp, foe.hp))


# ---------------------------------------------------------------- 8. 미래예지
def t_future():
    print("-- 미래예지·파멸의소원")
    bt, me, foe = fight(mon("ALAKAZAM", 50, ["FUTURESIGHT"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "FUTURESIGHT")
    chk("쓴 턴에는 안 맞는다", not hits(ev) and foe.hp == foe.maxhp and "예지" in texts(ev), texts(ev))
    ev = use(bt, "me", "FUTURESIGHT")
    chk("이미 걸어 뒀으면 실패", "실패" in texts(ev), texts(ev))
    got = []
    for _ in range(3):
        ev = eot(bt)
        got.append(foe.maxhp - foe.hp)
    chk("두 턴 뒤 턴 끝에 떨어진다", got[0] == 0 and got[1] == 0 and got[2] > 0, got)
    chk("  떨어지면 예약이 지워진다", not bt.field.side("foe").get("future"))
    bt, me, foe = fight(mon("ALAKAZAM", 50, ["FUTURESIGHT"]), mon("SNORLAX", 50))
    foe.cond["protect"] = "PROTECT"
    ev = use(bt, "me", "FUTURESIGHT")
    chk("방어로는 못 막는다 (예약이 선다)", bt.field.side("foe").get("future"), texts(ev))
    f2 = FD.Field.load(json.loads(json.dumps(bt.field.dump())))
    chk("판을 저장했다 되살려도 예약이 남는다", (f2.side("foe").get("future") or {}).get("move") == "FUTURESIGHT")
    bt, me, foe = fight(mon("ALAKAZAM", 50, ["FUTURESIGHT"]), mon("UMBREON", 50))
    use(bt, "me", "FUTURESIGHT")
    for _ in range(3):
        ev = eot(bt)
    chk("악 타입에게는 떨어져도 효과가 없다", foe.hp == foe.maxhp and "효과가 없는" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("JIRACHI", 50, ["DOOMDESIRE"]), mon("SNORLAX", 50))
    use(bt, "me", "DOOMDESIRE")
    for _ in range(3):
        eot(bt)
    chk("파멸의소원도 같다", foe.hp < foe.maxhp)


# ---------------------------------------------------------------- 9. 변화기
def t_status_moves():
    print("-- 변화기")
    bt, me, foe = fight(mon("KOMMOO", 50, ["CLANGOROUSSOUL"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "CLANGOROUSSOUL")
    chk("소울비트: 체력 1/3 을 깎고 모든 능력이 오른다",
        me.maxhp - me.hp == me.maxhp // 3 and all(me.stages[s] == 1 for s in ("atk", "def", "spa", "spd", "spe")),
        (me.hp, me.maxhp, me.stages))
    me.hp = me.maxhp // 3
    before = dict(me.stages)
    ev = use(bt, "me", "CLANGOROUSSOUL")
    chk("  체력이 1/3 이하면 실패", me.stages == before and "실패" in texts(ev), texts(ev))

    bt, me, foe = fight(mon("MAREANIE", 50, ["PURIFY"]), mon("SNORLAX", 50))
    me.hp = 10
    ev = use(bt, "me", "PURIFY")
    chk("정화: 상대가 멀쩡하면 실패 (예전에는 그냥 회복기였다)", me.hp == 10 and "실패" in texts(ev), texts(ev))
    foe.status = "burn"
    ev = use(bt, "me", "PURIFY")
    chk("  상대의 상태이상을 고치고 내가 회복한다", foe.status is None and me.hp > 10, (foe.status, me.hp))

    bt, me, foe = fight(mon("VILEPLUME", 50, ["STRENGTHSAP"]), mon("MACHAMP", 50))
    me.hp = 1
    atk = foe.stat("atk")
    use(bt, "me", "STRENGTHSAP")
    chk("힘흡수: 상대의 공격만큼 회복하고 공격을 내린다", me.hp == min(me.maxhp, 1 + atk) and foe.stages["atk"] == -1,
        (me.hp, atk, foe.stages))

    bt, me, foe = fight(mon("ZARUDE", 50, ["JUNGLEHEALING"]), mon("SNORLAX", 50))
    me.hp, me.status = 10, "burn"
    use(bt, "me", "JUNGLEHEALING")
    chk("정글힐: 회복하고 상태이상도 낫는다", me.hp > 10 and me.status is None, (me.hp, me.status))

    bt, me, foe = fight(mon("GREEDENT", 50, ["STUFFCHEEKS"], held="SITRUSBERRY"), mon("SNORLAX", 50))
    me.hp = 10
    ev = use(bt, "me", "STUFFCHEEKS")
    chk("볼가득넣기: 열매를 먹고 방어가 크게 오른다", me.hp > 10 and me.stages["def"] == 2 and me.used,
        (me.hp, me.stages, texts(ev)))
    ev = use(bt, "me", "STUFFCHEEKS")
    chk("  열매가 없으면 실패", me.stages["def"] == 2 and "실패" in texts(ev), texts(ev))

    bt, me, foe = fight(mon("FALINKS", 50, ["NORETREAT"]), mon("SNORLAX", 50))
    use(bt, "me", "NORETREAT")
    chk("배수의진: 모든 능력이 오르고 못 물러난다",
        all(me.stages[s] == 1 for s in ("atk", "def", "spa", "spd", "spe")) and SM.trapped(bt, me), me.stages)
    ev = use(bt, "me", "NORETREAT")
    chk("  두 번은 못 쓴다", me.stages["atk"] == 1 and "실패" in texts(ev), texts(ev))

    bt, me, foe = fight(mon("FLORGES", 50, ["FLOWERSHIELD"]), mon("VENUSAUR", 50))
    use(bt, "me", "FLOWERSHIELD")
    chk("플라워가드: 풀 타입만 방어가 오른다 (쓴 쪽이 풀이 아니면 안 오른다)",
        foe.stages["def"] == 1 and me.stages["def"] == 0, (me.stages, foe.stages))
    bt, me, foe = fight(mon("FLORGES", 50, ["FLOWERSHIELD"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "FLOWERSHIELD")
    chk("  풀 타입이 없으면 실패 (예전에는 상대 방어를 올려 줬다)", foe.stages["def"] == 0 and "실패" in texts(ev),
        (foe.stages, texts(ev)))


# ---------------------------------------------------------------- 10. AI·잡기 모드·레이드
def t_ai():
    print("-- AI 와 잡기 모드")
    bt, me, foe = fight(mon("ELECTRODE", 50, ["EXPLOSION", "TACKLE"]), mon("SNORLAX", 50))
    picks = [bt.choose_for(me, foe, "trainer") for _ in range(40)]
    chk("체력이 넉넉하면 대폭발을 좀처럼 안 쓴다", picks.count("EXPLOSION") <= 8, picks.count("EXPLOSION"))
    bt, me, foe = fight(mon("GENGAR", 50, ["DREAMEATER", "LICK"]), mon("MACHAMP", 50))
    picks = [bt.choose_for(me, foe, "trainer") for _ in range(40)]
    chk("깨어 있는 상대에게 꿈먹기를 안 쓴다", picks.count("DREAMEATER") <= 8, picks.count("DREAMEATER"))
    bt, me, foe = fight(mon("TINKATON", 60, ["GIGATONHAMMER", "TACKLE"]), mon("SNORLAX", 60))
    seq = []
    for _ in range(6):
        k = bt.choose_for(me, foe, "trainer")
        seq.append(k)
        use(bt, "me", k)
        foe.hp = foe.maxhp
    chk("AI 는 거대해머를 연달아 고르지 않는다",
        all(not (a == b == "GIGATONHAMMER") for a, b in zip(seq, seq[1:])), seq)

    bt, me, foe = fight(mon("SCIZOR", 60, ["FALSESWIPE", "BULLETPUNCH"]), mon("PIDGEY", 10), abilities=False)
    foe.status = "sleep"
    m, why = bt.spare_plan(me, foe)
    chk("잡기 모드: 칼등치기를 고른다 (쓰러뜨릴 걱정이 없다)", m == "FALSESWIPE", (m, why))
    bt, me, foe = fight(mon("ELECTRODE", 60, ["EXPLOSION"]), mon("SNORLAX", 60), abilities=False)
    foe.status = "sleep"
    m, why = bt.spare_plan(me, foe)
    chk("잡기 모드: 대폭발로는 잡지 않는다", m is None, (m, why))

    print("-- 레이드 보스는 스스로 쓰러지지 않는다")
    from common import raid_battle as R
    team = [mon("SNORLAX", 60, ["TACKLE"])]
    boss = mon("ELECTRODE", 60, ["EXPLOSION", "STEELBEAM"])
    try:
        rb = R.RaidBattle(DEX, boss, [(1, "가", team)], rng=random.Random(3))
    except TypeError:
        rb = None
    if rb is None:
        chk("레이드 배틀을 만들 수 있다", False, "RaidBattle 서명이 바뀌었다")
        return
    p = rb.players[0]
    bt = p.bt
    hp = rb.boss.hp
    ev = []
    bt._use("foe", rb.boss, p.mon, "EXPLOSION", ev)
    chk("보스의 대폭발: 때리기만 한다", rb.boss.hp == hp and rb.boss.alive(), (hp, rb.boss.hp, texts(ev)))
    ev = []
    bt._use("foe", rb.boss, p.mon, "STEELBEAM", ev)
    chk("보스의 철제광선: 체력을 안 잃는다", rb.boss.hp == hp, (hp, rb.boss.hp))


def t_coverage():
    print("-- 빠진 것이 없다")
    names = (AF.CRASH | AF.SELF_KO | AF.SELF_HALF | AF.LEAVE_ONE | AF.ATK_BY_DEF | AF.ATK_BY_FOE
             | AF.HITS_DEF | AF.HIGHER_STAT | AF.IGNORE_STAGES | AF.IGNORE_ABILITY | AF.SE_BOOST
             | AF.TRAP_HIT | AF.STEAL | AF.EAT_FOE_BERRY | set(AF.LOSE_TYPE) | AF.NEED_FOE_ATTACK
             | AF.NO_REPEAT | set(AF.HAZARD_HIT) | set(AF.DELAYED) | set(AF.CHAIN) | AF.RISING_HITS
             | AF.BAD_POISON | set(AF.IF_ROSE) | set(AF.HANDLERS))
    missing = sorted(k for k in names if DEX.move(k) is None)
    chk("표에 적은 기술이 전부 도감에 있다", not missing, missing)
    rc = [k for k, m in DEX.moves.items() if "recharge" in (m.get("flags") or [])]
    chk("반동 표시가 붙은 기술이 열 개 안팎이다", 8 <= len(rc) <= 14, sorted(rc))


# ---------------------------------------------------------------- Showdown 과 기계로 대조해서 찾은 것
_REAL_ACCURACY = B.accuracy_check


class _Dry(random.Random):
    """부가효과가 안 터지고(100 을 낸다) 저절로 녹지도 않는(0.99) 난수.

    명중도 같은 주사위라 이대로면 다 빗나간다 - t_showdown 이 도는 동안은 명중 판정을
    '늘 맞는다' 로 바꿔 둔다 (명중 자체를 보는 줄만 _REAL_ACCURACY 를 쓴다).
    """

    def uniform(self, a, b):
        return b

    def random(self):
        return 0.99


def _sure(bt):
    """명중은 늘 맞는 것으로 (검사할 것이 명중이 아닐 때)."""
    bt.rng = _Dry(1)
    return bt


def t_showdown():
    B.accuracy_check = lambda *a, **k: True
    try:
        _showdown()
    finally:
        B.accuracy_check = _REAL_ACCURACY


def _showdown():
    print("-- 가루·포자 기술은 풀 타입에게 안 통한다")
    for k in ("SLEEPPOWDER", "SPORE", "STUNSPORE", "COTTONSPORE"):
        bt, me, foe = fight(mon("BUTTERFREE", 50, [k]), mon("TANGELA", 50))
        ev = use(_sure(bt), "me", k)
        chk("%s: 풀 타입은 멀쩡하다" % DEX.move(k)["kr"],
            not foe.status and not any(foe.stages.values()) and "효과가 없는" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("BUTTERFREE", 50, ["SPORE"]), mon("SNORLAX", 50))
    use(_sure(bt), "me", "SPORE")
    chk("풀 타입이 아니면 잠든다", foe.status == "sleep", foe.status)
    bt, me, foe = fight(mon("VENUSAUR", 50, ["SLEEPPOWDER"]), mon("ESPEON", 50, ability="MAGICBOUNCE"))
    ev = use(_sure(bt), "me", "SLEEPPOWDER")
    chk("매직미러로 돌아온 가루도 풀 타입에게는 안 통한다", not me.status and not foe.status, texts(ev))

    print("-- 얼음: 불꽃을 맞으면 녹고, 화염바퀴류는 얼어 있어도 쓴다")
    for k, melts in (("EMBER", True), ("SCALD", True), ("SCORCHINGSANDS", True), ("WATERGUN", False),
                     ("TACKLE", False)):
        bt, me, foe = fight(mon("MEW", 50, [k]), mon("SNORLAX", 80))
        foe.status = "freeze"
        ev = use(_sure(bt), "me", k)
        chk("%s 을(를) 맞으면 %s" % (DEX.move(k)["kr"], "녹는다" if melts else "안 녹는다"),
            hits(ev) and (foe.status is None) == melts, (foe.status, texts(ev)))
    bt, me, foe = fight(mon("MEW", 50, ["EMBER"]), mon("SNORLAX", 80))
    foe.status, foe.cond["sub"] = "freeze", 50
    use(_sure(bt), "me", "EMBER")
    chk("대타가 맞았으면 안 녹는다", foe.status == "freeze", foe.status)
    bt2, me2, foe2 = fight(mon("ARCANINE", 50, ["FLAMEWHEEL", "TACKLE", "BURNUP"]), mon("SNORLAX", 80))
    me2.status = "freeze"
    ev = use(_sure(bt2), "me", "TACKLE")
    chk("얼어 있으면 보통 기술은 못 쓴다", me2.status == "freeze" and not hits(ev), texts(ev))
    ev = use(bt2, "me", "FLAMEWHEEL")
    chk("화염바퀴는 얼어 있어도 쓰고, 쓰면서 녹는다", me2.status is None and hits(ev) and "녹았다" in texts(ev),
        (me2.status, texts(ev)))
    bt2, me2, foe2 = fight(mon("MEW", 50, ["BURNUP"]), mon("SNORLAX", 80))
    me2.status = "freeze"
    ev = use(_sure(bt2), "me", "BURNUP")
    chk("불사르기: 불꽃 타입이 아니면 안 녹는다", me2.status == "freeze", texts(ev))

    print("-- 코골기는 잠든 채로만")
    bt, me, foe = fight(mon("SNORLAX", 50, ["SNORE"]), mon("MACHAMP", 80))
    ev = use(_sure(bt), "me", "SNORE")
    chk("깨어 있으면 실패한다", not hits(ev) and "실패" in texts(ev), texts(ev))
    me.status, me.sleep_turns = "sleep", 3
    ev = use(bt, "me", "SNORE")
    chk("잠들어 있으면 나간다", len(hits(ev)) == 1, texts(ev))

    print("-- 시럽봄: 방어에 막히고, 스피드는 턴 끝에만 떨어진다")
    chk("도감: 방어·방탄 플래그가 있다",
        set(DEX.move("SYRUPBOMB")["flags"]) >= {"protect", "ballistics", "mirror"}, DEX.move("SYRUPBOMB")["flags"])
    bt, me, foe = fight(mon("OGERPON", 50, ["SYRUPBOMB"]), mon("SNORLAX", 100, ["PROTECT"]))
    use(_sure(bt), "foe", "PROTECT")
    ev = use(bt, "me", "SYRUPBOMB")
    chk("방어에 막힌다", not hits(ev) and not foe.cond.get("syrup") and "지켰다" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("OGERPON", 50, ["SYRUPBOMB"]), mon("SNORLAX", 100))
    ev = use(_sure(bt), "me", "SYRUPBOMB")
    chk("맞는 순간에는 스피드가 안 떨어진다", foe.stages["spe"] == 0 and foe.cond.get("syrup"), (foe.stages, texts(ev)))
    eot(bt)
    chk("턴 끝에 한 단계", foe.stages["spe"] == -1, foe.stages["spe"])
    bt, me, foe = fight(mon("OGERPON", 50, ["SYRUPBOMB"]), mon("CHESNAUGHT", 100, ability="BULLETPROOF"))
    ev = use(_sure(bt), "me", "SYRUPBOMB")
    chk("방탄에게는 안 통한다", not hits(ev), texts(ev))
    chk("브레이브차지의 PP 는 15", DEX.move("TAKEHEART")["pp"] == 15, DEX.move("TAKEHEART")["pp"])

    print("-- 부자유친: 본가의 조건 그대로")
    def pb(k, target="SNORLAX", prep=None, twice=False):
        bt, me, foe = fight(mon("KANGASKHAN", 50, [k], ability="PARENTALBOND"), mon(target, 50))
        foe.maxhp = foe.hp = 5000
        _sure(bt)
        if prep:
            prep(bt, me, foe)
        ev = use(bt, "me", k)
        if twice and not hits(ev):
            ev = use(bt, "me", k)
        return hits(ev), me, texts(ev)
    h, me, tx = pb("SEISMICTOSS")
    chk("지구던지기는 두 번 다 레벨만큼", h == [50, 50], (h, tx))
    h, me, tx = pb("NIGHTSHADE", target="MACHAMP")
    chk("나이트헤드도 두 번", h == [50, 50], (h, tx))
    h, me, tx = pb("ROLLOUT")
    chk("구르기는 한 번", len(h) == 1, (h, tx))
    h, me, tx = pb("EXPLOSION")
    chk("대폭발은 한 번", len(h) == 1, (h, tx))
    h, me, tx = pb("SOLARBEAM", twice=True)
    chk("모았다 쓰는 기술은 한 번 (솔라빔)", len(h) == 1, (h, tx))
    h, me, tx = pb("STEELBEAM")
    chk("철제광선은 두 번 치고 반동은 한 번", len(h) == 2 and me.maxhp - me.hp == (me.maxhp + 1) // 2,
        (h, me.maxhp - me.hp, tx))
    h, me, tx = pb("COUNTER")
    chk("카운터는 부자유친과 상관없다", len(h) <= 1, (h, tx))
    chk("목록이 Showdown 의 noparentalbond 와 같다",
        AF.NO_PARENTAL == {"DRAGONDARTS", "DYNAMAXCANNON", "ENDEAVOR", "EXPLOSION", "FINALGAMBIT", "FLING",
                           "ICEBALL", "ROLLOUT", "SELFDESTRUCT"})

    print("-- 작아지기·웅크리기·숨은 상대")
    def dmg(k, prep=None, user="MEW", target="SNORLAX"):
        bt, me, foe = fight(mon(user, 50, [k, "DEFENSECURL"]), mon(target, 50, ["MINIMIZE", "DIG", "DIVE", "FLY"]))
        foe.maxhp = foe.hp = 5000
        _sure(bt)
        if prep:
            prep(bt, me, foe)
        return sum(hits(use(bt, "me", k)))
    for k in ("STOMP", "BODYSLAM", "DRAGONRUSH", "HEAVYSLAM"):
        d0 = dmg(k)
        d1 = dmg(k, lambda bt, me, foe: (use(bt, "foe", "MINIMIZE"), foe.stages.update(eva=0)))
        chk("작아진 상대에게 %s 두 배" % DEX.move(k)["kr"], d0 > 0 and abs(d1 - 2 * d0) <= 2, (d0, d1))
    d0 = dmg("TACKLE")
    d1 = dmg("TACKLE", lambda bt, me, foe: (use(bt, "foe", "MINIMIZE"), foe.stages.update(eva=0)))
    chk("  다른 기술은 그대로", d0 == d1, (d0, d1))
    bt, me, foe = fight(mon("MEW", 50, ["DRAGONRUSH"]), mon("SNORLAX", 50, ["MINIMIZE"]))
    use(bt, "foe", "MINIMIZE")
    foe.stages["eva"] = 6
    got = sum(1 for seed in range(30)
              if _REAL_ACCURACY(DEX, DEX.move("DRAGONRUSH"), me, foe, random.Random(seed)))
    chk("  작아진 상대에게는 반드시 맞는다 (명중 75, 회피 +6 인데도)", got == 30, got)
    d0 = dmg("ROLLOUT")
    d1 = dmg("ROLLOUT", lambda bt, me, foe: use(bt, "me", "DEFENSECURL"))
    chk("웅크리기 뒤의 구르기는 두 배", d0 > 0 and abs(d1 - 2 * d0) <= 2, (d0, d1))
    for k, hide, kr in (("EARTHQUAKE", "DIG", "땅속의 상대에게 지진"), ("SURF", "DIVE", "물속의 상대에게 파도타기"),
                        ("GUST", "FLY", "공중의 상대에게 바람일으키기")):
        d0 = dmg(k)
        d1 = dmg(k, lambda bt, me, foe, hide=hide: use(bt, "foe", hide))
        chk("%s 두 배" % kr, d0 > 0 and abs(d1 - 2 * d0) <= 2, (d0, d1))

    print("-- 미래예지도 '맞는 공격' 이다")
    for label, kw in (("옹골참", {"ability": "STURDY"}), ("기합의띠", {"held": "FOCUSSASH"})):
        bt, me, foe = fight(mon("MEWTWO", 100, ["FUTURESIGHT"]), mon("GEODUDE", 5, **kw))
        use(bt, "me", "FUTURESIGHT")
        for _ in range(3):
            eot(bt)
        chk("%s: 체력이 가득이면 1 남기고 버틴다" % label, foe.hp == 1, (foe.hp, foe.maxhp))

    print("-- 다른 기술을 부르는 기술: 못 부르는 것이 기술마다 다르다")
    bt, me, foe = fight(mon("SNORLAX", 50, ["SLEEPTALK", "PROTECT"]), mon("MACHAMP", 50))
    me.status, me.sleep_turns = "sleep", 3
    ev = use(bt, "me", "SLEEPTALK")
    chk("잠꼬대는 방어를 부를 수 있다", me.cond.get("protect"), texts(ev))
    for k in ("SOLARBEAM", "METEORBEAM", "FLY", "FOCUSPUNCH", "UPROAR"):
        bt, me, foe = fight(mon("SNORLAX", 50, ["SLEEPTALK", k]), mon("MACHAMP", 50))
        me.status, me.sleep_turns = "sleep", 3
        ev = use(bt, "me", "SLEEPTALK")
        chk("  잠꼬대는 %s 을(를) 못 부른다" % DEX.move(k)["kr"], "실패" in texts(ev), texts(ev))
    for k, ok in (("ROAR", False), ("DRAGONTAIL", False), ("PROTECT", False), ("SNORE", True), ("TACKLE", True)):
        bt, me, foe = fight(mon("CLEFABLE", 50, ["COPYCAT"]), mon("SNORLAX", 50))
        bt.field.last_move = k
        ev = use(bt, "me", "COPYCAT")
        chk("  흉내쟁이는 %s 을(를) %s" % (DEX.move(k)["kr"], "따라 한다" if ok else "못 따라 한다"),
            (DEX.move(k)["kr"] in texts(ev).split("흉내쟁이!", 1)[-1]) == ok, texts(ev))
    seen = []
    bt, me, foe = fight(mon("CLEFABLE", 50, ["METRONOME"]), mon("SNORLAX", 50))

    class Pick(random.Random):
        def choice(self, seq):
            seen.append(list(seq))
            return "SPLASH" if "SPLASH" in seq else seq[0]
    bt.rng = Pick(1)
    use(bt, "me", "METRONOME")
    pool = set(seen[0]) if seen else set()
    chk("손가락흔들기는 전용기를 안 부른다 (V제너레이트·근원의파동·거대해머는 부른다)",
        pool and not (pool & {"VCREATE", "ORIGINPULSE", "SPECTRALTHIEF", "PROTECT", "SNORE", "BIDE"})
        and {"GIGATONHAMMER", "TACKLE", "HYPERBEAM"} <= pool, len(pool))
    chk("  부를 수 있는 기술 수가 본가만큼 준다", pool.isdisjoint(SM.NO_METRONOME), len(pool & SM.NO_METRONOME))
    bt, me, foe = fight(mon("CLEFABLE", 50, ["ENCORE"]), mon("SNORLAX", 50, ["METRONOME", "TACKLE"]))
    foe.cond["lastMove"] = "METRONOME"
    ev = use(bt, "me", "ENCORE")
    chk("손가락흔들기에는 앙코르가 안 걸린다", not foe.cond.get("encore"), texts(ev))

    print("-- 자리를 못 뜨는 때: 반동 턴·날뛰는 중·모으는 중")
    f = B.Fighter(DEX, mon("SNORLAX", 50, ["HYPERBEAM"]))
    chk("보통은 뜰 수 있다", SM.must_stay(f) is None)
    f.cond["recharge"] = True
    chk("반동 턴에는 못 뜬다", "반동" in (SM.must_stay(f) or ""), SM.must_stay(f))
    f = B.Fighter(DEX, mon("GENGAR", 50, ["OUTRAGE"]))
    f.cond["rage"] = {"move": "OUTRAGE", "turns": 2}
    chk("날뛰는 중에도 못 뜬다 (고스트 타입이어도)", SM.must_stay(f) and not SM.trapped(fight(mon("GENGAR"), mon("MEW"))[0], f))
    f.pp["OUTRAGE"] = 0
    chk("  그 기술의 PP 가 떨어졌으면 뜰 수 있다", SM.must_stay(f) is None)
    f = B.Fighter(DEX, mon("PIDGEOT", 50, ["FLY"]))
    f.cond["charge2"] = {"move": "FLY"}
    chk("모으는 중에도 못 뜬다", SM.must_stay(f) is not None)
    from common import live_battle as LB
    a = [mon("SNORLAX", 50, ["HYPERBEAM", "TACKLE"]), mon("PIKACHU", 50, ["TACKLE"])]
    b = [mon("BLISSEY", 50, ["SPLASH"]), mon("PIKACHU", 50, ["TACKLE"])]
    lb = LB.LiveBattle(DEX, (1, "a", a), (2, "b", b), rng=_Dry(4))
    lb.start()
    lb.choose("a", "move", "HYPERBEAM")
    lb.choose("b", "move", "SPLASH")
    ev = lb.resolve()
    chk("실시간 배틀: 파괴광선이 맞았다", lb.a.mon.cond.get("recharge"), texts(ev))
    try:
        lb.choose("a", "switch", 1)
        refused = False
    except ValueError as e:
        refused = "반동" in str(e)
    chk("  그 다음 턴에는 교체를 받지 않는다", refused and lb.a.slot == 0)
    lb.choose("a", "move", "TACKLE")
    lb.choose("b", "move", "SPLASH")
    ev = lb.resolve()
    chk("  기술을 골라도 쉰다", "반동으로 움직일 수 없다" in texts(ev), texts(ev))
    lb.choose("a", "switch", 1)
    chk("  쉬고 난 다음에는 교체할 수 있다", lb.a.choice == ("switch", 1), lb.a.choice)

    print("-- 프리폴: 두 턴 기술")
    bt, me, foe = fight(mon("BRAVIARY", 50, ["SKYDROP"]), mon("MACHAMP", 50, ["TACKLE"]))
    _sure(bt)
    bt.begin_turn()
    ev = use(bt, "me", "SKYDROP")
    chk("첫 턴: 데리고 올라간다 (안 때린다)", not hits(ev) and foe.cond.get("skydrop") and me.cond.get("invuln") == "fly",
        texts(ev))
    ev = use(bt, "foe", "TACKLE")
    chk("  붙잡힌 상대는 못 움직인다", not hits(ev) and "붙잡혀" in texts(ev), texts(ev))
    chk("  붙잡힌 상대는 교체도 못 한다", SM.must_stay(foe) is not None)
    bt.begin_turn()
    ev = use(bt, "me", "SKYDROP")
    chk("둘째 턴: 떨어뜨려 때린다", len(hits(ev)) == 1 and not foe.cond.get("skydrop") and not me.cond.get("invuln"),
        texts(ev))
    ev = use(bt, "foe", "TACKLE")
    chk("  놓인 뒤에는 움직인다", len(hits(ev)) == 1, texts(ev))
    bt, me, foe = fight(mon("BRAVIARY", 50, ["SKYDROP"]), mon("PIDGEOT", 50))
    _sure(bt)
    use(bt, "me", "SKYDROP")
    ev = use(bt, "me", "SKYDROP")
    chk("비행 타입은 떨어뜨려도 안 다친다", not hits(ev) and foe.hp == foe.maxhp and not foe.cond.get("skydrop"), texts(ev))
    bt, me, foe = fight(mon("BRAVIARY", 50, ["SKYDROP"]), mon("SNORLAX", 50))
    ev = use(_sure(bt), "me", "SKYDROP")
    chk("무거운 상대(460kg)는 못 든다", not foe.cond.get("skydrop") and not me.cond.get("charge2") and "무거워서" in texts(ev),
        texts(ev))
    bt, me, foe = fight(mon("BRAVIARY", 50, ["SKYDROP"]), mon("MACHAMP", 50))
    _sure(bt)
    bt.begin_turn()
    use(bt, "me", "SKYDROP")
    me.hp = 0                                   # 붙잡은 쪽이 쓰러졌다 (독 같은 것으로)
    bt.begin_turn()
    chk("붙잡은 쪽이 쓰러지면 풀려난다", not foe.cond.get("skydrop"), foe.cond)
    from common import raid_battle as R
    rb = R.RaidBattle(DEX, mon("MACHAMP", 60, ["TACKLE"]),
                      [(1, "P1", [R.leveled(mon("BRAVIARY", 50, ["SKYDROP"]), 50)])], hp_mult=3,
                      rng=random.Random(3))
    rb.start()
    rb.choose(0, "move", "SKYDROP")
    ev = rb.resolve()
    chk("레이드 보스는 못 든다 (들 수 있으면 보스가 한 턴도 못 움직인다)",
        not rb.boss.cond.get("skydrop") and "실패" in texts(ev), texts(ev))

    print("-- 옛노래: 메로엣타가 스텝폼이 된다")
    bt, me, foe = fight(mon("MELOETTA", 50, ["RELICSONG"]), mon("SNORLAX", 80))
    foe.maxhp = foe.hp = 5000
    _sure(bt)
    atk0, spa0 = me.stat("atk"), me.stat("spa")
    ev = use(bt, "me", "RELICSONG")
    chk("쓰면 스텝폼: 노말·격투, 공격이 오르고 특수공격이 내린다",
        me.cond.get("form") == "pirouette" and me.types() == ["NORMAL", "FIGHTING"]
        and me.stat("atk") > atk0 and me.stat("spa") < spa0 and "스텝폼" in texts(ev),
        (me.cond.get("form"), me.types(), texts(ev)))
    eot(bt)
    chk("  턴이 끝나도 그대로다", me.cond.get("form") == "pirouette")
    f2 = B.Fighter(DEX, mon("MELOETTA", 50, ["RELICSONG"]))
    f2.load_volatile(json.loads(json.dumps(me.volatile())))
    chk("  저장했다 되살려도 그대로다", f2.cond.get("form") == "pirouette" and f2.types() == ["NORMAL", "FIGHTING"])
    use(bt, "me", "RELICSONG")
    chk("다시 쓰면 보이스폼으로 돌아온다", not me.cond.get("form") and me.types() == ["NORMAL", "PSYCHIC"]
        and me.stat("atk") == atk0, (me.cond.get("form"), me.types()))
    bt, me, foe = fight(mon("MEW", 50, ["RELICSONG"]), mon("SNORLAX", 80))
    use(_sure(bt), "me", "RELICSONG")
    chk("메로엣타가 아니면 아무 일도 없다", not me.cond.get("form") and not me.cond.get("pirouette"))

    print("-- 제보: 옹골참이 있으면 자폭을 두 번 쓴다")
    # 배포 중이던 1.9.1 은 자폭해도 아예 안 쓰러졌다. 지금은 쓰러지는데, **버티는 효과가
    # 그것까지 살려 주면 안 된다** - 옹골참·기합의띠·기합의머리띠는 '맞은' 데미지만 버틴다.
    class Lucky(random.Random):
        def random(self):
            return 0.0                          # 기합의머리띠가 반드시 터지는 주사위

        def uniform(self, a, b):
            return b
    for k in ("SELFDESTRUCT", "EXPLOSION", "MISTYEXPLOSION", "MEMENTO", "FINALGAMBIT"):
        for label, kw in (("옹골참", {"ability": "STURDY"}), ("기합의띠", {"held": "FOCUSSASH"}),
                          ("기합의머리띠", {"held": "FOCUSBAND"})):
            bt, me, foe = fight(mon("GOLEM", 50, [k, "TACKLE"], **kw), mon("SNORLAX", 50))
            bt.rng = Lucky(1)
            ev = use(bt, "me", k)
            chk("%s + %s: 쓴 쪽은 쓰러진다" % (label, DEX.move(k)["kr"]), me.hp == 0 and not me.alive(),
                (me.hp, texts(ev)))
    bt, me, foe = fight(mon("GOLEM", 50, ["SELFDESTRUCT", "ENDURE"], ability="STURDY"), mon("SNORLAX", 50))
    me.cond["endure"] = True
    use(bt, "me", "SELFDESTRUCT")
    chk("버티기가 걸려 있어도 쓰러진다", me.hp == 0)
    bt, me, foe = fight(mon("GOLEM", 50, ["SLEEPTALK", "SELFDESTRUCT"], ability="STURDY"), mon("SNORLAX", 50))
    me.status, me.sleep_turns = "sleep", 3
    use(bt, "me", "SLEEPTALK")
    chk("잠꼬대가 부른 자폭으로도 쓰러진다", me.hp == 0, me.hp)
    used = 0
    bt, me, foe = fight(mon("SNORLAX", 50, ["SPLASH"]), mon("GEODUDE", 50, ["SELFDESTRUCT"], ability="STURDY"))
    for _ in range(4):
        if bt.over:
            break
        ev = bt.take_turn("SPLASH")
        used += sum(1 for e in ev if e.get("t") == "move" and e.get("who") == "foe")
    chk("실제 턴 진행: 옹골참 꼬마돌은 자폭을 한 번 쓰고 쓰러진다", used == 1 and not foe.alive(), (used, foe.hp))
    bt, me, foe = fight(mon("ELECTRODE", 100, ["EXPLOSION"]), mon("GEODUDE", 5, ability="STURDY"))
    use(bt, "me", "EXPLOSION")
    chk("맞는 쪽의 옹골참은 그대로 버틴다 (1 남는다)", foe.hp == 1 and me.hp == 0, (foe.hp, me.hp))

    print("-- 걸린 뒤에 특성이 바뀌면 낫는다")
    bt, me, foe = fight(mon("ARAQUANID", 50, ["ENTRAINMENT"], ability="WATERBUBBLE"), mon("SNORLAX", 50))
    foe.status = "burn"
    ev = use(bt, "me", "ENTRAINMENT")
    chk("화상인 채 수포를 받으면 화상이 낫는다", foe.ability == "WATERBUBBLE" and foe.status is None
        and "나았다" in texts(ev), (foe.ability, foe.status, texts(ev)))
    hp = foe.hp
    eot(bt)
    chk("  그 턴 끝에 화상 데미지도 없다", foe.hp == hp, (hp, foe.hp))
    bt, me, foe = fight(mon("PERSIAN", 50, ["SKILLSWAP"], ability="LIMBER"), mon("SNORLAX", 50, ability="THICKFAT"))
    foe.status = "paralysis"
    use(bt, "me", "SKILLSWAP")
    chk("마비인 채 스킬스왑으로 유연을 받으면 풀린다", foe.ability == "LIMBER" and foe.status is None,
        (foe.ability, foe.status))
    bt, me, foe = fight(mon("HAXORUS", 50, ["THUNDERWAVE"], ability="MOLDBREAKER"), mon("PERSIAN", 50, ability="LIMBER"))
    ev = use(bt, "me", "THUNDERWAVE")
    chk("틀깨기에게 맞아 마비돼도 유연이면 바로 풀린다", foe.status is None and "나았다" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("MEW", 50, ["WILLOWISP"]), mon("SNORLAX", 50, ability="THICKFAT"))
    use(bt, "me", "WILLOWISP")
    chk("상관없는 특성이면 그대로 걸려 있다", foe.status == "burn", foe.status)
    bt, me, foe = fight(mon("MEW", 50, ["GASTROACID"]), mon("ARAQUANID", 50, ability="WATERBUBBLE"))
    foe.status = "burn"
    foe.cond["gastro"] = True
    eot(bt)
    chk("특성이 지워진 동안에는 안 낫는다", foe.status == "burn", foe.status)

    print("-- 손으로 적어 둔 목록")
    chk("에어로블라스트는 바람 기술이다", "AEROBLAST" in A.WIND)
    chk("얼음을 녹이는 기술(불꽃 아님)", AF.THAW_TARGET == {"SCALD", "STEAMERUPTION", "SCORCHINGSANDS", "HYDROSTEAM",
                                                  "MATCHAGOTCHA"})
    for name in ("NO_SLEEPTALK", "NO_COPYCAT", "NO_MIMIC", "NO_INSTRUCT", "NO_ENCORE", "NO_METRONOME"):
        ban = getattr(SM, name)
        gone = sorted(k for k in ban if k not in DEX.moves and k != "STRUGGLE")
        chk("%s 에 도감에 없는 이름이 없다 (%d개)" % (name, len(ban)), not gone, gone)


# ---------------------------------------------------------------- 위력·데미지가 계산으로 정해지는 기술
def _eng_power(k, user, target):
    """엔진이 데미지 식에 넣는 위력 (battle._damage 와 같은 길)."""
    m2 = SM.resolve(MC.resolve(DEX.move(k), user, target), user, target)
    return AF.power(MC.key(m2), m2.get("power") or 0, m2, user, target)


def t_formulas():
    """몸무게·체력·스피드·친밀도·랭크로 위력이 정해지는 기술과, 다른 능력치로 세는 기술.

    기대값은 **여기서 따로 적은 본가 공식**으로 낸다 (엔진의 식을 베끼지 않는다).
    "방어로 때리는 기술이 그냥 공격으로 세어지는 것 아니냐" 는 물음에 답하려고 넣었다.
    """
    B.accuracy_check = lambda *a, **k: True
    try:
        _formulas()
    finally:
        B.accuracy_check = _REAL_ACCURACY


def _formulas():
    import math
    kg = dict((sp["internal"], sp.get("kg")) for sp in DEX.raw["species"])

    print("-- 상대 몸무게로 정해진다 (안다리걸기·풀묶기)")
    def by_weight(w):
        for limit, p in ((10, 20), (25, 40), (50, 60), (100, 80), (200, 100)):
            if w < limit:
                return p
        return 120
    # 경계(10·25·50·100·200kg)에 딱 걸친 종과 바로 아래 종을 도감에서 찾아 쓴다
    picks = {"PIKACHU", "SNORLAX", "GROUDON", "GASTLY", "MACHAMP"}
    for sp in DEX.raw["species"]:
        w = sp.get("kg") or 0
        for b in (10, 25, 50, 100, 200):
            if w == b or b - 0.5 <= w < b:
                picks.add(sp["internal"])
    picks = sorted(picks)[:60]
    for k in ("LOWKICK", "GRASSKNOT"):
        wrong = []
        for t in picks:
            bt, me, foe = fight(mon("MEW", 50, [k]), mon(t, 50))
            if _eng_power(k, me, foe) != by_weight(kg[t]):
                wrong.append((t, kg[t], _eng_power(k, me, foe), by_weight(kg[t])))
        chk("%s: 종 %d개(경계값 포함)의 위력이 본가 표와 같다" % (DEX.move(k)["kr"], len(picks)), not wrong, wrong[:3])
    bt, me, foe = fight(mon("MEW", 50, ["LOWKICK"]), mon("MACHAMP", 50, ability="HEAVYMETAL"))
    chk("  헤비메탈이면 두 배로 무겁다 (130 → 260kg: 위력 120)", _eng_power("LOWKICK", me, foe) == 120)
    bt, me, foe = fight(mon("MEW", 50, ["LOWKICK"]), mon("MACHAMP", 50, ability="LIGHTMETAL"))
    chk("  라이트메탈이면 절반 (65kg: 위력 80)", _eng_power("LOWKICK", me, foe) == 80)

    print("-- 몸무게의 비로 정해진다 (헤비봄버·히트스탬프)")
    def by_ratio(u, t):
        r = math.floor(u / t)
        return 120 if r >= 5 else 100 if r == 4 else 80 if r == 3 else 60 if r == 2 else 40
    pairs = [("SNORLAX", "PIKACHU"), ("SNORLAX", "MACHAMP"), ("SNORLAX", "VENUSAUR"), ("SNORLAX", "ONIX"),
             ("SNORLAX", "SNORLAX"), ("PIKACHU", "SNORLAX"), ("GROUDON", "SNORLAX"), ("GROUDON", "ONIX"),
             ("MACHAMP", "CHARMELEON"), ("ONIX", "IVYSAUR"), ("AGGRON", "MACHAMP")]
    for k in ("HEAVYSLAM", "HEATCRASH"):
        wrong = []
        for u, t in pairs:
            bt, me, foe = fight(mon(u, 50, [k]), mon(t, 50))
            if _eng_power(k, me, foe) != by_ratio(kg[u], kg[t]):
                wrong.append((u, t, _eng_power(k, me, foe), by_ratio(kg[u], kg[t])))
        chk("%s: %d쌍의 위력이 본가 표와 같다" % (DEX.move(k)["kr"], len(pairs)), not wrong, wrong[:3])

    print("-- 체력으로 정해진다")
    def flail(hp, mx):
        x = hp * 48 // mx
        return 200 if x <= 1 else 150 if x <= 4 else 100 if x <= 9 else 80 if x <= 16 else 40 if x <= 32 else 20
    for k in ("FLAIL", "REVERSAL"):
        bt, me, foe = fight(mon("SNORLAX", 50, [k]), mon("MACHAMP", 50))
        wrong = []
        for hp in range(1, me.maxhp + 1):
            me.hp = hp
            if _eng_power(k, me, foe) != flail(hp, me.maxhp):
                wrong.append((hp, _eng_power(k, me, foe), flail(hp, me.maxhp)))
        chk("%s: 내 체력 1~%d 전부" % (DEX.move(k)["kr"], me.maxhp), not wrong, wrong[:3])
    for k in ("ERUPTION", "WATERSPOUT", "DRAGONENERGY"):
        bt, me, foe = fight(mon("SNORLAX", 50, [k]), mon("MACHAMP", 50))
        wrong = []
        for hp in range(1, me.maxhp + 1):
            me.hp = hp
            if _eng_power(k, me, foe) != max(1, hp * 150 // me.maxhp):
                wrong.append(hp)
        chk("%s: 내 체력 1~%d 전부 (150 x 체력 비율)" % (DEX.move(k)["kr"], me.maxhp), not wrong, wrong[:3])
    for k, base in (("CRUSHGRIP", 120), ("HARDPRESS", 100)):
        bt, me, foe = fight(mon("MEW", 50, [k]), mon("SNORLAX", 50))
        wrong = []
        for hp in range(1, foe.maxhp + 1):
            foe.hp = hp
            # 본가의 식 그대로 (1/4096 단위로 내림한 뒤 반 내림)
            want = math.floor(math.floor((base * (100 * math.floor(hp * 4096 / foe.maxhp)) + 2048 - 1) / 4096) / 100) or 1
            if _eng_power(k, me, foe) != want:
                wrong.append((hp, _eng_power(k, me, foe), want))
        chk("%s: 상대 체력 1~%d 전부 (반올림까지 본가와 같다)" % (DEX.move(k)["kr"], foe.maxhp), not wrong, wrong[:3])

    print("-- 스피드로 정해진다 (일렉트릭볼·자이로볼)")
    wrong = []
    for u, t in (("ELECTRODE", "SNORLAX"), ("ELECTRODE", "SHUCKLE"), ("SHUCKLE", "ELECTRODE"), ("PIKACHU", "MACHAMP"),
                 ("FERROTHORN", "ELECTRODE"), ("MACHAMP", "MACHAMP")):
        for us, ts, par in ((0, 0, False), (2, 0, False), (0, 2, False), (-2, 0, False), (0, -2, False), (0, 0, True),
                            (6, -6, False)):
            bt, me, foe = fight(mon(u, 50, ["ELECTROBALL", "GYROBALL"]), mon(t, 50))
            me.stages["spe"], foe.stages["spe"] = us, ts
            if par:
                me.status = "paralysis"
            a, b = me.stat("spe"), foe.stat("spe")
            r = a // b
            eb = 150 if r >= 4 else 120 if r == 3 else 80 if r == 2 else 60 if r == 1 else 40
            gy = min(150, 25 * b // a + 1)
            got = (_eng_power("ELECTROBALL", me, foe), _eng_power("GYROBALL", me, foe))
            if got != (eb, gy):
                wrong.append((u, t, a, b, got, (eb, gy)))
    chk("42가지 스피드 조합 (랭크·마비까지 본 스피드)", not wrong, wrong[:3])

    print("-- 친밀도·랭크·쓰러진 동료·맞은 횟수")
    wrong = []
    for h in (0, 1, 2, 70, 160, 254, 255):
        m = mon("SNORLAX", 50, ["RETURN", "FRUSTRATION"])
        m["happiness"] = h
        bt, me, foe = fight(m, mon("MACHAMP", 50))
        got = (_eng_power("RETURN", me, foe), _eng_power("FRUSTRATION", me, foe))
        if got != (max(1, h * 2 // 5), max(1, (255 - h) * 2 // 5)):
            wrong.append((h, got))
    chk("은혜갚기·화풀이: 친밀도 x 2/5 (최대 102, 최소 1)", not wrong, wrong)
    wrong = []
    for st in ({}, {"atk": 2}, {"atk": 6, "spe": 6, "eva": 1}, {"atk": -3, "def": 2}, {"acc": 3, "spa": 1}):
        for k in ("STOREDPOWER", "POWERTRIP"):
            bt, me, foe = fight(mon("MEW", 50, [k]), mon("MACHAMP", 50))
            me.stages.update(st)
            if _eng_power(k, me, foe) != 20 + 20 * sum(v for v in st.values() if v > 0):
                wrong.append((k, st, _eng_power(k, me, foe)))
    chk("어시스트파워·기어오르기: 20 + 오른 랭크 하나에 20 (내린 것은 안 센다)", not wrong, wrong)
    bt, me, foe = fight(mon("MEW", 50, ["LASTRESPECTS", "RAGEFIST"]), mon("SNORLAX", 50))
    got = []
    for n in range(4):
        me.ab["down"] = n
        got.append(_eng_power("LASTRESPECTS", me, foe))
    chk("성묘: 50 + 쓰러진 동료 하나에 50", got == [50, 100, 150, 200], got)

    print("-- 다른 능력치로 센다 (데미지를 본가 식으로 직접 내서 견준다)")
    # 잠만보(노말) → 윈디(불꽃): 격투·악·에스퍼가 모두 자속이 아니고 상성이 보통이다.
    def exact(label, k, pick, prep=None):
        bt, me, foe = fight(mon("SNORLAX", 50, [k]), mon("ARCANINE", 50))
        foe.maxhp = foe.hp = 100000
        _sure(bt)
        if prep:
            prep(me, foe)
        pw, a, d = pick(me, foe)
        want = (22 * pw * a // d) // 50 + 2
        got = sum(hits(use(bt, "me", k)))
        chk(label, got == want, (got, want, pw, a, d))
    exact("(견줌) 깨물어부수기: 내 공격 / 상대 방어", "CRUNCH", lambda me, foe: (80, me.stat("atk"), foe.stat("def")))
    exact("(견줌) 사이코키네시스: 내 특수공격 / 상대 특수방어", "PSYCHIC", lambda me, foe: (90, me.stat("spa"), foe.stat("spd")))
    for label, prep in (("그대로", None), ("내 방어 +2", lambda me, foe: me.stages.update({"def": 2})),
                        ("내 방어 -3", lambda me, foe: me.stages.update({"def": -3})),
                        ("내 공격 +6 은 상관없다", lambda me, foe: me.stages.update(atk=6))):
        exact("바디프레스 [%s]: 내 '방어' 로 때린다" % label, "BODYPRESS",
              lambda me, foe: (80, me.stat("def"), foe.stat("def")), prep)
    for label, prep in (("그대로", None), ("상대 공격 +2", lambda me, foe: foe.stages.update(atk=2)),
                        ("상대 공격 -2", lambda me, foe: foe.stages.update(atk=-2)),
                        ("내 공격 +6 은 상관없다", lambda me, foe: me.stages.update(atk=6))):
        exact("속임수 [%s]: '상대의 공격' 으로 때린다" % label, "FOULPLAY",
              lambda me, foe: (95, foe.stat("atk"), foe.stat("def")), prep)
    for k, bp in (("PSYSHOCK", 80), ("PSYSTRIKE", 100), ("SECRETSWORD", 85)):
        for label, prep in (("그대로", None), ("상대 방어 +2", lambda me, foe: foe.stages.update({"def": 2})),
                            ("상대 특수방어 +6 은 상관없다", lambda me, foe: foe.stages.update(spd=6)),
                            ("내 특수공격 +2", lambda me, foe: me.stages.update(spa=2))):
            exact("%s [%s]: 특수공격으로 때리고 '방어' 로 받는다" % (DEX.move(k)["kr"], label), k,
                  lambda me, foe, bp=bp: (bp, me.stat("spa"), foe.stat("def")), prep)
    exact("포톤가이저: 공격이 더 높으면 물리", "PHOTONGEYSER",
          lambda me, foe: (100, me.stat("atk"), foe.stat("def")), lambda me, foe: me.stages.update(atk=2))
    exact("포톤가이저: 특수공격이 더 높으면 특수", "PHOTONGEYSER",
          lambda me, foe: (100, me.stat("spa"), foe.stat("spd")), lambda me, foe: me.stages.update(spa=2))

    print("-- 고정 데미지")
    for k, want in (("SEISMICTOSS", 37), ("NIGHTSHADE", 37), ("DRAGONRAGE", 40), ("SONICBOOM", 20)):
        bt, me, foe = fight(mon("MEW", 37, [k]), mon("MACHAMP", 80))
        chk("%s: 레벨 37 이 쓰면 %d" % (DEX.move(k)["kr"], want), hits(use(_sure(bt), "me", k)) == [want])
    for hp, want in ((301, 150), (2, 1), (1, 1)):
        bt, me, foe = fight(mon("MEW", 50, ["SUPERFANG"]), mon("MACHAMP", 80))
        foe.maxhp, foe.hp = 400, hp
        chk("분노의앞니: 남은 체력 %d → %d" % (hp, want), hits(use(_sure(bt), "me", "SUPERFANG")) == [want])
    got = set()
    for seed in range(600):
        bt, me, foe = fight(mon("MEW", 50, ["PSYWAVE"]), mon("SNORLAX", 80), seed=seed)
        got.update(hits(use(bt, "me", "PSYWAVE")))
    chk("사이코웨이브: 레벨의 0.5~1.5배, **1.5배(75)도 나온다**", min(got) == 25 and max(got) == 75, (min(got), max(got)))
    for k, atk, mult in (("COUNTER", "TACKLE", 2.0), ("MIRRORCOAT", "WATERGUN", 2.0), ("METALBURST", "TACKLE", 1.5),
                         ("METALBURST", "WATERGUN", 1.5), ("COMEUPPANCE", "WATERGUN", 1.5)):
        bt, me, foe = fight(mon("SNORLAX", 50, [k]), mon("MACHAMP", 50, [atk]))
        foe.maxhp = foe.hp = 100000
        _sure(bt)
        bt.begin_turn()
        took = sum(hits(use(bt, "foe", atk)))
        chk("%s ← %s: 맞은 것의 %.1f배" % (DEX.move(k)["kr"], DEX.move(atk)["kr"], mult),
            took > 0 and hits(use(bt, "me", k)) == [int(took * mult)], took)

    print("-- 구르기: 이어 쓸수록 세지고, 맞히면 다섯 번째까지 묶인다")
    bt, me, foe = fight(mon("GOLEM", 50, ["ROLLOUT", "TACKLE"]), mon("SNORLAX", 50))
    foe.maxhp = foe.hp = 100000
    _sure(bt)
    pp0 = me.pp["ROLLOUT"]
    seen, locked = [], []
    for i in range(6):
        seen.append(_eng_power("ROLLOUT", me, foe))
        bt.begin_turn()
        use(bt, "me", "TACKLE" if i in (1, 2, 3, 4) else "ROLLOUT")     # 딴 것을 골라도 구르기가 나간다
        locked.append(SM.locked_move(me, bt))
    chk("위력 30 → 60 → 120 → 240 → 480, 그리고 다시 30", seen == [30, 60, 120, 240, 480, 30], seen)
    chk("넷째까지는 묶여 있고 다섯째를 치면 풀린다", locked[:5] == ["ROLLOUT"] * 4 + [None], locked)
    chk("PP 는 처음 쓸 때만 든다 (다섯 번에 1, 새로 시작한 여섯째에 1)", pp0 - me.pp["ROLLOUT"] == 2, pp0 - me.pp["ROLLOUT"])
    bt, me, foe = fight(mon("GOLEM", 50, ["ROLLOUT", "TACKLE"]), mon("SNORLAX", 50))
    foe.maxhp = foe.hp = 100000
    _sure(bt)
    use(bt, "me", "ROLLOUT")
    chk("묶인 동안: 다른 기술을 못 고르고 교체도 못 한다",
        "멈출 수 없다" in (SM.restricted(bt, me, "TACKLE") or "") and SM.must_stay(me) is not None,
        (SM.restricted(bt, me, "TACKLE"), SM.must_stay(me)))
    B.accuracy_check = lambda *a, **k: False
    use(bt, "me", "ROLLOUT")
    B.accuracy_check = lambda *a, **k: True
    chk("빗나가면 거기서 끝난다 (묶임도 위력도)", SM.locked_move(me, bt) is None and _eng_power("ROLLOUT", me, foe) == 30,
        (SM.locked_move(me, bt), _eng_power("ROLLOUT", me, foe)))
    use(bt, "me", "ROLLOUT")
    me.flinched = True
    ev = use(bt, "me", "ROLLOUT")
    chk("풀이 죽어 못 움직여도 끝난다", SM.locked_move(me, bt) is None and not hits(ev), texts(ev))
    f2 = B.Fighter(DEX, mon("GOLEM", 50, ["ROLLOUT", "TACKLE"]))
    f2.cond["roll"] = {"move": "ROLLOUT"}
    f3 = B.Fighter(DEX, mon("GOLEM", 50, ["ROLLOUT", "TACKLE"]))
    f3.load_volatile(json.loads(json.dumps(f2.volatile())))
    chk("저장했다 되살려도 묶여 있다", (f3.cond.get("roll") or {}).get("move") == "ROLLOUT")


def main():
    t_reports()
    t_after_use()
    t_conditions()
    t_stats()
    t_power()
    t_after_hit()
    t_toxic()
    t_future()
    t_status_moves()
    t_ai()
    t_showdown()
    t_formulas()
    t_coverage()
    print("")
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
