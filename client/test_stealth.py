# -*- coding: utf-8 -*-
"""긴급 숨기기 검사 (1.10.3) — 떠 있는 것을 전부 치웠다 그대로 되돌리는가.

    python client/test_stealth.py

**창을 진짜로 띄운다.** 단축키를 누르는 흉내는 내지 않는다 (키 입력을 만들어 넣지 않는다) -
단축키가 '눌렸다' 는 신호가 온 뒤의 길만 본다.

  1. 숨기면 떠 있던 창이 전부 사라진다: 보통 창, 테두리 없는 창(포켓몬), 작게 접어 둔 창.
  2. 되돌리면 그대로 돌아온다. 원래 안 보이던 창은 그대로 안 보인다. 접혀 있던 창은 접힌 채로.
  3. **숨긴 동안 앱이 창을 띄우려 해도 화면에 안 나온다** (새 창, deiconify). 되돌릴 때 나온다.
     숨긴 동안 앱이 스스로 거둔 창, 없어진 창은 되돌릴 때 안 나온다.
  4. 숨긴 동안에는 안 보이는 창에 grab 을 걸어도 죽지 않는다.
  5. 평소에는 아무것도 달라지지 않는다 (새 창은 바로 뜬다).
  6. 단축키 계산: 조합 이름·코드, 모르는 값은 '쓰지 않음'. 눌렸다는 신호는 한 번만 읽힌다.
  7. 설정 창에서 조합을 고르면 앱에 등록을 맡기고, 실패하면 까닭을 적고 '쓰지 않음' 으로 돌린다.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-stealth-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import hotkey as HK                       # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import stealth as ST                      # noqa: E402
from poketdesktop import tray as TRAY                       # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def seen(w):
    try:
        return bool(w.winfo_exists()) and str(w.state()) == "normal"
    except tk.TclError:
        return False


class App(object):
    def __init__(self, root):
        self.root, self.overlay, self.names_applied = root, self, 0
        self.settings = dict(config.DEFAULTS)
        self.tray_refreshed = 0
        self.registered = []
        self.refuse = None
        self.boss_key_error = ""
        self.stealth = ST.Stealth(self)

    wild = None

    def apply_names(self):
        self.names_applied += 1

    def apply_alpha(self):
        pass

    # 설정 창이 부르는 것들
    def refresh_tray(self):
        self.tray_refreshed += 1

    def stealth_on(self):
        return self.stealth.on

    def boss_key(self):
        return HK.clean(self.settings.get("bossKey"))

    def apply_boss_key(self, combo=None):
        if combo is not None:
            self.settings["bossKey"] = HK.clean(combo)
        want = self.boss_key()
        self.registered.append(want)
        if want and want == self.refuse:
            return False, "다른 프로그램이 이미 쓰고 있는 단축키입니다. 다른 조합을 골라 주세요."
        return True, ""

    def set_size(self, px):
        pass

    def set_autostart(self, on):
        return True, ""

    def set_show_grass(self, on):
        self.settings["showGrass"] = bool(on)

    def screen_choices(self):
        return []


def win(root, title, x, borderless=False):
    w = tk.Toplevel(root)
    w.title(title)
    w.geometry("180x90+%d+120" % x)
    tk.Label(w, text=title).pack(expand=True)
    if borderless:
        w.overrideredirect(True)
    return w


def main():
    print("=== 단축키 계산 (창 없이) ===")
    chk("고를 수 있는 것: 쓰지 않음 + Ctrl+Alt 조합 넷", HK.KEYS[0] == "" and len(HK.KEYS) == 5
        and all(k.startswith("ctrl+alt+") for k in HK.KEYS[1:]), HK.KEYS)
    chk("기본은 '쓰지 않음' 이다", config.DEFAULTS.get("bossKey") == "" and HK.clean(None) == "")
    chk("모르는 값·흔한 조합은 '쓰지 않음' 으로 읽는다", HK.clean("ctrl+c") == "" and HK.clean("x") == ""
        and HK.clean(" CTRL+ALT+H ") == "ctrl+alt+h")
    chk("이름: 윈도우는 글자로, 맥은 기호로", HK.label("ctrl+alt+h", mac=False) == "Ctrl + Alt + H"
        and HK.label("ctrl+alt+h", mac=True) == "⌃ ⌥ H" and HK.label("", mac=False) == "쓰지 않음"
        and HK.choices(mac=False)[0] == ("", "쓰지 않음"))
    chk("나누기", HK.parse("ctrl+alt+space") == ({"ctrl", "alt"}, "space") and HK.parse("") is None)
    chk("윈도우 코드: Ctrl+Alt+H = (누르고 있어도 한 번 | Ctrl | Alt, 'H')", HK.win_code("ctrl+alt+h") == (0x4003, 0x48)
        and HK.win_code("ctrl+alt+space") == (0x4003, 0x20), HK.win_code("ctrl+alt+h"))
    chk("맥 코드: ⌃⌥H = (4, control|option)", HK.mac_code("ctrl+alt+h") == (4, 0x1800)
        and HK.mac_code("ctrl+alt+space") == (49, 0x1800), HK.mac_code("ctrl+alt+h"))
    hk = HK.Hotkey()
    chk("'쓰지 않음' 은 아무것도 등록하지 않는다", hk.start("") == (True, "") and hk.back is None and hk.combo == "")
    hk._fire()
    chk("눌렸다는 신호는 한 번만 읽힌다", hk.fired() is True and hk.fired() is False)
    # 설명(주석·문서)이 아니라 **실제로 부르는 이름**을 본다
    import ast
    used = set()
    for name in ("hotkey.py", "stealth.py"):
        tree = ast.parse(open(os.path.join(HERE, "poketdesktop", name), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute):
                used.add(n.attr)
            elif isinstance(n, ast.Name):
                used.add(n.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                used.update(a.name.split(".")[0] for a in n.names)
    bad = used & {"SetWindowsHookExW", "SetWindowsHookExA", "SetWindowsHookEx", "GetAsyncKeyState", "GetKeyState",
                  "GetKeyboardState", "addGlobalMonitorForEventsMatchingMask_handler_", "CGEventTapCreate",
                  "pynput", "keyboard"}
    chk("전역 키보드 훅·키 상태 엿보기를 쓰지 않는다 (운영체제의 단축키 등록만 쓴다)", not bad
        and {"RegisterHotKey", "UnregisterHotKey", "RegisterEventHotKey", "UnregisterEventHotKey"} <= used, sorted(bad))

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = App(root)
    st = app.stealth

    print("\n=== 실제 등록 (이 운영체제) ===")
    if HK.supported():
        real = HK.Hotkey()
        ok, why = real.start("ctrl+alt+p")
        chk("단축키를 운영체제에 등록할 수 있다", ok and real.combo == "ctrl+alt+p" and real.back is not None, why)
        if ok and HK.MAC:
            real.back._handler(None, None, None)            # 운영체제가 부르는 그 함수를 직접 부른다
            chk("  눌렸다고 불리면 신호가 선다", real.fired() is True)
        elif ok and HK.WIN:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(real.back.tid, 0x0312, 1, 0)     # WM_HOTKEY 를 대기열에 넣는다
            end = time.time() + 2
            got = False
            while time.time() < end and not got:
                got = real.fired()
                time.sleep(0.02)
            chk("  눌렸다는 알림이 오면 신호가 선다", got)
        real.stop()
        chk("  풀면 남는 것이 없다", real.back is None and real.combo == "" and real.fired() is False)
        ok2, _why = real.start("ctrl+alt+p")
        chk("  풀고 나면 같은 조합을 다시 등록할 수 있다", ok2)
        real.stop()
    else:
        chk("이 운영체제에서는 단축키를 쓰지 않는다", HK.Hotkey().start("ctrl+alt+h")[0] is False)

    print("\n=== 평소 ===")
    hub = win(root, "허브", 60)
    pet = win(root, "포켓몬", 260, borderless=True)
    folded = win(root, "접어 둔 창", 460)
    gone = win(root, "원래 안 보이는 창", 660)
    settle(root)
    folded.iconify()
    gone.withdraw()
    settle(root, 0.4)
    chk("(준비) 창 넷: 둘은 떠 있고, 하나는 접혀 있고, 하나는 거둬져 있다", seen(hub) and seen(pet)
        and str(folded.state()) == "iconic" and str(gone.state()) == "withdrawn",
        (hub.state(), pet.state(), folded.state(), gone.state()))
    chk("숨기고 있지 않다", not st.on and ST.active() is None)

    print("\n=== 숨기기 ===")
    n = st.hide()
    settle(root)
    chk("떠 있던 것과 접혀 있던 것, 셋을 거둔다", n == 3 and st.on and ST.active() is st, n)
    chk("  화면에 남은 창이 없다", not any(seen(w) for w in (hub, pet, folded, gone))
        and all(str(w.state()) == "withdrawn" for w in (hub, pet, folded, gone)),
        [str(w.state()) for w in (hub, pet, folded, gone)])
    chk("  창이 없어진 것은 아니다 (게임은 그대로 돈다)", all(w.winfo_exists() for w in (hub, pet, folded, gone)))
    chk("한 번 더 숨겨도 아무 일도 없다", st.hide() == 0 and len(st.saved) == 3)

    print("\n=== 숨긴 동안 앱이 창을 띄우려 한다 ===")
    toast = win(root, "숨긴 동안 뜬 알림", 60)
    settle(root, 0.3)
    chk("새로 만든 창은 화면에 나오지 않는다", str(toast.state()) == "withdrawn" and toast in st.saved, toast.state())
    gone.deiconify()                                             # 배틀이 끝나 포켓몬이 돌아오려 한다
    settle(root, 0.2)
    chk("거둬 둔 창을 띄우려 해도 안 나온다, 대신 적어 둔다", str(gone.state()) == "withdrawn" and gone in st.saved)
    hub.withdraw()                                               # 앱이 스스로 닫았다
    chk("앱이 스스로 거둔 창은 되돌릴 것에서 빠진다", hub not in st.saved)
    PLAT.show_again(pet)                                         # 이름표를 다시 맞추는 주기
    settle(root, 0.2)
    chk("show_again 으로도 안 나온다", str(pet.state()) == "withdrawn" and pet in st.saved)
    ask = win(root, "되묻는 창", 260)
    try:
        ask.grab_set()
        grabbed = True
    except tk.TclError:
        grabbed = False
    chk("안 보이는 창에 grab 을 걸어도 죽지 않는다", grabbed)
    ask.destroy()                                                # 그사이 닫혔다
    battle = win(root, "끝난 배틀", 460)
    battle.destroy()
    settle(root, 0.2)
    chk("여전히 화면에 아무것도 없다", not any(seen(w) for w in (hub, pet, folded, gone, toast)))

    print("\n=== 되돌리기 ===")
    shown = []
    keep = PLAT.show_again
    PLAT.show_again = lambda w: (shown.append(w), keep(w))[1]
    n = st.show()
    PLAT.show_again = keep
    settle(root, 0.5)
    chk("숨기지 않았다면 떠 있었을 것만 돌아온다: 포켓몬·접힌 창·알림·돌아온 창", n == 4 and not st.on
        and ST.active() is None, n)
    chk("  포켓몬, 숨긴 동안 뜬 알림, 돌아온 창이 보인다", seen(pet) and seen(toast) and seen(gone),
        (pet.state(), toast.state(), gone.state()))
    chk("  앱이 스스로 거둔 창은 안 나온다", str(hub.state()) == "withdrawn")
    chk("  접어 둔 창은 접힌 채로 돌아온다", str(folded.state()) == "iconic", folded.state())
    chk("  테두리 없는 창은 show_again 으로 되돌린다 ('항상 위'·클릭 통과를 다시 건다)", shown == [pet], shown)
    chk("  이름표를 설정대로 다시 맞춘다", app.names_applied == 1)
    chk("  없어진 창 때문에 죽지 않았다", True)
    chk("한 번 더 되돌려도 아무 일도 없다", st.show() == 0)

    print("\n=== 되돌린 뒤에는 평소대로 ===")
    later = win(root, "나중에 연 창", 60)
    settle(root, 0.3)
    chk("새 창이 바로 뜬다", seen(later))
    later.withdraw()
    later.deiconify()
    settle(root, 0.3)
    chk("거뒀다 띄우기도 그대로 된다", seen(later))
    later.grab_set()
    chk("grab 도 평소대로 걸린다", str(later.grab_current()) == str(later))
    later.grab_release()

    print("\n=== 껐다 켰다 ===")
    chk("toggle: 숨김 -> 되돌림", st.toggle() is True and not seen(later) and st.toggle() is False)
    settle(root, 0.3)
    chk("  두 번 누르면 원래대로", seen(later) and seen(pet) and seen(toast))

    print("\n=== 트레이 메뉴의 글자 ===")
    chk("단축키가 없으면 '모두 숨기기'", TRAY.stealth_label(app) == "모두 숨기기")
    app.settings["bossKey"] = "ctrl+alt+h"
    chk("단축키를 골랐으면 옆에 적는다", TRAY.stealth_label(app) == "모두 숨기기  (%s)" % HK.label("ctrl+alt+h"))
    st.hide()
    chk("숨긴 동안에는 '다시 보이기'", TRAY.stealth_label(app) == "다시 보이기")
    st.show()
    settle(root, 0.2)
    app.settings["bossKey"] = ""

    print("\n=== 설정 창 ===")
    from poketdesktop.ui_settings import SettingsWindow
    for w in (hub, pet, folded, gone, toast, later):
        w.destroy()
    sw = SettingsWindow(app)
    top = sw.win.winfo_toplevel()
    top.deiconify()
    settle(root, 0.5)
    chk("단축키 줄이 있고 '쓰지 않음' 이 골라져 있다", sw.boss is not None and sw.boss.get() == ""
        and list(sw.boss_buttons) == list(HK.KEYS) and sw.boss_buttons["ctrl+alt+h"].cget("text") == HK.label("ctrl+alt+h"),
        list(sw.boss_buttons) if sw.boss is not None else None)
    sw.boss_buttons["ctrl+alt+x"].invoke()
    settle(root, 0.2)
    chk("조합을 고르면 앱에 등록을 맡기고 설정에 적힌다", app.registered[-1] == "ctrl+alt+x"
        and app.settings["bossKey"] == "ctrl+alt+x" and sw.boss_msg.cget("text") == "", app.registered)
    app.refuse = "ctrl+alt+p"
    sw.boss_buttons["ctrl+alt+p"].invoke()
    settle(root, 0.2)
    chk("등록하지 못하면 까닭을 적고 '쓰지 않음' 으로 돌린다", sw.boss.get() == "" and app.settings["bossKey"] == ""
        and "이미 쓰고 있는" in sw.boss_msg.cget("text") and app.registered[-2:] == ["ctrl+alt+p", ""],
        (sw.boss.get(), sw.boss_msg.cget("text"), app.registered[-2:]))
    sw.boss_buttons["ctrl+alt+h"].invoke()
    settle(root, 0.2)
    chk("  다른 조합을 고르면 까닭이 지워진다", sw.boss.get() == "ctrl+alt+h" and sw.boss_msg.cget("text") == "")
    sw.reset()
    settle(root, 0.2)
    chk("'기본값으로' 를 누르면 단축키도 풀린다", app.settings["bossKey"] == "" and sw.boss.get() == ""
        and app.registered[-1] == "", app.registered[-2:])
    sw.close()

    ST.uninstall()
    w = win(root, "문지기를 걷은 뒤", 60)
    settle(root, 0.2)
    chk("문지기를 걷으면 tkinter 가 원래대로다", seen(w) and tk.Wm.deiconify is tk.Wm.wm_deiconify)
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
