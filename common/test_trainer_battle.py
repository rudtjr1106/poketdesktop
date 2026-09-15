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
                if tb.valid_switches() and rng.random() < 0.15:
                    tb.act("switch", rng.choice(tb.valid_switches()))
                else:
                    keys = [m for m in tb.me.moves if tb.me.pp.get(m, 0) > 0] or [B.STRUGGLE]
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
    chk("아무 일도 안 하는 기술을 가려낸다",
        [TB.works(dex.move(k)) for k in ("PROTECT", "SUBSTITUTE", "HEAVYSLAM", "SWAGGER", "SWORDSDANCE", "WILLOWISP", "GROWL", "RECOVER")]
        == [False, False, False, False, True, True, True, True])
    dead = [(t["name"], m["species"], k) for t in gyms["trainers"] for m in t["team"]
            for k in m["moves"] if not TB.works(dex.move(k))]
    chk("관장 포켓몬에 헛기술이 없다", not dead, dead[:5])
    nohit = [(t["name"], m["species"]) for t in gyms["trainers"] for m in t["team"]
             if not any((dex.move(k) or {}).get("power") for k in m["moves"])]
    chk("모두 때리는 기술이 있다", not nohit, nohit[:5])
    chk("개체값은 모두 31", all(m["iv"] == 31 for t in gyms["trainers"] for m in t["team"]))
    lo20 = [sum(m["evs"].values()) for t in gyms["trainers"] if t["level"] == 20 for m in t["team"]]
    hi100 = [sum(m["evs"].values()) for t in gyms["trainers"] if t["level"] == 100 for m in t["team"]]
    chk("노력치: Lv.20 은 0, Lv.100 은 절반쯤", max(lo20) == 0 and 240 <= min(hi100) and max(hi100) <= 256,
        (max(lo20), min(hi100), max(hi100)))
    natures = collections.Counter(m["nature"] for t in gyms["trainers"] for m in t["team"])
    chk("성격을 포켓몬에 맞춘다 (무보정 없음)", "HARDY" not in natures and len(natures) >= 4, natures)
    f = TB.trainer_mon({"species": "PIKACHU", "level": 50, "iv": 31, "evs": {"spe": 126, "spa": 126}})
    chk("능력마다 따로 적은 노력치를 읽는다", f["evs"]["spe"] == 126 and f["evs"]["atk"] == 0, f["evs"])
    f = TB.trainer_mon({"species": "PIKACHU", "level": 50, "iv": 20, "ev": 40})
    chk("예전 자료(숫자 하나)도 읽는다", f["evs"]["hp"] == 40 and f["ivs"]["spe"] == 20, f)


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
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
