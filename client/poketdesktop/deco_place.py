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

## 눈 (2.1.0 - 선글라스 · 그리고 다른 장식이 눈을 가리지 않게)

Offsets 에는 눈 점이 없다. 그래서 그림에서 찾는다 (find_eyes): 머리 꼭대기 ~ 입 사이에서
  1. 짙은 눈동자(사방이 칠해진 아주 짙은 픽셀) 덩어리 + 바로 옆에 흰색에 가까운 빛(흰자 · 눈빛)
  2. 1 이 없으면 머리 띠에서 드문 색(몇 칸 안 되는 색 - 블래키 빨강 · 님피아 파랑 · 푸린 청록) 덩어리
정면은 입 줄을 가운데로 좌우 대칭인 한 쌍, 옆모습은 보는 쪽에 하나. 둘이 다르면 예상 높이(표본 69종에서 잰
정면 64% · 옆 55%)에 가까운 쪽. 그래도 없으면 그 예상 높이와 눈 간격(머리 폭의 43%)으로 둔다.
표본 69종 x 앞 · 옆 · 뒤 207 장면에서 '렌즈가 눈을 덮나 · 관이 머리에 걸치고 눈을 안 가리나 · 핀이 허공에
안 뜨나 · 넥타이가 몸 위에 있나' 를 픽셀로 셌다 (client/test_deco_place.py 에 일부 장면을 그림 없이 남겼다).

자리 고르기(2.1.0): 처음 자리가 눈을 가리거나 허공에 뜨면 가까운 다른 자리를 고른다 - 관은 눈 위로 올리거나
옆모습이면 뒤통수 쪽으로(_crown_fit), 머리 장식은 뒤통수 · 위 · 안쪽으로(_settle), 옆모습 렌즈는 코끝 밖으로
나오면 뒤로(_lens_fit), 넥타이는 몸 밖으로 삐지면 몸 쪽으로(_body_fit).

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
HEADS = ("flower_crown",)                # 왕관 자리에 얹지만 반짝이지 않는 것
HAIR = ("bow", "flower", "star_pin")
FACE = ("shades", "heart_shades")
MEDALS = {"medal_gold": "gold", "medal_silver": "silver", "medal_bronze": "bronze"}     # 올림픽 (2.3.0)
NECK = ("pearls", "bowtie") + tuple(MEDALS)
# 방향 -> SpriteCollab 행 번호의 뜻 (sprites 의 방향 상수와 상관없이 '어느 쪽을 보나' 만 쓴다)
FRONT = ("down", "downleft", "downright")
BACK = ("up", "upleft", "upright")
FACE_RIGHT = ("downright", "right", "upright")
GLINT_SEQ = {1: [2], 2: [1, 2], 3: [1, 2, 3], 4: [1, 2, 3, 4], 5: [0, 1, 2, 3, 4]}
GLINT_EVERY_MS = 1400                   # 왕관이 이만큼마다 한 번 반짝


def accessories(items):
    """그릴 장식만 (효과는 deco_fx 가 따로). 순서 = 그리는 차례."""
    return tuple(k for k in items or () if k in CROWNS or k in HEADS or k in HAIR or k in FACE or k in NECK)


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


def _lum(p):
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


FRONT_EYE, SIDE_EYE, EYE_SEP = 0.64, 0.55, 0.43     # 표본 69종에서 잰 눈 높이(꼭대기 0 ~ 입 1) · 눈 간격(머리 폭)


def _blobs(pts):
    """8방향으로 이어진 덩어리들."""
    left, out = set(pts), []
    while left:
        st = [left.pop()]
        b = list(st)
        while st:
            x, y = st.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in left:
                        left.discard(q)
                        st.append(q)
                        b.append(q)
        out.append(b)
    return out


def _center(b):
    return sum(q[0] for q in b) / float(len(b)), sum(q[1] for q in b) / float(len(b))


def find_eyes(cell, sp):
    """원래 칸 좌표의 눈 [(cx, cy, 픽셀들)] - 정면 둘, 옆 하나, 뒤 · 못 찾음은 []. (위 '눈' 설명)"""
    if sp.face in BACK:
        return []
    W, H = cell.size
    px = cell.load()

    def op(x, y):
        return 0 <= x < W and 0 <= y < H and px[x, y][3] > 0

    top, hy = sp.top // S, sp.hy // S
    band = max(2, hy - top)
    y0, y1 = top + max(1, int(band * 0.3)), max(top + 1, hy - 1)     # 머리 점 줄은 입이다
    span = _run(sp.im, sp.hx, (sp.top + sp.hy) // 2) or (sp.hx - 16, sp.hx + 16)
    x0, x1 = span[0] // S - 1, span[1] // S + 1
    hx, hw = sp.hx / float(S), max(4.0, (x1 - x0) / 2.0)
    front = sp.face in FRONT
    right = sp.face in FACE_RIGHT
    mid_y = top + band * (FRONT_EYE if front else SIDE_EYE)
    half = x0 + (x1 - x0) * (0.4 if right else 0.6)

    def light(x, y):                # 흰자 · 눈빛 (밝기만 보면 노랑 · 살구 같은 밝은 몸 색이 걸린다)
        return op(x, y) and min(px[x, y][:3]) >= 185

    def pair(blobs, cap):
        best, score = None, 1e9
        for i in range(len(blobs)):
            for j in range(i + 1, len(blobs)):
                a, c = sorted((blobs[i], blobs[j]), key=lambda t: t[0])
                dx = c[0] - a[0]
                if dx < 2.5 or dx > hw * 1.25 or abs(a[1] - c[1]) > 1.6:
                    continue
                if abs((a[0] + c[0]) / 2 - hx) > max(2.0, dx * 0.35):      # 입 줄을 가운데로 마주 본다
                    continue
                if max(abs(a[0] - hx), abs(c[0] - hx)) > hw * 0.72:        # 볼 · 수염 · 얼굴 가장자리는 아니다
                    continue
                sc = (abs(a[1] - c[1]) * 3 + abs((a[0] + c[0]) / 2 - hx) * 1.5
                      + abs((a[1] + c[1]) / 2 - mid_y) * 0.6 - min(a[3], c[3]) * cap)
                if sc < score:
                    best, score = [a, c], sc
        return best

    def side(blobs, wx):
        blobs = [b for b in blobs if (b[0] >= half if right else b[0] <= half)]
        blobs.sort(key=lambda t: (-t[0] if right else t[0]) * wx + abs(t[1] - mid_y) * 0.8 - t[3] * 0.1)
        return blobs[:1] or None

    # 1. 짙은 눈동자 + 흰 빛
    dark = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if op(x, y) and _lum(px[x, y]) < 70
            and all(op(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    lit = []
    for b in _blobs(dark):
        xs, ys = [q[0] for q in b], [q[1] for q in b]
        if len(b) > 16 or max(xs) - min(xs) > 4 or max(ys) - min(ys) > 5:
            continue
        n = len({(x + dx, y + dy) for (x, y) in b for dx in (-1, 0, 1) for dy in (-1, 0, 1) if light(x + dx, y + dy)})
        if n:
            lit.append(_center(b) + (b, n))
    # 2. 드문 색
    count, where = {}, {}
    for y in range(max(0, y0), min(H, y1)):          # 입 바로 위 줄까지
        for x in range(max(0, x0), min(W, x1 + 1)):
            if px[x, y][3]:
                k = px[x, y][:3]
                count[k] = count.get(k, 0) + 1
                where.setdefault(k, []).append((x, y))
    total = sum(count.values()) or 1
    rare = []
    for k, pts in where.items():
        if len(pts) > max(28, total * 0.08) or _lum(k) >= 200 or max(k) - min(k) < 40:
            continue                                  # 흰 · 회색 · 흔한 몸 색은 눈이 아니다
        for b in _blobs(pts):
            if _lum(k) >= 110 and not any(op(x + dx, y + dy) and _lum(px[x + dx, y + dy]) < 80
                                          for (x, y) in b for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue                              # 눈은 짙은 테두리에 붙어 있다 (색 자체가 짙으면 그것이 눈동자)
            if not front and len(b) > 16:
                continue
            rare.append(_center(b) + (b, 0))
    if front:
        a, b = pair(lit, 0.15), None
        groups = {}                                   # 드문 색 쌍은 같은 색끼리 (님피아: 눈과 같은 파랑이 리본에도)
        for e in rare:
            groups.setdefault(px[e[2][0]][:3], []).append(e)
        for g in groups.values():
            got = pair(g, 0)
            if got and (b is None or abs((got[0][1] + got[1][1]) / 2 - mid_y) < abs((b[0][1] + b[1][1]) / 2 - mid_y)):
                b = got
        pick = a or b
        if a and b and abs((b[0][1] + b[1][1]) / 2.0 - mid_y) + 1.0 < abs((a[0][1] + a[1][1]) / 2.0 - mid_y):
            pick = b                                  # 두 길이 다르면 예상 높이에 더 가까운 쪽
    else:
        a, b = side(lit, 0.3), side(rare, 0.1)
        pick = a or b
        if a and b and abs(b[0][1] - mid_y) + 1.0 < abs(a[0][1] - mid_y):
            pick = b
    return [_refine(cell, e) for e in (pick or [])]


def _refine(cell, eye):
    """찾은 눈 덩어리를 한 칸 넓혀(덩어리 색 · 짙은 색 · 흰자) 가운데를 다시 잡는다 (블래키: 살구 한 점 -> 빨간 눈).
    볼 · 몸 색으로는 안 퍼진다."""
    _cx, _cy, b = eye[:3]
    W, H = cell.size
    px = cell.load()
    own = set(px[q][:3] for q in b)
    pts = set(b)
    for (x, y) in b:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if 0 <= q[0] < W and 0 <= q[1] < H and px[q][3]:
                    col = px[q][:3]
                    if col in own or _lum(col) < 110 or min(col) >= 185:
                        pts.add(q)
    cx, cy = _center(list(pts))
    return cx, cy, list(pts)


def eye_points(cell, sp):
    """-> ([(촘촘 x, 촘촘 y)], 찾았나). 못 찾으면 예상 높이 · 간격. 등을 보이면 []."""
    if sp.face in BACK:
        return [], False
    ey = find_eyes(cell, sp)
    want = 2 if sp.face in FRONT else 1
    if len(ey) == want:
        return [(int(round(cx * S + S // 2)), int(round(cy * S + S // 2))) for cx, cy, _b in ey], True
    span = _run(sp.im, sp.hx, (sp.top + sp.hy) // 2) or (sp.hx - 16, sp.hx + 16)
    band = sp.hy - sp.top
    if sp.face in FRONT:
        y = int(round(sp.top + band * FRONT_EYE))
        half, mid = (span[1] - span[0]) * EYE_SEP / 2.0, (span[0] + span[1]) / 2.0
        return [(int(round(mid - half)), y), (int(round(mid + half)), y)], False
    y = int(round(sp.top + band * SIDE_EYE))
    row = _run(sp.im, sp.hx, y) or span
    return [(row[1] - 5 if sp.face in FACE_RIGHT else row[0] + 5, y)], False


# ---------------------------------------------------------------- 자리 고르기 (2.1.0)
def _over(big, it, xy, rows=None):
    """그림 칠한 칸 가운데 도트 위에 얹힌 몫 (0~1). rows 면 그 줄만."""
    W, H = big.size
    n = hit = 0
    for y in range(it.height):
        if rows is not None and y not in rows:
            continue
        for x in range(it.width):
            if it.getpixel((x, y))[3]:
                n += 1
                X, Y = xy[0] + x, xy[1] + y
                if 0 <= X < W and 0 <= Y < H and big.getpixel((X, Y))[3] > 0:
                    hit += 1
    return hit / float(n or 1)


def _covers(it, xy, eyes, r=2):
    for (ex, ey) in eyes:
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                x, y = ex + dx - xy[0], ey + dy - xy[1]
                if 0 <= x < it.width and 0 <= y < it.height and it.getpixel((x, y))[3]:
                    return True
    return False


def _lift(xy, it, eyes, gap=3):
    """아래 끝이 눈 가운데보다 gap 칸 위가 되게 올린다."""
    if not eyes:
        return xy
    return xy[0], min(xy[1], min(y for _x, y in eyes) - gap - it.height + 1)


def _crown_fit(big, it, xy, eyes, back=0, need=0.35):
    """관: 눈을 안 가리면서 아래 세 줄이 머리에 걸치는 가장 가까운 자리 (눈 위로 -> 옆모습은 뒤통수 쪽)."""
    rows = set(range(it.height - 3, it.height))
    up = _lift(xy, it, eyes)
    cand = [xy, up]
    for d in ((2, 4, 6, 8, 10) if back else ()):
        cand += [(xy[0] + back * d, xy[1]), (up[0] + back * d, up[1])]
    best, bf = up, -1
    for c in cand:
        if eyes and _covers(it, c, eyes):
            continue
        f = _over(big, it, c, rows)
        if f >= need:
            return c
        if f > bf:
            best, bf = c, f
    return best


def _settle(big, it, xy, eyes, back=1, need=0.5):
    """머리 장식: 눈을 안 가리고 절반 이상 머리에 얹히는 가장 가까운 자리 (처음 -> 뒤통수 쪽 -> 위 -> 안쪽)."""
    x0, y0 = xy
    cand = [xy] + [(x0 + back * d, y0) for d in (2, 4, 6, 8)]
    for d in (2, 4, 6):
        cand += [(x0, y0 - d), (x0 + back * d, y0 - d)]
    for d in (2, 4, 6):                                   # 작은 머리는 안쪽으로 (토게피 · 우파)
        cand += [(x0 - back * d, y0), (x0 - back * d, y0 + d // 2)]
    best, bf = None, -1
    for c in cand:
        if eyes and _covers(it, c, eyes):
            continue
        f = _over(big, it, c)
        if f >= need:
            return c
        if f > bf:
            best, bf = c, f
    return best or _lift(xy, it, eyes)


def _lens_fit(big, it, xy, face, need=0.8):
    """옆모습 렌즈가 코끝 밖으로 나오면 뒤로 한 칸씩 (3칸까지)."""
    if face in FRONT:
        return xy
    step = -1 if face in FACE_RIGHT else 1
    for i in range(4):
        c = (xy[0] + step * i, xy[1])
        if _over(big, it, c) >= need:
            return c
    return xy


def _body_fit(big, it, xy, cx, need=0.8):
    """넥타이가 몸 밖으로 삐지면 몸 가운데 쪽으로, 그래도 안 되면 위아래로 - 가장 많이 얹히는 자리."""
    x0, y0 = xy
    toward = 1 if cx > x0 + it.width / 2.0 else -1
    cand = [(x0 + toward * d, y0) for d in range(10)] + [(x0, y0 + d) for d in (1, 2, 3, -1, -2)]
    best, bf = xy, -1
    for c in cand:
        f = _over(big, it, c)
        if f >= need:
            return c
        if f > bf:
            best, bf = c, f
    return best


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


def _mask(im):
    """칠한 곳만 (255) - 메달은 가슴 테두리를 따라간다. 붐볼처럼 얼굴 무늬가 몸과 따로 움직이는 도트에서 무늬를
    따라가면 메달이 몸 밖으로 밀려났다 (0101 앞: 몸 3칸 · 메달 4칸)."""
    return im.split()[3].point(lambda v: 255 if v >= 128 else 0)


def shifts(cells, box, search=SEARCH, lum=True):
    """첫 칸의 box(원래 칸 좌표)를 다른 칸에서 찾아 이동량 [(dx, dy)] 을 준다 (첫 칸은 (0, 0)).

    **화면 스레드에서도 불린다** (처음 보는 동작) - 가볍게: 지난 칸의 이동량이 그대로 맞으면 바로 쓰고, 아니면 두 칸
    간격으로 훑은 뒤 그 둘레 한 칸만 다시 본다 (13x13 = 169 번 -> 49 + 8 번).
    """
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return [(0, 0)] * len(cells)
    look = _gray if lum else _mask
    ref = look(cells[0]).crop(box)
    out = [(0, 0)]
    prev = (0, 0)
    for im in cells[1:]:
        g = look(im)
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


# ---------------------------------------------------------------- 올림픽 메달 (2.3.0)
MEDAL_NEED = 0.9            # 메달 칠한 칸이 이만큼 넘게 몸 위에 - 허공 · 발치에 매달리지 않게
GUESS_CHIN = 0.55           # 위치 점이 없을 때 턱 = 그림 꼭대기에서 몸 높이의 이만큼 아래
MEDAL_DROP = 6              # 메달 위 = 끈 끝(턱 아래)에서 이만큼 아래 (메달 그림 칸 - 진주 목걸이 · 처음 메달과 같은 깊이)
STRAP_NEED = 0.85           # 끈도 몸 위에 (두 끝이 목 양옆에 붙는다)


def _alpha(big):
    W, H = big.size
    return big.split()[3].tobytes(), W, H


def _dots(it, a):
    """그림의 칠한 칸 가운데 점들 - 화면에서 그림 한 칸 = a 촘촘한 칸."""
    return [((u + 0.5) * a, (v + 0.5) * a) for v in range(it.height) for u in range(it.width)
            if it.getpixel((u, v))[3]]


def _hit(al, x, y):
    a, W, H = al
    x, y = int(x), int(y)
    return 0 <= x < W and 0 <= y < H and a[y * W + x] > 0


def _seg_on(al, p, q, n=8):
    """선분 p-q 위 점들 가운데 몸 위에 있는 몫."""
    pts = [(p[0] + (q[0] - p[0]) * i / float(n), p[1] + (q[1] - p[1]) * i / float(n)) for i in range(n + 1)]
    return sum(1 for x, y in pts if _hit(al, x, y)) / float(len(pts))


def _covers_at(it, xy, eyes, a, r=1):
    """_covers 와 같되 그림 한 칸 = a 촘촘한 칸 (화면 크기로 잰다)."""
    for (ex, ey) in eyes:
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                u, v = int((ex + dx - xy[0]) // a), int((ey + dy - xy[1]) // a)
                if 0 <= u < it.width and 0 <= v < it.height and it.getpixel((u, v))[3]:
                    return True
    return False


def _medal_place(big, sp, eyes, face, metal, a=1.0, guessed=False):
    """메달과 끈 -> ([(끈, x, y), (메달, x, y)], 걸을 때 이동량을 잴 상자(원래 칸)).

    모양은 목걸이 그대로 (진주 목걸이 · 처음 메달과 같은 자리): **끈 두 끝은 목 양옆, 턱 바로 아래 줄**에서 넓고 얕은
    V 로 내려와 가슴의 메달에 모인다 (옆모습은 뒷목에서 한 줄). 끈이 턱 위 얼굴로 올라가면 빨간 입처럼 보인다
    (11/08 사용자 '더 이상하다').

    메달: 끈 끝에서 DROP 만큼 아래가 처음 자리. **화면에 실제로 그려질 크기(a)로** 재서 97%(안 되면 90%) 넘게 몸 위에
    얹히고 눈을 안 가리는 가장 가까운 자리 - 몸이 짧으면 턱 쪽(위)으로 먼저 올린다. 메달 그림 한 칸 = a 촘촘한 칸
    (큰 도트를 줄여 그려도 장식은 1픽셀 아래로 안 줄어 커진다)."""
    al = _alpha(big)
    abytes, W, H = al
    it = ART.medal(metal)
    w, h = it.width * a, it.height * a
    offs = [(int(u), int(v)) for u, v in _dots(it, a)]           # 자리가 정수라 floor(x + u) = x + floor(u)
    f = 0 if face in FRONT else (1 if face in FACE_RIGHT else -1)
    nx, ny, half = sp.neck()
    ax = nx if f == 0 else sp.hx + (sp.cx - sp.hx) * 0.35       # 옆: 턱에서 몸 쪽으로 조금
    ey = max([y for _x, y in eyes] or [sp.top])
    chin = sp.hy
    bb = big.getbbox()
    if guessed and bb:                    # 위치 점이 없어 머리 점이 어림(그림 위 40%) - 그 둘레에서 찾은 '눈' 도 귀 끝 ·
        chin = max(chin, bb[1] + (bb[3] - bb[1]) * GUESS_CHIN)   # 이마이기 일쑤라 턱은 몸 높이로 (피카츄 · 잠만보 · 루카리오)
    end_y = int(round(chin + 1))                                 # 끈 두 끝 높이 = 턱 바로 아래 (목)
    x00, y00 = int(round(ax - w / 2.0)), int(max(end_y + MEDAL_DROP * a, ey + 4))
    cands = []
    for dy in range(-14, 21):
        for dx in range(-14, 15):
            back = (dx * f < 0) if f else True
            cost = (-dy if dy < 0 else 1.5 * dy) + abs(dx) * (1.0 if back else 2.0)   # 몸이 짧으면 위(턱 쪽)로 먼저
            cands.append((cost, x00 + dx, y00 + dy))
    cands.sort()
    seen = {}

    def on_at(x, y):
        got = seen.get((x, y))
        if got is None:
            hit = 0
            for u, v in offs:
                X, Y = x + u, y + v
                if 0 <= X < W and 0 <= Y < H and abytes[Y * W + X]:
                    hit += 1
            got = seen[(x, y)] = hit / float(len(offs))
        return got

    def first(need, gap):
        for cost, x, y in cands:
            if eyes and any(x - gap <= ex <= x + w + gap and y - gap <= ey_ <= y + h + gap for ex, ey_ in eyes):
                continue
            if on_at(x, y) >= need:
                return cost, x, y
        return None
    # 거의 다(97%) 몸 위인 자리가 '90% 자리' 보다 조금(4칸)만 멀면 그쪽 - 가장자리에서 삐져나온 메달이 안 보이게
    pick = None
    for gap in (2, 0):                    # 눈과 두 칸 띄워서 -> 안 되면(붐볼처럼 눈 아래가 좁다) 눈 사이 · 옆도
        p90, p97 = first(MEDAL_NEED, gap), first(0.97, gap)
        if p90:
            pick = p97 if p97 and p97[0] <= p90[0] + 4 else p90
            break
    if pick is None:                      # 어디도 90% 가 안 된다 - 가장 많이 얹히는 자리
        pick = max(((on_at(x, y), -cost, x, y) for cost, x, y in cands
                    if not (eyes and any(x <= ex <= x + w and y <= ey_ <= y + h for ex, ey_ in eyes))),
                   default=(0, 0, x00, y00))[1:]
    x, y = pick[1], pick[2]
    hx_, hy_ = int(round(x + w / 2.0)), y                        # 고리 = 메달 위 가운데
    # 끈: 두 끝은 목 양옆(턱 바로 아래 줄)에 붙박고, 목 폭에서 시작해 몸 위 · 눈을 안 가리는 데까지 좁힌다
    ty = min(end_y, hy_ - 2)              # 메달이 턱까지 올라온 몸(붐볼)은 끈이 거의 수평
    mid = nx if f == 0 and abs(hx_ - nx) <= half / 2.0 else hx_
    # 반폭은 목 폭까지 - 다만 메달이 끈 끝 가까이 올라온 몸(가는 다리 · 짧은 가슴)은 높이의 2.5배까지만 (넓고 납작한
    # 끈은 허리띠처럼 보인다)
    s_hi = max(w / 2.0 + 2 * a, min(half, 2.5 * max(0, hy_ - ty)))
    spick = None
    for down in (0, 1, 2):
        sp_ = s_hi
        while sp_ >= w / 2.0 + a * 0.5 - 1e-9:
            if f == 0:
                fe = [(mid - sp_, ty + down), (mid + sp_, ty + down)]
            else:
                fe = [(hx_ - f * sp_, ty + down)]
            on = min(_seg_on(al, e, (hx_, hy_ + a)) for e in fe)
            rel = [(int(round((e[0] - hx_) / a)), int(round((e[1] - hy_) / a))) for e in fe]
            pts = (rel[0], (0, 0), rel[1]) if f == 0 else (rel[0], (0, 0))
            st, sx, sy = ART.strap(pts)
            ok = on >= STRAP_NEED and all(_hit(al, *e) for e in fe) and not _covers_at(
                st, (hx_ + sx * a, hy_ + sy * a), eyes, a)
            if spick is None or (ok, on, sp_) > (spick[0], spick[1], spick[2]):
                spick = (ok, on, sp_, st, sx, sy)
            if ok:
                break
            sp_ -= 1
        if spick and spick[0]:
            break
    _ok, _on, _sp, st, sx, sy = spick
    draws = [(st, int(round(hx_ + sx * a)), int(round(hy_ + sy * a))), (it, x, y)]
    x0 = min(hx_ + sx * a, hx_ - w / 2.0)
    x1 = max(hx_ + (sx + st.width) * a, hx_ + w / 2.0)
    y0b, y1 = hy_ + sy * a, hy_ + h
    for yy in range(int(y0b), int(y1) + 1, S):  # 걸을 때 이동량은 그 줄들의 몸 폭 전체로 잰다 - 테두리가 붙잡아
        run = _run(big, hx_, yy)                # 표정(눈 · 입)만 바뀐 프레임에서 메달이 옆으로 튀지 않게
        if run:
            x0, x1 = min(x0, run[0]), max(x1, run[1] + 1)
    cw, ch = big.width // S, big.height // S
    box = (max(0, int(x0 // S) - 1), max(0, int(y0b // S) - 1), min(cw, int(x1 // S) + 2), min(ch, int(y1 // S) + 2))
    return draws, box


def _medal_follow(cells, medal, a, box, hsh):
    """걸을 때 메달 이동량 (촘촘한 칸, 프레임마다).

    1. 메달 둘레 몸 테두리(칠한 곳)를 첫 프레임과 맞댄 이동량 - 붐볼처럼 얼굴 무늬가 몸과 따로 움직여도 몸을 따른다
    2. 그게 머리 이동량과 2칸 넘게 다르면 머리를 따른다 - 끈은 목에 걸렸으니 머리에서 멀리 못 간다 (다리 · 꼬리가
       테두리를 바꾼 프레임에서 메달이 6칸씩 튀던 것)
    3. 그래도 그 프레임에서 메달이 90% 아래로 몸 위면 가장 가까운(아래 · 옆 먼저) 몸 위 자리로 조금 옮긴다"""
    it, x, y = medal
    offs = [(int(u), int(v)) for u, v in _dots(it, a)]
    msh = shifts(cells, box, lum=False)
    msh = [m if abs(m[0] - h[0]) <= 2 and abs(m[1] - h[1]) <= 2 else h for m, h in zip(msh, hsh)]
    near = sorted(((abs(dx) + (1.5 * -dy if dy < 0 else dy), dx, dy) for dx in range(-12, 13) for dy in range(-12, 11)))
    out = []
    for c, m in zip(cells, msh):
        abytes, W, H = _alpha(c.resize((c.width * S, c.height * S), Image.NEAREST))
        bx, by = x + m[0] * S, y + m[1] * S

        def on(px, py):
            hit = 0
            for u, v in offs:
                X, Y = px + u, py + v
                if 0 <= X < W and 0 <= Y < H and abytes[Y * W + X]:
                    hit += 1
            return hit / float(len(offs))
        got = (m[0] * S, m[1] * S)
        if on(bx, by) < MEDAL_NEED:
            for _cost, dx, dy in near:
                if on(bx + dx, by + dy) >= MEDAL_NEED:
                    got = (got[0] + dx, got[1] + dy)
                    break
        out.append(got)
    return out


# ---------------------------------------------------------------- 한 방향
def plan(cells, heads, centers, face, items, apx=1.0):
    """한 방향의 원래 칸들 -> 프레임마다 그릴 것 [[(그림, 촘촘x, 촘촘y)] ...] 과 왕관 자리 [(x, y, 폭) 또는 None].

    apx = 장식 그림 한 칸이 화면에서 차지하는 촘촘한 칸 수 (decorate 가 배율로 셈 - 큰 도트를 줄여 그리면 1 보다 크다).
    지금은 메달만 이 값으로 잰다 (끈 두 끝이 몸에 붙어야 해서)."""
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
    eyes = []
    if face not in BACK:
        eyes, _found = eye_points(c0, sp)
    head_draws, neck_draws = [], []
    crown_at = None
    has_crown = any(k in CROWNS or k in HEADS for k in items)
    back = -sp.side() if face not in FRONT else 0          # 뒤통수 쪽 (+1 = 화면 오른쪽)
    for k in items:
        if k in CROWNS or k in HEADS:
            c = ART.crown(CROWNS[k]) if k in CROWNS else ART.flower_crown()
            x, y = sp.crown(c)
            x, y = _crown_fit(big, c, (x, y + (1 if k in HEADS else 0)), eyes, back=back)
            head_draws.append((c, x, y))
            if k in CROWNS:
                crown_at = (x, y, c.width)
    for k in items:
        if k in HAIR:
            art = {"bow": ART.bow, "flower": ART.flower_pin, "star_pin": ART.star_pin}[k]()
            if sp.side() < 0:
                art = art.transpose(Image.FLIP_LEFT_RIGHT)
            x, y = sp.hair(art, low=6 if has_crown else 0)
            if has_crown:
                x += 3 if sp.side() > 0 else -3
            x, y = _settle(big, art, (x, y), eyes, back=back or 1)
            head_draws.append((art, x, y))
    for k in items:
        if k in FACE and face not in BACK and eyes:
            if face in FRONT and len(eyes) == 2:
                (ax, ay), (bx, by) = sorted(eyes)
                im, cx, ey = ART.glasses(k, bx - ax)
                xy = (ax - cx, (ay + by) // 2 - ey)
            else:
                im, cx, ey = ART.glasses(k, None, face in FACE_RIGHT)
                xy = (eyes[0][0] - cx, eyes[0][1] - ey)
            head_draws.append((im, ) + _lens_fit(big, im, xy, face))
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
    if "bowtie" in items and face not in BACK:
        nx, ny, half = sp.neck()
        it = ART.bowtie()
        top = sp.hy + 4 - it.height // 2                 # 매듭(가운데)이 입 줄 두 칸 아래
        bb = big.getbbox()
        if bb:
            top = min(top, bb[3] - it.height - 2)          # 몸 바닥 밖으로 처지지 않게
        if eyes:
            top = max(top, max(y for _x, y in eyes) + 3)    # 눈 아래로
        neck_draws.append((it, ) + _body_fit(big, it, (nx - it.width // 2, top), sp.cx))
    medal_draws, medal_box = [], None
    for k in items:
        if k in MEDALS and face not in BACK:
            medal_draws, medal_box = _medal_place(big, sp, eyes, face, MEDALS[k], apx,
                                                  guessed=not (heads and heads[0]))
    if neck_draws and n > 1:
        nx, ny, half = sp.neck()
        box = (max(0, (nx - half) // S - 1), max(0, (ny - 4) // S), (nx + half) // S + 2, (ny + 7) // S + 1)
        nsh = shifts(cells, box)
    moff = [(0, 0)] * n
    if medal_draws and n > 1:
        moff = _medal_follow(cells, medal_draws[-1], apx, medal_box, hsh)
    frames, crowns = [], []
    for i in range(n):
        hx, hy = hsh[i][0] * S, hsh[i][1] * S
        nx_, ny_ = nsh[i][0] * S, nsh[i][1] * S
        mx_, my_ = moff[i]
        frames.append([(im, x + nx_, y + ny_) for im, x, y in neck_draws]
                      + [(im, x + mx_, y + my_) for im, x, y in medal_draws]
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
    apx = k * float(S) / scale if scale else 1.0             # 그림 한 칸 = 화면에서 촘촘한 칸 몇 개
    for d, fs in frames.items():
        heads, centers = points.get(d) or (None, None)
        draws, crowns = plan(cuts[d], heads, centers, faces[d], items, apx)
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
