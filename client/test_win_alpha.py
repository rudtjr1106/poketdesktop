# -*- coding: utf-8 -*-
"""창 투명도 (게시판 #566 - '회사에서 쓸 때 있으면 유용할 것 같다').

    python client/test_win_alpha.py

설정의 '창 투명도' 하나로 **테두리가 있는 포스크탑 창**(관리 · 가방 · 게시판 · 설정 ...)이 늘 그만큼 비친다.
  1. config.win_alpha: 기본 100 (그대로) · 값이 없던 옛 설정도 그대로 · 60 은 0.6 · 투명도 70% 까지 (또렷함 30) · 이상한 값은 그대로.
  2. win_alpha.install 뒤에 뜨는 창은 그 투명도로 뜬다. 창 속 창도.
  3. 테두리 없는 창(바탕화면 도트 · 이름표 · 연출)과 스스로 투명도를 움직이는 창(_own_alpha)은 안 건드린다.
  4. 손잡이를 움직이면(apply_all) 이미 떠 있는 창도 바로 바뀐다. 입힌 창 수를 돌려준다.
  5. 거뒀다 다시 띄워도(긴급 숨기기) 같은 투명도.
진짜 Tk 창을 띄운다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-win-alpha-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import win_alpha as WA                    # noqa: E402

OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def alpha(w):
    return round(float(w.attributes("-alpha")), 2)


def pump(root, n=20):
    for _ in range(n):
        root.update()


def t_config():
    print("-- 1. 설정 값")
    chk("기본은 그대로 (100)", config.DEFAULTS["winOpacity"] == 100
        and config.win_alpha(dict(config.DEFAULTS)) == 1.0)
    chk("값이 없던 옛 설정도 그대로", config.win_alpha({}) == 1.0 and config.win_alpha(None) == 1.0)
    chk("60 은 0.6", abs(config.win_alpha({"winOpacity": 60}) - 0.6) < 1e-9)
    chk("투명도 70% 까지 (또렷함 30)", config.WIN_OPACITY_MIN == 30
        and abs(config.win_alpha({"winOpacity": 0}) - 0.3) < 1e-9
        and abs(config.win_alpha({"winOpacity": 10}) - 0.3) < 1e-9)
    chk("이상한 값이면 그대로", config.win_alpha({"winOpacity": "x"}) == 1.0
        and config.win_alpha({"winOpacity": 500}) == 1.0)
    chk("포켓몬 투명도와 따로다", config.win_alpha({"petOpacity": 40}) == 1.0)


def t_windows():
    print("-- 2~5. 창")
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    settings = {"winOpacity": 60}
    chk("설치 전에는 그대로 (1.0)", WA.current() == 1.0, WA.current())
    WA.install(root, lambda: settings)
    WA.install(root, lambda: settings)                     # 두 번 불러도 한 번만 건다
    chk("설치 뒤 current() 는 설정 값", abs(WA.current() - 0.6) < 1e-9, WA.current())

    win = tk.Toplevel(root)
    tk.Label(win, text="관리 창").pack()
    pump(root)
    chk("새로 뜬 창은 그 투명도로 뜬다", alpha(win) == 0.6, alpha(win))
    inner = tk.Toplevel(win)
    pump(root)
    chk("창 속 창도", alpha(inner) == 0.6, alpha(inner))

    bare = tk.Toplevel(root)
    bare.overrideredirect(True)
    pump(root)
    chk("테두리 없는 창(바탕화면 도트 · 연출)은 안 건드린다", alpha(bare) == 1.0, alpha(bare))
    own = tk.Toplevel(root)
    own._own_alpha = True
    own.attributes("-alpha", 0.0)
    pump(root)
    chk("스스로 투명도를 움직이는 창(_own_alpha)도 안 건드린다", alpha(own) == 0.0, alpha(own))
    chk("eligible: 테두리 창만", WA.eligible(win) and WA.eligible(inner) and not WA.eligible(bare)
        and not WA.eligible(own) and not WA.eligible(root))

    settings["winOpacity"] = 100
    n = WA.apply_all(root)
    chk("손잡이를 되돌리면 떠 있던 창이 바로 또렷해진다", alpha(win) == 1.0 and alpha(inner) == 1.0, (alpha(win), alpha(inner)))
    chk("  입힌 창 수 = 테두리 있는 창 수 (2)", n == 2, n)
    chk("  테두리 없는 창 · _own_alpha 창은 그대로", alpha(bare) == 1.0 and alpha(own) == 0.0, (alpha(bare), alpha(own)))
    settings["winOpacity"] = 45
    WA.apply_all(root)
    chk("다시 올리면 바로 비친다", alpha(win) == 0.45, alpha(win))
    chk("  창을 못 훑어도(루트가 이상해도) 부른 쪽을 터뜨리지 않는다 ('기본값으로' 가 멈추면 안 된다)",
        WA.apply_all(object()) == 0)
    chk("  같은 값이면 다시 입히지 않는다 (윈도우에서 창 틀을 다시 짓지 않게 - 기본 100% 인 사람은 Tk 를 안 부른다)",
        WA.apply_all(root) == 0, "바꾼 창이 있다")

    win.withdraw()
    pump(root)
    win.deiconify()
    pump(root)
    chk("거뒀다 다시 띄워도(긴급 숨기기) 같은 투명도", alpha(win) == 0.45, alpha(win))

    t_settings(root, settings)
    chk("창 오류 없음", not ERRORS, ERRORS[:2])
    root.destroy()


def labels_of(sw):
    """설정 창의 줄 이름들. 기본 테마는 위젯 글, DP 계열은 rows (캔버스에 그린다)."""
    rows = getattr(sw, "rows", None)
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return [r.get("label") for r in rows]
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                t = c.cget("text")
            except tk.TclError:
                t = None
            if t:
                out.append(t)
            walk(c)
    walk(sw.win)
    return out


def t_settings(root, settings):
    print("-- 6. 설정 창 (기본 테마 + DP 계열 테마) · 기본값으로")
    import test_mypage_ui as M
    from poketdesktop import ui_settings
    from poketdesktop.skins.dp import settings as DPS
    for name, cls in (("기본", ui_settings.SettingsWindow), ("DP 계열", DPS.SettingsWindow)):
        app = M.FakeApp(root)
        WA.install(root, lambda: app.settings)
        sw = cls(app)
        pump(root)
        names = labels_of(sw)
        ok = all(x in names for x in ("포켓몬 투명도", "창 투명도", "걷는 속도"))
        chk("%s: '창 투명도' 가 '포켓몬 투명도' 다음 줄 (걷는 속도 앞)" % name,
            ok and names.index("포켓몬 투명도") < names.index("창 투명도") < names.index("걷는 속도"), names[:8])
        sw._set_win_alpha(50)
        top = sw.win.winfo_toplevel()
        pump(root)
        chk("  50% 로 두면 열린 창이 바로 비친다", alpha(top) == 0.5 and app.settings["winOpacity"] == 50, alpha(top))
        sw.reset()
        pump(root)
        chk("  '기본값으로' 를 누르면 열린 창도 바로 또렷해진다", app.settings["winOpacity"] == 100 and alpha(top) == 1.0,
            (app.settings.get("winOpacity"), alpha(top)))
        try:
            sw.close()
        except Exception:                                   # noqa: BLE001
            top.destroy()
    WA.install(root, lambda: settings)


def main():
    t_config()
    t_windows()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
