# -*- coding: utf-8 -*-
"""이펙트를 그릴 투명 레이어.

바탕화면 위에 아무것도 안 보이는 창을 하나 깔고, 그 위에 기술 이펙트를 그린다.
포켓몬 도트는 각자 자기 창에 있으므로 이펙트만 이 레이어에 올라간다.

이 창은 **클릭이 그대로 통과한다.** 그냥 투명색만 지정하면 그려진 부분은
클릭을 먹어버려서, 이펙트가 야생 포켓몬 위를 지나갈 때 오른쪽 클릭이 씹힌다.
그래서 WS_EX_TRANSPARENT 를 걸어 창 전체를 통과시킨다.
"""
import tkinter as tk

KEY = "#fe01fe"


def make_click_through(win):
    """창 전체를 클릭이 통과하도록 만든다 (윈도우 전용)."""
    try:
        import ctypes
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
    except Exception:
        return False


class FxLayer(object):
    """이펙트를 그리는 캔버스. 좌표는 화면 좌표로 주고받는다."""

    def __init__(self, root, area):
        self.root = root
        x1, y1, x2, y2 = area
        # 이펙트가 활동 영역 밖으로 조금 튀어도 잘리지 않게 넉넉히
        pad = 90
        self.x = max(0, x1 - pad)
        self.y = max(0, y1 - pad)
        w = (x2 - x1) + pad * 2
        h = (y2 - y1) + pad * 2

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.configure(bg=KEY)
        self.win.geometry("%dx%d+%d+%d" % (w, h, self.x, self.y))
        self.cv = tk.Canvas(self.win, width=w, height=h, bg=KEY,
                            highlightthickness=0, bd=0)
        self.cv.pack()
        self.click_through = make_click_through(self.win)

    def to_local(self, sx, sy):
        """화면 좌표 -> 이 캔버스 좌표."""
        return sx - self.x, sy - self.y

    def raise_above(self):
        try:
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def clear(self):
        try:
            self.cv.delete("all")
        except Exception:
            pass

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class FloatText(object):
    """도트 위에 잠깐 떠올랐다 사라지는 짧은 글씨."""

    def __init__(self, layer, sx, sy, text, color="#ffffff", ms=900):
        self.layer = layer
        x, y = layer.to_local(sx, sy)
        self.items = [
            layer.cv.create_text(x + 1, y + 1, text=text, fill="#101014",
                                 font=("맑은 고딕", 10, "bold")),
            layer.cv.create_text(x, y, text=text, fill=color,
                                 font=("맑은 고딕", 10, "bold")),
        ]
        self.step = 0
        self.jobs = []
        self.ms = ms
        self._rise()

    def _rise(self):
        if self.step > 14:
            return self.done()
        for it in self.items:
            try:
                self.layer.cv.move(it, 0, -2)
            except Exception:
                return
        self.step += 1
        self.jobs.append(self.layer.root.after(int(self.ms / 16.0), self._rise))

    def done(self):
        for it in self.items:
            try:
                self.layer.cv.delete(it)
            except Exception:
                pass
        self.items = []

    def stop(self):
        for j in self.jobs:
            try:
                self.layer.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        self.done()
