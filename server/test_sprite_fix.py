# -*- coding: utf-8 -*-
"""납작한 배틀 도트 바꾸기 (common/sprite_fix). 서버를 띄우지 않는다.

    python server/test_sprite_fix.py

관장 카밀레의 스토마가 '찌부' 로 보인다는 제보. 쇼다운 도트가 98x15 였다.
  1. 서버는 그 종을 5세대 움직이는 도트부터 받는다 (이로치도 이로치 폴더에서).
  2. 캐시 이름에 판이 붙어서, 이미 받아 둔 옛 그림을 다시 쓰지 않는다.
  3. 안 바꾼 종은 예전과 같다.
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-sprite-fix-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_SPRITE_DIR"] = os.path.join(TMP, "sprites")

import urllib.request                                      # noqa: E402

from app import main as M                                  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class FakeResp(object):
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def main():
    asked = []
    real = urllib.request.urlopen

    def fake(url, timeout=None):
        asked.append(url)
        return FakeResp(b"GIF89a-fake")
    urllib.request.urlopen = fake
    try:
        print("=== 스토마 (618)")
        chk("캐시 이름에 판이 붙는다", os.path.basename(M._sprite_path(618, False, ".gif")) == "0618-r2.gif",
            M._sprite_path(618, False, ".gif"))
        chk("이로치도", os.path.basename(M._sprite_path(618, True, ".gif")) == "0618s-r2.gif",
            M._sprite_path(618, True, ".gif"))
        old = os.path.join(M.SPRITE_DIR, "0618.gif")
        os.makedirs(M.SPRITE_DIR, exist_ok=True)
        io.open(old, "wb").write(b"GIF89a-flat-showdown")
        chk("옛 이름으로 받아 둔 납작한 그림은 안 쓴다", M._sprite_cached(618, False) == (None, None),
            M._sprite_cached(618, False))
        p, ext = M._sprite_fetch(618, False)
        chk("5세대 움직이는 도트부터 받는다",
            asked and asked[0].endswith("/versions/generation-v/black-white/animated/618.gif"), asked[:1])
        chk("  판이 붙은 이름으로 남긴다", p and os.path.basename(p) == "0618-r2.gif", p)
        del asked[:]
        M._sprite_fetch(618, True)
        chk("이로치는 이로치 폴더에서",
            asked and asked[0].endswith("/versions/generation-v/black-white/animated/shiny/618.gif"),
            asked[:1])

        print("=== 안 바꾼 종 (피카츄)")
        chk("이름은 예전 그대로", os.path.basename(M._sprite_path(25, False, ".gif")) == "0025.gif")
        del asked[:]
        M._sprite_fetch(25, False)
        chk("쇼다운 도트부터 받는다", asked and asked[0].endswith("/other/showdown/25.gif"), asked[:1])
    finally:
        urllib.request.urlopen = real

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
