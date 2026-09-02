# -*- coding: utf-8 -*-
"""부팅 직후 로그인 재시도 검사.

    python client/test_boot_retry.py

컴퓨터를 켜면 게임이 같이 뜨는데, **그때는 아직 와이파이가 안 붙어
있다.** 그 상태에서 곧바로 로그인 창을 띄우면 사용자는 컴퓨터를
켜자마자 영문 모를 창부터 보고 손으로 다시 켜야 한다.

여기서 보는 것은 두 가지다.
  · 서버가 **답을 안 한 것**(못 닿음)과 **거절한 것**(토큰 만료)을 가르나
  · 부팅으로 켜졌을 때와 손으로 켰을 때 다르게 구는가

App 을 통째로 만들지 않는다. Tk 창도 서버도 없이, 쓰는 값만 가진 가짜에
메서드를 빌려 끼운다 - 이 로직은 순수하게 판단만 하기 때문이다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = os.path.join(tempfile.gettempdir(),
                                        "poket-test-bootretry")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop.api import ApiError                      # noqa: E402
from poketdesktop.app import App, BOOT_LOGIN_TRIES, MANUAL_LOGIN_TRIES  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class FakeRoot(object):
    """root.after 를 받아 적기만 한다. 실제로 기다리지 않는다."""

    def __init__(self):
        self.calls = []

    def after(self, ms, fn):
        self.calls.append((ms, fn))
        return "job"


class FakeApp(object):
    def __init__(self, autostarted):
        self.root = FakeRoot()
        self.autostarted = autostarted
        self._login_try = 0
        self._quitting = False

    def _auto_login(self):
        pass                    # 예약만 확인한다. 실제로 서버를 두드리지 않는다.

    retry = App._retry_login


def 못닿음():
    """서버가 아예 답을 안 했다. status 가 0 이다."""
    return ApiError("서버에 연결할 수 없습니다.")


def 거절됨(status=401):
    """서버가 답은 했는데 거절했다."""
    return ApiError("토큰이 만료되었습니다.", status)


def t_거절은_다시_해도_같다():
    """토큰 만료는 백 번 해도 만료다. 바로 로그인 창을 줘야 한다."""
    for st in (400, 401, 403, 409, 500):
        a = FakeApp(autostarted=True)
        chk("status %d 는 재시도하지 않는다" % st, a.retry(거절됨(st)) is False)
        chk("status %d 는 예약도 안 한다" % st, a.root.calls == [])


def t_못닿으면_다시_해_본다():
    a = FakeApp(autostarted=True)
    chk("못 닿으면 재시도한다", a.retry(못닿음()) is True)
    chk("한 번 예약했다", len(a.root.calls) == 1, a.root.calls)
    chk("첫 재시도는 3초 뒤", a.root.calls[0][0] == 3000, a.root.calls[0][0])


def t_점점_길게_기다린다():
    """3 6 12 24 48 - 붙자마자 붙고, 안 붙으면 조용해진다."""
    a = FakeApp(autostarted=True)
    waits = []
    while a.retry(못닿음()):
        waits.append(a.root.calls[-1][0] // 1000)
    chk("부팅이면 %d번 해 본다" % BOOT_LOGIN_TRIES,
        len(waits) == BOOT_LOGIN_TRIES, waits)
    chk("기다리는 시간이 점점 는다",
        all(waits[i] < waits[i + 1] for i in range(len(waits) - 1)), waits)
    chk("한 번에 48초를 넘기지 않는다", max(waits) <= 48, waits)
    chk("다 합쳐 1분은 넘게 기다려 준다", sum(waits) >= 60, sum(waits))
    # 여기가 없으면 와이파이가 늦게 붙는 PC 에서 영원히 다시 시도한다
    chk("끝나면 멈춘다", a.retry(못닿음()) is False)


def t_손으로_켰으면_오래_안_끈다():
    """사람이 화면을 보고 있다. 곧 답을 줘야 한다."""
    a = FakeApp(autostarted=False)
    n = 0
    while a.retry(못닿음()):
        n += 1
    chk("손으로 켰으면 %d번만" % MANUAL_LOGIN_TRIES,
        n == MANUAL_LOGIN_TRIES, n)
    chk("부팅 때보다 확실히 짧다", MANUAL_LOGIN_TRIES < BOOT_LOGIN_TRIES)


def t_status가_없는_예외도_넘긴다():
    """ApiError 가 아닌 것이 올라올 수도 있다. 그건 재시도 대상이 아니다."""
    a = FakeApp(autostarted=True)
    chk("모르는 예외는 재시도하지 않는다",
        a.retry(RuntimeError("무언가")) is False)


def main():
    for fn in (t_거절은_다시_해도_같다, t_못닿으면_다시_해_본다,
               t_점점_길게_기다린다, t_손으로_켰으면_오래_안_끈다,
               t_status가_없는_예외도_넘긴다):
        print("-- %s" % fn.__name__[2:])
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
