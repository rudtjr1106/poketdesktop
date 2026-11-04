# -*- coding: utf-8 -*-
"""포커스 지키기 (2.1.3, 게시판 #444 선언) — 바탕화면의 도트 · 이름표 · 연출 창이 떠도 쓰던 창(앱)의 포커스를
가져가지 않게 한다. 윈도우 · 맥.

    focus_guard.install()        앱이 Tk 를 만든 뒤 한 번 (윈도우 · 맥, 나머지는 아무것도 안 한다)
    focus_guard.quiet(win, fn)   fn() 을 부르되, 그 사이 우리가 남의 포커스를 가져가면 돌려준다

## 왜 가져가나

윈도우 Tk 는 **이미 떠 있는 창**의 순서를 바꿀 때 SetWindowPos 에 '활성화하지 마라'(SWP_NOACTIVATE)를 안 준다 -
`wm attributes -topmost` · `raise`(lift) · `wm deiconify`(다시 올리기) 가 다 그렇다. 그래서 풀숲에 야생이 돋거나
(raise_above 는 창을 먼저 띄운 뒤 '항상 위' 를 건다), 숨었던 도트가 다시 보이거나, 배틀 연출 층이 올라올 때 그 창이
활성화되면서 쓰던 프로그램의 포커스가 풀렸다. 윈도우가 다른 프로그램의 '앞으로 나오기' 를 막을 때도 있고 허용할
때도 있어서 '간헐적으로' 보였다.

맥은 Tk 이 새 창을 올릴 때 부르는 `activateIgnoringOtherApps:` 를 platform_mac.keep_focus 가 진작 막아 두었다. 같은
동작에 같은 문지기를 하나 더 세워, 다른 길로 우리 앱이 맨 앞이 되어도 돌려준다 (사용자 결정: 맥도 같이).

## 어떻게 막나

창 종류마다 고치는 대신 (긴급 숨기기 stealth 처럼) tkinter 의 그 세 동작에 문지기를 세운다. **테두리 없는 창
(overrideredirect = 바탕화면에 떠 있는 것들)에만** 걸고, 부르기 전 맨 앞이 **남의 것**이었는데 부른 뒤 **우리 것**이
됐으면 바로 남의 것으로 되돌린다 (그 순간 우리가 맨 앞이라 되돌릴 수 있다). 허브 · 대화상자처럼 테두리가 있는 창
(트레이에서 사용자가 연 것)은 손대지 않는다 - 그건 앞으로 나와야 한다. 사용자가 도트를 눌러 이미 우리가 맨
앞일 때도 손대지 않는다. '맨 앞' 은 윈도우는 맨 앞 창(hwnd), 맥은 맨 앞 앱(pid) 이다 (_Win · _Mac).
"""
import os
import sys
import tkinter as tk

_ORIG = {}
_BACKEND = [None]                # 맨 앞을 묻고 돌려주는 쪽 (검사가 가짜를 끼운다)
_PRESS = [0]                     # 우리 창을 누른 횟수 - 부른 뒤 늘었으면 그 뒤의 '맨 앞' 은 사용자가 고른 것
#                                  (시각으로 재면 윈도우 시계가 15.6ms 단위라 같은 때로 찍혀 못 가렸다 - CI 에서 걸림)
DEFER_MS = 150                   # 맥: 앱 활성화는 이벤트를 돌 때 일어난다 - 이만큼 뒤에 한 번 더 본다


class _Win(object):
    """윈도우: 맨 앞 창(hwnd). 그 창을 만든 프로세스가 우리면 우리 것."""

    def __init__(self):
        import ctypes
        self.ct = ctypes
        self.u = ctypes.windll.user32

    def front(self):
        return self.u.GetForegroundWindow() or None

    def ours(self, h):
        pid = self.ct.c_ulong(0)
        self.u.GetWindowThreadProcessId(h, self.ct.byref(pid))
        return pid.value == os.getpid()

    def give_back(self, h):
        self.u.SetForegroundWindow(h)


class _Mac(object):
    """맥: 맨 앞 앱(pid). **활성화가 부른 자리에서 바로 일어나지 않는다** - Tk 이 이벤트를 돌 때 일어나서, 부른 직후에
    보면 아직 남의 앱이 맨 앞이다 (맥에서 재 봄: keep_focus 를 끄면 창을 띄운 뒤 이벤트를 돌고 나서야 우리가 맨
    앞이 됐다). 그래서 DEFER_MS 뒤에 한 번 더 본다 (deferred)."""

    deferred = True

    def __init__(self):
        import AppKit
        self.ak = AppKit

    def front(self):
        a = self.ak.NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(a.processIdentifier()) if a is not None else None

    def ours(self, pid):
        return pid == os.getpid()

    def give_back(self, pid):
        a = self.ak.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if a is not None:
            a.activateWithOptions_(0)


def _backend():
    if _BACKEND[0] is None:
        _BACKEND[0] = _Win() if sys.platform == "win32" else _Mac()
    return _BACKEND[0]


def _borderless(win):
    try:
        return isinstance(win, tk.Wm) and bool(_ORIG.get("override", tk.Wm.wm_overrideredirect)(win))
    except Exception:                                       # noqa: BLE001
        return False


def quiet(win, fn):
    """fn() 을 부른다. 그 사이 테두리 없는 우리 창이 남의 창(앱)에서 포커스를 가져갔으면 돌려준다."""
    if not _ORIG or not _borderless(win):
        return fn()
    try:
        b = _backend()
        before = b.front()
    except Exception:                                       # noqa: BLE001
        return fn()
    seq = _PRESS[0]
    try:
        return fn()
    finally:
        _check(b, before, seq)
        if getattr(b, "deferred", False):
            try:
                win.after(DEFER_MS, lambda: _check(b, before, seq))
            except Exception:                               # noqa: BLE001
                pass


def _check(b, before, seq):
    """부르기 전 맨 앞이 남의 것이었는데 지금 우리 것이면 돌려준다. 그 사이 사용자가 우리 창을 눌렀으면 그대로 둔다."""
    try:
        if _PRESS[0] != seq:
            return
        now = b.front()
        if before and now and now != before and not b.ours(before) and b.ours(now):
            b.give_back(before)
    except Exception:                                       # noqa: BLE001
        pass


def _pressed(_e=None):
    _PRESS[0] += 1


def _topmost_set(args, kw):
    if "topmost" in kw:
        return True
    return any(str(a) == "-topmost" for a in args[0::2]) and len(args) >= 2


def install(force=False):
    """tkinter 의 deiconify · lift(raise) · attributes(-topmost) 에 문지기를 세운다. 윈도우 · 맥 (force 는 검사용)."""
    if _ORIG:
        return False
    if not force:
        if sys.platform not in ("win32", "darwin"):
            return False
        try:
            _backend()                                   # 맥에 pyobjc 가 없으면 세우지 않는다
        except Exception:                                   # noqa: BLE001
            return False
    _ORIG["override"] = tk.Wm.wm_overrideredirect
    _ORIG["deiconify"] = tk.Wm.wm_deiconify
    _ORIG["tkraise"] = tk.Misc.tkraise
    _ORIG["attributes"] = tk.Wm.wm_attributes

    def deiconify(self):
        return quiet(self, lambda: _ORIG["deiconify"](self))

    def tkraise(self, aboveThis=None):
        return quiet(self, lambda: _ORIG["tkraise"](self, aboveThis))

    def attributes(self, *args, **kw):
        if _topmost_set(args, kw):
            return quiet(self, lambda: _ORIG["attributes"](self, *args, **kw))
        return _ORIG["attributes"](self, *args, **kw)

    tk.Wm.wm_deiconify = tk.Wm.deiconify = deiconify
    tk.Misc.tkraise = tk.Misc.lift = tkraise
    tk.Wm.wm_attributes = tk.Wm.attributes = attributes
    root = getattr(tk, "_default_root", None)
    if root is not None:
        try:
            root.bind_all("<ButtonPress>", _pressed, add="+")     # 우리 창을 누르면 그 뒤의 '맨 앞' 은 사용자 것
        except tk.TclError:
            pass
    return True


def uninstall():
    if not _ORIG:
        return
    tk.Wm.wm_deiconify = tk.Wm.deiconify = _ORIG["deiconify"]
    tk.Misc.tkraise = tk.Misc.lift = _ORIG["tkraise"]
    tk.Wm.wm_attributes = tk.Wm.attributes = _ORIG["attributes"]
    _ORIG.clear()
