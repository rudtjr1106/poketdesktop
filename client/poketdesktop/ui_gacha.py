# -*- coding: utf-8 -*-
"""랜덤 캡슐 창 (2.1.0). 코인 상점 맨 위의 띠로 연다. 슬롯머신으로 만들었다가 사용자가 '캡슐 뽑는 머신으로',
그다음 '이름은 랜덤 캡슐 · 공이 엄청 섞이게 · 캡슐이 자연스럽게 나오게 · 코인 넣는 연출 · 맥에서도 60fps' 로
바꾸라고 해서 이 꼴이 되었다 (결과 · 확률표는 서버 그대로 - server/app/guild.py SLOT_TABLE).

## 생김새

          ╭──────────╮
         │ ◯ ◯  ◯ ◯ │   유리통 - 캡슐 서른여섯 알 (물리로 섞이고 쌓인다)
         │◯ ◯ ◯ ◯ ◯ │
          ╰──────────╯
        ┌─[ 랜덤 캡슐 ]─┐
        │ ▭배출구  (⊕)손잡이 ▯20 │
        └──────────────┘
          (안내 글)
       [  돌리기 · 20 코인  ]
    보유 코인 1,234                    확률 보기  닫기

**픽셀 그림이 아니다** (사용자 '픽셀로 만들지 말고 디자인 기깔나게'). 웹뷰는 쓰지 않았다 - 앱에 없고, 넣으면 윈도우
백신 오탐 · 맥 공증 · WebView2 런타임 · 두 번째 프로세스가 따라온다.

## 흐름

돌리기(단추 · 손잡이 · 유리통) -> 보유 코인에서 동전이 튀어 올라 빙글 돌며 날아가 동전 구멍에 쏙 (그동안 서버에
묻는다) -> 손잡이가 한 바퀴 -> 유리통 속 캡슐이 바닥 바람 · 소용돌이에 와르르 섞인다 -> 바람이 그치면 쌓이고
맨 아래 하나가 받침 속으로 빠진다 -> 배출구 덮개를 밀고 캡슐이 떨어져 통통 튀고 굴러가 멈춘다. **캡슐 빛깔이
등급**이다 (꽝 잿빛 · 흔함 파랑 · 드묾 보라 · 귀함 금빛 · 대박 무지개) -> 캡슐을 누르면(3초 지나면 저절로) 무대가
어두워지고 큰 캡슐이 흔들리다 반쪽씩 갈라지며 빛살과 함께 상품이 튀어나온다. 꽝은 잿빛 연기. 아무 데나 누르면 닫힌다.

## 맥 Tk 에서 60fps (2026-11-03 잰 것)

맥 Tk 는 무엇이 움직이면 그 둘레(바뀐 칸)에 걸친 **그림(PhotoImage)을 통째로** 다시 옮긴다(CGImage). 540x600
배경 그림 위에서 점 하나만 움직여도 30fps 였다. 그림을 작은 조각으로 잘라도 30 이었다. 움직이는 것과 안 겹치는
그림은 공짜, 캔버스 도형(네모 · 원 · 다각형)은 수백 개라도 거의 공짜였다. 그래서

- **맥은 배경 · 기계를 캔버스 도형으로 그린다** (Shapes). 빛깔 넘김은 가로 띠 여러 장, 빛은 겹친 원. 맥 도형은
  안티에일리어싱이 되고 레티나에서 오히려 더 또렷하다.
- 윈도우 Tk 도형은 계단이 지므로 **같은 도형 목록을 PIL 로 세 배 그려 줄인 그림**(뒤판 · 앞판 두 장)으로 깐다
  (윈도우는 그림 옮기기가 빠르다).
- 움직이는 것만 작은 그림이다: 캡슐(미리 돌려 둔 여러 장), 손잡이 막대, 동전, 배출구 덮개, 빛 조각.
- 여는 연출의 바탕도 어두운 네모 + 겹친 원 + 빛살 다각형 (예전의 '어둡게 한 장면 그림' 은 600x540 이라 느렸다).
  그 동안 유리통 캡슐은 숨긴다 (가려져도 그림은 그려지니까).
"""
import math
import os
import random
import sys
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from common.korean import natural

from . import config
from . import item_icons
from . import platform_os as PLAT
from . import ui_common as U

VECTOR = sys.platform == "darwin"      # 기계를 캔버스 도형으로 (맥) / 그림 두 장으로 (그 밖)
W, H = 540, 600                        # 창 안 캔버스 (논리 px - 화면 배율 s 를 곱한다)
SS = 2                                 # 두 배로 그려 줄인다 (매끈한 가장자리)
COST = 20
FRAME_MS = 15                          # 움직이는 동안 (맥은 그리기가 화면 주기에 맞춰져 60fps 가 된다)
IDLE_MS = 90
COIN_FLY, COIN_IN, COIN_CLICK = 0.5, 0.2, 0.16
CRANK_SEC = 0.6                        # 손잡이 한 바퀴
MIX_MIN = 1.25                         # 적어도 이만큼 섞는다 (답이 늦으면 더)
AUTO_OPEN = 3.0                        # 배출된 캡슐을 안 누르면 이만큼 뒤에 저절로 연다
CALM_SEC = 0.45                        # 상품 · 확률표를 닫은 뒤 이만큼은 돌리기 누름을 안 받는다 (두 번 누름)
GOLD = ((255, 244, 190), (234, 176, 52), (140, 86, 14))
BASE = (16, 10, 34)                    # 바탕 빛
TIER = {   # 상품 칩 빛깔 (위, 아래) · 빛
    "common": ((86, 156, 255), (34, 72, 170), (120, 190, 255)),
    "rare": ((190, 120, 255), (96, 40, 168), (200, 150, 255)),
    "epic": ((255, 196, 72), (190, 104, 16), (255, 214, 110)),
    "jackpot": ((255, 108, 150), (176, 24, 74), (255, 170, 200)),
    "lose": ((120, 126, 150), (60, 64, 84), (170, 176, 200)),
}
CAPSULE_TOPS = ((255, 82, 104), (66, 140, 255), (255, 204, 64), (88, 200, 120), (170, 110, 255), (255, 130, 200),
                (255, 150, 60), (60, 200, 210))
TIER_CAP = {   # 배출구로 나오는 캡슐 윗부분 빛깔 - 열기 전에도 등급이 보인다
    "lose": ((176, 180, 196), (120, 124, 142)),
    "common": ((92, 164, 255), (38, 90, 210)),
    "rare": ((196, 128, 255), (110, 50, 200)),
    "epic": ((255, 222, 110), (214, 140, 20)),
    "jackpot": None,                                   # 무지개
}
GX, GY, GR = 270, 176, 136             # 유리통 가운데 · 반지름
N_CAPS, CAP_R = 36, 16                 # 유리통 캡슐 수 · 반지름
DROP_R = 17                            # 배출 캡슐 반지름
KX, KY, KR = 320, 404, 38              # 손잡이
CHUTE = (156, 376, 238, 438)           # 배출구 구멍
DROP_X0, DROP_Y0, TRAY_Y = 184, 386, 420
SLIT = (380, 386, 394, 424)            # 동전 구멍
SLOT_PLATE = (373, 379, 401, 431)
COIN_R = 13
COIN_PATH = ((66, 566), (292, 214), (387, 360))   # 보유 코인 -> (높이) -> 구멍 위 (2차 베지어)
CENTER = (270, 250)                    # 여는 연출 가운데
N_ANG, N_DROP, N_KNOB, N_COIN = 24, 36, 24, 8      # 돌린 그림 장수 (15도 · 10도 · 15도 · 22.5도)


def font_path(black=True):
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    return os.path.join(d, "Pretendard-Black.otf" if black else "Pretendard-Bold.otf")


_FONTS = {}


def _font(px, black=True):
    """글꼴은 한 번만 읽는다 (연출 중 글을 바꿀 때마다 파일을 읽으면 그 틀이 밀린다)."""
    key = (max(6, int(px)), black)
    f = _FONTS.get(key)
    if f is None:
        try:
            f = ImageFont.truetype(font_path(black), key[0])
        except Exception:                                   # noqa: BLE001
            f = ImageFont.load_default()
        _FONTS[key] = f
    return f


def _mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in c[:3])


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _vgrad(w, h, top, bot, a=255):
    """세로 빛깔 넘김 (RGBA). 한 줄을 늘려 만든다."""
    col = Image.new("RGBA", (1, max(1, h)))
    for y in range(max(1, h)):
        t = y / float(max(1, h - 1))
        col.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (a,))
    return col.resize((max(1, w), max(1, h)), Image.NEAREST)


def _rmask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


def _paste_round(dst, src, xy, r):
    """불투명한 판을 둥근 모서리로 붙인다 (그 자리를 바꾼다)."""
    dst.paste(src, xy, _rmask(src.width, src.height, r))


def _comp_round(dst, src, xy, r):
    """반투명한 층(빛 · 그늘)을 둥근 모서리로 **겹쳐** 그린다 - paste 로 붙이면 밑그림까지 투명해진다."""
    a = Image.composite(src.split()[3], Image.new("L", src.size, 0), _rmask(src.width, src.height, r))
    layer = src.copy()
    layer.putalpha(a)
    dst.alpha_composite(layer, xy)


def _light(w, h, top_a, bot_a=0, col=(255, 255, 255)):
    """위에서 아래로 옅어지는 빛 한 장 (RGBA)."""
    im = Image.new("RGBA", (max(1, w), max(1, h)), col + (0,))
    im.putalpha(_vgrad(w, h, (top_a,) * 3, (bot_a,) * 3).split()[0])
    return im


def _glow(size, color, blur):
    """가운데가 밝은 둥근 빛 (RGBA, 바깥은 투명)."""
    im = Image.new("RGBA", size, color + (0,))
    a = Image.new("L", size, 0)
    ImageDraw.Draw(a).ellipse((blur, blur, size[0] - blur, size[1] - blur), fill=255)
    im.putalpha(a.filter(ImageFilter.GaussianBlur(blur / 2.0)))
    return im


def _text(text, px, fill=(255, 255, 255), black=True, glow=None, stroke=0, stroke_fill=(0, 0, 0)):
    """글자 한 줄을 그림으로 (Pretendard). glow = (빛깔, 번짐) 이면 뒤에 빛을 깐다."""
    f = _font(px, black)
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
    pad = int(px * 0.6) if glow else 2
    w, h = box[2] - box[0] + pad * 2, box[3] - box[1] + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow:
        g = Image.new("L", (w, h), 0)
        ImageDraw.Draw(g).text((pad - box[0], pad - box[1]), text, font=f, fill=255, stroke_width=stroke + 2)
        layer = Image.new("RGBA", (w, h), glow[0] + (0,))
        layer.putalpha(g.filter(ImageFilter.GaussianBlur(glow[1])))
        im.alpha_composite(layer)
        im.alpha_composite(layer)
    ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), text, font=f, fill=fill + (255,),
                            stroke_width=stroke, stroke_fill=stroke_fill + (255,))
    return im


def _egg(px):
    """전설 · 환상 알: 크림빛 알에 보랏빛 · 금빛 무늬 (매끈하게)."""
    S2 = 3
    w, h = int(px * 0.78) * S2, int(px) * S2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse((0, h * 0.04, w - 1, h - 1), fill=255)
    ImageDraw.Draw(m).ellipse((w * 0.08, 0, w * 0.92, h * 0.75), fill=255)
    im.paste(_vgrad(w, h, (255, 252, 236), (226, 206, 160)), (0, 0), m)
    d = ImageDraw.Draw(im)
    for (x, y, r, c) in ((0.3, 0.35, 0.12, (150, 90, 230)), (0.66, 0.52, 0.1, (240, 180, 50)),
                         (0.42, 0.72, 0.09, (150, 90, 230)), (0.7, 0.25, 0.07, (240, 180, 50))):
        d.ellipse(((x - r) * w, (y - r * 0.8) * h, (x + r) * w, (y + r * 0.8) * h), fill=c + (255,))
    hl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hl).ellipse((w * 0.2, h * 0.1, w * 0.45, h * 0.4), fill=110)
    white = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    white.putalpha(Image.composite(hl, Image.new("L", (w, h), 0), m))
    im.alpha_composite(white)
    return im.resize((w // S2, h // S2), Image.LANCZOS)


# ---------------------------------------------------------------- 캡슐 그림
RAINBOW = ((255, 110, 160), (255, 190, 70), (120, 220, 140), (90, 170, 255), (190, 120, 255))


def _rainbow(w, h):
    col = Image.new("RGBA", (1, max(1, h)))
    n = len(RAINBOW) - 1
    for y in range(max(1, h)):
        t = y / float(max(1, h - 1)) * n
        i = min(n - 1, int(t))
        f = t - i
        col.putpixel((0, y), tuple(int(RAINBOW[i][k] + (RAINBOW[i + 1][k] - RAINBOW[i][k]) * f) for k in range(3))
                     + (255,))
    return col.resize((w, h), Image.BILINEAR)


def capsule_frames(r, angles, tier=None, top=None):
    """캡슐 그림 여러 장 (RGBA, 반지름 r px, 세 배로 그려 줄인다). **몸(위 빛깔 · 아래 흰 반구 · 이음매)만 돌리고**
    둥근 그늘 · 왼쪽 위 빛 · 테는 그대로 둔다 - 굴러도 빛은 늘 왼쪽 위에서 온다. angles 는 시계 방향 도(度).
    tier 를 주면 그 등급 빛깔(대박은 무지개), 아니면 top. 가장자리를 빠듯하게 잘라 둔다 (맥은 그림 넓이가 곧 비용)."""
    S3 = 3
    d = max(6, int(round(r * 2 * S3)))
    pad = S3
    n = d + pad * 2
    out_px = max(2, int(round(n / float(S3))))
    if tier == "jackpot":
        upper = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        upper.paste(_rainbow(d, d // 2 + 2), (0, 0))
    else:
        if tier:
            top, bot = TIER_CAP[tier]
        else:
            bot = tuple(int(v * 0.68) for v in top)
        upper = _vgrad(d, d, tuple(min(255, v + 30) for v in top), bot)
    lower = _vgrad(d, d, (255, 255, 255), (204, 208, 226))
    um = Image.new("L", (d, d), 0)
    ImageDraw.Draw(um).rectangle((0, 0, d, d // 2), fill=255)
    body = Image.composite(upper, lower, um)
    ImageDraw.Draw(body).line((0, d // 2, d, d // 2), fill=(96, 70, 118, 255), width=max(2, d // 30))
    circle = Image.new("L", (d, d), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, d - 1, d - 1), fill=255)
    shade = Image.new("L", (d, d), 0)
    ImageDraw.Draw(shade).ellipse((-d * 0.15, -d * 0.15, d * 0.8, d * 0.8), fill=255)
    shade = Image.eval(shade.filter(ImageFilter.GaussianBlur(d * 0.14)), lambda v: (255 - v) * 78 // 255)
    dark = Image.new("RGBA", (d, d), (30, 10, 50, 0))
    dark.putalpha(Image.composite(shade, Image.new("L", (d, d), 0), circle))
    hl = Image.new("L", (d, d), 0)
    ImageDraw.Draw(hl).ellipse((d * 0.17, d * 0.1, d * 0.5, d * 0.33), fill=215)
    white = Image.new("RGBA", (d, d), (255, 255, 255, 0))
    white.putalpha(hl.filter(ImageFilter.GaussianBlur(d * 0.025)))
    rim = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(rim).ellipse((0, 0, d - 1, d - 1), outline=(70, 40, 90, 170), width=max(2, d // 40))
    out = []
    for a in angles:
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        im.paste(body.rotate(-a, resample=Image.BICUBIC) if a % 360 else body, (pad, pad), circle)
        im.alpha_composite(dark, (pad, pad))
        im.alpha_composite(white, (pad, pad))
        im.alpha_composite(rim, (pad, pad))
        out.append(im.resize((out_px, out_px), Image.LANCZOS))
    return out


def capsule(r, tier=None, top=None, angle=0):
    """캡슐 한 알 (띠 · 여는 연출)."""
    return capsule_frames(r, [angle], tier, top)[0]


def half(im, upper):
    """캡슐 그림을 반으로 (여는 연출)."""
    w, h = im.size
    return im.crop((0, 0, w, h // 2 + 1)) if upper else im.crop((0, h // 2, w, h))


# ---------------------------------------------------------------- 기계 도형
class Shapes(object):
    """기계 그림을 도형 목록으로 적어 둔다 (논리 좌표). 맥은 캔버스 도형으로(to_canvas), 그 밖은 PIL 로 세 배 그려
    줄인 그림으로(to_image) 낸다 - 윈도우 Tk 도형은 계단이 진다."""

    def __init__(self):
        self.ops = []

    def poly(self, pts, fill=None, outline=None, width=1.0):
        self.ops.append(("poly", [float(v) for v in pts], fill, outline, width))

    def oval(self, box, fill=None, outline=None, width=1.0):
        self.ops.append(("oval", [float(v) for v in box], fill, outline, width))

    def line(self, pts, fill, width=1.0):
        self.ops.append(("line", [float(v) for v in pts], fill, None, width))

    def to_canvas(self, cv, s, tag):
        ids = []
        for kind, geo, fill, outline, width in self.ops:
            g = [v * s for v in geo]
            if kind == "line":
                ids.append(cv.create_line(*g, fill=_hex(fill), width=width * s, capstyle="round", joinstyle="round",
                                          tags=(tag,)))
                continue
            kw = dict(fill=_hex(fill) if fill else "", outline=_hex(outline) if outline else "",
                      width=width * s if outline else 0, tags=(tag,))
            ids.append(cv.create_polygon(*g, **kw) if kind == "poly" else cv.create_oval(*g, **kw))
        return ids

    def to_image(self, w, h, s, mode="RGB", bg=BASE):
        S = 3
        K = s * S
        im = Image.new(mode, (w * S, h * S), tuple(bg) if mode == "RGB" else (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = (lambda c: tuple(c) + (255,)) if mode == "RGBA" else (lambda c: tuple(c))
        for kind, geo, fill, outline, width in self.ops:
            g = [v * K for v in geo]
            wd = max(1, int(round(width * K)))
            if kind == "line":
                d.line(list(zip(g[0::2], g[1::2])), fill=col(fill), width=wd, joint="curve")
            elif kind == "poly":
                pts = list(zip(g[0::2], g[1::2]))
                if fill:
                    d.polygon(pts, fill=col(fill))
                if outline:
                    d.line(pts + [pts[0], pts[1]], fill=col(outline), width=wd, joint="curve")
            else:
                if fill:
                    d.ellipse(g, fill=col(fill))
                if outline:                                # Tk 테는 둘레 가운데, PIL 테는 안쪽 - 반만큼 넓힌다
                    e = wd / 2.0
                    d.ellipse((g[0] - e, g[1] - e, g[2] + e, g[3] + e), outline=col(outline), width=wd)
        if mode == "RGBA":
            return im.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
        return im.resize((w, h), Image.LANCZOS)


def rrect_pts(x0, y0, x1, y1, r, seg=7):
    pts = []
    for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for j in range(seg + 1):
            a = math.radians(a0 + 90.0 * j / seg)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def _rr_ext(box, r):
    x0, y0, x1, y1 = box

    def ext(y):
        dy = (y0 + r - y) if y < y0 + r else ((y - (y1 - r)) if y > y1 - r else 0.0)
        dy = min(r, max(0.0, dy))
        dx = r - math.sqrt(max(0.0, r * r - dy * dy))
        return x0 + dx, x1 - dx
    return ext


def _circ_ext(cx, cy, R):
    def ext(y):
        dx = math.sqrt(max(0.0, R * R - (y - cy) ** 2))
        return cx - dx, cx + dx
    return ext


def grad_bands(sh, ext, y0, y1, color, n):
    """ext(y) -> (왼, 오른) 모양을 가로 띠 n 장으로 칠한다 (color(t), t=0 위 1 아래). 띠마다 아래로 1.2 더 내려
    그려 다음 띠가 덮게 한다 - 이음매에 바탕이 비치지 않게."""
    hgt = (y1 - y0) / float(n)
    for i in range(n):
        ya = y0 + i * hgt
        yb = min(y1, y0 + (i + 1) * hgt + 1.2)
        ys = [ya + (yb - ya) * j / 3.0 for j in range(4)]
        pts = []
        for y in ys:
            pts += [ext(y)[0], y]
        for y in reversed(ys):
            pts += [ext(y)[1], y]
        sh.poly(pts, fill=color((i + 0.5) / n))


def grad_rrect(sh, box, r, top, bot, n, light=0.0):
    """둥근 네모를 세로 빛깔 넘김으로. light = 위쪽 빛 (흰빛을 섞는 정도)."""
    def color(t):
        c = _mix(top, bot, t)
        if light and t < 0.32:
            c = _mix(c, (255, 255, 255), light * (1 - t / 0.32) ** 1.5)
        return c
    grad_bands(sh, _rr_ext(box, r), box[1], box[3], color, n)


def _halo():
    out = []
    N = 7
    for i in range(N):
        t = i / float(N - 1)                              # 0 바깥 -> 1 유리 바로 옆
        out.append((GR + 60 - 59 * t, _mix(BASE, _mix((72, 58, 190), (150, 90, 230), t), 0.05 + 0.24 * t ** 1.6)))
    return out


HALO = _halo()


def ring_polys(cx, cy, rings, seg=40, hole=False):
    """겹친 원 대신 안 겹치는 고리: rings = [(반지름 또는 (가로, 세로) 반지름, 빛깔)] 바깥부터. 고리 하나 = 위 · 아래
    반쪽 다각형 둘 (이음매가 안 보이게 1도씩 겹친다). 맨 안쪽은 꽉 찬 원, hole 이면 맨 안쪽 반지름은 구멍으로만
    쓴다 (그 안은 다른 것이 덮는다). 돌려주는 것 = [(점, 빛깔, 고리 번호)]."""
    def radii(v):
        return v if isinstance(v, tuple) else (v, v)
    out = []
    for n in range(len(rings) - (1 if hole else 0)):
        (ox, oy), c = radii(rings[n][0]), rings[n][1]
        ix, iy = radii(rings[n + 1][0]) if n + 1 < len(rings) else (0.0, 0.0)
        for a0, a1 in ((-1.0, 181.0), (179.0, 361.0)):
            pts = []
            for j in range(seg + 1):
                a = math.radians(a0 + (a1 - a0) * j / float(seg))
                pts += [cx + math.cos(a) * ox, cy + math.sin(a) * oy]
            for j in range(seg, -1, -1):
                a = math.radians(a0 + (a1 - a0) * j / float(seg))
                pts += [cx + math.cos(a) * ix, cy + math.sin(a) * iy]
            out.append((pts, c, n))
    return out


def bg_at(x, y):
    col = BASE
    d = math.hypot(x - GX, y - GY)
    for r, c in HALO:
        if d <= r:
            col = c
    return col


def _body_col(y):
    t = (y - 304) / 162.0
    c = _mix((255, 98, 118), (188, 22, 58), max(0.0, min(1.0, t)))
    if t < 0.32:
        c = _mix(c, (255, 255, 255), 0.3 * (1 - max(0.0, t) / 0.32) ** 1.5)
    return c


def scene_shapes():
    """(뒤판, 앞판, 맨 위) 도형. 뒤판 = 바탕 · 빛 · 별 · 그림자 · 다리 · 유리통 속, 그 위에 유리통 캡슐,
    앞판 = 유리 테 · 받침 · 몸통 · 이름판 · 배출구 · 손잡이 판 (가라앉는 캡슐이 받침 · 몸통 뒤로 사라진다),
    맨 위 = 동전 구멍 (날아온 동전보다 위 - 동전이 그 안으로 사라진다)."""
    back, front, top = Shapes(), Shapes(), Shapes()
    # 바탕: 유리통 둘레 빛 (얇은 고리 여러 겹). 맥 Tk 는 무엇이 움직이면 캔버스를 **통째로** 다시 칠한다 - 창
    # 전체를 덮는 빛(겹친 타원 20개)을 깔았더니 30fps 였다 (2026-11-03 잼). 그래서 빛은 유리통 둘레에만,
    # 안 겹치는 고리(위 · 아래 반쪽 다각형)로 칠한다
    for (pts, c, _n) in ring_polys(GX, GY, HALO, hole=True):     # 맨 안쪽은 유리통 속 · 테가 덮는다
        back.poly(pts, fill=c)
    rnd = random.Random(7)
    for _i in range(84):                                  # 별가루
        x, y = rnd.uniform(4, W - 4), rnd.uniform(4, H - 4)
        rr = rnd.choice((0.7, 0.9, 1.1, 1.5))
        back.oval((x - rr, y - rr, x + rr, y + rr), fill=_mix(bg_at(x, y), (255, 255, 255), rnd.uniform(0.25, 0.75)))
    for (x, y, a) in ((60, 70, 7), (478, 120, 6), (494, 336, 5), (40, 300, 5), (440, 34, 4), (104, 448, 4)):
        c = _mix(bg_at(x, y), (255, 236, 196), 0.8)     # 반짝 별 (네 갈래)
        q = a * 0.22
        back.poly((x, y - a, x + q, y - q, x + a, y, x + q, y + q, x, y + a, x - q, y + q, x - a, y, x - q, y - q),
                  fill=c)
    under = bg_at(270, 488)                               # 바닥 그림자 (고리 - 겹치게 칠하지 않는다)
    for (pts, c, _n) in ring_polys(270, 488, [((rx, ry), _mix(under, (0, 0, 0), a)) for (rx, ry, a) in (
            (166, 22, 0.1), (154, 18, 0.2), (140, 15, 0.3), (124, 12, 0.4), (106, 9, 0.5))], seg=28):
        back.poly(pts, fill=c)
    for x in (150, 362):                                  # 다리
        grad_rrect(back, (x, 456, x + 28, 488), 6, (84, 72, 104), (34, 28, 50), 6)
    # 유리통 속 (위가 밝은 보랏빛) + 바닥 쪽 유리 반사
    grad_bands(back, _circ_ext(GX, GY, GR), GY - GR, GY + GR, lambda t: _mix((66, 52, 128), (28, 20, 60), t), 40)
    pts = []
    for j in range(25):
        a = math.radians(32 + 116 * j / 24.0)
        pts += [GX + math.cos(a) * (GR - 9), GY + math.sin(a) * (GR - 9)]
    back.line(pts, (52, 42, 96), 3)

    # 앞판: 유리 테
    front.oval((GX - GR - 2.6, GY - GR - 2.6, GX + GR + 2.6, GY + GR + 2.6), outline=(64, 54, 124), width=1.4)
    front.oval((GX - GR, GY - GR, GX + GR, GY + GR), outline=(212, 220, 252), width=4)
    # 꼭지 (빨간 뚜껑)
    grad_rrect(front, (246, 30, 294, 48), 8, (255, 112, 128), (176, 22, 54), 6, light=0.35)
    front.poly(rrect_pts(245, 29, 295, 49, 8.5), outline=(110, 10, 34), width=2)
    # 몸통: 짙은 테 + 위가 밝은 빨강 + 윗날 빛
    # (짙은 테는 칠하지 않고 테두리 선으로 - 맥은 칠한 넓이가 곧 비용이라 몸통을 두 번 칠하지 않는다)
    grad_bands(front, _rr_ext((128, 302, 412, 468), 26.5), 302, 468, lambda t: _body_col(302 + t * 166), 40)
    front.poly(rrect_pts(128, 302, 412, 468, 26.5), outline=(104, 12, 36), width=4.5)
    front.line((158, 308.2, 382, 308.2), (255, 190, 200), 1.6)
    front.line((156, 462, 384, 462), (150, 14, 44), 2.0)
    # 받침 (금빛 띠)
    def gold(t):
        return _mix(GOLD[0], GOLD[1], t * 2) if t < 0.5 else _mix(GOLD[1], GOLD[2], (t - 0.5) * 2)
    grad_bands(front, _rr_ext((157.5, 289.5, 382.5, 316.5), 10.5), 289.5, 316.5, gold, 12)
    front.poly(rrect_pts(157.5, 289.5, 382.5, 316.5, 10.5), outline=(126, 74, 12), width=1.4)
    front.line((172, 292.4, 368, 292.4), (255, 252, 226), 1.2)
    # 이름판
    grad_rrect(front, (170, 318, 370, 358), 13, (255, 251, 242), (230, 216, 204), 12)
    front.poly(rrect_pts(170, 318, 370, 358, 13), outline=(150, 26, 48), width=2)
    # 배출구: 짙은 테 · 크림빛 테 · 어두운 구멍 (위가 더 깊다)
    rim = (151, 371, 243, 443)
    grad_rrect(front, rim, 17.5, (255, 238, 222), (204, 180, 168), 12)
    front.poly(rrect_pts(*rim, r=17.5), outline=(120, 16, 40), width=2)
    grad_rrect(front, CHUTE, 13, (12, 4, 16), (64, 24, 46), 14)
    # 손잡이 판: 그림자 · 은빛 둥근 판(왼쪽 위가 밝게) · 테 · 홈
    body = _body_col(KY)
    for (dr, a) in ((3.5, 0.12), (1.8, 0.22), (0.0, 0.34)):
        R = KR + dr
        front.oval((KX + 4 - R, KY + 7 - R, KX + 4 + R, KY + 7 + R), fill=_mix(body, (40, 0, 16), a))
    for i in range(9):
        u = i / 8.0
        R = KR * (1 - 0.8 * u)
        cx, cy = KX - 0.3 * KR * u, KY - 0.34 * KR * u
        front.oval((cx - R, cy - R, cx + R, cy + R), fill=_mix((164, 170, 196), (255, 255, 255), u ** 0.8))
    front.oval((KX - KR, KY - KR, KX + KR, KY + KR), outline=(104, 106, 138), width=2)
    front.oval((KX - KR * 0.84, KY - KR * 0.84, KX + KR * 0.84, KY + KR * 0.84), outline=(206, 210, 228), width=1)
    # 동전 판 (은빛)
    grad_rrect(front, SLOT_PLATE, 9, (240, 242, 250), (150, 156, 180), 10)
    # 맨 위: 동전 구멍 + 판 테 (동전이 들어가면 금빛으로 번쩍)
    grad_rrect(top, SLIT, 5, (44, 24, 50), (8, 2, 14), 6)
    top.poly(rrect_pts(*SLOT_PLATE, r=9), outline=(110, 12, 34), width=1.5)
    return back, front, top


# ---------------------------------------------------------------- 유리통 속 캡슐 (물리)
class Globe(object):
    """캡슐들 (논리 px). b[i] = [x, y, vx, vy, 각도(시계 방향 도), 돌기(도/초), 빛깔 번호].
    섞기(power>0) = 바닥에서 뿜는 바람 + 소용돌이 + 이따금 툭 치기, 그치면 중력으로 쌓인다.
    sink = 받침 속으로 빠지는 캡슐 (벽에 안 막힌다) -> 다 빠지면 gone 에 든다 (숨김, 다음 섞기에 위에서 다시 떨어진다)."""

    SUB = 3

    def __init__(self, rnd, n=N_CAPS, r=CAP_R):
        self.rnd, self.r = rnd, float(r)
        self.lim = GR - r - 5.0
        self.b = []
        y, row = GY + self.lim, 0
        while len(self.b) < n:
            half_w = math.sqrt(max(0.0, self.lim ** 2 - (y - GY) ** 2))
            x = GX - half_w + (r if row % 2 else 0)
            while x <= GX + half_w + 0.1 and len(self.b) < n:
                self.b.append([x + rnd.uniform(-2, 2), y, 0.0, 0.0, rnd.uniform(0, 360), 0.0,
                               rnd.randrange(len(CAPSULE_TOPS))])
                x += 2 * r + 0.5
            y -= r * 1.75
            row += 1
        self.gone = set()
        self.sink = None
        for _i in range(150):                             # 처음부터 쌓인 모습으로
            self.step(1 / 60.0, 0.0)

    def respawn(self):
        """빠진 캡슐을 위에서 다시 떨군다 (빛깔은 새로)."""
        for i in sorted(self.gone):
            b = self.b[i]
            b[0], b[1] = GX + self.rnd.uniform(-50, 50), GY - GR * 0.55
            b[2], b[3], b[6] = self.rnd.uniform(-60, 60), 80.0, self.rnd.randrange(len(CAPSULE_TOPS))
        self.gone = set()
        self.sink = None

    def choose_sink(self):
        live = [i for i in range(len(self.b)) if i not in self.gone]
        mid = [i for i in live if abs(self.b[i][0] - GX) < 46] or live
        self.sink = max(mid, key=lambda i: self.b[i][1])
        b = self.b[self.sink]
        b[2], b[3] = (GX - b[0]) * 2.0, 90.0
        return self.sink

    def step(self, dt, power):
        """dt 만큼 굴린다. 돌려주는 것 = 이 틀에 가장 많이 움직인 거리(px) - 쌓여 멈췄는지 보는 값이다. 속도로는 못
        본다: 쌓여 있어도 걸음마다 중력 몫이 붙었다가 충돌에 지워져 0 이 안 된다 (11/03 검토, 늘 88 언저리).
        틀이 늦어도(dt 가 커도) 한 걸음은 1/180초 이하로 - 걸음이 길면 쌓인 캡슐이 서로 깊이 파고든다."""
        before = [(b[0], b[1]) for b in self.b]
        n = max(self.SUB, int(math.ceil(dt * 180 - 1e-9)))
        for _i in range(n):
            self._sub(dt / n, power)
        return max(abs(b[0] - x) + abs(b[1] - y) for b, (x, y) in zip(self.b, before))

    def _sub(self, h, P):
        rnd, r, lim = self.rnd, self.r, self.lim
        damp = math.exp(-(0.45 if P > 0 else 2.6) * h)
        e_wall = 0.62 if P > 0 else 0.18
        act = [i for i in range(len(self.b)) if i not in self.gone]
        for i in act:
            b = self.b[i]
            x, y, vx, vy = b[0], b[1], b[2], b[3]
            ax, ay = 0.0, 1500.0
            if P > 0:
                dx, dy = (x - GX) / GR, (y - GY) / GR
                f = dy + 0.2
                if f > 0:                                 # 바닥 바람: 아래일수록 세게 위로
                    ay -= P * 5600.0 * min(1.0, f)
                ax -= P * 2300.0 * dy                     # 소용돌이
                ay += P * 2300.0 * dx
                if rnd.random() < P * h * 5.0:            # 툭
                    vx += rnd.uniform(-480, 480)
                    vy += rnd.uniform(-520, 160)
            vx = (vx + ax * h) * damp
            vy = (vy + ay * h) * damp
            sp = math.hypot(vx, vy)
            if sp > 1100:
                vx, vy, sp = vx * 1100 / sp, vy * 1100 / sp, 1100.0
            x += vx * h
            y += vy * h
            if i == self.sink:
                if y > GY + GR + r + 6:
                    self.gone.add(i)
            else:
                dx, dy = x - GX, y - GY
                d = math.hypot(dx, dy)
                if d > lim:
                    nx, ny = dx / d, dy / d
                    x, y = GX + nx * lim, GY + ny * lim
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= (1 + e_wall) * vn * nx
                        vy -= (1 + e_wall) * vn * ny
                        vt = -vx * ny + vy * nx
                        if vn > 60:                               # 세게 부딪혀 벽을 따라 구르면 그만큼 돈다
                            b[5] = -vt / r * 57.3                 # (쌓여 기대 있는 것은 돌지 않는다)
                        vx += ny * vt * 0.1
                        vy -= nx * vt * 0.1
            b[0], b[1], b[2], b[3] = x, y, vx, vy
            b[4] = (b[4] + b[5] * h) % 360.0
            b[5] = max(-900.0, min(900.0, b[5] * math.exp(-(1.0 if P > 0 else 6.0) * h)))
        D = 2 * r
        D2 = D * D
        e = 0.78 if P > 0 else 0.12
        n = len(act)
        for rnd_i in range(1 if P > 0 else 2):            # 쌓일 때는 자리 풀기를 한 번 더 (더미 무게에 파고들지 않게)
            for a in range(n):
                bi = self.b[act[a]]
                for c in range(a + 1, n):
                    bj = self.b[act[c]]
                    dx = bj[0] - bi[0]
                    if dx > D or dx < -D:
                        continue
                    dy = bj[1] - bi[1]
                    if dy > D or dy < -D:
                        continue
                    d2 = dx * dx + dy * dy
                    if d2 >= D2 or d2 <= 1e-6:
                        continue
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    push = (D - d) * 0.5
                    bi[0] -= nx * push
                    bi[1] -= ny * push
                    bj[0] += nx * push
                    bj[1] += ny * push
                    rel = (bj[2] - bi[2]) * nx + (bj[3] - bi[3]) * ny
                    if rel < 0 and rnd_i == 0:
                        j = -(1 + e) * rel * 0.5
                        bi[2] -= j * nx
                        bi[3] -= j * ny
                        bj[2] += j * nx
                        bj[3] += j * ny
                        if rel < -60:                     # 세게 스치면 돈다 (맞대고 쉬는 것은 안 돈다)
                            tv = (bj[2] - bi[2]) * -ny + (bj[3] - bi[3]) * nx
                            bi[5] -= tv / r * 18
                            bj[5] -= tv / r * 18
        for i in act:                                     # 서로 밀다 유리 밖으로 나간 것은 다시 안으로
            if i != self.sink:
                b = self.b[i]
                dx, dy = b[0] - GX, b[1] - GY
                d = math.hypot(dx, dy)
                if d > lim:
                    b[0], b[1] = GX + dx * lim / d, GY + dy * lim / d


# ---------------------------------------------------------------- 그림 (작업 스레드에서)
class Art(object):
    """열 때 한 번 그리는 그림들 + 유리통 물리. s = 화면 배율 (U.h(100) / 100)."""

    def __init__(self, s):
        self.s = s
        k = lambda v: int(round(v * s))                    # noqa: E731
        self.k = k
        self.W, self.H = k(W), k(H)
        self.back, self.front, self.top = scene_shapes()
        if not VECTOR:
            self.back_im = self.back.to_image(self.W, self.H, s, "RGB")
            fr = self.front.to_image(self.W, self.H, s, "RGBA")
            box = fr.split()[3].getbbox() or (0, 0, 1, 1)
            self.front_im, self.front_at = fr.crop(box), box[:2]
        self.globe = Globe(random.Random())
        self.caps = [capsule_frames(CAP_R * s, [i * 360.0 / N_ANG for i in range(N_ANG)], top=c)
                     for c in CAPSULE_TOPS]
        self.drop = dict((t, capsule_frames(DROP_R * s, [i * 360.0 / N_DROP for i in range(N_DROP)], tier=t))
                         for t in TIER_CAP)
        self.big = dict((t, {"pop": [capsule(30 * s, t), capsule(46 * s, t)],
                             "shake": capsule_frames(64 * s, (-10, -5, 0, 5, 10), tier=t)}) for t in TIER_CAP)
        self.halves = dict((t, (half(self.big[t]["shake"][2], True), half(self.big[t]["shake"][2], False)))
                           for t in TIER_CAP)
        self.knob = self._knob_frames()
        self.coin = self._coin_frames()
        self.flap = self._flap_frames()
        self.glass = self._glass()
        self.plate = _text("랜덤 캡슐", 25 * s, fill=(214, 36, 72))
        self.price = _text("20", 12 * s, fill=(255, 228, 176))
        self.spark = self._spark()
        self.confetti = [self._confetti(c, a) for c in ((255, 92, 140), (255, 210, 70), (90, 200, 255),
                                                       (160, 255, 150), (200, 140, 255)) for a in (0, 45)]
        self.puff = self._puff()

    def _knob_frames(self):
        """손잡이 막대 (빨간 알약 + 금빛 꼭지 + 그림자) 를 시계 방향으로 15도씩."""
        S3 = 3
        R = KR * self.s * S3
        size = int(R * 2.3) // S3 * S3
        bw, bh = int(R * 1.72), int(R * 0.46)
        bar = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        _paste_round(bar, _vgrad(bw, bh, (255, 104, 118), (186, 18, 48)), (0, 0), bh // 2)
        _comp_round(bar, _light(bw, bh // 2, 100), (0, 0), bh // 2)
        ImageDraw.Draw(bar).rounded_rectangle((0, 0, bw - 1, bh - 1), bh // 2, outline=(120, 10, 34, 255), width=S3)
        hub = R * 0.22
        c = size / 2.0
        off = (int(3 * self.s * S3), int(5 * self.s * S3))
        out = []
        for i in range(N_KNOB):
            big = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            rb = bar.rotate(-i * 360.0 / N_KNOB, expand=True, resample=Image.BICUBIC)
            at = (int(c - rb.width / 2.0), int(c - rb.height / 2.0))
            sa = Image.new("L", (size, size), 0)
            sa.paste(rb.split()[3].point(lambda v: v * 110 // 255), (at[0] + off[0], at[1] + off[1]))
            shadow = Image.new("RGBA", (size, size), (40, 0, 18, 0))
            shadow.putalpha(sa.filter(ImageFilter.GaussianBlur(2.5 * self.s * S3)))
            big.alpha_composite(shadow)
            big.alpha_composite(rb, at)
            d = ImageDraw.Draw(big)
            d.ellipse((c - hub, c - hub, c + hub, c + hub), fill=(255, 214, 110, 255), outline=(156, 96, 18, 255),
                      width=S3)
            d.ellipse((c - hub * 0.55, c - hub * 0.62, c - hub * 0.05, c - hub * 0.15), fill=(255, 246, 210, 255))
            out.append(big.resize((size // S3, size // S3), Image.LANCZOS))
        return out

    def _coin_frames(self):
        """금화 한 바퀴 반 (0 ~ 157.5도, 22.5도씩): 앞면(별) · 옆으로 누운 모습 · 뒷면(조금 어둡게)."""
        S3 = 3
        D = int(COIN_R * 2 * self.s) * S3
        R = D / 2.0

        def face(front):
            im = Image.new("RGBA", (D, D), (0, 0, 0, 0))
            m = Image.new("L", (D, D), 0)
            ImageDraw.Draw(m).ellipse((0, 0, D - 1, D - 1), fill=255)
            top, bot = ((255, 240, 160), (220, 146, 26)) if front else ((236, 206, 120), (186, 116, 18))
            im.paste(_vgrad(D, D, top, bot), (0, 0), m)
            d = ImageDraw.Draw(im)
            d.ellipse((0, 0, D - 1, D - 1), outline=(160, 94, 10, 255), width=2 * S3)
            d.ellipse((R * 0.26, R * 0.26, D - R * 0.26, D - R * 0.26), outline=(255, 232, 150, 255), width=S3)
            if front:
                pts = []
                for j in range(10):
                    a = math.radians(-90 + j * 36)
                    rr = R * (0.44 if j % 2 == 0 else 0.19)
                    pts.append((R + math.cos(a) * rr, R + math.sin(a) * rr))
                d.polygon(pts, fill=(226, 150, 28, 255))
            d.ellipse((R * 0.4, R * 0.22, R * 0.9, R * 0.5), fill=(255, 252, 230, 150))
            return im
        fa, fb = face(True), face(False)
        ew = max(4 * S3, int(D * 0.17))
        edge = Image.new("RGBA", (ew, D), (0, 0, 0, 0))
        col = Image.new("RGBA", (ew, 1))
        for x in range(ew):
            col.putpixel((x, 0), _mix((255, 236, 150), (170, 104, 14), x / float(max(1, ew - 1))) + (255,))
        _paste_round(edge, col.resize((ew, D)), (0, 0), ew // 2)
        out = []
        for i in range(N_COIN):
            th = i * 180.0 / N_COIN
            sc = abs(math.cos(math.radians(th)))
            im = Image.new("RGBA", (D, D), (0, 0, 0, 0))
            if D * sc < ew * 1.3:
                im.alpha_composite(edge, ((D - ew) // 2, 0))
            else:
                src = (fa if th < 90 else fb).resize((max(ew, int(D * sc)), D), Image.LANCZOS)
                im.alpha_composite(src, ((D - src.width) // 2, 0))
            out.append(im.resize((D // S3, D // S3), Image.LANCZOS))
        return out

    def _flap_frames(self):
        """배출구 덮개 (연기빛 반투명 판): 닫힘 -> 열림 (위로 젖혀져 얇아진다)."""
        S3 = 3
        w, h0 = (CHUTE[2] - CHUTE[0]) * self.s * S3, 26 * self.s * S3
        out = []
        for f in (1.0, 0.62, 0.3, 0.1):
            hh = max(3, int(h0 * f))
            im = Image.new("RGBA", (int(w), int(h0)), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            rad = int(12 * self.s * S3)
            d.rounded_rectangle((0, 0, w - 1, hh - 1), radius=min(rad, hh // 2), fill=(108, 78, 140, 128))
            d.rectangle((0, min(rad, hh // 2), w - 1, hh - 1), fill=(108, 78, 140, 128))
            d.line((S3 * 3, hh - S3 * 2, w - S3 * 3, hh - S3 * 2), fill=(255, 255, 255, 96), width=2 * S3)
            d.line((S3 * 4, S3, w - S3 * 4, S3), fill=(24, 8, 30, 170), width=2 * S3)
            out.append(im.resize((int(w / S3), int(h0 / S3)), Image.LANCZOS))
        return out

    def _glass(self):
        """유리 빛 (왼쪽 위 빛 줄기 · 오른쪽 아래 작은 빛) - 캡슐 위에 얹는 작은 그림 두 장 [(그림, (x, y))]."""
        S2 = 2
        R = GR * self.s * S2
        size = int(2 * R + 8)
        C = size / 2.0
        hl = Image.new("L", (size, size), 0)
        hd = ImageDraw.Draw(hl)
        hd.arc((C - R * 0.84, C - R * 0.84, C + R * 0.84, C + R * 0.84), 198, 258, fill=225, width=int(R * 0.085))
        hd.ellipse((C + R * 0.42, C + R * 0.3, C + R * 0.56, C + R * 0.42), fill=140)
        im = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        im.putalpha(hl.filter(ImageFilter.GaussianBlur(R * 0.02)))
        im = im.resize((size // S2, size // S2), Image.LANCZOS)
        ox, oy = self.k(GX) - im.width // 2, self.k(GY) - im.height // 2
        out = []
        hw = im.width // 2
        for box in ((0, 0, hw, hw), (hw, hw, im.width, im.height)):
            sub = im.crop(box)
            bb = sub.split()[3].getbbox()
            if bb:
                out.append((sub.crop(bb), (ox + box[0] + bb[0], oy + box[1] + bb[1])))
        return out

    def _spark(self):
        k = self.k
        im = Image.new("RGBA", (k(18), k(18)), (0, 0, 0, 0))
        im.alpha_composite(_glow(im.size, (255, 240, 180), k(4)))
        c = k(9)
        ImageDraw.Draw(im).polygon([(c, 0), (c + k(2), c - k(2)), (k(18), c), (c + k(2), c + k(2)), (c, k(18)),
                                    (c - k(2), c + k(2)), (0, c), (c - k(2), c - k(2))], fill=(255, 255, 240, 255))
        return im

    def _confetti(self, col, angle):
        k = self.k
        return Image.new("RGBA", (k(10), k(6)), col + (255,)).rotate(angle, expand=True, resample=Image.BICUBIC)

    def _puff(self):
        """꽝일 때 나는 잿빛 연기."""
        k = self.k
        im = Image.new("RGBA", (k(180), k(120)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for (x, y, r) in ((44, 64, 32), (90, 46, 40), (134, 66, 30), (76, 82, 28), (112, 86, 26)):
            d.ellipse((k(x - r), k(y - r), k(x + r), k(y + r)), fill=(206, 206, 220, 175))
        return im.filter(ImageFilter.GaussianBlur(k(3)))


def prize_chip(s, tier, art_im):
    """상품 칩: 등급 빛깔 둥근 판 + 상품 그림 (도트 그림은 정수 배로 키운다)."""
    S2 = SS
    size = int(116 * s * S2)
    top, bot, _g = TIER.get(tier, TIER["common"])
    im = Image.new("RGBA", (size + 20 * S2, size + 24 * S2), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((10 * S2, 16 * S2, 10 * S2 + size, 16 * S2 + size), size // 4,
                                         fill=(0, 0, 0, 140))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * S2)))
    _paste_round(im, _vgrad(size, size, top, bot), (10 * S2, 8 * S2), size // 4)
    _comp_round(im, _light(size - 12 * S2, size // 2, 95), (16 * S2, 12 * S2), size // 5)
    ImageDraw.Draw(im).rounded_rectangle((10 * S2, 8 * S2, 10 * S2 + size - 1, 8 * S2 + size - 1), size // 4,
                                         outline=tuple(min(255, v + 70) for v in top) + (255,), width=3 * S2)
    if art_im is not None:
        a = art_im
        want = int(size * 0.66)
        n = max(1, want // max(a.size))
        if max(a.size) <= 64:
            a = a.resize((a.width * n, a.height * n), Image.NEAREST)   # 도트 그림은 정수 배로
        if max(a.size) > want or max(a.size) > 64:        # 매끈한 그림(알)은 칸에 맞게 늘이고 줄인다
            f = want / float(max(a.size))
            a = a.resize((max(1, int(a.width * f)), max(1, int(a.height * f))), Image.LANCZOS)
        im.alpha_composite(a, (10 * S2 + (size - a.width) // 2, 8 * S2 + (size - a.height) // 2))
    return im.resize((im.width // S2, im.height // S2), Image.LANCZOS)


# ---------------------------------------------------------------- 창
def fit_scale(widget):
    """창 배율 = 글자 크기 배율(U.h) 그대로, 단 화면 작업 영역 높이를 넘지 않게. 글자 '크게' · '아주 크게' 면 맥에서
    600 x 1.4 = 840 이라 창 아래(단추 · 보유 코인 · 닫기)가 잘렸다 - 그때는 기계 전체를 같은 비율로 줄인다."""
    s = U.h(100) / 100.0
    try:
        _x1, y1, _x2, y2 = PLAT.work_area(widget.winfo_screenwidth(), widget.winfo_screenheight())
        s = min(s, (y2 - y1 - 48) / float(H))              # 48 = 제목 막대 · 여유
    except Exception:                                       # noqa: BLE001
        pass
    return max(0.5, s)


RAY_N = 14                                             # 빛살 수 · 마디 반지름 (마디마다 옅어진다)
RAY_R = tuple(120 + 30 * j for j in range(7))
RAY_A = tuple(0.36 * (1 - j / 6.0) ** 1.4 + 0.03 for j in range(6))
GLOW = tuple((164 - 140 * t, 0.05 + 0.72 * t ** 1.5) for t in [i / 15.0 for i in range(16)])   # 바깥 -> 가운데
BACKDROP = (12, 7, 22)                                 # 여는 연출 동안 캔버스 바탕 빛 (기계는 숨긴다)


class GachaWindow(object):
    """랜덤 캡슐 창. on_change(coin) = 코인 · 가방이 바뀌었을 때 (상점을 다시 받게).

    state: idle -> coin (동전이 날아가 들어간다, 서버에 묻는 중) -> crank (손잡이 한 바퀴) -> mix (와르르) ->
           settle (쌓이고 하나가 빠진다) -> drop (배출구로 굴러 나온다) -> ready (눌러서 열기) ->
           open (어두워지고 큰 캡슐이 흔들리다 갈라진다) -> reveal (상품) -> 누르면 idle.
           오류면 mix -> settle -> idle (코인 되돌림)."""

    def __init__(self, app, parent, coin=0, odds=None, on_change=None):
        self.app, self.root = app, app.root
        self.coin = int(coin or 0)
        self.odds = list(odds or [])
        self.on_change = on_change
        self.state = "loading"
        self.alive = True
        self.said = ""
        self.last_fx = None                                # (검사가 본다 - 연출은 금방 끝난다)
        self.perf = {}                                     # 상태별 [그린 횟수, 초] - 맥 60fps 확인용
        self.result = None
        self.err = None
        self.prize_art, self.prize_ready = None, False
        self.art = None
        self.parts = []
        self.globe_live = False
        self.calm_since = self.quiet_at = None
        self._notified = True                              # 한 판에 상점 알림 한 번 (돌리면 False)
        self._ui_click = False
        self._calm_until = 0.0                             # 이때까지 사람이 누른 돌리기는 안 받는다
        self.s = fit_scale(parent)
        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "랜덤 캡슐", int(W * self.s), int(H * self.s))
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        # 부모(허브)가 닫혀 같이 부서질 때도 멈추고 상점에 알린다 (close 를 안 거친다)
        self.win.bind("<Destroy>", lambda e: e.widget is self.win and self._gone())
        self.cv = tk.Canvas(self.win, width=int(W * self.s), height=int(H * self.s), bg=_hex(BASE),
                            highlightthickness=0, bd=0)
        self.cv.pack()
        self.loading = self.cv.create_text(int(W * self.s / 2), int(H * self.s / 2), text="캡슐 기계를 켜는 중...",
                                           fill="#d8d4f0", font=U.FONT_B)
        U.run_async(self.root, lambda: Art(self.s), self._ready)

    # ---------------- 짓기
    def _photo(self, name, im):
        p = ImageTk.PhotoImage(im)
        self.ph[name] = p                                  # 참조를 놓으면 tk 가 그림을 지운다
        return p

    def _ready(self, art, err):
        if not self.alive:
            return
        if err or art is None:
            self.cv.itemconfigure(self.loading, text="캡슐 기계를 켜지 못했습니다: %s" % (err or "?"))
            return
        self.art = art
        self.cv.delete(self.loading)
        k, cv, s = art.k, self.cv, self.s
        self.ph = {}
        # 1. 뒤판 -> 2. 유리통 캡슐 -> 3. 앞판 (가라앉는 캡슐이 그 뒤로) -> 4. 유리 빛 · 글 · 손잡이 막대 ->
        # 5. 배출 캡슐 · 덮개 -> 6. 동전 -> 7. 동전 구멍 (동전이 그 안으로 사라진다) -> 8. 글 · 단추 -> 9. 여는 연출
        if VECTOR:
            art.back.to_canvas(cv, s, "back")
        else:
            cv.create_image(0, 0, anchor="nw", image=self._photo("back", art.back_im))
        self.cap_ph = [[ImageTk.PhotoImage(im) for im in frames] for frames in art.caps]
        self.cap_ids = [cv.create_image(k(b[0]), k(b[1]), image=self.cap_ph[b[6]][0]) for b in art.globe.b]
        self._cap_drawn = [None] * len(self.cap_ids)       # (x, y, 그림, 숨김) - 바뀐 것만 고친다
        self._globe_hidden = False
        if VECTOR:
            art.front.to_canvas(cv, s, "front")
        else:
            cv.create_image(art.front_at[0], art.front_at[1], anchor="nw", image=self._photo("front", art.front_im))
        for i, (im, xy) in enumerate(art.glass):
            cv.create_image(xy[0], xy[1], anchor="nw", image=self._photo("glass%d" % i, im))
        cv.create_image(k(270), k(338), image=self._photo("plate", art.plate))
        cv.create_image(k(387), k(442), image=self._photo("price", art.price))
        self.knob_ph = [ImageTk.PhotoImage(im) for im in art.knob]
        self.knob_id = cv.create_image(k(KX), k(KY), image=self.knob_ph[0])
        self._knob_i = 0
        self.drop_ph = dict((t, [ImageTk.PhotoImage(im) for im in ims]) for t, ims in art.drop.items())
        self.drop_id = cv.create_image(k(DROP_X0), k(TRAY_Y), image=self.drop_ph["common"][0], state="hidden")
        self.flap_ph = [ImageTk.PhotoImage(im) for im in art.flap]
        self.flap_id = cv.create_image(k(CHUTE[0]), k(CHUTE[1]), anchor="nw", image=self.flap_ph[0])
        self._flap_i = 0
        self.coin_ph = [ImageTk.PhotoImage(im) for im in art.coin]
        self.coin_id = cv.create_image(0, 0, image=self.coin_ph[0], state="hidden")
        self.slot_rim = art.top.to_canvas(cv, s, "slot")[-1]
        # 글 · 단추 · 아래 줄
        self.msg_id = cv.create_image(k(270), k(504), anchor="center")
        self.btn_ph = [self._photo("btn%d" % i, im) for i, im in enumerate(self._button_imgs())]
        self.btn_id = cv.create_image(k(270), k(548), anchor="center", image=self.btn_ph[0])
        cv.tag_bind(self.btn_id, "<Button-1>", lambda _e: self._ui(self._button))
        cv.tag_bind(self.btn_id, "<Enter>", lambda _e: self._paint_button(True))
        cv.tag_bind(self.btn_id, "<Leave>", lambda _e: self._paint_button(False))
        self.coin_lbl = cv.create_image(k(22), k(586), anchor="w")
        self._text_button(k(396), k(586), "확률 보기", self.toggle_odds)
        self._text_button(k(494), k(586), "닫기", self.close)
        self.odds_id = None
        # 여는 연출 층 (맨 위) - 빛 · 빛살은 도형 (색만 등급마다 바꾼다). 바탕은 캔버스 바탕 빛을 바꾸고 기계를
        # 통째로 숨긴다 (맥은 가려진 것도 다 칠한다 - 덮는 네모를 얹으면 그만큼 느리다)
        self.scene_ids = [i for i in cv.find_all() if i not in set(self.cap_ids)]
        self._scene_hidden = []
        self.ray_ids = [(cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="", state="hidden"), i, j)
                        for i in range(RAY_N) for j in range(len(RAY_A))]
        self.glow_ids = [(cv.create_polygon(*[v * s for v in pts], fill="", outline="", state="hidden"), n)
                         for pts, _c, n in ring_polys(CENTER[0], CENTER[1], [(r, None) for r, _a in GLOW], seg=32)]
        self.puff_id = cv.create_image(k(270), k(250), state="hidden")
        self.top_id = cv.create_image(k(270), k(250), state="hidden")
        self.bot_id = cv.create_image(k(270), k(250), state="hidden")
        self.chip_id = cv.create_image(k(270), k(250), state="hidden")
        self.reveal_id = cv.create_image(k(270), k(430), state="hidden")
        self.hint_id = cv.create_image(k(270), k(474), state="hidden")
        self.overlay = [self.puff_id, self.top_id, self.bot_id, self.chip_id, self.reveal_id,
                        self.hint_id] + [g[0] for g in self.glow_ids] + [r[0] for r in self.ray_ids]
        cv.bind("<Button-1>", self._click)
        self.spark_ph = self._photo("spark", art.spark)
        self.ph["puff"] = ImageTk.PhotoImage(art.puff)
        self._tier_ph = {}
        self.conf_ph = [self._photo("conf%d" % i, im) for i, im in enumerate(art.confetti)]
        self._paint_coin()
        self._say("손잡이를 돌려 캡슐을 뽑으세요. 한 번 %d 코인 · 꽝도 있어요." % COST, (200, 196, 230), 15)
        self.state = "idle"
        self._paint_button()
        self._draw_globe(force=True)
        self.last = time.perf_counter()
        self._late = self._nframe = 0
        self._tick()

    def _button_imgs(self):
        """단추 네 벌: 돌리기 · 돌리기(올림) · 못 누름 · 열기."""
        out = []
        k = self.art.k
        for top, bot, txt, label in (((255, 120, 160), (200, 30, 90), (255, 255, 255), "돌리기  ·  %d 코인" % COST),
                                     ((255, 150, 185), (224, 50, 110), (255, 255, 255), "돌리기  ·  %d 코인" % COST),
                                     ((120, 116, 140), (70, 66, 90), (200, 196, 214), "돌리기  ·  %d 코인" % COST),
                                     ((255, 226, 120), (226, 150, 30), (96, 40, 10), "캡슐 열기")):
            w, h = k(250) * SS, k(50) * SS
            im = Image.new("RGBA", (w, h + 6 * SS), (0, 0, 0, 0))
            sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((0, 6 * SS, w - 1, h + 6 * SS - 1), h // 2, fill=(0, 0, 0, 130))
            im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(3 * SS)))
            _paste_round(im, _vgrad(w, h, top, bot), (0, 0), h // 2)
            _comp_round(im, _light(w - 16 * SS, h // 2, 110), (8 * SS, 3 * SS), h // 4)
            t = _text(label, 20 * self.s * SS, fill=txt)
            im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
            out.append(im.resize((im.width // SS, im.height // SS), Image.LANCZOS))
        return out

    def _text_button(self, x, y, text, cmd):
        tid = self.cv.create_text(x, y, text=text, fill="#cfc9ef", font=U.FONT_B, anchor="center")
        self.cv.tag_bind(tid, "<Button-1>", lambda _e: self._ui(cmd))
        self.cv.tag_bind(tid, "<Enter>", lambda _e: self.cv.itemconfigure(tid, fill="#ffffff"))
        self.cv.tag_bind(tid, "<Leave>", lambda _e: self.cv.itemconfigure(tid, fill="#cfc9ef"))
        return tid

    def _ui(self, cmd):
        """단추 · 글 단추 · 확률표 누름 (캔버스 전체 누름(_click)이 같은 누름을 또 받지 않게 표시해 둔다)."""
        self._ui_click = True
        cmd()

    def _click(self, e):
        """캔버스 아무 데나 누름: 쉴 때 유리통 · 손잡이 = 돌리기, 배출되면 배출구 = 열기, 상품이면 닫기."""
        if self._ui_click:
            self._ui_click = False
            return
        if not self.art:
            return
        x, y = e.x / self.s, e.y / self.s
        if self.state == "idle" and self.odds_id is None:
            if math.hypot(x - GX, y - GY) < GR or math.hypot(x - KX, y - KY) < KR + 8:
                self._user_spin()
        elif self.state == "ready":
            if CHUTE[0] - 12 <= x <= CHUTE[2] + 12 and CHUTE[1] - 12 <= y <= CHUTE[3] + 12:
                self.open_capsule()
        elif self.state == "reveal":
            self._overlay_click()

    # ---------------- 글 · 단추
    def _say(self, text, col=(255, 255, 255), px=17, glow=None):
        if not self.art:
            return
        self.said = natural(text)
        self.cv.itemconfigure(self.msg_id, image="")
        self.ph["msg"] = ImageTk.PhotoImage(_text(self.said, px * self.s, fill=col, glow=glow))
        self.cv.itemconfigure(self.msg_id, image=self.ph["msg"])

    def _paint_coin(self):
        if not self.art:
            return
        self.cv.itemconfigure(self.coin_lbl, image="")
        self.ph["coin"] = ImageTk.PhotoImage(_text("보유 코인  %s" % format(self.coin, ","), 16 * self.s,
                                                   fill=(255, 214, 110)))
        self.cv.itemconfigure(self.coin_lbl, image=self.ph["coin"])

    def _paint_button(self, hover=False):
        if not self.art:
            return
        if self.state == "ready":
            idx = 3
        elif self.state != "idle" or self.coin < COST:
            idx = 2
        else:
            idx = 1 if hover else 0
        self.cv.itemconfigure(self.btn_id, image=self.btn_ph[idx])

    def _button(self):
        if self.state == "ready":
            return self.open_capsule()
        self._user_spin()

    def _user_spin(self):
        """사람이 누른 돌리기. 상품 · 확률표를 닫은 직후의 누름은 받지 않는다 - 닫으려고 두 번 누르거나 연타하면
        둘째 누름이 유리통 · 단추에 떨어져 결과도 못 본 채 20 코인이 나갔다 (11/03 검토)."""
        if time.perf_counter() < self._calm_until:
            return
        self.spin()

    # ---------------- 돌리기
    def spin(self):
        if not self.art or self.state != "idle" or not self.alive:
            return
        if self.coin < COST:
            return self._say("길드 코인이 모자랍니다 (%d 코인 필요)." % COST, (255, 140, 150), 16)
        self.state = "coin"
        self.result, self.err = None, None
        self.prize_art, self.prize_ready = None, False
        self.t0 = None                                     # 첫 틱에서 잰다 (쉬는 동안 틱은 90ms 마다라 앞이 잘렸다)
        self._close_odds()
        self.coin_before = self.coin
        self.coin -= COST                                  # 동전이 떠나는 순간 줄인다 (오류면 되돌린다)
        self._notified = False
        self._paint_coin()
        self._paint_button()
        self._say("짤랑!", (255, 226, 150), 17)
        self._coin_i, self._coin_done = None, False
        k = self.art.k
        self.cv.coords(self.coin_id, k(COIN_PATH[0][0]), k(COIN_PATH[0][1]))   # 처음엔 (0, 0) 에 있었다
        self.cv.itemconfigure(self.coin_id, image=self.coin_ph[0], state="normal")
        U.run_async(self.root, self.app.api.guild_slot, self._answer)

    def _answer(self, r, err):
        if not self.alive:
            # 다 보기 전에 창을 닫았어도 서버는 코인을 빼고 상품을 줬다 - 상점 · 가방은 다시 받게 한다
            if not err and r:
                self.coin = int(r.get("coin", self.coin))
                self._notify()
            elif err and not getattr(err, "status", 0):    # 통신 오류 - 서버가 처리했을 수도 있다
                self._notify()
            return
        if err:
            self.err = err
            return
        self.result = r or {}
        self.coin = int(self.result.get("coin", self.coin))
        if self.state in ("coin", "crank", "mix", "settle"):
            self._paint_coin()
        # 상품 그림은 지금 받아 둔다 (열 때 기다리지 않게)
        item = self.result.get("item")
        deco = self.result.get("deco")
        api = self.app.api

        def work():
            if deco:
                return item_icons.pil("deco:%s" % deco)
            if item:
                item_icons.raw(api, item)
                return item_icons.pil(item)
            return None

        def got(im, _e):
            self.prize_art = im                            # 못 받았으면 None - 칩만 보인다
            self.prize_ready = True
        U.run_async(self.root, work, got)

    def _tier(self):
        return (self.result or {}).get("tier") or "lose"

    def _tick(self):
        if not self.alive:
            return
        now = time.perf_counter()
        gap = now - self.last
        dt = min(0.05, gap)
        self._late = self._late + 1 if gap > 0.028 else 0
        self.last = now
        st = self.state
        busy = st not in ("idle", "loading")
        if st == "coin":
            self._tick_coin(now)
        elif st == "crank":
            self._tick_crank(now)
        elif st == "mix":
            self._tick_mix(now)
        elif st == "settle":
            self._tick_settle(now)
        elif st == "drop":
            self._tick_drop(now, dt)
        elif st == "ready":
            self._tick_ready(now)
        elif st == "open":
            self._tick_open(now)
        elif st == "reveal":
            busy = self._tick_reveal(now) or bool(self.parts)
        if self.globe_live:
            self._tick_globe(now, dt)
            busy = True
        if self.parts:
            self._tick_parts(dt)
            busy = True
        if busy:
            p = self.perf.setdefault(st, [0, 0.0])
            p[0] += 1
            p[1] += dt
        # 그리기가 틱 간격보다 오래 걸리는 느린 PC 에서는 다음 틱이 늘 밀려 있어 update() 가 안 돌아온다 (맥에서
        # 그림 두 장 길로 돌리면 검사가 멈췄다). 틀이 네 번 잇달아 늦으면 네 틀에 한 번은 한 틀 걸린 만큼 더 쉬어
        # 틈을 낸다. '늘 걸린 만큼 쉬기' 는 안 된다 - 맥은 화면 주기(16.7ms), 윈도우는 시계(15.6ms) 단위로 깨어나서
        # 쉰 시간이 매번 조금씩 늘어 끝없이 느려졌다 (2026-11-03 잼)
        self._nframe += 1
        if not busy:
            self._late = 0
            delay = IDLE_MS
        elif self._late >= 4 and self._nframe % 4 == 0:
            delay = min(80, int(gap * 1000) + 6)
        else:
            delay = FRAME_MS
        self.win.after(delay, self._tick)

    # 동전: 보유 코인에서 튀어 올라 빙글 돌며 구멍 위로 -> 옆으로 서서 구멍 속으로 -> 판 테가 금빛으로 번쩍
    def _tick_coin(self, now):
        if self.t0 is None:
            self.t0 = now
        k, t = self.art.k, now - self.t0
        (x0, y0), (x1, y1), (x2, y2) = COIN_PATH
        if t < COIN_FLY:
            u = _smooth(t / COIN_FLY)
            x = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * x1 + u * u * x2
            y = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * y1 + u * u * y2
            th = 90 + 720 * (u - 1)                        # 두 바퀴 돌아 끝에는 옆으로 선다
            i = int(round((th % 180) / (180.0 / N_COIN))) % N_COIN
        elif t < COIN_FLY + COIN_IN:
            u = (t - COIN_FLY) / COIN_IN
            x, y, i = x2, y2 + 44 * u * u, N_COIN // 2
        else:
            if not self._coin_done:
                self._coin_done = True
                self.cv.itemconfigure(self.coin_id, state="hidden")
                self.cv.itemconfigure(self.slot_rim, outline="#ffd65a", width=2.6 * self.s)
                self._say("딸깍!", (255, 226, 150), 17)
            if t >= COIN_FLY + COIN_IN + COIN_CLICK:
                self.cv.itemconfigure(self.slot_rim, outline="#6e0c22", width=1.5 * self.s)
                self.state, self.t0 = "crank", now
                self._say("드르륵...", (230, 226, 255), 17)
            return
        self.cv.coords(self.coin_id, k(x), k(y))
        if i != self._coin_i:
            self._coin_i = i
            self.cv.itemconfigure(self.coin_id, image=self.coin_ph[i])

    def _tick_crank(self, now):
        u = (now - self.t0) / CRANK_SEC
        self._set_knob(int(round(_smooth(u) * N_KNOB)) % N_KNOB)
        if u >= 1.0:
            self._set_knob(0)
            self.state, self.t_mix = "mix", now
            self.art.globe.respawn()
            self.globe_live, self.calm_since, self.quiet_at = True, None, None
            self._say("와르르! 캡슐이 섞이는 중...", (230, 226, 255), 17)

    def _tick_mix(self, now):
        if now - self.t_mix < MIX_MIN:
            return
        if self.err is not None or (self.result is not None and self.prize_ready):
            self.state, self.t_settle = "settle", now
            self._sink_gone_at = None

    def _power(self, now):
        if self.state == "mix":
            return min(1.0, (now - self.t_mix) / 0.25)
        if self.state == "settle":
            return max(0.0, 1.0 - (now - self.t_settle) / 0.3)
        return 0.0

    def _tick_settle(self, now):
        gl, t = self.art.globe, now - self.t_settle
        if self.err is not None:                           # 오류: 쌓이기만 하고 멈춘다
            if t >= 0.9:
                self.state = "idle"
                self.coin = self.coin_before
                self._paint_coin()
                if getattr(self.err, "status", 0):          # 서버가 거절했다 (코인 모자람 등) - 안 빠졌다
                    msg = getattr(self.err, "message", None) or str(self.err)
                    self._say(msg or "뽑지 못했습니다. 코인은 그대로입니다.", (255, 140, 150), 15)
                else:                                       # 시간 초과 · 연결 끊김: 서버는 이미 뽑았을 수도 있다
                    self._say("결과를 확인하지 못했습니다. 가방과 코인을 확인해 주세요.", (255, 140, 150), 15)
                self._notify()                             # 어느 쪽이든 상점 · 가방을 서버에서 다시 받게 (11/03 검토)
                self._paint_button()
            return
        if gl.sink is None:
            if t >= 0.5:
                gl.choose_sink()
            return
        if gl.sink in gl.gone:
            if self._sink_gone_at is None:
                self._sink_gone_at = now
            elif now - self._sink_gone_at >= 0.12:
                self._start_drop(now)

    def _tick_globe(self, now, dt):
        """유리통을 한 틀 굴린다. 바람이 그치고 빠질 캡슐도 빠진 뒤, 틀마다 움직임이 0.35px 아래로 0.3초 이어지면
        멈춘다 (멈추면 다시 그리지 않는다 - 맥은 그릴 때마다 캔버스 전체를 칠한다). 그래도 2.5초면 그 자리에서 멈춘다."""
        gl = self.art.globe
        P = self._power(now)
        moved = gl.step(dt, P)
        self._draw_globe()
        waiting = self.state == "settle" and self.err is None and gl.sink is None     # 곧 하나가 빠진다
        if P > 0 or self.state == "mix" or waiting or (gl.sink is not None and gl.sink not in gl.gone):
            self.calm_since = self.quiet_at = None
            return
        if self.quiet_at is None:
            self.quiet_at = now
        if moved < 0.35:
            if self.calm_since is None:
                self.calm_since = now
            elif now - self.calm_since > 0.3:
                self.globe_live = False                    # 쌓였다 - 이제 안 그린다
        else:
            self.calm_since = None
        if now - self.quiet_at > 2.5:
            self.globe_live = False

    def _draw_globe(self, force=False):
        k, gl, cv = self.art.k, self.art.globe, self.cv
        for i, b in enumerate(gl.b):
            it, last = self.cap_ids[i], self._cap_drawn[i]
            hide = self._globe_hidden or i in gl.gone
            if hide:
                if force or last is None or not last[3]:
                    cv.itemconfigure(it, state="hidden")
                    self._cap_drawn[i] = (last[0], last[1], last[2], True) if last else (0, 0, None, True)
                continue
            x, y = b[0] * self.s, b[1] * self.s
            img = self.cap_ph[b[6]][int(round(b[4] / (360.0 / N_ANG))) % N_ANG]
            if force or last is None or last[3]:
                cv.itemconfigure(it, state="normal", image=img)
                cv.coords(it, x, y)
                self._cap_drawn[i] = (x, y, img, False)
                continue
            moved = abs(x - last[0]) >= 0.5 or abs(y - last[1]) >= 0.5
            if moved:
                cv.coords(it, x, y)
            if img is not last[2]:
                cv.itemconfigure(it, image=img)
            if moved or img is not last[2]:
                self._cap_drawn[i] = (x if moved else last[0], y if moved else last[1], img, False)

    def _set_knob(self, i):
        if self._knob_i != i:
            self._knob_i = i
            self.cv.itemconfigure(self.knob_id, image=self.knob_ph[i])

    def _set_flap(self, i):
        if self._flap_i != i:
            self._flap_i = i
            self.cv.itemconfigure(self.flap_id, image=self.flap_ph[i])

    # 배출: 덮개를 밀고 나와 떨어져 통통 튀고 굴러가 멈춘다 (구르는 만큼 돈다)
    def _start_drop(self, now):
        self.state, self.t0 = "drop", now
        self.dropst = {"x": float(DROP_X0), "y": float(DROP_Y0), "vx": 40.0, "vy": 30.0, "ang": 0.0, "floor": False}
        self._drop_drawn = None
        self.cv.itemconfigure(self.drop_id, state="normal", image=self.drop_ph[self._tier()][0])
        self._place_drop(0.0)
        self._say("덜컥! 캡슐이 나왔어요.", (255, 236, 200), 17)

    def _place_drop(self, extra_ang, lift=0.0):
        d, k = self.dropst, self.art.k
        i = int(round((d["ang"] + extra_ang) / (360.0 / N_DROP))) % N_DROP
        x, y = d["x"] * self.s, (d["y"] - lift) * self.s
        last = self._drop_drawn
        if last is None or abs(x - last[0]) >= 0.5 or abs(y - last[1]) >= 0.5:
            self.cv.coords(self.drop_id, x, y)
            last = (x, y, last[2] if last else None)
        if last[2] != i:
            self.cv.itemconfigure(self.drop_id, image=self.drop_ph[self._tier()][i])
            last = (last[0], last[1], i)
        self._drop_drawn = last

    def _tick_drop(self, now, dt):
        d, t = self.dropst, now - self.t0
        lo, hi = CHUTE[0] + DROP_R + 3, CHUTE[2] - DROP_R - 3
        h = dt / 2.0
        for _i in range(2):
            d["vy"] += 1900.0 * h
            d["x"] += d["vx"] * h
            d["y"] += d["vy"] * h
            if d["y"] >= TRAY_Y:
                d["y"] = TRAY_Y
                if d["vy"] > 110:
                    d["vy"] = -d["vy"] * 0.36
                    d["vx"] *= 0.86
                else:
                    d["vy"], d["floor"] = 0.0, True
            if d["floor"]:
                d["vx"] *= math.exp(-2.6 * h)
            if d["x"] > hi:
                d["x"], d["vx"] = hi, -abs(d["vx"]) * 0.45
            elif d["x"] < lo:
                d["x"], d["vx"] = lo, abs(d["vx"]) * 0.45
            d["ang"] += d["vx"] * h / DROP_R * 57.2958
        self._place_drop(0.0)
        for until, f in ((0.05, 0), (0.1, 1), (0.16, 2), (0.34, 3), (0.4, 2), (0.46, 1), (0.52, 0), (0.58, 1)):
            if t < until:
                self._set_flap(f)
                break
        else:
            self._set_flap(0)
        if d["floor"] and abs(d["vx"]) < 3 and t > 0.62:
            self._set_flap(0)
            self.state, self.t0 = "ready", now
            self._paint_button()
            self._say("캡슐을 눌러 열어 보세요!", (255, 236, 200), 18, ((255, 170, 90), 5 * self.s))

    def _tick_ready(self, now):
        t = now - self.t0
        c = t % 1.3                                        # 1.3초마다 들썩
        if c < 0.6:
            f = 1 - c / 0.6
            self._place_drop(16 * math.sin(c / 0.6 * math.pi * 3) * f, 3 * abs(math.sin(c / 0.6 * math.pi * 3)) * f)
        else:
            self._place_drop(0.0)
        if t >= AUTO_OPEN:
            self.open_capsule()

    # ---------------- 열기
    def open_capsule(self):
        if self.state != "ready":
            return
        art, k = self.art, self.art.k
        tier = self._tier()
        self.state, self.t0 = "open", time.perf_counter()
        self.cv.itemconfigure(self.drop_id, state="hidden")
        self._paint_button()
        self._overlay_blank()                              # 앞판 그림을 가리키던 칸부터 비운다 (그 그림이 지워진다)
        self._globe_hidden = True                          # 기계를 통째로 숨기고 바탕 빛만 바꾼다
        self._draw_globe()
        self._scene_hidden = [i for i in self.scene_ids if self.cv.itemcget(i, "state") != "hidden"]
        for i in self._scene_hidden:
            self.cv.itemconfigure(i, state="hidden")
        self.cv.configure(bg=_hex(BACKDROP))
        glow = TIER.get(tier, TIER["lose"])[2]
        for it, n in self.glow_ids:
            a = GLOW[n][1] * (0.55 if tier == "lose" else 1.0)
            self.cv.itemconfigure(it, fill=_hex(_mix(BACKDROP, glow, a)), state="normal")
        for it, _i, j in self.ray_ids:
            self.cv.itemconfigure(it, fill=_hex(_mix(BACKDROP, glow, RAY_A[j])))
        self._place_rays(0.0)
        for it in [g[0] for g in self.glow_ids] + [self.puff_id, self.top_id, self.bot_id, self.chip_id,
                                                    self.reveal_id, self.hint_id]:
            self.cv.tag_raise(it)
        got = self._tier_ph.get(tier)
        if got is None:                                    # 등급마다 한 번만 만든다
            b = art.big[tier]
            got = self._tier_ph[tier] = ([ImageTk.PhotoImage(im) for im in b["pop"]],
                                         [ImageTk.PhotoImage(im) for im in b["shake"]],
                                         tuple(ImageTk.PhotoImage(im) for im in art.halves[tier]))
        self.pop_ph, self.big_ph, self.half_ph = got
        self.cv.coords(self.top_id, k(CENTER[0]), k(CENTER[1]))
        self.cv.itemconfigure(self.top_id, image=self.pop_ph[0], state="normal")
        self._shake = None
        chip = prize_chip(self.s, tier if tier != "lose" else "lose",
                          None if tier == "lose" else (_egg(70 * self.s) if (self.result or {}).get("egg")
                                                       else getattr(self, "prize_art", None)))
        self.chip_sizes = [self._photo("chip%d" % i, chip.resize((max(1, int(chip.width * f)),
                                                                   max(1, int(chip.height * f))), Image.LANCZOS))
                           for i, f in enumerate((0.45, 0.75, 1.1, 1.0))]
        self._say("", px=10)

    def _place_rays(self, rot):
        k, cx, cy = self.art.k, CENTER[0], CENTER[1]
        half_w = math.radians(4.6)
        for it, i, j in self.ray_ids:
            a = math.radians(rot + i * 360.0 / RAY_N)
            r0, r1 = RAY_R[j], RAY_R[j + 1]
            pts = []
            for rr, aa in ((r0, a - half_w), (r1, a - half_w), (r1, a + half_w), (r0, a + half_w)):
                pts += [k(cx + math.cos(aa) * rr), k(cy + math.sin(aa) * rr)]
            self.cv.coords(it, *pts)

    def _tick_open(self, now):
        """튀어 오름 0.16초 -> 흔들림 0.46초 -> 갈라짐 0.45초."""
        k = self.art.k
        t = now - self.t0
        tier = self._tier()
        if t < 0.16:
            i = ("p", 0) if t < 0.08 else ("p", 1)
            if i != self._shake:
                self._shake = i
                self.cv.itemconfigure(self.top_id, image=self.pop_ph[i[1]])
            return
        if t < 0.62:
            seq = (2, 1, 0, 1, 2, 3, 4, 3, 2)
            i = ("s", seq[int((t - 0.16) / 0.055) % len(seq)])
            if i != self._shake:
                self._shake = i
                self.cv.itemconfigure(self.top_id, image=self.big_ph[i[1]])
            return
        if not getattr(self, "_split", False):
            self._split = True
            self.cv.itemconfigure(self.top_id, image=self.half_ph[0])
            self.cv.itemconfigure(self.bot_id, image=self.half_ph[1], state="normal")
            if tier == "lose":
                self.cv.itemconfigure(self.puff_id, image=self.ph["puff"], state="normal")
            else:
                for it, _i, _j in self.ray_ids:
                    self.cv.itemconfigure(it, state="normal")
                for it, _n in self.glow_ids:
                    self.cv.tag_raise(it)
            for it in (self.puff_id, self.top_id, self.bot_id, self.chip_id, self.reveal_id, self.hint_id):
                self.cv.tag_raise(it)
        u = min(1.0, (t - 0.62) / 0.45)
        e = 1 - (1 - u) ** 3
        ch = self.half_ph[0].height()                     # 반쪽 높이 - 가운데 기준이라 반만큼 올리고 내린다
        self.cv.coords(self.top_id, k(CENTER[0]) - e * k(110), k(CENTER[1]) - ch // 2 - e * k(120))
        self.cv.coords(self.bot_id, k(CENTER[0]) + e * k(110), k(CENTER[1]) + ch // 2 + e * k(150))
        if u >= 1.0:
            self.cv.itemconfigure(self.top_id, state="hidden")
            self.cv.itemconfigure(self.bot_id, state="hidden")
            self._split = False
            self.state, self.t0 = "reveal", now
            self._rev = None
            if tier != "lose":                             # 꽝은 칩 없이 잿빛 연기만
                self.cv.itemconfigure(self.chip_id, image=self.chip_sizes[0], state="normal")
                self.cv.tag_raise(self.chip_id)
            r = self.result or {}
            if tier == "lose":
                text, col, glow = "꽝! 다음에는 맞을 거예요.", (210, 206, 226), None
            else:
                text = self._prize_text(r)
                col = {"common": (255, 255, 255), "rare": (240, 226, 255), "epic": (255, 236, 170),
                       "jackpot": (255, 236, 244)}.get(tier, (255, 255, 255))
                glow = {"rare": ((190, 120, 255), 6 * self.s), "epic": ((255, 190, 60), 7 * self.s),
                        "jackpot": ((255, 90, 140), 9 * self.s)}.get(tier)
            self.said = natural(text)
            self.ph["reveal"] = ImageTk.PhotoImage(_text(self.said, (24 if tier == "jackpot" else 21) * self.s,
                                                         fill=col, glow=glow))
            self.cv.itemconfigure(self.reveal_id, image=self.ph["reveal"], state="normal")
            self.ph["hint"] = ImageTk.PhotoImage(_text("아무 데나 누르면 닫힙니다", 13 * self.s, fill=(190, 186, 214),
                                                       black=False))
            self.cv.itemconfigure(self.hint_id, image=self.ph["hint"], state="normal")
            for it in (self.reveal_id, self.hint_id):
                self.cv.tag_raise(it)
            self._celebrate(tier)
            self._notify()

    def _tick_reveal(self, now):
        """칩이 튀어나오고 빛살이 천천히 돈다 - 2.5초 뒤에는 멈춰 둔다 (누를 때까지 창을 계속 다시 그리지 않게)."""
        t = now - self.t0
        if self._tier() == "lose" or t > 2.5:
            return False
        i = min(3, int(t / 0.07))
        if i != self._rev:
            self._rev = i
            self.cv.itemconfigure(self.chip_id, image=self.chip_sizes[i])
        self._place_rays(t * 14.0)
        return True

    def _overlay_click(self):
        if self.state == "reveal" and time.perf_counter() - self.t0 > 0.35:
            self._close_overlay()

    def _overlay_blank(self):
        for it in self.overlay:
            self.cv.itemconfigure(it, state="hidden")
        for it in (self.puff_id, self.top_id, self.bot_id, self.chip_id, self.reveal_id, self.hint_id):
            self.cv.itemconfigure(it, image="")

    def _close_overlay(self):
        self._overlay_blank()
        for p in self.parts:
            self.cv.delete(p["id"])
        self.parts = []
        self.cv.configure(bg=_hex(BASE))
        for i in self._scene_hidden:
            self.cv.itemconfigure(i, state="normal")
        self._scene_hidden = []
        self._globe_hidden = False
        self._draw_globe(force=True)
        self.state = "idle"
        self._calm_until = time.perf_counter() + CALM_SEC
        self._paint_button()
        self._say("한 번 더? 한 번 %d 코인." % COST if self.coin >= COST else "코인이 모자랍니다.",
                  (200, 196, 230), 15)

    def _prize_text(self, r):
        if r.get("egg"):
            return "대박! %s!" % r["egg"].get("kr", "알")
        if r.get("deco"):
            return "꾸미기 '%s' 획득!" % (r.get("decoKr") or r["deco"])
        if r.get("prize") == "deco" and r.get("item"):
            return "꾸미기는 다 있어서 %s x%d" % (r.get("itemKr") or r["item"], int(r.get("count") or 1))
        if r.get("item"):
            pre = "대박! " if r.get("tier") == "jackpot" else ""
            return "%s%s x%d" % (pre, r.get("itemKr") or r["item"], int(r.get("count") or 1))
        return r.get("message") or r.get("kr") or "당첨!"

    def _celebrate(self, tier):
        k = self.art.k
        n = {"lose": 0, "common": 8, "rare": 18, "epic": 28, "jackpot": 40}.get(tier, 0)
        for i in range(n):
            a = (i / float(max(1, n))) * math.tau + random.uniform(-0.2, 0.2)
            sp = random.uniform(160, 380) * self.s
            pid = self.cv.create_image(k(CENTER[0]), k(CENTER[1]), image=self.spark_ph)
            self.parts.append({"id": pid, "vx": math.cos(a) * sp, "vy": math.sin(a) * sp - 60 * self.s,
                               "g": 420 * self.s, "life": 1.2, "age": 0.0})
        if tier == "jackpot":
            for _i in range(70):
                pid = self.cv.create_image(random.uniform(0, k(W)), random.uniform(-k(220), 0),
                                           image=random.choice(self.conf_ph))
                self.parts.append({"id": pid, "vx": random.uniform(-40, 40) * self.s,
                                   "vy": random.uniform(120, 260) * self.s, "g": 0, "life": 3.2, "age": 0.0,
                                   "sway": random.uniform(0, 6.28)})
        self.last_fx = {"tier": tier, "parts": n + (70 if tier == "jackpot" else 0)}

    def _tick_parts(self, dt):
        keep = []
        for p in self.parts:
            p["age"] += dt
            if p["age"] >= p["life"]:
                self.cv.delete(p["id"])
                continue
            p["vy"] += p["g"] * dt
            dx = p["vx"] * dt + (math.sin(p["sway"] + p["age"] * 5) * 30 * self.s * dt if "sway" in p else 0)
            self.cv.move(p["id"], dx, p["vy"] * dt)
            keep.append(p)
        self.parts = keep

    # ---------------- 확률표
    def _close_odds(self):
        if self.odds_id is not None:
            self.cv.delete(self.odds_id)
            self.odds_id = None
            self._calm_until = time.perf_counter() + CALM_SEC

    def toggle_odds(self):
        if not self.art or self.state not in ("idle",):
            return
        if self.odds_id is not None:
            return self._close_odds()
        if not self.odds:
            return self._say("확률표를 받지 못했습니다.", (255, 140, 150), 15)
        k = self.art.k
        w, h = k(300), k(34 + 21 * len(self.odds))
        im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        _paste_round(im, Image.new("RGBA", im.size, (14, 10, 30, 240)), (0, 0), k(16) * SS)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), k(16) * SS, outline=GOLD[1] + (255,), width=2 * SS)
        f, fb = _font(14 * self.s * SS, False), _font(15 * self.s * SS, True)
        d.text((k(16) * SS, k(10) * SS), "한 번 %d 코인 · 확률" % COST, font=fb, fill=(255, 214, 110, 255))
        for i, o in enumerate(self.odds):
            y = (k(36) + i * k(21)) * SS
            col = TIER.get(o.get("tier") or "lose", TIER["lose"])[2]
            d.ellipse((k(16) * SS, y + k(5) * SS, k(24) * SS, y + k(13) * SS), fill=col + (255,))
            d.text((k(32) * SS, y), str(o.get("kr") or o.get("key")), font=f, fill=(236, 232, 250, 255))
            pct = "%g%%" % float(o.get("pct") or 0)
            d.text((im.width - k(18) * SS - d.textlength(pct, font=f), y), pct, font=f, fill=(236, 232, 250, 255))
        self.ph["odds"] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
        self.odds_id = self.cv.create_image(k(270), k(250), image=self.ph["odds"])
        self.cv.tag_bind(self.odds_id, "<Button-1>", lambda _e: self._ui(self._close_odds))

    def _notify(self):
        """상점에 알린다 (코인 · 가방이 바뀌었다) - 한 판에 한 번. 상품이 뜰 때, 그 전에 창이 닫히면 닫힐 때나
        답이 왔을 때 (11/03 검토: 섞는 중에 닫으면 상점이 옛 코인을 들고 있다가 다시 열 때 그 값으로 열었다)."""
        if self._notified or not self.on_change:
            return
        self._notified = True
        try:
            self.on_change(self.coin)
        except Exception:                                   # noqa: BLE001
            config.log("랜덤 캡슐 뒤 상점 갱신 실패")

    def _gone(self):
        if not self.alive:
            return
        self.alive = False
        self.parts = []
        if self.result is not None and self.err is None:
            self._notify()                                 # 답은 왔는데 상품을 다 보기 전에 닫았다 (아직이면 _answer 가)

    def close(self):
        self._gone()
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def open_gacha(app, parent, coin, odds, on_change=None):
    """창 하나만 띄운다 (이미 떠 있으면 앞으로)."""
    old = getattr(app, "_gacha_win", None)
    if old is not None and old.alive:
        try:
            if old.state in ("idle", "loading") and coin is not None:   # 그사이 상점 코인이 바뀌었으면 따른다
                old.coin = int(coin or 0)
                old._paint_coin()
                old._paint_button()
            if odds:
                old.odds = list(odds)
            old.win.lift()
            old.win.focus_force()
            return old
        except tk.TclError:
            pass
    app._gacha_win = GachaWindow(app, parent, coin, odds, on_change)
    return app._gacha_win


# ---------------------------------------------------------------- 코인 상점 맨 위의 띠
class Banner(object):
    """코인 상점 맨 위에 까는 랜덤 캡슐 띠 (기본 · DP 테마가 같이 쓴다). 누르면 뽑기 창.

    상점 머리(코인 수 · 찾기 칸)는 테마마다 따로 짜여 있어서 거기에 끼우지 않고 한 줄을 따로 둔다.
    shop() = 지금 상점 자료 (coin · slot.odds), on_change(coin) = 뽑은 뒤 상점을 다시 받게."""

    HEIGHT = 66

    def __init__(self, parent, app, shop, on_change, bg):
        self.app, self.shop, self.on_change = app, shop, on_change
        self.s = U.h(100) / 100.0
        self.cv = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, height=int(self.HEIGHT * self.s),
                            cursor="hand2")
        self.cv.bind("<Configure>", lambda e: self._paint(e.width))
        self.cv.bind("<Button-1>", lambda _e: self.open())
        self.cv.bind("<Enter>", lambda _e: self._paint(self.cv.winfo_width(), True))
        self.cv.bind("<Leave>", lambda _e: self._paint(self.cv.winfo_width(), False))
        self.ph = None
        self._w = 0

    def pack(self, **kw):
        self.cv.pack(**kw)
        return self

    def _paint(self, w, hover=False):
        if w <= 2:
            return
        self._w = w
        self.ph = ImageTk.PhotoImage(banner_image(w, int(self.HEIGHT * self.s), self.s, hover))
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self.ph)

    def open(self):
        sh = self.shop() or {}
        slot = sh.get("slot") or {}
        open_gacha(self.app, self.cv.winfo_toplevel(), sh.get("coin") or 0, slot.get("odds"), self.on_change)


def banner_image(w, h, s, hover=False):
    """띠 그림: 자홍 -> 보라 넘김, 왼쪽에 캡슐 셋, 가운데 글, 오른쪽 알약 단추."""
    W2, H2 = w * SS, h * SS
    im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    top, bot = ((214, 56, 132), (92, 38, 168)) if not hover else ((236, 76, 152), (112, 52, 192))
    col = Image.new("RGBA", (W2, 1))
    for x in range(W2):
        t = x / float(max(1, W2 - 1))
        col.putpixel((x, 0), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    r = int(14 * s * SS)
    _paste_round(im, col.resize((W2, H2), Image.NEAREST), (0, 0), r)
    _comp_round(im, _light(W2, H2 // 2, 70), (0, 0), r)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, W2 - 1, H2 - 1), r, outline=GOLD[1] + (255,),
                                         width=max(2, int(1.5 * s * SS)))
    rnd = random.Random(3)
    for _i in range(10):
        g = _glow((int(14 * s * SS),) * 2, (255, 240, 200), int(4 * s * SS))
        im.alpha_composite(g, (rnd.randint(0, max(1, W2 - g.width)), rnd.randint(0, max(1, H2 - g.height))))
    x = int(14 * s * SS)
    for i, (tier, dy) in enumerate((("common", 6), ("jackpot", -4), ("rare", 6))):
        c = capsule(15 * s * SS, tier)
        im.alpha_composite(c, (x + i * int(26 * s * SS), (H2 - c.height) // 2 + int(dy * s)))
    x += int(26 * s * SS) * 2 + c.width + int(10 * s * SS)
    t1 = _text("랜덤 캡슐", 19 * s * SS, fill=(255, 250, 236), glow=((255, 140, 200), 5 * s * SS))
    t2 = _text("한 번 %d 코인 · 아주 낮은 확률로 이로치 사탕 · 전설 알 · 꾸미기" % COST, 12.5 * s * SS,
               fill=(255, 226, 240), black=False)
    bw = int(116 * s * SS)
    room = W2 - x - bw - int(28 * s * SS)
    im.alpha_composite(t1, (x - int(6 * s * SS), int(6 * s * SS)))
    if t2.width <= room:
        im.alpha_composite(t2, (x, int(38 * s * SS)))
    bh = int(36 * s * SS)
    pill = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    _paste_round(pill, _vgrad(bw, bh, GOLD[0], GOLD[1]), (0, 0), bh // 2)
    tb = _text("뽑으러 가기", 14 * s * SS, fill=(96, 40, 10))
    pill.alpha_composite(tb, ((bw - tb.width) // 2, (bh - tb.height) // 2))
    im.alpha_composite(pill, (W2 - bw - int(14 * s * SS), (H2 - bh) // 2))
    return im.resize((w, h), Image.LANCZOS)
