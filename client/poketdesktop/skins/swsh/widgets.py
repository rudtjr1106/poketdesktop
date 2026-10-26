# -*- coding: utf-8 -*-
"""소드·실드 테마의 '위젯 빛깔' - DP 의 것(dp/widgets.py)을 그대로 걸고, 이 테마에서만 하나를 더 바꾼다.

DP 화면 머리 띠의 제목은 흰 글자에 진한 테두리(kit.outlined)다. 시안 K 의 머리 글씨는 테두리 없는 흰 굵은
글씨이고, 테두리 글씨는 쓰지 않기로 했다 (남색 바탕 위에서는 테두리 여덟 겹이 번져 보인다). 그래서
kit.outlined 를 테두리 없는 흰 굵은 글씨 한 줄로 바꿔 끼운다 - 자리 · 크기 · 돌려주는 글자 id 는 같다.
빛깔 옮기기만으로 안 되는 나머지(주된 단추 · 작은 창 머리)는 _fixes.apply 가 한 번 바꿔 끼운다.
"""
from ..dp import kit as K
from ..dp import widgets as DPW

_patched = False


def _plain(cv, x, y, s, spec, fill="#ffffff", line="#3a4250", anchor="nw", tags=(), w=None):
    """테두리 없는 흰 글씨 (kit.outlined 와 같은 말을 받는다). 글자 id."""
    return cv.create_text(x, y, text=s, fill=fill, font=spec, anchor=anchor, tags=tags)


def install(root, style):
    global _patched
    DPW.install(root, style)
    if not _patched:
        _patched = True
        K.outlined = _plain
        from . import _fixes
        _fixes.apply()
