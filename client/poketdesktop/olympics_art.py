# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 중계 그림 (경기장 · 자막 · 전광판 · 결과판 · 시상대 · 소품).

**유리판** (11/07 사용자 '너무 크고 색이 강렬해서 띄워놓기 민망' → 시안 A 고름, '폭은 꽉 써도 괜찮아 높이만 신경써줘').
경기장은 Dock 처럼 어두운 판 하나 - 창 투명도(VENUE_ALPHA)로 바탕화면이 비친다. 그 위에 흰 선만 (레인 · 출발선 · 결승선 ·
언덕 윤곽). 관중석 · 광고판 · 하늘 그림은 없다. 높이는 130~190pt, 폭은 화면 폭을 쓴다. 카드(자막 · 전광판 · 결과판)도
같은 어두운 유리 (CARD_ALPHA), 글자는 Galmuri11 1배 (pt). 내 선수만 금빛.

경기장 선은 **1pt 로 그린다** (도트 2pt 와 결이 달라 '판 위 무대' 로 읽힌다). 소품(스키 · 썰매 · 장대 · 활 · 원반 · 메달)은
지금처럼 도트 배율 S 로 그린다. 창은 투명색 하나로 오린다 (keyed) - 반투명은 창 투명도 하나로 (맥 · 윈도우 같게).

    v = venue("sprint", W, S)        v.img (pt RGBA) · v.geo (pt, 경기장 왼쪽 위 기준)
        geo 공통: "card" = 자막 놓을 귀퉁이 ('tl' 'tr' 'bl' 'br') · "lineup" = 출전식 줄 (x1, x2, 발 y)
    lower_third(...) · board(...) · results_board(...) · podium(S) · target_face(...)
    skis(...) · sled(...) · pole_stick(...) · bow(...) · arrow(...) · disc(...) · puff(...) · flag_pin(...) · medal(...)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GALMURI = os.path.join(HERE, "fonts", "Galmuri11.ttf")
KEY = (255, 0, 255)

# ---------------------------------------------------------------- 빛깔 (유리판)
GLASS = (14, 19, 30)            # 판
GLASS_HI = (40, 50, 70)         # 판 위 밝은 면 (언덕 · 매트 · 얼음길)
L_HI = (246, 248, 252)          # 중요한 선 (출발 · 결승 · 바깥 줄 · 언덕 윤곽)
L_MID = (166, 178, 198)         # 보통 선
L_LO = (84, 96, 118)            # 흐린 선 (레인 사이 · 눈금)
TXT, TXT_DIM = (238, 242, 248), (150, 162, 184)
ACC = (240, 196, 104)           # 금빛 (내 선수 · 종목 이름)
COOL = (140, 172, 222)          # 보통 선수 표시
VENUE_ALPHA = 0.62              # 경기장 창 투명도 (바탕화면이 비친다)
CARD_ALPHA = 0.92               # 자막 · 전광판 · 결과판

# 소품 빛깔 (도트)
LINE = (247, 244, 236)
NAVY = (27, 42, 107)
GOLD, GOLD_D = (242, 183, 5), (196, 140, 0)
SILVER, BRONZE = (196, 204, 216), (205, 127, 50)
INK = (24, 26, 40)
STEEL, STEEL_D = (150, 160, 172), (96, 104, 116)
RED = (215, 38, 61)
SKI, SKI_D = (238, 124, 52), (96, 44, 12)
MEDAL = {1: GOLD, 2: SILVER, 3: BRONZE}


def scale_of(th):
    """포켓몬 높이(targetHeight)에 맞춘 픽셀 배율 - 소품을 도트와 같은 굵기로 (64 -> 2)."""
    return max(1, min(4, int(round(float(th or 64) / 32.0))))


# ---------------------------------------------------------------- 글자 · 오리기
_fonts = {}


def _font(px):
    f = _fonts.get(px)
    if f is None:
        try:
            f = ImageFont.truetype(GALMURI, px)
        except Exception:                                   # noqa: BLE001
            f = ImageFont.load_default()
        _fonts[px] = f
    return f


def text_img(text, color, px=12, scale=1, shadow=None):
    """픽셀 글자 한 줄 (안티에일리어싱 없이) -> scale 배."""
    f = _font(px)
    l, t, r, b = f.getbbox(text or " ")
    w, h = max(1, r - l + 2), max(1, b - t + 2)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    if shadow:
        d.text((1 - l, 1 - t), text, font=f, fill=shadow)
    d.text((-l, -t), text, font=f, fill=color)
    if scale != 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    return im


def up(im, k):
    return im if k == 1 else im.resize((im.width * k, im.height * k), Image.NEAREST)


def keyed(img):
    """창에 올릴 그림: 알파 128 아래는 투명색(KEY), 나머지는 그 색 그대로 (빠른 길 - 경기장처럼 큰 그림)."""
    img = img.convert("RGBA")
    mask = img.split()[3].point(lambda a: 255 if a >= 128 else 0)
    out = Image.new("RGB", img.size, KEY)
    out.paste(img.convert("RGB"), (0, 0), mask)
    return out


class Venue(object):
    def __init__(self, img, geo):
        self.img = img
        self.geo = geo
        self.w, self.h = img.size


def _panel(W, H, r=10):
    """둥근 유리판 (바깥 귀퉁이는 투명)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), r, fill=GLASS + (255,), outline=L_LO + (255,))
    return im, d


def _label(im, t, x, y, color=L_MID, px=8, anchor="mm"):
    """작은 글 (anchor: 'mm' 가운데 · 'lm' 왼쪽 · 'rm' 오른쪽)."""
    ti = text_img(t, color, px)
    if anchor[0] == "m":
        x -= ti.width / 2.0
    elif anchor[0] == "r":
        x -= ti.width
    im.alpha_composite(ti, (int(x), int(y - ti.height / 2.0)))


def _dotted(d, x1, y1, x2, y2, color, on=2, off=3):
    n = int(max(abs(x2 - x1), abs(y2 - y1)))
    for k in range(0, n, on + off):
        for j in range(on):
            u = min(1.0, (k + j) / float(max(1, n)))
            d.point((x1 + (x2 - x1) * u, y1 + (y2 - y1) * u), fill=color)


def _spline(ctrl, n):
    """캣멀롬 곡선 점 n 개."""
    pts = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    segs = len(ctrl) - 1
    for i in range(segs):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        m = max(2, n // segs)
        for k in range(m):
            t = k / float(m)
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(ctrl[-1])
    return out


def _loop_points(l, t, r, b, rad):
    """둥근 네모 둘레를 (아래쪽 왼쪽에서 오른쪽으로) 1pt 간격 점들."""
    pts = []

    def arc(cx, cy, a0, a1):
        n = max(4, int(abs(a1 - a0) * rad))
        for k in range(n):
            a = a0 + (a1 - a0) * k / float(n)
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    for x in range(l + rad, r - rad):
        pts.append((x, b))
    arc(r - rad, b - rad, math.pi / 2, 0)
    for y in range(b - rad, t + rad, -1):
        pts.append((r, y))
    arc(r - rad, t + rad, 0, -math.pi / 2)
    for x in range(r - rad, l + rad, -1):
        pts.append((x, t))
    arc(l + rad, t + rad, -math.pi / 2, -math.pi)
    for y in range(t + rad, b - rad):
        pts.append((l, y))
    arc(l + rad, b - rad, math.pi, math.pi / 2)
    return [(int(round(x)), int(round(y))) for x, y in pts]


def _span(S, n=8):
    """출전식 줄 길이 (선수 n 마리, 도트 배율 S)."""
    return n * 30 * S


# ---------------------------------------------------------------- 100m (레인 8, 비스듬한 출발선)
LANE_H = 16
SLANT = 0.85


def _sprint(W, S):
    lanes = 8
    top = 10
    bottom = top + LANE_H * lanes
    H = bottom + 12
    im, d = _panel(W, H)

    def sx(x0, yy):
        return x0 + (bottom - yy) * SLANT
    start_b = 34
    finish_b = W - 150 - int((bottom - top) * SLANT)
    for i in range(lanes + 1):
        y = top + i * LANE_H
        d.line((10, y, W - 11, y), fill=(L_MID if i in (0, lanes) else L_LO) + (255,))
    for yy in range(top + 1, bottom):
        d.point((sx(start_b, yy), yy), fill=L_HI + (255,))
        fx = int(sx(finish_b, yy))
        for k in range(3):
            d.point((fx + k, yy), fill=(L_HI if ((yy // 2) + k) % 2 == 0 else L_LO) + (255,))
    for m in range(10, 100, 10):                    # 10m 눈금 (위 · 아래 바깥 줄)
        x0 = start_b + (finish_b - start_b) * m / 100.0
        d.line((sx(x0, top), top - 3, sx(x0, top), top), fill=L_LO + (255,))
        d.line((sx(x0, bottom), bottom, sx(x0, bottom), bottom + 3), fill=L_LO + (255,))
    lane_geo = {}
    for i in range(lanes):
        lane = lanes - i
        y1, y2 = top + i * LANE_H, top + (i + 1) * LANE_H
        cy = (y1 + y2) / 2.0
        _label(im, str(lane), sx(start_b + 7, cy), cy, L_MID, 8)
        foot = y1 + LANE_H * 0.80
        lane_geo[lane] = {"y": foot, "y1": y1, "y2": y2, "start": sx(start_b - 10, foot),
                          "finish": sx(finish_b, foot), "after": sx(finish_b + 22, foot), "enter": sx(-30, foot)}
    return Venue(im, {"lanes": lane_geo, "apron": bottom + 4, "top": 0, "bottom": H, "card": "br"})


# ---------------------------------------------------------------- 마라톤 (공원 둘레 길, 위에서 본 모습)
def _marathon(W, S):
    H = 150
    im, d = _panel(W, H)
    l, t, r, b = 30, 34, W - 30, H - 26
    rad = (b - t) // 2
    path = _loop_points(l, t, r, b, rad)
    d.line(path + [path[0]], fill=L_MID + (255,), width=11, joint="curve")      # 길 가장자리
    d.line(path + [path[0]], fill=GLASS_HI + (255,), width=9, joint="curve")   # 길
    for i, (px, py) in enumerate(path):
        if (i // 6) % 2 == 0:
            d.point((px, py), fill=L_LO + (255,))
    # 출발 · 결승 (아래 곧은 길 왼쪽)
    ax = l + rad + 60
    for yy in range(b - 4, b + 5):
        for k in range(3):
            d.point((ax + k, yy), fill=(L_HI if ((yy // 2) + k) % 2 == 0 else GLASS) + (255,))
    d.line((ax - 18, b - 22, ax - 18, b + 6), fill=L_MID + (255,))
    d.line((ax + 20, b - 22, ax + 20, b + 6), fill=L_MID + (255,))
    d.rectangle((ax - 20, b - 30, ax + 22, b - 20), fill=GLASS_HI + (255,), outline=L_MID + (255,))
    _label(im, "결승", ax + 1, b - 25, L_HI, 8)
    # km 표지 (두 바퀴 = 42.195km)
    n = len(path)
    start_i = min(range(n), key=lambda i: abs(path[i][0] - (ax + 1)) + abs(path[i][1] - b) * 3)
    for km1, km2 in ((7, 28), (14, 35)):                       # 두 바퀴라 같은 자리에 둘
        frac = (km1 / 42.195 * 2) % 1.0
        px, py = path[(start_i + int(frac * n)) % n]
        cy = (t + b) / 2.0
        oy = -12 if py < cy else (12 if py > cy else 0)
        ox = -22 if (oy == 0 and px < W / 2) else (22 if oy == 0 else 0)
        _label(im, "%dk · %dk" % (km1, km2), px + ox, py + oy, L_MID, 8)
    _label(im, "반환", path[(start_i + n // 2) % n][0], path[(start_i + n // 2) % n][1] - 12, L_MID, 8)
    pts = path[start_i:] + path[:start_i]
    return Venue(im, {"path": [(float(x), float(y)) for x, y in pts], "finish": (ax + 1, b), "rest_y": b + 2,
                      "top": 0, "bottom": H, "card": "br"})


# ---------------------------------------------------------------- 봅슬레이 (얼음 트랙, 옆에서 본 내리막)
def _bobsled(W, S):
    H = 160
    im, d = _panel(W, H)
    ctrl = [(54, 30), (W * 0.18, 32), (W * 0.27, 62), (W * 0.40, 70), (W * 0.50, 66), (W * 0.58, 98),
            (W * 0.72, 106), (W * 0.82, 100), (W * 0.90, 122), (W - 44, 128)]
    path = _spline(ctrl, 1400)
    d.line(path, fill=L_MID + (255,), width=11, joint="curve")             # 벽
    d.line(path, fill=GLASS_HI + (255,), width=8, joint="curve")           # 얼음
    d.line([(x, y + 3) for x, y in path], fill=L_LO + (255,))
    sx, sy = path[0]
    d.rectangle((sx - 34, sy - 18, sx - 8, sy + 4), fill=GLASS_HI + (255,), outline=L_MID + (255,))
    _label(im, "출발", sx - 21, sy - 7, L_HI, 8)
    checks = [0.30, 0.58, 0.82]
    for k, u in enumerate(checks, 1):
        px, py = path[int(u * (len(path) - 1))]
        d.line((px, py - 16, px, py - 7), fill=L_MID + (255,))
        d.rectangle((px - 5, py - 24, px + 5, py - 16), fill=GLASS_HI + (255,), outline=L_MID + (255,))
        _label(im, str(k), px, py - 20, L_HI, 8)
    fx, fy = path[-1]
    for yy in range(int(fy) - 7, int(fy) + 7):
        for k in range(3):
            d.point((fx + 2 + k, yy), fill=(L_HI if ((yy // 2) + k) % 2 == 0 else GLASS) + (255,))
    _label(im, "결승", fx + 4, fy - 15, L_MID, 8)
    return Venue(im, {"path": path, "checks": checks, "rest_y": H - 12, "top": 0, "bottom": H, "card": "tr",
                      "lineup": (18, min(W * 0.36, 18 + _span(S)), H - 12)})


# ---------------------------------------------------------------- 장대높이뛰기 (옆에서)
def _pole(W, S):
    H = 172
    ground = H - 24
    im, d = _panel(W, H)
    box_x = int(W * 0.60)
    bar_x = box_x + 24
    run0 = 40
    d.rectangle((24, ground - 3, box_x, ground + 3), fill=GLASS_HI + (255,))
    d.line((24, ground - 3, box_x, ground - 3), fill=L_MID + (255,))
    d.line((24, ground + 3, box_x, ground + 3), fill=L_MID + (255,))
    d.line((14, ground + 4, W - 15, ground + 4), fill=L_LO + (255,))                   # 땅
    d.polygon([(box_x - 10, ground - 3), (box_x, ground + 3), (box_x, ground - 3)], fill=L_HI + (255,))
    for m in (5, 10, 20, 30):                                                        # 박스까지 거리
        x = box_x - 10 - m * (box_x - run0 - 30) / 32.0
        d.line((x, ground + 4, x, ground + 8), fill=L_MID + (255,))
        _label(im, "%dm" % m, x, ground + 14, L_MID, 8)
    top_y, low_y = 22, ground - 64
    for sx_ in (bar_x - 13 * S, bar_x + 13 * S):                                     # 지주 둘
        d.line((sx_, top_y - 4, sx_, ground), fill=L_MID + (255,))
        for yy in range(int(top_y), int(ground) - 4, 10):
            d.point((sx_ + 1, yy), fill=L_LO + (255,))
    mx1, mx2 = bar_x - 8, bar_x + 74
    mat_top = ground - 14
    d.rounded_rectangle((mx1, mat_top, mx2, ground + 3), 3, fill=GLASS_HI + (255,), outline=L_MID + (255,))
    _label(im, "POKET", (mx1 + mx2) / 2.0, mat_top + 8, L_LO, 8)
    hb = (bar_x + 13 * S + 8, top_y - 6, 44, 14)                                     # 높이 표 (글은 중계가 쓴다)
    d.rectangle((hb[0], hb[1], hb[0] + hb[2], hb[1] + hb[3]), fill=GLASS_HI + (255,), outline=L_MID + (255,))
    span = _span(S)
    return Venue(im, {"ground": ground, "run0": run0, "box": box_x, "bar_x": bar_x, "bar_top": top_y + 4,
                      "bar_low": low_y, "mat": (mx1, mx2), "mat_top": mat_top, "height_board": hb, "top": 0,
                      "bottom": H, "card": "tl",
                      "lineup": (int(W * 0.10), min(box_x - 70, int(W * 0.10) + span), ground - 40)})


# ---------------------------------------------------------------- 양궁 (옆에서: 사선 -> 과녁)
def target_face_img(r):
    """과녁 하나 (반지름 r): 흰 · 검 · 파 · 빨 · 노 (바깥에서 안으로)."""
    im = Image.new("RGBA", (r * 2 + 1, r * 2 + 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rings = [(226, 228, 232), (44, 46, 56), (70, 120, 196), (204, 70, 70), (238, 204, 72)]
    for k, col in enumerate(rings):
        rr = r - k * r / 5.0
        d.ellipse((r - rr, r - rr, r + rr, r + rr), fill=col)
    d.point((r, r), fill=INK)
    return im


def _archery(W, S):
    H = 136
    ground = H - 24
    im, d = _panel(W, H)
    shoot_x = int(W * 0.10)
    tx = W - 76
    d.line((14, ground, W - 15, ground), fill=L_MID + (255,))
    d.line((shoot_x, ground - 2, shoot_x - 4, ground + 12), fill=L_HI + (255,), width=2)          # 사선
    _label(im, "사선", shoot_x - 2, ground + 16, L_MID, 8)
    for m in (30, 50, 70):
        x = shoot_x + (tx - 30 - shoot_x) * m / 70.0
        _dotted(d, x, 20, x, ground, L_LO + (255,))
        _label(im, "%dm" % m, x, ground + 12, L_MID, 8)
    face_r = 12
    ty = ground - 30
    for k, dx in enumerate((-30, 0, 30)):                       # 과녁 셋 (가운데가 쓰는 것)
        cx = tx + dx
        r = face_r if dx == 0 else 10
        cy = ty if dx == 0 else ty + 4
        d.line((cx - 7, cy + r, cx - 11, ground), fill=L_MID + (255,))
        d.line((cx + 7, cy + r, cx + 11, ground), fill=L_MID + (255,))
        im.alpha_composite(target_face_img(r), (cx - r, int(cy - r)))
    return Venue(im, {"ground": ground, "shoot_x": shoot_x, "target": (tx, ty), "face_r": face_r, "top": 0,
                      "bottom": H, "card": "tl", "zoom": (tx - 54, 6),
                      "lineup": (int(W * 0.22), int(W * 0.22) + _span(S), ground)})


# ---------------------------------------------------------------- 원반던지기 (옆에서: 원 -> 부채꼴)
def _discus(W, S):
    H = 140
    ground = H - 24
    im, d = _panel(W, H)
    cx = 74

    def mx(m):
        return cx + 50 + (m - 20) * (W - cx - 120) / 55.0
    d.line((14, ground, W - 15, ground), fill=L_MID + (255,))
    for x in range(cx - 24, cx + 9, 6):                         # 그물 (뒤쪽)
        d.line((x, ground - 60, x, ground), fill=L_LO + (255,))
    for y in range(ground - 60, ground, 8):
        d.line((cx - 24, y, cx + 6, y), fill=L_LO + (255,))
    d.ellipse((cx - 12, ground - 3, cx + 12, ground + 3), outline=L_HI + (255,))
    for m in range(20, 80, 10):
        x = mx(m)
        d.line((x, ground, x, ground + 5), fill=L_MID + (255,))
        if m >= 30:
            _label(im, "%dm" % m, x, ground + 12, L_MID, 8)
        _dotted(d, x, ground - 2, x - 6, ground - 30, L_LO + (255,), 1, 3)
    return Venue(im, {"ground": ground, "circle": (cx, ground), "mx": mx, "top": 0, "bottom": H, "card": "tr",
                      "lineup": (cx + 120, min(W - 40, cx + 120 + _span(S)), ground)})


# ---------------------------------------------------------------- 스키점프 (옆에서 본 점프대)
SKI_W, SKI_H = 860, 252
GATE_I = 36                                            # 도움닫기 점 가운데 출발대 자리
SNOW_TOP, SNOW_BOT = (104, 122, 156), (54, 66, 92)     # 언덕 눈 (위가 밝다 - 판보다 밝아 언덕이 덩어리로 읽힌다)
RIDGE = (22, 30, 44)                                   # 먼 산 능선
TREE = (44, 58, 82)
DECK = (64, 78, 104)                                   # 도움닫기 상판
K_RED, HS_BLUE = (214, 104, 100), (112, 152, 214)
FLAG = (206, 172, 98)


def _spruce(d, x, base, h):
    """가문비나무 (유리판 결: 어두운 면 + 흐린 테두리)."""
    w = h * 0.36
    for k, (top, half) in enumerate(((base - h, w * 0.55), (base - h * 0.66, w * 0.8), (base - h * 0.36, w))):
        bottom = base - h * (0.42 - 0.28 * k) if k < 2 else base
        d.polygon([(x, top), (x - half, bottom), (x + half, bottom)], fill=TREE + (255,))
    d.line((x, base - h, x - w * 0.25, base - h * 0.62), fill=(70, 86, 112, 255))     # 눈 얹힌 쪽


def _ski(W, S):
    """스키점프 (11/07 사용자 '조금 더 높여주는데 디자인이 너무 별로야, 조금 더 신경써줘').

    화면 폭을 다 쓰면 착지 언덕이 납작해져 점프대로 안 보인다 - 경기장을 860 x 252pt 로 묶고 실제 점프대 비율로:
    왼쪽 위 출발 오두막 · 철골 탑 → 철골 위 35도 도움닫기(두 줄 레일) → 휘어 들어가는 전이 구간 → 살짝 내려가는
    도약대 → 볼록하다가 K점 앞에서 가장 가파른 착지 언덕(눈 그라데이션) → 평평한 브레이킹 트랙 · 펜스 · 심판탑.
    빛깔은 유리판 그대로(어두운 남색 단계 + 흰 선), 점만 K점 빨강 · HS 파랑 · 바람 깃발 금빛.
    """
    W = min(W, SKI_W)
    H = SKI_H
    base = H - 12
    im, d = _panel(W, H)

    # 먼 산 능선 (깊이)
    ridge = [(10, base)]
    for x in range(10, W - 9, 6):
        y = 132 - 26 * math.sin(x / 150.0 + 0.6) - 9 * math.sin(x / 47.0 + 1.3) + x * 0.02
        ridge.append((x, y))
    ridge.append((W - 10, base))
    d.polygon(ridge, fill=RIDGE + (255,))
    d.line(ridge[1:-1], fill=(40, 52, 72, 255))

    # 도움닫기: 출발대 -> 35도 곧은 길 -> 전이 곡선 -> 도약대 (살짝 내리막)
    gate = (64, 26)
    p1 = (150, 86)
    ctl = (184.2, 109.9)
    p2 = (206, 114)
    T = (238, 120)
    ramp = []
    n1 = 90
    for i in range(n1):
        u = i / float(n1)
        ramp.append((gate[0] + (p1[0] - gate[0]) * u, gate[1] + (p1[1] - gate[1]) * u))
    for i in range(60):
        u = i / 60.0
        ramp.append(((1 - u) ** 2 * p1[0] + 2 * (1 - u) * u * ctl[0] + u * u * p2[0],
                     (1 - u) ** 2 * p1[1] + 2 * (1 - u) * u * ctl[1] + u * u * p2[1]))
    for i in range(33):
        u = i / 32.0
        ramp.append((p2[0] + (T[0] - p2[0]) * u, p2[1] + (T[1] - p2[1]) * u))

    # 착지 언덕: 0m(도약대 밑) ~ 160m, 볼록 -> 가장 가파름 -> 브레이킹 트랙으로 펴짐
    x0, x1 = 232.0, 510.0
    y0, y1 = 132.0, base - 6.0

    def hill(m):
        u = max(0.0, min(1.0, m / 160.0))
        f = 0.5 - 0.5 * math.cos(math.pi * (u ** 0.85))
        return x0 + u * (x1 - x0), y0 + (y1 - y0) * f

    def out_y(x):
        """브레이킹 트랙: 평평하다가 끝에서 살짝 올라간다."""
        rise = max(0.0, x - (W - 120)) / 100.0
        return y1 - 7 * rise * rise

    def hill_y(x):
        """그 x 에서 눈 표면 높이 (도약대 앞 · 언덕 · 브레이킹 트랙)."""
        if x <= x0:
            return y0
        if x <= x1:
            return hill((x - x0) * 160.0 / (x1 - x0))[1]
        return out_y(x)
    prof = [hill(m) for m in range(0, 161)] + [(x, out_y(x)) for x in range(int(x1) + 1, W - 12)]

    # 철골 탑 (오두막 밑 기둥 둘 + 엑스자 버팀)
    tx1, tx2 = 38, 58
    d.line((tx1, 22, tx1, base), fill=L_LO + (255,))
    d.line((tx2, 22, tx2, base), fill=L_LO + (255,))
    for y in range(26, base - 16, 18):
        d.line((tx1, y, tx2, y + 18), fill=L_LO + (255,))
        d.line((tx2, y, tx1, y + 18), fill=L_LO + (255,))
    # 도움닫기 밑 철골: 다리 다섯 + 다리 사이 엑스 버팀
    legs = [ramp[i] for i in (18, 52, 88, 122, 158)]
    for k, (x, y) in enumerate(legs):
        d.line((x - 2, y + 8, x - 2, base), fill=L_LO + (255,))
        d.line((x + 2, y + 8, x + 2, base), fill=L_LO + (255,))
        if k:
            px, py = legs[k - 1]
            for yy in range(int(max(py, y)) + 14, base - 10, 26):
                d.line((px + 2, yy, x - 2, yy + 22), fill=L_LO + (255,))
                d.line((x - 2, yy, px + 2, yy + 22), fill=L_LO + (255,))

    # 언덕 눈 (그라데이션) - 도약대 밑에서 내려오는 앞면까지
    hill_poly = [(T[0] - 4, T[1] + 6)] + prof + [(W - 12, base + 1), (T[0] - 70, base + 1)]
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(hill_poly, fill=255)
    grad = Image.new("RGBA", (W, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        u = max(0.0, min(1.0, (y - 110) / float(base - 110)))
        gd.line((0, y, W, y), fill=tuple(int(a + (b - a) * u) for a, b in zip(SNOW_TOP, SNOW_BOT)) + (255,))
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    # 정설 자국 (언덕을 가로지르는 흐린 줄 - 눈 결)
    for m in range(6, 158, 5):
        x, y = hill(m)
        xa, ya = hill(m - 1)
        xb, yb = hill(m + 1)
        tx, ty = xb - xa, yb - ya
        nl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / nl, tx / nl
        d.line((x + nx * 3, y + ny * 3, x + nx * 9, y + ny * 9), fill=(92, 110, 142, 255))          # 거리 숫자는 그 아래
    # 조명탑 둘 (작은 금빛 등)
    for lx_, top in ((372, 84), (548, 118)):
        ly_ = hill_y(lx_)
        d.line((lx_, ly_, lx_, top), fill=L_LO + (255,))
        d.line((lx_ - 6, top, lx_ + 6, top), fill=L_MID + (255,))
        for k in (-5, -1, 3):
            d.rectangle((lx_ + k, top - 3, lx_ + k + 2, top - 1), fill=ACC + (255,))
    # 착지 구역 (80~135m) 표면 띠 · 눈 표면 선
    zone = [hill(m) for m in range(80, 136)]
    d.line([(x, y + 2) for x, y in zone], fill=(84, 102, 134, 255), width=3)
    d.line([(T[0] - 4, T[1] + 6)] + prof, fill=L_HI + (255,))

    # 거리 눈금 · 숫자 · K점(120) · HS(140)
    for m in range(50, 151, 10):
        x, y = hill(m)
        d.line((x, y + 2, x + 2, y + 6), fill=L_MID + (255,))
        if m % 20 == 0 and m != 120 and m != 140:
            _label(im, str(m), x + 4, y + 13, L_MID, 8)

    def mark(m, col, txt):
        x, y = hill(m)
        xa, ya = hill(m - 1)
        xb, yb = hill(m + 1)
        tx, ty = xb - xa, yb - ya
        nl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / nl, tx / nl                       # 표면에 수직
        d.line((x - nx * 7, y - ny * 7, x + nx * 9, y + ny * 9), fill=col + (255,), width=2)
        _label(im, txt, x + nx * 18 + 2, y + ny * 18, col, 8)
    mark(120, K_RED, "K 120")
    mark(140, HS_BLUE, "HS 140")

    # 바람 깃발 (언덕 옆 세 개)
    for m in (40, 75, 110):
        x, y = hill(m)
        d.line((x, y - 1, x, y - 15), fill=L_MID + (255,))
        d.polygon([(x + 1, y - 15), (x + 8, y - 13), (x + 1, y - 11)], fill=FLAG + (255,))

    # 도움닫기: 상판(두께 7pt, 법선 아래로) + 위에 레일 둘 · 출발 오두막 · 출발대
    def off(pts, dist):
        out = []
        for i, (x, y) in enumerate(pts):
            xa, ya = pts[max(0, i - 2)]
            xb, yb = pts[min(len(pts) - 1, i + 2)]
            tx, ty = xb - xa, yb - ya
            nl = math.hypot(tx, ty) or 1.0
            out.append((x - ty / nl * dist, y + tx / nl * dist))
        return out
    under = off(ramp, 7)
    d.polygon(ramp + under[::-1], fill=DECK + (255,))
    d.line(under, fill=L_MID + (255,))
    d.line(ramp, fill=L_HI + (255,))
    d.line(off(ramp, 2.5), fill=L_MID + (255,))
    d.line((T[0], T[1], under[-1][0], under[-1][1]), fill=L_HI + (255,))         # 도약대 끝
    d.rectangle((28, 8, 58, 22), fill=GLASS_HI + (255,), outline=L_MID + (255,))   # 오두막
    d.line((24, 8, 62, 8), fill=L_HI + (255,))                                     # 지붕
    d.rectangle((33, 12, 38, 17), outline=L_MID + (255,))
    d.rectangle((44, 12, 49, 17), outline=L_MID + (255,))
    # 출발대: 도움닫기 위쪽 3분의 1 (판 맨 위에서 출발하면 선수 머리가 판 밖 이름 띠를 가린다 - 11/07 시연)
    sx_, sy_ = ramp[GATE_I]
    d.line((sx_ - 5, sy_ - 3, sx_ + 7, sy_ - 3), fill=ACC + (255,), width=2)
    d.line((sx_ + 6, sy_ - 9, sx_ + 6, sy_ - 2), fill=ACC + (255,))

    # 심판탑 (브레이킹 트랙 옆)
    jx = 600
    d.line((jx, base, jx, 150), fill=L_LO + (255,))
    d.line((jx + 26, base, jx + 26, 150), fill=L_LO + (255,))
    for y in range(158, base - 8, 16):
        d.line((jx, y, jx + 26, y + 16), fill=L_LO + (255,))
    d.rectangle((jx - 6, 128, jx + 32, 150), fill=GLASS_HI + (255,), outline=L_MID + (255,))
    for k in range(4):
        d.rectangle((jx - 2 + k * 9, 133, jx + 4 + k * 9, 140), fill=(96, 116, 150, 255))
    d.line((jx - 9, 128, jx + 35, 128), fill=L_HI + (255,))

    # 브레이킹 트랙 펜스 (광고판)
    fx1, fx2 = 660, W - 22
    fy = base - 16
    d.rectangle((fx1, fy, fx2, fy + 9), fill=GLASS_HI + (255,), outline=L_MID + (255,))
    for x in range(fx1, fx2, 40):
        d.line((x, fy + 9, x, base - 2), fill=L_LO + (255,))
    _label(im, "POKET DESKTOP  ·  포스크탑 올림픽", (fx1 + fx2) / 2.0, fy + 5, L_MID, 8)

    # 나무
    for x, h in ((96, 30), (118, 22), (W - 40, 40), (W - 62, 26), (700, 20)):
        _spruce(d, x, base if x < 600 else fy - 1, h)

    return Venue(im, {"hill": hill, "hill_y": hill_y, "ramp": ramp[GATE_I:], "plat": ramp[GATE_I], "T": T,
                      "ground": base,
                      "top": 0, "bottom": H, "card": "tr", "lineup": (70, min(W - 40, 70 + _span(S)), base - 1)})


_BUILD = {"sprint": _sprint, "marathon": _marathon, "bobsled": _bobsled, "pole": _pole, "archery": _archery,
          "discus": _discus, "ski": _ski}


def venue(event, W, S=2):
    """종목 경기장 (유리판). W = 폭(pt). 그림과 기하 정보는 pt."""
    return _BUILD[event](max(480, int(W)), S)


# ---------------------------------------------------------------- 중계 카드 (유리, pt 1배 글자)
def _card(w, h, r=7):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(18, 22, 32, 255), outline=(66, 76, 98, 255))
    return im, d


def lower_third(num, owner, mon, sub, S=2, mine=False, label="레인", w=None):
    """선수 소개 자막: 왼쪽 번호(레인 · 순서) + '주인의 포켓몬' · 아래 줄. 내 선수면 금빛 줄 + '내 포켓몬'."""
    acc = ACC if mine else COOL
    n = text_img(str(num), acc, 12)
    lb = text_img(label, TXT_DIM, 8)
    l1 = text_img(owner + "의 ", TXT_DIM, 12)
    l2 = text_img(mon, TXT, 12)
    l3 = text_img(sub, TXT_DIM, 10)
    tag = text_img("내 포켓몬", (40, 32, 10), 8) if mine else None
    tw = max(l1.width + l2.width - 2 + (tag.width + 14 if tag else 0), l3.width)
    w = w or (36 + tw + 14)
    h = 36
    im, d = _card(w, h)
    d.rectangle((5, 6, 6, h - 7), fill=acc)
    nx = 13 + (18 - max(n.width, lb.width)) // 2
    im.alpha_composite(n, (nx + (max(n.width, lb.width) - n.width) // 2, 5))
    im.alpha_composite(lb, (nx + (max(n.width, lb.width) - lb.width) // 2, 22))
    im.alpha_composite(l1, (36, 5))
    im.alpha_composite(l2, (36 + l1.width - 2, 5))
    im.alpha_composite(l3, (36, 21))
    if tag is not None:
        d.rounded_rectangle((w - tag.width - 14, 6, w - 6, 8 + tag.height), 3, fill=acc)
        im.alpha_composite(tag, (w - tag.width - 10, 7))
    return im


def board(lines, w=0, colors=None):
    """전광판 (유리 칩): 첫 줄 종목 · 조 (금빛 12), 다음 줄들 (흰 10)."""
    rows = []
    for i, t in enumerate(lines):
        col = (colors or {}).get(i) or (ACC if i == 0 else TXT)
        rows.append(text_img(t, col, 12 if i == 0 else 10))
    w = max(w, max([r.width for r in rows] or [0]) + 20)
    h = 8 + sum(r.height + 3 for r in rows) + 4
    im, d = _card(w, h)
    y = 6
    for r in rows:
        im.alpha_composite(r, (10, y))
        y += r.height + 3
    return im


def results_board(title, rows, S=2, w=None):
    """결과판: [(순위, 이름, 기록, 내 것인가, 주인)] - 1~3위는 메달 빛깔 점."""
    head = text_img(title, ACC, 12)
    lines = []
    for row in rows:
        rank, name, rec, mine = row[:4]
        owner = row[4] if len(row) > 4 else None
        col = ACC if mine else TXT
        ni = text_img(name, col, 10)
        if owner:
            oi = text_img("  " + owner, TXT_DIM if not mine else GOLD_D, 8)
            both = Image.new("RGBA", (ni.width + oi.width, ni.height), (0, 0, 0, 0))
            both.alpha_composite(ni, (0, 0))
            both.alpha_composite(oi, (ni.width, ni.height - oi.height - 1))
            ni = both
        lines.append((rank, ni, text_img(rec, col, 10)))
    nw = max([x[1].width for x in lines] or [0])
    rw = max([x[2].width for x in lines] or [0])
    w = w or max(head.width + 24, 26 + nw + 18 + rw + 12)
    rh = 15
    h = 10 + head.height + 6 + rh * len(lines) + 6
    im, d = _card(w, h, 8)
    im.alpha_composite(head, (12, 8))
    y = 10 + head.height + 6
    for rank, ni, ri in lines:
        dot = MEDAL.get(rank)
        rt = text_img(str(rank), INK if dot else TXT_DIM, 8)
        if dot:
            d.ellipse((10, y + 1, 21, y + 12), fill=dot)
        im.alpha_composite(rt, (16 - rt.width // 2, y + 7 - rt.height // 2))
        im.alpha_composite(ni, (28, y + 1))
        im.alpha_composite(ri, (w - ri.width - 12, y + 1))
        y += rh
    return im


def podium(S=2):
    """시상대 (유리): 가운데 1 · 왼쪽 2 · 오른쪽 3. (그림, 발 자리 {1: (x,y), 2: .., 3: ..})."""
    w, h = 150, 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    steps = {2: (0, 14, 50), 1: (50, 2, 100), 3: (100, 22, 150)}
    for place, (x1, top, x2) in steps.items():
        d.rectangle((x1, top, x2 - 1, h - 1), fill=(30, 38, 56, 255), outline=(84, 96, 120, 255))
        d.rectangle((x1 + 1, top + 1, x2 - 2, top + 3), fill=MEDAL[place])
        t = text_img(str(place), TXT, 12)
        im.alpha_composite(t, ((x1 + x2) // 2 - t.width // 2, top + 7))
    feet = dict((p, ((x1 + x2) / 2.0, top)) for p, (x1, top, x2) in steps.items())
    return im, feet


def target_face(arrows, S=2, title="과녁"):
    """과녁 확대 (중계 화면 위): arrows = [(점수 또는 None, X인가, 각도)] - 맞은 자리에 점."""
    r = 24
    face = target_face_img(r)
    widest = text_img("10 10 10   합 30", ACC, 8).width              # 글이 길어져도 크기가 안 바뀌게
    W = max(r * 2 + 16, widest + 14)
    im, d = _card(W, r * 2 + 30)
    im.alpha_composite(face, ((W - r * 2) // 2, 7))
    cx, cy = W // 2, r + 7
    for pts, x, ang in arrows:
        if pts is None:
            continue
        dist = 0.3 if x else (10 - pts + 0.5) * r / 10.0
        px, py = cx + math.cos(ang) * dist, cy + math.sin(ang) * dist
        d.rectangle((px - 1, py - 1, px + 1, py + 1), fill=(60, 230, 130))
        d.point((px, py), fill=INK)
    total = sum(p or 0 for p, _x, _a in arrows)
    s = " ".join("X" if x else ("M" if p is None else str(p)) for p, x, _a in arrows)
    t = text_img("%s   합 %d" % (s, total) if arrows else title, ACC, 8)
    im.alpha_composite(t, ((W - t.width) // 2, r * 2 + 15))
    return im


# ---------------------------------------------------------------- 소품 (화면 픽셀)
def skis(mode, S=2, angle=0.0, length=30):
    """스키 판 둘. mode 'flat' = angle(라디안) 경사를 따라 나란히, 'v' = 비행 V 자 (앞코가 들린다).
    (그림, 발 자리) - 발 자리는 그림 안에서 바인딩이 있는 곳."""
    L = length
    pad = L
    im = Image.new("RGBA", (pad * 2, pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fx, fy = pad, pad // 2

    def plank(x1, y1, x2, y2):
        d.line((x1, y1, x2, y2), fill=SKI_D, width=4)
        d.line((x1, y1, x2, y2), fill=SKI, width=2)
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1
        d.line((x2, y2, x2 + dx / n * 2, y2 + dy / n * 2 - 2), fill=SKI_D, width=2)
    if mode == "flat":
        ca, sa = math.cos(angle), math.sin(angle)
        plank(fx - ca * L * 0.42, fy - sa * L * 0.42, fx + ca * L * 0.58, fy + sa * L * 0.58)
    else:
        for spread in (-0.22, 0.22):
            a = angle - 0.30 + spread
            plank(fx - math.cos(a) * L * 0.30, fy - math.sin(a) * L * 0.30,
                  fx + math.cos(a) * L * 0.70, fy + math.sin(a) * L * 0.70)
    d.rectangle((fx - 2, fy - 1, fx + 2, fy + 1), fill=INK)
    return up(im, S), (fx * S, fy * S)


def sled(S=2, angle=0.0, color=(84, 112, 158)):
    """봅슬레이 썰매 (옆에서). (그림, 앉는 자리) - 선수 도트 아래 반을 가린다."""
    w, h = 40, 18
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(2, 6), (30, 4), (38, 9), (34, 14), (4, 14)], fill=color)
    d.polygon([(2, 6), (30, 4), (33, 6), (4, 8)], fill=tuple(min(255, c + 50) for c in color))
    d.line((4, 15, 36, 15), fill=STEEL_D, width=2)
    d.line((36, 15, 38, 13), fill=STEEL_D)
    t = text_img("P", LINE, 8)
    im.alpha_composite(t, (18, 6))
    im = im.rotate(-math.degrees(angle), resample=Image.NEAREST, expand=True)
    return up(im, S), (im.width * S // 2, im.height * S // 2)


def pole_stick(S=2, angle=0.0, length=46):
    im = Image.new("RGBA", (length + 4, length + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = (length + 4) / 2.0
    dx, dy = math.cos(angle) * length / 2, math.sin(angle) * length / 2
    d.line((c - dx, c - dy, c + dx, c + dy), fill=(120, 84, 10), width=3)            # 테두리
    d.line((c - dx, c - dy, c + dx, c + dy), fill=(255, 214, 40), width=1)
    d.line((c + dx * 0.85, c + dy * 0.85, c + dx, c + dy), fill=INK, width=3)
    return up(im, S)


def bow(S=2):
    im = Image.new("RGBA", (10, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.arc((-6, 1, 8, 23), -70, 70, fill=(90, 60, 40), width=2)
    d.line((4, 2, 4, 22), fill=LINE)
    return up(im, S)


def arrow(S=2, angle=0.0):
    im = Image.new("RGBA", (22, 22), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    dx, dy = math.cos(angle) * 9, math.sin(angle) * 9
    d.line((11 - dx, 11 - dy, 11 + dx, 11 + dy), fill=(236, 230, 214), width=1)
    d.point((11 + dx, 11 + dy), fill=INK)
    d.line((11 - dx, 11 - dy, 11 - dx * 0.7, 11 - dy * 0.7), fill=RED, width=2)
    return up(im, S)


def disc(S=2):
    rows = ["..ww..", ".wGGw.", "wGggGw", "wGggGw", ".wGGw.", "..ww.."]
    cols = {"w": (236, 238, 244), "G": (120, 128, 150), "g": GOLD}
    im = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in cols:
                im.putpixel((x, y), cols[ch] + (255,))
    return up(im, S)


def puff(S=2):
    """출발 총 연기."""
    im = Image.new("RGBA", (16, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x, y, r in ((5, 6, 4), (10, 5, 4), (8, 3, 3), (12, 8, 3)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=(238, 238, 244))
    return up(im, S)


def flag_pin(S=2, color=GOLD):
    """거리 깃발 (원반 · 스키 착지 자리)."""
    im = Image.new("RGBA", (8, 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line((1, 0, 1, 13), fill=INK)
    d.polygon([(2, 0), (7, 2), (2, 4)], fill=color)
    return up(im, S)


def medal(place, S=2):
    col = {1: GOLD, 2: SILVER, 3: BRONZE}.get(place, GOLD)
    im = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line((2, 0, 4, 5), fill=NAVY)
    d.line((6, 0, 4, 5), fill=RED)
    d.ellipse((1, 4, 7, 11), fill=col)
    d.point((4, 7), fill=LINE)
    return up(im, S)


def lane_spot(S=2, w=40):
    """걸어 들어오는 선수 발밑의 금빛 바닥 표시."""
    im = Image.new("RGBA", (w, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, w - 1, 7), fill=GOLD)
    d.ellipse((3, 2, w - 4, 6), fill=(255, 214, 90))
    return up(im, S)
