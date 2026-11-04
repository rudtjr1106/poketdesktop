# -*- coding: utf-8 -*-
"""잡기 모드 검사 — 야생을 쓰러뜨리지 않고 잡기 좋게 만드는가. 서버 없이 돈다.

    python common/test_spare.py

Battle.spare_plan 이 보는 것:

1. **쓰러뜨리지 않는다.** 급소에 최대 난수로 맞아도 안 쓰러지는 기술을 먼저 쓰고,
   체력이 넉넉할 때만 급소가 아니면 안 쓰러지는 기술까지 쓴다. 수백 판을 실제로
   돌려 급소 아닌 기술로는 한 번도 쓰러뜨리지 않는지, 급소로도 드문지 본다.
2. 잠재우기·마비가 있으면 먼저 건다. 화상·독은 안 건다 (턴마다 깎여 쓰러진다).
3. 체력이 1/4 이하가 되거나, 어떤 기술이든 쓰러뜨릴 것 같으면 멈춘다.
4. 예전 AI(choose_for)는 그대로다 - test_held 의 요약값이 따로 지킨다.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import battle as B              # noqa: E402
from common import pokelogic as P           # noqa: E402

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


def mon(dex, species, level, moves, seed=1):
    m = P.make_pokemon(dex.get(species), level, random.Random(seed), shiny_rate=10 ** 9,
                       ivs=dict((s, 31) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = moves
    m["held"] = None
    return m


def fight(dex, a, b, seed=1):
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    return B.Battle(dex, me, foe, random.Random(seed)), me, foe


def t_고르기(dex):
    print("-- 고르기")
    bt, me, foe = fight(dex, mon(dex, "BUTTERFREE", 30, ["TACKLE", "SLEEPPOWDER", "STUNSPORE", "POISONPOWDER"]),
                        mon(dex, "RATTATA", 30, ["TACKLE"]))
    chk("잠재우기가 먼저", bt.spare_plan(me, foe) == ("SLEEPPOWDER", None), bt.spare_plan(me, foe))
    me.moves = ["TACKLE", "STUNSPORE", "POISONPOWDER"]
    chk("잠재우기가 없으면 마비", bt.spare_plan(me, foe) == ("STUNSPORE", None), bt.spare_plan(me, foe))
    me.moves = ["TACKLE", "POISONPOWDER"]
    chk("독은 안 건다 (턴마다 깎여 쓰러진다)", bt.spare_plan(me, foe)[0] == "TACKLE", bt.spare_plan(me, foe))
    foe.status = "sleep"
    me.moves = ["TACKLE", "SLEEPPOWDER"]
    chk("이미 상태이상이면 안 건다", bt.spare_plan(me, foe)[0] == "TACKLE", bt.spare_plan(me, foe))

    bt, me, foe = fight(dex, mon(dex, "PIKACHU", 30, ["THUNDERWAVE", "QUICKATTACK"]),
                        mon(dex, "MAGNEMITE", 30, ["TACKLE"]))
    chk("전기 타입에게는 마비를 안 건다", bt.spare_plan(me, foe)[0] == "QUICKATTACK", bt.spare_plan(me, foe))

    # 한 방에 쓰러뜨리는 센 기술 대신 약한 기술
    bt, me, foe = fight(dex, mon(dex, "GARCHOMP", 60, ["EARTHQUAKE", "DRAGONCLAW", "SANDATTACK"]),
                        mon(dex, "ONIX", 30, ["TACKLE"]))
    plan = bt.spare_plan(me, foe)
    worst, _c, _e = B.damage(dex, dex.move(plan[0]) or {}, me, foe, B.MAX_RNG, crit=True) if plan[0] else (0, 0, 0)
    chk("고른 기술은 급소·최대 난수로도 안 쓰러뜨린다", plan[0] is None or worst < foe.hp, (plan, worst, foe.hp))
    chk("지진(4배)은 고르지 않는다", plan[0] != "EARTHQUAKE", plan)

    bt, me, foe = fight(dex, mon(dex, "MEWTWO", 100, ["PSYSTRIKE", "AURASPHERE"]),
                        mon(dex, "CATERPIE", 5, ["TACKLE"]))
    chk("무엇을 써도 쓰러뜨리면 멈춘다 (nosafe)", bt.spare_plan(me, foe) == (None, "nosafe"), bt.spare_plan(me, foe))

    bt, me, foe = fight(dex, mon(dex, "RATTATA", 30, ["TACKLE"]), mon(dex, "SNORLAX", 30, ["TACKLE"]))
    foe.hp = foe.maxhp // 4
    chk("체력이 1/4 이하면 멈춘다 (low)", bt.spare_plan(me, foe) == (None, "low"), bt.spare_plan(me, foe))
    foe.hp = foe.maxhp // 4 + 5
    me.moves = ["TACKLE", "SING"]
    me.pp["SING"] = 15
    chk("1/4 근처라도 재울 수 있으면 재운다", bt.spare_plan(me, foe)[0] == "SING", bt.spare_plan(me, foe))

    bt, me, foe = fight(dex, mon(dex, "MAGIKARP", 30, ["SPLASH"]), mon(dex, "PIDGEY", 30, ["TACKLE"]))
    me.pp["SPLASH"] = 0
    chk("몸부림만 남으면 멈춘다", bt.spare_plan(me, foe) == (None, "nosafe"), bt.spare_plan(me, foe))

    # 야생 비버통이 먼저 이판사판태클을 쓰고 반동으로 깎인 뒤, '안 쓰러진다' 던
    # 사이코키네시스를 맞아 쓰러졌다 (기술표를 넓히면서 드러났다). 상대가 스스로
    # 깎을 수 있는 만큼을 빼고 센다.
    psy = mon(dex, "BEHEEYEM", 74, ["PSYCHIC"])
    # 사이코키네시스는 최대 154, 이판사판태클의 반동은 최대 62 다. 체력 200 이면
    # 반동이 없을 때는 남고(46), 반동을 먼저 받으면 138 이라 쓰러진다.
    bt, me, foe = fight(dex, psy, mon(dex, "BIBAREL", 74, ["TACKLE"]))
    foe.hp = 200
    chk("반동기가 없는 상대에게는 그 기술을 쓴다", bt.spare_plan(me, foe) == ("PSYCHIC", None),
        bt.spare_plan(me, foe))
    bt, me, foe = fight(dex, psy, mon(dex, "BIBAREL", 74, ["DOUBLEEDGE"]))
    foe.hp = 200
    chk("반동기를 가진 상대에게는 반동만큼 덜 남는다고 본다 (안 쓴다)",
        bt.spare_plan(me, foe) == (None, "nosafe"), bt.spare_plan(me, foe))
    chk("  상대가 스스로 깎을 수 있는 체력을 센다", 0 < bt._self_loss(foe, me) < foe.maxhp // 2,
        bt._self_loss(foe, me))
    bt, me, foe = fight(dex, psy, mon(dex, "BIBAREL", 74, ["BELLYDRUM"]))
    chk("배북은 절반을 깎는다고 본다", bt._self_loss(foe, me) == foe.maxhp // 2, bt._self_loss(foe, me))


def t_실제로_안_쓰러뜨린다(dex):
    print("-- 실제로 돌려 본다")
    rng = random.Random(20260915)
    killed, crit_ko, held, games, at = [], [], 0, 0, []
    for n in range(400):
        lv = rng.randint(5, 90)
        a = dex.roll_wild(lv, lv, rng)
        b = dex.roll_wild(max(2, lv - 8), lv + 3, rng)
        if not a or not b:
            continue
        a["held"] = b["held"] = None
        bt, me, foe = fight(dex, a, b, seed=n)
        games += 1
        for _turn in range(60):
            pick, reason = bt.spare_plan(me, foe)
            if reason:
                held += 1
                at.append(foe.hp / float(foe.maxhp))
                break
            hp = foe.hp
            ev = bt.take_turn(pick)
            mine = [e for e in ev if e.get("t") == "hit" and e.get("who") == "me" and e.get("hp") == 0]
            if mine:
                (crit_ko if mine[0].get("crit") else killed).append((a["species"], b["species"], pick, hp))
                break
            if bt.over:
                break
    chk("%d판 동안 급소가 아닌 내 기술로 쓰러뜨린 적이 없다" % games, not killed, killed[:5])
    chk("급소로 쓰러뜨리는 일도 드물다 (2% 이하)", len(crit_ko) <= games * 0.02, (len(crit_ko), crit_ko[:3]))
    chk("대부분 멈추는 데까지 간다 (쓰러뜨리거나 끝없이 돌지 않는다)", held >= games * 0.6, (held, games))
    at.sort()
    mid = at[len(at) // 2] if at else 1.0
    # 급소까지 막던 첫 판은 절반(0.53)에서 멈췄다
    chk("멈출 때 상대 체력은 가운데값이 1/3 이하다", mid <= 0.35, round(mid, 2))


def t_숨은_상대(dex):
    """게시판 #436 (니뉴): 야생 대왕끼리동이 구멍파기로 땅속에 들어간 턴에 멈췄다. 숨은 동안은 도트 창이 숨어 있어
    볼도 바로 싸우기도 못 누르고, 10초 뒤 끝까지 싸우기로 넘어가 올라온 대왕끼리동을 쓰러뜨렸다.
    이제 멈출 때 상대가 숨어 있으면 **숨은 상대에게 안 닿는 기술**로 한 턴을 넘기고, 올라온 뒤에 멈춘다."""
    print("-- 숨은 상대 (#436)")

    def setup(my_moves, foe_moves=("DIG",), seed=1, ability_on=True):
        bt, me, foe = fight(dex, mon(dex, "GOLISOPOD", 67, list(my_moves)), mon(dex, "COPPERAJAH", 54, list(foe_moves)),
                            seed)
        me.ability_on = foe.ability_on = ability_on
        return bt, me, foe

    # 그 판 그대로: 셸블레이드로 깎고 상대가 구멍파기로 들어간다
    moves = ["RAZORSHELL", "PINMISSILE", "SWORDSDANCE", "LIQUIDATION"]
    kept = surfaced = held_after = 0
    for seed in range(40):
        bt, me, foe = setup(moves, seed=seed)
        foe.hp = int(foe.maxhp * 0.6)
        pick, why = bt.spare_plan(me, foe)
        bt.take_turn(pick)
        if not foe.cond.get("invuln") or bt.over:
            continue                                        # 이 판은 구멍파기를 안 썼다 / 끝났다
        pick, why = bt.spare_plan(me, foe)                  # 서버가 턴 뒤에 '다음에 멈추나' 를 본다
        if why is not None:
            chk("숨은 동안은 멈추지 않는다 (seed %d)" % seed, False, (pick, why))
            continue
        hp = foe.hp
        bt.take_turn(pick)
        kept += foe.alive() and foe.hp == hp
        surfaced += not foe.cond.get("invuln")
        held_after += bt.spare_plan(me, foe)[1] is not None
        if seed == 0:
            chk("  넘기는 기술은 숨은 상대에게 안 닿는 공격 기술", pick in ("RAZORSHELL", "PINMISSILE", "LIQUIDATION"), pick)
    chk("숨은 턴에 멈추지 않고 넘긴 판에서 상대가 안 다친다", kept > 10 and kept == surfaced, (kept, surfaced))
    # (올라온 뒤는 평소 판단이다 - 셸블레이드로 방어가 떨어져 있지 않으면 아직 안전한 기술이 남은 판도 있다)
    chk("  올라온 뒤에는 (거의) 멈춘다 - 이제 도트가 보여 볼을 던질 수 있다", held_after >= kept * 0.8, (held_after, kept))

    def plan_when_hidden(my_moves, hp=0.2, **kw):
        bt, me, foe = setup(my_moves, **kw)
        foe.cond["invuln"] = "dig"
        foe.cond["charge2"] = {"move": "DIG"}
        foe.hp = max(1, int(foe.maxhp * hp))
        return bt.spare_plan(me, foe), bt, me, foe

    p, _bt, _me, _foe = plan_when_hidden(["EARTHQUAKE"])
    chk("땅속에도 닿는 지진(2배)만 있으면 넘기지 않고 멈춘다", p == (None, "low"), p)
    p, _bt, _me, _foe = plan_when_hidden(["EARTHQUAKE", "GROWL"])
    chk("상대에게 쓰는 변화기도 숨은 상대에게는 안 닿는다 - 그걸로 넘긴다", p == ("GROWL", None), p)
    p, _bt, _me, _foe = plan_when_hidden(["SWORDSDANCE"])
    chk("나에게 쓰는 기술만 있으면 멈춘다 (날씨 · 함정처럼 턴 끝에 깎을 수 있다)", p == (None, "low"), p)
    p, _bt, _me, _foe = plan_when_hidden(["HIGHJUMPKICK", "EXPLOSION", "OUTRAGE", "SOLARBEAM"])
    chk("빗나가면 내가 다치는 · 스스로 쓰러지는 · 묶이는 · 모으는 기술로는 안 넘긴다", p == (None, "low"), p)
    p, bt, me, foe = plan_when_hidden(["TACKLE"])
    chk("몸통박치기로 넘긴다", p == ("TACKLE", None), p)
    me.mon["ability"] = "NOGUARD"
    me.ability = "NOGUARD"
    chk("노가드는 숨어도 맞히니 멈춘다", bt.spare_plan(me, foe) == (None, "low"), bt.spare_plan(me, foe))
    p, bt, me, foe = plan_when_hidden(["TACKLE"], hp=0.05)
    foe.status = "poison"
    foe.hp = foe.maxhp // 8
    chk("턴 끝 독으로 쓰러질 체력이면 넘기지 않고 멈춘다", bt.spare_plan(me, foe) == (None, "low"),
        bt.spare_plan(me, foe))
    p, bt, me, foe = plan_when_hidden(["TACKLE"])
    foe.cond["invuln"] = "vanish"
    chk("섀도다이브(모습을 감췄다)도 넘긴다", p == ("TACKLE", None) and bt.spare_plan(me, foe) == ("TACKLE", None),
        bt.spare_plan(me, foe))
    bt, me, foe = setup(["TACKLE"])
    foe.hp = foe.maxhp // 5
    chk("숨지 않았으면 예전처럼 멈춘다", bt.spare_plan(me, foe) == (None, "low"), bt.spare_plan(me, foe))


def main():
    dex = load_dex()
    t_고르기(dex)
    t_실제로_안_쓰러뜨린다(dex)
    t_숨은_상대(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
