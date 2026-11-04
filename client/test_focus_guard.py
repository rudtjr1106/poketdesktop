# -*- coding: utf-8 -*-
"""포커스 지키기 (2.1.3, 게시판 #444) - 진짜 Tk + 가짜 '맨 앞' (윈도우 hwnd · 맥 pid 를 흉내).

    python client/test_focus_guard.py

판단은 윈도우 · 맥이 같다 - 가짜 백엔드로 '맨 앞' 을 흉내 내고 force 로 켠다. 실제로 포커스가 안 넘어가는지는
실기에서 본다 (pre-release). 맥에서는 진짜 백엔드(_Mac)가 맨 앞 앱을 읽는지도 본다. 못 박는 것:

  1. 테두리 없는 우리 창이 **남의 창**에서 포커스를 가져가면 그 남의 창으로 돌려준다.
  2. 원래 우리 창이 맨 앞이었으면(도트를 눌렀다) · 테두리 있는 창(허브 · 대화상자)이면 손대지 않는다.
  3. deiconify · lift · attributes(-topmost 를 걸 때만) 가 그 문지기를 거친다. 값을 묻는 attributes 는 그대로.
  4. uninstall 하면 tkinter 가 원래대로.
"""
import os
import sys
import tempfile
import tkinter as tk

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-focus-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import focus_guard as FG                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402

OK = FAIL = 0
MINE, OTHER = os.getpid(), os.getpid() + 1


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Front(object):
    """맨 앞(fg)과 그것을 만든 프로세스(pid)를 흉내 낸다 (focus_guard._Win · _Mac 과 같은 모양)."""

    def __init__(self):
        self.fg = 0
        self.pid = {}
        self.set_to = []
        self.asked = 0

    def front(self):
        self.asked += 1
        return self.fg or None

    def ours(self, h):
        return self.pid.get(h) == MINE

    def give_back(self, h):
        self.set_to.append(h)
        self.fg = h


def pump(root, secs):
    import time
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    if sys.platform == "darwin":
        real = FG._Mac()
        got = real.front()
        chk("맥: 진짜 백엔드가 맨 앞 앱(pid)을 읽는다", isinstance(got, int) and got > 0 and real.ours(os.getpid()), got)
    api = Front()
    FG._BACKEND[0] = api
    api.pid = {11: OTHER, 21: MINE, 22: MINE}           # 11 = 메모장(남의 것), 21 · 22 = 우리 창
    pet = tk.Toplevel(root)
    pet.overrideredirect(True)
    hub = tk.Toplevel(root)

    print("1. quiet")
    chk("켜기 전에는 그냥 부른다", FG.quiet(pet, lambda: "x") == "x" and api.asked == 0, api.asked)
    chk("켠다 (윈도우 · 맥)", FG.install(force=True) and FG._ORIG, FG._ORIG)
    chk("  두 번 켜지 않는다", FG.install(force=True) is False)

    def steal():
        api.fg = 21                                     # Tk 가 우리 창을 활성화했다
        return "done"
    api.fg = 11
    chk("남의 창(메모장)에서 가져가면 돌려준다", FG.quiet(pet, steal) == "done" and api.set_to == [11]
        and api.fg == 11, (api.set_to, api.fg))
    api.set_to = []
    api.fg = 22
    FG.quiet(pet, steal)
    chk("원래 우리 창이 맨 앞이었으면(도트를 눌렀다) 손대지 않는다", api.set_to == [] and api.fg == 21, api.set_to)
    api.fg = 11
    FG.quiet(hub, steal)
    chk("테두리 있는 창(허브 · 대화상자)은 앞으로 나오게 둔다", api.set_to == [] and api.fg == 21, api.set_to)
    api.fg = 11
    FG.quiet(pet, lambda: None)
    chk("가져가지 않았으면 아무것도 안 한다", api.set_to == [], api.set_to)
    api.fg = 0
    FG.quiet(pet, steal)
    chk("맨 앞 창을 몰랐으면(0) 손대지 않는다", api.set_to == [], api.set_to)

    print("1b. 맥처럼 활성화가 늦게 일어날 때 (deferred)")
    api.deferred = True
    api.set_to = []
    api.fg = 11
    FG.quiet(pet, lambda: None)                         # 부른 자리에서는 그대로
    api.fg = 21                                         # 이벤트를 돌다가 우리 앱이 맨 앞이 됐다
    pump(root, FG.DEFER_MS / 1000.0 + 0.2)
    chk("잠깐 뒤에 한 번 더 보고 돌려준다", api.set_to == [11] and api.fg == 11, api.set_to)
    api.set_to = []
    api.fg = 11
    FG.quiet(pet, lambda: None)
    FG._pressed()                                       # 그 사이 사용자가 우리 도트를 눌렀다
    api.fg = 21
    pump(root, FG.DEFER_MS / 1000.0 + 0.2)
    chk("  그 사이 우리 창을 눌렀으면 돌려주지 않는다 (사용자가 고른 것)", api.set_to == [] and api.fg == 21, api.set_to)
    api.deferred = False

    print("2. tkinter 문지기")
    for name, call in (("deiconify", lambda: pet.deiconify()), ("lift", lambda: pet.lift()),
                       ("tkraise", lambda: pet.tkraise()),
                       ("attributes(-topmost, True)", lambda: pet.attributes("-topmost", True))):
        n = api.asked
        call()
        chk("%s 는 문지기를 거친다 (맨 앞 창을 묻는다)" % name, api.asked > n, api.asked - n)
    n = api.asked
    got = pet.attributes("-topmost")
    chk("attributes(-topmost) 값을 묻기만 하면 그대로 (문지기 없음)", api.asked == n and str(got) in ("1", "True"),
        (api.asked - n, got))
    n = api.asked
    pet.attributes("-alpha", 1.0)
    chk("다른 속성은 문지기 없이", api.asked == n)
    n = api.asked
    hub.lift()
    chk("테두리 있는 창의 lift 는 맨 앞 창을 묻지 않는다", api.asked == n, api.asked - n)
    cv = tk.Canvas(pet)
    i = cv.create_rectangle(0, 0, 4, 4)
    cv.lift(i)
    chk("캔버스 항목 올리기(Canvas.lift)는 그대로", cv.find_all()[-1] == i)

    print("3. 끄기")
    FG.uninstall()
    n = api.asked
    pet.lift()
    pet.deiconify()
    pet.attributes("-topmost", True)
    chk("uninstall 하면 tkinter 가 원래대로", api.asked == n and not FG._ORIG, api.asked - n)
    FG._BACKEND[0] = None
    root.destroy()
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
