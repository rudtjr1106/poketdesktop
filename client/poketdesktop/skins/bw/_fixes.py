# -*- coding: utf-8 -*-
"""블랙·화이트 테마가 물려받은 DP 화면에서 빛깔 옮기기만으로는 안 되는 곳 (이 테마일 때만, 한 번).

DP 화면 파일은 고치지 않는다 - 이 테마가 켜졌을 때 그 모듈의 이름 몇 개만 이 테마 것으로 바꿔 끼운다
(widgets.install 이 처음 한 번 부른다).

    머리 띠 (친구수첩 · 길드 · 게시판 · 랭킹 팁)
        DP 는 띠마다 빛깔이 다르고(귤빛 · 흙빛 · 파랑 · 보라) 제목을 진한 테두리 글씨로 썼다. 옮기면 테두리가
        밝은 빛으로 바뀌어 번진 글씨가 된다 -> 다른 화면과 같은 한 단계 올라온 판 + 아래 가는 줄 + 테두리 없는 흰 제목.
    관장 지도의 이름표
        DP 는 밝은 땅 위 이름을 진한 글씨(INK)로 썼는데, 이 테마의 INK 는 밝은 글씨라 밝은 땅 위에서 안 보인다
        -> 지도 위 글씨만 진한 글씨로 (어두운 땅 위는 그대로 흰 글씨).
    길드전 지도의 바다
        DP 의 옅은 하늘빛 바다는 어두운 창 안에서 혼자 밝은 판이 된다 -> 기본 지도가 테마에 맡긴 바탕('bg' 꼬리표
        한 장, ui_war_map._backdrop)을 밤바다 빛깔로 칠한다. 캔버스 빛깔(SEA)은 그대로 둔다.
"""
from ... import ui_common as U
from ..dp import font
from . import LINE, MAP_INK, MAP_SUB, PANEL_HI, SEA_W, SEA_W_EDGE, TEXT

_done = False


def head_band(cv, w, h, band, line, title, tags=("head",), ty=None):
    """화면 맨 위 띠 (DP 의 rank.head_band 와 같은 말): 무늬 없는 판 + 아래 가는 줄 + 흰 제목. 제목 오른쪽 끝 x."""
    cv.create_rectangle(0, 0, w, h, fill=PANEL_HI, outline="", tags=tags)
    cv.create_rectangle(0, h - U.h(3), w, h, fill=LINE, outline="", tags=tags)
    tid = cv.create_text(U.h(16), h // 2 - U.h(1) if ty is None else ty, text=title, fill=TEXT, font=font(14),
                         anchor="w", tags=tags)
    bb = cv.bbox(tid)
    return bb[2] if bb else U.h(90)


def _lum(color):
    c = color.lstrip("#")
    if len(c) != 6:
        return 1.0
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _ink_on(fill):
    """지도 · 레벨 칸 위에서 읽히는 글자색 (어두운 바탕이면 흰 글씨, 밝으면 진한 글씨)."""
    return "#ffffff" if _lum(fill) < 0.5 else MAP_INK


def _war_backdrop(self):
    """무늬 없는 밤바다 한 장과 가는 테 ('bg' 꼬리표 - 확대 · 끌기에 안 움직인다)."""
    cv = self.cv
    w, h = cv.winfo_width(), cv.winfo_height()
    if w <= 1:
        return
    cv.create_rectangle(1, 1, w - 2, h - 2, fill=SEA_W, outline=SEA_W_EDGE, width=3, tags=("bg",))
    cv.tag_lower("bg")


def apply():
    global _done
    if _done:
        return
    _done = True
    import importlib
    pkg = __name__.rsplit(".", 2)[0] + ".dp."
    for name in ("rank", "board", "friends", "guild"):
        try:
            mod = importlib.import_module(pkg + name)
        except Exception:                                   # noqa: BLE001 - 못 불러오면 DP 모습 그대로
            continue
        if hasattr(mod, "head_band"):
            mod.head_band = head_band
    try:
        gym = importlib.import_module(pkg + "gym")
    except Exception:                                       # noqa: BLE001
        gym = None
    if gym is not None:
        gym._ink_on = _ink_on
        gym.GymWindow.MAP = dict(gym.GymWindow.MAP, label=MAP_INK, label_sub=MAP_SUB, ink=MAP_INK)
    try:
        war = importlib.import_module(pkg + "war_map")
    except Exception:                                       # noqa: BLE001
        war = None
    if war is not None:
        war.WarMap._backdrop = _war_backdrop
