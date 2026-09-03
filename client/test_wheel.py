# -*- coding: utf-8 -*-
"""휠 한 칸이 몇 줄인가 검사.

    python client/test_wheel.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다.

**한 칸이 얼마로 오는지가 OS 마다 다르다.** 윈도우는 120, 맥은 1~3 이다.
예전 코드는 `int(-delta / 60)` 이라 맥에서는 몫이 0 이 되어 휠이 아예
안 먹었다. 화면은 멀쩡해 보이는데 굴러가지만 않아서, 스크롤바를 손으로
끌기 전까지는 목록이 그게 다인 줄 안다.

여기서 지키는 것 둘.
  · 윈도우에서 굴러가는 정도가 예전과 **한 줄도 안 달라진다**
  · 어떤 값이 와도 0 으로 깎이지 않는다 (0 은 그대로 0)
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-wheel"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop.ui_common import wheel_units            # noqa: E402

OK = FAIL = 0

# 이 게임이 실제로 쓰는 값들 (U.scrollable 의 div)
DIVS = (60, 120, 30)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


def t_windows_unchanged():
    section("윈도우에서 굴러가는 정도가 예전과 같다")
    for div in DIVS:
        for delta in (120, -120, 240, -240, 360):
            old = int(-delta / div)          # 예전 식
            new = wheel_units(delta, div)
            chk("delta=%d div=%d" % (delta, div), new == old,
                "예전 %d, 지금 %d" % (old, new))


def t_mac_scrolls():
    section("맥 값(1~3)에서도 굴러간다")
    for div in DIVS:
        for delta in (1, -1, 2, -2, 3, -3):
            n = wheel_units(delta, div)
            chk("delta=%d div=%d 가 0 이 아니다" % (delta, div), n != 0, n)
            chk("delta=%d div=%d 방향이 맞다" % (delta, div),
                (n < 0) == (delta > 0), n)


def t_direction():
    section("방향 — 위로 굴리면 위로 간다")
    # tk 는 위로 굴릴 때 delta 가 양수다. yview_scroll 은 음수가 위다.
    chk("위로(+) 는 음수", wheel_units(120, 60) < 0)
    chk("아래로(-) 는 양수", wheel_units(-120, 60) > 0)
    chk("맥 위로(+1) 도 음수", wheel_units(1, 60) < 0)
    chk("맥 아래로(-1) 도 양수", wheel_units(-1, 60) > 0)


def t_zero_and_junk():
    section("이상한 값에도 안 죽는다")
    chk("0 은 0", wheel_units(0, 60) == 0)
    chk("None 은 0", wheel_units(None, 60) == 0)
    chk("글자는 0", wheel_units("x", 60) == 0)
    chk("div 가 0 이어도 안 죽는다", wheel_units(120, 0) != 0)
    chk("아주 큰 값도 넘어간다", wheel_units(100000, 60) != 0)


def t_never_zero():
    section("어떤 값이 와도 0 으로 깎이지 않는다")
    for div in (30, 60, 120, 240, 1000):
        for delta in (1, -1, 5, -5, 120, -120):
            chk("delta=%s div=%s" % (delta, div),
                wheel_units(delta, div) != 0)


def main():
    for fn in (t_windows_unchanged, t_mac_scrolls, t_direction,
               t_zero_and_junk, t_never_zero):
        fn()
    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
