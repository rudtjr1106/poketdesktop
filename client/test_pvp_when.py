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
import time

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


def _force_kst():
    """될 수 있으면 시간대를 한국으로 맞춰 놓고 검사한다.

    **CI 러너는 UTC 다.** UTC 에서는 옮기나 마나 같은 글자가 나와서,
    고친 것과 안 고친 것을 가릴 수가 없다 - 그대로 두면 이 검사가
    러너에서 아무것도 안 지킨다.

    리눅스·맥은 TZ 를 바꾸고 tzset() 을 부르면 astimezone() 이 따라온다.
    윈도우에는 tzset 이 없어서 그 PC 시간대를 그대로 쓴다(어차피 한국이다).
    """
    if not hasattr(time, "tzset"):
        return
    os.environ["TZ"] = "Asia/Seoul"
    try:
        time.tzset()
    except Exception:                                       # noqa: BLE001
        pass


def _kst_now_offset():
    """이 검사를 도는 시점의 시간대 차이."""
    return datetime.datetime.now().astimezone().utcoffset()


def main():
    _force_kst()
    offset = _kst_now_offset()
    on_kst = offset == datetime.timedelta(hours=9)

    chk("빈 값은 빈 문자열", _when("") == "" and _when(None) == "")
    chk("모르는 형식은 안 죽고 대강 자른다",
        _when("이상한값") == "이상한값", _when("이상한값"))

    def want(iso):
        """이 PC 시간대로 옮겼을 때 나와야 하는 글자."""
        return datetime.datetime.fromisoformat(iso).astimezone().strftime(
            "%m-%d %H:%M")

    # UTC 자정 근처를 골랐다 - 날짜까지 넘어가는 경우를 놓치지 않으려고.
    # 15:30 UTC 는 한국에서 다음날 00:30 이다. 예전 코드는 "09-02 15:30"
    # 을 그대로 보여줬다. 날짜가 넘어가는 줄은 특히 놓치기 쉽다.
    for iso in ("2026-09-02T15:30:00+00:00", "2026-09-02T03:22:07+00:00"):
        chk("이 PC 시간대로 옮겨진다 (%s)" % iso[11:16],
            _when(iso) == want(iso), (_when(iso), want(iso)))

    if on_kst:
        chk("한국이면 자정을 넘겨 다음날로",
            _when("2026-09-02T15:30:00+00:00") == "09-03 00:30")
        chk("한국이면 같은 날 안에서 9시간 밀린다",
            _when("2026-09-02T03:22:07+00:00") == "09-02 12:22")

    # **시간대가 UTC 면 이 검사를 건너뛴다.** 옮기나 마나 같은 글자라
    # 고친 것과 안 고친 것을 가릴 수가 없다 (러너가 대개 UTC 다).
    if offset:
        chk("문자 그대로 잘라 붙인 옛 결과와는 다르다 (버그였던 그 값)",
            _when("2026-09-02T03:22:07+00:00") != "09-02 03:22")

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d  (이 PC 시간대 UTC%s)"
          % (OK, FAIL, ("+9" if on_kst else "%+d" % (
              offset.total_seconds() // 3600 if offset else 0))))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
