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
# 이미 '항상 위' 인 창을 다시 맨 위로 (overlay 가 몇 초에 한 번 부른다).
keep_on_top = getattr(_M, "keep_on_top", _M.raise_above)
show_again = _M.show_again
bind_right = _M.bind_right
RIGHT_CLICK = _M.RIGHT_CLICK
NATIVE_MENU = getattr(_M, "NATIVE_MENU", True)
make_click_through = _M.make_click_through
SpriteView = _M.SpriteView
work_area = _M.work_area
screens = _M.screens
# 화면마다 작업표시줄·독을 뺀 영역 (1.9.1). screens 와 같은 차례.
screen_works = getattr(_M, "screen_works",
                       lambda w, h: [_M.work_area(w, h)])
# 모니터 전부를 아우르는 사각형 (영역 직접 그리기가 이 위에 덮개를 깐다).
virtual_screen = getattr(_M, "virtual_screen",
                         lambda w, h: (0, 0, w, h))
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
own_dialog = _M.own_dialog
surface = _M.surface
accept_first_click = _M.accept_first_click
# 테두리 없는 창이 글자를 받게 (친구 채팅, 1.11.0). 맥은 고른 창만 키 창이 될 수 있게 연다.
take_keys = _M.take_keys
drop_keys = _M.drop_keys
# 한글 입력기가 지금 조합 중인 글자를 읽는다 (윈도우만). 윈도우 Tk 는 조합 중인 글자를 칸에 안 그려서
# '한 글자 늦게' 보인다 - 친구 채팅 입력 말풍선이 이걸로 직접 그린다. 없는 곳(맥은 Tk 가 그린다)은 None.
ime_composition = getattr(_M, "ime_composition", None)
keep_focus = _M.keep_focus
watch_right_click = _M.watch_right_click
take_right_clicks = _M.take_right_clicks
mouse_buttons_down = _M.mouse_buttons_down
missing_requirement = getattr(_M, "missing_requirement", lambda: None)
font_candidates = _M.font_candidates
pil_font_files = _M.pil_font_files
# 화면 테마의 글꼴을 이 프로그램 안에서만 등록한다 (tk.Tk() 전에).
register_font = getattr(_M, "register_font", lambda path: False)
already_running_hint = _M.already_running_hint

# 맥에만 있는 것. 없는 데서는 아무 일도 안 하게 해 둔다.
keep_click_through = getattr(_M, "keep_click_through", lambda win: None)
# win 을 ref 바로 아래로 (꾸미기 효과 창이 제 포켓몬 밑에 깔리게 - 다른 창은 안 올린다)
order_below = getattr(_M, "order_below", lambda win, ref: False)
