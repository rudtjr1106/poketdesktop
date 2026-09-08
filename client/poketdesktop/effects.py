# -*- coding: utf-8 -*-
"""풀숲과 몬스터볼 그림을 직접 그린다.

게임에서 뜯어온 이미지를 쓰지 않고 코드로 그린다.
- 저작권 문제가 없다
- 파일을 같이 배포할 필요가 없다
- 크기를 바꿔도 늘 또렷하다
"""
import math

from PIL import Image, ImageDraw

from . import platform_os as PLAT

_FONT_CACHE = {}


def pil_font(size, bold=False):
    """한글이 실제로 그려지는 PIL 글꼴 하나.

    PIL 은 Tk 과 다르다. Tk 은 글꼴 **이름**("맑은 고딕")을 받고 없으면
    조용히 딴 것으로 바꿔 주지만, PIL 은 글꼴 **파일**("malgun.ttf")을
    찾고 없으면 OSError 를 낸다. 그걸 그냥 넘기면 load_default() 로
    떨어지는데, 그 글꼴에는 한글이 없어서 글자가 통째로 두부(□)가 된다.

    맥 기본 글꼴은 .ttc 라 굵기 여러 벌이 한 파일에 들어 있다. 몇 번째가
    Bold 인지는 OS 판마다 다르므로 번호를 박지 않고 이름으로 찾는다.
    """
    size = max(1, int(size))
    ck = (size, bool(bold))
    if ck in _FONT_CACHE:
        return _FONT_CACHE[ck]
    from PIL import ImageFont
    got = None
    for name in PLAT.pil_font_files(bold):
        try:
            f = ImageFont.truetype(name, size)
        except Exception:                                   # noqa: BLE001
            continue
        if bold and f.getname()[1] != "Bold":
            for i in range(1, 20):
                try:
                    g = ImageFont.truetype(name, size, index=i)
                except Exception:                           # noqa: BLE001
                    break                    # 범위를 넘으면 여기서 끝난다
                fam, sty = g.getname()
                if sty == "Bold" and not fam.startswith("."):
                    f = g                    # '.' 로 시작하면 내부용이다
                    break
        got = f
        break
    if got is None:
        got = ImageFont.load_default()       # 여기까지 오면 한글은 두부다
    _FONT_CACHE[ck] = got
    return got

GRASS_DARK = (34, 102, 46)
GRASS_MID = (58, 148, 62)
GRASS_LIGHT = (108, 194, 88)
GRASS_SHADOW = (22, 68, 34)

BALL_RED = (228, 62, 62)
BALL_WHITE = (246, 246, 250)
BALL_LINE = (26, 26, 32)
BALL_GREY = (186, 186, 198)

# 볼마다 위쪽 색이 다르다. 어떤 볼을 던졌는지 눈으로 알 수 있어야 한다.
# 본가 색을 눈대중으로 옮긴 것이라 정확한 값은 아니다.
BALL_TOP = {
    "POKEBALL": (228, 62, 62),
    "PREMIERBALL": (246, 246, 250),      # 흰 볼. 띠만 붉다
    "GREATBALL": (48, 108, 208),
    "ULTRABALL": (246, 200, 60),
    "MASTERBALL": (126, 62, 176),
    "HEALBALL": (240, 150, 190),
    "NETBALL": (56, 158, 160),
    "NESTBALL": (150, 190, 70),
    "DUSKBALL": (70, 74, 86),
    "TIMERBALL": (232, 232, 236),
    "QUICKBALL": (70, 160, 220),
    "REPEATBALL": (236, 168, 60),
    "LUXURYBALL": (46, 46, 54),
    "LEVELBALL": (226, 106, 70),
    "LOVEBALL": (240, 138, 176),
    "MOONBALL": (60, 76, 140),
    "FRIENDBALL": (110, 190, 120),
    "FASTBALL": (238, 196, 78),
    "HEAVYBALL": (84, 106, 140),
    "DREAMBALL": (232, 158, 208),
    "FLOWERBALL": (240, 138, 176),
}

# 위쪽에 한 줄 더 긋는 볼. 흰 볼끼리 구분이 안 되는 것을 막는다.
BALL_STRIPE = {
    "PREMIERBALL": (228, 62, 62),
    "TIMERBALL": (60, 60, 68),
    "LUXURYBALL": (214, 176, 92),
    "MASTERBALL": (238, 150, 200),
    "FLOWERBALL": (250, 206, 224),
}

# 위쪽에 작은 꽃을 하나 더 그리는 볼. 분홍 볼끼리(하트볼·드림볼) 색만으로는
# 구분이 안 돼서, 22px 에서도 알아볼 표식을 얹는다.
BALL_BLOOM = ("FLOWERBALL",)


def _blade(d, x, base_y, h, lean, w, color):
    """풀 한 포기. lean 이 클수록 옆으로 눕는다."""
    tip_x = x + lean
    tip_y = base_y - h
    mid_x = x + lean * 0.35
    mid_y = base_y - h * 0.55
    d.polygon([(x - w, base_y), (x + w, base_y), (mid_x + w * 0.6, mid_y),
               (tip_x, tip_y), (mid_x - w * 0.6, mid_y)], fill=color)


# 꽃이 핀 풀숲에 쓰는 색.
PETAL = (236, 130, 170)
PETAL_HI = (250, 176, 200)
PETAL_DIM = (198, 104, 142)      # 뒤쪽 포기의 꽃. 조금 어두워야 멀어 보인다
PETAL_CORE = (252, 246, 232)

# 풀 포기 (x비율, 높이비율, 두께비율, 기우는 세기). 겹마다 나눠 둔다.
_BLADES = (
    (GRASS_DARK, 0.11, [(0.20, 0.62, 0.045, -1), (0.50, 0.74, 0.050, +1),
                        (0.80, 0.60, 0.045, -1)]),
    (GRASS_MID, 0.15, [(0.33, 0.80, 0.055, -1), (0.66, 0.86, 0.055, +1)]),
    (GRASS_LIGHT, 0.18, [(0.44, 0.95, 0.060, +1), (0.58, 0.70, 0.050, -1)]),
)

# 어느 포기의 줄기 어디에 꽃을 달까. (겹, 포기 번호, 줄기 위치 0~1, 크기비율)
# 줄기 위치는 0 이 뿌리, 1 이 끝이다. **끝에 달면 안 된다** - 제일 높은
# 포기 끝이 그림 위쪽 끝이라 꽃이 잘려 나간다. 중간에 달면 머리 공간이
# 남아서 크게 그릴 수 있고, 얹어 놓은 것이 아니라 풀숲에서 핀 것으로 읽힌다.
_BLOOMS = [
    (0, 0, 0.55, 0.17), (0, 2, 0.58, 0.16),
    (1, 0, 0.62, 0.21), (1, 1, 0.46, 0.19),
    (2, 0, 0.50, 0.22), (2, 0, 0.26, 0.17), (2, 1, 0.60, 0.20),
]


def _stem_point(w, h, size, base, blade, t, ph, lean_mul):
    """포기의 줄기에서 t 지점(0 뿌리 ~ 1 끝)의 좌표.

    _blade 가 그리는 다각형을 그대로 따라간다 - 뿌리에서 중간(0.55)까지와
    중간에서 끝까지가 기우는 정도가 달라서, 직선으로 이으면 어긋난다.
    """
    bx, bh, _bw, sign = blade
    x0 = w * bx
    lean = ph * size * lean_mul * sign
    mid_x, mid_y = x0 + lean * 0.35, base - h * bh * 0.55
    tip_x, tip_y = x0 + lean, base - h * bh
    if t <= 0.55:
        k = t / 0.55
        return x0 + (mid_x - x0) * k, base + (mid_y - base) * k
    k = (t - 0.55) / 0.45
    return mid_x + (tip_x - mid_x) * k, mid_y + (tip_y - mid_y) * k


def _petal_flower(d, cx, cy, r, ph, petal, hi):
    """다섯 장짜리 꽃 하나. ph 로 살짝 돌려 풀과 흔들림 결을 맞춘다."""
    r = max(2.0, r)
    for i in range(5):
        a = ph * 0.22 + i * (2 * math.pi / 5) - math.pi / 2
        px = cx + math.cos(a) * r * 0.60
        py = cy + math.sin(a) * r * 0.60
        d.ellipse((px - r * 0.55, py - r * 0.55, px + r * 0.55, py + r * 0.55),
                  fill=hi if i in (0, 4) else petal)
    d.ellipse((cx - r * 0.28, cy - r * 0.28, cx + r * 0.28, cy + r * 0.28),
              fill=PETAL_CORE)


def grass_frames(size=48, frames=4, key=(255, 0, 255), bloom=False):
    """흔들리는 풀숲. 배경은 투명색으로 채워서 그대로 창에 올릴 수 있다.

    bloom 이면 줄기에 꽃이 핀 판을 그린다. 풀 배치와 흔들림은 한 픽셀도
    안 바뀌므로 평소 풀숲과 **같은 물건**으로 읽힌다 - 아예 다른 그림을
    쓰면 눌러 볼 것인지부터 헷갈린다.

    꽃은 겹마다 그 겹의 풀을 그린 **직후**에 그린다. 전부 맨 위에 그리면
    앞쪽 풀이 뒤쪽 꽃을 못 가려서 스티커를 붙인 것처럼 보인다.
    """
    w = int(size * 1.15)
    h = size
    out = []
    for i in range(frames):
        ph = math.sin(i / float(frames) * 2 * math.pi)
        im = Image.new("RGB", (w, h), key)
        d = ImageDraw.Draw(im)
        base = h - max(2, h // 12)
        for layer, (color, lean_mul, blades) in enumerate(_BLADES):
            for (bx, bh, bw, sign) in blades:
                _blade(d, w * bx, base, h * bh, ph * size * lean_mul * sign,
                       max(1.5, w * bw), color)
            if not bloom:
                continue
            back = layer == 0
            for (lay, idx, t, fr) in _BLOOMS:
                if lay != layer or idx >= len(blades):
                    continue
                cx, cy = _stem_point(w, h, size, base, blades[idx], t, ph,
                                     lean_mul)
                _petal_flower(d, cx, cy, size * fr * 0.5, ph,
                              PETAL_DIM if back else PETAL,
                              PETAL if back else PETAL_HI)
        # 바닥 그림자
        d.ellipse((w * 0.18, base - h * 0.06, w * 0.82, base + h * 0.06),
                  fill=GRASS_SHADOW)
        out.append(im)
    return out, w, h


def ball_image(size=22, key=(255, 0, 255), open_top=False, tilt=0.0,
               ball="POKEBALL"):
    """몬스터볼. tilt 는 흔들릴 때 기울이는 각도(도).

    ball 로 종류를 주면 위쪽 색이 달라진다. 스무 가지를 던지는데 전부
    같은 그림이면 뭘 던졌는지 알 수가 없다.
    """
    ss = 4                                   # 계단 현상을 줄이려고 크게 그린 뒤 줄인다
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = ss
    box = (pad, pad, S - pad, S - pad)
    d.ellipse(box, fill=BALL_WHITE, outline=BALL_LINE, width=ss * 2)
    top = BALL_TOP.get(ball, BALL_RED)
    if not open_top:
        d.pieslice(box, 180, 360, fill=top, outline=BALL_LINE, width=ss * 2)
        stripe = BALL_STRIPE.get(ball)
        if stripe:
            # 위쪽에 띠 하나. 흰 볼(프리미어·타이머)끼리 구분이 된다.
            d.arc(box, 200, 340, fill=stripe, width=ss * 3)
        if ball in BALL_BLOOM:
            _petal_flower(d, S * 0.5, S * 0.30, S * 0.13, 0.0,
                          PETAL_HI, PETAL_CORE)
    mid = S // 2
    band = max(ss, S // 12)
    d.rectangle((pad, mid - band, S - pad, mid + band), fill=BALL_LINE)
    r = S // 6
    d.ellipse((mid - r, mid - r, mid + r, mid + r), fill=BALL_WHITE,
              outline=BALL_LINE, width=ss * 2)
    r2 = S // 12
    d.ellipse((mid - r2, mid - r2, mid + r2, mid + r2), fill=BALL_GREY)
    if tilt:
        im = im.rotate(tilt, resample=Image.BICUBIC, expand=False)
    # 그냥 줄이면 가장자리가 반투명해져서 투명색이 테두리처럼 번진다.
    # 스프라이트와 똑같이 알파를 미리 곱해 줄이고 다시 나눠 복원한다.
    from .sprites import flatten_rgba, premultiply
    im = premultiply(im).resize((size, size), Image.LANCZOS)
    return flatten_rgba(im, key)


def ball_shake_frames(size=22, key=(255, 0, 255), ball="POKEBALL"):
    """볼이 좌우로 흔들리는 한 사이클."""
    return [ball_image(size, key, tilt=t, ball=ball) for t in (0, -16, 0, 16, 0)]


# 흔들릴 때 기울이는 각도. 직접 그린 볼과 같은 사이클이라 연출 길이가
# 안 바뀐다(wild_ui 가 프레임 수로 흔든 횟수를 센다).
TILTS = (0, -16, 0, 16, 0)


def sprite_ball_frames(sprite, size=26, key=(255, 0, 255)):
    """가방·상점에 뜨는 **공식 도구 그림**으로 볼 연출 프레임을 만든다.

    직접 그린 볼(ball_image)은 종류마다 위쪽 색만 바꾼 것이라, 가방에서
    보던 그림과 던지는 그림이 서로 달랐다. 같은 그림을 쓰면 무엇을
    던졌는지가 한눈에 맞아떨어진다.

    돌려주는 것은 (흔들림 프레임 목록, 열린 볼 한 장) 이다.

    **양쪽 OS 가 같은 형식을 받는다.** 색빼기로 칠한 RGB 한 장씩이고,
    윈도우는 그 색을 창에서 뚫고 맥은 sprites.to_rgba 로 알파를 되살린다
    (platform_mac.SpriteView.frames). 직접 그린 볼도 같은 형식이라,
    이걸 지키면 어느 쪽에서도 새로 손댈 것이 없다.
    """
    from .sprites import flatten_rgba, premultiply

    # **여백을 먼저 잘라낸다.** 공식 도구 그림은 30x30 안에 볼이 작게
    # 들어 있어서, 그대로 쓰면 던지는 볼이 눈에 띄게 작아진다.
    box = sprite.getbbox()
    if box:
        sprite = sprite.crop(box)

    ss = 4                       # 크게 키워서 돌리고 줄인다. 그래야 안 뭉갠다
    # 돌릴 때 모서리가 잘리지 않게 자리를 조금 남긴다. 원 안에 든 그림이라
    # 대각선 길이(√2)까지는 필요 없고 이 정도면 ±16도를 견딘다.
    inner = int(size * ss * 0.86)
    big = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    fit = sprite.resize((inner, inner), Image.NEAREST)
    big.paste(fit, ((big.width - inner) // 2, (big.height - inner) // 2))

    def one(img):
        # 그냥 줄이면 가장자리가 반투명해져서 투명색이 테두리처럼 번진다.
        # 알파를 미리 곱해 줄이고 다시 나눠 복원한다(ball_image 와 같다).
        small = premultiply(img).resize((size, size), Image.LANCZOS)
        return flatten_rgba(small, key)

    shake = [one(big if not t else
                 big.rotate(t, resample=Image.BICUBIC, expand=False))
             for t in TILTS]

    # 공식 그림에는 '열린 볼' 이 없다. 밝게 태워서 터지듯 보이게 한다 -
    # 여기서 직접 그린 볼로 갈아타면 260ms 동안만 그림체가 튄다.
    white = Image.new("RGBA", big.size, (255, 255, 255, 0))
    white.putalpha(big.getchannel("A"))
    return shake, one(Image.blend(big, white, 0.72))


def sparkle_frames(size=40, frames=4, key=(255, 0, 255),
                   color=(255, 226, 120)):
    """포획 성공 때 튀는 반짝임."""
    out = []
    for i in range(frames):
        im = Image.new("RGB", (size, size), key)
        d = ImageDraw.Draw(im)
        c = size / 2.0
        g = (i + 1) / float(frames)
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            r1 = c * 0.25 * g
            r2 = c * 0.95 * g
            d.line([(c + math.cos(a) * r1, c + math.sin(a) * r1),
                    (c + math.cos(a) * r2, c + math.sin(a) * r2)],
                   fill=color, width=max(1, size // 18))
        rr = c * 0.2 * (1.2 - g)
        d.ellipse((c - rr, c - rr, c + rr, c + rr), fill=(255, 255, 255))
        out.append(im)
    return out


def badge_image(text="야생", w=42, h=16, key=(255, 0, 255),
                bg=(226, 78, 78), fg=(255, 255, 255)):
    """야생 개체 위에 붙일 작은 표식."""
    im = Image.new("RGB", (w, h), key)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg)
    try:
        f = pil_font(h * 0.62)
    except Exception:                                       # noqa: BLE001
        f = None
    tw = d.textlength(text, font=f) if f else len(text) * 6
    d.text(((w - tw) / 2.0, h * 0.16), text, fill=fg, font=f)
    return im
