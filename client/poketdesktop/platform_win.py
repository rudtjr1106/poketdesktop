# -*- coding: utf-8 -*-
"""윈도우에서만 쓰는 것들.

여기 있는 코드는 전부 **원래 있던 자리에서 그대로 옮겨온 것**이다.
옮기면서 고친 것은 없다. 겸사겸사 고치면 뭐가 깨졌는지 못 찾는다.

어디서 왔는지:

    transparent_window   overlay.py:61  wild_ui.py:47,255  fx_layer.py:54
    make_click_through   fx_layer.py:16
    work_area            overlay.py:22
    double_click_ms      wild_ui.py:220 (_double_ms)
    single_lock          single.py:24 (_win_lock)
    machine_raw          config.py:149
    dpi_aware            app.py:81
"""
import ctypes

from .platform_base import (NATIVE_MENU, RIGHT_CLICK,   # noqa: F401
                            SpriteView, accept_first_click, activate, keep_focus,
                            bind_right, data_dir, mouse_buttons_down,
                            take_right_clicks, watch_right_click,
                            hide_from_dock, screens, show_again,
                            own_dialog, surface)


def raise_above(win):
    """항상 위로. **자리를 지켜 준다.**

    윈도우에서 테두리 없는 창(overrideredirect)에 -topmost 를 걸면 창이
    왼쪽 위 (0, 0) 으로 튄다. 그래서 마우스를 올렸을 때 뜨는 설명이
    포켓몬 위가 아니라 화면 구석에 나타났다.

    맥은 정반대로 **창이 뜬 뒤에** 걸어야 먹는다(platform_mac.raise_above).
    그래서 부르는 쪽에서 순서를 맞추는 대신 여기서 자리를 되돌린다 -
    호출부가 열 군데라 하나씩 고치면 다음에 또 빠진다.

    튀지 않았으면 아무것도 안 한다. 아직 자리를 안 잡은 창(만들자마자
    부르고 나중에 place 하는 것들)을 엉뚱한 데 붙박지 않으려는 것이다.
    """
    try:
        win.update_idletasks()
        before = (win.winfo_x(), win.winfo_y())
        win.attributes("-topmost", True)
        win.update_idletasks()
        if (win.winfo_x(), win.winfo_y()) != before:
            win.geometry("+%d+%d" % before)
    except Exception:                                       # noqa: BLE001
        pass

NAME = "poketdesktop-single-instance"


# ---------------------------------------------------------------- 창
def transparent_window(win, hexkey):
    """특정 색을 칠해 두면 윈도우가 그 색만 뚫어 준다."""
    win.attributes("-topmost", True)
    win.attributes("-transparentcolor", hexkey)
    win.configure(bg=hexkey)
    return hexkey


def make_click_through(win):
    """창 전체를 클릭이 통과하도록 만든다."""
    try:
        from ctypes import wintypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        u = ctypes.windll.user32
        u.GetWindowLongW.restype = ctypes.c_long
        style = u.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
        u.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE,
                         style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                         | WS_EX_TOOLWINDOW)
        return True
    except Exception:                                       # noqa: BLE001
        return False


# ---------------------------------------------------------------- 화면
def work_area(fallback_w, fallback_h):
    """작업표시줄을 뺀 화면 영역."""
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        r = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return r.left, r.top, r.right, r.bottom
    except Exception:                                       # noqa: BLE001
        pass
    return 0, 0, fallback_w, fallback_h


def double_click_ms():
    """이 PC 에서 두 번 클릭으로 치는 간격(ms)."""
    try:
        v = int(ctypes.windll.user32.GetDoubleClickTime())
        return max(160, min(600, v))
    except Exception:                                       # noqa: BLE001
        return 350


# ---------------------------------------------------------------- 프로세스
def single_lock(data_dir_):
    """이름 있는 뮤텍스. 이미 있으면 다른 인스턴스가 돌고 있다는 뜻.

    프로세스가 어떻게 죽든 - 강제 종료든 정전이든 - 커널이 알아서
    놓아주기 때문에, 잠금 파일처럼 '지우지 못한 채 죽어서 다시는 못
    켜는' 일이 없다.
    """
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL,
                                 wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    # 이름 앞에 Local\ 을 붙여 같은 세션 안에서만 겹치게 한다. 여러 사용자가
    # 각자 로그인해 쓰는 컴퓨터에서 남의 것까지 막으면 안 된다.
    h = k32.CreateMutexW(None, False, "Local\\" + NAME)
    if not h:
        return None, False
    return h, k32.GetLastError() == ERROR_ALREADY_EXISTS


def single_release(handle):
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:                                       # noqa: BLE001
        pass


def machine_raw():
    """레지스트리의 MachineGuid."""
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Cryptography", 0,
                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        raw = winreg.QueryValueEx(k, "MachineGuid")[0]
        winreg.CloseKey(k)
        return raw
    except Exception:                                       # noqa: BLE001
        return None


def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:                                       # noqa: BLE001
        pass


# ---------------------------------------------------------------- 글꼴
def font_candidates():
    return ["맑은 고딕", "Malgun Gothic"]


def pil_font_files(bold=False):
    return ("malgunbd.ttf", "malgun.ttf") if bold else ("malgun.ttf",)


def already_running_hint():
    """이미 돌고 있다고 알릴 때, 어디를 보라고 할 것인가."""
    return ("작업표시줄 오른쪽 끝의 '숨겨진 아이콘 표시'(^) 를 눌러\n"
            "몬스터볼 아이콘을 찾아보세요.")

