# -*- coding: utf-8 -*-
"""긴급 숨기기 (1.10.3) — 화면에 떠 있는 포스크탑을 전부 치웠다가 그대로 되돌린다.

    s = Stealth(app)
    s.toggle()        숨겨져 있으면 되돌리고, 아니면 숨긴다

게시판 건의(#148): 회사에서 급히 가려야 할 때 누르는 단축키. 바탕화면의 포켓몬, 포스크탑 창,
배틀 창 - 무엇이 떠 있든 한 번에. 단축키는 hotkey.py 가 받고, 트레이 메뉴에도 같은 것이 있다.

## 어떻게 숨기나

창의 종류를 가리지 않는다. **떠 있는 Toplevel 을 전부 거두고(withdraw), 무엇을 거뒀는지 적어 둔다.**
포켓몬·알·이름표·풀숲·배틀의 포켓몬과 체력바·허브 창·대화상자·알림이 다 Toplevel 이라 하나도
안 빠진다 (종류마다 따로 숨기면 창이 하나 새로 생길 때마다 여기에 줄을 보태야 한다).

## 숨긴 동안에도 게임은 돈다

포켓몬은 걸어다니고 배틀은 진행된다 - 창만 안 보인다. 그러다 보면 앱이 스스로 창을 띄우려 한다
(배틀이 끝나 포켓몬이 돌아온다, 새 알림이 뜬다, 30초마다 이름표를 다시 맞춘다). 그게 화면에
번쩍하면 숨긴 보람이 없다. 그래서 숨긴 동안에는 **창을 띄우는 길 셋을 막아 둔다** (install):

    Toplevel 을 새로 만든다      -> 만들자마자 거둔다 (화면에 한 번도 안 나온다)
    deiconify / show_again       -> 띄우지 않는다
    withdraw                     -> 그대로 하고, '되돌릴 것' 에서 뺀다

그리고 그때마다 '되돌릴 것' 목록을 고친다. 그래서 되돌릴 때 나오는 것은 **숨기기 전에 떠 있던
것이 아니라, 숨기지 않았다면 지금 떠 있었을 것**이다 - 그사이 끝난 배틀의 창은 안 나오고,
그사이 돌아온 포켓몬은 나온다.

## 조심한 것

- 맥에서 테두리 없는 창을 그냥 deiconify 하면 '항상 위' 와 클릭 통과가 풀린다 (platform_mac).
  그런 창(overrideredirect)은 PLAT.show_again 으로 되돌린다.
- grab_set 은 안 보이는 창에 걸면 오류가 난다. 숨긴 동안 뜨려던 되묻는 창이 그 오류로 죽지
  않게, 숨긴 동안에는 그 오류를 넘긴다.
"""
import tkinter as tk

from . import platform_os as PLAT

_ACTIVE = [None]              # 지금 숨기고 있는 Stealth. 없으면 None
_ORIG = {}                    # 손대기 전의 tkinter 함수들
_BUSY = [False]               # 우리 스스로 거두거나 되돌리는 중 (그때는 목록을 고치지 않는다)


def active():
    s = _ACTIVE[0]
    return s if (s is not None and s.on) else None


def install():
    """tkinter 의 '창을 띄우고 거두는' 함수에 문지기를 세운다. 한 번만 하면 된다.

    숨기고 있지 않을 때는 원래 함수를 그대로 부른다 - 평소 동작은 바뀌지 않는다.
    """
    if _ORIG:
        return
    _ORIG["deiconify"] = tk.Wm.wm_deiconify
    _ORIG["withdraw"] = tk.Wm.wm_withdraw
    _ORIG["init"] = tk.Toplevel.__init__
    _ORIG["grab"] = tk.Misc.grab_set

    def deiconify(self):
        s = active()
        if s is None or _BUSY[0]:
            return _ORIG["deiconify"](self)
        s.want(self, True)                       # 숨긴 동안에는 띄우지 않고 적어만 둔다
        return None

    def withdraw(self):
        s = active()
        if s is not None and not _BUSY[0]:
            s.want(self, False)                  # 앱이 스스로 거뒀다 - 되돌릴 것이 아니다
        return _ORIG["withdraw"](self)

    def init(self, *a, **kw):
        _ORIG["init"](self, *a, **kw)
        s = active()
        if s is not None:
            try:
                _ORIG["withdraw"](self)          # 만들자마자 거둔다 (아직 화면에 안 나왔다)
            except tk.TclError:
                pass
            s.want(self, True)

    def grab_set(self):
        try:
            return _ORIG["grab"](self)
        except tk.TclError:
            if active() is None:
                raise
            return None                          # 숨긴 창에는 걸 수 없다 - 넘어간다

    tk.Wm.wm_deiconify = tk.Wm.deiconify = deiconify
    tk.Wm.wm_withdraw = tk.Wm.withdraw = withdraw
    tk.Toplevel.__init__ = init
    tk.Misc.grab_set = grab_set


def uninstall():
    """문지기를 걷는다 (검사용)."""
    if not _ORIG:
        return
    tk.Wm.wm_deiconify = tk.Wm.deiconify = _ORIG["deiconify"]
    tk.Wm.wm_withdraw = tk.Wm.withdraw = _ORIG["withdraw"]
    tk.Toplevel.__init__ = _ORIG["init"]
    tk.Misc.grab_set = _ORIG["grab"]
    _ORIG.clear()
    _ACTIVE[0] = None


def toplevels(root):
    """그 아래의 Toplevel 전부 (창 안에서 띄운 창까지)."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel):
                out.append(c)
            walk(c)
    walk(root)
    return out


class Stealth(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.on = False
        self.saved = []           # 되돌릴 창 (숨기지 않았다면 지금 떠 있었을 것들)
        self.states = {}          # 그 가운데 작게 접혀 있던 창 ({창: "iconic"}). 되돌릴 때 다시 접는다
        install()

    def want(self, win, shown):
        """숨긴 동안 앱이 그 창을 띄우려 했다(shown) / 거뒀다. 되돌릴 것 목록을 고친다."""
        if shown:
            if win not in self.saved:
                self.saved.append(win)
        elif win in self.saved:
            self.saved.remove(win)

    def toggle(self):
        if self.on:
            self.show()
        else:
            self.hide()
        return self.on

    def hide(self):
        """떠 있는 것을 전부 거둔다. 거둔 창 수를 돌려준다."""
        if self.on:
            return 0
        self.saved, self.states = [], {}
        _BUSY[0] = True
        try:
            for w in toplevels(self.root):
                try:
                    if not w.winfo_exists():
                        continue
                    st = str(w.state())
                    # 작게 접어 둔 창(iconic)도 거둔다 - 작업 표시줄에 단추가 남으면 숨긴 것이 아니다
                    if st in ("normal", "zoomed", "iconic"):
                        _ORIG["withdraw"](w)
                        self.saved.append(w)
                        if st != "normal":
                            self.states[w] = st
                except tk.TclError:
                    pass
        finally:
            _BUSY[0] = False
        self.on = True
        _ACTIVE[0] = self
        return len(self.saved)

    def show(self):
        """거둔 것을 되돌린다. 되돌린 창 수를 돌려준다."""
        if not self.on:
            return 0
        self.on = False
        _ACTIVE[0] = None
        wins, self.saved, n = self.saved, [], 0
        states, self.states = self.states, {}
        for w in wins:
            try:
                if not w.winfo_exists():
                    continue                     # 그사이 없어졌다 (끝난 배틀의 창, 지나간 알림)
                if w.overrideredirect():
                    PLAT.show_again(w)           # 테두리 없는 창: '항상 위' 와 클릭 통과를 다시 건다
                elif states.get(w) == "iconic":
                    w.iconify()                  # 접혀 있던 창은 접힌 채로
                else:
                    _ORIG["deiconify"](w)
                    if states.get(w) == "zoomed":
                        w.state("zoomed")
                n += 1
            except tk.TclError:
                pass
        ov = getattr(self.app, "overlay", None)
        if ov is not None:
            try:
                ov.apply_names()                 # 이름표는 설정대로 다시 맞춘다
            except Exception:                    # noqa: BLE001
                pass
        return n
