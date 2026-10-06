# -*- coding: utf-8 -*-
"""남아 있던 특성 검사 (1.9.2) — 도감에는 있는데 아무 일도 안 하던 것들. 서버 없이 돈다.

    python common/test_abilities2.py

특성이 있는 포켓몬 1,025종 + 메가 폼이 가진 특성 293개 중 58개가 엔진에 없었다.
그중 같은 편이 있어야 뜻이 있는 것(텔레파시·치유의마음 ...)과 배틀 밖의 것
(픽업·꿀모으기 ...)을 빼고, **1:1 에서 뜻이 있는 것은 전부** 채웠다. 여기서 하나씩 못 박는다.
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


with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as _f:
    DEX = P.Pokedex(json.load(_f))


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


def fight(a, b, seed=1, enter=True):
    """특성이 켜진 1:1. enter 면 둘 다 '나올 때' 특성을 돌린다 (빠른 쪽부터)."""
    me, foe = B.Fighter(DEX, a), B.Fighter(DEX, b)
    me.ability_on = foe.ability_on = True
    bt = B.Battle(DEX, me, foe, random.Random(seed), ai="trainer")
    bt.kind = "gym"
    ev = []
    if enter:
        for who, f in sorted((("me", me), ("foe", foe)), key=lambda p: -p[1].stat("spe")):
            A.on_switch_in(bt, f, who, ev)
            SM.on_enter_abilities(bt, f, who, ev)
    bt.entry = ev
    return bt, me, foe


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


def est(user, target, key):
    d, _c, _e = B.damage(DEX, DEX.move(key), user, target, B.EST_RNG, crit=False)
    return d


def t_field():
    print("-- 판에 걸리는 특성")
    bt, me, foe = fight(mon("WEEZING", 50, ability="NEUTRALIZINGGAS"),
                        mon("GYARADOS", 50, ability="INTIMIDATE"))
    chk("화학변화가스: 나올 때 알린다", "화학변화가스" in texts(bt.entry), texts(bt.entry))
    chk("  상대의 위협이 안 터진다", me.stages["atk"] == 0 and not A.on(foe), (me.stages, texts(bt.entry)))
    me.hp = 0
    chk("  뿜던 포켓몬이 쓰러지면 특성이 돌아온다", A.on(foe))
    bt, me, foe = fight(mon("WEEZING", 50, ability="NEUTRALIZINGGAS"),
                        mon("MIMIKYU", 50, ability="DISGUISE"))
    chk("  탈처럼 폼이 걸린 특성은 그대로다", A.on(foe))

    bt, me, foe = fight(mon("XERNEAS", 50, ["MOONBLAST"], ability="FAIRYAURA"),
                        mon("SNORLAX", 50, ["PLAYROUGH", "TACKLE"]))
    plain = fight(mon("XERNEAS", 50, ["MOONBLAST"], ability="PRESSURE"), mon("SNORLAX", 50))
    chk("페어리오라: 내 페어리 기술이 4/3 배",
        abs(est(me, foe, "MOONBLAST") / float(est(plain[1], plain[2], "MOONBLAST")) - 4 / 3.0) < 0.03,
        (est(me, foe, "MOONBLAST"), est(plain[1], plain[2], "MOONBLAST")))
    chk("  상대의 페어리 기술도 세진다 (판 전체)",
        est(foe, me, "PLAYROUGH") > est(plain[2], plain[1], "PLAYROUGH") * 1.25)
    chk("  다른 타입은 그대로", est(foe, me, "TACKLE") == est(plain[2], plain[1], "TACKLE"))
    bt, me, foe = fight(mon("XERNEAS", 50, ["MOONBLAST"], ability="FAIRYAURA"),
                        mon("ZYGARDE", 50, ability="AURABREAK"))
    foe.types_override = ["NORMAL"]
    p2 = fight(mon("XERNEAS", 50, ["MOONBLAST"], ability="PRESSURE"), mon("ZYGARDE", 50, ability="PRESSURE"))
    p2[2].types_override = ["NORMAL"]
    chk("오라브레이크: 오라가 거꾸로 3/4 배가 된다",
        abs(est(me, foe, "MOONBLAST") / float(est(p2[1], p2[2], "MOONBLAST")) - 0.75) < 0.03,
        (est(me, foe, "MOONBLAST"), est(p2[1], p2[2], "MOONBLAST")))
    chk("다크오라도 표에 있다", A.AURA.get("DARKAURA") == "DARK")

    bt, me, foe = fight(mon("CHIENPAO", 50, ["ICICLECRASH", "ICEBEAM"], ability="SWORDOFRUIN"),
                        mon("SNORLAX", 50, ["TACKLE"]))
    p2 = fight(mon("CHIENPAO", 50, ability="PRESSURE"), mon("SNORLAX", 50))
    chk("재앙의검: 상대의 방어가 3/4 (물리가 더 아프다)",
        est(me, foe, "ICICLECRASH") > est(p2[1], p2[2], "ICICLECRASH") * 1.25,
        (est(me, foe, "ICICLECRASH"), est(p2[1], p2[2], "ICICLECRASH")))
    chk("  특수는 그대로", est(me, foe, "ICEBEAM") == est(p2[1], p2[2], "ICEBEAM"))
    bt, me, foe = fight(mon("WOCHIEN", 50, ability="TABLETSOFRUIN"), mon("MACHAMP", 50, ["CROSSCHOP", "FLAMETHROWER"]))
    p2 = fight(mon("WOCHIEN", 50, ability="PRESSURE"), mon("MACHAMP", 50))
    chk("재앙의목간: 상대의 공격이 3/4 (물리를 덜 맞는다)",
        est(foe, me, "CROSSCHOP") < est(p2[2], p2[1], "CROSSCHOP") * 0.8,
        (est(foe, me, "CROSSCHOP"), est(p2[2], p2[1], "CROSSCHOP")))
    chk("  특수는 그대로", est(foe, me, "FLAMETHROWER") == est(p2[2], p2[1], "FLAMETHROWER"))
    chk("재앙의구슬·재앙의그릇도 표에 있다", A.RUIN["BEADSOFRUIN"] == "spd" and A.RUIN["VESSELOFRUIN"] == "spa")

    bt, me, foe = fight(mon("ARTICUNO", 50, ["ICEBEAM"]), mon("RAYQUAZA", 50, ability="DELTASTREAM"))
    _d, _c, e = B.damage(DEX, DEX.move("ICEBEAM"), me, foe, B.EST_RNG, crit=False)
    chk("델타스트림: 얼음이 드래곤/비행에게 4배가 아니라 2배", e == 2.0, e)
    chk("  나올 때 알린다", "난기류" in texts(bt.entry), texts(bt.entry))


def t_attacker():
    print("-- 때리는 쪽의 특성")
    bt, me, foe = fight(mon("URSHIFU", 50, ["WICKEDBLOW", "DARKPULSE"], ability="UNSEENFIST"), mon("SNORLAX", 50))
    foe.cond["protect"] = "PROTECT"
    ev = use(bt, "me", "WICKEDBLOW")
    chk("보이지않는주먹: 닿는 기술은 방어를 뚫는다", hits(ev) and hits(ev)[0] > 0, texts(ev))
    foe.cond["protect"] = "PROTECT"
    ev = use(bt, "me", "DARKPULSE")
    chk("  안 닿는 기술은 막힌다", not hits(ev) and "지켰다" in texts(ev), texts(ev))

    bt, me, foe = fight(mon("EXCADRILL", 50, ["IRONHEAD"], ability="PIERCINGDRILL"), mon("SNORLAX", 50), seed=4)
    full = est(me, foe, "IRONHEAD")
    foe.cond["protect"] = "PROTECT"
    ev = use(bt, "me", "IRONHEAD")
    chk("관통드릴: 방어를 뚫되 데미지는 1/4", hits(ev) and hits(ev)[0] <= full * 0.45, (hits(ev), full))
    chk("  뚫은 표시는 그 한 번뿐이다", not me.cond.get("pierce") and est(me, foe, "IRONHEAD") == full)

    bt, me, foe = fight(mon("KANGASKHAN", 50, ["TACKLE", "DOUBLEKICK", "SEISMICTOSS"], ability="PARENTALBOND"),
                        mon("SNORLAX", 100))
    ev = use(bt, "me", "TACKLE")
    h = hits(ev)
    chk("부자유친: 한 번 치는 기술을 두 번", len(h) == 2 and "2번 맞았다" in texts(ev), (h, texts(ev)))
    chk("  둘째는 1/4 쯤", len(h) == 2 and h[1] <= h[0] * 0.4, h)
    ev = use(bt, "me", "DOUBLEKICK")
    chk("  원래 여러 번 치는 기술은 그대로", len(hits(ev)) == 2, hits(ev))
    ev = use(bt, "me", "SEISMICTOSS")
    # 본가: 지구던지기도 두 번 다 들어간다 (메가캥카의 그 조합). 전에는 한 번으로 잘못 알았다.
    chk("  고정 데미지 기술도 두 번, 둘 다 레벨만큼", hits(ev) == [50, 50], hits(ev))

    bt, me, foe = fight(mon("DELPHOX", 50, ["PSYCHIC"], ability="MAGICIAN"), mon("SNORLAX", 100, held="LEFTOVERS"))
    ev = use(bt, "me", "PSYCHIC")
    chk("매지션: 기술을 맞은 상대의 도구를 빼앗는다", me.held == "LEFTOVERS" and foe.held is None, texts(ev))

    bt, me, foe = fight(mon("PYROAR", 50, ["FLAMETHROWER"], ability="FIREMANE"), mon("SNORLAX", 50))
    p2 = fight(mon("PYROAR", 50, ability="RIVALRY", gender="M"), mon("SNORLAX", 50))
    p2[2].mon["gender"] = None
    chk("Firemane: 불꽃 기술 1.5배", abs(est(me, foe, "FLAMETHROWER") / float(est(p2[1], p2[2], "FLAMETHROWER")) - 1.5) < 0.05)
    bt, me, foe = fight(mon("FERALIGATR", 50, ["RETURN"], ability="DRAGONIZE"), mon("SNORLAX", 50))
    chk("드래곤스킨: 노말 기술이 드래곤이 된다", A.move_type(me, DEX.move("RETURN")) == "DRAGON")
    chk("  위력이 1.2배", A.type_power_mult(me, DEX.move("RETURN")) == 1.2)

    bt, me, foe = fight(mon("MEGANIUM", 50, ["SOLARBEAM", "FLAMETHROWER", "SYNTHESIS"], ability="MEGASOL"),
                        mon("SNORLAX", 100))
    ev = use(bt, "me", "SOLARBEAM")
    chk("메가솔라: 날씨가 안 맑아도 솔라빔이 바로 나간다", hits(ev), texts(ev))
    p2 = fight(mon("MEGANIUM", 50, ability="OVERGROW"), mon("SNORLAX", 100))
    chk("  불꽃 기술이 1.5배", abs(est(me, foe, "FLAMETHROWER") / float(est(p2[1], p2[2], "FLAMETHROWER")) - 1.5) < 0.05)
    chk("  상대는 맑은 날씨가 아니다", SM.weather(foe) is None and SM.weather(me) == "sun")

    print("-- 특성을 무시하는 기술")
    bt, me, foe = fight(mon("LUNALA", 50, ["MOONGEISTBEAM", "SHADOWBALL"]), mon("DRAGONITE", 50, ability="MULTISCALE"))
    foe.types_override = ["PSYCHIC"]
    ev = use(bt, "me", "SHADOWBALL")
    half = hits(ev)[0]
    foe.hp = foe.maxhp
    ev = use(bt, "me", "MOONGEISTBEAM")
    chk("섀도레이: 멀티스케일을 무시한다", hits(ev)[0] > half * 1.8, (hits(ev), half))
    chk("  쓰고 나면 표시가 지워진다", not me.cond.get("breaker"))
    bt, me, foe = fight(mon("SOLGALEO", 50, ["SUNSTEELSTRIKE"]), mon("MIMIKYU", 50, ability="DISGUISE"))
    ev = use(bt, "me", "SUNSTEELSTRIKE")
    chk("메테오드라이브: 탈을 무시하고 그대로 들어간다", hits(ev) and hits(ev)[0] > 0 and not foe.ab.get("busted"),
        (texts(ev), foe.ab))


def t_defender():
    print("-- 맞는 쪽의 특성")
    bt, me, foe = fight(mon("MACHAMP", 50, ["CROSSCHOP"]), mon("SCOVILLAIN", 100, ability="SPICYSPRAY"))
    use(bt, "me", "CROSSCHOP")
    chk("하바네로분출: 기술로 때린 쪽이 데인다", me.status == "burn", me.status)

    bt, me, foe = fight(mon("MACHAMP", 50, ["CROSSCHOP"], ability="NOGUARD"),
                        mon("RUNERIGUS", 100, ability="WANDERINGSPIRIT"))
    foe.types_override = ["GROUND"]
    use(bt, "me", "CROSSCHOP")
    chk("떠도는영혼: 닿으면 특성이 맞바뀐다", me.ability == "WANDERINGSPIRIT" and foe.ability == "NOGUARD",
        (me.ability, foe.ability))

    bt, me, foe = fight(mon("MACHAMP", 50, ["CROSSCHOP"], held="LEFTOVERS", ability="NOGUARD"),
                        mon("WEAVILE", 100, ability="PICKPOCKET"))
    ev = use(bt, "me", "CROSSCHOP")
    if foe.alive():
        chk("나쁜손버릇: 닿은 상대의 도구를 훔친다", foe.held == "LEFTOVERS" and me.held is None, texts(ev))
    else:
        chk("나쁜손버릇: (상대가 쓰러져 확인 못 함)", False, texts(ev))

    bt, me, foe = fight(mon("MACHAMP", 50, ["CROSSCHOP", "FLAMETHROWER"], ability="NOGUARD"),
                        mon("EISCUE", 100, ability="ICEFACE"))
    spe0, def0 = foe.stat("spe"), foe.stat("def")
    ev = use(bt, "me", "CROSSCHOP")
    chk("아이스페이스: 물리 공격 한 번을 얼음이 대신 맞는다", foe.hp == foe.maxhp and "얼음이 대신" in texts(ev),
        (foe.hp, foe.maxhp, texts(ev)))
    chk("  얼음이 깨지면 빨라지고 물러진다", foe.stat("spe") > spe0 * 1.5 and foe.stat("def") < def0,
        (spe0, foe.stat("spe"), def0, foe.stat("def")))
    ev = use(bt, "me", "CROSSCHOP")
    chk("  두 번째는 그대로 맞는다", foe.hp < foe.maxhp, texts(ev))
    ev = []
    SM.set_weather(bt, "snow", ev)
    chk("  눈이 내리면 얼음이 다시 언다", not foe.ab.get("noice") and foe.stat("spe") == spe0, (foe.ab, texts(ev)))
    bt, me, foe = fight(mon("MACHAMP", 50, ["FLAMETHROWER"]), mon("EISCUE", 100, ability="ICEFACE"))
    use(bt, "me", "FLAMETHROWER")
    chk("  특수 공격은 못 막는다", foe.hp < foe.maxhp and not foe.ab.get("noice"))

    bt, me, foe = fight(mon("MACHAMP", 100, ["CROSSCHOP"], ability="NOGUARD"),
                        mon("CRAMORANT", 60, ["SURF"], ability="GULPMISSILE"))
    ev = use(bt, "foe", "SURF")
    chk("그대로꿀꺽미사일: 파도타기를 쓰면 먹이를 문다", foe.ab.get("prey") == "gulp", (foe.ab, texts(ev)))
    hp = me.hp
    ev = use(bt, "me", "CROSSCHOP")
    chk("  맞으면 먹이를 뱉는다 (최대 체력의 1/4, 방어 하락)",
        hp - me.hp == me.maxhp // 4 and me.stages["def"] == -1 and not foe.ab.get("prey"),
        (hp - me.hp, me.maxhp // 4, me.stages, texts(ev)))

    asked = []
    bt, me, foe = fight(mon("MACHAMP", 50, ["CROSSCHOP"], ability="NOGUARD"),
                        mon("GOLISOPOD", 50, ability="EMERGENCYEXIT"))
    bt.teams = {"me": [me], "foe": [foe, B.Fighter(DEX, mon("SNORLAX", 50))]}
    bt.switcher = lambda who, mode, ev, key, state=None: asked.append((who, mode)) or True
    foe.hp = foe.maxhp // 2 + 5
    use(bt, "me", "CROSSCHOP")
    chk("위기회피: 체력이 절반 아래로 내려가면 물러난다", asked == [("foe", "out")], asked)
    asked[:] = []
    bt.teams = {"me": [me], "foe": [foe]}
    foe.hp = foe.maxhp // 2 + 5
    foe.ab.pop("fainted", None)
    use(bt, "me", "CROSSCHOP")
    chk("  바꿀 동료가 없으면 그대로 있는다", asked == [], asked)
    chk("도망태세도 같다", "WIMPOUT" in A.IMPLEMENTED)

    bt, me, foe = fight(mon("ESPATHRA", 50, ability="OPPORTUNIST"), mon("SNORLAX", 50, ["SWORDSDANCE", "GROWL"]))
    ev = use(bt, "foe", "SWORDSDANCE")
    chk("편승: 상대의 능력이 오르면 나도 오른다", me.stages["atk"] == 2 and foe.stages["atk"] == 2, (me.stages, texts(ev)))
    use(bt, "foe", "GROWL")
    chk("  떨어지는 것은 안 따라간다", me.stages["atk"] == 1 and foe.stages["atk"] == 2, (me.stages, foe.stages))

    bt, me, foe = fight(mon("ORICORIO", 50, ability="DANCER"), mon("SNORLAX", 50, ["SWORDSDANCE", "TACKLE"]))
    ev = use(bt, "foe", "SWORDSDANCE")
    chk("무희: 상대가 춤 기술을 쓰면 따라 춘다", me.stages["atk"] == 2 and foe.stages["atk"] == 2, (me.stages, texts(ev)))
    use(bt, "foe", "TACKLE")
    chk("  춤이 아닌 기술은 안 따라 한다", me.stages["atk"] == 2)
    bt, me, foe = fight(mon("ORICORIO", 50, ["SWORDSDANCE"], ability="DANCER"),
                        mon("ORICORIO", 50, ability="DANCER"))
    use(bt, "me", "SWORDSDANCE")
    chk("  무희끼리 끝없이 따라 추지 않는다", me.stages["atk"] == 2 and foe.stages["atk"] == 2, (me.stages, foe.stages))


def t_items():
    print("-- 나무열매를 다시 쓰는 특성")
    bt, me, foe = fight(mon("EXEGGUTOR", 50, held="SITRUSBERRY", ability="HARVEST"), mon("SNORLAX", 50))
    bt.field.weather, bt.field.weather_turns = "sun", 5
    me.hp = me.maxhp // 3
    ev = []
    B.H.check_hp(bt, me, "me", ev)
    chk("수확: 열매를 먹었다", me.used, texts(ev))
    ev = eot(bt)
    chk("  쾌청이면 턴 끝에 반드시 다시 열린다", not me.used and me.held == "SITRUSBERRY" and "수확" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("FARIGIRAF", 50, held="SITRUSBERRY", ability="CUDCHEW"), mon("SNORLAX", 50))
    me.hp = me.maxhp // 3
    ev = []
    B.H.check_hp(bt, me, "me", ev)
    hp1 = me.hp
    eot(bt)
    chk("되새김질: 먹은 턴에는 아직", me.hp == hp1, (hp1, me.hp))
    me.hp = hp1 = me.maxhp // 3
    ev = eot(bt)
    chk("  다음 턴 끝에 한 번 더 먹는다", me.hp > hp1 and "먹었다" in texts(ev), (hp1, me.hp, texts(ev)))
    hp2 = me.hp = me.maxhp // 3
    eot(bt)
    chk("  한 번뿐이다", me.hp == hp2)


def t_forms():
    print("-- 모습이 바뀌는 특성")
    bt, me, foe = fight(mon("WISHIWASHI", 50, ability="SCHOOLING"), mon("SNORLAX", 50))
    solo = B.Fighter(DEX, mon("WISHIWASHI", 50, ability="SCHOOLING"))
    chk("어군: 나오면 군집의 모습 (능력치가 훌쩍 뛴다)", me.cond.get("form") == "school"
        and me.stat("atk") > solo.stat("atk") * 3, (me.cond, me.stat("atk"), solo.stat("atk")))
    chk("  체력은 그대로", me.maxhp == solo.maxhp)
    me.hp = me.maxhp // 4
    ev = eot(bt)
    chk("  체력이 1/4 이하가 되면 흩어진다", me.cond.get("form") is None and me.stat("atk") == solo.stat("atk"),
        (me.cond, texts(ev)))
    bt, me, foe = fight(mon("WISHIWASHI", 19, ability="SCHOOLING"), mon("SNORLAX", 50))
    chk("  레벨 20 아래는 무리를 못 짓는다", me.cond.get("form") is None)

    bt, me, foe = fight(mon("MINIOR", 50, ability="SHIELDSDOWN"), mon("SNORLAX", 50))
    ev = []
    bt._apply_status(me, "paralysis", ev, source=foe)
    chk("리밋실드: 껍질이 있는 동안은 상태이상에 안 걸린다", me.status is None, texts(ev))
    spe0 = me.stat("spe")
    me.hp = me.maxhp // 2
    eot(bt)
    chk("  체력이 절반 이하면 껍질이 깨진다 (빨라진다)", me.cond.get("form") == "core" and me.stat("spe") > spe0 * 1.5,
        (me.cond, spe0, me.stat("spe")))
    bt._apply_status(me, "paralysis", ev, source=foe)
    chk("  깨진 뒤에는 걸린다", me.status == "paralysis")

    bt, me, foe = fight(mon("DARMANITAN", 50, ability="ZENMODE"), mon("SNORLAX", 50))
    spa0 = me.stat("spa")
    me.hp = me.maxhp // 2
    ev = eot(bt)
    chk("달마모드: 체력이 절반 이하면 변한다 (불꽃/에스퍼, 특수공격이 뛴다)",
        me.types() == ["FIRE", "PSYCHIC"] and me.stat("spa") > spa0 * 2, (me.types(), spa0, me.stat("spa"), texts(ev)))
    f2 = B.Fighter(DEX, me.mon)
    f2.ability_on = True
    f2.load_volatile(json.loads(json.dumps(me.volatile())))
    chk("  저장했다 되살려도 그 모습이다", f2.types() == ["FIRE", "PSYCHIC"] and f2.stat("spa") == me.stat("spa"))
    me.hp = me.maxhp
    eot(bt)
    chk("  회복하면 돌아온다", me.types() == ["FIRE"] and me.stat("spa") == spa0)

    bt, me, foe = fight(mon("PALAFIN", 50, ability="ZEROTOHERO"), mon("SNORLAX", 50))
    atk0 = me.stat("atk")
    chk("마이티체인지: 처음에는 그대로", me.cond.get("form") is None)
    A.on_switch_out(me)
    me.clear_volatile()
    ev = []
    A.on_switch_in(bt, me, "me", ev)
    chk("  물러났다 나오면 마이티폼", me.cond.get("form") == "hero" and me.stat("atk") > atk0 * 1.8
        and "마이티폼" in texts(ev), (me.cond, atk0, me.stat("atk"), texts(ev)))

    bt, me, foe = fight(mon("TERAPAGOS", 50, ability="TERASHIFT"), mon("MACHAMP", 50, ["CROSSCHOP", "TACKLE"]))
    base = B.Fighter(DEX, mon("TERAPAGOS", 50, ability="TERASHIFT"))
    chk("테라체인지: 나오면 테라스탈폼", me.cond.get("form") == "terastal" and me.stat("def") > base.stat("def"),
        (me.cond, me.stat("def"), base.stat("def")))
    _d, _c, e = B.damage(DEX, DEX.move("CROSSCHOP"), foe, me, B.EST_RNG, crit=False)
    full = est(foe, me, "CROSSCHOP")
    me.hp -= 1
    chk("  테라셸: 체력이 가득하면 효과가 굉장한 기술도 별로다", full * 3 < est(foe, me, "CROSSCHOP"),
        (full, est(foe, me, "CROSSCHOP")))

    bt, me, foe = fight(mon("CASTFORM", 50, ["WEATHERBALL"], ability="FORECAST"), mon("SNORLAX", 50))
    chk("기분파: 날씨가 없으면 노말", me.types() == ["NORMAL"])
    ev = []
    SM.set_weather(bt, "sun", ev)
    chk("  쾌청이면 불꽃", me.types() == ["FIRE"], (me.types(), texts(ev)))
    SM.set_weather(bt, "rain", ev)
    chk("  비가 오면 물", me.types() == ["WATER"])
    SM.set_weather(bt, "snow", ev)
    chk("  눈이 오면 얼음", me.types() == ["ICE"])
    bt.field.weather_turns = 1
    eot(bt)
    chk("  날씨가 끝나면 노말로", me.types() == ["NORMAL"], (me.types(), bt.field.weather))

    bt, me, foe = fight(mon("CHERRIM", 50, ability="FLOWERGIFT"), mon("SNORLAX", 50))
    a0, d0 = me.stat("atk"), me.stat("spd")
    bt.field.weather, bt.field.weather_turns = "sun", 5
    chk("플라워기프트: 쾌청이면 공격과 특수방어가 1.5배",
        me.stat("atk") == int(a0 * 1.5) and me.stat("spd") == int(d0 * 1.5), (a0, me.stat("atk"), d0, me.stat("spd")))

    bt, me, foe = fight(mon("MORPEKO", 50, ["AURAWHEEL"], ability="HUNGERSWITCH"), mon("SNORLAX", 100))
    chk("꼬르륵스위치: 처음에는 배부른 모양 (오라휠은 전기)", AF.move_type(DEX.move("AURAWHEEL"), me) is None)
    ev = eot(bt)
    chk("  턴이 끝나면 배고픈 모양 (오라휠은 악)", me.cond.get("hangry") and AF.move_type(DEX.move("AURAWHEEL"), me) == "DARK",
        texts(ev))
    eot(bt)
    chk("  다음 턴 끝에는 다시 배부른 모양", not me.cond.get("hangry"))

    bt, me, foe = fight(mon("ARCEUS", 50, ["JUDGMENT"], held="FLAMEPLATE", ability="MULTITYPE"), mon("SNORLAX", 50))
    chk("멀티타입: 지닌 플레이트의 타입이 된다", me.types() == ["FIRE"], (me.types(), texts(bt.entry)))
    bt, me, foe = fight(mon("ARCEUS", 50, ability="MULTITYPE"), mon("SNORLAX", 50))
    chk("  플레이트가 없으면 노말", me.types() == ["NORMAL"])

    bt, me, foe = fight(mon("DITTO", 50, ["TRANSFORM"], ability="IMPOSTER"), mon("MACHAMP", 50, ["CROSSCHOP", "TACKLE"]))
    chk("괴짜: 나오자마자 눈앞의 포켓몬으로 변신한다",
        me.cond.get("transformed") == "MACHAMP" and me.moves == ["CROSSCHOP", "TACKLE"] and me.types() == foe.types(),
        (me.cond.get("transformed"), me.moves, texts(bt.entry)))

    bt, me, foe = fight(mon("EELEKTROSS", 50, ability="EELEVATE"), mon("GARCHOMP", 50, ["EARTHQUAKE"]))
    ev = use(bt, "foe", "EARTHQUAKE")
    chk("Eelevate: 땅 기술을 안 받는다", not hits(ev) and me.hp == me.maxhp, texts(ev))
    bt.field.side("me")["spikes"] = 3
    ev = []
    SM.enter(bt, "me", ev)
    chk("  압정도 안 밟는다", me.hp == me.maxhp, texts(ev))


def t_moves_with_abilities():
    print("-- 특성과 맞물리는 기술 (1.9.2)")
    bt, me, foe = fight(mon("ZERAORA", 50, ["PLASMAFISTS"]), mon("SNORLAX", 100, ["TACKLE"]))
    me.types_override = ["GROUND"]
    use(bt, "me", "PLASMAFISTS")
    ev = use(bt, "foe", "TACKLE")
    chk("플라스마피스트: 그 턴의 노말 기술이 전기가 된다 (땅 타입에게 안 통한다)",
        not hits(ev) and "효과가 없는" in texts(ev), texts(ev))
    eot(bt)
    ev = use(bt, "foe", "TACKLE")
    chk("  다음 턴에는 다시 노말", hits(ev), texts(ev))

    bt, me, foe = fight(mon("PIDGEOT", 50, ["ROOST"]), mon("GARCHOMP", 50, ["EARTHQUAKE"]))
    me.hp = me.maxhp // 2
    bt.begin_turn()
    use(bt, "me", "ROOST")
    ev = use(bt, "foe", "EARTHQUAKE")
    chk("날개쉬기: 그 턴에는 비행 타입이 아니다 (지진이 맞는다)", hits(ev), texts(ev))
    bt.begin_turn()
    me.hp = me.maxhp
    ev = use(bt, "foe", "EARTHQUAKE")
    chk("  다음 턴에는 다시 비행", not hits(ev), texts(ev))

    bt, me, foe = fight(mon("TOUCANNON", 50, ["BEAKBLAST"]), mon("MACHAMP", 50, ["CROSSCHOP", "FLAMETHROWER"]))
    bt.begin_turn()
    bt.pending = {"me": "BEAKBLAST", "foe": "CROSSCHOP"}
    foe.ability = "NOGUARD"
    use(bt, "foe", "CROSSCHOP")
    chk("부리캐논: 가열하는 동안 닿으면 데인다", foe.status == "burn", foe.status)
    bt, me, foe = fight(mon("TOUCANNON", 50, ["BEAKBLAST"]), mon("MACHAMP", 50, ["FLAMETHROWER"]))
    bt.begin_turn()
    bt.pending = {"me": "BEAKBLAST", "foe": "FLAMETHROWER"}
    use(bt, "foe", "FLAMETHROWER")
    chk("  안 닿는 기술은 괜찮다", foe.status is None)


def t_protean():
    """변환자재·리베로 (1.10.0 에서 본가와 다른 세 곳을 고쳤다).

    9세대 규칙이다: **나와 있는 동안 한 번만** 바뀐다 (8세대까지는 기술을 쓸 때마다였다).
    바뀌는 타입은 '도감에 적힌 타입' 이 아니라 **그 기술이 지금 실제로 나가는 타입**이고,
    다른 기술을 부르는 기술(흉내쟁이·잠꼬대·손가락흔들기 ...)은 **불려 나온 기술**의 타입이다.
    """
    print("-- 변환자재·리베로")
    G = lambda moves, ab="PROTEAN": mon("GRENINJA", 50, moves, ability=ab)   # noqa: E731

    bt, me, foe = fight(G(["ICEBEAM", "DARKPULSE"]), mon("SNORLAX", 50, ["TACKLE"]))
    ev = use(bt, "me", "ICEBEAM")
    chk("쓰는 기술의 타입 하나가 된다", me.types() == ["ICE"] and "얼음 타입이 되었다" in texts(ev), texts(ev))
    use(bt, "me", "DARKPULSE")
    chk("  나와 있는 동안 한 번만 (두 번째 기술에는 그대로)", me.types() == ["ICE"], me.types())
    me.types_override = None                       # 물러났다 (드라이버가 지운다)
    A.on_switch_in(bt, me, "me", [])
    use(bt, "me", "DARKPULSE")
    chk("  물러났다 나오면 다시 한 번", me.types() == ["DARK"], me.types())
    d = {}
    for ab in ("PROTEAN", "TORRENT"):
        bt, me, foe = fight(G(["THUNDERBOLT"], ab), mon("BLISSEY", 50, ["SPLASH"]))
        hp = foe.hp
        use(bt, "me", "THUNDERBOLT")
        d[ab] = hp - foe.hp
    chk("  바뀐 타입으로 자속이 붙는다 (1.5배)", 1.4 < d["PROTEAN"] / float(max(1, d["TORRENT"])) < 1.6, d)
    bt, me, foe = fight(mon("FROAKIE", 50, ["WATERGUN", "ICEBEAM"], ability="PROTEAN"), mon("SNORLAX", 50))
    use(bt, "me", "WATERGUN")
    first = me.types()
    use(bt, "me", "ICEBEAM")
    chk("  이미 그 타입 하나뿐이면 아껴 둔다", first == ["WATER"] and me.types() == ["ICE"], (first, me.types()))
    bt, me, foe = fight(G(["SURF"]), mon("SNORLAX", 50))
    use(bt, "me", None)
    chk("  발버둥으로는 안 바뀐다", me.types() == ["WATER", "DARK"], me.types())
    bt, me, foe = fight(mon("CINDERACE", 50, ["UTURN"], ability="LIBERO"), mon("SNORLAX", 50))
    use(bt, "me", "UTURN")
    chk("  리베로도 같다", me.types() == ["BUG"], me.types())

    # --- 다른 기술을 부르는 기술: 불려 나온 기술의 타입 (예전에는 부르는 기술의 노말이 되고 끝났다)
    bt, me, foe = fight(G(["COPYCAT"]), mon("CHARIZARD", 50, ["FLAMETHROWER"]))
    use(bt, "foe", "FLAMETHROWER")
    ev = use(bt, "me", "COPYCAT")
    chk("흉내쟁이로 화염방사를 쓰면 불꽃이 된다", me.types() == ["FIRE"], (me.types(), texts(ev)))
    bt, me, foe = fight(G(["SLEEPTALK", "ICEBEAM"]), mon("SNORLAX", 50))
    me.status, me.sleep_turns = "sleep", 3
    ev = use(bt, "me", "SLEEPTALK")
    chk("잠꼬대로 냉동빔이 나가면 얼음이 된다", me.types() == ["ICE"], (me.types(), texts(ev)))
    bt, me, foe = fight(G(["METRONOME"]), mon("SNORLAX", 50), seed=4)
    ev = use(bt, "me", "METRONOME")
    out = [e for e in ev if e.get("t") == "move"]
    chk("손가락흔들기는 나온 기술의 타입이 된다", len(out) == 2 and me.types() == [out[1]["moveType"]],
        (me.types(), [(e["move"], e["moveType"]) for e in out]))
    bt, me, foe = fight(G(["COPYCAT"]), mon("SNORLAX", 50))
    ev = use(bt, "me", "COPYCAT")
    chk("  부를 기술이 없어 실패하면 안 바뀌고, 다음 기술에 쓸 수 있다", me.types() == ["WATER", "DARK"]
        and not me.ab.get("protean"), (me.types(), texts(ev)))

    # --- 타입이 그때그때 정해지는 기술: 실제로 나가는 타입
    bt, me, foe = fight(G(["WEATHERBALL"]), mon("BLISSEY", 50, ["SPLASH"]))
    bt.field.weather, bt.field.weather_turns = "rain", 5
    ev = use(bt, "me", "WEATHERBALL")
    chk("비 올 때 웨더볼은 물 → 물 타입이 된다", me.types() == ["WATER"], (me.types(), texts(ev)))
    bt, me, foe = fight(G(["WEATHERBALL"]), mon("BLISSEY", 50, ["SPLASH"]))
    use(bt, "me", "WEATHERBALL")
    chk("  날씨가 없으면 노말", me.types() == ["NORMAL"], me.types())
    m = G(["HIDDENPOWER"])
    bt, me, foe = fight(m, mon("BLISSEY", 50, ["SPLASH"]))
    want = MC.move_type(DEX.move("HIDDENPOWER"), me)
    use(bt, "me", "HIDDENPOWER")
    chk("잠재파워는 그 포켓몬의 잠재파워 타입", me.types() == [want] and want != "NORMAL", (me.types(), want))

    # --- 송전: 전기가 된 기술
    bt, me, foe = fight(G(["TACKLE"]), mon("SNORLAX", 50))
    me.cond["electrify"] = True
    ev = use(bt, "me", "TACKLE")
    chk("송전에 걸려 전기가 된 몸통박치기 → 전기 타입", me.types() == ["ELECTRIC"], (me.types(), texts(ev)))
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"]), mon("JOLTEON", 50, ["TACKLE"], ability="VOLTABSORB"))
    me.cond["electrify"] = True
    foe.hp = foe.maxhp // 2
    hp = foe.hp
    ev = use(bt, "me", "TACKLE")
    chk("  전기가 된 기술은 축전이 받아먹는다", foe.hp > hp and not hits(ev), (hp, foe.hp, texts(ev)))


def t_coverage():
    print("-- 남은 것")
    have = set()
    for s in DEX.species:
        have.update(s.get("abil") or [])
        if s.get("hidden"):
            have.add(s["hidden"])
    for m in DEX.megas if hasattr(DEX, "megas") else []:
        have.update(m.get("abil") or [])
    left = sorted(have - A.IMPLEMENTED - A.SINGLES_NOTHING)
    chk("포켓몬이 가진 특성은 전부 '동작한다' 아니면 '1:1 에서는 원작도 아무 일 없다' 다", not left, left)
    both = sorted(A.IMPLEMENTED & A.SINGLES_NOTHING)
    chk("두 목록이 겹치지 않는다", not both, both)
    chk("폼 표의 종이 전부 도감에 있다", all(DEX.get(k[0]) for k in A.FORMS), [k for k in A.FORMS if not DEX.get(k[0])])


def main():
    t_field()
    t_attacker()
    t_defender()
    t_items()
    t_forms()
    t_moves_with_abilities()
    t_protean()
    t_coverage()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
