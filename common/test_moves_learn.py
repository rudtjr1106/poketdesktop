# -*- coding: utf-8 -*-
"""기술을 배우고 잊는 규칙 — 엔진만. 서버 없이 돈다.

    python common/test_moves_learn.py

세 가지를 본다.

1. **진화하면서 배우는 기술이 도감에 있다.** 도감의 레벨 0 이 그것이다
   (tools/build_pokedex.py). 그동안 빌더가 `lv <= 0` 으로 통째로 버려서,
   버터플이 바람일으키기를, 독침붕이 마구찌르기를 영영 못 배웠다.
   레벨업으로는 절대 안 걸린다 - 레벨이 0 보다 커지는 순간은 없으니까.

2. **하나 남은 공격기는 안 밀어낸다.** 버터플이 그랬다. 독가루,
   저리가루, 수면가루, 초음파를 연달아 배우면서 몸통박치기가 밀려나,
   Lv21~31 동안 때릴 방법이 몸부림밖에 없었다.

3. 서버와 같은 규칙으로 키웠을 때, **상태이상 기술만 넉 장 들고 있는
   포켓몬이 안 나온다.** 남는 것은 본가도 그런 종뿐이다 (캐이시는
   순간이동만, 잉어킹은 튀어오르기만 안다).
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import pokelogic as P                           # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def section(t):
    print()
    print("=== %s ===" % t)


# 본가도 때릴 방법이 없는 종들. 이건 결함이 아니다.
NO_ATTACK_OK = {"ABRA", "MAGIKARP", "WAILMER", "SPOINK", "MILCERY", "COSMOG",
                "WYNAUT", "TYROGUE", "IGGLYBUFF", "AZURILL"}


def load():
    p = os.path.join(os.path.dirname(HERE), "server", "data", "pokedex.json")
    return P.Pokedex(json.load(io.open(p, encoding="utf-8"))), \
        json.load(io.open(p, encoding="utf-8"))


def evo_level(sp):
    for e in (sp.get("evo") or []):
        if e.get("level"):
            return e["level"], e["to"]
    return None, None


def main():
    dex, raw = load()
    sps = dict((s["internal"], s) for s in raw["species"])

    section("진화하면서 배우는 기술이 도감에 있다")
    have = [k for k, sp in sps.items() if P.evolution_moves(sp)]
    chk("레벨 0 기술을 가진 종이 있다", len(have) > 200, len(have))
    for key, want in (("BUTTERFREE", "바람일으키기"),
                      ("BEEDRILL", "마구찌르기"),
                      ("METAPOD", "단단해지기"),
                      ("GYARADOS", "물기")):
        got = [dex.move_name(m) for m in P.evolution_moves(sps[key])]
        chk("%s 이(가) %s 을(를) 진화하며 배운다" % (sps[key]["kr"], want),
            want in got, got)
    # 레벨업으로는 절대 안 걸린다 - evolution.apply 가 넣어 줘야 한다.
    for key in have[:50]:
        z = [lv for lv, _m in sps[key]["moves"] if lv <= 0]
        chk("레벨 0 은 레벨업 구간에 안 걸린다 (%s)" % key,
            all(not (0 < lv <= 100) for lv in z), z)

    section("하나 남은 공격기는 안 밀어낸다")
    # 몸통박치기 하나만 공격기고 나머지는 전부 상태이상.
    atk, st1, st2, st3, st4 = ("TACKLE", "GROWL", "HARDEN", "POISONPOWDER",
                               "STUNSPORE")
    keep, forgot = P.trim_moves(dex, [atk, st1, st2, st3, st4])
    chk("공격기가 남는다", atk in keep, keep)
    chk("대신 그 다음으로 오래된 것이 밀린다", forgot == [st1], forgot)
    # 공격기가 둘이면 평소대로 제일 오래된 것부터.
    keep, forgot = P.trim_moves(dex, [atk, "SCRATCH", st1, st2, st3])
    chk("공격기가 둘이면 오래된 것부터 민다", forgot == [atk], forgot)
    # 넉 장 이하면 아무것도 안 민다.
    keep, forgot = P.trim_moves(dex, [atk, st1, st2])
    chk("넉 장 이하는 그대로", (keep, forgot) == ([atk, st1, st2], []),
        (keep, forgot))
    # 전부 상태이상이면 어쩔 수 없이 오래된 것부터.
    keep, forgot = P.trim_moves(dex, [st1, st2, st3, st4, "SING"])
    chk("전부 상태이상이면 오래된 것부터", forgot == [st1], forgot)

    section("서버와 같은 규칙으로 키워 본다")

    def grow(start, top=50):
        """deps._learn + evolution.apply 와 같은 순서."""
        sp = sps[start]
        lv = max(1, sp.get("minLevel") or 5)
        moves = P.default_moveset(sp, lv)
        while lv < top:
            before, lv = lv, lv + 1
            got = [mv for mlv, mv in sp.get("moves", [])
                   if before < mlv <= lv and mv not in moves]
            if got:
                moves, _f = P.trim_moves(dex, moves + got)
            el, to = evo_level(sp)
            if el and lv >= el and to in sps:
                sp = sps[to]
                new = [m for m in P.evolution_moves(sp) if m not in moves]
                if new:
                    moves, _f = P.trim_moves(dex, moves + new)
        return sp, moves

    end, moves = grow("CATERPIE", 25)
    names = [dex.move_name(m) for m in moves]
    chk("버터플이 Lv25에 공격기를 갖고 있다",
        any(P.is_attack(dex, m) for m in moves), names)
    end, moves = grow("WEEDLE", 25)
    chk("독침붕이 Lv25에 공격기를 갖고 있다",
        any(P.is_attack(dex, m) for m in moves),
        [dex.move_name(m) for m in moves])

    bad = []
    for key, sp in sps.items():
        if sp.get("prevo") or not evo_level(sp)[0]:
            continue
        _end, mv = grow(key)
        if not any(P.is_attack(dex, m) for m in mv) and key not in NO_ATTACK_OK:
            bad.append((sp["kr"], [dex.move_name(m) for m in mv]))
    chk("Lv50까지 키워 공격기가 없는 계열이 없다", not bad, bad)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
