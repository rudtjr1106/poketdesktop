# -*- coding: utf-8 -*-
"""풀숲과 몬스터볼 그림을 직접 그린다.

게임에서 뜯어온 이미지를 쓰지 않고 코드로 그린다.
- 저작권 문제가 없다
- 파일을 같이 배포할 필요가 없다
- 크기를 바꿔도 늘 또렷하다
"""
import math

from PIL import Image, ImageDraw

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
}

# 위쪽에 한 줄 더 긋는 볼. 흰 볼끼리 구분이 안 되는 것을 막는다.
BALL_STRIPE = {
    "PREMIERBALL": (228, 62, 62),
    "TIMERBALL": (60, 60, 68),
    "LUXURYBALL": (214, 176, 92),
    "MASTERBALL": (238, 150, 200),
}


def _blade(d, x, base_y, h, lean, w, color):
    """풀 한 포기. lean 이 클수록 옆으로 눕는다."""
    tip_x = x + lean
    tip_y = base_y - h
    mid_x = x + lean * 0.35
    mid_y = base_y - h * 0.55
    d.polygon([(x - w, base_y), (x + w, base_y), (mid_x + w * 0.6, mid_y),
               (tip_x, tip_y), (mid_x - w * 0.6, mid_y)], fill=color)


def grass_frames(size=48, frames=4, key=(255, 0, 255)):
    """흔들리는 풀숲. 배경은 투명색으로 채워서 그대로 창에 올릴 수 있다."""
    w = int(size * 1.15)
    h = size
    out = []
    for i in range(frames):
        ph = math.sin(i / float(frames) * 2 * math.pi)
        im = Image.new("RGB", (w, h), key)
        d = ImageDraw.Draw(im)
        base = h - max(2, h // 12)
        # 뒤쪽 어두운 포기
        for k, (bx, bh, bw) in enumerate([(0.20, 0.62, 0.045), (0.50, 0.74, 0.05),
                                          (0.80, 0.60, 0.045)]):
            _blade(d, w * bx, base, h * bh, ph * size * 0.11 * (1 if k % 2 else -1),
                   max(1.5, w * bw), GRASS_DARK)
        # 가운데
        for k, (bx, bh, bw) in enumerate([(0.33, 0.80, 0.055), (0.66, 0.86, 0.055)]):
            _blade(d, w * bx, base, h * bh, ph * size * 0.15 * (1 if k else -1),
                   max(1.5, w * bw), GRASS_MID)
        # 앞쪽 밝은 포기
        for k, (bx, bh, bw) in enumerate([(0.44, 0.95, 0.06), (0.58, 0.70, 0.05)]):
            _blade(d, w * bx, base, h * bh, ph * size * 0.18 * (-1 if k else 1),
                   max(1.5, w * bw), GRASS_LIGHT)
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
        from PIL import ImageFont
        f = ImageFont.truetype("malgun.ttf", int(h * 0.62))
    except Exception:
        f = None
    tw = d.textlength(text, font=f) if f else len(text) * 6
    d.text(((w - tw) / 2.0, h * 0.16), text, fill=fg, font=f)
    return im
