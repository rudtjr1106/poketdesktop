# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 거르기(box_filter) 검사.

    python client/test_box_filter.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다. 도감은 저장소의
pokedex.json 을 그대로 읽는다 - 타입 id 와 한글 이름이 진짜여야 한다.
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-boxfilter"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from common import pokelogic as P                           # noqa: E402
from poketdesktop import box_filter as F                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mon(dex, num, nickname=None, pid=None):
    sp = dex.get(num)
    m = {"id": pid or num, "species": sp["internal"], "num": num,
         "nickname": nickname, "level": 10,
         "info": {"name": nickname or sp["kr"], "species": sp["kr"]}}
    return m


def main():
    p = os.path.join(HERE, "..", "server", "data", "pokedex.json")
    with open(p, encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    mons = [mon(dex, 4, "불꽃이"), mon(dex, 7), mon(dex, 1), mon(dex, 25),
            mon(dex, 133, "이브"), mon(dex, 6)]          # 파이리(별명) 꼬부기 이상해씨 피카츄 이브이(별명) 리자몽

    print("-- 아무것도 안 걸면 전부")
    chk("전부 나온다", len(F.apply(mons, dex)) == 6)
    chk("순서가 그대로", [m["num"] for m in F.apply(mons, dex)] == [4, 7, 1, 25, 133, 6])

    print("-- 타입")
    fire = F.apply(mons, dex, type_id="FIRE")
    chk("불꽃 타입만 (파이리·리자몽)", sorted(m["num"] for m in fire) == [4, 6], [m["num"] for m in fire])
    chk("두 타입 중 하나만 맞아도 (리자몽은 불꽃/비행)",
        [m["num"] for m in F.apply(mons, dex, type_id="FLYING")] == [6])
    chk("없는 타입이면 빈 목록", F.apply(mons, dex, type_id="DRAGON") == [])

    print("-- 이름")
    chk("종 이름으로", [m["num"] for m in F.apply(mons, dex, query="꼬부기")] == [7])
    chk("별명으로", [m["num"] for m in F.apply(mons, dex, query="불꽃이")] == [4])
    chk("별명이 있어도 종 이름으로 찾힌다", [m["num"] for m in F.apply(mons, dex, query="파이리")] == [4])
    chk("앞글자만", sorted(m["num"] for m in F.apply(mons, dex, query="이")) >= [1],
        [m["num"] for m in F.apply(mons, dex, query="이")])
    chk("이상해씨·이브이·불꽃이 셋 다 '이' 가 들어간다",
        sorted(m["num"] for m in F.apply(mons, dex, query="이")) == [1, 4, 133],
        [m["num"] for m in F.apply(mons, dex, query="이")])
    chk("도감 번호로", [m["num"] for m in F.apply(mons, dex, query="25")] == [25])
    chk("네 자리 번호로", [m["num"] for m in F.apply(mons, dex, query="0007")] == [7])
    chk("빈칸은 무시", [m["num"] for m in F.apply(mons, dex, query="  꼬부기 ")] == [7])
    chk("없는 이름이면 빈 목록", F.apply(mons, dex, query="뮤츠") == [])

    print("-- 타입 + 이름")
    chk("둘 다 걸면 둘 다 맞아야", [m["num"] for m in F.apply(mons, dex, "FIRE", "리자몽")] == [6])
    chk("타입은 맞는데 이름이 다르면 없음", F.apply(mons, dex, "FIRE", "꼬부기") == [])

    print("-- 갖고 있는 타입만")
    types = F.types_present(mons, dex)
    chk("불꽃·물·풀·전기·노말·비행·독", set(types) == {"FIRE", "WATER", "GRASS", "POISON", "ELECTRIC", "NORMAL", "FLYING"}, types)
    chk("처음 나온 순서", types[0] == "FIRE" and types[1] == "WATER", types[:3])

    print("-- 도감이 없어도 안 터진다")
    chk("dex None 이면 타입 거르기는 전부 걸러진다", F.apply(mons, None, type_id="FIRE") == [])
    chk("dex None 이어도 이름으로는 찾는다", [m["num"] for m in F.apply(mons, None, query="불꽃이")] == [4])

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
