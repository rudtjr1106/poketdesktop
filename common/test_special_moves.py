# -*- coding: utf-8 -*-
"""원작 공식 기술 검사 — 위력이 정해지지 않았던 기술과 씨뿌리기. 서버 없이 돈다.

    python common/test_special_moves.py

사용자 제보: "근육몬 vs 내룸벨트에서 안다리걸기를 세 번 썼는데 세 번 다 안 맞았다".
관장 배틀 #909 의 저장본에 안다리걸기 PP 가 17/20 이었고 근육몬은 노가드였다 -
빗나간 게 아니라 **맞았는데 데미지가 0** 이었다. 도감의 위력이 0 이라 battle.py 가
데미지 계산을 건너뛰었다. 같은 이유로 공격기 34개(배울 수 있는 것)가 아무 일도
안 했고, 씨뿌리기는 상태를 처리하는 곳이 없어서 안 됐다.

1. 버그를 그대로 재현해 이제 들어가는지 본다.
2. 공식마다 위력·데미지가 원작 수치와 같은지 본다.
3. 실패 조건(카운터로 돌려줄 게 없다, 일격기가 레벨이 낮다 ...)을 본다.
4. 씨뿌리기: 심고, 턴마다 빼앗고, 물러나면 풀리고, 저장했다 되살려도 남는다.
5. 배울 수 있는 위력 0 공격기가 하나도 빠지지 않았다.
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import battle as B              # noqa: E402
from common import movecalc as MC           # noqa: E402
from common import party_battle as PB       # noqa: E402
from common import pokelogic as P           # noqa: E402
from common import trainer_battle as TB     # noqa: E402

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


def mon(dex, species, level, moves, iv=31, happiness=None, held=None, ability=None):
    m = P.make_pokemon(dex.get(species), level, random.Random(1), shiny_rate=10 ** 9,
                       ivs=dict((s, iv) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    if happiness is not None:
        m["happiness"] = happiness
    if ability:
        m["ability"] = ability
    return m


def fight(dex, a, b, seed=1, abilities=False):
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    me.ability_on = foe.ability_on = abilities
    return B.Battle(dex, me, foe, random.Random(seed), ai="trainer"), me, foe


def use(bt, who, key):
    ev = []
    user, target = (bt.me, bt.foe) if who == "me" else (bt.foe, bt.me)
    bt._use(who, user, target, key, ev)
    return ev


def texts(ev):
    return " | ".join(e.get("text", "") for e in ev if e.get("text"))


def pw(dex, key, user, target):
    return MC.power(dex.move(key), user, target)


# ---------------------------------------------------------------- 1. 제보
def t_제보(dex):
    print("-- 제보: 근육몬 안다리걸기 vs 내룸벨트")
    bt, me, foe = fight(dex, mon(dex, "MACHOKE", 37, ["LOWKICK"], ability="NOGUARD"),
                        mon(dex, "WATCHOG", 33, ["TACKLE"]), abilities=True)
    ev = use(bt, "me", "LOWKICK")
    hits = [e for e in ev if e.get("t") == "hit"]
    chk("안다리걸기가 들어간다", hits and hits[0]["damage"] > 0 and foe.hp < foe.maxhp, texts(ev))
    chk("내룸벨트(27kg)에게는 위력 60", pw(dex, "LOWKICK", me, foe) == 60, pw(dex, "LOWKICK", me, foe))
    chk("PP 는 한 번만 준다", me.pp["LOWKICK"] == dex.move("LOWKICK")["pp"] - 1, me.pp)


# ---------------------------------------------------------------- 2. 위력 공식
def t_위력(dex):
    print("-- 위력 공식")
    pika, lax = mon(dex, "PIKACHU", 50, ["TACKLE"]), mon(dex, "SNORLAX", 50, ["TACKLE"])
    bt, a, b = fight(dex, pika, lax)
    chk("도감에 몸무게가 있다 (피카츄 6kg, 잠만보 460kg)", MC.kg(a) == 6.0 and MC.kg(b) == 460.0, (MC.kg(a), MC.kg(b)))
    chk("안다리걸기: 460kg 이면 120", pw(dex, "LOWKICK", a, b) == 120)
    chk("풀묶기: 6kg 이면 20", pw(dex, "GRASSKNOT", b, a) == 20)
    chk("헤비봄버: 5배 넘게 무거우면 120", pw(dex, "HEAVYSLAM", b, a) == 120)
    chk("히트스탬프: 가벼우면 40", pw(dex, "HEATCRASH", a, b) == 40)

    a.hp = 1
    chk("바둥바둥: 체력 1 이면 200", pw(dex, "FLAIL", a, b) == 200)
    a.hp = a.maxhp
    chk("기사회생: 체력이 가득하면 20", pw(dex, "REVERSAL", a, b) == 20)
    chk("분화: 체력이 가득하면 150", pw(dex, "ERUPTION", a, b) == 150)
    a.hp = a.maxhp // 2
    chk("분화: 반이면 75 쯤", abs(pw(dex, "ERUPTION", a, b) - 75) <= 1, pw(dex, "ERUPTION", a, b))
    a.hp = a.maxhp
    chk("묵사발: 상대 체력이 가득하면 120", pw(dex, "CRUSHGRIP", a, b) == 120)

    a.base["spe"], b.base["spe"] = 400, 100
    chk("일렉트릭볼: 스피드 4배면 150", pw(dex, "ELECTROBALL", a, b) == 150)
    a.base["spe"], b.base["spe"] = 50, 200
    chk("자이로볼: 25x200/50+1 = 101", pw(dex, "GYROBALL", a, b) == 101, pw(dex, "GYROBALL", a, b))

    a.mon["happiness"] = 255
    chk("은혜갚기: 친밀도 255 면 102", pw(dex, "RETURN", a, b) == 102)
    a.mon["happiness"] = 0
    chk("분풀이: 친밀도 0 이면 102", pw(dex, "FRUSTRATION", a, b) == 102)

    a.stages["atk"], a.stages["spe"] = 2, 1
    chk("어시스트파워: 랭크 +3 이면 80", pw(dex, "STOREDPOWER", a, b) == 80)
    b.stages["def"] = 2
    chk("혼내기: 상대 +2 면 100", pw(dex, "PUNISHMENT", a, b) == 100)
    a.pp["TRUMPCARD"] = 0
    chk("마지막수단: 쓰고 남은 PP 0 이면 200", pw(dex, "TRUMPCARD", a, b) == 200)

    a.status = "burn"
    chk("객기: 화상이면 140", pw(dex, "FACADE", a, b) == 140)
    b.status = "sleep"
    chk("병상첨병: 상대가 상태이상이면 130", pw(dex, "HEX", a, b) == 130)
    b.hp = b.maxhp // 2
    chk("소금물: 상대 체력이 반 이하면 130", pw(dex, "BRINE", a, b) == 130)
    chk("애크러뱃: 도구가 없으면 110", pw(dex, "ACROBATICS", a, b) == 110)
    b.held = "LEFTOVERS"
    chk("탁쳐서떨구기: 상대가 도구를 들면 97", pw(dex, "KNOCKOFF", a, b) == 97)

    # 화상이어도 객기는 반감되지 않는다
    bt, a, b = fight(dex, mon(dex, "RATICATE", 50, ["FACADE"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    plain, _c, _e = B.damage(dex, dex.move("FACADE"), a, b, B.EST_RNG, crit=False)
    a.status = "burn"
    burned, _c, _e = B.damage(dex, dex.move("FACADE"), a, b, B.EST_RNG, crit=False)
    chk("객기: 화상이면 데미지가 두 배 (반감 없음)", abs(burned - plain * 2) <= 3, (plain, burned))

    hp = mon(dex, "PIKACHU", 50, ["HIDDENPOWER"], iv=31)
    f = B.Fighter(dex, hp)
    chk("잠재파워: 개체값이 모두 31 이면 악", MC.move_type(dex.move("HIDDENPOWER"), f) == "DARK")
    f.mon["ivs"] = dict((s, 30) for s in P.STATS)
    chk("잠재파워: 모두 짝수면 격투", MC.move_type(dex.move("HIDDENPOWER"), f) == "FIGHTING")


# ---------------------------------------------------------------- 3. 고정 데미지
def t_고정(dex):
    print("-- 고정 데미지")
    bt, me, foe = fight(dex, mon(dex, "MACHAMP", 50, ["SEISMICTOSS", "DRAGONRAGE", "SONICBOOM", "SUPERFANG"]),
                        mon(dex, "SNORLAX", 60, ["TACKLE"]))
    for key, want in (("SEISMICTOSS", 50), ("DRAGONRAGE", 40), ("SONICBOOM", 20)):
        foe.hp = foe.maxhp
        ev = use(bt, "me", key)
        chk("%s: 정확히 %d" % (key, want), foe.maxhp - foe.hp == want, (foe.maxhp - foe.hp, texts(ev)))
        chk("%s: 상성 문구가 없다" % key, "효과가" not in texts(ev), texts(ev))
    foe.hp = 101
    use(bt, "me", "SUPERFANG")
    chk("분노의앞니: 101 -> 51 (반을 깎는다, 내림)", foe.hp == 51, foe.hp)

    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["NIGHTSHADE"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    ev = use(bt, "me", "NIGHTSHADE")
    chk("나이트헤드: 노말 타입에게는 효과가 없다", foe.hp == foe.maxhp and "효과가 없는" in texts(ev), texts(ev))
    bt, me, foe = fight(dex, mon(dex, "MACHAMP", 50, ["SEISMICTOSS"]), mon(dex, "GASTLY", 50, ["LICK"]))
    use(bt, "me", "SEISMICTOSS")
    chk("지구던지기: 고스트에게는 효과가 없다", foe.hp == foe.maxhp)

    bt, me, foe = fight(dex, mon(dex, "RATTATA", 50, ["ENDEAVOR"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    me.hp = 10
    use(bt, "me", "ENDEAVOR")
    chk("죽기살기: 상대 체력을 내 체력(10)까지", foe.hp == 10, foe.hp)
    ev = use(bt, "me", "ENDEAVOR")
    chk("죽기살기: 상대가 이미 같거나 적으면 실패", foe.hp == 10 and "실패" in texts(ev), texts(ev))

    bt, me, foe = fight(dex, mon(dex, "INFERNAPE", 50, ["FINALGAMBIT"]), mon(dex, "SNORLAX", 70, ["TACKLE"]))
    have = me.hp
    use(bt, "me", "FINALGAMBIT")
    chk("목숨걸기: 내 체력만큼 주고 쓰러진다", foe.maxhp - foe.hp == have and not me.alive(), (foe.hp, me.hp))

    got = set()
    for s in range(60):
        bt, me, foe = fight(dex, mon(dex, "ABRA", 40, ["PSYWAVE"]), mon(dex, "SNORLAX", 60, ["TACKLE"]), seed=s)
        use(bt, "me", "PSYWAVE")
        got.add(foe.maxhp - foe.hp)
    chk("사이코웨이브: 레벨의 0.5~1.5 배 (40 -> 20~60)", got and min(got) >= 20 and max(got) <= 60 and len(got) > 5,
        (min(got), max(got)))


def t_일격기(dex):
    print("-- 일격기")
    bt, me, foe = fight(dex, mon(dex, "KINGLER", 30, ["GUILLOTINE"]), mon(dex, "SNORLAX", 40, ["TACKLE"]))
    ev = use(bt, "me", "GUILLOTINE")
    chk("상대 레벨이 높으면 안 먹힌다", foe.hp == foe.maxhp and "효과가 없는" in texts(ev), texts(ev))
    bt, me, foe = fight(dex, mon(dex, "KINGLER", 100, ["GUILLOTINE"]), mon(dex, "SNORLAX", 30, ["TACKLE"]))
    chk("레벨 차 70 이면 명중률 100", MC.ohko_accuracy(dex.move("GUILLOTINE"), me, foe) == 100)
    ev = use(bt, "me", "GUILLOTINE")
    chk("맞으면 한 방 (일격필살!)", not foe.alive() and "일격필살" in texts(ev), texts(ev))
    bt, me, foe = fight(dex, mon(dex, "LAPRAS", 100, ["SHEERCOLD"]), mon(dex, "GLACEON", 30, ["TACKLE"]))
    use(bt, "me", "SHEERCOLD")
    chk("절대영도: 얼음 타입에게는 안 먹힌다", foe.hp == foe.maxhp)
    chk("절대영도: 얼음 타입이 아니면 기본 20", MC.ohko_accuracy(dex.move("SHEERCOLD"), B.Fighter(dex, mon(dex, "SNORLAX", 50, [])),
                                                         B.Fighter(dex, mon(dex, "RATTATA", 50, []))) == 20)
    bt, me, foe = fight(dex, mon(dex, "DUGTRIO", 100, ["FISSURE"]), mon(dex, "GEODUDE", 30, ["TACKLE"], ability="STURDY"),
                        abilities=True)
    ev = use(bt, "me", "FISSURE")
    chk("옹골참은 일격기를 막는다", foe.hp == foe.maxhp and "옹골참" in texts(ev), texts(ev))


def t_돌려주기(dex):
    print("-- 카운터·미러코트·메탈버스트·참기")
    bt, me, foe = fight(dex, mon(dex, "WOBBUFFET", 50, ["COUNTER", "MIRRORCOAT"]),
                        mon(dex, "RATICATE", 50, ["TACKLE", "SWIFT"]))
    bt.begin_turn()
    ev = use(bt, "me", "COUNTER")
    chk("맞은 게 없으면 카운터는 실패", foe.hp == foe.maxhp and "실패" in texts(ev), texts(ev))
    bt.begin_turn()
    use(bt, "foe", "TACKLE")
    took = me.maxhp - me.hp
    use(bt, "me", "COUNTER")
    chk("카운터: 물리로 맞은 %d 의 두 배" % took, foe.maxhp - foe.hp == took * 2, (took, foe.maxhp - foe.hp))
    foe.hp = foe.maxhp
    bt.begin_turn()
    use(bt, "foe", "SWIFT")
    ev = use(bt, "me", "COUNTER")
    chk("카운터: 특수로 맞았으면 실패", foe.hp == foe.maxhp, texts(ev))
    me.hp = me.maxhp
    bt.begin_turn()
    use(bt, "foe", "SWIFT")
    took = me.maxhp - me.hp
    use(bt, "me", "MIRRORCOAT")
    chk("미러코트: 특수로 맞은 것의 두 배", foe.maxhp - foe.hp == took * 2, (took, foe.maxhp - foe.hp))
    bt.begin_turn()
    ev = use(bt, "me", "MIRRORCOAT")
    chk("턴이 바뀌면 지난 턴 데미지는 못 돌려준다", "실패" in texts(ev), texts(ev))

    bt, me, foe = fight(dex, mon(dex, "ARON", 50, ["METALBURST"]), mon(dex, "RATICATE", 50, ["TACKLE"]))
    bt.begin_turn()
    use(bt, "foe", "TACKLE")
    took = me.maxhp - me.hp
    use(bt, "me", "METALBURST")
    chk("메탈버스트: 1.5 배", foe.maxhp - foe.hp == int(took * 1.5), (took, foe.maxhp - foe.hp))

    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 60, ["BIDE"]), mon(dex, "RATTATA", 40, ["TACKLE"]))
    total = 0
    for turn in range(3):
        bt.begin_turn()
        ev = use(bt, "me", "BIDE")
        if turn < 2:
            before = me.hp
            use(bt, "foe", "TACKLE")
            total += before - me.hp
    chk("참기: 두 턴 참고 셋째 턴에 받은 만큼 두 배", foe.maxhp - foe.hp == min(foe.maxhp, total * 2),
        (total, foe.maxhp - foe.hp, texts(ev)))
    chk("참기: PP 는 처음 한 번만", me.pp["BIDE"] == dex.move("BIDE")["pp"] - 1, me.pp)


def t_비축(dex):
    print("-- 비축하기·토해내기·꿀꺽")
    bt, me, foe = fight(dex, mon(dex, "SWALOT", 50, ["STOCKPILE", "SPITUP", "SWALLOW"]), mon(dex, "SNORLAX", 60, ["TACKLE"]))
    ev = use(bt, "me", "SPITUP")
    chk("비축이 없으면 토해내기 실패", foe.hp == foe.maxhp and "실패" in texts(ev), texts(ev))
    use(bt, "me", "STOCKPILE")
    use(bt, "me", "STOCKPILE")
    chk("두 번 비축: 방어·특방 +2", me.stockpile == 2 and me.stages["def"] == 2 and me.stages["spd"] == 2,
        (me.stockpile, me.stages))
    one = B.damage(dex, dict(dex.move("SPITUP"), _power=100), me, foe, B.EST_RNG, crit=False)[0]
    two = B.damage(dex, dict(dex.move("SPITUP"), _power=200), me, foe, B.EST_RNG, crit=False)[0]
    chk("토해내기 위력은 비축 수 x100", MC.expected_power(dex.move("SPITUP"), me, foe) == 200 and two > one)
    use(bt, "me", "SPITUP")
    chk("토해내면 비축과 올린 랭크가 사라진다", me.stockpile == 0 and me.stages["def"] == 0 and foe.hp < foe.maxhp,
        (me.stockpile, me.stages))
    for _ in range(3):
        use(bt, "me", "STOCKPILE")
    ev = use(bt, "me", "STOCKPILE")
    chk("비축은 세 번까지", me.stockpile == 3 and "실패" in texts(ev), texts(ev))
    me.hp = 1
    use(bt, "me", "SWALLOW")
    chk("꿀꺽: 세 번 비축이면 전부 회복", me.hp == me.maxhp and me.stockpile == 0, (me.hp, me.maxhp))


def t_한번씩(dex):
    print("-- 매그니튜드·프레젠트·집단폭행·내던지기·자연의은혜")
    sizes = set()
    for s in range(80):
        bt, me, foe = fight(dex, mon(dex, "DUGTRIO", 50, ["MAGNITUDE"]), mon(dex, "SNORLAX", 70, ["TACKLE"]), seed=s)
        ev = use(bt, "me", "MAGNITUDE")
        for e in ev:
            if e.get("t") == "msg" and e.get("text", "").startswith("매그니튜드 "):
                sizes.add(int(e["text"].split()[1].strip("!")))
    chk("매그니튜드: 4~10, 여러 크기가 나온다", sizes and min(sizes) >= 4 and max(sizes) <= 10 and len(sizes) >= 5, sizes)

    healed = hurt = 0
    for s in range(120):
        bt, me, foe = fight(dex, mon(dex, "DELIBIRD", 50, ["PRESENT"]), mon(dex, "SNORLAX", 70, ["TACKLE"]), seed=s)
        foe.hp = foe.maxhp // 2
        use(bt, "me", "PRESENT")
        healed += foe.hp > foe.maxhp // 2
        hurt += foe.hp < foe.maxhp // 2
    chk("프레젠트: 대개 때리고 가끔(20%%) 회복시킨다 (%d/%d)" % (healed, hurt), 10 <= healed <= 40 and hurt >= 60)

    team = [mon(dex, sp, 50, ["BEATUP"]) for sp in ("SNEASEL", "HOUNDOUR", "MURKROW", "UMBREON")]
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "t", "level": 50,
               "team": [{"species": "SNORLAX", "level": 70, "moves": ["TACKLE"], "iv": 31, "evs": {},
                         "nature": "HARDY", "ability": "THICKFAT", "held": None, "gender": "M"}]}
    tb = TB.TrainerBattle(dex, team, trainer, random.Random(3))
    tb.start()
    tb.me_team[3].status = "poison"
    ev = []
    tb.bt._use("me", tb.me, tb.foe, "BEATUP", ev)
    n = [e for e in ev if e.get("t") == "hit"]
    chk("집단폭행: 기절·상태이상이 아닌 동료 수(3)만큼 때린다", len(n) == 3, texts(ev))

    bt, me, foe = fight(dex, mon(dex, "SNEASEL", 50, ["FLING"], held="KINGSROCK"), mon(dex, "SNORLAX", 60, ["TACKLE"]))
    ev = use(bt, "me", "FLING")
    chk("내던지기: 왕의징표석을 던져 때리고 풀죽게 한다", foe.hp < foe.maxhp and foe.flinched and me.item_gone, texts(ev))
    ev = use(bt, "me", "FLING")
    chk("던진 도구는 이 판에서 다시 못 쓴다", "실패" in texts(ev) and not MC.item_on(me) and me.held is None
        and me.mon.get("held") == "KINGSROCK", texts(ev))
    bt, me, foe = fight(dex, mon(dex, "SNEASEL", 50, ["FLING"], held="FLAMEORB"), mon(dex, "SNORLAX", 60, ["TACKLE"]))
    use(bt, "me", "FLING")
    chk("화염구슬을 던지면 화상", foe.status == "burn", foe.status)
    bt, me, foe = fight(dex, mon(dex, "SNEASEL", 50, ["FLING"]), mon(dex, "SNORLAX", 60, ["TACKLE"]))
    chk("도구가 없으면 내던지기 실패", "실패" in texts(use(bt, "me", "FLING")))

    bt, me, foe = fight(dex, mon(dex, "TROPIUS", 50, ["NATURALGIFT"], held="SITRUSBERRY"), mon(dex, "MACHAMP", 50, ["TACKLE"]))
    chk("자연의은혜: 자뭉열매는 에스퍼 80", MC.move_type(dex.move("NATURALGIFT"), me) == "PSYCHIC"
        and MC.expected_power(dex.move("NATURALGIFT"), me, foe) == 80)
    ev = use(bt, "me", "NATURALGIFT")
    hit = [e for e in ev if e.get("t") == "hit"]
    chk("자연의은혜: 격투에게 효과가 굉장하고 열매가 없어진다", hit and "효과가 굉장" in texts(ev) and me.item_gone, texts(ev))


# ---------------------------------------------------------------- 4. 씨뿌리기
def t_씨뿌리기(dex):
    print("-- 씨뿌리기")
    bt, me, foe = fight(dex, mon(dex, "BULBASAUR", 30, ["LEECHSEED"]), mon(dex, "RATTATA", 30, ["TACKLE"]), seed=2)
    me.hp = me.maxhp // 2
    ev = []
    for s in range(10):
        bt.rng = random.Random(s)
        ev = use(bt, "me", "LEECHSEED")
        if foe.seeded:
            break
    chk("씨앗을 심는다", foe.seeded and "씨앗을 심었다" in texts(ev), texts(ev))
    ev = use(bt, "me", "LEECHSEED")
    chk("이미 심었으면 실패", "실패" in texts(ev) or "빗나갔다" in texts(ev), texts(ev))
    before_me, before_foe = me.hp, foe.hp
    ev = []
    bt._end_of_turn(ev)
    d = max(1, foe.maxhp // 8)
    chk("턴 끝에 최대 체력의 1/8 을 빼앗는다", before_foe - foe.hp == d, (before_foe, foe.hp, d))
    chk("빼앗은 만큼 맞은편이 회복한다", me.hp - before_me == d, (before_me, me.hp))
    chk("화면이 그리는 이벤트(chip·heal)로 나간다", [e["t"] for e in ev][:2] == ["chip", "heal"], [e["t"] for e in ev])

    back = B.Fighter(dex, foe.mon, foe.hp, foe.pp, foe.status)
    back.load_volatile(json.loads(json.dumps(foe.volatile())))
    chk("저장했다 되살려도 씨앗이 남는다", back.seeded)

    bt, me, foe = fight(dex, mon(dex, "BULBASAUR", 30, ["LEECHSEED"]), mon(dex, "ODDISH", 30, ["TACKLE"]))
    ev = use(bt, "me", "LEECHSEED")
    chk("풀 타입에게는 안 걸린다", not foe.seeded and ("효과가 없는" in texts(ev) or "빗나갔다" in texts(ev)), texts(ev))

    # 관장 배틀: 물러나면 풀리고, 저장본에 남는다
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "t", "level": 50,
               "team": [{"species": "VENUSAUR", "level": 50, "moves": ["LEECHSEED"], "iv": 31, "evs": {},
                         "nature": "HARDY", "ability": "OVERGROW", "held": None, "gender": "M"}]}
    party = [mon(dex, "RATICATE", 50, ["TACKLE"]), mon(dex, "PIDGEOT", 50, ["TACKLE"])]
    tb = TB.TrainerBattle(dex, party, trainer, random.Random(1))
    tb.start()
    tb.me.seeded = True
    saved = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("관장 배틀 저장본에 씨앗이 남는다", saved.me.seeded)
    tb._switch("me", 1, [])
    chk("물러나면 씨앗이 풀린다", not tb.me_team[0].seeded)


# ---------------------------------------------------------------- 5. AI 와 빠진 것
def t_AI와_빠진것(dex):
    print("-- AI 와 빠진 기술")
    bt, me, foe = fight(dex, mon(dex, "MACHOKE", 40, ["LOWKICK", "LEER"]), mon(dex, "SNORLAX", 40, ["TACKLE"]))
    picks = collections.Counter()
    for s in range(40):
        bt.rng = random.Random(s)
        picks[bt.choose_for(me, foe, "trainer")] += 1
    chk("AI 가 잠만보에게 안다리걸기(120)를 쓴다", picks["LOWKICK"] >= 30, picks)
    bt, me, foe = fight(dex, mon(dex, "WOBBUFFET", 40, ["COUNTER", "TACKLE"]), mon(dex, "RATTATA", 40, ["TACKLE"]))
    bt.begin_turn()
    picks = collections.Counter()
    for s in range(40):
        bt.rng = random.Random(s)
        picks[bt.choose_for(me, foe, "trainer")] += 1
    chk("고를 때는 카운터 값을 모른다 - 몸통박치기를 쓴다", picks["TACKLE"] >= 30, picks)

    raw = dex.raw
    learn = set(k for s in raw["species"] for _lv, k in s.get("moves", []))
    with open(os.path.join(ROOT, "server", "data", "tms.json"), encoding="utf-8") as f:
        learn |= set(v["move"] for v in json.load(f)["tms"].values())
    dead = [k for k, m in raw["moves"].items() if m.get("cat") in ("physical", "special")
            and not m.get("power") and k in learn and not (MC.key(m) in MC.VARIABLE or MC.key(m) in MC.FIXED)]
    chk("배울 수 있는 위력 0 공격기가 모두 공식을 갖고 있다", not dead, dead)
    missing_kg = [s["internal"] for s in raw["species"] if not s.get("kg")]
    chk("모든 종에 몸무게(kg)가 있다", not missing_kg, missing_kg[:5])
    left = [k for k, m in raw["moves"].items() if k in learn
            and (m.get("desc") or "").startswith("사용할 수 없는 기술")]
    chk("배울 수 있는 기술에 '사용할 수 없는 기술입니다' 설명이 없다", not left, left)

    # 이런 기술을 든 팀끼리 끝까지 돈다 (예외 없이, 같은 시드면 같은 로그)
    names = ["MACHOKE", "WOBBUFFET", "SWALOT", "DUGTRIO", "SNORLAX", "BULBASAUR"]
    moves = [["LOWKICK", "SEISMICTOSS", "COUNTER", "BIDE"], ["COUNTER", "MIRRORCOAT", "SUPERFANG", "ENDEAVOR"],
             ["STOCKPILE", "SPITUP", "SWALLOW", "FLING"], ["MAGNITUDE", "FISSURE", "REVERSAL", "BEATUP"],
             ["HEAVYSLAM", "RETURN", "FLAIL", "PRESENT"], ["LEECHSEED", "GRASSKNOT", "NATURALGIFT", "PSYWAVE"]]
    a = [mon(dex, n, 45, m, held="SITRUSBERRY" if "NATURALGIFT" in m else ("IRONBALL" if "FLING" in m else None))
         for n, m in zip(names, moves)]
    b = [mon(dex, n, 45, m) for n, m in zip(reversed(names), reversed(moves))]
    ok, logs = True, []
    try:
        for s in range(20):
            logs.append(json.dumps(PB.simulate(dex, a, b, seed=s)["events"], sort_keys=True))
        again = json.dumps(PB.simulate(dex, a, b, seed=7)["events"], sort_keys=True)
    except Exception as e:                                          # noqa: BLE001
        ok, again = False, repr(e)
    chk("이런 기술을 든 팀끼리 20판이 끝까지 돈다", ok, again)
    chk("같은 시드면 같은 로그", ok and again == logs[7])


def main():
    dex = load_dex()
    t_제보(dex)
    t_위력(dex)
    t_고정(dex)
    t_일격기(dex)
    t_돌려주기(dex)
    t_비축(dex)
    t_한번씩(dex)
    t_씨뿌리기(dex)
    t_AI와_빠진것(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
