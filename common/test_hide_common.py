# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7) 의 공통 규칙 (common/hide.py) 과 숨은 포켓몬 표 (pokelogic.Pokedex.roll_hide).

    python common/test_hide_common.py

못 박는 것:

  1. 숨는 종(HIDERS)은 설계 목록 30종 그대로, 모두 도감에 있고 spawnable. HIDE_SHARE 0.5 · HIDE_HIDDEN_RATE 4.
  2. make_pokemon 의 숨겨진 특성 확률은 부르는 쪽이 주지 않으면 지금 그대로 1/128 - 같은 씨앗이면 바이트 단위로 같다.
  3. 숨는 표(hide_pool)는 HIDERS 만, 레벨 · 종족값 상한 · 뺄 종은 풀숲 표와 같게. 캐시 열쇠가 달라 풀숲 표와 섞이지 않는다
     (HIDERS 를 바꾸면 다른 표).
  4. roll_hide: 약 절반은 숨는 표에서, 나머지는 평소 표(할로윈 · 스프레이 없음). 숨겨진 특성 1/4 (있는 종만),
     이로치 확률은 부르는 쪽이 준 그대로. 숨는 표가 비면 평소 표로.
"""
import inspect
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import fishing as F                             # noqa: E402
from common import hide as H                                # noqa: E402
from common import pokelogic as P                            # noqa: E402

OK = FAIL = 0

# 설계 목록 (design-notes/2026-11-27-hide-and-seek-plan.md 'Global Constraints') - 여기서 한 번 더 적어 둔다.
# 목록이 바뀌면 이 검사가 먼저 알려 준다.
PLAN = ("GASTLY HAUNTER GENGAR MISDREAVUS MISMAGIUS SABLEYE SHUPPET BANETTE DUSKULL DUSCLOPS DUSKNOIR DRIFLOON "
        "DRIFBLIM SPIRITOMB ZORUA ZOROARK KECLEON MIMIKYU MURKROW HONCHKROW PHANTUMP TREVENANT PUMPKABOO GOURGEIST "
        "SINISTEA POLTEAGEIST GREAVARD SANDYGAST DITTO SMEARGLE").split()


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def load_dex():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


def cap(lv):
    return 330 + lv * 8                      # 서버 풀숲과 같은 종족값 상한 (config.WILD_BST_*)


def t_hiders(dex):
    print("[숨는 종]")
    chk("frozenset 이다 (캐시 열쇠가 된다)", isinstance(H.HIDERS, frozenset), type(H.HIDERS))
    chk("설계 목록 30종 그대로", H.HIDERS == frozenset(PLAN) and len(PLAN) == 30, sorted(H.HIDERS ^ frozenset(PLAN)))
    missing = sorted(k for k in H.HIDERS if not dex.get(k))
    chk("모두 도감에 있다", not missing, missing)
    shut = sorted(k for k in H.HIDERS if dex.get(k) and not dex.get(k).get("spawnable"))
    chk("모두 spawnable (풀숲에 나오는 종)", not shut, shut)
    light = sorted(k for k in H.HIDERS if dex.get(k) and not dex.get(k).get("weight"))
    chk("모두 가중치가 있다 (표에서 0 이 아니다)", not light, light)
    fish = sorted(H.HIDERS & F.FISH_ONLY)
    chk("낚시 위주 종과 겹치지 않는다", not fish, fish)
    chk("HIDE_SHARE = 0.5", H.HIDE_SHARE == 0.5, H.HIDE_SHARE)
    chk("HIDE_HIDDEN_RATE = 4 (숨겨진 특성 1/4)", H.HIDE_HIDDEN_RATE == 4, H.HIDE_HIDDEN_RATE)


def t_make_pokemon_default(dex):
    print("[make_pokemon 숨겨진 특성 확률 - 기본은 그대로]")
    sig = inspect.signature(P.make_pokemon)
    chk("hidden_rate 인자가 있고 기본은 HIDDEN_ABILITY_RATE (128)",
        "hidden_rate" in sig.parameters and sig.parameters["hidden_rate"].default == P.HIDDEN_ABILITY_RATE == 128,
        str(sig))
    sp = dex.get("SHUPPET")
    same = all(P.make_pokemon(sp, 10, random.Random(s)) == P.make_pokemon(sp, 10, random.Random(s), hidden_rate=128)
               for s in range(300))
    chk("같은 씨앗이면 hidden_rate 를 안 줘도 · 128 을 줘도 똑같다 (300개)", same)
    old = sum(1 for s in range(4000) if P.roll_ability(sp, random.Random(s))[1])
    got =sum(1 for s in range(4000) if P.make_pokemon(sp, 10, random.Random(s))["hiddenAbility"])
    chk("기본 확률은 약 1/128 (4000개 중 %d)" % got, 10 <= got <= 60, got)
    chk("  roll_ability 기본도 1/128 (4000개 중 %d)" % old, 10 <= old <= 60, old)
    every = all(P.make_pokemon(sp, 10, random.Random(s), hidden_rate=1)["hiddenAbility"] for s in range(50))
    chk("hidden_rate=1 이면 늘 숨겨진 특성", every)
    quarter = sum(1 for s in range(4000) if P.make_pokemon(sp, 10, random.Random(s), hidden_rate=4)["hiddenAbility"])
    chk("hidden_rate=4 이면 약 1/4 (4000개 중 %d)" % quarter, 850 <= quarter <= 1150, quarter)
    none = dex.get("GASTLY")                 # 숨겨진 특성이 없는 종
    plain = all(not P.make_pokemon(none, 10, random.Random(s), hidden_rate=1)["hiddenAbility"] for s in range(50))
    chk("숨겨진 특성이 없는 종은 hidden_rate=1 이어도 평소 특성", plain)


def t_hide_pool(dex):
    print("[숨는 표 - hide_pool]")
    lv = 20
    pool, cum, total = dex.hide_pool(lv, cap(lv), F.FISH_ONLY)
    names = [s["internal"] for s in pool]
    chk("HIDERS 만 있다", names and set(names) <= H.HIDERS, sorted(set(names) - H.HIDERS))
    ref = [s for s in dex.species if s["internal"] in H.HIDERS and s.get("spawnable")
           and s.get("minLevel", 1) <= lv and dex.bst(s) <= cap(lv)]
    chk("레벨 · 종족값 상한은 풀숲 표와 같게 (종 · 가중치 합)",
        names == [s["internal"] for s in ref] and total == sum(s.get("weight", 0) for s in ref),
        (names, [s["internal"] for s in ref]))
    chk("  Lv20 에는 팬텀(Lv41~) · 무우마직(종족값 495 > 490) 이 없다", "GENGAR" not in names and "MISMAGIUS" not in names)
    cut = dex.hide_pool(lv, cap(lv), frozenset(("SHUPPET", "DUSKULL")))[0]
    chk("뺄 종(exclude)은 숨는 표에서도 빠진다", not ({"SHUPPET", "DUSKULL"} & set(s["internal"] for s in cut)),
        [s["internal"] for s in cut])
    base = dex.spawn_pool(lv, cap(lv), None, F.FISH_ONLY)[0]
    chk("캐시 열쇠가 다르다 - 같은 레벨 풀숲 표와 다른 표", base is not pool and len(base) > len(pool))
    again = dex.hide_pool(lv, cap(lv), F.FISH_ONLY)[0]
    chk("  다시 부르면 같은 캐시", again is pool)
    chk("  풀숲 표도 그대로 (HIDERS 가 아닌 종이 있다)",
        dex.spawn_pool(lv, cap(lv), None, F.FISH_ONLY)[0] is base and any(s["internal"] not in H.HIDERS for s in base))
    real = H.HIDERS
    try:
        H.HIDERS = frozenset(("DITTO",))
        tiny = dex.hide_pool(lv, cap(lv), F.FISH_ONLY)[0]
        chk("HIDERS 를 바꾸면 다른 표 (캐시 열쇠에 숨는 종이 들어간다)", [s["internal"] for s in tiny] == ["DITTO"],
            [s["internal"] for s in tiny])
    finally:
        H.HIDERS = real
    chk("  되돌리면 원래 표", dex.hide_pool(lv, cap(lv), F.FISH_ONLY)[0] is pool)
    low = dex.hide_pool(2, 10, frozenset())        # 상한이 너무 좁으면 풀숲처럼 상한을 푼다
    chk("종족값 상한이 너무 좁아 비면 상한을 푼다 (풀숲 표와 같다)", low[0] and low[2] > 0, len(low[0]))


def t_roll_hide(dex):
    print("[숨은 포켓몬 하나 - roll_hide]")
    lv = 20
    rng = random.Random(20261127)
    mons = [dex.roll_hide(lv, lv, rng, max_bst=cap(lv), exclude=F.FISH_ONLY,
                          hidden_rate=H.HIDE_HIDDEN_RATE, shiny_rate=P.SHINY_RATE) for _ in range(3000)]
    chk("늘 한 마리 (None 없음)", all(m for m in mons))
    base, _c, total = dex.spawn_pool(lv, cap(lv), None, F.FISH_ONLY)
    p = sum(s.get("weight", 0) for s in base if s["internal"] in H.HIDERS) / float(total)
    want = H.HIDE_SHARE + (1 - H.HIDE_SHARE) * p
    got = sum(1 for m in mons if m["species"] in H.HIDERS) / float(len(mons))
    chk("숨는 종 몫 %.3f ≈ %.3f (절반 + 평소 표에서 나온 숨는 종)" % (got, want), abs(got - want) < 0.04, (got, want))
    chk("낚시 위주 종 없음", not [m["species"] for m in mons if m["species"] in F.FISH_ONLY])
    chk("레벨은 준 범위 (Lv20)", all(m["level"] == lv for m in mons), set(m["level"] for m in mons))
    has = [m for m in mons if dex.get(m["species"]).get("hidden")]
    rate = sum(1 for m in has if m["hiddenAbility"]) / float(len(has))
    chk("숨겨진 특성 ≈ 1/4 (있는 종 %d마리 중 %.3f)" % (len(has), rate), 0.21 <= rate <= 0.29, rate)
    chk("숨겨진 특성이 없는 종은 늘 평소 특성",
        all(not m["hiddenAbility"] for m in mons if not dex.get(m["species"]).get("hidden")))
    shiny = [dex.roll_hide(lv, lv, rng, max_bst=cap(lv), shiny_rate=1)["shiny"] for _ in range(30)]
    chk("이로치 확률은 부르는 쪽이 준 그대로 (shiny_rate=1 이면 다 이로치)", all(shiny))
    none = [dex.roll_hide(lv, lv, rng, max_bst=cap(lv), exclude=H.HIDERS) for _ in range(200)]
    chk("숨는 표가 비면 평소 표로 (HIDERS 를 다 빼도 한 마리, 숨는 종은 0)",
        all(none) and not [m["species"] for m in none if m["species"] in H.HIDERS])
    sig = inspect.signature(dex.roll_hide)
    chk("shiny_rate 기본은 SHINY_RATE", sig.parameters["shiny_rate"].default == P.SHINY_RATE, str(sig))
    # hidden_rate 를 안 주면 HIDE_HIDDEN_RATE (pokelogic 은 hide 를 늦게 부르므로 기본값은 None 으로 두고 안에서 채운다)
    plain = [dex.roll_hide(lv, lv, rng, max_bst=cap(lv)) for _ in range(2000)]
    has = [m for m in plain if dex.get(m["species"]).get("hidden")]
    rate = sum(1 for m in has if m["hiddenAbility"]) / float(len(has))
    chk("  hidden_rate 를 안 주면 HIDE_HIDDEN_RATE (%.3f ≈ 0.25)" % rate, 0.21 <= rate <= 0.29, rate)
    # 진화한 모습은 풀숲과 같게 (grown_form) - Lv45 해골몽은 미라몽으로 나온다
    hi = [dex.roll_hide(45, 45, random.Random(s), max_bst=cap(45)) for s in range(400)]
    chk("레벨에 맞게 진화한 모습 (Lv45 에 해골몽 · 어둠대신 · 흔들풍손 · 조로아는 없다)",
        not [m["species"] for m in hi if m["species"] in ("DUSKULL", "SHUPPET", "DRIFLOON", "ZORUA")],
        sorted(set(m["species"] for m in hi if m["species"] in ("DUSKULL", "SHUPPET", "DRIFLOON", "ZORUA"))))


def main():
    dex = load_dex()
    for t in (t_hiders, t_make_pokemon_default, t_hide_pool, t_roll_hide):
        try:
            t(dex)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            chk("%s 이 끝까지 돈다" % t.__name__, False, repr(e))
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
