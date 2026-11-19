# -*- coding: utf-8 -*-
"""붙잡혀 있는 것이 화면에 보이나 (게시판 #664 뒤, 11/19). 서버 없이 돈다.

    python common/test_trap_view.py

회오리불꽃이 지속 데미지도 교체 봉인도 안 된다는 제보가 왔다. 진짜 원인은 엔진에 있었지만(따로 고쳤다),
화면에는 묶였는지가 하나도 안 보이고 교체 단추도 켜져 있어서, 묶기가 걸렸는지 실패했는지를 알 길이 없었다.
엔진의 판정(statusmoves.trapped)은 그대로 두고, **view 에 싣는 것**만 본다.

  · 관장(trainer_battle) view()["me"]: trapped (교체가 막혔나) · noSwitch (지금 스스로 바꿀 수 없는 까닭 - 화면에 띄울 문구)
    view()["foe"]: trapped (보이는 것만으로 - 상대의 아름다운허물은 안 드러낸다)
  · 나와 있는 포켓몬(team[slot])의 bound: 조이기류 기술 이름 · 남은 턴.
    **남은 턴은 내가 건 것만 보인다** - 상대가 건 것의 턴 수는 상대의 끈기갈고리손톱(8턴, 아니면 5~6)을 드러낸다.
  · 실시간(live_battle) view(who)["me"]: 같은 것 + switches 는 붙잡혀 있으면 빈 목록 (옛 앱도 단추를 잠근다).
    다음 포켓몬을 골라야 할 때(phase=switch)는 그대로다.
  · 교체 판정은 그대로다 - 붙잡혀 있으면 서버가 여전히 거절한다.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import live_battle as L          # noqa: E402
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


def mon(dex, species, level, moves, seed=1, held=None):
    m = P.make_pokemon(dex.get(species), level, random.Random(seed), shiny_rate=10 ** 9,
                       ivs=dict((s, 20) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    return m


def gym(dex, me_held=None, foe_held=None, foe_moves=("SPLASH",), me_moves=("SPLASH",), seed=5):
    """내 쪽 둘(바꿀 데가 있다) · 상대 하나 (AI 가 바꾸지 않는다)."""
    mine = [mon(dex, "SNORLAX", 50, me_moves, 1, me_held), mon(dex, "PIDGEY", 50, ["TACKLE"], 2)]
    t = {"name": "검사", "team": [mon(dex, "BLISSEY", 50, foe_moves, 3, foe_held)]}
    tb = TB.TrainerBattle(dex, mine, t, random.Random(seed))
    tb.start()
    return tb


def active(side):
    return side["team"][side["slot"]]


def can_switch_now(tb):
    try:
        cp = TB.TrainerBattle.load(tb.dex, json.loads(json.dumps(tb.dump())))
        cp.act("switch", 1)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- 관장
def t_관장_내가_붙잡힘(dex):
    print("-- 관장: 내 포켓몬이 회오리불꽃에 붙잡혀 있다")
    tb = gym(dex)
    tb.me.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    v = tb.view()
    me = v["me"]
    chk("me.trapped = True", me.get("trapped") is True, me.get("trapped"))
    chk("me.noSwitch 에 기술 이름과 '교체할 수 없다'",
        "회오리불꽃" in (me.get("noSwitch") or "") and "교체할 수 없다" in (me.get("noSwitch") or ""), me.get("noSwitch"))
    b = active(me).get("bound") or {}
    chk("나와 있는 포켓몬의 bound: 기술 열쇠 · 이름", b.get("move") == "FIRESPIN" and b.get("moveKr") == "회오리불꽃", b)
    chk("상대가 건 것은 남은 턴을 안 보인다 (끈기갈고리손톱을 드러내지 않는다)", "turns" in b and b["turns"] is None, b)
    chk("뒤에 있는 포켓몬에는 bound 가 없다", not v["me"]["team"][1].get("bound"), v["me"]["team"][1].get("bound"))
    chk("교체 판정은 그대로 - 서버가 거절한다", not can_switch_now(tb))
    json.dumps(v)
    chk("view 는 JSON 으로 나간다", True)


def t_관장_상대가_붙잡힘(dex):
    print("-- 관장: 상대가 내 바다회오리에 붙잡혀 있다")
    tb = gym(dex)
    tb.foe.cond["bound"] = {"turns": 4, "by": "me", "move": "WHIRLPOOL"}
    v = tb.view()
    b = active(v["foe"]).get("bound") or {}
    chk("상대 포켓몬의 bound: 바다회오리 · 남은 4턴 (내가 건 것)",
        b.get("moveKr") == "바다회오리" and b.get("turns") == 4, b)
    chk("foe.trapped = True", v["foe"].get("trapped") is True, v["foe"].get("trapped"))
    chk("내 쪽은 멀쩡하다: trapped False · noSwitch 없음",
        v["me"].get("trapped") is False and v["me"].get("noSwitch") is None,
        (v["me"].get("trapped"), v["me"].get("noSwitch")))
    chk("foe 에는 noSwitch 를 싣지 않는다 (상대의 교체 판정은 비밀)", "noSwitch" not in v["foe"], list(v["foe"]))


def t_관장_아무것도_없음(dex):
    print("-- 관장: 붙잡힌 것이 없다")
    tb = gym(dex)
    v = tb.view()
    chk("me.trapped False · noSwitch None", v["me"].get("trapped") is False and v["me"].get("noSwitch") is None,
        (v["me"].get("trapped"), v["me"].get("noSwitch")))
    chk("foe.trapped False", v["foe"].get("trapped") is False, v["foe"].get("trapped"))
    chk("bound 없음", not active(v["me"]).get("bound") and not active(v["foe"]).get("bound"))
    chk("바꿀 수 있다", can_switch_now(tb))


def t_관장_아름다운허물(dex):
    print("-- 관장: 아름다운허물")
    tb = gym(dex, me_held="SHEDSHELL")
    tb.me.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    v = tb.view()
    chk("내가 지녔으면 trapped False · noSwitch 없음 (바꿀 수 있다)",
        v["me"].get("trapped") is False and v["me"].get("noSwitch") is None and can_switch_now(tb),
        (v["me"].get("trapped"), v["me"].get("noSwitch")))
    chk("  붙잡힌 것(지속 데미지)은 그대로 보인다", (active(v["me"]).get("bound") or {}).get("moveKr") == "회오리불꽃",
        active(v["me"]).get("bound"))
    tb = gym(dex, foe_held="SHEDSHELL")
    tb.foe.cond["bound"] = {"turns": 4, "by": "me", "move": "FIRESPIN"}
    v = tb.view()
    chk("상대가 지녔어도 foe.trapped True (상대의 도구를 드러내지 않는다)", v["foe"].get("trapped") is True,
        v["foe"].get("trapped"))


def t_관장_여러_까닭(dex):
    print("-- 관장: 검은눈빛 · 문어굳히기 · 뿌리박기 · 페어리록 · 반동")
    for name, setup, word in (
            ("검은눈빛", lambda tb: tb.me.cond.__setitem__("trapped", "foe"), "붙잡혀"),
            ("문어굳히기", lambda tb: tb.me.cond.__setitem__("octolock", "foe"), "문어굳히기"),
            ("뿌리박기", lambda tb: tb.me.cond.__setitem__("ingrain", True), "뿌리"),
            ("페어리록", lambda tb: tb.bt.field.rooms.__setitem__("fairylock", 2), "페어리록")):
        tb = gym(dex)
        setup(tb)
        v = tb.view()
        chk("%s: trapped True · noSwitch 에 '%s'" % (name, word),
            v["me"].get("trapped") is True and word in (v["me"].get("noSwitch") or ""),
            (v["me"].get("trapped"), v["me"].get("noSwitch")))
        chk("  %s: 서버도 거절한다" % name, not can_switch_now(tb))
        chk("  %s: trap_kind 와 trapped 가 같은 답" % name,
            bool(SM.trap_kind(tb.bt, tb.me)) == SM.trapped(tb.bt, tb.me), SM.trap_kind(tb.bt, tb.me))
    tb = gym(dex)
    tb.me.cond["recharge"] = True
    v = tb.view()
    chk("반동으로 쉬는 턴: trapped False 지만 noSwitch 는 그 까닭",
        v["me"].get("trapped") is False and v["me"].get("noSwitch") == SM.must_stay(tb.me),
        (v["me"].get("trapped"), v["me"].get("noSwitch")))


def t_관장_교체할_차례(dex):
    print("-- 관장: 다음 포켓몬을 골라야 할 때 (유턴으로 물러나는 중)")
    tb = gym(dex)
    tb.me.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    tb.need_switch = True
    v = tb.view()
    chk("need_switch 면 noSwitch 없음 (붙잡혀 있어도 고른다)", v["me"].get("noSwitch") is None, v["me"].get("noSwitch"))


def t_관장_실제로_걸기(dex):
    print("-- 관장: 실제로 회오리불꽃을 주고받는다")
    tb = gym(dex, me_moves=("FIRESPIN",), foe_moves=("SPLASH",))
    for _ in range(12):
        if tb.foe.cond.get("bound"):
            break
        tb.act("move", "FIRESPIN")
    left = (tb.foe.cond.get("bound") or {}).get("turns")
    b = active(tb.view()["foe"]).get("bound") or {}
    chk("내가 건 회오리불꽃: 상대 이름표에 이름 · 남은 턴 (엔진의 값과 같다)",
        left is not None and b.get("moveKr") == "회오리불꽃" and b.get("turns") == left, (b, left))
    # 남은 턴이 말 그대로인가: 보인 N 턴이 지나는 턴 끝에 풀린다 (b7169e1 부터 묶기는 5~6턴 - 건 턴 끝에 하나 줄어 4~5)
    tb = gym(dex, me_moves=("FIRESPIN", "SPLASH"), foe_moves=("SPLASH",))
    for _ in range(12):
        if tb.foe.cond.get("bound"):
            break
        tb.act("move", "FIRESPIN")
    shown = (active(tb.view()["foe"]).get("bound") or {}).get("turns") or 0
    seen = [shown]
    for _ in range(shown - 1):
        tb.act("move", "SPLASH")
        seen.append((active(tb.view()["foe"]).get("bound") or {}).get("turns"))
    tb.act("move", "SPLASH")
    gone = active(tb.view()["foe"]).get("bound")
    chk("남은 턴: 건 턴 끝에 4~5 · 한 턴에 하나씩 줄어 1 다음 턴 끝에 풀린다",
        shown in (4, 5) and seen == list(range(shown, 0, -1)) and gone is None, (seen, gone))
    tb = gym(dex, me_moves=("SPLASH",), foe_moves=("FIRESPIN",))
    for _ in range(12):
        if tb.me.cond.get("bound") or tb.over:
            break
        tb.act("move", "SPLASH")
    v = tb.view()
    chk("상대가 건 회오리불꽃: 교체가 잠기고 까닭이 보인다",
        bool(tb.me.cond.get("bound")) and v["me"].get("trapped") is True
        and "회오리불꽃" in (v["me"].get("noSwitch") or ""), v["me"].get("noSwitch"))
    cp = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("저장했다 되살려도 view 가 같다", cp.view() == v)


# ---------------------------------------------------------------- 실시간
def live(dex, a_held=None):
    a = [mon(dex, "SNORLAX", 50, ["SPLASH"], 1, a_held), mon(dex, "PIDGEY", 50, ["TACKLE"], 2)]
    b = [mon(dex, "BLISSEY", 50, ["SPLASH"], 3), mon(dex, "RATTATA", 50, ["TACKLE"], 4)]
    lb = L.LiveBattle(dex, (1, "가", a), (2, "나", b), rng=random.Random(5))
    lb.start()
    return lb


def t_실시간(dex):
    print("-- 실시간: a 가 b 의 회오리불꽃에 붙잡혀 있다")
    lb = live(dex)
    lb.a.mon.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    va, vb = lb.view("a"), lb.view("b")
    chk("a: switches 가 빈 목록 (옛 앱도 교체 단추를 잠근다)", va["me"].get("switches") == [], va["me"].get("switches"))
    chk("a: trapped True · noSwitch 에 회오리불꽃",
        va["me"].get("trapped") is True and "회오리불꽃" in (va["me"].get("noSwitch") or ""),
        (va["me"].get("trapped"), va["me"].get("noSwitch")))
    b = active(va["me"]).get("bound") or {}
    chk("a: 내 포켓몬의 bound - 남은 턴은 안 보인다 (상대가 걸었다)", b.get("moveKr") == "회오리불꽃" and b.get("turns") is None, b)
    b = active(vb["foe"]).get("bound") or {}
    chk("b: 상대 포켓몬의 bound - 내가 건 것이라 남은 3턴", b.get("moveKr") == "회오리불꽃" and b.get("turns") == 3, b)
    chk("b: foe.trapped True", vb["foe"].get("trapped") is True, vb["foe"].get("trapped"))
    chk("b: 내 쪽은 바꿀 수 있다", vb["me"].get("switches") == [1] and vb["me"].get("noSwitch") is None,
        (vb["me"].get("switches"), vb["me"].get("noSwitch")))
    try:
        lb.choose("a", "switch", 1)
        refused = False
    except ValueError:
        refused = True
    chk("교체 판정은 그대로 - 서버가 거절한다", refused)
    json.dumps(va)
    json.dumps(vb)

    print("-- 실시간: 다음 포켓몬을 골라야 할 때")
    lb = live(dex)
    lb.a.mon.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    lb.a.need_switch = True
    va = lb.view("a")
    chk("phase=switch 면 switches 는 그대로 · noSwitch 없음",
        va["phase"] == "switch" and va["me"].get("switches") == [1] and va["me"].get("noSwitch") is None,
        (va["phase"], va["me"].get("switches"), va["me"].get("noSwitch")))

    print("-- 실시간: 아름다운허물 · 반동")
    lb = live(dex, a_held="SHEDSHELL")
    lb.a.mon.cond["bound"] = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
    va, vb = lb.view("a"), lb.view("b")
    chk("a 가 지녔으면 switches 그대로 · trapped False", va["me"].get("switches") == [1]
        and va["me"].get("trapped") is False, (va["me"].get("switches"), va["me"].get("trapped")))
    chk("b 에게는 그래도 foe.trapped True (도구를 드러내지 않는다)", vb["foe"].get("trapped") is True)
    lb = live(dex)
    lb.a.mon.cond["recharge"] = True
    va = lb.view("a")
    chk("반동으로 쉬는 턴: switches 빈 목록 · noSwitch 는 그 까닭",
        va["me"].get("switches") == [] and va["me"].get("noSwitch") == SM.must_stay(lb.a.mon),
        (va["me"].get("switches"), va["me"].get("noSwitch")))


def main():
    dex = load_dex()
    t_관장_내가_붙잡힘(dex)
    t_관장_상대가_붙잡힘(dex)
    t_관장_아무것도_없음(dex)
    t_관장_아름다운허물(dex)
    t_관장_여러_까닭(dex)
    t_관장_교체할_차례(dex)
    t_관장_실제로_걸기(dex)
    t_실시간(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
