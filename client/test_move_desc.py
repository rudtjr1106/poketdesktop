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
    """ui_box.pick_move 가 만드는 줄과 같은 규칙."""
    print("-- 화면 표기")

    def line(md):
        bits = [md.get("kr") or "?"]
        power = md.get("power")
        bits.append("위력 %d" % power if power else "변화 기술")
        acc = md.get("acc")
        bits.append("명중 %d" % acc if acc else "명중 —")
        if md.get("pp"):
            bits.append("PP %d" % md["pp"])
        return "  ·  ".join(bits)

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
        line(moves["THUNDERBOLT"]) == "10만볼트  ·  위력 90  ·  명중 100  ·  PP 15",
        line(moves["THUNDERBOLT"]))
    chk("변화 기술은 위력 대신 '변화 기술'",
        "변화 기술" in line(moves["SWORDSDANCE"]), line(moves["SWORDSDANCE"]))


def main():
    if not os.path.exists(DEX):
        print("도감 파일이 없습니다:", DEX)
        return 1
    with open(DEX, encoding="utf-8") as f:
        moves = json.load(f)["moves"]

    t_도감에_설명이_있다(moves)
    t_설명_말고는_안_바뀌었다(moves)
    t_화면에_적는_법(moves)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
