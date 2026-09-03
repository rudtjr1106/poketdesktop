# -*- coding: utf-8 -*-
"""이 컴퓨터에 맞는 구현을 고른다.

부르는 쪽은 이 모듈 하나만 본다.

    from . import platform_os as PLAT
    PLAT.work_area(w, h)

윈도우에서는 `platform_mac` 을 **import 조차 하지 않는다** (pyobjc 가
없으니 당연히 없어야 한다). 반대도 마찬가지다.
"""
import sys


def _pick():
    if sys.platform == "win32":
        from . import platform_win as m
    elif sys.platform == "darwin":
        from . import platform_mac as m
    else:
        from . import platform_base as m
    return m


_M = _pick()

NAME = getattr(_M, "__name__", "?").rsplit(".", 1)[-1]
NEEDS_HIT_TRACKING = getattr(_M, "NEEDS_HIT_TRACKING", False)

transparent_window = _M.transparent_window
raise_above = _M.raise_above
show_again = _M.show_again
bind_right = _M.bind_right
RIGHT_CLICK = _M.RIGHT_CLICK
NATIVE_MENU = getattr(_M, "NATIVE_MENU", True)
make_click_through = _M.make_click_through
SpriteView = _M.SpriteView
work_area = _M.work_area
double_click_ms = _M.double_click_ms
single_lock = _M.single_lock
single_release = _M.single_release
data_dir = _M.data_dir
machine_raw = _M.machine_raw
dpi_aware = _M.dpi_aware
before_tk = getattr(_M, "before_tk", lambda: None)
gui_ready = getattr(_M, "gui_ready", lambda: True)
hide_from_dock = _M.hide_from_dock
activate = _M.activate
missing_requirement = getattr(_M, "missing_requirement", lambda: None)
font_candidates = _M.font_candidates
pil_font_files = _M.pil_font_files
already_running_hint = _M.already_running_hint

# 맥에만 있는 것. 없는 데서는 아무 일도 안 하게 해 둔다.
keep_click_through = getattr(_M, "keep_click_through", lambda win: None)
