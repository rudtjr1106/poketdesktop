# -*- coding: utf-8 -*-
"""켤 때의 tk scaling 붙잡기 (게시판 #707).

    python client/test_tk_scaling.py

**창을 실제로 만든다.** 윈도우에서 켜 둔 사이 화면 배율이 바뀌면(WM_DISPLAYCHANGE) Tk 이 tk scaling 을
1.333 에서 2.0 으로 다시 잰다. 그 뒤 새로 만드는 글꼴만 커지고 떠 있던 글꼴(FONT_S = FONT_TIP)은 옛 크기로
남아 포켓몬 관리 창의 글씨 크기가 섞였다. 못 박는 것:

  1. platform_os.pin_tk_scaling 이 import 오류 없이 있다 - 맥은 아무것도 안 한다 (platform_mac 은
     platform_base 를 import 하지 않는다. _M.pin_tk_scaling 로 쓰면 맥 앱이 import 에서 죽는다).
  2. 화면 폭이 켤 때와 달라져도 '되돌림' 이 한 번으로 그친다. Tk 은 scaling 을 화면 폭의 정수 mm 로 들고
     있어서(tkCmds.c) 폭이 바뀌면 켤 때 값을 넣어도 0.1% 쯤 어긋나게 읽힌다 - 절대 1e-3 으로 비교하던 판은
     0.5초마다 끝없이 되돌리고 로그를 남겼다. 진짜 Tk 은 폭을 못 바꾸니 Tk 의 계산을 흉내 낸 가짜 root 로 본다
     (가짜의 반올림이 진짜 Tk 과 같은지 먼저 맞춰 본다).
       - 150% 1920 (켤 때 DPI 를 몰라 1280@96) -> 1920@144: '되돌림' 1줄
       - 125% 1920 (1536@96) -> 1920@120: 1줄
       - 100% 에서 해상도만 1920 -> 1600 · 1366 · 1280: 0줄 (배율은 안 바뀌었다)
  3. platform_win.pin_tk_scaling(root, 50) 뒤 tk scaling 을 2.0 으로 바꾸면 고리가 켤 때 값으로 되돌린다.
     되돌릴 때마다 로그에 '되돌림' 이 남는다. 두 번 불러도 고리는 하나다.
     (윈도우 API 를 안 부르니 맥에서도 돈다 - 바꾸는 것은 Tk 뿐이다)
  4. 바뀐 직후 0.5초 안에 여는 창도 style_window 가 먼저 되돌린다 - 그 창의 글꼴은 켤 때 크기다.
     (윈도우는 같은 pt 글꼴의 줄 높이까지 본다. 맥 aqua 는 pt 글꼴이 scaling 을 안 따라서 값만 본다)
  5. app.py 가 dpi_aware() 바로 다음, init_fonts 앞에서 건다. dpi_aware 는 그대로 tk.Tk() 뒤다
     (앞으로 옮기면 켤 때부터 글꼴이 1.5배가 되어 모든 창이 넘친다).
  6. root 가 없어지면 확인 함수는 False 를 돌려주고 멈춘다 (오류를 안 낸다).
"""
import os
import sys
import tempfile
import time

HOME = tempfile.mkdtemp(prefix="poket-tk-scaling-")
os.environ["POKET_HOME"] = HOME

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from poketdesktop import config                            # noqa: E402
from poketdesktop import platform_base                     # noqa: E402
from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import platform_win                      # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def scaling(root):
    return float(root.tk.call("tk", "scaling"))


def pump(root, ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def log_text():
    try:
        with open(config.LOG_PATH, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def linespace(root, font):
    """그 설명 문자열 글꼴의 줄 높이 (붙잡는 위젯이 없으면 지금 scaling 으로 새로 만든다)."""
    return int(root.tk.call("font", "metrics", font, "-linespace"))


# ---------------------------------------------------------------- Tk 의 scaling 계산을 흉내 낸 가짜 root
MM_PER_PT = 25.4 / 72


def muldiv(a, b, c):
    """윈도우 MulDiv (양수만 - 반올림)."""
    return (a * b * 2 + c) // (2 * c)


class FakeTkApp(object):
    """tk scaling 만 받는 가짜 root.tk. 화면 폭 W 와 정수 mm 로 들고 있다 (Tk 8.6 과 같게).

    읽기 25.4/72*W/mm, 쓰기 mm=(int)(25.4/72/v*W+0.5) (tkCmds.c Tk_ScalingObjCmd).
    켤 때 · WM_DISPLAYCHANGE 는 mm=MulDiv(W, 254, LOGPIXELSX*10) (tkWinX.c · tkWinWm.c).
    """

    def __init__(self, W, dpi):
        self.display_change(W, dpi)

    def call(self, *a):
        if a[:2] != ("tk", "scaling"):
            raise tk.TclError("가짜 root 는 tk scaling 만 안다: %r" % (a,))
        if len(a) == 2:
            return MM_PER_PT * self.W / self.mm
        self.mm = max(1, int(MM_PER_PT / float(a[2]) * self.W + 0.5))
        return ""

    def display_change(self, W, dpi):
        self.W = W
        self.mm = muldiv(W, 254, dpi * 10)


class FakeRoot(object):
    """after 는 줄에 쌓았다가 run() 이 한 바퀴씩 부른다 (한 바퀴 = 0.5초)."""

    def __init__(self, W, dpi):
        self.tk = FakeTkApp(W, dpi)
        self.queue = []

    def after(self, ms, fn):
        self.queue.append(fn)

    def run(self, ticks):
        for _ in range(ticks):
            q, self.queue = self.queue, []
            for fn in q:
                fn()


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)

    want = scaling(root)
    other = 2.0 if abs(want - 2.0) > 0.1 else 1.0
    font = (U.FAMILY, 23)                                   # 앱이 안 쓰는 크기 - 캐시에 붙잡힌 것이 없다
    lines0 = linespace(root, font)

    # 고리를 걸기 **전에** 본다 - 맥은 Tk 이 여럿이어도 화면 하나를 같이 써서, 다른 Tk 에 건 고리가 되돌린다
    print("=== 1. platform_os.pin_tk_scaling ===")
    chk("platform_os 에 있다 (import 오류 없음)", callable(getattr(PLAT, "pin_tk_scaling", None)))
    chk("platform_base 에 아무것도 안 하는 것이 있다 (리눅스)", platform_base.pin_tk_scaling(root) is None
        and getattr(root, "_pin_tk_scaling", None) is None)
    src = open(os.path.join(HERE, "poketdesktop", "platform_os.py"), encoding="utf-8").read()
    chk("getattr 로 내보낸다 (맥이 import 에서 안 죽게)",
        'pin_tk_scaling = getattr(_M, "pin_tk_scaling"' in src
        and not any(ln.replace(" ", "").startswith("pin_tk_scaling=_M.") for ln in src.splitlines()))
    if sys.platform == "win32":
        chk("윈도우는 platform_win 의 것", PLAT.pin_tk_scaling is platform_win.pin_tk_scaling)
    else:
        got = PLAT.pin_tk_scaling(root)
        root.tk.call("tk", "scaling", other)
        pump(root, 150)
        chk("%s 는 아무것도 안 한다 (확인 함수 없음 · 되돌리지 않음)" % PLAT.NAME,
            got is None and getattr(root, "_pin_tk_scaling", None) is None and abs(scaling(root) - other) < 1e-3,
            (got, scaling(root)))
        w = tk.Toplevel(root)
        try:
            U.style_window(w, "확인 함수 없는 root", 200, 120)
            chk("  확인 함수가 없어도 style_window 는 그대로 (배율도 안 건드린다)",
                w.title() == "확인 함수 없는 root" and abs(scaling(root) - other) < 1e-3, scaling(root))
        except Exception as e:                              # noqa: BLE001
            chk("  확인 함수가 없어도 style_window 는 그대로 (배율도 안 건드린다)", False, repr(e))
        w.destroy()
        root.tk.call("tk", "scaling", want)
        root.update()

    print("\n=== 2. 화면 폭이 바뀌어도 '되돌림' 은 한 번 (Tk 계산을 흉내 낸 가짜 root) ===")
    # 진짜 Tk 은 화면 폭(WidthOfScreen)을 못 바꾼다. 가짜가 넣고 다시 읽는 반올림이 진짜와 같은지 먼저 본다.
    W = int(root.winfo_screenwidth())
    fake = FakeTkApp(W, 96)
    bad = []
    for v in (1.0, 1.25, 1.332022, 1.333, 1.5, 1.998, 2.0, 1.12345):
        root.tk.call("tk", "scaling", v)
        fake.call("tk", "scaling", v)
        real, mine = scaling(root), fake.call("tk", "scaling")
        if abs(real - mine) > 1e-9:
            bad.append((v, real, mine))
    root.tk.call("tk", "scaling", want)
    root.update()
    chk("가짜의 반올림이 진짜 Tk 과 같다 (폭 %d, 넣고 다시 읽기 8개)" % W,
        not bad and abs(scaling(root) - want) < 1e-9, (bad, scaling(root), want))

    def moves(label, start, changes, lines):
        """start 로 켜고 고리를 건 뒤 changes 마다 WM_DISPLAYCHANGE 를 흉내 내고 20번(10초) 돌린다."""
        froot = FakeRoot(*start)
        fcheck = platform_win.pin_tk_scaling(froot, 500)
        fwant = froot.tk.call("tk", "scaling")
        n0 = log_text().count("되돌림")
        moved = []
        for W1, dpi1 in changes:
            froot.tk.display_change(W1, dpi1)
            moved.append(froot.tk.call("tk", "scaling"))
            froot.run(20)
        end = froot.tk.call("tk", "scaling")
        n = log_text().count("되돌림") - n0
        chk("%s: '되돌림' %d줄" % (label, lines),
            callable(fcheck) and n == lines and abs(end - fwant) <= fwant * 0.01 and len(froot.queue) == 1,
            "%d줄  켤 때 %.6f  바뀐 값 %s  끝 %.6f  고리 %d" % (
                n, fwant, " ".join("%.6f" % m for m in moved), end, len(froot.queue)))
        return froot, moved, end

    moves("150% 1920 (켤 때 DPI 를 몰라 1280@96) -> 1920@144", (1280, 96), [(1920, 144)], 1)
    moves("125% 1920 (켤 때 1536@96) -> 1920@120", (1536, 96), [(1920, 120)], 1)
    moves("150% 2560 (켤 때 1707@96) -> 2560@144", (1707, 96), [(2560, 144)], 1)
    for W1 in (1600, 1366, 1280, 2560):
        froot, moved, end = moves("100%% 에서 해상도만 1920 -> %d" % W1, (1920, 96), [(W1, 96)], 0)
        chk("  그대로 둔다 (넣지 않는다)", abs(end - moved[0]) < 1e-12, (moved, end))
    moves("해상도만 바꾼 뒤(1920 -> 1600) 배율도 150% 로 -> 그때 되돌린다", (1920, 96), [(1600, 96), (1600, 144)], 1)

    print("\n=== 3. 고리가 켤 때 값으로 되돌린다 (platform_win.pin_tk_scaling) ===")
    check = platform_win.pin_tk_scaling(root, 50)
    chk("확인 함수를 돌려주고 root 에 둔다", callable(check) and getattr(root, "_pin_tk_scaling", None) is check)
    chk("두 번 불러도 같은 확인 함수 (고리는 하나)", platform_win.pin_tk_scaling(root, 50) is check)
    root.tk.call("tk", "scaling", other)
    chk("바꾼 직후에는 %.3f" % other, abs(scaling(root) - other) < 1e-3, scaling(root))
    if sys.platform == "win32":
        chk("  (윈도우) 이때 새로 만드는 글꼴은 크기가 다르다 - 섞임의 원인", linespace(root, font) != lines0,
            (lines0, linespace(root, font)))
    pump(root, 250)
    chk("after 뒤 켤 때 값 %.3f 로 돌아온다" % want, abs(scaling(root) - want) < 1e-3, scaling(root))
    log = log_text()
    chk("로그에 '되돌림' 이 남는다", "tk scaling %.3f -> %.3f 되돌림" % (other, want) in log, log[-200:])
    n = log.count("되돌림")
    pump(root, 200)
    chk("같은 값이면 로그를 더 안 남긴다", log_text().count("되돌림") == n, log_text().count("되돌림"))
    root.tk.call("tk", "scaling", other)
    pump(root, 250)
    chk("또 바뀌어도 또 되돌린다 (고리가 계속 돈다)", abs(scaling(root) - want) < 1e-3, scaling(root))

    print("\n=== 4. 바뀐 직후 여는 창 - style_window 가 먼저 되돌린다 ===")
    root.tk.call("tk", "scaling", other)
    win = tk.Toplevel(root)
    U.style_window(win, "배율 시험", 300, 200)
    chk("style_window 가 고리를 기다리지 않고 되돌린다", abs(scaling(root) - want) < 1e-3, scaling(root))
    chk("  그 창의 글꼴은 켤 때 크기 (줄 높이가 같다)", linespace(root, font) == lines0,
        (lines0, linespace(root, font)))
    lab = tk.Label(win, text="리자몽 별명 짓기", font=U.FONT_S)
    lab.pack()
    root.update()
    win.destroy()

    print("\n=== 5. app.py 순서 ===")
    app = open(os.path.join(HERE, "poketdesktop", "app.py"), encoding="utf-8").read()
    i_tk = app.find("self.root = tk.Tk()")
    i_dpi = app.find("PLAT.dpi_aware()")
    i_pin = app.find("PLAT.pin_tk_scaling(self.root)")
    i_fonts = app.find("U.init_fonts(self.root)")
    chk("tk.Tk() → dpi_aware() → pin_tk_scaling → init_fonts",
        -1 not in (i_tk, i_dpi, i_pin, i_fonts) and i_tk < i_dpi < i_pin < i_fonts,
        (i_tk, i_dpi, i_pin, i_fonts))
    between = app[i_dpi + len("PLAT.dpi_aware()"):i_pin]
    chk("  dpi_aware 바로 다음 (사이에 다른 부름이 없다)",
        all(ln.strip() == "" or ln.strip().startswith("#") for ln in between.splitlines()), between)

    chk("도는 동안 오류 없음", not ERRORS, ERRORS[:2])

    print("\n=== 6. root 가 없어지면 멈춘다 ===")
    # 앱은 Tk 가 하나라 root 를 부수면 바로 끝난다. 그래서 여기서도 부순 뒤에는 이벤트를 더 돌리지 않는다
    # (부순 Tk 의 남은 after 는 tkinter 가 명령을 지워서 다른 Tk 의 update 안에서 bgerror 로 멈춘다 - 앱과 상관없음).
    root.destroy()
    try:
        res = check()
        chk("없어진 뒤 확인 함수는 False (오류 없이 - 고리가 멈춘다)", res is False, res)
    except Exception as e:                                  # noqa: BLE001
        chk("없어진 뒤 확인 함수는 False (오류 없이 - 고리가 멈춘다)", False, repr(e))
    try:
        U._keep_tk_scaling(win)
        chk("  부서진 창으로 style_window 의 확인을 불러도 오류 없음", True)
    except Exception as e:                                  # noqa: BLE001
        chk("  부서진 창으로 style_window 의 확인을 불러도 오류 없음", False, repr(e))
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
