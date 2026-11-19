# -*- coding: utf-8 -*-
"""켤 때의 tk scaling 붙잡기 (게시판 #707).

    python client/test_tk_scaling.py

**창을 실제로 만든다.** 윈도우에서 켜 둔 사이 화면 배율이 바뀌면(WM_DISPLAYCHANGE) Tk 이 tk scaling 을
1.333 에서 2.0 으로 다시 잰다. 그 뒤 새로 만드는 글꼴만 커지고 떠 있던 글꼴(FONT_S = FONT_TIP)은 옛 크기로
남아 포켓몬 관리 창의 글씨 크기가 섞였다. 못 박는 것:

  1. platform_os.pin_tk_scaling 이 import 오류 없이 있다 - 맥은 아무것도 안 한다 (platform_mac 은
     platform_base 를 import 하지 않는다. _M.pin_tk_scaling 로 쓰면 맥 앱이 import 에서 죽는다).
  2. platform_win.pin_tk_scaling(root, 50) 뒤 tk scaling 을 2.0 으로 바꾸면 고리가 켤 때 값으로 되돌린다.
     되돌릴 때마다 로그에 '되돌림' 이 남는다. 두 번 불러도 고리는 하나다.
     (윈도우 API 를 안 부르니 맥에서도 돈다 - 바꾸는 것은 Tk 뿐이다)
  3. 바뀐 직후 0.5초 안에 여는 창도 style_window 가 먼저 되돌린다 - 그 창의 글꼴은 켤 때 크기다.
     (윈도우는 같은 pt 글꼴의 줄 높이까지 본다. 맥 aqua 는 pt 글꼴이 scaling 을 안 따라서 값만 본다)
  4. app.py 가 dpi_aware() 바로 다음, init_fonts 앞에서 건다. dpi_aware 는 그대로 tk.Tk() 뒤다
     (앞으로 옮기면 켤 때부터 글꼴이 1.5배가 되어 모든 창이 넘친다).
  5. root 가 없어지면 확인 함수는 False 를 돌려주고 멈춘다 (오류를 안 낸다).
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

    print("\n=== 2. 고리가 켤 때 값으로 되돌린다 (platform_win.pin_tk_scaling) ===")
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

    print("\n=== 3. 바뀐 직후 여는 창 - style_window 가 먼저 되돌린다 ===")
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

    print("\n=== 4. app.py 순서 ===")
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

    print("\n=== 5. root 가 없어지면 멈춘다 ===")
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
