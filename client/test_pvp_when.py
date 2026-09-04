# -*- coding: utf-8 -*-
"""대전 목록의 시각 표시(_when) 검사.

    python client/test_pvp_when.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다.

**서버는 UTC 로 보낸다.** 예전 코드는 문자열을 그대로 잘라서 보여줬다 -
"2026-09-02T03:22:07+00:00" 을 그냥 "09-02 03:22" 로 찍었는데, 한국은
UTC+9 라 실제로는 "09-02 12:22" 이다. 9시간이 이르게 나와서, 새벽에 진
판이 낮에 진 것처럼 보였다.
"""
import datetime
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-pvpwhen"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop.ui_pvp import _when                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def _kst_now_offset():
    """이 검사를 도는 PC 의 시간대가 실제로 KST(+9) 인지.

    CI 러너는 대개 UTC 다 - 거기서는 이 검사가 확인하려는 "+9시간
    당겨진다" 를 확인할 수 없으므로, 그 사실 자체를 검사 결과로 남긴다.
    """
    return datetime.datetime.now().astimezone().utcoffset()


def main():
    offset = _kst_now_offset()
    on_kst = offset == datetime.timedelta(hours=9)

    chk("빈 값은 빈 문자열", _when("") == "" and _when(None) == "")
    chk("모르는 형식은 안 죽고 대강 자른다",
        _when("이상한값") == "이상한값", _when("이상한값"))

    # UTC 자정 근처를 골랐다 - 날짜까지 넘어가는 경우를 놓치지 않으려고.
    s = "2026-09-02T15:30:00+00:00"
    got = _when(s)
    if on_kst:
        # 15:30 UTC + 9시간 = 다음날 00:30 KST. 여기가 예전 버그의 핵심 -
        # 예전 코드는 "09-02 15:30" 을 그대로 보여줬는데 실제로는
        # "09-03 00:30" 이다. 날짜까지 넘어가는 줄은 특히 놓치기 쉽다.
        chk("UTC 자정 근처는 다음날로 넘어간다 (KST 러너)",
            got == "09-03 00:30", got)
    else:
        chk("이 PC 시간대로 정확히 옮겨진다 (KST 아닌 러너)",
            datetime.datetime.strptime(got, "%m-%d %H:%M")
            .replace(year=2026) ==
            (datetime.datetime.fromisoformat(s) + offset).replace(
                year=2026, tzinfo=None), got)

    # 흔한 경우: 같은 날 안에서 시간만 밀린다.
    s2 = "2026-09-02T03:22:07+00:00"
    got2 = _when(s2)
    if on_kst:
        chk("같은 날 안에서 9시간 밀린다 (KST 러너)",
            got2 == "09-02 12:22", got2)
    chk("문자 그대로 잘라 붙인 옛 결과와는 다르다 (버그였던 그 값)",
        got2 != "09-02 03:22", got2)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d  (이 PC 시간대 UTC%s)"
          % (OK, FAIL, ("+9" if on_kst else "%+d" % (
              offset.total_seconds() // 3600 if offset else 0))))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
