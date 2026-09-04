# -*- coding: utf-8 -*-
"""던지는 몬스터볼 그림 검사.

    python client/test_ball_sprite.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다.

가방·상점에 뜨는 **공식 도구 그림**을 던지는 연출에도 쓴다. 직접 그린
볼은 종류마다 위쪽 색만 바꾼 것이라, 가방에서 보던 그림과 던지는 그림이
서로 달랐다.

**여기서 지키는 것은 그림의 모양보다 형식이다.** 양쪽 OS 가 같은 형식을
받는다 - 색빼기로 칠한 RGB 한 장씩. 윈도우는 그 색을 창에서 뚫고, 맥은
sprites.to_rgba 로 알파를 되살린다(platform_mac.SpriteView.frames).
투명한 자리가 하나도 없으면 맥에서 볼이 **자홍색 네모**로 뜬다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-ball"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image                                       # noqa: E402

from poketdesktop import effects                            # noqa: E402
from poketdesktop.sprites import to_rgba                    # noqa: E402

OK = FAIL = 0
KEY = (255, 0, 255)
SIZE = 26


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def fake_sprite(pad=6, box=30, color=(220, 60, 60, 255)):
    """공식 도구 그림 흉내. 30x30 안에 볼이 작게 들어 있다."""
    im = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    for y in range(pad, box - pad):
        for x in range(pad, box - pad):
            im.putpixel((x, y), color)
    return im


def alpha_zero(rgb):
    """맥이 되살렸을 때 완전히 투명한 점이 몇 개인가."""
    a = to_rgba(rgb, KEY).getchannel("A")
    return sum(1 for v in a.tobytes() if v == 0)


def t_형식():
    print("-- 양쪽 OS 가 받는 형식")
    shake, opened = effects.sprite_ball_frames(fake_sprite(), SIZE, KEY)

    chk("흔들림은 다섯 장", len(shake) == 5, len(shake))
    # wild_ui 가 흔든 횟수를 프레임 수로 센다. 직접 그린 것과 같아야
    # 연출 길이가 안 바뀐다.
    chk("직접 그린 것과 장수가 같다",
        len(shake) == len(effects.ball_shake_frames(SIZE, KEY)), len(shake))

    for i, f in enumerate(shake + [opened]):
        chk("%d번째가 RGB" % i, f.mode == "RGB", f.mode)
        chk("%d번째 크기" % i, f.size == (SIZE, SIZE), f.size)

    # **여기가 맥이 걸리는 자리다.** 투명한 자리가 없으면 네모로 뜬다.
    for i, f in enumerate(shake):
        chk("%d번째에 투명한 자리가 있다" % i, alpha_zero(f) > 0)


def t_여백을_잘라낸다():
    print("-- 공식 그림의 여백")
    # 공식 그림은 30x30 안에 볼이 작게 들어 있다. 그대로 쓰면 던지는 볼이
    # 눈에 띄게 작아진다.
    wide = effects.sprite_ball_frames(fake_sprite(pad=10), SIZE, KEY)[0][0]
    tight = effects.sprite_ball_frames(fake_sprite(pad=1), SIZE, KEY)[0][0]
    a, b = alpha_zero(wide), alpha_zero(tight)
    # 여백을 잘라내므로 원래 여백이 얼마였든 결과가 비슷해야 한다.
    chk("여백이 넓든 좁든 채우는 정도가 비슷하다", abs(a - b) < SIZE * SIZE * 0.1,
        (a, b))
    filled = SIZE * SIZE - a
    chk("칸을 충분히 채운다 (작아 보이지 않게)",
        filled > SIZE * SIZE * 0.4, filled)


def t_돌려도_안_잘린다():
    print("-- 기울여도 모서리가 안 잘린다")
    shake, _ = effects.sprite_ball_frames(fake_sprite(pad=1), SIZE, KEY)
    straight = SIZE * SIZE - alpha_zero(shake[0])
    tilted = SIZE * SIZE - alpha_zero(shake[1])
    # 돌리면 조금은 줄어드는 게 정상이지만, 모서리가 잘려 나가면
    # 눈에 띄게 준다.
    chk("기울인 장도 크기가 비슷하다", tilted > straight * 0.8,
        (straight, tilted))


def t_열린_볼():
    print("-- 열린 볼")
    shake, opened = effects.sprite_ball_frames(fake_sprite(), SIZE, KEY)
    # 공식 그림에는 '열린 볼' 이 없어서 밝게 태운다. 원본보다 밝아야 한다.
    def brightness(rgb):
        """보이는 자리(알파가 있는 곳)의 평균 밝기."""
        px = to_rgba(rgb, KEY)
        a = px.getchannel("A").tobytes()
        tot = n = 0
        for band in ("R", "G", "B"):
            data = px.getchannel(band).tobytes()
            tot += sum(v for v, av in zip(data, a) if av)
        n = sum(1 for av in a if av)
        return tot / float(n or 1)
    chk("열린 볼이 원래보다 밝다", brightness(opened) > brightness(shake[0]),
        (brightness(shake[0]), brightness(opened)))
    chk("열린 볼도 투명한 자리가 남는다", alpha_zero(opened) > 0)


def main():
    for fn in (t_형식, t_여백을_잘라낸다, t_돌려도_안_잘린다, t_열린_볼):
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
