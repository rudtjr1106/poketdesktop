# -*- coding: utf-8 -*-
"""길드 깃발 그림 (2.5.0) - 깃발 문자열(common/flag.py) 을 Tk 그림으로. 같은 깃발 · 같은 배율은 한 번만 만든다.

    img = flag_art.image(widget, pixels, scale=1)   # 24 x 24 (scale 2 면 48 x 48). 깃발이 없거나 틀리면 None
    flag_art.label(parent, pixels, scale=1, bg=...)  # 그림을 담은 Label (깃발이 없으면 None)

투명 칸은 비워 둔다 (바탕이 비친다). 그림은 위젯이 아니라 이 모듈이 붙잡아 둔다 - Tk 그림은 파이썬 쪽 참조가
사라지면 화면에서도 사라진다.
"""
import collections
import tkinter as tk

from common import flag as F

# (깃발, 배율) -> PhotoImage. 오래 안 쓴 것부터 하나씩 뺀다 - 통째로 비우면 DP 캔버스(create_image 는 파이썬 참조를
# 안 잡는다)에 그려 둔 깃발까지 빈칸이 됐다 (11/14 검토). 지금 보이는 깃발은 방금 쓴 것이라 맨 나중에 빠진다.
_CACHE = collections.OrderedDict()
_CACHE_MAX = 600


def image(widget, pixels, scale=1):
    if not pixels or not F.valid(pixels) or F.is_blank(pixels):
        return None
    scale = max(1, int(scale))
    key = (pixels, scale)
    img = _CACHE.get(key)
    if img is not None:
        _CACHE.move_to_end(key)
        return img
    try:
        img = tk.PhotoImage(master=widget, width=F.SIZE * scale, height=F.SIZE * scale)
        for y in range(F.SIZE):
            for x in range(F.SIZE):
                c = F.color_at(pixels, x, y)
                if c is not None:
                    img.put(c, to=(x * scale, y * scale, (x + 1) * scale, (y + 1) * scale))
    except tk.TclError:
        return None
    while len(_CACHE) >= _CACHE_MAX:
        _CACHE.popitem(last=False)
    _CACHE[key] = img
    return img


def label(parent, pixels, scale=1, bg=None, **kw):
    """깃발 그림을 담은 Label. 깃발이 없으면 None (부르는 쪽이 자리를 비운다)."""
    img = image(parent, pixels, scale)
    if img is None:
        return None
    opts = dict(image=img, bd=0, highlightthickness=0)
    if bg is not None:
        opts["bg"] = bg
    opts.update(kw)
    lb = tk.Label(parent, **opts)
    lb.image = img
    return lb
