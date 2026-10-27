# -*- coding: utf-8 -*-
"""숨는 기술 연출 (2.0) — 공중날기·뛰어오르다·프리폴·구멍파기·다이빙·고스트다이브·섀도다이브와 모으는 기술.

두 턴 기술은 첫 턴에 숨거나 힘을 모으고, 둘째 턴에 때린다. 예전에는 첫 턴에도 공격 연출을 그대로
틀어서 두 번 때리는 것처럼 보였고, 숨은 턴에도 포켓몬이 그 자리에 서 있었다. 이제

    첫 턴    fly     웅크렸다가 하늘로 솟구쳐 사라진다 (발밑에 먼지, 뒤에 바람 줄기)
             dig     몸을 떨며 땅을 파고들어 흙먼지 속으로 사라진다
             dive    살짝 뛰었다가 물보라를 일으키며 물속으로
             vanish  검은 기운에 싸여 깜빡이다가 사라진다
             power   타입 색 기운이 몸으로 모여든다 (숨지 않는다 - 솔라빔·로켓박치기 ...)
    숨은 동안 그 도트는 안 보인다 (battle_fx.Hiding)
    둘째 턴  fly     위에서 내리꽂혀 돌아온 뒤 공격 / dig·dive 는 발밑에서 솟아 나온 뒤 공격
             vanish  안 보이는 채로 공격하고, 끝나면 나타난다

charge 는 서버가 첫 턴 기술 사건에 단다 (common/battle._charge_turn). 숨은 자리 하나에 연출 하나라
뛰어오르다·프리폴은 공중날기와 같은 것을 쓴다.

그리는 법은 move_fx 와 같다 (반투명 없음, create_* / coords / move / delete 만). 도트는 fx.body_move /
body_show 로만 움직인다 - 연출이 끝나거나 도중에 멈추면 battle_fx.Effect.finish 가 제자리로 돌려놓고
보임을 숨김 기록대로 맞춘다. 그래서 숨김 기록은 **연출을 시작할 때** 적는다.
"""
import math
import random

from . import battle_fx as FX
from . import move_fx as M

HIDE = ("fly", "dig", "dive", "vanish")
DUST = ("#f4f1e8", "#b8b2a0")          # 먼지 (밝은, 어두운)
DIRT = ("#e0c08a", "#8a5a2b")          # 흙
WIND = ("#ffffff", "#c9d6ea")          # 바람 줄기
MS = M.MS


def takes(fx):
    """이 기술 사건을 여기서 틀어야 하나: 첫 턴이거나, 쓰는 쪽(또는 데려간 상대)이 숨어 있다.

    숨은 채로 따라 쓴 기술(춤추기가 상대의 춤을 따라 했다 - 서버가 stay 를 단다)은 아니다. 엔진도 그대로
    숨겨 두므로 보통 연출을 숨은 자리에서 틀고, 다시 나오는 것은 진짜 둘째 턴에 한다.
    """
    if fx.charge:
        return True
    if fx.stay:
        return False
    hd = fx.hiding
    return bool(hd is not None and (hd.hidden(fx.keys[0]) or fx.keys[0] in hd.held))


def play(fx, attack):
    """attack() 은 보통의 공격 연출 (battle_fx.Effect._play_move)."""
    hd = fx.hiding
    if fx.charge and hd is not None and hd.hidden(fx.keys[0]):
        # 숨어 있었는데 새 두 턴 기술을 시작한다 - 잠금이 풀려(PP · 사슬묶기 ...) 엔진은 이미 내려놓았다.
        # 보이게 돌려놓고 거기서 다시 숨거나 모은다.
        for key, _kind in hd.come_out(fx.keys[0]):
            fx.touched.add(key)
            hd.set(key, True)
    if fx.charge in HIDE:
        return hide(fx, fx.charge)
    if fx.charge:
        return gather(fx)
    return come_back(fx, attack)


# ---------------------------------------------------------------- 몸
class Body(object):
    """움직일 도트 하나와 그 몸의 자리."""

    def __init__(self, fx, key, center):
        self.fx, self.key = fx, key
        box = fx.body_box(key)
        cx, cy = center
        if box and box[3] > box[1]:
            self.cx = (box[0] + box[2]) / 2.0
            self.h = max(24.0, float(box[3] - box[1]))
            self.w = max(24.0, float(box[2] - box[0]))
            self.feet = float(box[3])
        else:
            self.cx, self.h, self.w = cx, 56.0, 56.0
            self.feet = cy + 28.0
        self.cy = self.feet - self.h / 2.0
        self.off = [0.0, 0.0]                   # 지금 옮겨 둔 만큼

    def to(self, x, y):
        """제자리에서 (x, y) 만큼 비킨 곳으로."""
        self.fx.body_move(self.key, x - self.off[0], y - self.off[1])
        self.off = [x, y]

    def show(self, on):
        self.fx.body_show(self.key, on)

    def home(self):
        self.to(0.0, 0.0)


def _bodies(fx, keys):
    out = []
    for key in keys:
        center = fx.src if key == fx.keys[0] else fx.dst
        out.append(Body(fx, key, center))
    return out


# ---------------------------------------------------------------- 첫 턴: 숨는다
def hide(fx, kind):
    src, dst = fx.keys
    keys = [src] + ([dst] if fx.carry and dst is not None else [])
    hd = fx.hiding
    if hd is not None:
        # 기록을 먼저 적는다 - 도중에 멈춰도 finish 가 숨김대로 맞춘다
        for key in keys:
            hd.kind[key] = kind if key == src else "fly"
            fx.touched.add(key)
        if len(keys) > 1:
            hd.held[src] = dst
    bodies = _bodies(fx, keys) if hd is not None else []
    if not bodies:                              # 숨길 수 없는 화면이다 - 그 자리에서 기운만 보인다
        bodies = [Body(fx, None, fx.src)]
    {"fly": _fly_up, "dig": _dig_in, "dive": _dive_in, "vanish": _fade_out}[kind](fx, bodies, fx.finish)


def _streaks(fx, cel, x, y0, y1, k, w=1.0):
    """세로 바람 줄기 세 가닥 (y0 아래 끝, y1 위 끝). k 는 남은 굵기 1 -> 0."""
    cv = fx.cv
    for dx, sc in ((-0.32, 0.7), (0.0, 1.0), (0.3, 0.8)):
        xx = x + dx * w
        top = y1 + (y0 - y1) * (1.0 - sc) * 0.5
        th = max(1, int(round(4 * k * sc)))
        cel.put(cv.create_line(xx, y0, xx, top, fill=WIND[1], width=th + 2, capstyle="round"),
                cv.create_line(xx, y0, xx, top, fill=WIND[0], width=th, capstyle="round"))


def _dust(fx, sp, x, y, n=6, col=DUST, spread=3.2):
    """발밑에서 양옆으로 퍼지는 먼지."""
    cv = fx.cv
    for j in range(n):
        side = -1 if j % 2 else 1
        r0 = random.uniform(6, 10)
        sp.add(lambda px, py, k, r0=r0: M.puff(cv, px, py, r0 * (0.4 + 0.6 * k), col[0], col[1]),
               x + side * random.uniform(2, 8), y - random.uniform(0, 4),
               side * random.uniform(1.2, spread), -random.uniform(0.2, 1.2), life=random.randint(7, 11),
               drag=0.86)


def _fly_up(fx, bodies, done):
    """웅크렸다가 하늘로 솟구친다. 사라진 자리에 반짝임 하나."""
    cv = fx.cv
    cel = M.Cel(fx)
    sp = M.Sparks(fx)
    lift = max(90.0, max(b.h for b in bodies) * 1.7)
    gone = 9                                    # 이 장에서 사라진다
    peak = {}                                   # 사라지기 직전에 올라가 있던 만큼

    def draw(i, t):
        cel.clear()
        for j, b in enumerate(bodies):
            if b.key is None:
                continue
            if i <= 3:
                b.to(0.0, 4.0 * i / 3.0)                            # 웅크린다
            elif i < gone:
                u = (i - 3) / float(gone - 3)
                b.to(0.0, 4.0 - (lift + 4.0) * M.ease_in(u) * (1.0 - 0.12 * j))
            elif i == gone:
                b.show(False)
                b.home()                                            # 안 보이는 동안 제자리로
        b = bodies[0]
        if i == 3:
            for bb in bodies:
                _dust(fx, sp, bb.cx, bb.feet)
        if 4 <= i < gone:                                           # 올라간 길에 바람 줄기
            up = 4.0 - (lift + 4.0) * M.ease_in((i - 3) / float(gone - 3))
            peak[0] = up
            _streaks(fx, cel, b.cx, b.feet - 4, b.feet + up, 1.0, w=b.w * 0.5)
        elif gone <= i < gone + 5:                                  # 줄기가 위로 걷히며 가늘어진다
            u = (i - gone + 1) / 5.0
            top = b.feet + peak.get(0, -lift)
            _streaks(fx, cel, b.cx, b.feet + (top - b.feet) * u, top, 1.0 - u, w=b.w * 0.5)
            cel.put(M.glint(cv, b.cx, top - b.h * 0.5, max(2, 13 * (1.0 - u))))

    M.run(fx, gone + 6, draw, done, ms=MS)


def _mound(cv, x, y, w, h, col):
    """흙더미 (발밑의 반달)."""
    return [cv.create_oval(x - w / 2.0, y - h, x + w / 2.0, y + h * 0.6, fill=col[1], outline=col[0], width=2),
            cv.create_oval(x - w * 0.3, y - h * 0.8, x + w * 0.1, y - h * 0.3, fill=col[0], outline="")]


def _clods(fx, sp, x, y, n, col=DIRT, up=5.0):
    """튀어 오르는 흙덩이."""
    cv = fx.cv
    for _ in range(n):
        r0 = random.uniform(2.5, 4.5)
        seed = random.randint(0, 99)
        sp.add(lambda px, py, k, r0=r0, seed=seed: M.rock(cv, px, py, r0 * (0.5 + 0.5 * k), col[0], col[1], seed),
               x + random.uniform(-10, 10), y - 4, random.uniform(-2.6, 2.6), -random.uniform(up * 0.6, up),
               life=random.randint(8, 12), g=0.55)


def _dig_in(fx, bodies, done):
    """몸을 떨며 땅을 파고든다. 흙이 튀고, 흙먼지 속으로 사라진다."""
    cv = fx.cv
    cel = M.Cel(fx)
    sp = M.Sparks(fx)
    b = bodies[0]
    gone = 8
    mw = max(40.0, b.w * 0.95)

    def draw(i, t):
        cel.clear()
        if b.key is not None and i < gone:
            b.to(2.5 if i % 2 else -2.5, 10.0 * M.ease_in(i / float(gone)))
        elif b.key is not None and i == gone:
            b.show(False)
            b.home()
        if 2 <= i <= gone:
            _clods(fx, sp, b.cx, b.feet, 2)
        if i == gone:
            _dust(fx, sp, b.cx, b.feet - 6, n=8, col=DIRT, spread=2.6)
        mh = 4 + 8 * min(1.0, i / 4.0)
        if i > gone + 4:
            mh *= max(0.35, 1.0 - (i - gone - 4) / 6.0)
        cel.put(_mound(cv, b.cx, b.feet, mw, mh, DIRT))

    M.run(fx, gone + 9, draw, done, ms=MS)


def _ripple(cv, cel, x, y, r, k, col):
    th = max(1, int(round(3 * k)))
    cel.put(cv.create_oval(x - r, y - r * 0.28, x + r, y + r * 0.28, outline=col[1], width=th + 2),
            cv.create_oval(x - r, y - r * 0.28, x + r, y + r * 0.28, outline=col[0], width=th))


def _splash(fx, sp, x, y, n=9, up=6.0):
    cv = fx.cv
    light, dark = FX.colors("WATER")
    for _ in range(n):
        r0 = random.uniform(3, 5)
        sp.add(lambda px, py, k, r0=r0: FX._drop(cv, px, py, r0 * (0.5 + 0.5 * k), light, dark),
               x + random.uniform(-12, 12), y - 4, random.uniform(-2.2, 2.2), -random.uniform(up * 0.6, up),
               life=random.randint(8, 12), g=0.6)


def _dive_in(fx, bodies, done):
    """살짝 뛰었다가 물보라 속으로 들어간다. 물결이 퍼진다."""
    cv = fx.cv
    cel = M.Cel(fx)
    sp = M.Sparks(fx)
    b = bodies[0]
    water = FX.colors("WATER")
    gone = 7

    def draw(i, t):
        cel.clear()
        if b.key is not None:
            if i <= 3:
                b.to(0.0, -12.0 * M.ease_out(i / 3.0))
            elif i < gone:
                b.to(0.0, -12.0 + 26.0 * M.ease_in((i - 3) / float(gone - 3)))
            elif i == gone:
                b.show(False)
                b.home()
        if i >= 3:                                              # 물낯
            w = max(34.0, b.w * 0.9)
            cel.put(cv.create_oval(b.cx - w / 2.0, b.feet - 5, b.cx + w / 2.0, b.feet + 5,
                                   fill=water[1], outline=water[0], width=2))
        if i == gone - 1:
            _splash(fx, sp, b.cx, b.feet)
        if i >= gone:
            for q in range(2):
                u = (i - gone - q * 2) / 7.0
                if 0.0 <= u <= 1.0:
                    _ripple(cv, cel, b.cx, b.feet, 16 + 34 * M.ease_out(u), 1.0 - u, water)

    M.run(fx, gone + 9, draw, done, ms=MS)


# 깜빡임: 보이면 1 (11 번째 장부터는 계속 안 보인다)
FLICKER = (1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 1)


def _fade_out(fx, bodies, done):
    """검은 기운이 몸을 휘감고, 깜빡이다 사라진다."""
    cv = fx.cv
    cel = M.Cel(fx)
    b = bodies[0]
    light, dark = FX.colors(fx.type if fx.type in ("GHOST", "DARK") else "GHOST")
    ink = M.mix(dark, "#000000", 0.45)
    n = 16
    r0 = max(30.0, b.h * 0.62)

    def draw(i, t):
        cel.clear()
        if b.key is not None:
            b.show(bool(FLICKER[i]) if i < len(FLICKER) else False)
        if i < n - 3:
            rr = r0 * (1.0 - 0.6 * t)
            for j in range(6):
                a = i * 0.55 + j * math.pi / 3.0
                x, y = b.cx + math.cos(a) * rr, b.cy + math.sin(a) * rr * 0.75
                cel.put(M.tongue(cv, x, y, 7 + 3 * math.sin(i + j), 4 * math.cos(a), ink, light))
        else:                                                   # 한 점으로 오그라든다
            u = (i - (n - 3)) / 3.0
            r = max(2, 12 * (1.0 - u))
            cel.put(cv.create_oval(b.cx - r, b.cy - r, b.cx + r, b.cy + r, fill=ink, outline=light, width=2))

    M.run(fx, n, draw, done, ms=MS)


# ---------------------------------------------------------------- 첫 턴: 모은다 (숨지 않는 두 턴 기술)
def gather(fx):
    """타입 색 기운이 둘레에서 몸으로 모여든다. 다 모이면 고리가 한 번 번쩍한다."""
    cv = fx.cv
    cel = M.Cel(fx)
    b = Body(fx, None, fx.src)
    light, dark = FX.colors(fx.type)
    R = max(48.0, b.h * 0.95)
    waves = [[random.uniform(0, 2 * math.pi) for _ in range(8)] for _ in range(2)]
    n = 18

    def draw(i, t):
        cel.clear()
        for w, angs in enumerate(waves):
            u = (i - w * 6) / 9.0
            if not 0.0 <= u <= 1.0:
                continue
            for a in angs:
                rr = R * (1.0 - M.ease_in(u))
                x, y = b.cx + math.cos(a) * rr, b.cy + math.sin(a) * rr
                cel.put(FX.particle(cv, fx.type, x, y, 3.5 + 3.5 * (1.0 - u)))
        if 4 <= i <= 15:
            r = 4 + 10 * min(1.0, (i - 4) / 9.0)
            cel.put(M.orb(cv, b.cx, b.cy, r, light, dark))
        if i >= 15:
            u = (i - 15) / 3.0
            r = 14 + 30 * M.ease_out(u)
            th = max(1, int(round(4 * (1.0 - u))))
            cel.put(cv.create_oval(b.cx - r, b.cy - r, b.cx + r, b.cy + r, outline=light, width=th))

    M.run(fx, n, draw, fx.finish, ms=MS)


# ---------------------------------------------------------------- 둘째 턴: 다시 나온다
def come_back(fx, attack):
    back = fx.hiding.come_out(fx.keys[0])
    for key, _kind in back:
        fx.touched.add(key)                     # 도중에 멈춰도 finish 가 보이게 한다
    if not back:
        return attack()
    kind = back[0][1]
    if kind == "vanish":
        return attack()                         # 안 보이는 채로 때리고, 끝나면(finish) 나타난다
    bodies = []
    for key, _k in back:
        b = Body(fx, key, fx.src if key == fx.keys[0] else fx.dst)
        bodies.append(b)
    {"fly": _drop_in, "dig": _pop_up, "dive": _pop_up}.get(kind, _drop_in)(fx, bodies, kind, attack)


def _drop_in(fx, bodies, _kind, then):
    """위에서 내리꽂혀 제자리로 (공중날기·프리폴). 끌려간 상대도 같이 떨어진다."""
    cel = M.Cel(fx)
    sp = M.Sparks(fx)
    lift = max(90.0, max(b.h for b in bodies) * 1.7)
    for b in bodies:
        b.to(0.0, -lift)
        b.show(True)
    n = 6

    def draw(i, t):
        cel.clear()
        for b in bodies:
            b.to(0.0, -lift * (1.0 - M.ease_in(t)))
            if i < n:
                _streaks(fx, cel, b.cx, b.feet - b.h + b.off[1], b.feet - b.h + b.off[1] - 40, 1.0 - t * 0.6,
                         w=b.w * 0.5)

    def land():
        cel.clear()
        for b in bodies:
            _dust(fx, sp, b.cx, b.feet, n=6)
        then()
    M.run(fx, n, draw, land, ms=MS)


def _pop_up(fx, bodies, kind, then):
    """발밑에서 솟아 나온다 (구멍파기 - 흙, 다이빙 - 물보라)."""
    cv = fx.cv
    cel = M.Cel(fx)
    sp = M.Sparks(fx)
    b = bodies[0]
    b.to(0.0, 12.0)
    b.show(True)
    if kind == "dig":
        _clods(fx, sp, b.cx, b.feet, 7, up=6.0)
    else:
        _splash(fx, sp, b.cx, b.feet, n=10, up=7.0)
    water = FX.colors("WATER")
    n = 5

    def draw(i, t):
        cel.clear()
        b.to(0.0, 12.0 * (1.0 - M.ease_out(t)))
        w = max(36.0, b.w * 0.9) * (1.0 - 0.4 * t)
        if kind == "dig":
            cel.put(_mound(cv, b.cx, b.feet, w, 10 * (1.0 - 0.5 * t), DIRT))
        else:
            cel.put(cv.create_oval(b.cx - w / 2.0, b.feet - 5, b.cx + w / 2.0, b.feet + 5,
                                   fill=water[1], outline=water[0], width=2))

    def up():
        cel.clear()
        then()
    M.run(fx, n, draw, up, ms=MS)
