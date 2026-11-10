# -*- coding: utf-8 -*-
"""아르케 열쇠 아이템 (2.4.0) 아이콘을 server/data/item_sprites/<ID>.png 로 굽는다.

그림은 client/poketdesktop/arche_art.item_icon (24x24 도트)이 그린다 - 앱과 서버가 같은 그림을 쓴다.
다른 도구 그림이 30x30 이라 가운데에 놓아 30x30 으로 맞춘다 (키우지 않는다 - 도트가 뭉개진다).

    python tools/build_arche_icons.py            # 여섯 개 다시 굽기
    python tools/build_arche_icons.py --check    # 구운 것이 지금 그림과 같은지만 본다 (다르면 1)

tools/build_item_sprites.py 는 이미 있는 파일을 건너뛰므로 이것을 덮어쓰지 않는다.
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, ROOT)

from PIL import Image                                     # noqa: E402

from poketdesktop import arche_art                        # noqa: E402

SIZE = 30
OUT = os.path.join(ROOT, "server", "data", "item_sprites")


def render(key):
    """한 아이템의 30x30 RGBA."""
    icon = arche_art.item_icon(key).convert("RGBA")
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    im.paste(icon, ((SIZE - icon.width) // 2, (SIZE - icon.height) // 2), icon)
    return im


def png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    bad = []
    for key in arche_art.ITEMS:
        path = os.path.join(a.out, key + ".png")
        im = render(key)
        if a.check:
            try:
                same = Image.open(path).convert("RGBA").tobytes() == im.tobytes()
            except OSError:
                same = False
            if not same:
                bad.append(key)
            continue
        with open(path, "wb") as f:
            f.write(png_bytes(im))
        print("  %s.png" % key)
    if a.check:
        print("다른 것: %s" % (", ".join(bad) if bad else "없음"))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
