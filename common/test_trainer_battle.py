# -*- coding: utf-8 -*-
"""관장 도전 엔진 검사 — 특성과 6:6 진행. 서버 없이 돈다.

    python common/test_trainer_battle.py

넷을 본다.

1. **판이 끝까지 돈다.** 256명 전부를 상대로, 기술을 아무렇게나 고르고
   아무 때나 바꾸는 사람을 붙인다. 예외 없이 끝나야 하고, 쓰러진 포켓몬을
   다시 내보내는 일이 없어야 한다.
2. **저장했다 되살려도 같다.** 서버는 턴마다 DB 에 잤다 깬다. 중간에
   dump -> load 한 판과 안 한 판에 같은 입력을 넣으면 이벤트가 한 글자도
   달라지면 안 된다.
3. **특성이 정말 뭔가 한다.** 훅을 부르는 자리만 만들고 효과가 안 나는
   실수를 막는다. 특성이 있는 판과 없는 판을 같은 시드로 붙여 비교한다.
4. **특성을 끈 판은 예전과 같다.** (야생·PvP) test_held 의 요약값이 따로 지킨다.
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import abilities as A            # noqa: E402
from common import battle as B               # noqa: E402
from common import pokelogic as P            # noqa: E402
from common import statusmoves as SM          # noqa: E402
from common import trainer_battle as TB      # noqa: E402

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


def mon(dex, species, level, ability=None, moves=None, seed=1, held=None, iv=20):
    sp = dex.get(species)
    m = P.make_pokemon(sp, level, random.Random(seed), shiny_rate=10 ** 9,
                       ivs=dict((s, iv) for s in P.STATS))
    m["nature"] = "HARDY"
    if ability:
        m["ability"] = ability
    if moves:
        m["moves"] = moves
    m["held"] = held
    return m


def duel(dex, a, b, seed=7, on=True):
    """1:1 배틀 (Duel). a 가 me."""
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    me.ability_on = foe.ability_on = on
    bt = TB.Duel(dex, me, foe, random.Random(seed), ai="trainer")
    return bt, me, foe


def texts(ev):
    return " | ".join(e.get("text", "") for e in ev if e.get("text"))


# ---------------------------------------------------------------- 1. 끝까지
def t_끝까지_돈다(dex, gyms):
    print("-- 256명 전부와 끝까지")
    party = [mon(dex, k, 60, seed=i) for i, k in
             enumerate(["GARCHOMP", "GYARADOS", "ALAKAZAM", "SCIZOR", "VENUSAUR", "ARCANINE"])]
    errors, results, turns, bad_switch = [], {}, [], []
    for n, t in enumerate(gyms["trainers"]):
        rng = random.Random(1000 + n)
        tb = TB.TrainerBattle(dex, [dict(m) for m in party], t, random.Random(n))
        try:
            tb.start()
            guard = 0
            while not tb.over and guard < 2000:
                guard += 1
                if tb.need_switch:
                    tb.act("switch", rng.choice(tb.valid_switches()))
                    continue
                # 붙잡혀 있으면(검은눈빛·그림자밟기·자력 ...) 못 바꾼다.
                # 쓰러져서 바꾸는 것(need_switch)은 붙잡혀도 된다.
                # 날뛰는 중·모으는 중·반동 턴에도 못 바꾼다 (1.9.2, SM.must_stay).
                if tb.valid_switches() and rng.random() < 0.15 \
                        and not SM.trapped(tb.bt, tb.me) and not SM.must_stay(tb.me):
                    tb.act("switch", rng.choice(tb.valid_switches()))
                else:
                    # 막힌 기술(사슬묶기·도발·앵콜 ...)은 고르지 않는다 - 화면도 못 누르게
                    # 막고, 서버(TrainerBattle.act)는 거절한다. 이 봇이 거르지 않아서 급소
                    # 확률이 바뀌어 판이 달라지자 사슬묶기에 걸린 기술을 골라 예외가 났다.
                    keys = [m for m in tb.me.moves if tb.me.pp.get(m, 0) > 0
                            and not SM.restricted(tb.bt, tb.me, m)] or [B.STRUGGLE]
                    tb.act("move", rng.choice(keys))
                if not tb.me.alive() and not tb.need_switch and not tb.over:
                    bad_switch.append(t["name"])
            results[tb.result] = results.get(tb.result, 0) + 1
            turns.append(tb.turn)
            if not tb.over:
                errors.append((t["name"], "안 끝남"))
        except Exception as e:                            # noqa: BLE001
            import traceback
            errors.append((t["name"], traceback.format_exc().splitlines()[-3:]))
    chk("256판 모두 예외 없이 끝났다", not errors, errors[:3])
    chk("쓰러진 채 교체를 안 묻는 순간이 없다", not bad_switch, bad_switch[:3])
    print("       결과 %s · 평균 %.1f턴 · 최대 %d턴" % (results, sum(turns) / len(turns), max(turns)))


# ---------------------------------------------------------------- 2. 저장/복원
def t_저장했다_되살려도_같다(dex, gyms):
    print("-- dump -> load 해도 같은 판")
    t = next(x for x in gyms["trainers"] if x["name"] == "난천")
    party = [mon(dex, k, 95, seed=i) for i, k in
             enumerate(["LUCARIO", "TOGEKISS", "GYARADOS", "GARCHOMP", "ROSERADE", "SPIRITOMB"])]
    a = TB.TrainerBattle(dex, [dict(m) for m in party], t, random.Random(42))
    b = TB.TrainerBattle(dex, [dict(m) for m in party], t, random.Random(42))
    ea, eb = a.start(), b.start()
    same = ea == eb
    rng = random.Random(3)
    step = 0
    while not a.over and step < 300:
        step += 1
        # 매 턴 b 를 JSON 으로 내보냈다가 되살린다 (서버와 같다)
        b = TB.TrainerBattle.load(dex, json.loads(json.dumps(b.dump())))
        if a.need_switch:
            act = ("switch", rng.choice(a.valid_switches()))
        elif a.valid_switches() and rng.random() < 0.2:
            act = ("switch", rng.choice(a.valid_switches()))
        else:
            act = ("move", rng.choice([m for m in a.me.moves if a.me.pp.get(m, 0) > 0] or [B.STRUGGLE]))
        ea, eb = a.act(*act), b.act(*act)
        if ea != eb:
            same = False
            print("       %d턴에서 갈라짐\n       %s\n       %s" % (step, texts(ea)[:200], texts(eb)[:200]))
            break
    chk("매 턴 저장·복원한 판과 결과가 같다", same, step)
    chk("판이 끝났다", a.over, a.result)
    chk("view 가 JSON 으로 나간다", bool(json.dumps(b.view(), ensure_ascii=False)))


# ---------------------------------------------------------------- 3. 교체 규칙
def t_교체_규칙(dex, gyms):
    print("-- 교체와 강제 교체")
    t = dict(next(x for x in gyms["trainers"] if x["level"] == 100))
    weak = [mon(dex, "MAGIKARP", 5, seed=i, moves=["SPLASH"]) for i in range(3)]
    tb = TB.TrainerBattle(dex, weak, t, random.Random(1))
    tb.start()
    for _ in range(10):
        if tb.need_switch or tb.over:
            break
        tb.act("move", "SPLASH")
    chk("내가 쓰러지면 교체를 묻는다", tb.need_switch, (tb.need_switch, tb.over))
    try:
        tb.act("move", "SPLASH")
        chk("교체해야 할 때 기술은 안 받는다", False)
    except ValueError:
        chk("교체해야 할 때 기술은 안 받는다", True)
    fainted = [i for i, f in enumerate(tb.me_team) if not f.alive()]
    try:
        tb.act("switch", fainted[0])
        chk("쓰러진 포켓몬으로는 못 바꾼다", False)
    except ValueError:
        chk("쓰러진 포켓몬으로는 못 바꾼다", True)
    ev = tb.act("switch", tb.valid_switches()[0])
    chk("살아 있는 포켓몬으로 바꾼다", any(e["t"] == "switch" for e in ev), texts(ev))
    tb2 = TB.TrainerBattle(dex, weak, t, random.Random(1))
    tb2.start()
    ev = tb2.act("forfeit")
    chk("기권하면 끝난다", tb2.over and tb2.result == "forfeit", tb2.result)
    v = TB.TrainerBattle(dex, weak, t, random.Random(1)).view()
    hidden = sum(1 for x in v["foe"]["team"] if x.get("hidden"))
    chk("안 나온 상대 포켓몬은 가린다", hidden == 5, hidden)
    shown = v["foe"]["team"][0]
    chk("상대 특성은 드러나기 전까지 안 보인다", "ability" not in shown or shown.get("ability") is None, shown)


# ---------------------------------------------------------------- 4. 특성
def t_특성(dex):
    print("-- 특성")
    # 위협
    bt, me, foe = duel(dex, mon(dex, "GYARADOS", 50, "INTIMIDATE", ["WATERFALL"]),
                       mon(dex, "MACHAMP", 50, "GUTS", ["CROSSCHOP"]))
    ev = []
    A.on_switch_in(bt, me, "me", ev)
    chk("위협 - 상대 공격이 1 떨어진다", foe.stages["atk"] == -1, texts(ev))
    bt, me, foe = duel(dex, mon(dex, "GYARADOS", 50, "INTIMIDATE", ["WATERFALL"]),
                       mon(dex, "METAGROSS", 50, "CLEARBODY", ["METEORMASH"]))
    ev = []
    A.on_switch_in(bt, me, "me", ev)
    chk("클리어바디 - 위협을 막는다", foe.stages["atk"] == 0, texts(ev))

    # 부유: 지진이 안 맞는다
    bt, me, foe = duel(dex, mon(dex, "GARCHOMP", 60, "ROUGHSKIN", ["EARTHQUAKE"]),
                       mon(dex, "WEEZING", 60, "LEVITATE", ["SLUDGEBOMB"]))
    hp = foe.hp
    ev = []
    bt._use("me", me, foe, "EARTHQUAKE", ev)
    chk("부유 - 땅 기술이 안 맞는다", foe.hp == hp, texts(ev))
    bt, me, foe = duel(dex, mon(dex, "EXCADRILL", 60, "MOLDBREAKER", ["EARTHQUAKE"]),
                       mon(dex, "WEEZING", 60, "LEVITATE", ["SLUDGEBOMB"]))
    ev = []
    bt._use("me", me, foe, "EARTHQUAKE", ev)
    chk("틀깨기 - 부유를 무시하고 맞힌다", foe.hp < foe.maxhp, texts(ev))

    # 저수: 물 기술로 회복
    bt, me, foe = duel(dex, mon(dex, "BLASTOISE", 60, "TORRENT", ["SURF"]),
                       mon(dex, "LAPRAS", 60, "WATERABSORB", ["ICEBEAM"]))
    foe.hp = foe.maxhp // 2
    ev = []
    bt._use("me", me, foe, "SURF", ev)
    chk("저수 - 물 기술을 맞으면 회복한다", foe.hp > foe.maxhp // 2, texts(ev))
    bt, me, foe = duel(dex, mon(dex, "BLASTOISE", 60, "TORRENT", ["SURF", "BITE"]),
                       mon(dex, "LAPRAS", 60, "WATERABSORB", ["ICEBEAM"]))
    picks = set()
    for s in range(40):
        bt.rng = random.Random(s)
        picks.add(bt.choose_for(me, foe, "trainer"))
    # AI 는 15% 는 일부러 아무거나 고른다. 그래도 거의 물기를 골라야 한다.
    chk("AI 는 저수에 물 기술을 안 쓴다 (고른 것에 물기가 있다)", "BITE" in picks, picks)
    surf = sum(1 for s in range(200) if (setattr(bt, "rng", random.Random(s)) or bt.choose_for(me, foe, "trainer")) == "SURF")
    chk("AI 는 저수에 물 기술을 거의 안 쓴다", surf < 40, surf)

    # 옹골참
    bt, me, foe = duel(dex, mon(dex, "GARCHOMP", 100, "ROUGHSKIN", ["EARTHQUAKE"]),
                       mon(dex, "GEODUDE", 5, "STURDY", ["TACKLE"]))
    ev = []
    bt._use("me", me, foe, "EARTHQUAKE", ev)
    chk("옹골참 - 체력이 가득하면 한 방에 안 쓰러진다", foe.hp == 1, (foe.hp, texts(ev)))

    # 천하장사: 공격 실수치가 두 배
    a = B.Fighter(dex, mon(dex, "AZUMARILL", 50, "HUGEPOWER"))
    b = B.Fighter(dex, mon(dex, "AZUMARILL", 50, "HUGEPOWER"))
    b.ability_on = True
    chk("천하장사 - 공격이 두 배", b.stat("atk") == 2 * a.stat("atk"), (a.stat("atk"), b.stat("atk")))

    # 불가사의부적: 효과가 굉장하지 않으면 안 맞는다
    bt, me, foe = duel(dex, mon(dex, "MACHAMP", 60, "GUTS", ["CROSSCHOP", "ROCKSLIDE"]),
                       mon(dex, "SHEDINJA", 30, "WONDERGUARD", ["SHADOWSNEAK"]))
    ev = []
    bt._use("me", me, foe, "CROSSCHOP", ev)
    chk("불가사의부적 - 격투는 고스트에게 안 들어간다", foe.alive(), texts(ev))
    ev = []
    bt._use("me", me, foe, "ROCKSLIDE", ev)
    chk("불가사의부적 - 바위(효과 굉장)는 맞는다", not foe.alive(), texts(ev))

    # 타오르는불꽃
    bt, me, foe = duel(dex, mon(dex, "ARCANINE", 60, "INTIMIDATE", ["FLAMETHROWER"]),
                       mon(dex, "HEATRAN", 60, "FLASHFIRE", ["FLAMETHROWER"]))
    ev = []
    bt._use("me", me, foe, "FLAMETHROWER", ev)
    chk("타오르는불꽃 - 불꽃 기술이 안 들고 켜진다", foe.hp == foe.maxhp and foe.ab.get("flash"), texts(ev))

    # 가속
    bt, me, foe = duel(dex, mon(dex, "NINJASK", 40, "SPEEDBOOST", ["XSCISSOR"]),
                       mon(dex, "SNORLAX", 40, "THICKFAT", ["BODYSLAM"]))
    ev = []
    bt._end_of_turn(ev)
    chk("가속 - 턴이 끝나면 스피드가 오른다", me.stages["spe"] == 1, texts(ev))

    # 포이즌힐 / 매직가드
    bt, me, foe = duel(dex, mon(dex, "GLISCOR", 50, "POISONHEAL", ["EARTHQUAKE"]),
                       mon(dex, "CLEFABLE", 50, "MAGICGUARD", ["MOONBLAST"]))
    me.status, foe.status = "poison", "burn"
    me.hp = me.maxhp // 2
    h1, h2 = me.hp, foe.hp
    ev = []
    bt._end_of_turn(ev)
    chk("포이즌힐 - 독이면 회복한다", me.hp > h1, texts(ev))
    chk("매직가드 - 화상 데미지를 안 받는다", foe.hp == h2, texts(ev))

    # 적응력 / 테크니션: 같은 시드로 켠 판이 더 아프다
    def dmg(sp, ab, move, target="SNORLAX"):
        out = []
        for on in (False, True):
            bt, me, foe = duel(dex, mon(dex, sp, 50, ab, [move]), mon(dex, target, 50, "IMMUNITY"),
                               seed=5, on=on)
            d, _c, _e = B.damage(dex, dex.move(move), me, foe, B.EST_RNG, crit=False)
            out.append(d)
        return out
    off, on = dmg("PORYGONZ", "ADAPTABILITY", "TRIATTACK")
    chk("적응력 - 자속 1.5 -> 2.0", on > off * 1.25, (off, on))
    off, on = dmg("SCIZOR", "TECHNICIAN", "BULLETPUNCH")
    chk("테크니션 - 위력 60 이하 1.5배", on > off * 1.4, (off, on))
    off, on = dmg("SNORLAX", "THICKFAT", "FLAMETHROWER", target="SNORLAX")
    bt, me, foe = duel(dex, mon(dex, "CHARIZARD", 50, "BLAZE", ["FLAMETHROWER"]),
                       mon(dex, "SNORLAX", 50, "THICKFAT"), on=True)
    d_on, _c, _e = B.damage(dex, dex.move("FLAMETHROWER"), me, foe, B.EST_RNG, crit=False)
    bt2, me2, foe2 = duel(dex, mon(dex, "CHARIZARD", 50, "BLAZE", ["FLAMETHROWER"]),
                          mon(dex, "SNORLAX", 50, "THICKFAT"), on=False)
    d_off, _c, _e = B.damage(dex, dex.move("FLAMETHROWER"), me2, foe2, B.EST_RNG, crit=False)
    chk("두꺼운지방 - 불꽃이 반감", d_on <= d_off * 0.55, (d_off, d_on))

    # 자기과신
    bt, me, foe = duel(dex, mon(dex, "SALAMENCE", 100, "MOXIE", ["DRAGONCLAW"]),
                       mon(dex, "MAGIKARP", 5, "SWIFTSWIM", ["SPLASH"]))
    ev = []
    bt._use("me", me, foe, "DRAGONCLAW", ev)
    chk("자기과신 - 쓰러뜨리면 공격이 오른다", me.stages["atk"] == 1, texts(ev))

    # 정전기 (30% - 여러 번 굴린다)
    got = False
    for s in range(60):
        bt, me, foe = duel(dex, mon(dex, "SNORLAX", 50, "THICKFAT", ["TACKLE"]),
                           mon(dex, "PIKACHU", 80, "STATIC", ["THUNDERBOLT"]), seed=s)
        ev = []
        bt._use("me", me, foe, "TACKLE", ev)
        if me.status == "paralysis":
            got = True
            break
    chk("정전기 - 접촉하면 가끔 마비된다", got)

    # 변환자재
    bt, me, foe = duel(dex, mon(dex, "GRENINJA", 60, "PROTEAN", ["DARKPULSE"]),
                       mon(dex, "SNORLAX", 60, "THICKFAT", ["BODYSLAM"]))
    ev = []
    bt._use("me", me, foe, "DARKPULSE", ev)
    chk("변환자재 - 쓰는 기술의 타입이 된다", me.types() == ["DARK"], (me.types(), texts(ev)))

    # 심술꾸러기: 리프스톰이 특공을 올린다
    bt, me, foe = duel(dex, mon(dex, "SERPERIOR", 60, "CONTRARY", ["LEAFSTORM"]),
                       mon(dex, "SNORLAX", 60, "THICKFAT", ["BODYSLAM"]))
    ev = []
    bt._use("me", me, foe, "LEAFSTORM", ev)
    chk("심술꾸러기 - 떨어질 능력이 오른다", me.stages["spa"] > 0, (me.stages, texts(ev)))

    # 불면: 잠들지 않는다
    bt, me, foe = duel(dex, mon(dex, "BRELOOM", 60, "EFFECTSPORE", ["SPORE"]),
                       mon(dex, "HONCHKROW", 60, "INSOMNIA", ["NIGHTSLASH"]))
    ev = []
    bt._use("me", me, foe, "SPORE", ev)
    chk("불면 - 잠들지 않는다", foe.status is None, texts(ev))

    # 끄면 아무것도 안 한다
    bt, me, foe = duel(dex, mon(dex, "GARCHOMP", 60, "ROUGHSKIN", ["EARTHQUAKE"]),
                       mon(dex, "WEEZING", 60, "LEVITATE", ["SLUDGEBOMB"]), on=False)
    ev = []
    bt._use("me", me, foe, "EARTHQUAKE", ev)
    chk("특성을 끈 판에서는 부유가 없다", foe.hp < foe.maxhp, texts(ev))


def t_로스터(dex, gyms):
    print("-- 로스터가 엔진에 맞는다")
    bad = []
    unknown_ab = {}
    for t in gyms["trainers"]:
        for m in t["team"]:
            if not dex.get(m["species"]):
                bad.append((t["name"], m["species"]))
            for mv in m["moves"]:
                if not dex.move(mv):
                    bad.append((t["name"], mv))
            ab = m.get("ability")
            if ab and ab not in A.IMPLEMENTED:
                unknown_ab[ab] = unknown_ab.get(ab, 0) + 1
    chk("모든 종·기술이 도감에 있다", not bad, bad[:5])
    total = sum(len(t["team"]) for t in gyms["trainers"])
    no_effect = sum(unknown_ab.values())
    print("       특성 %d칸 중 효과 있는 것 %d칸 (%.0f%%). 효과 없는 흔한 것: %s"
          % (total, total - no_effect, 100.0 * (total - no_effect) / total,
             sorted(unknown_ab.items(), key=lambda x: -x[1])[:8]))
    chk("대부분의 특성이 뭔가 한다", (total - no_effect) >= total * 0.5, (total, no_effect))

    # 관장은 타입 전문가다. 담죽(얼음)이 포켓우드 영화 배역 팀(악 타입)을 들고
    # 나온 적이 있다 - 문서의 '영화 촬영' 표가 레벨이 높아 본래 팀을 밀어냈다.
    off = []
    for t in gyms["trainers"]:
        if t["role"] != "관장" or t["id"] == "easter-egg" or not t.get("type"):
            continue
        n = sum(1 for m in t["team"] if t["type"] in (dex.get(m["species"]) or {}).get("types", []))
        if n < 3:
            off.append((t["name"], t["type"], [m["species"] for m in t["team"]]))
    chk("관장은 자기 타입을 셋 이상 데리고 있다", not off, off[:3])
    six = [t["name"] for t in gyms["trainers"] if len(t["team"]) != 6]
    chk("모두 여섯 마리", not six, six[:5])

    # 능력치 배율: 이스터에그 렌트라는 전설 평균만큼, 지우의 마임맨·따라큐는 조금
    egg = next(t for t in gyms["trainers"] if t["id"] == "easter-egg")
    tb = TB.TrainerBattle(dex, [mon(dex, "PIKACHU", 50, "STATIC", ["THUNDERBOLT"])], egg, random.Random(1))
    lux = tb.foe_team[-1]
    legends = [sum(f.base.values()) for f in tb.foe_team[:-1]]
    chk("이스터에그 에이스는 렌트라", lux.mon["species"] == "LUXRAY", lux.mon["species"])
    chk("렌트라 능력치 합계가 전설 평균 ±2%", abs(sum(lux.base.values()) - sum(legends) / 5.0) <= sum(legends) / 5.0 * 0.02,
        (sum(lux.base.values()), sum(legends) / 5.0))
    tb.start()
    back = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("배율은 저장했다 되살려도 남는다", back.foe_team[-1].base == lux.base, back.foe_team[-1].base)
    plain = B.Fighter(dex, dict(TB.trainer_mon(egg["team"][-1]), statBoost=None))
    chk("배율이 없으면 원래 능력치", sum(plain.base.values()) < sum(lux.base.values()) * 0.85,
        (sum(plain.base.values()), sum(lux.base.values())))
    ash = next(t for t in gyms["trainers"] if t["id"] == "ash-ketchum")
    chk("지우 팀", [m["species"] for m in ash["team"]] ==
        ["MEOWSCARADA", "ALAKAZAM", "MRMIME", "GENGAR", "DRIFBLIM", "MIMIKYU"], [m["species"] for m in ash["team"]])
    chk("지우: 종족값 낮은 둘만 조금 올렸다", {m["species"]: m.get("boost") for m in ash["team"] if m.get("boost")}
        == {"MRMIME": 1.07, "MIMIKYU": 1.08})
    boosted = [t["name"] for t in gyms["trainers"] if t["id"] not in ("easter-egg", "ash-ketchum")
               and any(m.get("boost") for m in t["team"])]
    chk("다른 트레이너에게는 배율이 없다", not boosted, boosted)


# ---------------------------------------------------------------- 5. 상대 AI
def gym(level, *team):
    """(종, 레벨, 기술, 특성) 들로 트레이너 하나."""
    return {"id": "t", "name": "시험", "role": "관장", "sprite": "t", "level": level,
            "team": [{"species": sp, "level": lv, "moves": mv, "ability": ab, "held": None,
                      "iv": 31, "evs": {}, "nature": "HARDY", "gender": "M"}
                     for sp, lv, mv, ab in team]}


def ai_battle(dex, trainer, mine, seed=1):
    tb = TB.TrainerBattle(dex, mine, trainer, random.Random(seed))
    tb.start()
    return tb


def picks(tb, n=40):
    out = collections.Counter()
    for s in range(n):
        tb.rng = random.Random(s)
        out[tb._foe_move()] += 1
    return out


def t_상대_AI(dex, gyms):
    print("-- 상대 AI")
    # 먼저 쓰러뜨릴 수 있으면 끝낸다 (칼춤을 안 춘다)
    tb = ai_battle(dex, gym(100, ("GARCHOMP", 60, ["SWORDSDANCE", "DRAGONCLAW", "EARTHQUAKE"], "ROUGHSKIN")),
                   [mon(dex, "HEATRAN", 60, "FLASHFIRE", ["FLAMETHROWER"])])
    got = picks(tb)
    chk("한 방에 끝낼 수 있으면 그 기술 (지진 -> 히드런)", got["EARTHQUAKE"] == 40, got)

    # 먼저 맞고 쓰러질 판이면 선공기
    tb = ai_battle(dex, gym(100, ("SCIZOR", 50, ["XSCISSOR", "BULLETPUNCH", "SWORDSDANCE"], "TECHNICIAN")),
                   [mon(dex, "ARCANINE", 50, "INTIMIDATE", ["FLAMETHROWER"])])
    tb.me.hp = max(1, tb.me.maxhp // 12)
    got = picks(tb)
    chk("느린데 먼저 맞고 쓰러질 판이면 선공기로 끝낸다 (불릿펀치)", got["BULLETPUNCH"] == 40, got)

    # 걸리지 않을 상태이상은 안 건다
    t = gym(100, ("SABLEYE", 50, ["WILLOWISP", "SHADOWSNEAK"], "KEENEYE"))
    got = picks(ai_battle(dex, t, [mon(dex, "ARCANINE", 50, "INTIMIDATE", ["BITE"])]))
    chk("불꽃 타입에게 도깨비불을 안 쓴다", not got["WILLOWISP"], got)
    tb = ai_battle(dex, t, [mon(dex, "MACHAMP", 50, "GUTS", ["CROSSCHOP"])])
    got = picks(tb)
    chk("물리형 격투에게는 도깨비불", got.most_common(1)[0][0] == "WILLOWISP", got)
    tb.me.status = "paralysis"
    got = picks(tb)
    chk("이미 상태이상이면 도깨비불을 안 쓴다", not got["WILLOWISP"], got)

    # 랭크업은 안전할 때만, +2 까지만
    t = gym(100, ("GARCHOMP", 60, ["SWORDSDANCE", "DRAGONCLAW"], "ROUGHSKIN"))
    tb = ai_battle(dex, t, [mon(dex, "BLISSEY", 60, "NATURALCURE", ["POUND"])])
    chk("아프게 못 때리는 상대 앞에서는 칼춤", picks(tb).most_common(1)[0][0] == "SWORDSDANCE", picks(tb))
    tb.foe.stages["atk"] = 2
    got = picks(tb)
    chk("+2 가 되면 더 안 쌓고 때린다", not got["SWORDSDANCE"], got)
    tb = ai_battle(dex, t, [mon(dex, "MAMOSWINE", 60, "OBLIVIOUS", ["ICICLECRASH"])])
    got = picks(tb)
    chk("한 방에 쓰러질 상대 앞에서는 칼춤을 안 춘다", not got["SWORDSDANCE"], got)

    # 회복은 깎였을 때만
    t = gym(100, ("SLOWBRO", 60, ["SLACKOFF", "PSYCHIC"], "OWNTEMPO"))
    tb = ai_battle(dex, t, [mon(dex, "BLISSEY", 60, "NATURALCURE", ["POUND"])])
    chk("체력이 가득하면 회복기를 안 쓴다", not picks(tb)["SLACKOFF"], picks(tb))
    tb.foe.hp = tb.foe.maxhp * 3 // 10
    chk("깎였고 회복이 맞는 양보다 크면 회복기", picks(tb).most_common(1)[0][0] == "SLACKOFF", picks(tb))
    tb.me.moves, tb.me.pp = ["DOUBLEEDGE"], {"DOUBLEEDGE": 15}
    tb.me.stages["atk"] = 6
    got = picks(tb)
    chk("회복해도 그만큼 다시 맞으면 회복기를 안 쓴다", not got["SLACKOFF"], got)

    # 교체: 이번 턴에 쓰러질 판이면 버티는 포켓몬으로. 레벨이 높을수록 잘 한다.
    def switch_rate(level):
        n = 0
        for s in range(60):
            tb = ai_battle(dex, gym(level, ("GARCHOMP", 60, ["DRAGONCLAW", "EARTHQUAKE"], "ROUGHSKIN"),
                                    ("METAGROSS", 60, ["METEORMASH", "ZENHEADBUTT"], "CLEARBODY")),
                           [mon(dex, "WEAVILE", 62, "PRESSURE", ["ICEPUNCH"])], seed=s)
            n += tb._foe_wants_switch() == 1
        return n / 60.0
    hi, lo = switch_rate(100), switch_rate(20)
    chk("Lv.100 트레이너는 쓰러질 판에서 거의 바꾼다 (얼음 -> 메타그로스)", hi >= 0.75, hi)
    chk("Lv.20 트레이너는 덜 바꾼다", lo < hi and lo >= 0.2, (lo, hi))
    t = gym(100, ("GARCHOMP", 60, ["DRAGONCLAW", "EARTHQUAKE"], "ROUGHSKIN"),
            ("METAGROSS", 60, ["METEORMASH", "ZENHEADBUTT"], "CLEARBODY"))
    kept = [ai_battle(dex, t, [mon(dex, "HEATRAN", 60, "FLASHFIRE", ["FLAMETHROWER"])], seed=s)._foe_wants_switch()
            for s in range(20)]
    chk("유리한 판(지진으로 먼저 끝낸다)에서는 안 바꾼다", kept == [None] * 20, kept)

    # 쓰러진 뒤에는 상대에게 강한 포켓몬
    tb = ai_battle(dex, gym(100, ("PIKACHU", 30, ["THUNDERBOLT"], "STATIC"),
                            ("RATICATE", 60, ["HYPERFANG"], "GUTS"),
                            ("LAPRAS", 60, ["ICEBEAM", "SURF"], "WATERABSORB"),
                            ("SNORLAX", 60, ["BODYSLAM"], "THICKFAT")),
                   [mon(dex, "GARCHOMP", 60, "ROUGHSKIN", ["EARTHQUAKE", "DRAGONCLAW"])])
    chk("쓰러지면 상대(한카리아스)에게 강한 라프라스를 낸다", tb._pick(tb.foe_team, tb.me) == 2,
        tb._pick(tb.foe_team, tb.me))

    # 실수: Lv.100 은 안 하고 Lv.20 은 가끔
    def second_rate(level):
        tb = ai_battle(dex, gym(level, ("MACHAMP", 60, ["CROSSCHOP", "KNOCKOFF"], "GUTS")),
                       [mon(dex, "SNORLAX", 60, "THICKFAT", ["BODYSLAM"])])
        return picks(tb, 400)["KNOCKOFF"] / 400.0
    chk("Lv.100 은 더 약한 기술을 안 고른다", second_rate(100) == 0, second_rate(100))
    chk("Lv.20 은 가끔(10% 안팎) 두 번째 기술", 0.04 <= second_rate(20) <= 0.16, second_rate(20))

    # 자료
    chk("관장 AI 가 쓸 수 있는 기술을 가려낸다 (1:1 에서 실패하는 것·AI 가 쓸 일 없는 것은 뺀다)",
        [TB.works(dex.move(k)) for k in ("HELPINGHAND", "SPLASH", "INSTRUCT", "SKETCH",
                                         "SWORDSDANCE", "WILLOWISP", "GROWL", "RECOVER",
                                         "HEAVYSLAM", "NIGHTSHADE", "LEECHSEED", "COUNTER",
                                         "PROTECT", "SUBSTITUTE", "RAINDANCE", "STEALTHROCK")]
        == [False, False, False, False] + [True] * 12)
    dead = [(t["name"], m["species"], k) for t in gyms["trainers"] for m in t["team"]
            for k in m["moves"] if not TB.works(dex.move(k))]
    chk("관장 포켓몬에 헛기술이 없다", not dead, dead[:5])
    nohit = [(t["name"], m["species"]) for t in gyms["trainers"] for m in t["team"]
             if not any((dex.move(k) or {}).get("power") for k in m["moves"])]
    chk("모두 때리는 기술이 있다", not nohit, nohit[:5])
    chk("개체값은 모두 31", all(m["iv"] == 31 for t in gyms["trainers"] for m in t["team"]))
    # 시즌 챔피언 관장(2.0.3 WhiteSna)은 신청서 그대로라 노력치도 그 사람 것 (252/252) - 합만 본가 상한 안
    made = [t for t in gyms["trainers"] if t.get("role") != "시즌 챔피언"]
    lo20 = [sum(m["evs"].values()) for t in made if t["level"] == 20 for m in t["team"]]
    hi100 = [sum(m["evs"].values()) for t in made if t["level"] == 100 for m in t["team"]]
    chk("노력치: Lv.20 은 0, Lv.100 은 절반쯤", max(lo20) == 0 and 240 <= min(hi100) and max(hi100) <= 256,
        (max(lo20), min(hi100), max(hi100)))
    champ = [sum(m["evs"].values()) for t in gyms["trainers"] if t.get("role") == "시즌 챔피언" for m in t["team"]]
    chk("  시즌 챔피언 관장의 노력치 합은 510 이하", all(n <= 510 for n in champ), champ)
    natures = collections.Counter(m["nature"] for t in gyms["trainers"] for m in t["team"])
    chk("성격을 포켓몬에 맞춘다 (무보정 없음)", "HARDY" not in natures and len(natures) >= 4, natures)
    f = TB.trainer_mon({"species": "PIKACHU", "level": 50, "iv": 31, "evs": {"spe": 126, "spa": 126}})
    chk("능력마다 따로 적은 노력치를 읽는다", f["evs"]["spe"] == 126 and f["evs"]["atk"] == 0, f["evs"])
    f = TB.trainer_mon({"species": "PIKACHU", "level": 50, "iv": 20, "ev": 40})
    chk("예전 자료(숫자 하나)도 읽는다", f["evs"]["hp"] == 40 and f["ivs"]["spe"] == 20, f)


def t_길드전_방어_AI(dex, gyms):
    """길드전 (시즌 4): 사람이 짠 방어팀(이미 mon 인 것)을 센 AI(ai="war")가 굴린다."""
    print("\n=== 길드전 방어 AI ===")
    import time
    full = mon(dex, "GARCHOMP", 50, seed=3, iv=31)
    full["ivs"]["spe"] = 7
    got = TB.trainer_mon(full)
    chk("이미 mon 인 것은 그대로 쓴다 (개체값을 능력마다 그대로)", got["ivs"]["spe"] == 7 and got["moves"] == full["moves"]
        and got["happiness"] == full.get("happiness", 255), (got["ivs"], got.get("happiness")))
    team = [TB.trainer_mon(dict(e, level=50, iv=31)) for e in gyms["trainers"][-1]["team"]]
    tr = {"id": "gw:c01", "name": "AI 수비대", "role": "[로켓단]", "level": 50, "team": team, "noMega": True,
          "ai": "war", "keystone": True, "zring": True}
    mine = [TB.trainer_mon(dict(e, level=50, iv=31)) for e in gyms["trainers"][-2]["team"]]
    tb = TB.TrainerBattle(dex, mine, tr, random.Random(5))
    chk("키스톤·Z링을 쓰고, Z기술을 알아서 쓴다", tb.war and tb.keystone["foe"] and tb.zring["foe"]
        and tb.bt.auto_z["foe"])
    chk("실수하지 않고, 불리하면 늘 바꾼다", tb.mistake() == 0.0 and tb.smartness() == 1.0)
    tb.start()
    spent, turns = [], 0
    while not tb.over and turns < 200:
        if tb.need_switch:
            tb.act("switch", tb.valid_switches()[0])
        else:
            _d, k = tb._best(tb.me, tb.foe)
            t0 = time.time()
            try:
                tb.act("move", k or tb.bt.usable(tb.me)[0])
            except ValueError:
                tb.act("move", tb.bt.usable(tb.me)[0])
            spent.append(time.time() - t0)
        if turns == 3:
            tb = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
        turns += 1
    chk("끝까지 돈다 (턴마다 저장했다 되살려도 길드전 AI 그대로)", tb.over and tb.war, (tb.over, turns))
    limit = TB.TrainerBattle.WAR2_EMERGENCY if TB.TrainerBattle.WAR_V2 else TB.TrainerBattle.WAR_BUDGET
    chk("한 턴의 셈은 시간 상한 안 (%.0fms)" % (1000 * max(spent)), max(spent) < limit + 0.5, max(spent))
    gym_tb = TB.TrainerBattle(dex, mine, dict(tr, ai=None, zring=None), random.Random(5))
    chk("ai 가 없는 판은 그대로 (길드전 AI 가 아니고 셈하지 않는다)",
        not gym_tb.war and not gym_tb.searches and not gym_tb.bt.auto_z["foe"])
    chk("  Z링을 가진 관장(시즌 챔피언)은 Z기술을 알아서 쓴다",
        TB.TrainerBattle(dex, mine, dict(tr, ai=None), random.Random(5)).bt.auto_z["foe"])


def war_tb(dex, foe_mons, me_mons, seed=1):
    """길드전 판 (ai="war"). foe_mons 는 AI(방어) 쪽, me_mons 는 사람(공격) 쪽."""
    tr = {"id": "gw:t", "name": "AI", "role": "[t]", "level": 50, "team": [TB.trainer_mon(m) for m in foe_mons],
          "noMega": True, "ai": "war", "keystone": True, "zring": True}
    tb = TB.TrainerBattle(dex, me_mons, tr, random.Random(seed))
    tb.start()
    return tb


def t_길드전_평가(dex):
    """길드전 방어 AI 의 새 형세 평가 (_eval_v2 · _hazard_toll, 2026-10-22 design-notes).

    옛 _eval 은 깔기를 안 보고 랭크를 ±2 까지 0.05 씩만 쳐서, 스텔스록 · 칼춤이 '이번 턴 데미지를 버린 수' 로만 보였다.
    2026-11-01 부터 끝나지 않은 판은 poke-engine 식(_eval_pe, t_길드전_평가_pe)으로 잰다. 여기는 그것을 끈 식(되돌릴 때 쓰는 식)을 본다.
    """
    old_pe = TB.TrainerBattle.WAR_PE_EVAL
    TB.TrainerBattle.WAR_PE_EVAL = False
    try:
        _길드전_평가_옛(dex)
    finally:
        TB.TrainerBattle.WAR_PE_EVAL = old_pe


def t_길드전_평가_pe(dex):
    """poke-engine 형세 평가 (_eval_pe, WAR_PE_EVAL, 2026-11-01): 값이 evaluate.rs 를 / 100 한 것과 맞는다."""
    print("-- 길드전 방어 AI: poke-engine 형세 평가")
    ai = [mon(dex, "GARCHOMP", 50, "ROUGHSKIN", ["EARTHQUAKE", "DRAGONCLAW", "STEALTHROCK", "SWORDSDANCE"], iv=31)]
    people = [mon(dex, "MACHAMP", 50, "NOGUARD", ["CROSSCHOP", "KNOCKOFF", "BULLETPUNCH", "ICEPUNCH"], iv=31),
              mon(dex, "GYARADOS", 50, iv=31, seed=3)]

    def gain(fn):
        tb = war_tb(dex, ai, people)
        base = tb._eval_v2()
        fn(tb)
        return round(tb._eval_v2() - base, 6)
    chk("AI 의 공격 +2 는 0.60 · +6 은 0.99 (올라갈수록 덜)",
        (gain(lambda tb: tb.foe.stages.__setitem__("atk", 2)), gain(lambda tb: tb.foe.stages.__setitem__("atk", 6)))
        == (0.6, 0.99))
    chk("  방어 +2 는 그 절반 (0.30)", gain(lambda tb: tb.foe.stages.__setitem__("def", 2)) == 0.3)
    chk("AI 의 대타출동은 +0.75", gain(lambda tb: tb.foe.cond.__setitem__("sub", 40)) == 0.75)
    chk("  사람 쪽 혼란은 AI 에게 +0.20", gain(lambda tb: tb.me.cond.__setitem__("confused", 3)) == 0.2)
    chk("  사람 쪽 씨뿌리기는 AI 에게 +0.30", gain(lambda tb: setattr(tb.me, "seeded", True)) == 0.3)
    tb = war_tb(dex, ai, people)
    tb.me_team[1].held = "LEFTOVERS"
    base = tb._eval_v2()
    tb.me_team[1].held = None
    chk("사람 쪽 도구가 없어지면 AI 에게 +0.10 (탁쳐서떨구기)", round(tb._eval_v2() - base, 6) == 0.1,
        tb._eval_v2() - base)
    burn = gain(lambda tb: setattr(tb.me, "status", "burn"))
    chk("물리 공격기 넷인 괴력몬의 화상은 AI 에게 +1.00 (공격기 하나에 0.25)", burn == 1.0, burn)
    chk("  마비는 +0.25", gain(lambda tb: setattr(tb.me, "status", "paralysis")) == 0.25)
    rock = gain(lambda tb: tb.bt.field.side("me").__setitem__("stealthrock", 1))
    chk("사람 진영의 스텔스록은 살아 있는 한 마리에 0.10 (나와 있는 것까지)", rock == 0.2, rock)
    chk("  AI 진영의 리플렉터 5턴은 +1.00", gain(lambda tb: tb.bt.field.side("foe").__setitem__("reflect", 5)) == 1.0)
    tb = war_tb(dex, ai, people)
    tb.me.hp = 1
    tb.me.status = "burn"
    chk("체력 · 상태이상 · 도구 합은 0 밑으로 안 내려간다 (쓰러지기 직전 포켓몬도 살아 있는 값 0.30 은 남는다)",
        tb._pe_side(tb.me_team[:1], tb.me, {}) == 0.3, tb._pe_side(tb.me_team[:1], tb.me, {}))
    tb = war_tb(dex, ai, people)
    tb.over, tb.result, tb.turn = True, "draw", TB.MAX_TURNS
    chk("끝난 판의 값은 그대로 (400턴 무승부 = -100)", tb._eval_v2() == -100.0, tb._eval_v2())


def t_길드전_헛수(dex):
    """헛수 감점 (_wasted, WAR_WASTE_PEN, 2026-11-01): 지금 쓰면 아무 일도 없는 변화기를 짚는다."""
    print("-- 길드전 방어 AI: 헛수")
    ai = [mon(dex, "SKARMORY", 50, "STURDY", ["STEALTHROCK", "ROOST", "PROTECT", "REFLECT"], iv=31),
          mon(dex, "GARCHOMP", 50, "ROUGHSKIN", ["EARTHQUAKE", "DRAGONCLAW", "STEALTHROCK", "SWORDSDANCE"], iv=31)]
    people = [mon(dex, "MACHAMP", 50, "NOGUARD", iv=31), mon(dex, "GYARADOS", 50, iv=31, seed=3),
              mon(dex, "ARCANINE", 50, iv=31, seed=4)]
    tb = war_tb(dex, ai, people)
    chk("스텔스록이 아직 없으면 헛수가 아니다", not tb._wasted("STEALTHROCK"))
    tb.bt.field.side("me")["stealthrock"] = 1
    chk("  이미 깔렸으면 헛수", tb._wasted("STEALTHROCK"))
    chk("체력이 가득한데 날개쉬기는 헛수", tb._wasted("ROOST"))
    tb.foe.hp = tb.foe.maxhp // 2
    chk("  반쯤 깎였으면 헛수가 아니다", not tb._wasted("ROOST"))
    tb.foe.hp = tb.foe.maxhp            # 반 남은 무장조는 괴력몬 한 방에 가까워 관장 AI 가 벽을 '소용없다' 고 본다
    chk("리플렉터가 없으면 헛수가 아니다", not tb._wasted("REFLECT"))
    tb.bt.field.side("foe")["reflect"] = 3
    chk("  이미 세웠으면 헛수", tb._wasted("REFLECT"))
    tb.foe.cond["streak"] = 1
    chk("방어를 연달아 쓰면 헛수", tb._wasted("PROTECT"))
    chk("공격 기술은 여기서 안 본다 (_no_effect 가 본다)", not tb._wasted("EARTHQUAKE"))
    tb = war_tb(dex, ai[1:], people)
    tb.foe.stages["atk"] = 6
    chk("공격이 +6 인데 칼춤은 헛수", tb._wasted("SWORDSDANCE"))
    chk("길드전에서도 무효 공격 감점이 켜져 있다 (WAR_NOEFFECT_PEN)", TB.TrainerBattle.WAR_NOEFFECT_PEN > 0)

    # 스스로 바꿔 넣은 포켓몬도 '막 낸 포켓몬' 이다 (다음 턴에 또 바꾸면 WAR2_REENTRY_PEN)
    tb = war_tb(dex, ai, people)
    real = TB.TrainerBattle._war_search
    TB.TrainerBattle._war_search = lambda self, plain: ("switch", 1)
    try:
        tb.act("move", tb.bt.usable(tb.me)[0])
    finally:
        TB.TrainerBattle._war_search = real
    chk("AI 가 스스로 바꾸면 그 턴이 war_sent 에 남는다", tb.war_sent == tb.turn and tb.fi == 1, (tb.war_sent, tb.turn, tb.fi))
    chk("  물러난 자리(0)도 war_left 에 남는다 (A -> B -> A 감점)", tb.war_left == {"0": tb.turn}, tb.war_left)
    back = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("  dump -> load 해도 남는다", back.war_left == tb.war_left and back.war_sent == tb.war_sent,
        (back.war_left, back.war_sent))


def t_관장_AI(dex, gyms):
    """관장 (ai="gym", 2026-11-02): 길드전 방어 AI 의 셈을 얕게 쓴다. 레벨이 낮으면 가끔 셈 없이 (_gym_slip)."""
    print("\n=== 관장 AI (셈하는 관장) ===")
    import time
    by_lv = dict((t["level"], t) for t in gyms["trainers"] if t.get("role") != "시즌 챔피언")
    hi, lo = by_lv[max(by_lv)], by_lv[min(by_lv)]
    mine = [TB.trainer_mon(dict(e, level=50, iv=31)) for e in gyms["trainers"][-2]["team"]]
    tb = TB.TrainerBattle(dex, mine, dict(hi, ai="gym"), random.Random(3))
    chk("관장 판은 셈하지만 길드전 AI 는 아니다", tb.searches and not tb.war)
    chk("  셈은 얕게 (깊이 1 · 시드 1 · 한 수 0.5초 상한)",
        (tb.WAR2_DEPTH, tb.WAR2_SEEDS, tb.WAR2_EMERGENCY) == (1, 1, 0.5)
        and TB.TrainerBattle.WAR2_DEPTH == 2, (tb.WAR2_DEPTH, tb.WAR2_SEEDS, tb.WAR2_EMERGENCY))
    back = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("  dump -> load 해도 셈하는 관장 그대로", back.searches and not back.war and back.WAR2_DEPTH == 1)
    rnd = random.Random(1)

    def slips(t, n=4000):
        b = TB.TrainerBattle(dex, mine, dict(t, ai="gym"), random.Random(1))
        b.rng = rnd
        return sum(1 for _ in range(n) if b._gym_slip()) / float(n)
    s_lo, s_hi = slips(lo), slips(hi)
    chk("Lv.%d 관장은 10%% 쯤 셈 없이 두고, Lv.%d 는 늘 셈한다" % (lo["level"], hi["level"]),
        0.08 <= s_lo <= 0.12 and s_hi == 0.0, (s_lo, s_hi))
    chk("  불리할 때 바꾸는 확률은 관장 그대로 (레벨이 낮으면 덜 바꾼다)",
        TB.TrainerBattle(dex, mine, dict(lo, ai="gym"), random.Random(1)).smartness() < 1.0)

    calls = []
    real = TB.TrainerBattle._war_choice

    def spy(self):
        calls.append(1)
        return real(self)
    TB.TrainerBattle._war_choice = spy
    spent = []
    try:
        tb.start()
        guard = 0
        while not tb.over and guard < 200:
            guard += 1
            if tb.need_switch:
                tb.act("switch", tb.valid_switches()[0])
                continue
            _d, k = tb._best(tb.me, tb.foe)
            t0 = time.time()
            try:
                tb.act("move", k or tb.bt.usable(tb.me)[0])
            except ValueError:
                tb.act("move", tb.bt.usable(tb.me)[0])
            spent.append(time.time() - t0)
    finally:
        TB.TrainerBattle._war_choice = real
    chk("Lv.%d 관장과 끝까지 돈다 · 턴마다 셈한다" % hi["level"], tb.over and len(calls) >= len(spent) - 1,
        (tb.over, len(calls), len(spent)))
    chk("  한 턴은 셈 상한 안 (%.0fms)" % (1000 * max(spent)), max(spent) < 0.5 + 0.5, max(spent))


def _길드전_평가_옛(dex):
    print("-- 길드전 방어 AI: 새 형세 평가 (WAR_PE_EVAL 을 끈 식)")
    ai = [mon(dex, "GARCHOMP", 50, "ROUGHSKIN", ["EARTHQUAKE", "DRAGONCLAW", "STEALTHROCK", "SWORDSDANCE"], iv=31)]

    def bench(n):
        names = ["MACHAMP", "GYARADOS", "ARCANINE", "TYRANITAR", "SCIZOR", "VENUSAUR"]
        return [mon(dex, names[i], 50, iv=31, seed=i + 2) for i in range(n)]

    def rock_gain(n):
        tb = war_tb(dex, ai, bench(n))
        base = tb._eval_v2()
        tb.bt.field.side("me")["stealthrock"] = 1
        return tb._eval_v2() - base
    g6, g2 = rock_gain(6), rock_gain(2)
    chk("사람 진영의 스텔스록은 남은(안 나온) 포켓몬이 많을수록 값이 크다", g6 > g2 > 0, (g6, g2))

    def toll(bench_mon, hazard, layers=1):
        tb = war_tb(dex, ai, [mon(dex, "MACHAMP", 50, iv=31), bench_mon])
        tb.bt.field.side("me")[hazard] = layers
        return tb._hazard_toll("me")
    chk("  통굽부츠를 지닌 포켓몬은 안 친다",
        toll(mon(dex, "ARCANINE", 50, iv=31, held="HEAVYDUTYBOOTS"), "stealthrock") == 0, None)
    chk("  매직가드는 안 친다", toll(mon(dex, "CLEFABLE", 50, "MAGICGUARD", iv=31), "stealthrock") == 0)
    pid = mon(dex, "PIDGEOT", 50, "KEENEYE", iv=31)
    chk("  비행 타입은 압정을 안 밟는다 (스텔스록은 맞는다)", toll(pid, "spikes") == 0 and toll(pid, "stealthrock") > 0,
        (toll(pid, "spikes"), toll(pid, "stealthrock")))
    chk("  독 타입은 독압정을 흡수한다", toll(mon(dex, "MUK", 50, "STENCH", iv=31), "toxicspikes") == 0)
    chk("  나와 있는 포켓몬은 안 친다 (이미 밟고 나왔다)",
        toll(mon(dex, "ARCANINE", 50, iv=31, held="HEAVYDUTYBOOTS"), "stealthrock") == 0)

    def stage_gain(stat, n):
        tb = war_tb(dex, ai, bench(2))
        base = tb._eval_v2()
        tb.foe.stages[stat] = n
        return tb._eval_v2() - base
    a2, c2, a6 = stage_gain("atk", 2), stage_gain("spa", 2), stage_gain("atk", 6)
    chk("AI 의 공격 +2 (물리 기술만 가진 한카리아스) 는 특공 +2 보다 값이 크다", a2 > c2, (a2, c2))
    chk("  올라갈수록 덜 쳐 준다 (+6 < +2 의 3배)", a2 < a6 < 3 * a2, (a2, a6))

    tb = war_tb(dex, ai, bench(2))
    tb.over, tb.result, tb.turn = True, "draw", TB.MAX_TURNS
    chk("400턴 무승부는 AI 에게 진 것과 같다 (시간 끌기로 무승부를 노리지 않게)", tb._eval_v2() == -100.0,
        tb._eval_v2())
    tb.turn = 12
    chk("  마지막끼리 같이 쓰러진 무승부는 방어 성공에 가깝다 (길드전에서 무승부는 칸을 지킨다 - defends)",
        tb._eval_v2() == 90.0, tb._eval_v2())

    def status_gain(st):
        # 사람 선두 = 괴력몬 (물리, 한카리아스보다 느리다). 특성은 노가드로 - 근성이면 상태이상이 오히려 이득이라 0 이다
        tb = war_tb(dex, ai, [mon(dex, "MACHAMP", 50, "NOGUARD", iv=31)] + bench(2)[1:])
        base = tb._eval_v2()
        tb.me.status = st
        return tb._eval_v2() - base
    burn, para = status_gain("burn"), status_gain("paralysis")
    chk("사람 쪽 물리 공격수의 화상은 마비보다 값이 크다 (이미 AI 가 더 빠르다)", burn > para > 0, (burn, para))
    def benched(st, side):
        tb = war_tb(dex, ai + [mon(dex, "SKARMORY", 50, "STURDY", ["BRAVEBIRD", "DRILLPECK"], iv=31)],
                    [mon(dex, "MACHAMP", 50, "NOGUARD", iv=31), mon(dex, "TYRANITAR", 50, "SANDSTREAM", iv=31)])
        (tb.foe_team if side == "foe" else tb.me_team)[1].status = st
        return tb._eval_v2()
    chk("벤치에 있는 AI 포켓몬의 화상도 친다 (교체해 넣기만 해도 값이 오르면 쓸데없는 교체를 부추긴다)",
        benched("burn", "foe") < benched(None, "foe"), (benched("burn", "foe"), benched(None, "foe")))
    chk("  벤치에 있는 사람 포켓몬의 상태이상도", benched("burn", "me") > benched(None, "me"),
        (benched("burn", "me"), benched(None, "me")))
    tb = war_tb(dex, ai, [mon(dex, "MACHAMP", 50, "GUTS", iv=31)] + bench(2)[1:])
    base = tb._eval_v2()
    tb.me.status = "burn"
    chk("  근성 포켓몬의 화상은 값이 없다 (오히려 공격이 오른다)", tb._eval_v2() - base == 0, tb._eval_v2() - base)


def t_길드전_셈(dex, gyms):
    """길드전 방어 AI 의 새 셈 (_war_choice_v2, WAR_V2): 안전장치 · 시간 끌기 감점 · 깔기 · 관장 판 그대로."""
    print("-- 길드전 방어 AI: 새 셈")
    import time
    old_flag = TB.TrainerBattle.WAR_V2
    TB.TrainerBattle.WAR_V2 = True
    try:
        gar = mon(dex, "GARCHOMP", 50, "ROUGHSKIN", ["EARTHQUAKE", "DRAGONCLAW", "STEALTHROCK", "SWORDSDANCE"], iv=31)
        names = ["MACHAMP", "GYARADOS", "ARCANINE", "TYRANITAR", "SCIZOR", "VENUSAUR"]
        six = [mon(dex, n, 50, "NOGUARD" if n == "MACHAMP" else None, iv=31, seed=i + 2) for i, n in enumerate(names)]

        # (a) 셈이 터져도 그 턴은 관장 AI 의 수 - act 가 예외로 떨어지면 판이 멈춰 공격권이 날아간다
        tb = war_tb(dex, [gar], six)
        real = TB.TrainerBattle._eval_v2
        TB.TrainerBattle._eval_v2 = lambda self: 1 / 0
        try:
            st = tb.rng.getstate()
            got = tb._war_choice()
            tb.rng.setstate(st)
            slot = tb._foe_wants_switch()
            want = (slot, None) if slot is not None else (None, tb._foe_move())
            chk("셈이 터지면 그 턴은 관장 AI 의 수", got == want, (got, want))
            try:
                tb.act("move", "CROSSCHOP" if "CROSSCHOP" in tb.me.moves else tb.bt.usable(tb.me)[0])
                ok = True
            except Exception as e:                       # noqa: BLE001
                ok = repr(e)
            chk("  판은 그대로 이어진다 (예외로 떨어지지 않는다)", ok is True, ok)
        finally:
            TB.TrainerBattle._eval_v2 = real

        # (a2) 셈이 실패하거나 느리면 서버 로그(docker logs)에 남는다 - 전쟁 중 되돌릴지 정할 근거
        import io as _io
        real_err = sys.stderr
        TB.TrainerBattle._eval_v2 = lambda self: 1 / 0
        sys.stderr = _io.StringIO()
        try:
            war_tb(dex, [gar], six)._war_choice()
            failed = sys.stderr.getvalue()
        finally:
            sys.stderr = real_err
            TB.TrainerBattle._eval_v2 = real
        chk("셈이 터지면 서버 로그에 남는다", "[길드전 AI]" in failed and "ZeroDivisionError" in failed, failed)
        slow0 = getattr(TB.TrainerBattle, "WAR2_SLOW", None)
        TB.TrainerBattle.WAR2_SLOW = 0.0
        sys.stderr = _io.StringIO()
        try:
            war_tb(dex, [gar], six)._war_choice()
            slow = sys.stderr.getvalue()
        finally:
            sys.stderr = real_err
            if slow0 is None:
                del TB.TrainerBattle.WAR2_SLOW
            else:
                TB.TrainerBattle.WAR2_SLOW = slow0
        chk("  느린 턴도 남는다 (WAR2_SLOW 를 넘으면)", "[길드전 AI]" in slow and "ms" in slow, slow)

        # (a3) 셈은 턴을 열기 전의 판에서 시작한다 - 예전에는 턴을 연 뒤의 판을 떠서 사본이 턴을 두 번 열었고,
        # 나오자마자 쓰는 속이기가 사본에서는 늘 실패했다 (셈이 AI 의 속이기를 헛수로 보았다)
        amb = mon(dex, "AMBIPOM", 50, "TECHNICIAN", ["FAKEOUT", "DOUBLEHIT", "UTURN", "TAUNT"], iv=31)
        tb = war_tb(dex, [amb, gar], [mon(dex, "MACHAMP", 50, "NOGUARD", ["CROSSCHOP"], iv=31)] + six[1:])
        used = []
        real_load = TB.TrainerBattle.__dict__["load"]

        def spy(cls, dex_, d):
            used.append(json.loads(json.dumps(d)))
            return real_load.__func__(cls, dex_, d)
        TB.TrainerBattle.load = classmethod(spy)
        try:
            tb.act("move", "CROSSCHOP")
        finally:
            TB.TrainerBattle.load = real_load
        pre = used[0] if used else None
        chk("셈에 쓴 판은 이번 턴을 열기 전의 것", pre is not None and pre["turn"] == tb.turn - 1,
            pre and pre["turn"])
        chk("  쓴 판은 비운다 (다음 셈이 낡은 판을 쓰지 않게)", getattr(tb, "_war_pre", None) is None)
        if pre:
            sim = TB.TrainerBattle.load(dex, pre)
            sim._sim, sim._forced = True, ("move", "FAKEOUT")
            ev = sim.act("move", "CROSSCHOP")
            chk("  그 판의 사본에서 첫 턴 속이기가 상대를 풀죽게 한다", "풀이 죽어" in texts(ev), texts(ev))

        # (b) 시간 끌기: 같은 포켓몬이 회복을 많이 썼으면 공격을 고른다
        bl = mon(dex, "BLISSEY", 50, "NATURALCURE", ["SOFTBOILED", "SEISMICTOSS", "TOXIC", "PROTECT"], iv=31)
        picks_ = []
        for s in range(6):
            tb = war_tb(dex, [bl], [mon(dex, "MACHAMP", 50, "NOGUARD", iv=31)] + six[1:3], seed=s + 1)
            tb.foe.hp = int(tb.foe.maxhp * 0.45)
            tb.war_stall = {str(tb.fi): 6}
            picks_.append(tb._war_choice()[1])
        chk("시간 끌기: 회복 · 방어를 여러 번 쓴 포켓몬은 공격(지구던지기 · 맹독)을 고른다",
            all(p not in ("SOFTBOILED", "PROTECT") for p in picks_), picks_)
        tb2 = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
        chk("  회복 · 방어 횟수는 저장했다 되살려도 남는다", tb2.war_stall == tb.war_stall, tb2.war_stall)

        # (b2) 지금 쓰러뜨릴 수 있으면 쓰러뜨린다 (2026-10-22 테스트 플레이 T19: 대도각참이 체력 1 의 메가레쿠쟈 앞에서
        # 칼춤을 쓰고 한 대를 더 맞았다 - 레쿠쟈가 빨라서 어느 쪽이든 이번 턴에 맞지만, 칼춤이면 다음 턴에 또 맞는다)
        kg = mon(dex, "KINGAMBIT", 50, "DEFIANT", ["KOWTOWCLEAVE", "ROCKTOMB", "IRONHEAD", "SWORDSDANCE"], iv=31,
                 held="BLACKGLASSES")
        ray = mon(dex, "RAYQUAZA", 50, "AIRLOCK", ["DRAGONDANCE", "DRAGONASCENT", "HYDROPUMP", "CRUNCH"], iv=31)
        took = []
        for s in range(8):
            tb = war_tb(dex, [kg, mon(dex, "GHOLDENGO", 50, "GOODASGOLD", iv=31)], [ray] + six[1:3], seed=s + 1)
            tb.foe.hp = int(tb.foe.maxhp * 0.71)
            tb.me.hp = 1
            took.append(tb._war_choice()[1])
        chk("지금 쓰러뜨릴 수 있으면 랭크업하지 않고 쓰러뜨린다 (체력 1 의 레쿠쟈 앞 대도각참)",
            all(k in ("KOWTOWCLEAVE", "ROCKTOMB", "IRONHEAD") for k in took), took)
        tb = war_tb(dex, [kg, mon(dex, "GHOLDENGO", 50, "GOODASGOLD", iv=31)],
                    [mon(dex, "CATERPIE", 50, "SHIELDDUST", ["STRINGSHOT", "TACKLE"], iv=31)] + six[1:3])
        tb.me.hp = 1
        chk("  상대가 거의 못 깎으면 강제하지 않는다 (공짜 랭크업은 셈이 정한다 - 벤치마크에서 강제하면 졌다)",
            tb._secure_ko() == [], tb._secure_ko())

        # (b3) 들어오다가 쓰러질 포켓몬으로는 바꾸지 않는다 (2026-10-22 테스트 플레이 T20: 막 나온 따라큐 62% 를 체력
        # 30% 의 토게키스로 바꿔 토게키스가 들어오며 쓰러졌다 - 관장 AI 는 '그 기술을 60% 넘게 맞을 포켓몬' 으로는 안
        # 바꾸는데 새 셈의 교체 후보에는 그 거름이 없었다)
        mk = mon(dex, "MIMIKYU", 50, "DISGUISE", ["SHADOWCLAW", "WOODHAMMER", "PLAYROUGH", "SLASH"], iv=31,
                 held="CHOICESCARF")
        tg = mon(dex, "TOGEKISS", 50, "HUSTLE", ["AIRSLASH", "TRIATTACK", "EXTRASENSORY", "MOONBLAST"], iv=31)
        dp = mon(dex, "DELPHOX", 50, "BLAZE", ["FLAMETHROWER", "PSYCHIC", "DAZZLINGGLEAM", "SHADOWBALL"], iv=31)
        picks2 = []
        for s in range(8):
            tb = war_tb(dex, [mk, tg, dp], [ray] + six[1:3], seed=s + 1)
            tb.foe.hp = int(tb.foe.maxhp * 0.62)
            tb.foe_team[1].hp = int(tb.foe_team[1].maxhp * 0.30)
            tb.foe_team[2].hp = int(tb.foe_team[2].maxhp * 0.30)
            tb.foe.ab["busted"] = True                     # 탈은 벗겨졌다 (실제 판에서도 이미 62%)
            tb.me.hp = int(tb.me.maxhp * 0.17)
            tb.me.stages["spe"] = 2                        # 레쿠쟈가 용의춤으로 스카프 따라큐보다 빠르다 (174 < 230)
            got = tb._war_choice()
            picks2.append(("교체 %s" % tb.foe_team[got[0]].name) if got[0] is not None else got[1])
        chk("들어오다가 쓰러질 포켓몬(체력 30% 토게키스 · 마폭시)으로는 바꾸지 않는다",
            not any(str(p).startswith("교체") for p in picks2), picks2)

        # (b4) 쓰러진 뒤 내보낸 포켓몬을 바로 다음 턴에 바꾸지 않는다 (2026-10-22 테스트 플레이 T14: 파이어로가 쓰러진 뒤
        # 따라큐를 내보냈다가 바로 토게키스로 바꿔 몰드류에게 한 턴을 공짜로 줬다 - 내보낼 포켓몬은 옛 점수(_pick)로,
        # 다음 수는 새 셈으로 골라 둘이 어긋났다)
        ex = mon(dex, "EXCADRILL", 50, "SANDRUSH", ["ROCKSLIDE", "RAPIDSPIN", "EARTHQUAKE", "SWORDSDANCE"], iv=31)
        tf = mon(dex, "TALONFLAME", 50, "FLAMEBODY", ["STEELWING", "ACROBATICS", "FLAREBLITZ", "AERIALACE"], iv=31)
        gl = mon(dex, "GLIMMORA", 50, "TOXICDEBRIS", ["STEALTHROCK", "POWERGEM", "DAZZLINGGLEAM", "SLUDGEWAVE"], iv=31)
        caught = []
        real_wc = TB.TrainerBattle._war_choice

        def spy_wc(self):
            got = real_wc(self)
            caught.append(got)
            return got
        flips = []
        TB.TrainerBattle._war_choice = spy_wc
        try:
            for s in range(8):
                tb = war_tb(dex, [tf, mk, tg, gl], [ex] + six[1:3], seed=s + 1)
                tb.foe_team[1].hp = int(tb.foe_team[1].maxhp * 0.87)
                tb.foe_team[1].ab["busted"] = True
                tb.foe_team[2].hp = int(tb.foe_team[2].maxhp * 0.74)
                tb.me.hp = int(tb.me.maxhp * 0.5)
                tb.foe.hp = 0                              # 파이어로가 방금 쓰러졌다 - 다음 포켓몬을 낸다
                tb._settle([])
                sent = tb.foe.name
                del caught[:]
                tb.act("move", "EARTHQUAKE")
                got = caught[-1] if caught else (None, None)
                flips.append("%s -> 교체 %s" % (sent, tb.foe_team[got[0]].name) if got[0] is not None else sent)
        finally:
            TB.TrainerBattle._war_choice = real_wc
        chk("쓰러진 뒤 내보낸 포켓몬을 바로 다음 턴에 바꾸지 않는다 (몰드류 앞, 8판)",
            not any("교체" in f for f in flips), flips)
        # 관장 자료 팀으로 훑은 상태 가운데 고치기 전에 '내보내자마자 교체' 가 나온 넷(5 · 86 · 92 · 108)과 다른 넷
        tops = [t for t in gyms["trainers"] if t.get("role") in ("챔피언", "사천왕", "프런티어브레인")]
        flips = []
        TB.TrainerBattle._war_choice = spy_wc
        try:
            for n in (5, 86, 92, 108, 0, 1, 2, 3):
                d, a = tops[n % len(tops)], tops[(n * 7 + 3) % len(tops)]
                rnd = random.Random(n)
                tb = war_tb(dex, [TB.trainer_mon(dict(e, level=50, iv=31)) for e in d["team"]],
                            [TB.trainer_mon(dict(e, level=50, iv=31)) for e in a["team"]][:3], seed=n + 1)
                for f in tb.foe_team[1:]:
                    f.hp = max(1, int(f.maxhp * rnd.uniform(0.3, 1.0)))
                tb.me.hp = max(1, int(tb.me.maxhp * rnd.choice((0.3, 0.6, 0.9))))
                tb.me.stages["atk"] = tb.me.stages["spa"] = rnd.choice((0, 0, 1, 2))
                tb.foe.hp = 0
                tb._settle([])
                sent = tb.foe.name
                del caught[:]
                _d, k = tb._best(tb.me, tb.foe)
                tb.act("move", k or tb.bt.usable(tb.me)[0])
                got = caught[-1] if caught else (None, None)
                if got[0] is not None:
                    flips.append("%d: %s -> 교체 %s" % (n, sent, tb.foe_team[got[0]].name))
        finally:
            TB.TrainerBattle._war_choice = real_wc
        chk("  관장 팀 8판에서도 내보내자마자 바꾸지 않는다", not flips, flips)

        # (c) 깔기: 사람에게 6마리가 남았고 이번 턴에 안 쓰러지면 스텔스록부터
        def firsts(pe):
            old_pe = TB.TrainerBattle.WAR_PE_EVAL
            TB.TrainerBattle.WAR_PE_EVAL = pe
            try:
                return [war_tb(dex, [gar, mon(dex, "SKARMORY", 50, iv=31)], six, seed=s + 1)._war_choice()[1]
                        for s in range(9)]
            finally:
                TB.TrainerBattle.WAR_PE_EVAL = old_pe
        first = firsts(False)
        chk("깔기: 사람에게 6마리가 남았으면 첫 턴에 스텔스록 (9판 중 과반, 예전 형세 평가)",
            sum(1 for k in first if k == "STEALTHROCK") >= 5, first)
        # poke-engine 평가는 스텔스록(남은 6마리 x 0.10)과 칼춤(+2 = 0.60)을 비슷하게 본다 - 둘 다 첫 턴의 좋은 수다
        first = firsts(True)
        chk("  poke-engine 평가: 첫 턴은 스텔스록이나 칼춤 (9판 모두 - 때리기만 하지 않는다)",
            all(k in ("STEALTHROCK", "SWORDSDANCE") for k in first), first)
        chk("  스텔스록도 깐다 (9판 중 셋 이상)", sum(1 for k in first if k == "STEALTHROCK") >= 3, first)

        # (d) 관장 판(ai 없음)은 새 셈과 상관없다 - 같은 시드면 사건이 같다
        gym = dict(next(x for x in gyms["trainers"] if x["name"] == "난천"))
        evs = []
        for flag in (False, True):
            TB.TrainerBattle.WAR_V2 = flag
            tb = TB.TrainerBattle(dex, [dict(m) for m in six], gym, random.Random(11))
            tb.start()
            log = []
            for _ in range(12):
                if tb.over:
                    break
                if tb.need_switch:
                    tb.act("switch", tb.valid_switches()[0])
                    continue
                log.append([e.get("text") for e in tb.act("move", tb.bt.usable(tb.me)[0])])
            evs.append(log)
        TB.TrainerBattle.WAR_V2 = True
        chk("관장 판은 새 셈을 켜도 사건이 같다", evs[0] == evs[1] and evs[0], len(evs[0]))

        # (e) 시간: 6 대 6 판을 끝까지 - 한 턴의 셈이 비상 상한 안
        team = [TB.trainer_mon(dict(e, level=50, iv=31)) for e in gyms["trainers"][-1]["team"]]
        mine = [TB.trainer_mon(dict(e, level=50, iv=31)) for e in gyms["trainers"][-2]["team"]]
        tr = {"id": "gw:t", "name": "AI", "level": 50, "team": team, "noMega": True, "ai": "war",
              "keystone": True, "zring": True}
        tb = TB.TrainerBattle(dex, mine, tr, random.Random(5))
        tb.start()
        spent, turns = [], 0
        while not tb.over and turns < 200:
            if tb.need_switch:
                tb.act("switch", tb.valid_switches()[0])
            else:
                _d, k = tb._best(tb.me, tb.foe)
                t0 = time.time()
                try:
                    tb.act("move", k or tb.bt.usable(tb.me)[0])
                except ValueError:
                    tb.act("move", tb.bt.usable(tb.me)[0])
                spent.append(time.time() - t0)
            tb = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))       # 턴마다 저장 · 되살림
            turns += 1
        chk("끝까지 돈다 (턴마다 저장했다 되살려도)", tb.over, turns)
        chk("  한 턴의 셈은 비상 상한 안 (%.0fms)" % (1000 * max(spent)),
            max(spent) < TB.TrainerBattle.WAR2_EMERGENCY + 0.3, max(spent))
    finally:
        TB.TrainerBattle.WAR_V2 = old_flag


def t_턴_끝(dex):
    """쓰러짐과 턴 끝 (1.13.3, 게시판 #295 뒤 전수 점검).

    · 마지막끼리: 내 마지막(화상 · 체력 1)이 상대의 마지막을 쓰러뜨려도 턴 끝 화상 데미지로 같이 쓰러져 무승부다.
      본가와 다르지만 **시즌 중에 판정을 바꾸지 않는다** (형평성, 2026-10-20 사용자 결정) - 바뀌면 알리려고 못 박는다.
    · 상대에게 다음 포켓몬이 있으면 턴 끝은 온다 (화염구슬 · 먹다남은음식 …, 원래 그랬다 - 그대로인지).
    """
    print("-- 쓰러짐과 턴 끝")

    def last_vs_last():
        me = mon(dex, "MACHAMP", 70, "NOGUARD", ["CROSSCHOP"])
        t = {"name": "검사", "team": [mon(dex, "CATERPIE", 2, moves=["STRINGSHOT"], seed=2)]}
        tb = TB.TrainerBattle(dex, [me], t, random.Random(5))
        tb.start()
        tb.me.status = "burn"
        tb.me.hp = 1
        tb.act("move", "CROSSCHOP")
        return tb
    tb = last_vs_last()
    chk("마지막끼리는 예전 그대로: 화상 데미지로 같이 쓰러지면 무승부 (시즌 중 판정 유지)",
        tb.over and tb.result == "draw", (tb.result, tb.me.hp))
    me = mon(dex, "CONKELDURR", 70, "GUTS", ["MACHPUNCH"], held="FLAMEORB")
    t = {"name": "검사", "team": [mon(dex, "CATERPIE", 2, moves=["STRINGSHOT"], seed=2),
                                 mon(dex, "BLISSEY", 100, moves=["SOFTBOILED"], seed=3)]}
    tb = TB.TrainerBattle(dex, [me], t, random.Random(5))
    tb.start()
    tb.act("move", "MACHPUNCH")
    chk("상대에게 다음 포켓몬이 있으면 쓰러뜨린 턴에도 턴 끝 (화염구슬)", tb.me.status == "burn", tb.me.status)


def main():
    dex = load_dex()
    with open(os.path.join(ROOT, "server", "data", "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    t_특성(dex)
    t_교체_규칙(dex, gyms)
    t_저장했다_되살려도_같다(dex, gyms)
    t_로스터(dex, gyms)
    t_상대_AI(dex, gyms)
    t_끝까지_돈다(dex, gyms)
    t_길드전_방어_AI(dex, gyms)
    t_길드전_평가(dex)
    t_길드전_평가_pe(dex)
    t_길드전_헛수(dex)
    t_관장_AI(dex, gyms)
    t_길드전_셈(dex, gyms)
    t_턴_끝(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
