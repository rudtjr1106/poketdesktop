# -*- coding: utf-8 -*-
"""기다리는 동안 보여주는 표시.

서버가 무료 등급이라 자고 있으면 깨는 데 30~60초가 걸린다. 그동안
창은 비어 있고 아무 말도 없어서, 사용자는 고장 났다고 생각하고 다시
누르거나 닫아 버린다.

**무엇을 기다리는지, 얼마나 걸렸는지**를 보여준다. 오래 걸리면 왜
오래 걸리는지도 말해 준다 - 이유를 알면 기다릴 수 있다.

창을 따로 띄우지 않는다. 열려 있는 창 위에 덮어서, 다 받으면 걷힌다.
"""
import time
import tkinter as tk

from . import ui_common as U

# 이만큼 지나면 "자고 있어서 그렇다" 고 알려준다.
SLOW_AFTER = 4.0


class Overlay(object):
    """창 위에 덮는 기다림 표시."""

    def __init__(self, parent, text="불러오는 중"):
        self.parent = parent
        self.text = text
        self.t0 = time.time()
        self.job = None
        self.spin = 0
        self.done = False

        self.box = tk.Frame(parent, bg=U.BG)
        self.box.place(relx=0, rely=0, relwidth=1, relheight=1)
        mid = tk.Frame(self.box, bg=U.BG)
        mid.place(relx=0.5, rely=0.42, anchor="center")

        self.cv = tk.Canvas(mid, width=54, height=54, bg=U.BG,
                            highlightthickness=0, bd=0)
        self.cv.pack()
        self.label = tk.Label(mid, text=text, bg=U.BG, fg=U.FG,
                              font=U.FONT_B)
        self.label.pack(pady=(10, 0))
        self.note = tk.Label(mid, text="", bg=U.BG, fg=U.FG_FAINT,
                             font=U.FONT_XS, justify="center")
        self.note.pack(pady=(4, 0))
        self._tick()

    def _tick(self):
        if self.done:
            return
        # 몬스터볼이 구른다. 도는 것이 있어야 멈춘 게 아니라는 걸 안다.
        self.spin = (self.spin + 11) % 360
        c = self.cv
        c.delete("all")
        r = 20
        x = y = 27
        c.create_oval(x - r, y - r, x + r, y + r, fill="#f4f6fb",
                      outline=U.INK, width=3)
        c.create_arc(x - r, y - r, x + r, y + r, start=self.spin, extent=180,
                     fill=U.RED, outline=U.INK, width=3)
        c.create_oval(x - 7, y - 7, x + 7, y + 7, fill="#f4f6fb",
                      outline=U.INK, width=3)

        waited = time.time() - self.t0
        if waited >= SLOW_AFTER:
            self.note.configure(
                text="서버가 자고 있어서 깨우는 중입니다.\n"
                     "처음 한 번은 1분쯤 걸릴 수 있습니다.  (%d초)"
                     % int(waited))
        try:
            self.job = self.parent.after(45, self._tick)
        except Exception:                                   # noqa: BLE001
            self.done = True

    def say(self, text):
        try:
            self.label.configure(text=text)
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        if self.done:
            return
        self.done = True
        if self.job:
            try:
                self.parent.after_cancel(self.job)
            except Exception:                               # noqa: BLE001
                pass
            self.job = None
        try:
            self.box.destroy()
        except Exception:                                   # noqa: BLE001
            pass


def wrap(parent, text="불러오는 중"):
    """with 로 쓸 수 있게. 다 쓰면 알아서 걷힌다."""
    return Overlay(parent, text)
