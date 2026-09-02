# -*- coding: utf-8 -*-
"""설정 창·트레이에 자동 시작 손잡이가 제대로 붙었는지.

    python client/smoke_autostart.py

창을 실제로 만들어 본다. 화면이 필요하다(윈도우에서만).
**진짜 Run 키는 건드리지 않는다** - 가짜 자리로 바꿔치기한다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = os.path.join(tempfile.gettempdir(),
                                        "poket-smoke-autostart")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import autostart, config                  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.tray import Tray                          # noqa: E402
from poketdesktop.ui_settings import SettingsWindow         # noqa: E402

SCRATCH = r"Software\poketdesktop-smoke\Run"
SCRATCH_APPROVED = r"Software\poketdesktop-smoke\Approved"
autostart.RUN_KEY = SCRATCH
autostart.APPROVED_KEY = SCRATCH_APPROVED

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wipe():
    import winreg
    for k in (SCRATCH, SCRATCH_APPROVED, r"Software\poketdesktop-smoke"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, k)
        except OSError:
            pass


def approve(first):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SCRATCH_APPROVED, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, autostart.VALUE, 0, winreg.REG_BINARY,
                          bytes([first]) + bytes(11))


def labels(w, out=None):
    out = [] if out is None else out
    for c in w.winfo_children():
        try:
            t = c.cget("text")
            if t:
                out.append(str(t))
        except Exception:                                   # noqa: BLE001
            pass
        labels(c, out)
    return out


def menu_labels(menu, out=None):
    out = [] if out is None else out
    for it in menu:
        try:
            out.append(str(it.text))
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(it, "submenu", None):
            menu_labels(it.submenu, out)
    return out


class FakeApp(object):
    username = "테스트"
    balls = 3
    money = 0
    overlay = None
    pvp_unseen = 0
    api = None                      # 로그인 전

    def __init__(self, root):
        self.root = root
        self.settings = config.load_settings()

    def set_autostart(self, want):
        ok, msg = autostart.enable() if want else autostart.disable()
        if ok:
            self.settings["autostart"] = bool(want)
        return ok, msg

    def toggle_autostart(self):
        return self.set_autostart(not self.settings.get("autostart"))

    def set_size(self, *a):
        pass

    def refresh_tray(self):
        pass

    def notify(self, m):
        pass

    def _refresh_autostart_ui(self):
        pass


def main():
    if sys.platform != "win32":
        print("윈도우에서만 하는 검사입니다.")
        return 0
    wipe()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)
    try:
        print("-- 기본값")
        chk("새로 받으면 자동 시작이 켜져 있다",
            config.DEFAULTS["autostart"] is True)

        print("-- 설정 창")
        w = SettingsWindow(app)
        chk("체크박스와 설명이 생겼다",
            hasattr(w, "boot_var") and hasattr(w, "boot_note"))
        chk("이름이 화면에 있다",
            any("컴퓨터 켤 때 같이 시작" in x for x in labels(w.win)))
        chk("처음엔 꺼짐", w.boot_var.get() is False)

        w.boot_var.set(True)
        w._toggle_autostart()
        chk("켜면 등록된다",
            autostart.registered() == autostart.command(),
            autostart.registered())
        chk("체크가 남는다", w.boot_var.get() is True)

        # 트레이에서 껐을 때 열려 있는 설정 탭이 따라오는가.
        # 안 따라오면 거기서 다시 누를 때 tk 가 먼저 체크를 뒤집어서
        # 정반대로 동작한다.
        autostart.disable()
        w.show_autostart()
        chk("밖에서 꺼도 설정 탭이 따라온다", w.boot_var.get() is False)

        print("-- 막혔을 때")
        autostart.enable()
        approve(0x03)
        w2 = SettingsWindow(app)
        chk("빨갛게 말해 준다",
            "작업 관리자" in w2.boot_note.cget("text")
            and w2.boot_note.cget("fg") == U.DANGER,
            w2.boot_note.cget("text"))

        print("-- 트레이")
        tray = Tray(app)
        got = menu_labels(tray.build_menu())
        # 로그인 전(api=None)에는 줄인 메뉴여야 한다. 서버가 있어야 하는
        # 항목을 눌러도 실패하기 때문이다.
        chk("로그인 전에는 연결 중이라고 알린다",
            any("연결하는 중" in x for x in got), got)
        chk("로그인 전에는 종료만 누를 수 있다",
            not any("포켓몬 관리" in x for x in got), got)

        app.api = object()          # 로그인했다고 치고
        got = menu_labels(tray.build_menu())
        hit = [x for x in got if "컴퓨터 켤 때" in x]
        chk("로그인 뒤에는 손잡이가 나온다", bool(hit), got[:6])
        chk("막힌 것을 이름에 적는다",
            any("작업 관리자에서 꺼짐" in x for x in hit), hit)
    finally:
        wipe()
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
