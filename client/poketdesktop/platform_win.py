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
                            hide_from_dock,
                            own_dialog, surface, take_keys, drop_keys)
from .platform_base import show_again as _base_show_again


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

    **쓰던 창의 포커스를 가져가지 않게 감싼다** (2.1.3, 게시판 #444). 창을 먼저 띄우고(update_idletasks)
    '항상 위' 를 거는데, 둘 다 테두리 없는 창을 활성화할 수 있다 - focus_guard 를 보라.
    """
    from . import focus_guard
    focus_guard.quiet(win, lambda: _raise_above(win))


def _raise_above(win):
    try:
        win.update_idletasks()
        before = (win.winfo_x(), win.winfo_y())
        win.attributes("-topmost", True)
        win.update_idletasks()
        if (win.winfo_x(), win.winfo_y()) != before:
            win.geometry("+%d+%d" % before)
    except Exception:                                       # noqa: BLE001
        pass

def keep_on_top(win):
    """다시 맨 위로. **SetWindowPos 로만 한다.**

    Tk 의 -topmost 를 다시 걸면 테두리 없는 창이 (0, 0) 으로 튄다
    (raise_above 의 설명). SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE 를 주면
    자리도 크기도 포커스도 안 건드리고 '항상 위' 무리의 맨 앞으로만 간다.
    """
    HWND_TOPMOST = -1
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        ctypes.windll.user32.SetWindowPos(
            ctypes.c_void_p(hwnd), ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    except Exception:                                       # noqa: BLE001
        pass


def _ours(hwnd):
    """그 창이 이 프로그램(프로세스)의 것인가."""
    import os
    pid = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return pid.value == os.getpid()


def _desktop(hwnd):
    """바탕화면 창인가 (Progman / WorkerW - 아이콘과 배경을 그리는 창)."""
    buf = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 64)
    return buf.value in ("Progman", "WorkerW")


def send_back(win):
    """'항상 위' 를 풀고 **지금 쓰는 창 바로 뒤로** 넣는다 (2.5.0, 설정 petBehind, 게시판 #533).

    맨 아래(HWND_BOTTOM)로 보내면 바탕화면 창(Progman) 뒤로 들어가 아예 안 보일 수 있다. 그래서 지금 앞에 있는
    창(GetForegroundWindow) 바로 뒤에 끼운다 - 그 창을 가리지 않고, 바탕화면보다는 위다. 앞 창이 우리 것이거나
    바탕화면이면 '항상 위' 만 푼다 - 다른 프로그램을 누르면 윈도우가 그 창을 우리 위로 올린다.

    -topmost 를 풀 때 테두리 없는 창이 (0, 0) 으로 튀면 제자리로 돌린다 (raise_above 와 같다). 포커스는 안
    가져간다 (SWP_NOACTIVATE, focus_guard).
    """
    from . import focus_guard
    focus_guard.quiet(win, lambda: _send_back(win))


def _send_back(win):
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x0001, 0x0002, 0x0010, 0x0200
    try:
        win.update_idletasks()
        before = (win.winfo_x(), win.winfo_y())
        win.attributes("-topmost", False)
        win.update_idletasks()
        if (win.winfo_x(), win.winfo_y()) != before:
            win.geometry("+%d+%d" % before)
        u = ctypes.windll.user32
        me = u.GetParent(win.winfo_id()) or win.winfo_id()
        fg = u.GetForegroundWindow()
        if fg and fg != me and not _ours(fg) and not _desktop(fg):
            u.SetWindowPos(ctypes.c_void_p(me), ctypes.c_void_p(fg), 0, 0, 0, 0,
                           SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)
    except Exception:                                       # noqa: BLE001
        pass


def show_again(win):
    """숨긴 창을 다시 보여준다 (platform_base.show_again). 다른 창 뒤로 다니는 포켓몬(win._poket_behind)은
    여기의 send_back 으로 - 기본 구현의 send_back 은 지금 쓰는 창 뒤로 넣지 못한다."""
    if getattr(win, "_poket_behind", False):
        win.deiconify()
        send_back(win)
        return
    _base_show_again(win)


def order_below(win, ref):
    """win 을 ref 바로 아래로 (꾸미기 효과 창 - deco_fx). SetWindowPos 의 '뒤에 넣기' - 다른 창 · 포커스는 그대로."""
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x0001, 0x0002, 0x0010, 0x0200
    try:
        u = ctypes.windll.user32
        a = u.GetParent(win.winfo_id()) or win.winfo_id()
        b = u.GetParent(ref.winfo_id()) or ref.winfo_id()
        u.SetWindowPos(ctypes.c_void_p(a), ctypes.c_void_p(b), 0, 0, 0, 0,
                       SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)
        return True
    except Exception:                                       # noqa: BLE001
        return False


# ---------------------------------------------------------------- 숨바꼭질 (시즌 7, 2026-11-27)
# 창 뒤 · 작업표시줄 뒤 · 바탕화면 가장자리 - 셋 다 SetWindowPos 의 '이 창 뒤에 넣기' 로 된다 (send_back 과 같은 꼴).
# 이 맥에서는 돌려 볼 수 없어서 창을 거르는 셈(_keep_window) · 좌표 고르기(_frame_rect) · 전체 화면 판정(_busy_state)은
# 순수 함수로 떼고, 창 목록 · 모니터 DPI 는 가짜 Win32(_HIDE · _DPI 자리)로 검사한다 (test_hide_ui.FakeWin32).
#
# 좌표 (검토 #3 · #7): 이 앱은 '시스템 DPI' 앱이다 (dpi_aware - SetProcessDpiAwareness(1)). 그래서 Tk · screens() ·
# 활동 영역 · GetWindowRect 는 시스템 DPI 로 바꿔 준(가상화한) 논리 좌표고, 배율이 시스템 DPI 와 다른 모니터에서는 물리
# 픽셀과 어긋난다. 창 목록도 같은 논리 좌표로 맞춘다 (_frame_rect). 그런 모니터의 창은 odd (걸지 않는다), 활동 영역이 그런
# 모니터에 있으면 창 뒤 · 가장자리 자리를 아예 안 쓴다 (monitor_dpi_mismatch - hide.kinds_at).
HIDE_KINDS = ("window", "bar", "edge")

_SWP = 0x0001 | 0x0002 | 0x0010 | 0x0200         # NOSIZE | NOMOVE | NOACTIVATE | NOOWNERZORDER
_SKIP_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")
_BARS = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
_HIDE = None
_DPI = None
_PER_MONITOR = -3          # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE
_MONITOR_NEAREST = 2       # MONITOR_DEFAULTTONEAREST


def _hide_fns():
    """창 목록 · 겹침 순서에 쓰는 함수들 (한 번만 만든다). 핸들이 64비트라 타입을 정해 둔다 - 안 정하면 잘린다."""
    global _HIDE
    if _HIDE is None:
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows.argtypes = [proc, wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL
        for nm in ("IsWindowVisible", "IsIconic", "IsZoomed"):
            getattr(u, nm).argtypes = [wintypes.HWND]
            getattr(u, nm).restype = wintypes.BOOL
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND
        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindow.restype = wintypes.HWND
        u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowExW.restype = wintypes.HWND
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.UINT]
        u.SetWindowPos.restype = wintypes.BOOL
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.MonitorFromWindow.restype = wintypes.HMONITOR
        u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        u.MonitorFromPoint.restype = wintypes.HMONITOR
        u.GetDC.argtypes = [wintypes.HWND]
        u.GetDC.restype = wintypes.HDC
        u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        u.ReleaseDC.restype = ctypes.c_int
        sysdpi = getattr(u, "GetDpiForSystem", None)            # 윈도 10 1607 부터
        if sysdpi is not None:
            sysdpi.argtypes = []
            sysdpi.restype = wintypes.UINT
        ctx = getattr(u, "SetThreadDpiAwarenessContext", None)  # 윈도 10 1607 부터 - DPI_AWARENESS_CONTEXT 는 손잡이(포인터)
        if ctx is not None:
            ctx.argtypes = [ctypes.c_void_p]
            ctx.restype = ctypes.c_void_p
        try:
            dwm = ctypes.WinDLL("dwmapi")
            dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        except Exception:                                   # noqa: BLE001
            dwm = None
        _HIDE = (u, dwm, proc)
    return _HIDE


def _dpi_fns():
    """(shcore, gdi32) - 모니터 DPI · 시스템 DPI 를 묻는 함수 (한 번만). 없는 윈도(8.1 앞 shcore 없음)는 그 칸이 None."""
    global _DPI
    if _DPI is None:
        from ctypes import wintypes
        try:
            sh = ctypes.WinDLL("shcore")
            sh.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int, ctypes.POINTER(wintypes.UINT),
                                            ctypes.POINTER(wintypes.UINT)]
            sh.GetDpiForMonitor.restype = ctypes.c_long         # HRESULT
        except Exception:                                   # noqa: BLE001
            sh = None
        try:
            gdi = ctypes.WinDLL("gdi32")
            gdi.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
            gdi.GetDeviceCaps.restype = ctypes.c_int
        except Exception:                                   # noqa: BLE001
            gdi = None
        _DPI = (sh, gdi)
    return _DPI


def _sys_dpi(u, gdi):
    """시스템 DPI - 이 프로세스의 논리 좌표가 맞는 DPI. GetDpiForSystem 이 없는 윈도는 화면 DC 의 LOGPIXELSX
    (시스템 DPI 앱에게는 시스템 DPI 다). 모르면 0."""
    fn = getattr(u, "GetDpiForSystem", None)
    if fn is not None:
        try:
            v = int(fn())
            if v > 0:
                return v
        except Exception:                                   # noqa: BLE001
            pass
    if gdi is not None:
        try:
            dc = u.GetDC(None)
            try:
                return int(gdi.GetDeviceCaps(dc, 88) or 0)      # LOGPIXELSX
            finally:
                u.ReleaseDC(None, dc)
        except Exception:                                   # noqa: BLE001
            pass
    return 0


def _monitor_dpi(u, sh, hmon):
    """그 모니터의 실제 배율 DPI (MDT_EFFECTIVE_DPI). 모르면 0 (= 다르지 않다고 본다).

    **GetDpiForMonitor 는 부르는 쪽의 DPI 인식을 따른다** - 우리 같은 시스템 DPI 앱이 그냥 부르면 어느 모니터든
    시스템 DPI 를 돌려준다 (문서의 표). 그래서 이 스레드만 잠깐 '모니터마다' 로 바꿔 묻고 바로 되돌린다 (그 사이 창을
    만들지 않으니 다른 것은 안 바뀐다). 그 함수가 없는 윈도(10 1607 앞)는 물어도 시스템 DPI 라 0 으로 둔다."""
    from ctypes import wintypes
    setctx = getattr(u, "SetThreadDpiAwarenessContext", None)
    if sh is None or setctx is None or not hmon:
        return 0
    old = setctx(_PER_MONITOR)
    if not old:
        return 0                                            # 못 바꿨다 - 물으면 시스템 DPI 가 온다
    try:
        x, y = wintypes.UINT(0), wintypes.UINT(0)
        if sh.GetDpiForMonitor(hmon, 0, ctypes.byref(x), ctypes.byref(y)) != 0:     # MDT_EFFECTIVE_DPI
            return 0
        return int(x.value)
    finally:
        setctx(old)


def _dpi_differs(mon_dpi, sys_dpi):
    """모니터 DPI 가 시스템 DPI 와 다른가 (둘 중 하나라도 모르면 다르지 않다고 본다)."""
    return bool(mon_dpi and sys_dpi and int(mon_dpi) != int(sys_dpi))


def _frame_rect(win_rect, dwm_rect, sys_dpi=96):
    """창 사각형을 Tk · screens() 와 같은 논리 좌표로 -> (rect, 배율이 다름).

    GetWindowRect 는 이 스레드(시스템 DPI)에 맞춰 바꿔 준 논리 좌표다. DWM EXTENDED_FRAME_BOUNDS 는 DPI 를 안 맞춘
    물리 픽셀이다 (문서). 둘은 시스템 DPI 와 배율이 같은 모니터에서만 같은 공간이고, 그때 DWM 쪽이 안 보이는 크기 조절
    테두리(윈 10 - 100% 에서 7px)를 뺀 눈에 보이는 테두리다. 그래서 **네 변이 다 테두리 폭 안으로만 다르면** DWM 을 쓰고,
    아니면(배율이 달라 크기 · 자리가 어긋남) GetWindowRect 를 쓰고 '배율이 다름' 을 알린다. DWM 칸이 창 안에 들어가는지만
    보면 안 된다 - 배율이 시스템보다 낮은 모니터의 물리 칸은 더 커진 논리 칸 안에 들어가 버린다 (모니터 왼쪽 위 근처).
    테두리 폭은 시스템 배율을 따라 커진다 (300% 에서 21px 쯤) - 16px 를 시스템 배율만큼 늘려 잰다.
    (검토 #3: DWM 칸을 그대로 쓰면 1/1.5 크기 · 어긋난 자리로 덮임을 봐서, 덮인 가장자리를 '보인다' 고 골랐다)"""
    w = tuple(int(v) for v in win_rect)
    if not dwm_rect:
        return w, False
    d = tuple(int(v) for v in dwm_rect)
    if d[2] <= d[0] or d[3] <= d[1]:
        return w, False
    tol = 16 * max(96, int(sys_dpi or 96)) // 96
    if all(abs(a - b) <= tol for a, b in zip(d, w)):
        return d, False
    return w, True


def _keep_window(visible, iconic, style, exstyle, pid, me, cls, cloaked, rect, zoomed, mon_dpi, sys_dpi, scaled=False):
    """창 하나를 숨바꼭질 창 목록에 넣을까 - 넣으면 {rect, max, top, odd, own}, 빼면 None. **제목은 안 본다.**

    빼는 것: 안 보임 · 최소화 · 자식 창 · 도구 창(WS_EX_TOOLWINDOW) · 눌러도 안 앞으로 오는 창(WS_EX_NOACTIVATE) ·
    바탕화면(Progman / WorkerW) · 작업표시줄 · 클로킹(다른 가상 데스크톱 · 숨긴 UWP) · 크기 0.
    own: 이 앱의 창 - 빼지 않고 남긴다 (검토 #4). 테두리 없는 우리 창(도트 · 이름표 · 숨은 포켓몬)은 Tk 가 도구 창으로
    만들어서 위에서 빠지고, 남는 것은 포켓몬 관리 · PC 박스 · 설정 같은 테두리 있는 창뿐이다 - 그 밑의 가장자리 · 창 뒤
    자리는 진짜로 가려진다. 걸지는 않는다 (hide_spots.anchor_for).
    odd: 그 창이 있는 **모니터**의 DPI 가 시스템 DPI 와 다르거나(mon_dpi) 좌표 배율이 어긋났다(scaled, _frame_rect) -
    그 창의 DPI 인식(GetDpiForWindow)으로 보면 시스템 DPI 앱 창은 어느 모니터에 있든 시스템 DPI 라 놓친다 (검토 #7)."""
    if not visible or iconic:
        return None
    if style & 0x40000000:                                  # WS_CHILD
        return None
    if exstyle & (0x00000080 | 0x08000000):                 # WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        return None
    if cls in _SKIP_CLASSES or cloaked:
        return None
    x1, y1, x2, y2 = (int(v) for v in rect)
    if x2 <= x1 or y2 <= y1:
        return None
    return {"rect": (x1, y1, x2, y2), "max": bool(zoomed), "top": bool(exstyle & 0x00000008),   # WS_EX_TOPMOST
            "odd": bool(scaled) or _dpi_differs(mon_dpi, sys_dpi), "own": pid == me}


def _busy_state(n):
    """SHQueryUserNotificationState 값 -> 전체 화면/발표 중인가 (QUNS_BUSY 2 · RUNNING_D3D_FULL_SCREEN 3 ·
    PRESENTATION_MODE 4). 방해 금지(5 QUNS_QUIET_TIME)나 보통(5 · 6 · 1)은 아니다."""
    return int(n) in (2, 3, 4)


def _cls(u, hwnd):
    buf = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(hwnd, buf, 64)
    return buf.value


def _rect_of(u, dwm, hwnd, sys_dpi):
    """(논리 좌표 사각형, 배율이 다름) - GetWindowRect 와 DWM 눈에 보이는 테두리를 둘 다 읽어 _frame_rect 로 고른다."""
    from ctypes import wintypes
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    d = None
    if dwm is not None:
        f = wintypes.RECT()
        try:
            if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(f), ctypes.sizeof(f)) == 0:   # EXTENDED_FRAME_BOUNDS
                d = (f.left, f.top, f.right, f.bottom)
        except Exception:                                   # noqa: BLE001
            d = None
    return _frame_rect((r.left, r.top, r.right, r.bottom), d, sys_dpi)


def other_windows():
    """보이는 보통 창 - EnumWindows 는 앞에서부터 준다. 위치 · 크기 · 손잡이만 (제목은 안 읽는다).

    이 앱의 테두리 있는 창도 own 으로 든다 (가리는 창으로만), 좌표는 Tk 와 같은 논리 좌표 (_frame_rect), odd 는 그 창이
    있는 모니터의 DPI 가 시스템 DPI 와 다르거나 좌표 배율이 어긋난 창."""
    import os
    from ctypes import wintypes
    try:
        u, dwm, proc = _hide_fns()
        sh, gdi = _dpi_fns()
        me = os.getpid()
        sysdpi = _sys_dpi(u, gdi)
        mons = {}                                           # 모니터 손잡이 -> DPI (창마다 묻지 않는다)
        out = []

        def each(hwnd, _l):
            try:
                if not u.IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD(0)
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                cloaked = wintypes.DWORD(0)
                if dwm is not None:
                    dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))   # CLOAKED
                rect, scaled = _rect_of(u, dwm, hwnd, sysdpi)
                hmon = u.MonitorFromWindow(hwnd, _MONITOR_NEAREST)
                key = int(hmon or 0)
                if key not in mons:
                    mons[key] = _monitor_dpi(u, sh, hmon)
                got = _keep_window(
                    True, bool(u.IsIconic(hwnd)), u.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF,
                    u.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF, int(pid.value), me, _cls(u, hwnd),
                    int(cloaked.value), rect, bool(u.IsZoomed(hwnd)), mons[key], sysdpi, scaled)
                if got is not None:
                    got["id"] = int(hwnd)
                    out.append(got)
            except Exception:                               # noqa: BLE001
                pass
            return True
        cb = proc(each)
        u.EnumWindows(cb, 0)
        return out
    except Exception:                                       # noqa: BLE001
        return []


def monitor_dpi_mismatch(rect):
    """활동 영역(rect)이 있는 모니터의 DPI 가 시스템 DPI 와 다른가. 다르면 그 모니터의 창 · 화면 좌표가 물리 픽셀과
    어긋나서(가상화 배율) 창 뒤 · 가장자리 자리를 믿을 수 없다 - 부르는 쪽(hide.kinds_at)이 작업표시줄 자리만 쓴다
    (검토 #3 · #7). 모니터는 hide_spots.monitor_for 처럼 영역의 오른쪽 아래 모서리로 고른다. 모르면 False."""
    from ctypes import wintypes
    try:
        u = _hide_fns()[0]
        sh, gdi = _dpi_fns()
        hmon = u.MonitorFromPoint(wintypes.POINT(int(rect[2]) - 1, int(rect[3]) - 1), _MONITOR_NEAREST)
        return _dpi_differs(_monitor_dpi(u, sh, hmon), _sys_dpi(u, gdi))
    except Exception:                                       # noqa: BLE001
        return False


def _me(u, win):
    return u.GetParent(win.winfo_id()) or win.winfo_id()


def _unpin(win):
    """'항상 위' 를 푼다 - 테두리 없는 창이 (0, 0) 으로 튀면 제자리로 (_send_back 과 같다). 이미 풀려 있으면 그대로."""
    if not int(win.attributes("-topmost")):
        return
    win.update_idletasks()
    before = (win.winfo_x(), win.winfo_y())
    win.attributes("-topmost", False)
    win.update_idletasks()
    if (win.winfo_x(), win.winfo_y()) != before:
        win.geometry("+%d+%d" % before)


def order_just_below(win, other_id, strip=None):
    """win 을 그 창 바로 뒤로 (SetWindowPos 의 '이 창 뒤에 넣기'). 포커스는 안 가져간다.

    strip(보일 띠)은 안 본다 - 윈도우는 부탁한 그 자리에 넣는다 (주인 있는 창 뒤라도 그 창과 주인 사이에 들어간다).
    맥은 자식 창이면 부모 뒤로 가서 걸고 나서 본다 (platform_mac.order_just_below)."""
    from . import focus_guard

    def go():
        try:
            if not win.winfo_viewable():
                return False
            u = _hide_fns()[0]
            _unpin(win)
            return bool(u.SetWindowPos(_me(u, win), other_id, 0, 0, 0, 0, _SWP))
        except Exception:                                   # noqa: BLE001
            return False
    return bool(focus_guard.quiet(win, go))


def _bar_for(u, win):
    """win 이 있는 모니터의 작업표시줄 (주 화면 Shell_TrayWnd · 다른 화면 Shell_SecondaryTrayWnd). 없으면 None."""
    from ctypes import wintypes
    cx = win.winfo_rootx() + win.winfo_width() // 2
    cy = win.winfo_rooty() + win.winfo_height() // 2
    best, bd = None, None
    for name in _BARS:
        h = u.FindWindowExW(None, None, name, None)
        while h:
            r = wintypes.RECT()
            if u.GetWindowRect(h, ctypes.byref(r)) and u.IsWindowVisible(h):
                dx = max(r.left - cx, 0, cx - r.right)
                dy = max(r.top - cy, 0, cy - r.bottom)
                d = dx * dx + dy * dy
                if bd is None or d < bd:
                    best, bd = h, d
            h = u.FindWindowExW(None, h, name, None)
    return best


def order_below_bar(win):
    """win 을 작업표시줄 바로 뒤로 - 작업표시줄은 '항상 위' 라 그 뒤에 넣으면 우리도 '항상 위' 무리에 들어가 보통 창보다
    위, 작업표시줄보다 아래가 된다. Overlay.keep_on_top 은 _poket_hider 를 보고 이 창을 맨 위로 안 올린다."""
    from . import focus_guard

    def go():
        try:
            if not win.winfo_viewable():
                return False
            u = _hide_fns()[0]
            bar = _bar_for(u, win)
            if not bar:
                return False
            return bool(u.SetWindowPos(_me(u, win), bar, 0, 0, 0, 0, _SWP))
        except Exception:                                   # noqa: BLE001
            return False
    return bool(focus_guard.quiet(win, go))


def _desktop_host(u):
    """바탕화면 아이콘을 그리는 맨 위 창 (SHELLDLL_DefView 를 품은 Progman 이나 WorkerW)."""
    for name in ("Progman", "WorkerW"):
        h = u.FindWindowExW(None, None, name, None)
        while h:
            if u.FindWindowExW(h, None, "SHELLDLL_DefView", None):
                return h
            h = u.FindWindowExW(None, h, name, None)
    return None


def order_above_desktop(win):
    """win 을 모든 보통 창 뒤 · 바탕화면 바로 위로. **HWND_BOTTOM 으로 보내지 않는다** - 바탕화면(Progman) 뒤로 들어가
    아예 안 보인다 (send_back 의 설명). 바탕화면 창 바로 위 창의 뒤에 넣는다."""
    from . import focus_guard

    def go():
        try:
            if not win.winfo_viewable():
                return False
            u = _hide_fns()[0]
            desk = _desktop_host(u)
            if not desk:
                return False
            me = _me(u, win)
            _unpin(win)
            prev = u.GetWindow(desk, 3)                     # GW_HWNDPREV - 바탕화면 바로 위 창
            if not prev:
                return False
            if int(prev) == int(me):
                return True                                 # 이미 그 자리
            return bool(u.SetWindowPos(me, prev, 0, 0, 0, 0, _SWP))
        except Exception:                                   # noqa: BLE001
            return False
    return bool(focus_guard.quiet(win, go))


def fullscreen_busy():
    """전체 화면 앱 · 게임 · 발표 중 (SHQueryUserNotificationState). 그동안은 숨은 포켓몬을 청하지 않는다."""
    try:
        n = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(n)) != 0:
            return False
        return _busy_state(n.value)
    except Exception:                                       # noqa: BLE001
        return False


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


def _monitors():
    """[(화면 사각형, 작업 영역 사각형, 주 화면인가)] - EnumDisplayMonitors.

    좌표는 이 프로세스가 보는 화면 좌표다 (Tk 가 창을 놓을 때 쓰는 것과 같다).
    왼쪽이나 위에 둔 모니터는 음수가 된다.
    """
    from ctypes import wintypes
    out = []

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32 = ctypes.windll.user32
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)

    def each(hmon, _hdc, _rect, _data):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        get = user32.GetMonitorInfoW
        get.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        if get(hmon, ctypes.byref(mi)):
            m, w = mi.rcMonitor, mi.rcWork
            out.append(((m.left, m.top, m.right, m.bottom),
                        (w.left, w.top, w.right, w.bottom),
                        bool(mi.dwFlags & 1)))               # MONITORINFOF_PRIMARY
        return 1

    cb = proc_t(each)
    enum = user32.EnumDisplayMonitors
    enum.argtypes = [ctypes.c_void_p, ctypes.c_void_p, proc_t, ctypes.c_void_p]
    enum(None, None, cb, None)
    out.sort(key=lambda t: (not t[2], t[0][0], t[0][1]))      # 주 화면이 맨 앞
    return out


def screens(fallback_w, fallback_h):
    """모든 화면을 Tk 좌표로. 첫 번째가 주 화면 (1.9.1).

    **그동안 윈도우에서는 주 화면 하나만 돌려줬다** (기본 구현을 그대로 썼다).
    모니터가 둘이어도 둘째 화면을 몰라서, 화면을 골라 영역으로 삼을 수가 없었다.
    """
    try:
        got = [m[0] for m in _monitors() if m[0][2] > m[0][0] and m[0][3] > m[0][1]]
        if got:
            return got
    except Exception:                                       # noqa: BLE001
        pass
    return [(0, 0, fallback_w, fallback_h)]


def screen_works(fallback_w, fallback_h):
    """화면마다 작업표시줄을 뺀 영역. screens() 와 같은 차례다."""
    try:
        got = [m[1] for m in _monitors() if m[0][2] > m[0][0] and m[0][3] > m[0][1]]
        if got:
            return got
    except Exception:                                       # noqa: BLE001
        pass
    return [work_area(fallback_w, fallback_h)]


def virtual_screen(fallback_w, fallback_h):
    """모니터 전부를 아우르는 사각형. 왼쪽/위 모니터가 있으면 x·y 가 음수다."""
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    try:
        g = ctypes.windll.user32.GetSystemMetrics
        x, y = g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN)
        w, h = g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN)
        if w > 0 and h > 0:
            return x, y, x + w, y + h
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


_IMM = None


def _imm():
    """조합 글자를 읽는 함수들 (한 번만 만든다). 핸들이 64비트라 타입을 정해 둔다 - 안 정하면 잘린다."""
    global _IMM
    if _IMM is None:
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")
        imm = ctypes.WinDLL("imm32")
        u.GetFocus.restype = wintypes.HWND
        u.GetFocus.argtypes = []
        imm.ImmGetContext.restype = wintypes.HANDLE
        imm.ImmGetContext.argtypes = [wintypes.HWND]
        imm.ImmGetCompositionStringW.restype = wintypes.LONG
        imm.ImmGetCompositionStringW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                                 wintypes.DWORD]
        imm.ImmReleaseContext.restype = wintypes.BOOL
        imm.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        _IMM = (u, imm)
    return _IMM


GCS_COMPSTR = 0x0008


def ime_composition():
    """한글 입력기가 지금 조합 중인 글자 (없으면 "").

    윈도우 Tk 는 입력기가 다 짠 글자만 칸에 넣고, 짜는 중인 글자('녕' 을 치다 만 'ㄴ'·'녀')는 칸에
    그리지 않는다. 그래서 친구 채팅에서 글자가 한 박자씩 늦게 보였다. 키보드 포커스를 가진 창의
    입력기에 직접 묻는다 (Tk 를 돌리는 이 스레드의 포커스).
    """
    try:
        u, imm = _imm()
        hwnd = u.GetFocus()
        if not hwnd:
            return ""
        himc = imm.ImmGetContext(hwnd)
        if not himc:
            return ""
        try:
            size = imm.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
            if size <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(size // 2 + 1)
            imm.ImmGetCompositionStringW(himc, GCS_COMPSTR, buf, size)
            return buf.value[:size // 2]
        finally:
            imm.ImmReleaseContext(hwnd, himc)
    except Exception:                                       # noqa: BLE001
        return ""


_TITLE = None


def _title_fns():
    """맨 앞 창 제목을 읽는 함수들 (한 번만 만든다). 핸들이 64비트라 타입을 정해 둔다 - 안 정하면 잘린다."""
    global _TITLE
    if _TITLE is None:
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetForegroundWindow.argtypes = []
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        _TITLE = u
    return _TITLE


def foreground_title():
    """맨 앞 창의 제목 하나 (아르케 2.4.0 '브라우저 단서 찾기'). 없거나 못 읽으면 None.

    **제목만 읽는다** - 주소 · 방문 기록 · 페이지 내용 · 다른 창은 보지 않는다. 서명 · 관리자 권한도 필요 없다
    (GetWindowTextW 는 보통 권한으로 남의 창 제목을 준다). 읽은 제목을 저장하거나 보내는 일은 여기서 하지 않는다 -
    arche_title.TitleWatch 가 맞는 말일 때만 알린다.
    """
    try:
        u = _title_fns()
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return None
        n = u.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return None
        n = min(int(n), 1024)                               # 아주 긴 제목은 앞만 (맞을 말은 짧다)
        buf = ctypes.create_unicode_buffer(n + 1)
        got = u.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value[:got] if got > 0 else None
    except Exception:                                       # noqa: BLE001
        return None


def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:                                       # noqa: BLE001
        pass


def pin_tk_scaling(root, every_ms=500):
    """켤 때의 tk scaling 을 붙잡아 둔다. 바뀌면 되돌린다 (게시판 #707). 확인 함수를 돌려준다.

    tk.Tk() 가 dpi_aware() 보다 먼저라 Tk 은 96 DPI(1.333)로 잡힌다. 켜 둔 사이 WM_DISPLAYCHANGE 가 오면
    (모니터 절전 · 연결 · 해상도 - 추정) Tk 이 그때는 실제 DPI 로 다시 재서 150% 화면이면 2.0 이 된다. 그 뒤 새로
    만드는 글꼴만 커지고, 바탕화면에 떠 있던 글꼴(FONT_S = FONT_TIP)은 캐시에 옛 크기로 남아 섞였다.

    0.5초마다 보고 다르면 켤 때 값으로 되돌린다. 되돌릴 때마다 로그에 남긴다 (언제 바뀌는지 보려고).
    확인 함수는 root._pin_tk_scaling 에 둔다 - style_window 가 창을 만들 때 한 번 더 부른다 (0.5초 틈).
    Tk 만 부른다 - 윈도우 API 를 안 쓰니 맥에서도 돈다 (검사가 맥에서 돈다). 맥은 platform_os 가 안 건다.

    dpi_aware 를 tk.Tk() 앞으로 옮기면 안 된다 - 켤 때부터 글꼴이 1.5배가 되는데 칸 · 줄 높이(h() · COLS)는
    픽셀 그대로라 모든 창이 넘친다.

    비교는 **상대 1%** 다 (절대 1e-3 이 아니다). Tk 은 scaling 을 화면 폭의 정수 mm 로 들고 있다 (tkCmds.c:
    읽기 25.4/72*W/mm, 쓰기 mm=(int)(25.4/72/v*W+0.5)). WM_DISPLAYCHANGE 는 새 폭 W 로 mm 를 다시 잰다.
    그래서 W 가 켤 때와 다르면 want 를 넣고 다시 읽어도 0.5/mm 만큼(1920 폭에서 약 0.1%) 어긋난다 - 절대 1e-3 이면
    0.5초마다 '되돌림' 을 끝없이 남겼다 (하루 17만 줄). 해상도만 바뀐 100% 화면도 그랬다. 진짜 배율은 25% 씩 바뀐다.
    """
    import tkinter as tk
    have = getattr(root, "_pin_tk_scaling", None)
    if have is not None:                                    # 두 번 불러도 고리는 하나
        return have
    try:
        want = float(root.tk.call("tk", "scaling"))
    except (tk.TclError, ValueError):
        return None

    def check():
        """지금 값이 켤 때와 다르면 되돌린다. 계속 볼 수 있으면 True (root 가 없어졌으면 False)."""
        try:
            now = float(root.tk.call("tk", "scaling"))
            if abs(now - want) > want * 0.01:               # mm 반올림(폭이 바뀌면 생김)은 넘기고 배율만 본다
                root.tk.call("tk", "scaling", want)
                from . import config
                config.log("tk scaling %.3f -> %.3f 되돌림 (화면 배율이 바뀜, 게시판 #707)" % (now, want))
            return True
        except (tk.TclError, ValueError):
            return False

    def tick():
        if not check():
            return
        try:
            root.after(every_ms, tick)
        except tk.TclError:
            pass

    root._pin_tk_scaling = check
    try:
        root.after(every_ms, tick)
    except tk.TclError:
        return None
    return check


# ---------------------------------------------------------------- 글꼴
def font_candidates():
    return ["맑은 고딕", "Malgun Gothic"]


def pil_font_files(bold=False):
    return ("malgunbd.ttf", "malgun.ttf") if bold else ("malgun.ttf",)


def register_font(path):
    """AddFontResourceEx(FR_PRIVATE) - 이 프로세스만 보는 글꼴로 등록한다 (설치하지 않는다)."""
    from ctypes import wintypes
    FR_PRIVATE = 0x10
    try:
        gdi = ctypes.windll.gdi32
        gdi.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        gdi.AddFontResourceExW.restype = ctypes.c_int
        return gdi.AddFontResourceExW(path, FR_PRIVATE, None) > 0
    except Exception:                                       # noqa: BLE001
        return False


def already_running_hint():
    """이미 돌고 있다고 알릴 때, 어디를 보라고 할 것인가."""
    return ("작업표시줄 오른쪽 끝의 '숨겨진 아이콘 표시'(^) 를 눌러\n"
            "몬스터볼 아이콘을 찾아보세요.")

