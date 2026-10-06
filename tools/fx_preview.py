# -*- coding: utf-8 -*-
"""기술 연출을 창 없이 그려 본다 (GIF · 프레임을 이어 붙인 그림).

    python tools/fx_preview.py 문포스 화염방사          기술 이름(한글·영문)으로
    python tools/fx_preview.py --style moon --type FAIRY 갈래를 직접
    python tools/fx_preview.py --all-styles              갈래마다 대표 기술 하나씩

    --out 폴더    결과를 둘 곳 (기본: ./fx_preview_out)
    --flip        상대가 쓰는 쪽 (오른쪽 위 -> 왼쪽 아래)
    --flat        바탕화면 배틀처럼 나란히 선 배치
    --zoom 2      그리는 배율 (관장 배틀 창은 2배로 그린다)
    --no-gif      이어 붙인 그림만

battle_fx 는 Tk 캔버스에 도형을 그리고 root.after 로 굴러간다. 여기서는 캔버스와
시계를 흉내 내서(FakeCanvas / FakeRoot) **같은 코드를 그대로** 돌리고, 프레임마다
PIL 로 옮겨 그린다. 화면을 못 찍는 환경에서도 연출을 눈으로 볼 수 있다.

client/test_move_fx.py 가 같은 흉내 캔버스로 '끝까지 가는지 · 찌꺼기가 남는지 ·
도형이 너무 많지 않은지' 를 센다 (창을 띄우지 않는다).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))

# 연출 좌표계의 무대 (battle_fx 는 키 48px 도트에 맞춘 크기로 그린다)
# 관장 배틀 창의 실제 비율이다 (860x296 을 2배로 그리니 연출 좌표로는 430x148).
# 가로로 길고 낮아서, 위로 솟는 연출은 머리 위 40~50 에서 잘린다.
STAGE_W, STAGE_H = 430, 148
ME, FOE = (120, 104), (301, 47)             # 나는 왼쪽 아래, 상대는 오른쪽 위 (도트의 가운데)
FLAT_ME, FLAT_FOE = (95, 84), (335, 84)     # 바탕화면 배틀처럼 나란히
BG_TOP, BG_BOT = (44, 50, 72), (26, 30, 44)
FRAME_MS = 33


# ---------------------------------------------------------------- 흉내 시계
class FakeRoot(object):
    """root.after 만 있는 시계. advance(ms) 로 시간을 민다."""

    def __init__(self):
        self.now = 0
        self.jobs = {}
        self._n = 0

    def after(self, ms, fn=None):
        self._n += 1
        self.jobs[self._n] = (self.now + max(0, int(ms)), self._n, fn)
        return self._n

    def after_cancel(self, jid):
        self.jobs.pop(jid, None)

    def advance(self, ms):
        end = self.now + ms
        while True:
            due = [j for j in self.jobs.values() if j[0] <= end]
            if not due:
                break
            when, jid, fn = min(due)
            self.jobs.pop(jid, None)
            self.now = max(self.now, when)
            if fn:
                fn()
        self.now = end


# ---------------------------------------------------------------- 흉내 캔버스
class FakeCanvas(object):
    """battle_fx 가 쓰는 만큼의 Tk Canvas. 그린 것을 적어 두기만 한다."""

    KINDS = ("line", "oval", "polygon", "arc", "rectangle", "text")

    def __init__(self, w=STAGE_W, h=STAGE_H):
        self.w, self.h = w, h
        self.items = {}          # id -> [kind, coords, opts]  (파이썬 dict 는 넣은 순서 = 쌓인 순서)
        self._n = 0
        self.made = 0            # 지금까지 만든 도형 수
        self.peak = 0            # 한때 가장 많았던 도형 수

    @staticmethod
    def _flat(args):
        out = []
        for a in args:
            if isinstance(a, (list, tuple)):
                out.extend(FakeCanvas._flat(a))
            else:
                out.append(float(a))
        return out

    def _make(self, kind, args, kw):
        pts = self._flat(args)
        if len(pts) % 2 or not pts:
            raise ValueError("%s: 좌표가 짝이 안 맞는다 %r" % (kind, pts))
        if any(v != v or abs(v) == float("inf") for v in pts):
            raise ValueError("%s: 좌표에 NaN/inf %r" % (kind, pts))
        self._n += 1
        self.made += 1
        self.items[self._n] = [kind, pts, dict(kw)]
        self.peak = max(self.peak, len(self.items))
        return self._n

    def create_line(self, *a, **kw):
        return self._make("line", a, kw)

    def create_oval(self, *a, **kw):
        return self._make("oval", a, kw)

    def create_polygon(self, *a, **kw):
        return self._make("polygon", a, kw)

    def create_arc(self, *a, **kw):
        return self._make("arc", a, kw)

    def create_rectangle(self, *a, **kw):
        return self._make("rectangle", a, kw)

    def create_text(self, *a, **kw):
        return self._make("text", a, kw)

    def coords(self, item, *a):
        it = self.items.get(item)
        if not a:
            return list(it[1]) if it else []
        if it:
            it[1] = self._flat(a)
        return None

    def move(self, item, dx, dy):
        it = self.items.get(item)
        if it:
            it[1] = [v + (dx if i % 2 == 0 else dy) for i, v in enumerate(it[1])]

    def delete(self, *ids):
        for i in ids:
            if i == "all":
                self.items.clear()
            else:
                self.items.pop(i, None)

    def itemconfigure(self, item, **kw):
        it = self.items.get(item)
        if it:
            it[2].update(kw)

    itemconfig = itemconfigure

    def tag_raise(self, item, *_a):
        it = self.items.pop(item, None)
        if it:
            self.items[item] = it

    def tag_lower(self, item, *_a):
        it = self.items.pop(item, None)
        if it:
            rest = dict(self.items)
            self.items.clear()
            self.items[item] = it
            self.items.update(rest)

    def bbox(self, item):
        it = self.items.get(item)
        if not it:
            return None
        xs, ys = it[1][0::2], it[1][1::2]
        return (min(xs), min(ys), max(xs), max(ys))

    def winfo_width(self):
        return self.w

    def winfo_height(self):
        return self.h


class FakeStage(object):
    """battle_fx.Effect 가 바라는 무대: cv, root, lunge(who, done)."""

    def __init__(self, root=None, cv=None, me=ME, foe=FOE):
        self.root = root or FakeRoot()
        self.cv = cv or FakeCanvas()
        self.pos = {"me": me, "foe": foe}
        self.off = {"me": (0.0, 0.0), "foe": (0.0, 0.0)}
        self.lunges = 0

    def lunge(self, who, done):
        """달려들었다 돌아온다. 관장 배틀 창처럼 190ms 뒤에 done."""
        self.lunges += 1
        other = "foe" if who == "me" else "me"
        (ax, ay), (bx, by) = self.pos[who], self.pos[other]
        d = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / d, (by - ay) / d
        n = 5

        def go(i):
            if i > n * 2:
                self.off[who] = (0.0, 0.0)
                return
            k = i if i <= n else n * 2 - i
            self.off[who] = (ux * 26 * k / n, uy * 26 * k / n)
            self.root.after(28, lambda: go(i + 1))
        go(0)
        self.root.after(190, done)


# ---------------------------------------------------------------- PIL 로 옮겨 그리기
def _rgb(c):
    if not c:
        return None
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _bezier(pts, closed):
    """Tk 의 smooth=True: 꼭짓점을 조절점으로, 변의 가운데를 지나는 2차 곡선."""
    p = list(zip(pts[0::2], pts[1::2]))
    if len(p) < 3:
        return pts
    out = []

    def quad(a, c, b):
        for i in range(7):
            t = i / 6.0
            out.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                        (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]))

    def mid(a, b):
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

    if closed:
        n = len(p)
        for i in range(n):
            quad(mid(p[i - 1], p[i]), p[i], mid(p[i], p[(i + 1) % n]))
    else:
        out.append(p[0])
        for i in range(1, len(p) - 1):
            a = p[0] if i == 1 else mid(p[i - 1], p[i])
            b = p[-1] if i == len(p) - 2 else mid(p[i], p[i + 1])
            quad(a, p[i], b)
    flat = []
    for x, y in out:
        flat += [x, y]
    return flat


_FONTS = {}


def _font(size):
    from PIL import ImageFont
    size = max(6, int(size))
    if size not in _FONTS:
        for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
                     "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf"):
            try:
                _FONTS[size] = ImageFont.truetype(path, size)
                break
            except Exception:                                # noqa: BLE001
                continue
        else:
            _FONTS[size] = ImageFont.load_default()
    return _FONTS[size]


def render(stage, zoom=2.0, ss=2, sprites=True):
    """지금 캔버스에 있는 것을 그림 한 장으로."""
    from PIL import Image, ImageDraw
    cv = stage.cv
    k = zoom * ss
    W, H = int(cv.w * k), int(cv.h * k)
    img = Image.new("RGB", (W, H))
    dr = ImageDraw.Draw(img)
    for y in range(H):
        t = y / float(H)
        dr.line([(0, y), (W, y)], fill=tuple(int(BG_TOP[i] * (1 - t) + BG_BOT[i] * t) for i in range(3)))
    if sprites:
        for who, col in (("foe", (108, 116, 150)), ("me", (124, 134, 170))):
            x, y = stage.pos[who]
            ox, oy = stage.off[who]
            x, y = (x + ox) * k, (y + oy) * k
            z = k * (1.18 if who == "me" else 0.96)          # 내 도트가 조금 크다 (132px / 108px)
            dr.ellipse([x - 22 * z, y + 22 * z, x + 22 * z, y + 30 * z], fill=(18, 20, 30))      # 그림자
            dr.ellipse([x - 17 * z, y - 6 * z, x + 17 * z, y + 26 * z], fill=col)                # 몸
            dr.ellipse([x - 13 * z, y - 26 * z, x + 13 * z, y], fill=col)                         # 머리
    for kind, pts, o in list(cv.items.values()):
        p = [v * k for v in pts]
        fill, outline = _rgb(o.get("fill")), _rgb(o.get("outline"))
        w = max(1, int(round(float(o.get("width", 1)) * k)))
        if kind == "line":
            if o.get("smooth"):
                p = _bezier(p, False)
            col = fill or (0, 0, 0)
            xy = list(zip(p[0::2], p[1::2]))
            dash = o.get("dash")
            if dash:
                on, off = dash[0] * k, (dash[1] if len(dash) > 1 else dash[0]) * k
                for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
                    d = math.hypot(x2 - x1, y2 - y1) or 1.0
                    s = 0.0
                    while s < d:
                        e = min(d, s + on)
                        dr.line([(x1 + (x2 - x1) * s / d, y1 + (y2 - y1) * s / d),
                                 (x1 + (x2 - x1) * e / d, y1 + (y2 - y1) * e / d)], fill=col, width=w)
                        s += on + off
            else:
                dr.line(xy, fill=col, width=w, joint="curve")
                if o.get("capstyle") == "round" and w > 2:
                    for x, y in (xy[0], xy[-1]):
                        dr.ellipse([x - w / 2.0, y - w / 2.0, x + w / 2.0, y + w / 2.0], fill=col)
        elif kind in ("oval", "rectangle"):
            x1, y1, x2, y2 = min(p[0], p[2]), min(p[1], p[3]), max(p[0], p[2]), max(p[1], p[3])
            if kind == "oval" and "outline" not in o:
                outline = (0, 0, 0)                          # Tk 의 기본 테두리는 검정
            fn = dr.ellipse if kind == "oval" else dr.rectangle
            fn([x1, y1, x2, y2], fill=fill, outline=outline, width=w if outline else 0)
        elif kind == "polygon":
            if o.get("smooth"):
                p = _bezier(p, True)
            xy = list(zip(p[0::2], p[1::2]))
            if len(xy) >= 3:
                dr.polygon(xy, fill=fill)
                if outline:
                    dr.line(xy + [xy[0]], fill=outline, width=w, joint="curve")
        elif kind == "arc":
            x1, y1, x2, y2 = min(p[0], p[2]), min(p[1], p[3]), max(p[0], p[2]), max(p[1], p[3])
            st, ex = float(o.get("start", 0)), float(o.get("extent", 90))
            if ex < 0:
                st, ex = st + ex, -ex
            a1, a2 = -(st + ex), -st                         # Tk 는 반시계, PIL 은 시계 방향
            style = o.get("style", "pieslice")
            if x2 - x1 >= 1 and y2 - y1 >= 1:
                if style == "arc":
                    dr.arc([x1, y1, x2, y2], a1, a2, fill=outline or (0, 0, 0), width=w)
                elif style == "chord":
                    dr.chord([x1, y1, x2, y2], a1, a2, fill=fill, outline=outline, width=w)
                else:
                    dr.pieslice([x1, y1, x2, y2], a1, a2, fill=fill, outline=outline, width=w)
        elif kind == "text":
            f = o.get("font")
            size = (f[1] if isinstance(f, tuple) and len(f) > 1 else 10) * 1.33 * k
            dr.text((p[0], p[1]), str(o.get("text", "")), fill=fill or (0, 0, 0),
                    font=_font(size), anchor="mm")
    if ss != 1:
        img = img.resize((W // ss, H // ss), Image.LANCZOS)
    return img


# ---------------------------------------------------------------- 한 편 돌리기
def load_moves():
    raw = json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))
    return raw["moves"]


def find_move(moves, name):
    key = name.strip().lower().replace(" ", "")
    for m in moves.values():
        if (m.get("kr") or "") == name or (m.get("en") or "").lower().replace(" ", "") == key:
            return m
    if name.upper() in moves:
        return moves[name.upper()]
    raise SystemExit("기술을 못 찾았습니다: %s" % name)


def play(move, flip=False, flat=False, limit_ms=4000, step_ms=FRAME_MS, on_frame=None, style=None):
    """연출 하나를 끝까지 돌린다. (stage, 걸린 ms, 끝났나) 를 돌려준다."""
    from poketdesktop import battle_fx as FX
    me, foe = (FLAT_ME, FLAT_FOE) if flat else (ME, FOE)
    stage = FakeStage(me=me, foe=foe)
    who = "foe" if flip else "me"
    src, dst = (foe, me) if flip else (me, foe)
    state = {"done": None}

    def done():
        if state["done"] is None:
            state["done"] = stage.root.now

    fx = FX.Effect(stage, move, src, dst, done, who=who)
    if style:
        fx.style = style                                     # 갈래를 직접 골라 본다
    fx.play()
    if on_frame:
        on_frame(stage)
    while stage.root.now < limit_ms and state["done"] is None:
        stage.root.advance(step_ms)
        if on_frame:
            on_frame(stage)
    return stage, fx, state["done"]


def record(move, zoom=2.0, **kw):
    frames = []
    stage, fx, took = play(move, on_frame=lambda st: frames.append(render(st, zoom=zoom)), **kw)
    return frames, fx, took


def sheet(frames, n=10, cols=5, scale=0.465):
    """프레임 n장을 골라 한 장으로 붙인다."""
    from PIL import Image
    if len(frames) > n:
        idx = [int(round(i * (len(frames) - 1) / float(n - 1))) for i in range(n)]
        frames = [frames[i] for i in idx]
    w, h = frames[0].size
    w2, h2 = int(w * scale), int(h * scale)
    rows = (len(frames) + cols - 1) // cols
    out = Image.new("RGB", (cols * w2, rows * h2), (12, 14, 20))
    for i, f in enumerate(frames):
        out.paste(f.resize((w2, h2), Image.LANCZOS), ((i % cols) * w2, (i // cols) * h2))
    return out


def label(img, text):
    from PIL import Image, ImageDraw
    bar = 26
    out = Image.new("RGB", (img.size[0], img.size[1] + bar), (12, 14, 20))
    out.paste(img, (0, bar))
    ImageDraw.Draw(out).text((8, bar // 2), text, fill=(235, 238, 250), font=_font(16), anchor="lm")
    return out


def stack(images):
    from PIL import Image
    w = max(i.size[0] for i in images)
    out = Image.new("RGB", (w, sum(i.size[1] for i in images)), (12, 14, 20))
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.size[1]
    return out


def main():
    ap = argparse.ArgumentParser(description="기술 연출 미리보기")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--style")
    ap.add_argument("--type", default="NORMAL")
    ap.add_argument("--power", type=int, default=80)
    ap.add_argument("--all-styles", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "fx_preview_out"))
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--zoom", type=float, default=2.0)
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--sheet", help="이어 붙인 그림을 이 이름 하나로 묶는다")
    ap.add_argument("--frames", type=int, default=10)
    a = ap.parse_args()

    from poketdesktop import battle_fx as FX
    moves = load_moves()
    todo = []
    if a.style:
        todo.append(({"kr": a.style, "en": "", "type": a.type, "cat": "special", "power": a.power,
                      "flags": []}, "%s_%s" % (a.style, a.type)))
    for n in a.names:
        m = find_move(moves, n)
        todo.append((m, m["kr"]))
    if a.all_styles:
        seen = set()
        for m in moves.values():
            st = FX.style_of(m)
            if st not in seen and (m.get("power") or 0) < 200:
                seen.add(st)
                todo.append((m, "%s_%s" % (st, m["kr"])))
    if not todo:
        ap.error("기술 이름이나 --style, --all-styles 를 주세요")

    os.makedirs(a.out, exist_ok=True)
    rows = []
    for m, name in todo:
        frames, fx, took = record(m, zoom=a.zoom, flip=a.flip, flat=a.flat,
                                  style=a.style if m.get("kr") == a.style else None)
        tag = "%s  [%s · %s · 위력 %s]  %s" % (
            m.get("kr"), fx.style, m.get("type"), m.get("power"),
            ("%dms" % took) if took is not None else "안 끝남!")
        print("%-26s %-9s %5s ms  프레임 %3d  도형 최대 %3d / 만든 수 %4d" % (
            name, fx.style, took, len(frames), fx.cv.peak, fx.cv.made))
        row = label(sheet(frames, n=a.frames), tag)
        rows.append(row)
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)
        if not a.sheet:
            row.save(os.path.join(a.out, safe + ".png"))
        if not a.no_gif:
            frames[0].save(os.path.join(a.out, safe + ".gif"), save_all=True, append_images=frames[1:],
                           duration=FRAME_MS + 7, loop=0)
    if a.sheet:
        stack(rows).save(os.path.join(a.out, a.sheet))
        print("->", os.path.join(a.out, a.sheet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
