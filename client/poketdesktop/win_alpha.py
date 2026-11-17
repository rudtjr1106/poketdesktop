# -*- coding: utf-8 -*-
"""창 투명도 (게시판 #566) — 테두리가 있는 포스크탑 창을 설정의 '창 투명도' 만큼 비치게 한다.

    install(root, lambda: app.settings)   앱을 켤 때 한 번
    apply_all(root)                       설정에서 손잡이를 움직였을 때 (떠 있는 창에 바로)
    current()                             지금 입힐 알파 (스스로 투명도를 움직이는 창이 끝값으로 쓴다)

창을 만드는 곳(39개 파일)마다 손대지 않는다. **Toplevel 이 화면에 나올 때(<Map>) 한 군데서 입힌다** - 긴급 숨기기
(stealth.py)가 창 종류를 가리지 않고 거두는 것과 같은 생각이다. 거뒀다 다시 띄울 때도 <Map> 이 와서 그대로다.

안 건드리는 창:
  · 테두리 없는 창(overrideredirect) - 바탕화면 도트 · 이름표 · 연출 · 말풍선. 포켓몬은 '포켓몬 투명도' 가 따로 있다.
  · _own_alpha 가 켜진 창 - 스스로 -alpha 를 움직인다 (실시간 배틀 창이 비친 데서 또렷해지며 뜬다). 그런 창은
    끝값을 current() 로 맞춘다.
"""
import tkinter as tk

from . import config

_get = [None]          # 설정을 돌려주는 함수. install 전이면 None (그때는 늘 그대로)


def current():
    """지금 입힐 알파. 설치 전이면 1.0."""
    get = _get[0]
    if get is None:
        return 1.0
    try:
        return config.win_alpha(get())
    except Exception:                                   # noqa: BLE001
        return 1.0


def eligible(w):
    """투명도를 입힐 창인가: 테두리가 있는 Toplevel 이고, 스스로 투명도를 움직이지 않는다."""
    if not isinstance(w, tk.Toplevel) or getattr(w, "_own_alpha", False):
        return False
    try:
        return not w.overrideredirect()
    except tk.TclError:
        return False


def _put(w, a):
    """바꿨으면 True. **이미 그 값이면 건드리지 않는다** - 윈도우는 -alpha 를 걸 때 창 틀을 다시 지어서
    (deco_fx · platform_win 설명) 같은 값을 또 걸면 괜히 깜빡일 수 있다. 기본(100%)인 사람은 Tk 를 한 번도 안 부른다."""
    try:
        if abs(float(w.attributes("-alpha")) - a) < 0.005:
            return False
        w.attributes("-alpha", a)
        return True
    except (tk.TclError, ValueError):
        return False


def _on_map(e):
    w = e.widget
    if eligible(w):
        _put(w, current())


def install(root, get_settings):
    """루트에 문지기를 건다. 여러 번 불러도 한 번만 건다 (설정 함수만 새것으로)."""
    first = _get[0] is None
    _get[0] = get_settings
    if first:
        root.bind_class("Toplevel", "<Map>", _on_map, add="+")


def apply_all(root):
    """이미 떠 있는 창(창 속 창까지)에 지금 투명도를 입힌다. 바꾼 창 수를 돌려준다 (이미 그 값인 창은 안 센다)."""
    from .stealth import toplevels             # 긴급 숨기기와 같은 '떠 있는 창 전부'
    a = current()
    try:
        wins = toplevels(root)
    except (tk.TclError, AttributeError):       # 창을 못 훑으면 그냥 둔다 - 부른 쪽('기본값으로' 등)을 멈추지 않는다
        return 0
    return sum(1 for w in wins if eligible(w) and _put(w, a))
