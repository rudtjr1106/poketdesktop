# -*- coding: utf-8 -*-
"""홍보용 동영상을 찍는다.

    python tools/promo_video.py            # 18초, 4:5 (인스타 피드)
    python tools/promo_video.py --reels    # 15초, 9:16 (릴스/스토리)

앱이 **떠 있는 상태**에서 돌려야 한다. 바탕화면 오른쪽 아래에서 포켓몬이
걸어다니는 자리만 담는다 - 화면 전체를 찍으면 열려 있는 창이나 파일
이름까지 그대로 들어간다.

작업 표시줄은 잘라낸다. 홍보 영상에 시계와 트레이 아이콘이 나올 이유가 없다.

찍은 것을 그대로 쓰지 않고 앱 색으로 만든 판 위에 얹는다. 인스타는
가로로 긴 영상을 잘라 버리기 때문에, 세로로 여백을 만들어 제목과 설명을
넣는 편이 낫다.
"""
import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "client"))     # poketdesktop 패키지 자리

from PIL import Image, ImageDraw, ImageGrab               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 앱 색 (client/poketdesktop/ui_common.py 와 같은 값)
BG = (19, 23, 34)
BG2 = (27, 32, 48)
LINE = (42, 49, 71)
FG = (242, 244, 251)
DIM = (142, 151, 179)
ACCENT = (255, 192, 67)

# 잡을 자리. 활동 영역이 오른쪽 아래 520x360 이고 작업 표시줄이 y=1026 부터다.
GRAB = (1370, 670, 1900, 1024)

SIZES = {"feed": (1080, 1350), "reels": (1080, 1920)}

LINES = [
    "바탕화면에서 포켓몬이 걸어다닙니다",
    "풀숲이 돋고 · 잡고 · 키우고 · 친구와 붙습니다",
]


def font(size, bold=False):
    """자막 글꼴. 못 찾으면 자막이 통째로 두부(□)가 된다.

    윈도우 글꼴 폴더를 손으로 조립하던 것을 effects 의 공용 헬퍼로
    옮겼다. 맥에서도 한글이 그려진다.
    """
    from poketdesktop.effects import pil_font
    return pil_font(size, bold)


def rounded(im, r):
    """모서리를 둥글린다. 그냥 네모로 얹으면 화면 캡처 티가 심하게 난다."""
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1),
                                           radius=r, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def backdrop(w, h):
    """위에서 아래로 살짝 밝아지는 판."""
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / float(h)
        d.line([(0, y), (w, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(BG, BG2)))
    return im


def compose(shot, size, icon):
    w, h = size
    im = backdrop(w, h)
    d = ImageDraw.Draw(im)

    pad = 60
    inner = w - pad * 2
    scale = inner / float(shot.width)
    game = shot.resize((inner, int(shot.height * scale)), Image.LANCZOS)
    game = rounded(game.convert("RGBA"), 22)

    # 제목 · 화면 · 설명을 한 덩어리로 보고 세로 가운데에 놓는다.
    # 9:16 은 위아래가 길어서, 위쪽에 고정하면 아래가 휑하게 빈다.
    block = 200 + 92 + game.height + 46 + 56 + 48
    gy = max(int(h * 0.16), (h - block) // 2 + 200)
    # 테두리를 한 겹 두른다. 배경과 화면이 붙어 보이지 않게.
    d.rounded_rectangle((pad - 3, gy - 3, pad + inner + 2, gy + game.height + 2),
                        radius=25, outline=LINE, width=3)
    im.paste(game, (pad, gy), game)

    # 제목
    if icon is not None:
        ic = icon.resize((96, 96), Image.LANCZOS)
        im.paste(ic, ((w - 96) // 2, gy - 200), ic)
    t = font(76, True)
    tw = d.textbbox((0, 0), "포스크탑", font=t)[2]
    d.text(((w - tw) // 2, gy - 92), "포스크탑", font=t, fill=FG)

    # 설명
    y = gy + game.height + 46
    for i, line in enumerate(LINES):
        f = font(38 if i == 0 else 30, i == 0)
        lw = d.textbbox((0, 0), line, font=f)[2]
        d.text(((w - lw) // 2, y), line, font=f,
               fill=FG if i == 0 else DIM)
        y += 56 if i == 0 else 48

    # 아래 띠
    f = font(28)
    link = "github.com/rudtjr1106/poketdesktop"
    lw = d.textbbox((0, 0), link, font=f)[2]
    d.text(((w - lw) // 2, h - 78), link, font=f, fill=ACCENT)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reels", action="store_true", help="9:16 세로")
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    size = SIZES["reels" if a.reels else "feed"]
    secs = a.seconds or (15.0 if a.reels else 18.0)
    out = a.out or os.path.join(ROOT, "dist",
                                "promo-%s.mp4" % ("reels" if a.reels else "feed"))
    os.makedirs(os.path.dirname(out), exist_ok=True)

    try:
        import imageio.v2 as imageio
    except ImportError:
        print("imageio 가 필요합니다:  pip install imageio imageio-ffmpeg")
        return 1

    icon = None
    ip = os.path.join(ROOT, "docs", "images", "icon.png")
    if os.path.exists(ip):
        icon = Image.open(ip).convert("RGBA")

    n = int(secs * a.fps)
    gap = 1.0 / a.fps
    print("%d초 x %dfps = %d장,  %dx%d 로 만듭니다" % (secs, a.fps, n, size[0], size[1]))
    print("찍는 자리: 화면 (%d,%d)-(%d,%d)  — 포켓몬이 걸어다니는 곳만" % GRAB)

    frames = []
    t0 = time.time()
    for i in range(n):
        want = t0 + i * gap
        now = time.time()
        if want > now:
            time.sleep(want - now)
        frames.append(ImageGrab.grab(bbox=GRAB).convert("RGB"))
        if (i + 1) % (a.fps * 3) == 0:
            print("  %d/%d" % (i + 1, n))
    took = time.time() - t0
    print("찍기 끝: %.1f초 (실제 %.1ffps)" % (took, n / took))

    print("판 위에 얹는 중...")
    w = imageio.get_writer(out, fps=a.fps, codec="libx264", quality=8,
                           macro_block_size=1)
    for i, f in enumerate(frames):
        w.append_data(__import__("numpy").asarray(compose(f, size, icon)))
        if (i + 1) % 60 == 0:
            print("  %d/%d" % (i + 1, len(frames)))
    w.close()
    mb = os.path.getsize(out) / 1024.0 / 1024.0
    print()
    print("완성: %s  (%.1f MB)" % (out, mb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
