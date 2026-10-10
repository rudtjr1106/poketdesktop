# -*- coding: utf-8 -*-
"""유턴·볼트체인지는 **쓰자마자** 물러난다 (1.10.4). 서버도 화면도 없이 엔진만.

    python common/test_pivot.py

제보: "볼트체인지, 유턴 오류 있는 것 같음 (공격 후 바로 교체를 안 함)"

예전에는 사람이 고르는 교체를 **턴이 다 끝난 뒤에** 물었다. 그래서 유턴을 쓴 포켓몬이 상대의
기술을 그대로 맞고, 턴 끝의 독·날씨 피해까지 받고 나서야 바뀌었다. 원작에서는 기술이 끝나자마자
누구를 낼지 고르고, 그 턴의 남은 기술은 **새로 나온 포켓몬이** 맞는다.

  관장 배틀 (trainer_battle)
    1. 내가 먼저 유턴: 상대가 움직이기 전에 묻는다. 고르면 상대의 기술은 나온 포켓몬이 맞는다.
    2. 내가 나중에 유턴: 상대는 이미 움직였다. 고르면 턴 끝 피해는 나온 포켓몬이 받는다.
    3. 멈춘 채로 저장했다 되살려도 똑같이 이어진다.
    4. 마지막 상대를 쓰러뜨리면 안 묻는다 (판이 끝난다). 바꿀 동료가 없어도 안 묻는다.
    5. 볼트체인지·퀵턴·배턴터치·막말내뱉기·순간이동도 같다. 안 통하면(땅 타입) 안 물러난다.
    6. 턴 도중에 나온 포켓몬은 그 턴에 움직이지 않는다 (위기회피).
  실시간 배틀 (live_battle)
    7. 먼저 쓴 쪽만 교체를 고른다 (상대는 기다린다). 고르면 턴이 이어진다. 턴 수는 한 번만 는다.
    8. 둘 다 유턴이면 차례로 멈춘다. 시간 안에 못 고르면 서버가 대신 고른다. 저장해도 이어진다.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from common import live_battle as L                          # noqa: E402
from common import pokelogic as P                            # noqa: E402
from common import trainer_battle as TB                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Sure(random.Random):
    """명중·부가효과 판정이 늘 같은 쪽으로 가는 rng."""

    def uniform(self, a, b):
        return a


def load_dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


DEX = load_dex()


def mon(species, moves, level=50, ability=None, held=None, iv=31):
    m = P.make_pokemon(DEX.get(species), level, random.Random(1), shiny_rate=10 ** 9,
                       ivs=dict((s, iv) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    m["evs"] = dict((s, 0) for s in P.STATS)
    if ability:
        m["ability"] = ability
    return m


def gym(team, party, seed=3):
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "t", "level": 50,
               "team": [{"species": m["species"], "level": m["level"], "moves": m["moves"],
                         "ability": m["ability"], "held": m.get("held"), "iv": 31, "evs": {},
                         "nature": "HARDY", "gender": m.get("gender") or "M"} for m in team]}
    tb = TB.TrainerBattle(DEX, party, trainer, Sure(seed))
    tb.start()
    return tb


def live(a, b, seed=5):
    lb = L.LiveBattle(DEX, (1, "가", a), (2, "나", b), rng=Sure(seed), max_turns=150)
    lb.resolve()                                     # 시작 (첫 포켓몬이 나온다)
    return lb


def texts(ev):
    return " | ".join(e.get("text", "") for e in ev if e.get("text"))


def kinds(ev, who=None):
    return [e["t"] for e in ev if who is None or e.get("who") == who]


def moved(ev, who):
    return any(e.get("t") == "move" and e.get("who") == who for e in ev)


def t_관장():
    print("== 관장 배틀 ==")
    print("-- 내가 먼저 유턴")
    # 핫삼(유턴) + 잠만보. 상대 해피너스의 지구던지기는 늘 50 을 깎는다 (누가 맞았는지 재기 좋다).
    party = [mon("NINJASK", ["UTURN", "PROTECT"]), mon("SNORLAX", ["TACKLE"])]
    tb = gym([mon("BLISSEY", ["SEISMICTOSS"])], party)
    ninja, lax, foe = tb.me_team[0], tb.me_team[1], tb.foe
    foe_hp = foe.hp
    ev = tb.act("move", "UTURN")
    chk("**유턴이 끝나자마자 교체를 묻는다** (상대는 아직 안 움직였다)", tb.need_switch and ev[-1]["t"] == "choose"
        and moved(ev, "me") and not moved(ev, "foe"), texts(ev))
    chk("  유턴의 피해는 들어갔다", foe.hp < foe_hp, (foe.hp, foe_hp))
    chk("  유턴을 쓴 포켓몬은 한 대도 안 맞았다", ninja.hp == ninja.maxhp and tb.mi == 0, (ninja.hp, ninja.maxhp))
    chk("  턴은 한 번 올라 있다 (멈춘 것이다)", tb.turn == 1 and tb.mid is not None, tb.turn)
    try:
        tb.act("move", "UTURN")
        refused = False
    except ValueError:
        refused = True
    chk("  멈춘 동안에는 교체만 받는다", refused)
    saved = json.loads(json.dumps(tb.dump()))
    ev2 = tb.act("switch", 1)
    chk("**고르면 턴이 이어진다: 상대의 기술은 나온 포켓몬이 맞는다**", tb.mi == 1 and moved(ev2, "foe")
        and lax.hp == lax.maxhp - 50 and ninja.hp == ninja.maxhp, (lax.maxhp - lax.hp, ninja.maxhp - ninja.hp, texts(ev2)))
    chk("  턴은 그대로 1 이고, 이제 기술을 고를 차례다", tb.turn == 1 and not tb.need_switch and tb.mid is None and not tb.over,
        (tb.turn, tb.need_switch))
    chk("  순서: 나온다 -> 상대의 기술", kinds(ev2).index("switch") < [i for i, e in enumerate(ev2) if e.get("t") == "move"][0],
        kinds(ev2))
    back = TB.TrainerBattle.load(DEX, saved)
    ev3 = back.act("switch", 1)
    chk("멈춘 채로 저장했다 되살려도 똑같이 이어진다", texts(ev3) == texts(ev2) and back.me.hp == lax.hp and back.turn == 1,
        (texts(ev3), texts(ev2)))
    ev = tb.act("move", "TACKLE")
    chk("  다음 턴은 평소대로 돈다", tb.turn == 2 and moved(ev, "me") and moved(ev, "foe"), texts(ev))

    print("-- 내가 나중에 유턴 (턴 끝 피해는 나온 포켓몬이 받는다)")
    party = [mon("SNORLAX", ["UTURN"]), mon("BLISSEY", ["TACKLE"])]
    tb = gym([mon("TYRANITAR", ["SANDSTORM", "CRUNCH"], ability="UNNERVE")], party)
    lax, bli = tb.me_team[0], tb.me_team[1]
    tb.bt.field.weather, tb.bt.field.weather_turns = "sand", 5          # 모래바람 (바위·땅·강철이 아니면 깎인다)
    ev = tb.act("move", "UTURN")
    hit = lax.maxhp - lax.hp
    chk("상대가 먼저 움직였고, 내 유턴 뒤에 멈췄다", tb.need_switch and moved(ev, "foe") and moved(ev, "me")
        and [e["who"] for e in ev if e.get("t") == "move"][0] == "foe", texts(ev))
    chk("  **턴 끝(모래바람)은 아직 안 왔다**", "모래바람" not in texts([e for e in ev if e.get("t") == "chip"]), texts(ev))
    ev2 = tb.act("switch", 1)
    chk("고르면 턴 끝이 온다: 모래바람은 **나온 포켓몬이** 맞는다", bli.hp == bli.maxhp - bli.maxhp // 16
        and lax.maxhp - lax.hp == hit and not moved(ev2, "foe"), (bli.maxhp - bli.hp, lax.maxhp - lax.hp, hit, texts(ev2)))

    print("-- 안 묻는 때")
    tb = gym([mon("RATTATA", ["TACKLE"], level=5)], [mon("SCIZOR", ["UTURN"]), mon("SNORLAX", ["TACKLE"])])
    ev = tb.act("move", "UTURN")
    chk("마지막 상대를 쓰러뜨리면 안 묻는다 (이겼다)", tb.over and tb.result == "won" and not tb.need_switch, texts(ev))
    tb = gym([mon("BLISSEY", ["SEISMICTOSS"])], [mon("NINJASK", ["UTURN"])])
    foe_hp = tb.foe.hp
    ev = tb.act("move", "UTURN")
    chk("바꿀 동료가 없으면 안 묻는다 (공격만 한다)", not tb.need_switch and tb.foe.hp < foe_hp and moved(ev, "foe")
        and tb.pending_out is None, texts(ev))
    tb = gym([mon("GARCHOMP", ["SEISMICTOSS"])], [mon("JOLTEON", ["VOLTSWITCH"]), mon("SNORLAX", ["TACKLE"])])
    ev = tb.act("move", "VOLTSWITCH")
    chk("볼트체인지가 땅 타입에 안 통하면 안 물러난다", not tb.need_switch and tb.mi == 0 and tb.foe.hp == tb.foe.maxhp
        and moved(ev, "foe"), texts(ev))
    tb = gym([mon("RATTATA", ["TACKLE"], level=5), mon("BLISSEY", ["SEISMICTOSS"])],
             [mon("SCIZOR", ["UTURN"]), mon("SNORLAX", ["TACKLE"])])
    ev = tb.act("move", "UTURN")
    chk("상대를 쓰러뜨려도 남은 상대가 있으면 묻는다 (내가 먼저 바꾼다)", tb.need_switch and not tb.over and not tb.foe.alive(),
        texts(ev))
    ev2 = tb.act("switch", 1)
    chk("  고른 뒤에 상대의 다음 포켓몬이 나온다", tb.mi == 1 and tb.fi == 1 and tb.foe.alive() and not tb.need_switch
        and [e.get("who") for e in ev2 if e.get("t") == "switch"] == ["me", "foe"], kinds(ev2))

    print("-- 다른 교체 기술")
    for key, user, foe_sp in (("VOLTSWITCH", "JOLTEON", "BLISSEY"), ("FLIPTURN", "STARMIE", "BLISSEY"),
                              ("PARTINGSHOT", "PERSIAN", "BLISSEY"), ("TELEPORT", "ALAKAZAM", "BLISSEY"),
                              ("BATONPASS", "NINJASK", "BLISSEY")):
        tb = gym([mon(foe_sp, ["SEISMICTOSS"])], [mon(user, [key, "SWORDSDANCE"]), mon("SNORLAX", ["TACKLE"])])
        first, lax = tb.me_team[0], tb.me_team[1]
        if key == "BATONPASS":
            first.stages["atk"] = 2
        ev = tb.act("move", key)
        # 순간이동은 우선도가 -6 이라 상대가 먼저 움직인다. 나머지는 내가 빠르다.
        late = key == "TELEPORT"
        ok = tb.need_switch and ev[-1]["t"] == "choose" and moved(ev, "foe") == late
        ev2 = tb.act("switch", 1)
        ok = ok and tb.mi == 1 and not tb.need_switch and moved(ev2, "foe") == (not late)
        ok = ok and (lax.hp == lax.maxhp - (0 if late else 50)) and first.hp == first.maxhp - (50 if late else 0)
        if key == "BATONPASS":
            ok = ok and lax.stages["atk"] == 2
        chk("%s: 쓰자마자 묻고, 고르면 이어진다%s" % (DEX.move(key).get("kr") or key, " (랭크를 넘겨받는다)" if key == "BATONPASS" else ""),
            ok, (texts(ev), texts(ev2), lax.maxhp - lax.hp, first.maxhp - first.hp))

    print("-- 턴 도중에 나온 포켓몬은 그 턴에 움직이지 않는다 (위기회피)")
    party = [mon("GOLISOPOD", ["TACKLE"], ability="EMERGENCYEXIT"), mon("SNORLAX", ["TACKLE"])]
    tb = gym([mon("JOLTEON", ["SEISMICTOSS"])], party)                  # 늘 50 을 깎는다. 갑주무사보다 빠르다
    goli, lax = tb.me_team[0], tb.me_team[1]
    goli.hp = goli.maxhp // 2 + 10                                      # 한 대 맞으면 절반 아래다
    foe_hp = tb.foe.hp
    ev = tb.act("move", "TACKLE")
    chk("상대의 기술에 체력이 절반 아래로 내려가면 그 자리에서 묻는다 (내 기술은 못 썼다)",
        tb.need_switch and moved(ev, "foe") and not moved(ev, "me") and goli.alive(), texts(ev))
    ev2 = tb.act("switch", 1)
    chk("  나온 포켓몬은 이 턴에 기술을 쓰지 않는다 (물러난 포켓몬의 차례는 사라진다)",
        tb.mi == 1 and not moved(ev2, "me") and tb.foe.hp == foe_hp and tb.turn == 1, texts(ev2))


def t_실시간():
    print("\n== 실시간 배틀 ==")
    print("-- 먼저 쓴 쪽만 교체를 고른다")
    a = [mon("NINJASK", ["UTURN"]), mon("SNORLAX", ["TACKLE"])]
    b = [mon("BLISSEY", ["SEISMICTOSS"]), mon("SNORLAX", ["TACKLE"])]
    lb = live(a, b)
    ninja, lax, bli = lb.a.team[0], lb.a.team[1], lb.b.team[0]
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "SEISMICTOSS")
    step = lb.step
    ev = lb.resolve()
    chk("**유턴이 끝나자마자 멈춘다**: 교체 단계, 쓴 쪽만 고른다", lb.phase() == "switch" and lb.can_act("a") and not lb.can_act("b")
        and moved(ev, "me") and not moved(ev, "foe") and lb.turn == 1, (lb.phase(), texts(ev)))
    chk("  유턴을 쓴 포켓몬은 안 맞았고, 상대는 맞았다", ninja.hp == ninja.maxhp and bli.hp < bli.maxhp)
    chk("  기다리는 쪽에게는 '고르고 있다' 로 알린다 (상대 시점으로 뒤집혀 간다)",
        ev[-1]["t"] == "choose" and ev[-1]["who"] == "me" and lb.events_for("b", ev)[-1]["who"] == "foe", ev[-1])
    try:
        lb.choose("b", "move", "SEISMICTOSS")
        refused = False
    except ValueError:
        refused = True
    chk("  상대는 그동안 아무것도 못 고른다 (이 턴의 기술은 이미 냈다)", refused and lb.b.choice is None and not lb.ready())
    view = lb.view("a")
    chk("  화면에 주는 것: 내 쪽은 교체해야 한다, 상대는 아니다", view["phase"] == "switch" and view["me"]["needSwitch"]
        and not view["foe"]["needSwitch"] and view["canAct"] and not lb.view("b")["canAct"], view["phase"])
    saved = json.loads(json.dumps(lb.dump()))
    lb.choose("a", "switch", 1)
    chk("  고르면 바로 돌 수 있다", lb.ready())
    ev2 = lb.resolve()
    chk("**고르면 턴이 이어진다: 상대의 기술은 나온 포켓몬이 맞는다**", lb.a.slot == 1 and moved(ev2, "foe")
        and lax.hp == lax.maxhp - 50 and ninja.hp == ninja.maxhp, (lax.maxhp - lax.hp, texts(ev2)))
    chk("  턴은 그대로 1, 단계(step)는 둘 올랐다. 다시 기술을 고를 차례다", lb.turn == 1 and lb.step == step + 2
        and lb.phase() == "choose" and lb.can_act("a") and lb.can_act("b") and lb.mid is None, (lb.turn, lb.step, step))
    back = L.LiveBattle.load(DEX, saved)
    chk("멈춘 채로 저장했다 되살려도 같은 자리다", back.phase() == "switch" and back.can_act("a") and not back.can_act("b")
        and back.mid is not None)
    back.choose("a", "switch", 1)
    ev3 = back.resolve()
    chk("  똑같이 이어진다", texts(ev3) == texts(ev2) and back.a.mon.hp == lax.hp and back.turn == 1, (texts(ev3), texts(ev2)))

    print("-- 시간 안에 못 고르면 서버가 대신 고른다")
    lb = live([mon("NINJASK", ["UTURN"]), mon("SNORLAX", ["TACKLE"])], [mon("BLISSEY", ["SEISMICTOSS"]), mon("SNORLAX", ["TACKLE"])])
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "SEISMICTOSS")
    lb.resolve()
    ev = lb.resolve()                                                    # 제한 시간이 지났다
    chk("대신 다음 포켓몬을 내고 턴을 마저 돈다", lb.a.slot == 1 and moved(ev, "foe") and lb.phase() == "choose"
        and lb.a.auto == 1 and lb.b.auto == 0, (lb.a.slot, lb.a.auto, lb.b.auto, texts(ev)))

    print("-- 둘 다 유턴")
    a = [mon("NINJASK", ["UTURN"]), mon("SNORLAX", ["TACKLE"])]
    b = [mon("SCIZOR", ["UTURN"]), mon("BLISSEY", ["TACKLE"])]
    lb = live(a, b)
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "UTURN")
    ev = lb.resolve()
    chk("빠른 쪽이 먼저 멈춘다 (느린 쪽은 아직 안 썼다)", lb.can_act("a") and not lb.can_act("b") and not moved(ev, "foe"), texts(ev))
    lb.choose("a", "switch", 1)
    ev = lb.resolve()
    chk("느린 쪽의 유턴은 **나온 포켓몬이** 맞고, 이번에는 그쪽이 멈춘다", lb.phase() == "switch" and lb.can_act("b")
        and not lb.can_act("a") and moved(ev, "foe") and lb.a.team[1].hp < lb.a.team[1].maxhp
        and lb.a.team[0].hp == lb.a.team[0].maxhp, texts(ev))
    lb.choose("b", "switch", 1)
    ev = lb.resolve()
    chk("둘 다 고르면 턴이 끝난다 (한 턴이다)", lb.phase() == "choose" and lb.turn == 1 and lb.a.slot == 1 and lb.b.slot == 1
        and lb.mid is None, (lb.phase(), lb.turn))

    print("-- 쓰러뜨렸을 때")
    a = [mon("SCIZOR", ["UTURN"]), mon("SNORLAX", ["TACKLE"])]
    b = [mon("RATTATA", ["TACKLE"], level=5), mon("BLISSEY", ["TACKLE"])]
    lb = live(a, b)
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    chk("유턴으로 쓰러뜨려도 남은 상대가 있으면 내가 먼저 고른다", lb.can_act("a") and not lb.can_act("b")
        and not lb.b.mon.alive() and not lb.over, texts(ev))
    lb.choose("a", "switch", 1)
    ev = lb.resolve()
    chk("  그다음에 쓰러진 쪽이 다음 포켓몬을 고른다", lb.phase() == "switch" and lb.can_act("b") and not lb.can_act("a")
        and lb.a.slot == 1, (lb.phase(), texts(ev)))
    lb.choose("b", "switch", 1)
    lb.resolve()
    chk("  그러고 나면 다음 턴이다", lb.phase() == "choose" and lb.turn == 1 and lb.b.slot == 1)
    lb = live([mon("SCIZOR", ["UTURN"]), mon("SNORLAX", ["TACKLE"])], [mon("RATTATA", ["TACKLE"], level=5)])
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    chk("마지막 상대를 쓰러뜨리면 안 묻는다 (이겼다)", lb.over and lb.result == "a" and not lb.a.need_switch, texts(ev))

    print("-- 멈춘 동안의 기권")
    lb = live([mon("NINJASK", ["UTURN"]), mon("SNORLAX", ["TACKLE"])], [mon("BLISSEY", ["SEISMICTOSS"]), mon("SNORLAX", ["TACKLE"])])
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "SEISMICTOSS")
    lb.resolve()
    lb.choose("b", "forfeit")
    ev = lb.resolve()
    chk("기다리는 쪽이 기권하면 그 자리에서 끝난다", lb.over and lb.result == "a" and lb.reason == "forfeit", texts(ev))


def t_무작위():
    """교체 기술을 섞어 끝까지 돌린다 - 멈춘 자리에서 판이 굳지 않는다."""
    print("\n== 섞어 돌리기 ==")
    pool = [("NINJASK", ["UTURN", "BATONPASS", "SWORDSDANCE", "XSCISSOR"]), ("JOLTEON", ["VOLTSWITCH", "THUNDERBOLT"]),
            ("STARMIE", ["FLIPTURN", "SURF"]), ("GOLISOPOD", ["TACKLE", "LIQUIDATION"]), ("PERSIAN", ["PARTINGSHOT", "SLASH"]),
            ("SKARMORY", ["WHIRLWIND", "STEALTHROCK", "SPIKES"]), ("GARCHOMP", ["DRAGONTAIL", "EARTHQUAKE"]),
            ("ALAKAZAM", ["TELEPORT", "PSYCHIC"])]
    stuck = bad = pauses = 0
    for seed in range(60):
        rng = random.Random(seed)
        a = [mon(sp, mv) for sp, mv in rng.sample(pool, 4)]
        b = [mon(sp, mv) for sp, mv in rng.sample(pool, 4)]
        lb = L.LiveBattle(DEX, (1, "가", a), (2, "나", b), rng=random.Random(seed), max_turns=60)
        lb.resolve()
        for _i in range(600):
            if lb.over:
                break
            if rng.random() < 0.3:                                        # 가끔 저장했다 깨운다
                lb = L.LiveBattle.load(DEX, json.loads(json.dumps(lb.dump())))
            if lb.phase() == "switch" and lb.mid is not None:
                pauses += 1
            for w in ("a", "b"):
                if lb.can_act(w) and lb.side(w).choice is None:
                    if lb.phase() == "switch":
                        lb.choose(w, "switch", rng.choice(lb.valid_switches(w)))
                    else:
                        usable = [m["key"] for m in lb.moves_of(w) if not m.get("disabled")] if hasattr(lb, "moves_of") else []
                        try:
                            lb.choose(w, "move", rng.choice(usable or lb.bt.usable(lb.side(w).mon)))
                        except ValueError:
                            lb.choose(w, *lb.auto_choice(w))
            if not lb.ready():
                bad += 1
                break
            lb.resolve()
        else:
            stuck += 1
    chk("실시간 60판: 굳거나 고를 수 없는 자리가 없다 (턴 도중 멈춤 %d번)" % pauses, stuck == 0 and bad == 0 and pauses > 20,
        (stuck, bad, pauses))
    stuck = pauses = 0
    for seed in range(60):
        rng = random.Random(1000 + seed)
        party = [mon(sp, mv) for sp, mv in rng.sample(pool, 4)]
        team = [mon(sp, mv) for sp, mv in rng.sample(pool, 4)]
        tb = gym(team, party, seed=seed)
        for _i in range(600):
            if tb.over:
                break
            if rng.random() < 0.3:
                tb = TB.TrainerBattle.load(DEX, json.loads(json.dumps(tb.dump())))
            if tb.need_switch:
                pauses += tb.mid is not None
                tb.act("switch", rng.choice(tb.valid_switches()))
                continue
            try:
                tb.act("move", rng.choice(tb.bt.usable(tb.me)))
            except ValueError:
                tb.act("move", tb.bt.usable(tb.me)[0])
        else:
            stuck += 1
    chk("관장 60판: 끝까지 돈다 (턴 도중 멈춤 %d번)" % pauses, stuck == 0 and pauses > 20, (stuck, pauses))


def main():
    t_관장()
    t_실시간()
    t_무작위()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
