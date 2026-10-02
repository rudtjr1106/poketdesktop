# -*- coding: utf-8 -*-
"""이로치가 고른 색대로 도트의 색조를 돌린다 (1.8.0, common/tint).

색마다 그림을 따로 두지 않는다. 받아 둔 도트(이로치 것이나 기본 것)의
**색조만 돌려서** 옆에 새 파일로 남긴다. 한 번 만들면 다음부터는 그 파일을
그대로 읽는다 - 그래서 도트를 읽는 쪽(sprites)은 아무것도 몰라도 된다.

  · 밝기와 채도는 그대로 두고 색조(H)만 돌린다. 검은 테두리·흰 눈자위처럼
    채도가 없는 곳은 그대로 남는다.
  · 투명한 곳(알파)은 건드리지 않는다.
  · 움직이는 배틀 도트(GIF)는 **움직이는 PNG** 로 남긴다. GIF 로 다시 쓰면
    256색으로 줄이면서 색이 뭉개진다.

**작업 스레드에서 부를 것.** 60프레임짜리도 0.05초 안쪽이지만, 화면 스레드에서
파일을 쓰면 그동안 도트가 멈춘다.
"""
import os

from PIL import Image, ImageSequence


def shift(im, hue):
    """RGBA 한 장의 색조를 hue 도 돌린다."""
    im = im.convert("RGBA")
    if not hue:
        return im
    r, g, b, a = im.split()
    h, s, v = Image.merge("RGB", (r, g, b)).convert("HSV").split()
    off = int(round(hue / 360.0 * 256)) % 256
    h = h.point(lambda x: (x + off) % 256)
    out = Image.merge("HSV", (h, s, v)).convert("RGB")
    out.putalpha(a)
    return out


def make(src, dst, hue):
    """src 의 색조를 돌려 dst 에 쓴다. 됐으면 True.

    여러 장이면(움직이는 도트) 장마다 돌려서 움직이는 PNG 로 쓴다.
    """
    try:
        im = Image.open(src)
        frames, durs = [], []
        for fr in ImageSequence.Iterator(im):
            frames.append(shift(fr, hue))
            durs.append(int(fr.info.get("duration", 90) or 90))
        if not frames:
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".part"
        if len(frames) == 1:
            frames[0].save(tmp, format="PNG")
        else:
            # 장마다 통째로 갈아 끼운다 (앞 장 위에 덧그리지 않는다)
            frames[0].save(tmp, format="PNG", save_all=True, append_images=frames[1:],
                           duration=durs, loop=0, disposal=1, blend=0)
        os.replace(tmp, dst)
        return True
    except Exception:                                       # noqa: BLE001
        try:
            os.remove(dst + ".part")
        except OSError:
            pass
        return False
