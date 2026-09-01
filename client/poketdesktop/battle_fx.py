# -*- coding: utf-8 -*-
"""기술 연출.

기술마다 그림을 따로 그리는 건 900개라 불가능하다. 대신 PokeAPI 가 주는
**기술 플래그**와 **타입**을 조합해서 연출을 고른다. 본가도 결국
'접촉기는 달려들고, 원거리 특수기는 뭔가 날아간다' 는 규칙을 따른다.

    contact / punch / bite   달려들어 때린다 (주먹·이빨·베기 자국)
    ballistics               둥근 것이 포물선으로 날아간다
    pulse                    고리가 퍼지며 날아간다
    sound                    음파가 겹겹이 퍼진다
    powder                   가루가 흩날려 내려앉는다
    dance / heal / 자기대상    자기 몸에서 기운이 피어오른다
    그 외 특수기              타입 색의 줄기가 뿜어져 나간다 (화염방사 같은)

타입은 색과 모양을 정한다. 불꽃은 일렁이는 불덩이, 물은 물방울,
전기는 지그재그, 풀은 잎사귀... 하는 식이다.

전부 Canvas 도형으로 그린다. 이미지가 아니라서 크기를 바꿔도 깨지지 않고,
저작권 있는 그림을 쓰지 않는다.
"""
import math
import random

# 타입별 색 (밝은색, 어두운색)
TYPE_FX = {
    "NORMAL":   ("#f2f0e4", "#b9b5a0"),
    "FIRE":     ("#ffd24a", "#ff5b2e"),
    "WATER":    ("#8ec9ff", "#2f7fd6"),
    "ELECTRIC": ("#fff27a", "#f2c400"),
    "GRASS":    ("#a8e86a", "#3f9e3a"),
    "ICE":      ("#d8fbff", "#63c8d8"),
    "FIGHTING": ("#ff9a7a", "#c33a52"),
    "POISON":   ("#e5a8ff", "#8f3fbf"),
    "GROUND":   ("#e8cf9a", "#b07a35"),
    "FLYING":   ("#e6ecff", "#8fa9de"),
    "PSYCHIC":  ("#ffb3d9", "#f0537a"),
    "BUG":      ("#d4f07a", "#7ba316"),
    "ROCK":     ("#ded0a8", "#9c8248"),
    "DARK":     ("#8f86a8", "#3a3348"),
    "DRAGON":   ("#9fb8ff", "#3352c4"),
    "STEEL":    ("#e0eaf0", "#7f9aa8"),
    "FAIRY":    ("#ffd6f2", "#e88fd0"),
    "GHOST":    ("#b9a8e0", "#5a4a8f"),
}
DEFAULT_FX = ("#f0f0f0", "#9a9a9a")


def colors(mtype):
    return TYPE_FX.get(mtype, DEFAULT_FX)


def style_of(move):
    """기술 하나가 어떤 연출을 쓸지 고른다."""
    flags = set(move.get("flags") or [])
    cat = move.get("cat") or "status"
    target = move.get("target") or 10
    # 7 = 자기 자신, 6/12 = 자기 편
    if target in (7, 6, 12) or "dance" in flags or "heal" in flags:
        return "self"
    if "powder" in flags:
        return "powder"
    if "sound" in flags:
        return "sound"
    if "punch" in flags:
        return "punch"
    if "bite" in flags:
        return "bite"
    if "pulse" in flags:
        return "pulse"
    if "ballistics" in flags:
        return "ball"
    if "contact" in flags:
        return "contact"
    if cat == "status":
        return "hex"
    return "beam"


def contact_style(style):
    """때리는 쪽이 달려들어야 하는 연출인지."""
    return style in ("contact", "punch", "bite")


# ---------------------------------------------------------------- 도형 조각
def _blob(cv, x, y, r, fill, outline=""):
    return cv.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline)


def _flame(cv, x, y, r, light, dark):
    """불꽃 모양 조각."""
    pts = []
    n = 9
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1.35 if i % 2 == 0 else 0.62)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * 1.15 - r * 0.25]
    return cv.create_polygon(pts, fill=dark, outline=light, width=1, smooth=True)


def _drop(cv, x, y, r, light, dark):
    """물방울."""
    return cv.create_polygon(
        x, y - r * 1.5, x + r, y + r * 0.4, x, y + r, x - r, y + r * 0.4,
        fill=dark, outline=light, width=1, smooth=True)


def _bolt(cv, x, y, r, light, dark):
    """번개 지그재그."""
    return cv.create_line(x - r, y - r, x + r * 0.3, y - r * 0.2,
                          x - r * 0.3, y + r * 0.2, x + r, y + r,
                          fill=light, width=max(2, int(r * 0.5)))


def _leaf(cv, x, y, r, light, dark):
    return cv.create_polygon(x - r, y, x, y - r * 0.8, x + r, y, x, y + r * 0.8,
                             fill=dark, outline=light, width=1, smooth=True)


def _shard(cv, x, y, r, light, dark):
    return cv.create_polygon(x, y - r * 1.3, x + r * 0.7, y, x, y + r * 1.3,
                             x - r * 0.7, y, fill=light, outline=dark, width=1)


def _star(cv, x, y, r, light, dark):
    pts = []
    for i in range(10):
        a = math.pi * i / 5 - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return cv.create_polygon(pts, fill=light, outline=dark, width=1)


PARTICLE = {
    "FIRE": _flame, "WATER": _drop, "ELECTRIC": _bolt, "GRASS": _leaf,
    "ICE": _shard, "PSYCHIC": _star, "FAIRY": _star, "BUG": _leaf,
    "DRAGON": _shard, "GHOST": _blob, "POISON": _blob,
}


def particle(cv, mtype, x, y, r):
    light, dark = colors(mtype)
    fn = PARTICLE.get(mtype)
    if fn is None:
        return _blob(cv, x, y, r, dark, light)
    return fn(cv, x, y, r, light, dark)


# ---------------------------------------------------------------- 연출 재생
class Effect(object):
    """캔버스 위에서 도는 연출 하나. root.after 로 스스로 굴러간다."""

    def __init__(self, stage, move, src, dst, on_done, who="me"):
        self.st = stage
        self.who = who
        self.cv = stage.cv
        self.root = stage.root
        self.move = move or {}
        self.type = self.move.get("type") or "NORMAL"
        self.style = style_of(self.move)
        self.src = src
        self.dst = dst
        self.on_done = on_done
        self.items = []
        self.jobs = []
        self.dead = False

    # ---- 도구 ----
    def after(self, ms, fn):
        if self.dead:
            return
        self.jobs.append(self.root.after(ms, fn))

    def add(self, item):
        self.items.append(item)
        return item

    def clear(self):
        for i in self.items:
            try:
                self.cv.delete(i)
            except Exception:
                pass
        self.items = []

    def finish(self):
        if self.dead:
            return
        self.dead = True
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        self.clear()
        if self.on_done:
            self.on_done()

    def stop(self):
        self.on_done = None
        self.finish()

    # ---- 시작 ----
    def play(self):
        fn = getattr(self, "_" + self.style, None) or self._beam
        try:
            fn()
        except Exception:
            self.finish()

    # ---- 각 연출 ----
    def _beam(self):
        """타입 색 줄기가 뿜어져 나간다 (화염방사, 냉동빔 같은)."""
        sx, sy = self.src
        tx, ty = self.dst
        n = 16

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            for k in range(2):
                r = 7 + 5 * math.sin(i * 0.7 + k)
                self.add(particle(self.cv, self.type,
                                  x + random.uniform(-9, 9),
                                  y + random.uniform(-9, 9), r))
            if i > 6:                        # 꼬리부터 지워서 줄기처럼 보이게
                for _ in range(2):
                    if self.items:
                        self.cv.delete(self.items.pop(0))
            self.after(26, lambda: step(i + 1))
        step(0)

    def _ball(self):
        """둥근 것이 포물선으로 날아간다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        core = self.add(_blob(self.cv, sx, sy, 11, dark, light))
        n = 18

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t - 70 * (t - t * t) * 4
            self.cv.coords(core, x - 11, y - 11, x + 11, y + 11)
            trail = self.add(_blob(self.cv, x, y, 6, light))
            self.after(180, lambda it=trail: self.cv.delete(it))
            self.after(24, lambda: step(i + 1))
        step(0)

    def _pulse(self):
        """고리가 퍼지며 날아간다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        n = 16

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            r = 10 + i * 1.6
            ring = self.add(self.cv.create_oval(x - r, y - r * 0.7, x + r, y + r * 0.7,
                                                outline=light, width=3))
            self.after(220, lambda it=ring: self.cv.delete(it))
            self.after(28, lambda: step(i + 1))
        step(0)

    def _sound(self):
        """음파가 상대 쪽으로 겹겹이 퍼진다."""
        sx, sy = self.src
        tx, _ty = self.dst
        # tkinter 의 0도는 **오른쪽**이다. 각도를 고정해 두면 누가 쓰든
        # 음파가 오른쪽으로만 나가서, 오른쪽에 선 상대가 울음소리를 쓰면
        # 나를 등지고 퍼진다. 부채꼴의 기준을 목표 방향으로 잡는다.
        base = 0 if tx >= sx else 180
        light, dark = colors(self.type)

        def wave(k):
            if self.dead:
                return
            if k >= 4:
                return self.after(220, self.burst)
            r = [0]

            def grow(i):
                if self.dead:
                    return
                if i > 12:
                    return
                rr = 14 + i * 16
                if r[0]:
                    self.cv.delete(r[0])
                r[0] = self.cv.create_arc(sx - rr, sy - rr, sx + rr, sy + rr,
                                          start=base - 50, extent=100,
                                          style="arc", outline=light, width=3)
                self.items.append(r[0])
                self.after(34, lambda: grow(i + 1))
            grow(0)
            self.after(120, lambda: wave(k + 1))
        wave(0)

    def _powder(self):
        """가루가 흩날려 내려앉는다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        bits = []
        for _ in range(22):
            x = sx + random.uniform(-14, 14)
            y = sy + random.uniform(-14, 14)
            bits.append([self.add(_blob(self.cv, x, y, random.uniform(2, 4),
                                        light)), x, y,
                         random.uniform(0.6, 1.4), random.uniform(-0.4, 0.9)])

        def step(i):
            if self.dead:
                return
            if i > 26:
                return self.burst()
            for b in bits:
                item, x, y, vx, vy = b
                x += (tx - sx) / 26.0 * vx
                y += (ty - sy) / 26.0 * vx + vy
                b[1], b[2] = x, y
                r = 3
                self.cv.coords(item, x - r, y - r, x + r, y + r)
            self.after(30, lambda: step(i + 1))
        step(0)

    def _self(self):
        """자기 몸에서 기운이 피어오른다 (능력 상승, 회복, 춤)."""
        sx, sy = self.src
        light, dark = colors(self.type)
        bits = []
        for k in range(14):
            a = 2 * math.pi * k / 14
            bits.append([None, a, 0])

        def step(i):
            if self.dead:
                return
            if i > 20:
                return self.finish()
            for b in bits:
                if b[0]:
                    self.cv.delete(b[0])
                a = b[1] + i * 0.18
                rad = 16 + i * 2.2
                x = sx + math.cos(a) * rad
                y = sy + math.sin(a) * rad * 0.5 - i * 2.4
                b[0] = self.cv.create_oval(x - 4, y - 4, x + 4, y + 4,
                                           fill=light, outline=dark)
                self.items.append(b[0])
            self.after(34, lambda: step(i + 1))
        step(0)

    def _hex(self):
        """상대에게 거는 변화기. 고리가 상대를 감싼다."""
        tx, ty = self.dst
        light, dark = colors(self.type)

        def step(i):
            if self.dead:
                return
            if i > 14:
                return self.finish()
            r = 46 - i * 2.4
            ring = self.add(self.cv.create_oval(tx - r, ty - r * 0.8,
                                                tx + r, ty + r * 0.8,
                                                outline=light, width=3))
            self.after(200, lambda it=ring: self.cv.delete(it))
            self.after(34, lambda: step(i + 1))
        step(0)

    # ---- 접촉기: 때리는 쪽이 달려든 뒤 자국이 남는다 ----
    def _contact(self):
        self.st.lunge(self.src_side(), lambda: self.slash())

    def _punch(self):
        self.st.lunge(self.src_side(), lambda: self.fist())

    def _bite(self):
        self.st.lunge(self.src_side(), lambda: self.fangs())

    def src_side(self):
        return self.who

    def slash(self):
        """베기 자국 세 줄."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for k in range(3):
            off = (k - 1) * 16
            self.add(self.cv.create_line(tx - 30 + off, ty - 30, tx + 30 + off,
                                         ty + 30, fill=light, width=5))
            self.add(self.cv.create_line(tx - 28 + off, ty - 28, tx + 28 + off,
                                         ty + 28, fill=dark, width=2))
        self.after(200, self.burst)

    def fist(self):
        """주먹 충격."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for k in range(8):
            a = 2 * math.pi * k / 8
            self.add(self.cv.create_line(tx + math.cos(a) * 16, ty + math.sin(a) * 16,
                                         tx + math.cos(a) * 42, ty + math.sin(a) * 42,
                                         fill=light, width=4))
        self.add(_blob(self.cv, tx, ty, 15, dark, light))
        self.after(200, self.burst)

    def fangs(self):
        """이빨 자국."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for sign in (-1, 1):
            for k in range(3):
                x = tx + sign * (14 + k * 12)
                self.add(self.cv.create_polygon(
                    x, ty - sign * 6, x + 7, ty - 26 * sign, x + 14, ty - sign * 6,
                    fill=light, outline=dark))
        self.after(200, self.burst)

    # ---- 마무리 충격 ----
    def burst(self):
        self.clear()
        tx, ty = self.dst
        light, dark = colors(self.type)
        rings = []

        def step(i):
            if self.dead:
                return
            if i > 7:
                return self.finish()
            for it in rings:
                self.cv.delete(it)
            del rings[:]
            r = 12 + i * 9
            rings.append(self.cv.create_oval(tx - r, ty - r, tx + r, ty + r,
                                             outline=light if i % 2 else dark,
                                             width=max(1, 6 - i)))
            self.items.extend(rings)
            self.after(30, lambda: step(i + 1))
        step(0)
