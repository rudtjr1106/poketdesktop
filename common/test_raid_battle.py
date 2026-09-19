# -*- coding: utf-8 -*-
"""레이드 엔진 검사 — 여럿이 보스 하나를 때리는 판.

    python common/test_raid_battle.py

서버도 DB 도 없이 common/raid_battle.py 만 본다.

제일 중요한 것 둘.
  · **턴 끝이 사람 수만큼 겹치지 않는가** - 보스의 화상 데미지가 세 명이면
    세 번 들어가고 날씨의 남은 턴도 세 번 줄면 판이 완전히 달라진다.
  · **저장/복원이 판을 그대로 되살리는가** - 라운드마다 DB 에 잤다 깬다.
"""
import copy
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import battle as B                        # noqa: E402
from common import pokelogic as P                     # noqa: E402
from common import raid_battle as R                   # noqa: E402

DEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "server", "data", "pokedex.json")
OK = FAIL = 0
DEX = None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(species, level, moves=None, ivs=31):
    sp = DEX.get(species)
    m = P.make_pokemon(sp, level, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, ivs) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    if moves:
        m["moves"] = list(moves)
    return m


def build(n=3, boss="MEWTWO", hp_mult=None, moves=("TACKLE",), rounds=15,
          double_from=4, seed=3, species="SNORLAX", level=50):
    players = [(i + 1, "P%d" % (i + 1),
                [R.leveled(mon(species, level, moves), level),
                 R.leveled(mon("PIDGEY", level, moves), level)])
               for i in range(n)]
    return R.RaidBattle(DEX, mon(boss, 60), players,
                        hp_mult=hp_mult if hp_mult is not None else 2 + 1.6 * n,
                        max_rounds=rounds, double_from=double_from,
                        rng=random.Random(seed))


def all_choose(rb, key="TACKLE"):
    for i, p in enumerate(rb.players):
        if p.playing():
            try:
                rb.choose(i, "move", key)
            except ValueError:
                rb.choose(i, *rb.auto_choice(i))


def main():
    global DEX
    DEX = P.Pokedex.load(DEX_PATH)

    print("=== 레벨 맞추기 ===")
    high = mon("SNORLAX", 100)
    low = mon("SNORLAX", 12)
    a, b = R.leveled(high, 50), R.leveled(low, 50)
    chk("높은 쪽은 내린다", a["level"] == 50, a["level"])
    chk("낮은 쪽은 올린다", b["level"] == 50, b["level"])
    chk("원본은 안 바뀐다", high["level"] == 100 and low["level"] == 12)
    chk("개체값·성격·기술은 그대로",
        a["ivs"] == high["ivs"] and a["nature"] == high["nature"]
        and a["moves"] == high["moves"])
    fa = B.Fighter(DEX, a)
    fb = B.Fighter(DEX, b)
    chk("같은 레벨이면 능력치도 같다", fa.base == fb.base or fa.level == fb.level)

    print("=== 판 만들기 ===")
    rb = build(3)
    one = B.Fighter(DEX, mon("MEWTWO", 60))
    chk("보스 체력이 배율만큼", abs(rb.boss.maxhp - one.maxhp * (2 + 1.6 * 3)) <= 1,
        "%d vs %d" % (rb.boss.maxhp, one.maxhp))
    chk("보스 공격력은 그대로", rb.boss.stat("atk") == one.stat("atk"))
    chk("체력이 가득", rb.boss.hp == rb.boss.maxhp)
    chk("사람마다 판이 하나씩", len(set(id(p.bt) for p in rb.players)) == 3)
    chk("보스는 하나를 같이 쓴다",
        all(p.bt.foe is rb.boss for p in rb.players))
    chk("판(날씨)도 하나", all(p.bt.field is rb.field for p in rb.players))
    ev = rb.start()
    chk("시작 연출", any(e["t"] == "intro" for e in ev))
    chk("전원이 나온다", sum(1 for e in ev if e["t"] == "switch") == 3)

    print("=== 여럿이 때린다 ===")
    rb = build(3, hp_mult=40)
    rb.start()
    before = rb.boss.hp
    all_choose(rb)
    rb.resolve()
    chk("체력이 한 곳에서 준다", rb.boss.hp < before, "%d -> %d" % (before, rb.boss.hp))
    chk("셋 다 기여가 잡힌다", sum(1 for p in rb.players if p.damage > 0) >= 2,
        [p.damage for p in rb.players])
    chk("기여 합이 깎인 만큼", abs(sum(p.damage for p in rb.players)
                                   - (before - rb.boss.hp)) <= 2,
        "%d vs %d" % (sum(p.damage for p in rb.players), before - rb.boss.hp))

    print("=== 턴 끝이 겹치지 않는가 ===")
    rb = build(3, hp_mult=200)          # 절반 아래로 안 내려가게 넉넉히
    rb.start()
    rb.boss.status = "burn"
    before = rb.boss.hp
    dmg0 = [p.damage for p in rb.players]
    all_choose(rb)
    rb.resolve()
    hit = sum(p.damage - d for p, d in zip(rb.players, dmg0))
    chip = (before - rb.boss.hp) - hit
    want = max(1, rb.boss.maxhp // 16)
    chk("화상은 한 라운드에 한 번만", chip == want,
        "%d (한 번이면 %d, 세 번이면 %d)" % (chip, want, want * 3))

    print("=== 날씨 ===")
    # 레지락(클리어바디)으로 본다. 그란돈처럼 날씨 특성이 있는 보스는
    # **특성이 이긴다** - 나온 순간의 가뭄이 타입 날씨를 덮는다.
    rb = build(3, boss="REGIROCK", hp_mult=200)
    rb.start()
    chk("보스 타입에 맞는 날씨", rb.field.weather == "sand", rb.field.weather)
    rb2 = build(3, boss="GROUDON", hp_mult=200)
    rb2.start()
    chk("날씨 특성이 있으면 그쪽이 이긴다", rb2.field.weather == "sun", rb2.field.weather)
    turns = rb.field.weather_turns
    all_choose(rb)
    rb.resolve()
    chk("남은 턴도 한 번만 준다", rb.field.weather_turns == turns - 1,
        "%d -> %d" % (turns, rb.field.weather_turns))

    print("=== 보호막 ===")
    rb = build(3, hp_mult=40)
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    ev = rb.resolve()
    chk("절반 아래로 내려가면 막이 선다", rb.shield is not None,
        rb.boss.hp / float(rb.boss.maxhp))
    chk("막이 선 것을 알린다", any(e["t"] == "shieldUp" for e in ev))
    hp_at = rb.boss.hp
    all_choose(rb)
    ev = rb.resolve()
    chk("막이 있으면 체력이 안 준다", rb.boss.hp == hp_at, "%d/%d" % (rb.boss.hp, hp_at))
    chk("막이 깎인다", rb.shield is None or rb.shield["hp"] < rb.shield["max"],
        rb.shield)
    chk("깎인 것을 알린다", any(e["t"] in ("shield", "shieldBreak") for e in ev))

    print("=== 막이 서 있는 동안 체력은 안 준다 ===")
    rb = build(3, hp_mult=400)          # 막이 두꺼워 한 라운드에 안 깨진다
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    rb.resolve()
    hp_at = rb.boss.hp
    sh_at = rb.shield["hp"]
    all_choose(rb)
    ev = rb.resolve()
    chk("체력이 그대로", rb.boss.hp == hp_at, "%d/%d" % (rb.boss.hp, hp_at))
    chk("막만 깎였다", rb.shield["hp"] < sh_at, (sh_at, rb.shield["hp"]))
    # 일어난 일에 적힌 체력도 같아야 한다 - 안 그러면 화면이 체력바를
    # 내렸다가 판이 끝날 때 도로 올린다 (막이 있는데 줄어드는 것처럼 보인다)
    said = [e for e in ev if (e.get("target") == "foe" if e.get("t") == "hit"
                              else e.get("who") == "foe") and "hp" in e]
    chk("적어 보낸 체력도 그대로", all(e["hp"] == hp_at for e in said),
        [(e["t"], e["hp"]) for e in said][:4])
    chk("맞았다는 말은 그대로 간다", any(e.get("t") == "hit" for e in ev))
    chk("막이 깎였다고 알린다", any(e.get("t") == "shield" for e in ev))

    print("=== 턴 끝 데미지도 막이 받는다 ===")
    rb = build(3, hp_mult=400)
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    rb.resolve()
    rb.boss.status = "burn"
    hp_at, sh_at = rb.boss.hp, rb.shield["hp"]
    all_choose(rb)
    rb.resolve()
    chk("화상이 있어도 체력은 그대로", rb.boss.hp == hp_at,
        "%d/%d" % (rb.boss.hp, hp_at))
    chk("화상만큼도 막에서 빠진다", sh_at - rb.shield["hp"] >= rb.boss.maxhp // 16,
        (sh_at, rb.shield["hp"], rb.boss.maxhp // 16))

    print("=== 막보다 큰 한 방 ===")
    rb = build(3, hp_mult=40)
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    rb.resolve()
    if rb.shield:
        rb.shield["hp"] = 1             # 막이 거의 다 깎였다
        hp_at = rb.boss.hp
        all_choose(rb)
        rb.resolve()
        chk("막이 깨진다", rb.shield is None)
        chk("넘친 만큼은 체력으로 들어간다", rb.boss.hp < hp_at,
            "%d -> %d" % (hp_at, rb.boss.hp))

    print("=== 막에 남은 라운드 ===")
    rb = build(3, hp_mult=400)
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    rb.resolve()
    v = rb.view()
    chk("남은 라운드를 준다", v["boss"]["shield"]["left"] == R.SHIELD_ROUNDS,
        v["boss"]["shield"])
    all_choose(rb)
    rb.resolve()
    chk("라운드가 지나면 줄어든다",
        rb.view()["boss"]["shield"]["left"] == R.SHIELD_ROUNDS - 1,
        rb.view()["boss"]["shield"])

    print("=== 막을 못 깨면 포효 ===")
    rb = build(3, hp_mult=400)          # 막이 너무 두꺼워 못 깬다
    rb.start()
    rb.boss.hp = int(rb.boss.maxhp * 0.45)
    all_choose(rb)
    rb.resolve()
    chk("막이 섰다", rb.shield is not None)
    seen_roar = False
    for _ in range(R.SHIELD_ROUNDS + 2):
        all_choose(rb)
        ev = rb.resolve()
        if any(e["t"] == "roar" for e in ev):
            seen_roar = True
            break
    chk("정해진 라운드가 지나면 포효", seen_roar)

    print("=== 분노 ===")
    rb = build(3, hp_mult=40)
    rb.start()
    rb.shielded_once = True             # 막은 건너뛴다
    rb.boss.hp = int(rb.boss.maxhp * 0.2)
    atk = rb.boss.stages["atk"]
    all_choose(rb)
    ev = rb.resolve()
    chk("1/4 아래면 분노", rb.raged, rb.boss.hp / float(rb.boss.maxhp))
    chk("공격이 오른다", rb.boss.stages["atk"] > atk, rb.boss.stages)
    raged_at = rb.boss.stages["atk"]
    if not rb.over:
        all_choose(rb)
        rb.resolve()
        chk("분노는 한 번뿐", rb.boss.stages["atk"] <= raged_at + 0, rb.boss.stages)

    print("=== 보스가 두 번 움직이는가 ===")
    rb3 = build(3, hp_mult=200)
    rb3.start()
    chk("3인이면 한 번", len([x for x in rb3._order() if x[0] == "boss"]) == 1)
    rb4 = build(4, hp_mult=200)
    rb4.start()
    chk("4인이면 두 번", len([x for x in rb4._order() if x[0] == "boss"]) == 2)
    chk("화면에도 실린다", rb4.view()["bossHits"] == 2)

    print("=== 쓰러지면 ===")
    rb = build(3, hp_mult=200)
    rb.start()
    p0 = rb.players[0]
    p0.mon.hp = 0
    p0.mon.ab["fainted"] = True
    ev = []
    rb._settle(ev)
    # **그 라운드가 끝나면서 바로 다음 포켓몬이 나온다.** 다음 라운드가
    # 시작할 때 내보내면 그 사람은 고를 기회를 못 받는다 (사용자 제보).
    chk("그 자리에서 다음 포켓몬이 나온다", p0.slot == 1, p0.slot)
    chk("나왔다고 알린다", any(e.get("t") == "switch" and e.get("p") == 0 for e in ev))
    chk("남은 마릿수를 센다", rb.view()["players"][0]["alive"] == 1,
        rb.view()["players"][0])
    chk("다음 라운드에 제 손으로 고를 수 있다", rb.view(0)["me"]["canAct"])
    chk("서버가 대신 고르지 않았다", p0.choice is None, p0.choice)
    before_auto = p0.auto
    rb.choose(0, "move", "TACKLE")
    for i in (1, 2):
        rb.choose(i, *rb.auto_choice(i))
    ev = rb.resolve()
    chk("고른 대로 쓴다", p0.auto == before_auto, "%d/%d" % (p0.auto, before_auto))

    print("=== 전멸 ===")
    rb = build(3, hp_mult=400)
    rb.start()
    for p in rb.players:
        for f in p.team:
            f.hp = 0
    rb._settle([])
    chk("모두 쓰러지면 진다", rb.over and rb.result == "lost", rb.result)

    print("=== 나가기 ===")
    rb = build(3, hp_mult=200)
    rb.start()
    ev = rb.leave(0)
    chk("나간 것을 알린다", any(e["t"] == "leave" for e in ev))
    chk("나간 사람은 안 움직인다", not rb.players[0].playing())
    chk("남은 사람은 계속", not rb.over)
    all_choose(rb)
    rb.resolve()
    chk("나간 사람 자리로는 아무 일도 안 일어난다", rb.players[0].damage == 0)
    rb.leave(1)
    rb.leave(2)
    chk("전부 나가면 끝", rb.over and rb.result == "lost", rb.result)

    print("=== 라운드 상한 ===")
    rb = build(3, hp_mult=4000, rounds=3)
    rb.start()
    while not rb.over:
        all_choose(rb)
        rb.resolve()
    chk("상한을 넘기면 실패", rb.result == "timeout", rb.result)
    chk("라운드가 상한에서 멈춘다", rb.round == 3, rb.round)

    print("=== 이기면 ===")
    rb = build(3, hp_mult=1)
    rb.start()
    rb.shielded_once = True
    rb.boss.hp = 1
    all_choose(rb)
    ev = rb.resolve()
    chk("보스를 쓰러뜨리면 이긴다", rb.over and rb.result == "won", rb.result)
    chk("끝난 것을 알린다", any(e["t"] == "over" for e in ev))
    chk("기여 순으로 줄 선다",
        [r[3] for r in rb.ranking()] == sorted([r[3] for r in rb.ranking()], reverse=True))

    print("=== 저장하고 되살리기 ===")
    rb = build(4, hp_mult=40, seed=11)
    rb.start()
    for _ in range(3):
        all_choose(rb)
        rb.resolve()
    rb.players[0].choice = ("move", "TACKLE")
    d = json.loads(json.dumps(rb.dump()))
    back = R.RaidBattle.load(DEX, copy.deepcopy(d))
    chk("보스 체력", back.boss.hp == rb.boss.hp and back.boss.maxhp == rb.boss.maxhp,
        "%d/%d vs %d/%d" % (back.boss.hp, back.boss.maxhp, rb.boss.hp, rb.boss.maxhp))
    chk("라운드", back.round == rb.round)
    chk("사람 수와 기여",
        [p.damage for p in back.players] == [p.damage for p in rb.players],
        [p.damage for p in back.players])
    chk("고른 것", back.players[0].choice == ("move", "TACKLE"), back.players[0].choice)
    chk("자리", [p.slot for p in back.players] == [p.slot for p in rb.players])
    chk("PP", [dict(f.pp) for f in back.players[0].team]
        == [dict(f.pp) for f in rb.players[0].team])
    chk("날씨", back.field.weather == rb.field.weather)
    chk("다시 저장해도 같다", back.dump() == d, "")
    # 난수까지 같아야 다음 라운드가 갈라지지 않는다
    for x in (rb, back):
        for i, p in enumerate(x.players):
            p.choice = None
        all_choose(x)
        x.resolve()
    chk("이어서 돌려도 같은 결과", back.boss.hp == rb.boss.hp,
        "%d vs %d" % (back.boss.hp, rb.boss.hp))

    print("=== 화면에 줄 것 ===")
    rb = build(3, hp_mult=40)
    rb.start()
    v = rb.view(1)
    chk("보스 칸", v["boss"]["maxhp"] == rb.boss.maxhp)
    chk("사람 칸 셋", len(v["players"]) == 3)
    chk("남의 기술은 안 보낸다", "moves" not in v["players"][0]["mon"])
    chk("내 기술은 보낸다", len(v["me"]["moves"]) >= 1)
    chk("내 파티도", len(v["me"]["team"]) == 2)
    chk("내 자리", v["me"]["index"] == 1)
    chk("고르기 전", v["players"][1]["chosen"] is False)
    rb.choose(1, "move", "TACKLE")
    chk("고른 뒤", rb.view(1)["players"][1]["chosen"] is True)
    chk("누가 안 골랐는지", rb.waiting() == [0, 2], rb.waiting())
    chk("다 골라야 준비됨", not rb.ready())
    rb.choose(0, "move", "TACKLE")
    rb.choose(2, "move", "TACKLE")
    chk("다 고르면 준비됨", rb.ready())

    print("=== 못 고르는 것 ===")
    rb = build(3, hp_mult=40, moves=("TACKLE",))
    rb.start()
    try:
        rb.choose(0, "move", "HYPERBEAM")
        chk("안 배운 기술은 거절", False)
    except ValueError as e:
        chk("안 배운 기술은 거절", "배우지" in str(e), str(e))
    try:
        rb.choose(0, "switch", 0)
        chk("지금 나와 있는 자리로는 못 바꾼다", False)
    except ValueError:
        chk("지금 나와 있는 자리로는 못 바꾼다", True)
    rb.players[0].team[1].hp = 0
    try:
        rb.choose(0, "switch", 1)
        chk("쓰러진 자리로는 못 바꾼다", False)
    except ValueError:
        chk("쓰러진 자리로는 못 바꾼다", True)

    print("=== 교체 ===")
    rb = build(3, hp_mult=200)
    rb.start()
    rb.choose(0, "switch", 1)
    rb.choose(1, "move", "TACKLE")
    rb.choose(2, "move", "TACKLE")
    ev = rb.resolve()
    # 바꾼 뒤 그 포켓몬이 그 라운드에 쓰러지면 다음 것이 또 나오므로(_settle),
    # 마지막 자리로 보지 않고 **바꿨다는 일**로 본다.
    outs = [e for e in ev if e["t"] == "switch" and e.get("p") == 0]
    chk("교체가 된다", outs and outs[0]["slot"] == 1, [e.get("slot") for e in outs])
    chk("교체를 알린다", any(e["t"] == "recall" and e.get("p") == 0 for e in ev))
    chk("교체한 사람은 공격을 안 한다", rb.players[0].damage == 0)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
