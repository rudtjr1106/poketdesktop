# -*- coding: utf-8 -*-
"""디아루가·펄기아 (4세대 · 닌텐도 DS) 테마.

실제 DP 화면에서 따 온 것 (불바피디아 · 세레비 스크린샷을 보고 맞췄다, 2026-10-25):

    가방      위 화면 - 하늘색 줄무늬 칸(가방 이름표 · 주머니 띠 · 주머니 이름), 초록 칸 안의 흰 목록,
              빨간 네모 커서, 보라 설명 띠 / 아래 화면 - 황토색 바탕의 몬스터볼 다이얼과 둘레의 주머니 단추
    파티      올리브 빗금 바탕, 모서리를 깎은 하늘색 판, 고른 판은 주황 테
    배틀      아래 화면 - 옅은 몬스터볼 무늬, 큰 빨간 '싸운다', 빨간 꺾쇠 커서, 타입 색 테두리의 기술 단추
    포켓치    짙은 회색 테 · 연두 액정 · 빨간 알약 단추 · 파란 몸통
    글자      진회색 글자에 옅은 회색 그림자 (오른쪽 아래로 한 칸). 단추 글씨는 흰 글자에 진한 테두리

글꼴은 갈무리11 (닌텐도 DS 글꼴을 본뜬 픽셀 글꼴).
"""
from ... import ui_common as U

FONT = "Galmuri11"

# ---------------------------------------------------------------- 색
INK = "#2c3038"          # 글자 (v2: 더 진하게 - 밝은 바탕에서 또렷하게)
SH = "#d0d0c8"           # 글자 그림자
DIM = "#80808a"          # 흐린 글자 (못 쓰는 것)
FAINT = "#a8a8b0"
CUR = "#e83030"          # 커서 (빨간 네모 · 꺾쇠)
WHITE = "#ffffff"
BEZEL = "#23262d"        # 화면 사이 (DS 몸통)

CYAN1, CYAN2 = "#d6f3fb", "#c0e9f7"             # 위 화면 왼쪽 줄무늬
TAG, TAG_LINE, TAG_IN = "#6fc6e6", "#2f86b0", "#bdeefa"
STRIP, STRIP_LINE, CELL, CELL_INK = "#f2a84c", "#b8661c", "#fff3dc", "#a0622a"

TAN_L, TAN, TAN_D = "#f4dc94", "#e6c574", "#e2be68"   # 아래 화면 다이얼 바탕
BROWN = "#8a6a3a"
BTN_TAN, BTN_LINE, BTN_IN, BTN_INK = "#f6dc8e", "#a07c3c", "#fff2c4", "#8a5a20"
BALL_RED, BALL_WHITE, BALL_BTN = "#e87474", "#f8f8f4", "#c6c6c6"

GREEN, GREEN_LINE, GREEN_IN = "#9fd884", "#6cba52", "#c6eeae"   # 목록 칸
LIST_FRAME, LIST_IN = "#8a96a8", "#e0e6ee"
HOVER = "#eef2f6"

PURPLE, PURPLE_HI, PURPLE_LO, PURPLE_SH, PURPLE_EM = "#5f55d2", "#8b83ee", "#3f36a8", "#3c3398", "#ffe7a0"

OLIVE1, OLIVE2 = "#a6ae6a", "#98a25e"            # 파티 화면 바탕
PLATE_LINE, PLATE_TOP, PLATE_BOT = "#4d6c8c", "#c2e4f8", "#96caec"
PLATE_SEL = "#f06428"
PLATE_GOOD_TOP, PLATE_GOOD_BOT = "#d4f4c6", "#a6dc94"
PLATE_OFF_TOP, PLATE_OFF_BOT = "#d6d9de", "#bcc1c8"
PLATE_HOVER_TOP, PLATE_HOVER_BOT = "#dcf0fe", "#b4dcf6"

BLUE, BLUE_HI, BLUE_LINE, BLUE_TOP = "#2f5cc8", "#5c88ee", "#1a3784", "#9cbaf8"
GRAY_BTN, GRAY_HI, GRAY_LINE = "#9aa2ae", "#c4cad2", "#5a6270"
RED_BTN, RED_HI, RED_LINE = "#d04642", "#e66c64", "#8a2020"
OFF_BTN, OFF_HI, OFF_LINE = "#b8bcc4", "#d0d4da", "#8a8e96"

MSG_FRAME, MSG_ST1, MSG_ST2, MSG_ST_LINE = "#4c5a70", "#a8b8d0", "#c6d2e4", "#8698b6"

# ---------------------------------------------------------------- v2 (2026-10-25 다시 짬: 단순 · 잘 보임)
# 1차 DP 는 줄무늬 · 빗금 · 다이얼 · 흰 테두리 글씨가 많아 읽기 어려웠다 (사용자). v2 는 무늬 없는 바탕에
# 흰 판 · 가는 테 · 빨간 커서 · 파란 꼬리표 · 납작한 단추만 쓴다. 창 · 메뉴 크기는 기본 테마 그대로.
WIN_BG = "#e8edf2"       # 창 바탕 (무늬 없음)
PANEL = "#ffffff"        # 판
LINE = "#c3ccd6"         # 판 테 (보통)
LINE_D = "#5a6a80"       # 판 테 (지금 손대는 판 · 글상자)
INK2 = "#5a6270"         # 덜 중요한 글
SEL = "#fff1dc"          # 고른 줄 (크림)
HOV = "#eef4fb"          # 마우스를 올린 줄
TAGC, TAGC_D = "#3a78c8", "#24569a"   # 단락 꼬리표 (파랑)
SEP = "#e6eaef"          # 줄 사이 금

# 앱이 쓰는 뜻 색(U.GOOD 같은 것)을 이 테마에서 읽히는 색으로 (줄 끝의 상태 글 등)
_MEANING = {}


def tone(color):
    """기본 테마의 뜻 색을 DP 바탕(밝은 칸)에서 읽히는 색으로 바꾼다."""
    if not _MEANING:
        _MEANING.update({
            U.GOOD: "#2c8a3c", U.FG_FAINT: DIM, U.FG_DIM: "#606068", U.FG: INK,
            U.DANGER: "#d02828", U.ACCENT: "#c06810", U.ACCENT_TEXT: "#c06810",
            U.INFO: "#2860c0", U.SHINY: "#b88a00", U.PINK: "#c83a78", U.RED: "#d02828",
        })
    return _MEANING.get(color, color)


RADIUS_K = 1.0           # 둥근 모서리 배율 (kit.rrect) - 물려받는 테마가 바꾼다 (각진 테마는 0)
LINE_K = 1.0             # 판 · 글상자 테 두께 배율 (kit.panel) - 게임보이처럼 굵은 테는 2


# ---------------------------------------------------------------- 글꼴
def font(n):
    """갈무리11, n 은 기본 테마의 pt 와 같은 눈금 (U.pt - 맥은 한 단계 크다)."""
    return (FONT, U.pt(n))


# ---------------------------------------------------------------- 이 틀을 물려받은 테마
def _inherit():
    """지금 테마가 DP 를 물려받았으면 (플라티나 · 금은 …) 그 테마의 빛깔 · 글꼴로 위 상수를 바꿔 끼우고,
    DP 화면 코드에 박힌 빛깔을 그 테마 빛깔로 옮기는 고리를 건다 (skins/derive.py). DP 자신이면 아무것도 안 한다."""
    import importlib
    from .. import active, chain
    key = active()
    if key == "dp" or "dp" not in chain(key):
        return None
    try:
        theme = importlib.import_module("%s.%s" % (__name__.rsplit(".", 1)[0], key))
    except ModuleNotFoundError:
        return None
    g = globals()
    for k, v in (getattr(theme, "PALETTE", {}) or {}).items():
        if k in g:
            g[k] = v
    for k in ("FONT", "RADIUS_K", "LINE_K"):
        if hasattr(theme, k):
            g[k] = getattr(theme, k)
    from .. import derive
    from ._literals import LITERALS
    keep = list((getattr(theme, "PALETTE", {}) or {}).values())
    keep += list(U.TYPE_COLOR.values())                 # 타입 빛깔은 뜻이 있다 - 옮기지 않는다
    derive.install(theme, LITERALS, keep)
    return theme


THEME = _inherit()
