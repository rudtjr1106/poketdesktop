# -*- coding: utf-8 -*-
"""프로그램 아이콘 — 컴퓨터 화면 안에 들어 있는 몬스터볼.

작업표시줄과 트레이, exe 가 같은 그림을 쓴다. 한 곳에서 그려서 나눠 쓴다.

작게(16px) 줄여도 알아볼 수 있어야 한다. 그래서
    - 모니터는 테두리만 굵게, 안은 어둡게 비워 둔다
    - 몬스터볼은 화면을 거의 꽉 채운다
    - 받침대는 아주 작은 크기에서는 아예 그리지 않는다 (뭉개지기만 한다)
"""
from PIL import Image, ImageDraw

INK = (22, 24, 32, 255)          # 테두리
SCREEN = (18, 22, 34, 255)       # 화면 안쪽
FRAME = (86, 96, 124, 255)       # 모니터 몸통
BALL_TOP = (228, 62, 62, 255)
BALL_BOT = (246, 247, 250, 255)
BUTTON = (208, 210, 220, 255)


def _rr(d, box, r, fill, outline=None, width=1):
    """둥근 모서리 사각형. 아주 작을 때는 그냥 사각형으로."""
    if r < 2:
        d.rectangle(box, fill=fill, outline=outline, width=width)
    else:
        d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def make(size=256):
    """아이콘 한 장. RGBA 로 돌려준다."""
    # 큰 크기로 그리고 줄인다. 작은 크기에서 선이 깨지지 않게.
    S = max(size, 128) * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100.0                      # 100 칸 기준으로 좌표를 잡는다
    tiny = size < 24                   # 아주 작으면 받침대를 뺀다

    # ---- 모니터 ----
    mx1, my1 = 6 * u, (10 if tiny else 8) * u
    mx2, my2 = 94 * u, (90 if tiny else 74) * u
    line = max(2.0, 4 * u)
    _rr(d, (mx1, my1, mx2, my2), 9 * u, fill=FRAME, outline=INK,
        width=int(line))

    # 화면 안쪽
    p = 7 * u
    sx1, sy1, sx2, sy2 = mx1 + p, my1 + p, mx2 - p, my2 - p
    _rr(d, (sx1, sy1, sx2, sy2), 5 * u, fill=SCREEN)

    # ---- 받침대 ----
    if not tiny:
        nw = 14 * u
        d.rectangle((50 * u - nw / 2, my2 - line / 2, 50 * u + nw / 2, 84 * u),
                    fill=FRAME)
        _rr(d, (30 * u, 84 * u, 70 * u, 93 * u), 4 * u, fill=FRAME,
            outline=INK, width=int(line))

    # ---- 화면 안의 몬스터볼 ----
    cx, cy = (sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0
    r = min(sx2 - sx1, sy2 - sy1) / 2.0 * 0.82
    box = (cx - r, cy - r, cx + r, cy + r)
    bl = max(2.0, 3.4 * u)

    d.ellipse(box, fill=BALL_BOT, outline=INK, width=int(bl))
    d.pieslice(box, 180, 360, fill=BALL_TOP, outline=INK, width=int(bl))
    # 가운데 띠
    d.rectangle((cx - r, cy - bl * 0.75, cx + r, cy + bl * 0.75), fill=INK)
    # 가운데 버튼
    br = r * 0.34
    d.ellipse((cx - br, cy - br, cx + br, cy + br), fill=BALL_BOT,
              outline=INK, width=int(bl))
    if not tiny:
        br2 = r * 0.16
        d.ellipse((cx - br2, cy - br2, cx + br2, cy + br2), fill=BUTTON)

    return im.resize((size, size), Image.LANCZOS)


ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def save_ico(path):
    """작업표시줄·탐색기가 쓸 .ico. 크기별로 따로 그려 넣는다."""
    imgs = [make(s) for s in ICO_SIZES]
    imgs[-1].save(path, format="ICO",
                  sizes=[(im.width, im.height) for im in imgs])
    return path
