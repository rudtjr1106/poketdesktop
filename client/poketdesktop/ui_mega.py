# -*- coding: utf-8 -*-
"""배틀 창의 '메가진화' 단추 (시즌 3).

관장·실시간·레이드 창이 같이 쓴다.

## 어디에 붙나

**메시지 막대 오른쪽 끝.** 명령 칸 오른쪽 기둥에 넣으면 그 아래 기술 설명
칸이 50px 줄어 설명이 잘린다(관장 창은 설명 칸이 60px 남짓이다). 메시지
막대는 명령을 고르는 동안 '무엇을 할까?' 한 줄뿐이라 자리가 남는다.

## 켜고 끄기

  · 누르면 켜지고, 다음 **기술**과 함께 보낸다. 교체·기권에는 안 실린다.
  · 한 번 보내면 꺼진다. 한 판에 한 번은 서버가 막는다 - 쓰고 나면
    canMega 가 False 로 와서 단추가 아예 안 뜬다.
  · 명령을 고르는 때가 아니면(재생 중·교체 고르는 중) 숨긴다.
"""
import math
import random
import tkinter as tk

from . import ui_common as U

ON_FILL = "#8a5cf6"
ON_HOVER = "#9f7af8"
ON_SHADOW = "#35206b"
TEXT = "메가진화"


class MegaToggle(object):
    def __init__(self, bar, before=None, height=34):
        self.bar = bar
        self.before = before
        self.on = False
        self.shown = False
        self.btn = U.ghost_button(bar, TEXT, self.toggle, height=height)
        b = self.btn
        self._off = (b.fill, b._fg, b.hover, b._shadow)

    def toggle(self):
        self.set(not self.on)

    def set(self, on):
        self.on = bool(on)
        b = self.btn
        if self.on:
            b.fill, b._fg, b.hover, b._shadow = ON_FILL, "#ffffff", ON_HOVER, ON_SHADOW
        else:
            b.fill, b._fg, b.hover, b._shadow = self._off
        b.configure(state="normal")          # 바탕·그림자·글자를 새 색으로 다시 칠한다

    def show(self, can):
        """명령을 고를 때 canMega 면 보인다. 숨기면 꺼진다."""
        can = bool(can)
        if can and not self.shown:
            kw = {"side": "right", "padx": (8, 12)}
            if self.before is not None:
                kw["before"] = self.before
            self.btn.holder.pack(**kw)
        elif not can and self.shown:
            self.btn.holder.pack_forget()
        self.shown = can
        if not can and self.on:
            self.set(False)

    def take(self):
        """이번 기술과 함께 보낼 값. 한 번 꺼내면 꺼진다."""
        v = bool(self.on and self.shown)
        if self.on:
            self.set(False)
        return v


# ---------------------------------------------------------------- 배틀 창의 메가진화 연출
# 본가의 메가진화: 무지갯빛 기운이 몸으로 모여들고, 빛의 알에 싸였다가, 빛이
# 터지며 새 모습이 드러난다. 배틀 창은 캔버스 하나라 그 위에 바로 그린다.
#
#   1. 모인다    여러 색 알갱이가 둘레에서 돌며 몸 쪽으로 빨려 든다
#   2. 감싼다    흰 빛이 몸을 덮으며 커진다 - 가장 클 때 도트를 갈아 끼운다(on_swap)
#   3. 터진다    무지갯빛 고리가 겹겹이 퍼지고 알갱이가 튄다
#
# 시간은 창의 later 로 흘린다 (창이 닫히면 같이 멈추고, 검사는 빨리 돌릴 수 있다).
RAINBOW = ("#ff6b9d", "#ffb347", "#ffe66d", "#7bffa0", "#6fd3ff", "#b69cff")
GATHER_STEPS = 16
GATHER_MS = 42
COVER_STEPS = 6
BURST_STEPS = 9
BURST_MS = 40
SAFETY_MS = 2800          # 연출이 어디서 멈춰도 판은 흘러가야 한다
AFTER_MS = 520            # 새 모습을 잠깐 보여 주고 다음 사건으로


class MegaFx(object):
    """캔버스 위의 메가진화 연출 한 번.

        fx = MegaFx(cv, (x, y), later, on_swap=..., on_done=...)
        fx.play()

    on_swap 은 빛이 몸을 다 덮은 순간 한 번 부른다 - 여기서 도트를 바꾸면 바뀌는
    순간이 빛에 가려진다. on_done 은 끝나면 한 번. 창을 닫을 때는 stop().
    """

    def __init__(self, cv, center, later, on_swap=None, on_done=None, size=None):
        self.cv = cv
        self.cx, self.cy = center
        self.later = later
        self.on_swap = on_swap
        self.on_done = on_done
        self.size = float(size or U.h(64))        # 도트 반지름쯤
        self.items = []
        self.dead = False
        self._swapped = False

    # ---- 도구 ----
    def _add(self, item):
        self.items.append(item)
        return item

    def _kill(self, item):
        try:
            self.cv.delete(item)
        except tk.TclError:
            pass
        if item in self.items:
            self.items.remove(item)

    def _ok(self):
        if self.dead:
            return False
        try:
            return bool(self.cv.winfo_exists())
        except tk.TclError:
            return False

    def play(self):
        try:
            self._gather(0, self._orbs())
        except tk.TclError:
            self._finish()
        return self

    # ---- 1. 모인다 ----
    def _orbs(self):
        orbs = []
        n = 12
        for k in range(n):
            a = 2 * math.pi * k / n
            r = U.h(4) + (k % 3)
            it = self._add(self.cv.create_oval(0, 0, 0, 0, fill=RAINBOW[k % len(RAINBOW)],
                                               outline=""))
            orbs.append((it, a, r))
        return orbs

    def _gather(self, i, orbs):
        if not self._ok():
            return self._finish()
        if i >= GATHER_STEPS:
            for it, _a, _r in orbs:
                self._kill(it)
            return self._cover(0)
        t = i / float(GATHER_STEPS)
        dist = self.size * 1.9 * (1.0 - t) ** 1.4 + U.h(6)
        spin = t * math.pi * 2.2                   # 돌면서 들어온다
        try:
            for it, a, r in orbs:
                x = self.cx + math.cos(a + spin) * dist
                y = self.cy + math.sin(a + spin) * dist * 0.8
                self.cv.coords(it, x - r, y - r, x + r, y + r)
                self.cv.tag_raise(it)
        except tk.TclError:
            return self._finish()
        self.later(GATHER_MS, lambda: self._gather(i + 1, orbs))

    # ---- 2. 감싼다 ----
    def _cover(self, i, core=None):
        if not self._ok():
            return self._finish()
        try:
            if core is None:
                core = self._add(self.cv.create_oval(0, 0, 0, 0, fill="#ffffff", outline=""))
            r = self.size * (0.25 + 0.17 * i)
            self.cv.coords(core, self.cx - r, self.cy - r * 1.05, self.cx + r, self.cy + r * 1.05)
            self.cv.tag_raise(core)
        except tk.TclError:
            return self._finish()
        if i >= COVER_STEPS:
            self._swap()
            return self.later(90, lambda: self._burst(0, core))
        self.later(38, lambda: self._cover(i + 1, core))

    def _swap(self):
        if self._swapped:
            return
        self._swapped = True
        if self.on_swap:
            try:
                self.on_swap()
            except Exception:                               # noqa: BLE001
                pass

    # ---- 3. 터진다 ----
    def _burst(self, i, core, bits=None):
        if not self._ok():
            return self._finish()
        try:
            if bits is None:
                bits = []
                for k in range(16):
                    a = random.uniform(0, 2 * math.pi)
                    sp = random.uniform(0.07, 0.15) * self.size
                    r = random.uniform(2, 4)
                    it = self._add(self.cv.create_oval(self.cx - r, self.cy - r, self.cx + r,
                                                       self.cy + r, fill=RAINBOW[k % len(RAINBOW)],
                                                       outline=""))
                    bits.append((it, math.cos(a) * sp, math.sin(a) * sp * 0.8))
            if i >= BURST_STEPS:
                return self._finish()
            # 빛의 알이 걷힌다
            r = self.size * max(0.0, 1.25 - 0.22 * i)
            if r > 3:
                self.cv.coords(core, self.cx - r, self.cy - r * 1.05, self.cx + r, self.cy + r * 1.05)
            else:
                self._kill(core)
            # 무지갯빛 고리
            rr = self.size * (0.5 + 0.28 * i)
            ring = self._add(self.cv.create_oval(self.cx - rr, self.cy - rr * 0.9, self.cx + rr,
                                                 self.cy + rr * 0.9,
                                                 outline=RAINBOW[i % len(RAINBOW)],
                                                 width=max(1, 6 - i // 2)))
            self.later(150, lambda it=ring: self._kill(it))
            for it, vx, vy in bits:
                self.cv.move(it, vx, vy + i * 0.3)
        except tk.TclError:
            return self._finish()
        self.later(BURST_MS, lambda: self._burst(i + 1, core, bits))

    # ---- 끝 ----
    def _finish(self):
        if self.dead:
            return
        self.dead = True
        self._swap()                               # 도중에 끊겨도 도트는 바뀌어 있어야 한다
        for it in list(self.items):
            try:
                self.cv.delete(it)
            except tk.TclError:
                pass
        self.items = []
        cb, self.on_done = self.on_done, None
        if cb:
            try:
                cb()
            except Exception:                               # noqa: BLE001
                pass

    def stop(self):
        """창을 닫을 때. 다음으로 넘기지 않고 조용히 치운다."""
        self.on_done = None
        self.on_swap = None
        self._swapped = True
        self._finish()


def play_in(win, center, on_swap, size=None):
    """배틀 창(win)에서 메가진화 연출을 한 번 돌리고, 끝나면 win._next 로 넘긴다.

    win 은 cv·later·effects·alive·_next 를 가진 창 (관장·실시간·레이드가 다 같다).
    _apply 에서 이걸 부르고 None 을 돌려주면 된다 - 기술 연출과 같은 약속이다.
    """
    state = {"done": False}

    def done():
        if state["done"] or not win.alive:
            return
        state["done"] = True
        win.later(AFTER_MS, win._next)

    try:
        fx = MegaFx(win.cv, center, win.later, on_swap=on_swap, on_done=done, size=size)
        # 안전 타이머가 먼저 넘겨도 연출은 아직 돌 수 있다. 창을 닫을 때 멈추게 들고 있는다.
        win.effects = [e for e in win.effects if not e.dead] + [fx]
        win.later(SAFETY_MS, done)
        fx.play()
    except Exception:                                       # noqa: BLE001
        try:
            on_swap()
        except Exception:                                   # noqa: BLE001
            pass
        done()


def warm(win, num, shiny):
    """메가 폼 도트를 미리 받아 둔다 - 빛이 걷힐 때 바로 보이게."""
    from . import sprite_cache
    try:
        U.run_async(win.root, lambda: sprite_cache.ensure(win.app.api, num, shiny),
                    lambda *_a: None)
    except Exception:                                       # noqa: BLE001
        pass
