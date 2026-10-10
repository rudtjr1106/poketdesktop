# -*- coding: utf-8 -*-
"""배틀에 들어갈 때의 연출 (1.10.3) — 배틀 창이 불쑥 뜨지 않고, 검은 띠가 걷히며 드러난다.

실시간 배틀이 열리면 배틀 창이 **아무 예고 없이** 떴다. 원작에서 배틀에 들어갈 때 화면이 한 번
닫혔다 열리는 것처럼, 여기서도 한 박자를 둔다:

    배틀 창   비치는 데서 또렷해지며 뜨고 -> (새 판이면) 닫힌 띠 위에 '나 VS 상대' 가 한 박자 뜨고
              -> 검은 띠가 걷히며 장면이 드러난다

**천천히 한다** (1.10.4). 처음에는 0.5초 만에 지나가서 "너무 빨라서 크게 못 다가온다" 는 말을 들었다.
새 판은 이름을 보여 주는 한 박자(HOLD_S)를 두고, 띠도 두 배쯤 느리게 걷는다.

띠는 화면을 가로 줄 여러 개로 나눠, 줄마다 번갈아 왼쪽·오른쪽에서 자란다 (위 줄부터 조금씩 먼저).
캔버스에는 반투명이 없어서 '어두워지는' 연출은 못 한다 - 그래서 덮는 넓이로 닫는다.

번쩍이는 연출(화면 전체를 희게 깜빡이기)은 넣지 않았다. 일하다 옆에 띄워 두는 프로그램이다.
"""
import tkinter as tk

ROWS = 9                      # 띠의 수
LAG = 0.35                    # 맨 아래 줄이 맨 위 줄보다 늦게 출발하는 정도 (전체 길이에 대한 비)
OPEN_S = 0.85                 # 걷히는 시간 (0.42 는 눈에 안 들어왔다)
FADE_S = 0.30                 # 배틀 창이 또렷해지는 시간
HOLD_S = 1.10                 # 새 판: 닫힌 띠 위에 '나 VS 상대' 를 띄워 두는 시간
SLIDE_S = 0.32                # 이름이 양쪽에서 미끄러져 들어오는 시간
BLACK = "#0b0e16"
VS_COLOR = "#ffd447"          # 'VS'
ME_COLOR = "#8fc2ff"          # 내 이름
FOE_COLOR = "#ff9a8f"         # 상대 이름
RULE_COLOR = "#3a4466"        # 이름 아래의 금


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


def versus_spots(w, h, t, k=1.0):
    """'나 VS 상대' 가 놓일 자리 {"me": (x, y), "vs": (x, y), "foe": (x, y), "rule": 금의 반 길이}.

    t = 띠가 닫힌 뒤 흐른 시간(초): 이름이 양쪽 밖에서 미끄러져 들어와 제자리에 선다.
    k = 띠가 닫힌 정도 (1 = 다 닫힘): 걷히기 시작하면(k < 1) 이름은 다시 양쪽으로 물러난다.
    """
    cx, cy = w / 2.0, h / 2.0
    side = w * 0.27                              # 가운데에서 이름까지
    off = w * 0.6                                # 화면 밖에서 들어오는 거리
    come = ease(t / SLIDE_S)                     # 0 -> 1: 들어온다
    away = ease((1.0 - max(0.0, min(1.0, k))) / 0.5)   # 0 -> 1: 띠가 절반 걷힐 때까지 물러난다
    d = off * (1.0 - come) + off * away
    return {"me": (cx - side - d, cy), "foe": (cx + side + d, cy), "vs": (cx, cy - h * 1.2 * away),
            "rule": w * 0.34 * come * (1.0 - away), "show_vs": t >= SLIDE_S * 0.6}


class Versus(object):
    """닫힌 띠 위의 '나  VS  상대'. draw(장면 크기, 닫힌 뒤 흐른 시간, 닫힌 정도) 로 움직인다."""

    def __init__(self, cv, me, foe, family, name_pt, vs_pt, tags=()):
        self.cv = cv
        try:
            self.rule = cv.create_line(0, 0, 0, 0, fill=RULE_COLOR, width=2, state="hidden", tags=tags)
            self.me = cv.create_text(0, 0, text=me, fill=ME_COLOR, font=(family, name_pt, "bold"),
                                     anchor="center", state="hidden", tags=tags)
            self.foe = cv.create_text(0, 0, text=foe, fill=FOE_COLOR, font=(family, name_pt, "bold"),
                                      anchor="center", state="hidden", tags=tags)
            self.vs = cv.create_text(0, 0, text="VS", fill=VS_COLOR, font=(family, vs_pt, "bold"),
                                     anchor="center", state="hidden", tags=tags)
            self.items = [self.rule, self.me, self.foe, self.vs]
        except tk.TclError:
            self.items = []

    def draw(self, w, h, t, k=1.0):
        if not self.items:
            return
        sp = versus_spots(w, h, t, k)
        cy = h / 2.0
        try:
            self.cv.coords(self.me, *sp["me"])
            self.cv.coords(self.foe, *sp["foe"])
            self.cv.coords(self.vs, *sp["vs"])
            self.cv.coords(self.rule, w / 2.0 - sp["rule"], cy + h * 0.12, w / 2.0 + sp["rule"], cy + h * 0.12)
            for item in (self.me, self.foe, self.rule):
                self.cv.itemconfigure(item, state="normal" if t >= 0 else "hidden")
            self.cv.itemconfigure(self.vs, state="normal" if sp["show_vs"] else "hidden")
            for item in self.items:              # 띠는 그릴 때마다 맨 위로 올라온다 - 그 위에 다시 올린다
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
