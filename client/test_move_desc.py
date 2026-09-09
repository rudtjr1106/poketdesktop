# -*- coding: utf-8 -*-
"""기술 설명 검사.

    python client/test_move_desc.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다.

포켓몬 관리에서 기술을 누르면 설명이 뜬다. 그 문장은 **본가에 실제로
실린 것**이어야 한다 - 우리가 지어내면 게임과 다른 말을 하게 된다.
그래서 PokeAPI 의 move_flavor_text 를 그대로 도감에 넣어 둔다
(tools/build_pokedex.py).

여기서 지키는 것 셋.
  · 설명이 도감에 실제로 들어 있다 (거의 모든 기술에)
  · 한국어 기술은 한국어 설명이 붙는다
  · 화면에 적을 때 0 을 그대로 적지 않는다 (명중률 없는 기술이 288개다)
"""
import collections
import json
import os
import re
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-movedesc"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from common import movetext as MT        # noqa: E402

OK = FAIL = 0
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
HANGUL = re.compile(r"[가-힣]")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def t_도감에_설명이_있다(moves):
    print("-- 도감 데이터")
    have = [k for k, m in moves.items() if m.get("desc")]
    chk("거의 모든 기술에 설명이 있다", len(have) > len(moves) * 0.98,
        "%d / %d" % (len(have), len(moves)))

    ko = [k for k in have if HANGUL.search(moves[k]["desc"])]
    # 한국어는 6세대부터 있다. 그 뒤에 나온 기술은 영어로 대신한다.
    chk("대부분 한국어다", len(ko) > len(moves) * 0.85,
        "%d / %d" % (len(ko), len(moves)))

    # 게임 글상자 줄바꿈이 그대로 남으면 화면에서 이상하게 끊긴다.
    bad = [k for k in have if "\n" in moves[k]["desc"]]
    chk("줄바꿈이 안 남아 있다", not bad, bad[:3])

    # 본가 문장 몇 개를 그대로 확인한다. 우리가 지어낸 말이 아니라는 뜻.
    known = {
        "THUNDERBOLT": "마비",
        "SWORDSDANCE": "공격을 크게 올린다",
        "PROTECT": "상대의 공격을 전혀 받지 않는다",
    }
    for k, must in known.items():
        chk("%s 설명이 본가 문장이다" % k, must in moves.get(k, {}).get("desc", ""),
            moves.get(k, {}).get("desc", "")[:50])


def t_설명_말고는_안_바뀌었다(moves):
    print("-- 기존 값 보존")
    # 설명을 붙이면서 다른 값이 흔들리면 배틀 계산이 통째로 달라진다.
    tb = moves.get("THUNDERBOLT", {})
    chk("10만볼트 위력 90", tb.get("power") == 90, tb.get("power"))
    chk("10만볼트 PP 15", tb.get("pp") == 15, tb.get("pp"))
    chk("10만볼트 전기 타입", tb.get("type") == "ELECTRIC", tb.get("type"))


def t_화면에_적는_법(moves):
    """화면에 적는 줄. **베끼지 않고 진짜 함수를 부른다.**

    전에는 여기에 ui_box.pick_move 를 손으로 옮겨 적어 뒀다. 그러면
    화면 쪽을 고치는 날 이 검사는 옛 문장을 지키는 꼴이 된다. 이제는
    common/movetext 한곳을 부른다 - 화면도 여기도 같은 것을 쓴다.
    """
    print("-- 화면 표기")

    def line(md):
        return MT.stat_line(md, md.get("kr") or "?")

    # 명중률이 없는 기술이 288개다. 0 을 그대로 적으면 절대 안 맞는
    # 기술처럼 보인다.
    noacc = [k for k, m in moves.items() if not m.get("acc")]
    chk("명중률 없는 기술이 실제로 많다", len(noacc) > 100, len(noacc))
    for k in noacc[:20]:
        chk("%s 를 '명중 0' 으로 안 적는다" % k, "명중 0" not in line(moves[k]),
            line(moves[k]))

    nopow = [k for k, m in moves.items() if not m.get("power")]
    for k in nopow[:20]:
        chk("%s 를 '위력 0' 으로 안 적는다" % k, "위력 0" not in line(moves[k]),
            line(moves[k]))

    chk("보통 기술은 다 적힌다",
        line(moves["THUNDERBOLT"])
        == "10만볼트  ·  특수  ·  위력 90  ·  명중 100  ·  PP 15",
        line(moves["THUNDERBOLT"]))
    # 변화 기술은 위력 칸을 아예 안 만든다. '변화' 라고 적어 두면
    # 위력이 없다는 뜻이 이미 들어 있다.
    sd = line(moves["SWORDSDANCE"])
    chk("변화 기술은 '변화' 로 적는다", "변화" in sd, sd)
    chk("변화 기술에 위력 칸이 없다", "위력" not in sd, sd)


def t_분류를_적는다(moves):
    """물리인지 특수인지가 화면에 나와야 한다.

    같은 위력 90짜리 불꽃 기술이라도 공격이 높으면 물리를, 특수공격이
    높으면 특수를 골라야 한다. 화면에 없으면 고를 수가 없다.
    """
    print("-- 분류")
    kinds = collections.Counter(m.get("cat") for m in moves.values())
    chk("도감에 분류가 셋 다 있다",
        set(kinds) == {"physical", "special", "status"}, dict(kinds))
    chk("분류가 빠진 기술이 없다", None not in kinds, dict(kinds))

    for k, want in (("THUNDERBOLT", "특수"), ("SCRATCH", "물리"),
                    ("SWORDSDANCE", "변화")):
        chk("%s 는 %s" % (k, want), MT.cat_name(moves[k]) == want,
            MT.cat_name(moves[k]))

    # 919개 전부가 한국어 한 낱말로 적힌다. 영어가 새어 나오면 안 된다.
    bad = [k for k, m in moves.items()
           if MT.cat_name(m) not in ("물리", "특수", "변화")]
    chk("전부 한국어로 적힌다", not bad, bad[:3])

    # 좁은 칸에 넣는 짧은 꼴도 같이 본다.
    chk("짧은 꼴 - 10만볼트", MT.short_line(moves["THUNDERBOLT"]) == "특수 · 90",
        MT.short_line(moves["THUNDERBOLT"]))
    chk("짧은 꼴 - 검무는 위력을 안 적는다",
        MT.short_line(moves["SWORDSDANCE"]) == "변화",
        MT.short_line(moves["SWORDSDANCE"]))
    # 위력이 0인 물리·특수 기술이 77개 있다(참기, 집단구타, Z기술).
    # '물리 · 0' 이라고 적으면 안 아픈 기술로 읽힌다.
    z = [k for k, m in moves.items()
         if m.get("cat") in ("physical", "special") and not m.get("power")]
    chk("위력 0인 공격 기술이 실제로 있다", len(z) > 20, len(z))
    for k in z[:10]:
        chk("%s 짧은 꼴에 0 이 안 붙는다" % k,
            not MT.short_line(moves[k]).endswith("0"), MT.short_line(moves[k]))


def t_설명이_다_있다(moves):
    """기술을 배울 때 설명을 보여준다. 빈 곳이 있으면 그 자리가 빈다."""
    print("-- 배울 때 쓸 설명")
    empty = [k for k, m in moves.items() if not MT.desc(m).strip()]
    chk("설명이 빈 기술이 없다", not empty, empty[:3])
    fallback = [k for k, m in moves.items()
                if MT.desc(m) == "설명이 아직 없는 기술입니다."]
    chk("대신 적는 문장이 쓰일 일이 없다", not fallback, fallback[:3])
    # 창 높이를 내용에 맞추긴 하지만, 소설이 실려 오면 곤란하다.
    longest = max(moves.values(), key=lambda m: len(MT.desc(m)))
    chk("가장 긴 설명도 100자 안", len(MT.desc(longest)) < 100,
        len(MT.desc(longest)))


def main():
    if not os.path.exists(DEX):
        print("도감 파일이 없습니다:", DEX)
        return 1
    with open(DEX, encoding="utf-8") as f:
        moves = json.load(f)["moves"]

    t_도감에_설명이_있다(moves)
    t_설명_말고는_안_바뀌었다(moves)
    t_화면에_적는_법(moves)
    t_분류를_적는다(moves)
    t_설명이_다_있다(moves)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
