# -*- coding: utf-8 -*-
"""꾸미기 효과 (버전 2) - 바탕화면 포켓몬이 걸어간 자리에 남는 발자국 · 별가루 · 꽃잎 · 하트, 발밑 빛 고리.

포켓몬마다 **투명 창 하나**(Trail)를 둔다. 입자마다 작은 창을 띄우는 것보다 가볍다. 창은 클릭이 그대로
통과하고(fx_layer 와 같은 까닭 - 통과를 못 걸면 아예 안 띄운다), **제 포켓몬 창 바로 아래**에 깔린다
(PLAT.order_below). 포켓몬을 올리지 않는다 - 그러면 열려 있는 메뉴 · 배틀 연출 층 위로 포켓몬이 튀어나온다.
'항상 위' 를 다시 거는 Overlay.keep_on_top 은 이 창을 건너뛰고 제 포켓몬 밑으로만 다시 넣는다 (_poket_under).

입자는 화면 좌표에 남는다 - 포켓몬이 걸어가면 뒤로 처진다. 창은 포켓몬이 가장자리에 닿을 때만 옮긴다
(매 틱 옮기면 윈도우에서 옛 그림이 한 칸 밀려 보인다). 창 크기는 포켓몬 크기를 따른다 (큰 포켓몬의 하트가 안 잘리게).

윈도우 창은 투명색으로 뚫는다. 그래서 반투명이 안 된다 - 사라질 때는 체크무늬로 칸을 하나씩 빼서 옅어진다(디더).
맥은 알파를 그대로 받지만 같은 그림을 쓴다 (두 OS 가 똑같이 보이게).
그림은 deco_art 의 촘촘한 칸 그림, 배수 k 는 장식과 같다 (max(1, round(배율 / 2))).

걷는지는 **실제로 움직였나**로 본다 (state 가 아니라) - 놀러 온 친구 포켓몬은 스스로 안 돌아다니게 battling 을
켜 둔 채 따로 걸린다(visit.py). 배틀 중이라고 숨기지 않는다 (발밑 빛이 그대로 있는 편이 자연스럽다).
"""
import math
import random
import tkinter as tk

from PIL import Image, ImageChops

from . import config
from . import deco_art as ART
from . import platform_os as PLAT

KEY = (254, 1, 254)
KEY_HEX = "#fe01fe"
MIN_W, MIN_H = 320, 200         # 창 크기의 바닥 (포켓몬이 크면 늘린다)
BELOW_FEET = 50                 # 창 안에서 발 아래로 남기는 칸 (발자국 · 발밑 빛)
EVERY = 2                       # 몇 틱마다 다시 그리나
REORDER_MS = 800                # 다시 띄운 뒤 이 동안은 그릴 때마다 제 포켓몬 밑으로 다시 넣는다
MAX_PARTS = 90
MOVED = 0.3                     # 한 틱에 이만큼(px) 넘게 움직였으면 걷는 것
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
TONES = {"fx_stars_gold": "gold", "fx_stars_silver": "silver", "fx_stars_bronze": "bronze"}
RGBA_OK = PLAT.NAME == "platform_mac"      # 맥 SpriteView 는 알파 그림을 그대로 받는다
_masks = {}
_scaled = {}


def _mask(level, w, h):
    """체크무늬 가림판 (w x h, 'L'). level 0~16 - 16 이면 다 보인다."""
    level = max(0, min(16, int(level)))
    m = _masks.get((level, w, h))
    if m is None:
        rows = [bytes(255 if BAYER[y][x % 4] < level else 0 for x in range(w)) for y in range(4)]
        m = Image.frombytes("L", (w, h), b"".join(rows[y % 4] for y in range(h)))
        _masks[(level, w, h)] = m
    return m


def scaled(im, k):
    """ART.scaled 를 기억해 둔다 (입자마다 매번 키우지 않게). 그림은 ART 가 붙들고 있어서 id 가 안 바뀐다."""
    got = _scaled.get((id(im), k))
    if got is None:
        got = _scaled[(id(im), k)] = (im, ART.scaled(im, k))
    return got[1]


def fade(f, keep):
    """나이 비율 f(0~1) -> 보이는 정도(0~16). keep 까지는 다 보이고 그 뒤로 옅어진다."""
    if f <= keep:
        return 16
    return max(0, int(round(16 * (1 - f) / (1 - keep))))


def glow_phase(tick):
    """발밑 빛 고리의 밝기 0~3 (테가 밝아졌다 어두워졌다)."""
    return int(round(1.5 + 1.5 * math.sin(tick / 5.0)))


class Particle(object):
    __slots__ = ("kind", "x", "y", "life", "age", "size", "tw", "vy", "ph", "rot", "tone")

    def __init__(self, kind, x, y, life, **kw):
        self.kind, self.x, self.y, self.life, self.age = kind, float(x), float(y), life, 0
        self.size, self.tw, self.vy, self.ph, self.rot, self.tone = 3, 0.0, 0.0, 0.0, 0, "gold"
        for k, v in kw.items():
            setattr(self, k, v)


def draws(p, k):
    """입자 하나 -> (그림, 화면 x, 화면 y, 보이는 정도). 나이에서 바로 셈한다 (그리는 빈도와 무관하게)."""
    f = p.age / float(p.life)
    if p.kind == "paw":
        return ART.paw(), p.x, p.y, fade(f, 0.3)
    if p.kind == "star":
        s = p.size if math.sin(p.tw + p.age / 90.0) > -0.2 else max(1, p.size - 2)
        im = ART.star(s, p.tone)
        return im, p.x - im.width * k / 2.0, p.y + p.vy * p.age - im.height * k / 2.0, fade(f, 0.6)
    if p.kind == "petal":
        xx = p.x + math.sin(p.ph + p.age / 260.0) * 4 * k - p.age / 160.0
        return ART.petal(p.rot + p.age // 180), xx, p.y + p.vy * p.age, fade(f, 0.65)
    if p.kind == "heart":
        im = ART.heart_fx()
        xx = p.x + math.sin(p.ph + p.age / 200.0) * 3 * k
        return im, xx - im.width * k / 2.0, p.y - p.age / 28.0, fade(f, 0.55)
    return None


class Trail(object):
    """포켓몬 한 마리의 효과 창. Overlay._tick 이 틱마다 step 을 부른다."""

    def __init__(self, pet, keys):
        self.pet = pet
        self.ov = pet.ov
        self.keys = tuple(keys)
        self.parts = []
        self.tick = 0
        self.shown = False
        self.last = None             # 지난 발 자리 (걸은 거리 · 방향을 잰다)
        self.walked = 0.0
        self.back = 0                # 몸 뒤쪽 (-1 왼쪽 · 1 오른쪽 · 0 위아래로 걷는 중)
        self.since = {"star": 0, "petal": 0, "heart": 0}
        self.paw_side = 0
        self.k = max(1, int(round((getattr(pet, "base_scale", None) or 2.0) / 2.0)))
        self.ox = self.oy = None
        self._sig = None
        self._reorder = 0            # 다시 띄운 뒤 얼마 동안(ms) 제 포켓몬 밑으로 다시 넣나 - 맥 Tk 는 '항상 위' 를 한 박자 늦게
        #                              적용하면서 창을 다시 앞으로 올린다 (실제로 그랬다: 넣은 직후 update 한 번에 도로 위)
        self._frame = None
        self.view = None
        self.ok = False
        self.fit_size()
        w = tk.Toplevel(self.ov.root)
        w._poket_under = True        # Overlay.keep_on_top 이 이 창은 올리지 않는다 (제 포켓몬 밑으로만)
        self.win = w
        try:
            w.overrideredirect(True)
            bg = PLAT.transparent_window(w, KEY_HEX)
            w.geometry("%dx%d+%d+%d" % (self.W, self.H, int(pet.x), int(pet.y)))
            self.view = PLAT.SpriteView(w, bg, self.W, self.H)
            alpha = config.pet_alpha(getattr(self.ov, "settings", None))
            if alpha < 1.0:
                w.attributes("-alpha", alpha)
        except Exception as e:                              # noqa: BLE001
            config.log("꾸미기 효과 창을 못 만들었습니다: %s" % e)
            self.destroy()
            return
        PLAT.raise_above(w)
        if not PLAT.make_click_through(w):
            # 통과하지 않는 투명 창은 화면을 덮는 벽이다 - 효과 없이 간다 (fx_layer 와 같은 까닭)
            self.destroy()
            return
        w.withdraw()
        self.ok = True

    def fit_size(self):
        """창 크기: 포켓몬 키 위로 하트가 떠오를 자리 + 양옆으로 몸 뒤 별가루 자리."""
        p = self.pet
        self.W = max(MIN_W, int(p.fw * 3) + 60)
        self.H = max(MIN_H, int(p.fh) + 70 * self.k + BELOW_FEET + 20)
        self.cx, self.cy = self.W / 2.0, self.H - BELOW_FEET
        self.edge = max(70, int(p.fw))

    # ---------------- 보이나
    def _visible(self):
        p, ov = self.pet, self.ov
        if getattr(ov, "hidden", False) or getattr(p, "evolving", False):
            return False
        if getattr(p, "state", "") == "held" or getattr(p, "dragging", False):
            return False
        try:
            return p.win.state() != "withdrawn"
        except Exception:                                   # noqa: BLE001
            return False

    def _show(self, on):
        if on == self.shown:
            return
        try:
            if on:
                PLAT.show_again(self.win)
                self.shown = True
                self._reorder = REORDER_MS
                self.below_pet()
            else:
                self.win.withdraw()
        except Exception:                                   # noqa: BLE001
            pass
        self.shown = on

    def bottom_pet(self):
        """바탕화면 포켓몬 창 가운데 가장 먼저 만든(= 가장 아래) 보이는 창. Overlay.keep_on_top 이 만든 차례대로
        올리므로 먼저 만든 것이 맨 아래다. 효과 창을 그 밑에 깔면 이웃 포켓몬의 꽃잎이 내 포켓몬 몸 위에 안 찍힌다."""
        ov = self.ov
        wins = set()
        for p in list(getattr(ov, "pets", {}).values()) + list(getattr(ov, "extra", [])):
            w = getattr(p, "win", None)
            if w is not None:
                wins.add(str(w))
        try:
            for w in ov.root.winfo_children():
                if str(w) in wins and w.winfo_ismapped():
                    return w
        except Exception:                                   # noqa: BLE001
            pass
        return self.pet.win

    def below_pet(self):
        """효과 창을 포켓몬들 아래로 (가장 아래 포켓몬 창 바로 밑). 메뉴 · 배틀 연출 층 같은 다른 창은 안 건드린다."""
        if not self.ok or not self.shown:
            return False
        try:
            done = bool(PLAT.order_below(self.win, self.bottom_pet()))
            PLAT.keep_click_through(self.win)
        except Exception:                                   # noqa: BLE001
            done = False
        return done

    # ---------------- 틱
    def feet(self):
        p = self.pet
        a = p.anims.get(p.anim_name) if hasattr(p, "anims") else None
        foot = getattr(a, "foot", None) or p.fh            # 장식으로 늘린 칸이 아니라 몸 밑
        return p.x + getattr(p, "ax", p.fw / 2.0), p.y + foot - 2

    def step(self, ms):
        if not self.ok:
            return
        if not self._visible():
            self.parts = []
            self.last = None
            self._show(False)
            return
        fx, fy = self.feet()
        p = self.pet
        moved = 0.0
        if self.last is not None:
            dx = fx - self.last[0]
            moved = math.hypot(dx, fy - self.last[1])
            if moved > MOVED:
                self.back = -1 if dx > 0.2 else (1 if dx < -0.2 else 0)
        self.last = (fx, fy)
        if moved > MOVED and moved < 60 and getattr(p, "anim_name", "Walk") == "Walk" and not getattr(p, "once", None):
            self.walked += moved        # (60 넘게 한 번에 옮긴 것은 걷기가 아니라 자리 옮기기 - 들어 옮기기 · 화면 바뀜)
            self._spawn(ms, fx, fy)
        for q in self.parts:
            q.age += ms
        self.parts = [q for q in self.parts if q.age < q.life]
        aura = "fx_glow" in self.keys
        if not self.parts and not aura:
            self._show(False)
            return
        self.tick += 1
        if self.tick % EVERY and self.shown:
            return
        self._render(fx, fy, aura)
        self._show(True)
        if self._reorder > 0:
            self._reorder -= ms * EVERY
            self.below_pet()

    def _spawn(self, ms, fx, fy):
        p = self.pet
        k = self.k
        x0, y0, x1, y1 = p.x, p.y, p.x + p.fw, p.y + p.fh
        mid = p.x + getattr(p, "ax", p.fw / 2.0)
        back = self.back
        half = (x1 - x0) / 2.0

        def behind():
            d = random.uniform(0, half)
            return mid + (back * d if back else random.choice((-1, 1)) * d)

        for key in self.keys:
            if key == "fx_paw":
                if self.walked >= 13 * k:
                    self.walked = 0.0
                    self.paw_side ^= 1
                    side = 2 * k if self.paw_side else -2 * k
                    pw = ART.paw().width * k
                    self.parts.append(Particle("paw", fx - pw / 2.0 + (side if back == 0 else 0),
                                               fy - 4 * k + (side if back else 0), 2200))
            elif key in TONES:
                self.since["star"] += ms
                while self.since["star"] >= 70:
                    self.since["star"] -= 70
                    self.parts.append(Particle("star", behind(), random.uniform(y0 + (y1 - y0) * 0.1, y1 - 2),
                                               random.randint(700, 1500),
                                               size=random.choice((1, 3, 3, 5, 5, 5, 7, 7)),
                                               tw=random.uniform(0, 6.28), vy=random.uniform(0.004, 0.012),
                                               tone=TONES[key]))
            elif key == "fx_petals":
                self.since["petal"] += ms
                while self.since["petal"] >= 90:
                    self.since["petal"] -= 90
                    self.parts.append(Particle("petal", behind(), y0 + random.uniform(0, (y1 - y0) * 0.4),
                                               random.randint(1300, 1900), ph=random.uniform(0, 6.28),
                                               vy=random.uniform(0.009, 0.015), rot=random.randint(0, 3)))
            elif key == "fx_hearts":
                self.since["heart"] += ms
                while self.since["heart"] >= 300:
                    self.since["heart"] -= 300
                    self.parts.append(Particle("heart", mid + random.uniform(-6, 6) * k, y0 - 2 * k, 1200,
                                               ph=random.uniform(0, 6.28)))
        if len(self.parts) > MAX_PARTS:
            self.parts = self.parts[-MAX_PARTS:]

    # ---------------- 그리기
    def _place(self, fx, fy):
        """발이 창 가운데 둘레를 벗어났을 때만 창을 옮긴다. 옮겼으면 True."""
        if (self.ox is not None and abs(fx - (self.ox + self.cx)) < self.W / 2.0 - self.edge
                and abs(fy - (self.oy + self.cy)) < 20):
            return False
        self.ox, self.oy = int(fx - self.cx), int(fy - self.cy)
        return True

    def compose(self, fx, fy, aura):
        """지금 모습 한 장 (RGBA, 알파는 0 아니면 255)."""
        k, W, H = self.k, self.W, self.H
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        def put(sprite, sx, sy, level):
            if level <= 0:
                return
            sprite = scaled(sprite, k)
            x, y = int(round(sx - self.ox)), int(round(sy - self.oy))
            if x >= W or y >= H or x + sprite.width <= 0 or y + sprite.height <= 0:
                return
            a = sprite.split()[3]
            if level < 16:
                box = (max(0, x), max(0, y), min(W, x + sprite.width), min(H, y + sprite.height))
                m = Image.new("L", sprite.size, 0)
                m.paste(_mask(level, W, H).crop(box), (box[0] - x, box[1] - y))
                a = ImageChops.multiply(a, m)
            img.paste(sprite, (x, y), a)

        if aura:
            ring = ART.glow_ring(max(10, int(self.pet.fw * 0.8) // k), glow_phase(self.tick))
            put(ring, fx - ring.width * k / 2.0, fy - ring.height * k / 2.0 + k, 16)
        for q in self.parts:
            got = draws(q, k)
            if got:
                put(*got)
        return img

    def _render(self, fx, fy, aura):
        moved = self._place(fx, fy)
        sig = (self.ox, self.oy, int(fx), int(fy), glow_phase(self.tick) if aura else 0)
        if not self.parts and sig == self._sig:
            return                       # 발밑 빛만 있고 그대로다 - 다시 안 그린다
        self._sig = sig
        img = self.compose(fx, fy, aura)
        if not RGBA_OK:
            flat = Image.new("RGB", (self.W, self.H), KEY)
            flat.paste(img, (0, 0), img.split()[3])
            img = flat
        try:
            if moved:
                self.win.geometry("+%d+%d" % (self.ox, self.oy))
            self._frame = self.view.frames([img], KEY)[0]
            self.view.show(self._frame)
        except Exception:                                   # noqa: BLE001
            pass

    def set_alpha(self, alpha):
        """설정의 투명도. 윈도우는 -alpha 를 바꾸면 Tk 가 창 모양을 다시 걸면서 클릭 통과가 풀릴 수 있다 - 다시 건다."""
        try:
            self.win.attributes("-alpha", alpha)
            PLAT.make_click_through(self.win)
        except Exception:                                   # noqa: BLE001
            pass

    def destroy(self):
        self.ok = False
        self.parts = []
        try:
            if self.view is not None:
                self.view.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
