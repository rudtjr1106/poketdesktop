# -*- coding: utf-8 -*-
"""지난 시간을 사람 말로 옮기는 것 검사.

    python common/test_korean.py

경계에서 틀리기 쉽다 - 59초와 60초, 6일과 7일, 29일과 30일.
한 칸씩 밀리면 "1시간 전" 이 "1분 전" 으로 나오는 식이라 눈에도 잘 안 띈다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.korean import ago                                # noqa: E402

OK = FAIL = 0
분, 시간, 일 = 60, 3600, 86400

CASES = [
    # (초, 나와야 할 말)
    (0, "방금"),
    (1, "방금"),
    (59, "방금"),
    (60, "1분 전"),                    # 여기서 단위가 바뀐다
    (61, "1분 전"),
    (59 * 분 + 59, "59분 전"),
    (시간, "1시간 전"),                # 여기서 또 바뀐다
    (2 * 시간, "2시간 전"),
    (23 * 시간 + 59 * 분, "23시간 전"),
    (일, "1일 전"),
    (6 * 일, "6일 전"),
    (7 * 일, "1주 전"),                # 일 -> 주
    (13 * 일, "1주 전"),
    (14 * 일, "2주 전"),
    (29 * 일, "4주 전"),
    (30 * 일, "1달 전"),               # 주 -> 달
    (364 * 일, "12달 전"),
    (365 * 일, "1년 전"),              # 달 -> 년
    (900 * 일, "2년 전"),
    (5000 * 일, "오래전"),
    # 시계가 앞선 PC 에서 음수가 올 수 있다. 미래로 보여주면 안 된다.
    (-1, "방금"),
    (-99999, "방금"),
    # 모르면 비운다. 틀린 값을 보여주느니 낫다.
    (None, ""),
    ("몰라", ""),
    ([], ""),
]


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def main():
    for sec, want in CASES:
        got = ago(sec)
        chk("%s -> %s" % (sec, want), got == want, "실제 %r" % got)

    # 시간이 갈수록 표시가 뒤로 가면 안 된다. 어느 두 시점을 잡아도
    # 나중 것이 더 "오래된" 칸에 있어야 한다.
    order = ["방금", "분", "시간", "일", "주", "달", "년", "오래전"]

    def 칸(t):
        for i, u in enumerate(order):
            if u in t:
                return i
        return -1

    step = [ago(s) for s in (0, 30, 90, 시간 * 2, 일 * 2, 일 * 10,
                             일 * 60, 일 * 400, 일 * 5000)]
    chk("시간이 갈수록 뒤 칸으로만 간다",
        all(칸(step[i]) <= 칸(step[i + 1]) for i in range(len(step) - 1)), step)

    # 숫자가 0 으로 나오면 "0분 전" 같은 말이 된다
    for s in range(0, 일 * 800, 977):
        t = ago(s)
        chk("0 으로 시작하지 않는다 (%d초)" % s, not t.startswith("0"), t)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
