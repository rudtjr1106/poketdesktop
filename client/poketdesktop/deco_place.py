# -*- coding: utf-8 -*-
"""꾸미기 장식을 걷는 도트에 얹는다 (버전 2). sprites.load_walk 가 부른다. 그림은 deco_art, 목록은 common/deco.

## 자리 (시안 4 의 규칙 그대로)

서버가 meta 에 실어 주는 위치 점(SpriteCollab Offsets - server/app/walkpts.py)을 쓴다. 머리 점(검정)은 실제로
**입 · 턱 자리**, 몸 가운데(초록)는 늘 있다. 장식은 도트보다 두 배 촘촘한 칸으로 그렸으므로, 자리는 원래 칸을
두 배로 키운 '촘촘한 칸' 좌표에서 잡는다.

  · 머리 꼭대기: 머리 점에서 위로 끊기지 않고 칠해진 데까지. 줄의 폭이 머리 폭의 30% 아래로 좁아지면 멈춘다
    (이브이 이마 털 · 귀 끝에 왕관이 올라가지 않게)
  · 왕관: 꼭대기에 아래 세 줄이 걸치게 · 머리 장식(리본 · 꽃핀): 정면은 머리 안쪽 오른쪽 위, 옆모습은 뒤통수 위
  · 목걸이: 머리 점 조금 아래, 옆모습은 몸 가운데 쪽으로. 등을 보이면 안 그린다

위치 점이 없는 출처(followers · ow)는 그림 윗부분 가운데를 머리 점으로 친다.

## 걸을 때 튀지 않게 (10/30 사용자 제보)

프레임마다 자리를 새로 재면 귀 · 털이 흔들리거나 원본 점이 들쭉날쭉해서 장식이 4~10칸씩 튀었다. 그래서 **방향마다
첫 프레임에서 한 번 자리를 정하고**, 다른 프레임은 머리(목) 부분 그림을 첫 프레임과 맞대어 가장 잘 겹치는
이동량만큼만 옮긴다 (shifts). 장식이 머리에 붙어서 같이 움직인다.

## 화면에 얹기

load_walk 가 칸을 잘라 키운 **뒤에** 화면 픽셀 단위로 얹는다 (키우기 전에 얹으면 장식 칸도 같이 뭉개진다):

    화면 = (촘촘한 칸 / 2 - (l, t)) x scale,  장식 배수 k = max(1, round(scale / 2))

장식이 칸 밖으로 나가도 잘리지 않게 위 · 옆에 여백을 더하고, 부르는 쪽이 기준점(ax, ay)을 그만큼 옮긴다.
"""
from PIL import Image, ImageChops

from . import deco_art as ART

S = 2                                   # 원래 도트 칸 1 = 촘촘한 칸 S x S
SEARCH = 6                              # 머리 움직임을 찾아보는 칸 수 (원래 칸)
CROWNS = {"crown_gold": "gold", "crown_silver": "silver", "crown_bronze": "bronze"}
HAIR = ("bow", "flower")
# 방향 -> SpriteCollab 행 번호의 뜻 (sprites 의 방향 상수와 상관없이 '어느 쪽을 보나' 만 쓴다)
FRONT = ("down", "downleft", "downright")
BACK = ("up", "upleft", "upright")
FACE_RIGHT = ("downright", "right", "upright")
GLINT_SEQ = {1: [2], 2: [1, 2], 3: [1, 2, 3], 4: [1, 2, 3, 4], 5: [0, 1, 2, 3, 4]}
GLINT_EVERY_MS = 1400                   # 왕관이 이만큼마다 한 번 반짝


def accessories(items):
    """그릴 장식만 (효과는 deco_fx 가 따로). 순서 = 그리는 차례."""
    return tuple(k for k in items or () if k in CROWNS or k in HAIR or k == "pearls")


# ---------------------------------------------------------------- 그림 재기 (촘촘한 칸)
def _opaque(im, x, y):
    return 0 <= x < im.width and 0 <= y < im.height and im.getpixel((x, y))[3] > 0


def _run(im, x, y):
    if not _opaque(im, x, y):
        return None
    l = r = x
    while _opaque(im, l - 1, y):
        l -= 1
    while _opaque(im, r + 1, y):
        r += 1
    return l, r


def _head_top(im, hx, hy):
    y = hy
    if not _opaque(im, hx, y):
        for dy in range(1, 3 * S):
            if _opaque(im, hx, y - dy):
                y -= dy
                break
    wide = 0
    for yy in range(y, max(-1, y - 6 * S), -1):
        r = _run(im, hx, yy)
        if r:
            wide = max(wide, r[1] - r[0] + 1)
    while _opaque(im, hx, y - 1):
        r = _run(im, hx, y - 1)
        if r and (r[1] - r[0] + 1) < max(3 * S, wide * 0.3):
            break
        y -= 1
    return y


def guess_head(cell):
    """위치 점이 없을 때 (원래 칸 좌표): 그림 윗부분 가운데."""
    bb = cell.getbbox()
    if not bb:
        return cell.width // 2, cell.height // 2
    x = (bb[0] + bb[2]) // 2
    return x, bb[1] + int((bb[3] - bb[1]) * 0.4)


class Spot(object):
    """한 방향 첫 프레임의 자리. im = 촘촘한 칸으로 키운 칸, head · center = 원래 칸 좌표."""

    def __init__(self, im, head, center, face):
        self.im, self.face = im, face
        self.hx, self.hy = head[0] * S + S // 2, head[1] * S + S // 2
        c = center or head
        self.cx, self.cy = c[0] * S + S // 2, c[1] * S + S // 2
        if not _opaque(im, self.hx, self.hy):
            # 점이 투명한 자리에 찍힌 칸 - 가장 가까운 칠한 줄로
            bb = im.getbbox()
            if bb:
                self.hx = min(max(self.hx, bb[0]), bb[2] - 1)
        self.top = _head_top(im, self.hx, self.hy)

    def side(self):
        """머리 장식을 다는 쪽 (+1 = 화면 오른쪽). 옆모습은 뒤통수 쪽, 정면은 오른쪽."""
        return -1 if self.face in FACE_RIGHT else 1

    def crown(self, it):
        span = _run(self.im, self.hx, min(self.top + 3, self.hy)) or (self.hx, self.hx)
        mid = (span[0] + span[1] + 1) // 2
        return mid - it.width // 2, self.top - it.height + 3

    def hair(self, it, low=0):
        yy = min(self.top + 2 + low, self.hy)
        span = _run(self.im, self.hx, yy) or (self.hx, self.hx)
        if self.face in FRONT:
            return span[1] - int(it.width * 0.9), self.top - it.height // 2 + 3 + low
        if self.side() > 0:
            return span[1] - it.width + 4, self.top - it.height // 2 + 1 + low
        return span[0] - 3, self.top - it.height // 2 + 1 + low

    def neck(self):
        nx = int(round(self.hx + (self.cx - self.hx) * 0.6))
        ny = self.hy + 3
        span = _run(self.im, nx, ny) or (nx - 6, nx + 6)
        half = max(4, int(round((span[1] - span[0] + 1) * 0.34)))
        return nx, ny, half


# ---------------------------------------------------------------- 튀지 않게
def _gray(im):
    """찾기용 한 장: 투명 = 0, 칠한 칸 = 64 + 밝기 3/4. RGBA 넷을 다 견주는 것보다 네 배 가볍고, 투명 · 칠함이
    어긋난 칸은 색이 다른 칸보다 늘 크게 친다 (예전 '알파는 네 배' 와 같은 뜻)."""
    a = im.split()[3].point(lambda v: 255 if v >= 128 else 0)
    lum = im.convert("L").point(lambda v: 64 + v * 3 // 4)
    return Image.composite(lum, Image.new("L", im.size, 0), a)


def _diff(a, b):
    """두 조각이 얼마나 다른가 (작을수록 같다)."""
    return sum(ImageChops.difference(a, b).tobytes())


def shifts(cells, box, search=SEARCH):
    """첫 칸의 box(원래 칸 좌표)를 다른 칸에서 찾아 이동량 [(dx, dy)] 을 준다 (첫 칸은 (0, 0)).

    **화면 스레드에서도 불린다** (처음 보는 동작) - 가볍게: 지난 칸의 이동량이 그대로 맞으면 바로 쓰고, 아니면 두 칸
    간격으로 훑은 뒤 그 둘레 한 칸만 다시 본다 (13x13 = 169 번 -> 49 + 8 번).
    """
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return [(0, 0)] * len(cells)
    ref = _gray(cells[0]).crop(box)
    out = [(0, 0)]
    prev = (0, 0)
    for im in cells[1:]:
        g = _gray(im)
        seen = {}

        def score(dx, dy):
            got = seen.get((dx, dy))
            if got is None:
                got = seen[(dx, dy)] = (_diff(ref, g.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy))),
                                        abs(dx - prev[0]) + abs(dy - prev[1]), abs(dx) + abs(dy))
            return got
        if score(*prev)[0] == 0:
            out.append(prev)
            continue
        best = min(((score(dx, dy), (dx, dy)) for dy in range(-search, search + 1, 2)
                    for dx in range(-search, search + 1, 2)), key=lambda t: t[0])
        bx, by = best[1]
        best = min([best] + [(score(dx, dy), (dx, dy)) for dy in (by - 1, by, by + 1) for dx in (bx - 1, bx, bx + 1)
                             if abs(dx) <= search and abs(dy) <= search], key=lambda t: t[0])
        prev = best[1]
        out.append(best[1])
    return out


def _head_box(sp):
    """머리 상자 (원래 칸 좌표): 머리 꼭대기 ~ 머리 점, 폭은 그 사이 가운데 줄의 칠한 폭."""
    mid = (sp.top + sp.hy) // 2
    span = _run(sp.im, sp.hx, mid) or (sp.hx - 4, sp.hx + 4)
    return (max(0, span[0] // S - 1), max(0, sp.top // S - 1), span[1] // S + 2, sp.hy // S + 2)


# ---------------------------------------------------------------- 한 방향
def plan(cells, heads, centers, face, items):
    """한 방향의 원래 칸들 -> 프레임마다 그릴 것 [[(그림, 촘촘x, 촘촘y)] ...] 과 왕관 자리 [(x, y, 폭) 또는 None]."""
    n = len(cells)
    if not n or not items:
        return [[] for _ in range(n)], [None] * n
    c0 = cells[0]
    head = (heads[0] if heads and heads[0] else None) or (centers[0] if centers and centers[0] else None) \
        or guess_head(c0)
    center = centers[0] if centers and centers[0] else None
    big = c0.resize((c0.width * S, c0.height * S), Image.NEAREST)
    sp = Spot(big, head, center, face)
    hsh = shifts(cells, _head_box(sp)) if n > 1 else [(0, 0)]
    head_draws, neck_draws = [], []
    crown_at = None
    has_crown = any(k in CROWNS for k in items)
    for k in items:
        if k in CROWNS:
            c = ART.crown(CROWNS[k])
            x, y = sp.crown(c)
            head_draws.append((c, x, y))
            crown_at = (x, y, c.width)
    for k in items:
        if k in HAIR:
            art = ART.bow() if k == "bow" else ART.flower_pin()
            if sp.side() < 0:
                art = art.transpose(Image.FLIP_LEFT_RIGHT)
            x, y = sp.hair(art, low=6 if has_crown else 0)
            if has_crown:
                x += 3 if sp.side() > 0 else -3
            head_draws.append((art, x, y))
    nsh = [(0, 0)] * n
    if "pearls" in items and face not in BACK:
        nx, ny, half = sp.neck()
        pts = []
        if face in FRONT:
            for dx in range(-half, half + 1, 2):
                t = dx / float(half)
                pts.append((nx + dx, ny - 1 + int(round(4 * (1 - t * t)))))
            low = (nx, ny + 3)
        else:
            f = 1 if face in FACE_RIGHT else -1
            a, b = (nx - f * half, ny - 3), (nx + f * max(1, half // 4), ny + 2)
            m = max(2, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / 2))
            for i in range(m + 1):
                pts.append((int(round(a[0] + (b[0] - a[0]) * i / float(m))),
                            int(round(a[1] + (b[1] - a[1]) * i / float(m)))))
            low = b
        p = ART.pearl()
        for (x, y) in pts:
            neck_draws.append((p, x - 1, y - 1))
        h = ART.heart()
        neck_draws.append((h, low[0] - h.width // 2, low[1]))
        if n > 1:
            box = (max(0, (nx - half) // S - 1), max(0, (ny - 4) // S), (nx + half) // S + 2, (ny + 7) // S + 1)
            nsh = shifts(cells, box)
    frames, crowns = [], []
    for i in range(n):
        hx, hy = hsh[i][0] * S, hsh[i][1] * S
        nx_, ny_ = nsh[i][0] * S, nsh[i][1] * S
        frames.append([(im, x + nx_, y + ny_) for im, x, y in neck_draws]
                      + [(im, x + hx, y + hy) for im, x, y in head_draws])
        crowns.append((crown_at[0] + hx, crown_at[1] + hy, crown_at[2]) if crown_at else None)
    return frames, crowns


# ---------------------------------------------------------------- load_walk 에서
def decorate(frames, cuts, faces, points, crop, scale, items):
    """sprites.load_walk 가 키운 프레임들에 장식을 얹는다.

    frames  {방향: [키운 RGBA 칸]}   (아직 투명색으로 칠하기 전)
    cuts    {방향: [원래 칸]}         faces {방향: 'down' 따위}
    points  {방향: (머리 점 목록, 몸 가운데 목록)}  (원래 칸 좌표, 없으면 None)
    crop    (l, t) - 원래 칸에서 잘라 낸 왼쪽 위
    -> (새 frames, 늘어난 (왼, 위, 오른, 아래) 여백, 반짝일 자리 {방향: [(화면x, 화면y) 또는 None]}, 장식 배수 k)
    """
    items = accessories(items)
    if not items:
        return frames, (0, 0, 0, 0), {}, 1
    l, t = crop
    k = max(1, int(round(scale / 2.0)))
    placed = {}
    lo_x = lo_y = 0
    hi_x = hi_y = 0
    ow = max(f.width for fs in frames.values() for f in fs)
    oh = max(f.height for fs in frames.values() for f in fs)
    for d, fs in frames.items():
        heads, centers = points.get(d) or (None, None)
        draws, crowns = plan(cuts[d], heads, centers, faces[d], items)
        out, glints = [], []
        for i, dr in enumerate(draws):
            row = []
            for im, fx, fy in dr:
                art = ART.scaled(im, k)
                sx = int(round((fx / float(S) - l) * scale))
                sy = int(round((fy / float(S) - t) * scale))
                row.append((art, sx, sy))
                lo_x, lo_y = min(lo_x, sx), min(lo_y, sy)
                hi_x, hi_y = max(hi_x, sx + art.width), max(hi_y, sy + art.height)
            out.append(row)
            c = crowns[i] if i < len(crowns) else None
            glints.append((int(round(((c[0] + c[2] - 5) / float(S) - l) * scale)),
                           int(round(((c[1] - 3) / float(S) - t) * scale))) if c else None)
        placed[d] = (out, glints)
    g = ART.scaled(ART.glint(2), k)
    for d, (_out, glints) in placed.items():
        for gp in glints:
            if gp:
                lo_x, lo_y = min(lo_x, gp[0]), min(lo_y, gp[1])
                hi_x, hi_y = max(hi_x, gp[0] + g.width), max(hi_y, gp[1] + g.height)
    pad = (max(0, -lo_x), max(0, -lo_y), max(0, hi_x - ow), max(0, hi_y - oh))
    new = {}
    spots = {}
    for d, fs in frames.items():
        out, glints = placed[d]
        res = []
        for i, f in enumerate(fs):
            canvas = Image.new("RGBA", (ow + pad[0] + pad[2], oh + pad[1] + pad[3]), (0, 0, 0, 0))
            canvas.alpha_composite(f, (pad[0], pad[1]))
            for art, sx, sy in out[i]:
                canvas.alpha_composite(art, (sx + pad[0], sy + pad[1]))
            res.append(canvas)
        new[d] = res
        spots[d] = [((gp[0] + pad[0], gp[1] + pad[1]) if gp else None) for gp in glints]
    return new, pad, spots, k


def with_glint(frames, durations, spots, k):
    """왕관이 있으면 걷기 고리를 몇 번 이어 붙이고 마지막 고리에만 반짝임을 넣는다 (GLINT_EVERY_MS 마다 한 번).

    frames {방향: [RGBA]} 는 장식을 얹은 뒤의 것. -> (새 frames, 새 durations)
    """
    if not spots or not any(any(s) for s in spots.values()):
        return frames, durations
    n = len(durations)
    total = sum(durations) or 1
    reps = max(1, int(round(GLINT_EVERY_MS / float(total))))
    seq = GLINT_SEQ[min(5, n)]
    out = {}
    for d, fs in frames.items():
        sp = spots.get(d) or []
        last = []
        for i, f in enumerate(fs):
            if i < len(seq) and i < len(sp) and sp[i]:
                g = ART.scaled(ART.glint(seq[i]), k)
                f = f.copy()
                f.alpha_composite(g, (max(0, min(sp[i][0], f.width - g.width)),
                                      max(0, min(sp[i][1], f.height - g.height))))
            last.append(f)
        out[d] = list(fs) * (reps - 1) + last
    return out, list(durations) * reps
