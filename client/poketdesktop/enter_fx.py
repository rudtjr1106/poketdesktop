# -*- coding: utf-8 -*-
"""배틀에 들어갈 때의 연출 (1.10.3) — 배틀 창이 불쑥 뜨지 않고, 검은 띠가 걷히며 드러난다.

실시간 배틀이 열리면 배틀 창이 **아무 예고 없이** 떴다. 원작에서 배틀에 들어갈 때 화면이 한 번
닫혔다 열리는 것처럼, 여기서도 한 박자를 둔다:

    배틀 창   비치는 데서 또렷해지며 뜨고 -> 검은 띠가 걷히며 장면이 드러난다

띠는 화면을 가로 줄 여러 개로 나눠, 줄마다 번갈아 왼쪽·오른쪽에서 자란다 (위 줄부터 조금씩 먼저).
캔버스에는 반투명이 없어서 '어두워지는' 연출은 못 한다 - 그래서 덮는 넓이로 닫는다.

번쩍이는 연출(화면 전체를 희게 깜빡이기)은 넣지 않았다. 일하다 옆에 띄워 두는 프로그램이다.
"""
import tkinter as tk

ROWS = 9                      # 띠의 수
LAG = 0.35                    # 맨 아래 줄이 맨 위 줄보다 늦게 출발하는 정도 (전체 길이에 대한 비)
OPEN_S = 0.42                 # 걷히는 시간
FADE_S = 0.22                 # 배틀 창이 또렷해지는 시간
BLACK = "#0b0e16"


def ease(t):
    """천천히 출발해서 천천히 멈춘다 (0..1)."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def blinds(w, h, k, rows=ROWS):
    """화면(w x h)을 덮는 띠들 [(x0, y0, x1, y1)]. k = 0 이면 다 걷혔고 1 이면 다 닫혔다.

    띠의 수는 늘 rows 다 (폭이 0 인 띠도 준다 - 그리는 쪽이 항목을 그대로 쓴다).
    """
    k = max(0.0, min(1.0, k))
    out = []
    for i in range(rows):
        y0, y1 = h * i // rows, h * (i + 1) // rows
        lag = LAG * i / float(max(1, rows - 1))
        ww = int(round(w * ease(k * (1.0 + LAG) - lag)))
        out.append((0, y0, ww, y1) if i % 2 == 0 else (w - ww, y0, w, y1))
    return out


class Blinds(object):
    """캔버스 위의 검은 띠들. draw(화면의 왼쪽 위, 크기, k) 로 닫힌 정도를 바꾼다."""

    def __init__(self, cv, rows=ROWS, tags=()):
        self.cv = cv
        self.last = None
        try:
            self.items = [cv.create_rectangle(0, 0, 0, 0, fill=BLACK, outline="", state="hidden", tags=tags)
                          for _i in range(rows)]
        except tk.TclError:
            self.items = []

    def draw(self, ox, oy, w, h, k):
        """(ox, oy) 는 캔버스에서 덮을 곳의 왼쪽 위다."""
        sig = (ox, oy, w, h, round(max(0.0, min(1.0, k)), 4))
        if sig == self.last:
            return                               # 그대로다 - 건드리면 다시 그린다
        self.last = sig
        try:
            for item, (x0, y0, x1, y1) in zip(self.items, blinds(w, h, k, len(self.items))):
                if x1 <= x0:
                    self.cv.itemconfigure(item, state="hidden")
                else:
                    self.cv.coords(item, ox + x0, oy + y0, ox + x1, oy + y1)
                    self.cv.itemconfigure(item, state="normal")
                    self.cv.tag_raise(item)
        except tk.TclError:
            pass

    def close(self):
        for item in self.items:
            try:
                self.cv.delete(item)
            except tk.TclError:
                pass
        self.items = []
