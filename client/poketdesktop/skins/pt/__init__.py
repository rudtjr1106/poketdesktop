# -*- coding: utf-8 -*-
"""플라티나 (4세대 · 닌텐도 DS) 테마 - 시안 B (design-notes/ui-revamp/concepts.html, 2026-10-25 다시 짬).

DS 플라티나 · 하트골드 아래 화면의 터치 단추 느낌이다. 1차(DP 빛깔만 은회색으로)는 시안과 달랐다 - 시안대로:

    바탕      강철 회색 세로 그라데이션(#3d4654 → #4a5464) 위에 10px 마다 옅은 흰 점 (판 바깥에만)
    머리 띠   #5b6676 → #465060, 아래 3px 진한 줄(#2a323e), 흰 글씨. 돈 같은 값은 진한 캡슐(#1e2630)에
    판        옅은 회색(#e6eaef) · 3px 진한 테(#2a323e) · 둥근 16 · 안쪽 위에 흰 빛 줄
    단추      둥근 캡슐 - 위가 밝은 그라데이션 + 위쪽 흰 빛 줄 + 진한 테.
              주된 일은 주황, 고른 것은 하늘색, 보통은 흰 회색
    목록 줄   흰 캡슐 (테 #c3cad3), 고른 줄은 하늘색 테 + 옅은 빛 고리
    설명 머리 보라 그라데이션(#8f7be8 → #6a55d8), 흰 글씨
    배틀      옅은 하늘 → 연둣빛 장면, 연둣빛 발판, 흰 둥근 이름표, 타입 색 캡슐 기술 단추

허브 · 가방(도구 · 기술머신) · 배틀(관장 · 실시간 · 레이드)은 이 폴더의 화면 파일이 시안대로 다시 그린다.
그 밖의 화면은 DP 틀(배치)을 그대로 받고, 아래 PALETTE · COLORS · shade 로 빛깔만 플라티나로 옮긴다
(skins/derive.py) - 바탕은 강철, 판은 옅은 회색에 진한 테, 주된 단추는 주황, 고른 것은 하늘색.

글꼴은 갈무리11. 글씨는 늘 단색 판 위에 둔다 (점 무늬 위에 글을 두지 않는다).
"""
BASE = "dp"
FONT = "Galmuri11"
RADIUS_K = 2.0           # 둥근 모서리 배율 - DP 의 판(8) 이 시안의 둥근 16 이 된다
LINE_K = 1.5             # 판 테 두께 배율 - 보통 2px · 진한 판 3px (시안의 3px 테)

# ---------------------------------------------------------------- 시안 빛깔 (이 폴더의 화면이 쓴다)
INK = "#26303c"          # 글자 (판 위)
DIM = "#5f6b78"          # 흐린 글자 · 묶음 이름
FAINT = "#8a929c"        # 못 쓰는 것
WHITE = "#ffffff"

STEEL1, STEEL2 = "#3d4654", "#4a5464"          # 바탕 그라데이션 (위 → 아래)
STEEL = "#434c5c"                              # 그림을 못 쓰는 곳의 바탕 (둘의 가운데)
BAR1, BAR2 = "#5b6676", "#465060"              # 머리 띠 그라데이션
RIM = "#2a323e"          # 진한 테 (판 · 단추 · 띠 아래 줄)
BAR_SH = "#1e2630"       # 띠 글씨 그림자 · 돈 캡슐 바탕
ON_STEEL = "#eef1f5"     # 강철 바탕(단색 띠) 위의 글자
ON_STEEL_DIM = "#b8c2ce"

PANEL = "#e6eaef"        # 판 바탕
PANEL_HI = "#ffffff"     # 판 안쪽 위의 빛 줄
SEG = "#c3cad3"          # 고르기 줄 홈 · 목록 줄 테
LINE2 = "#8d99a8"        # 입력칸 테
GLOW = "#a9daea"         # 고른 줄의 빛 고리 (하늘색 35% 를 판 위에 섞은 빛)

CYAN, CYAN_TOP = "#2fbbe6", "#7fdcfa"          # 고른 것
CYAN_INK = "#06303e"
CYAN_SOFT = "#d5f2fb"
CYAN_TEXT = "#127ea8"    # 판 위에서 읽히는 하늘색 글자

ORANGE, ORANGE_TOP, ORANGE_LINE, ORANGE_SH = "#f07a3a", "#ffb04a", "#7a3410", "#9a4410"
RED, RED_TOP, RED_LINE = "#e04a3c", "#ff8a7a", "#7a1c14"
GREEN, GREEN_TOP, GREEN_LINE = "#3cb85a", "#8fe0a0", "#1c5e2c"
BLUE, BLUE_TOP, BLUE_LINE = "#4f8ee6", "#9cc4f8", "#1c3c7a"
PURPLE, PURPLE_TOP, PURPLE_SH = "#6a55d8", "#8f7be8", "#3c2c98"
BTN_TOP, BTN_BOT = "#f4f6f8", "#cdd4dc"        # 보통 캡슐 단추

# ---------------------------------------------------------------- skins/dp/__init__.py 의 상수 -> 플라티나
PALETTE = {
    "INK": INK, "SH": "#c3cad3", "DIM": "#6a7582", "FAINT": FAINT, "CUR": CYAN_TEXT,
    "BEZEL": RIM,
    # (DP 가방 위 화면 - 이 테마는 bag.py 를 따로 그리지만, 물려받은 코드가 읽을 수 있어 맞춰 둔다)
    "CYAN1": PANEL, "CYAN2": "#dde2e8",
    "TAG": CYAN, "TAG_LINE": RIM, "TAG_IN": CYAN_TOP,
    "STRIP": BAR2, "STRIP_LINE": RIM, "CELL": PANEL, "CELL_INK": DIM,
    "TAN_L": STEEL2, "TAN": STEEL, "TAN_D": STEEL1, "BROWN": RIM,
    "BTN_TAN": BTN_TOP, "BTN_LINE": RIM, "BTN_IN": WHITE, "BTN_INK": INK,
    # 목록 칸 (DP: 연두 테) -> 판
    "GREEN": STEEL, "GREEN_LINE": RIM, "GREEN_IN": STEEL2,
    "LIST_FRAME": RIM, "LIST_IN": SEG, "HOVER": "#f1f7fa",
    # 설명 띠 (DP: 보라) -> 시안의 보라 머리
    "PURPLE": PURPLE, "PURPLE_HI": PURPLE_TOP, "PURPLE_LO": "#4f3cc0", "PURPLE_SH": PURPLE_SH,
    "PURPLE_EM": WHITE,
    # 파티 판 (DP: 올리브 바탕 · 하늘색 판 · 주황 고름) -> 옅은 판 · 흰 판 · 하늘색 고름
    "OLIVE1": PANEL, "OLIVE2": "#dde2e8",
    "PLATE_LINE": RIM, "PLATE_TOP": "#ffffff", "PLATE_BOT": "#eef1f4", "PLATE_SEL": CYAN,
    "PLATE_GOOD_TOP": "#e6f7ea", "PLATE_GOOD_BOT": "#c8ecd2",
    "PLATE_OFF_TOP": "#dde1e6", "PLATE_OFF_BOT": "#cdd2d9",
    "PLATE_HOVER_TOP": "#f4fbfe", "PLATE_HOVER_BOT": CYAN_SOFT,
    # 단추 (DP: 파랑 = 주된 일) -> 주황
    "BLUE": ORANGE, "BLUE_HI": ORANGE_TOP, "BLUE_LINE": ORANGE_LINE, "BLUE_TOP": ORANGE_TOP,
    "GRAY_BTN": BTN_BOT, "GRAY_HI": BTN_TOP, "GRAY_LINE": RIM,
    "RED_BTN": RED, "RED_HI": RED_TOP, "RED_LINE": RED_LINE,
    "OFF_BTN": "#cfd4da", "OFF_HI": "#dfe3e8", "OFF_LINE": "#9aa3ad",
    "MSG_FRAME": RIM, "MSG_ST1": SEG, "MSG_ST2": PANEL, "MSG_ST_LINE": LINE2,
    # v2 바탕 · 판: 강철 바탕 위에 옅은 회색 판 (진한 테)
    "WIN_BG": STEEL, "PANEL": PANEL, "LINE": "#7d8896", "LINE_D": RIM, "INK2": "#4c5866",
    "SEL": CYAN_SOFT, "HOV": "#f1f7fa", "TAGC": PURPLE, "TAGC_D": PURPLE_SH, "SEP": "#d3d9e0",
    # 몬스터볼 빛깔은 그대로
    "BALL_RED": "#e87474", "BALL_WHITE": "#f8f8f4", "BALL_BTN": "#c6c6c6",
}

# DP 화면 코드에 박힌 빛깔 중 따로 정해 둔 것 (나머지는 아래 shade 규칙으로)
COLORS = {
    # 납작한 단추 (kit.KINDS) - 파랑(주된 일) -> 주황 캡슐, 회색 -> 흰 회색 캡슐
    "#3570d0": ORANGE, "#4682e2": "#ff9450", "#1f4890": ORANGE_LINE,
    "#f4f6f9": "#eef1f4", "#8a96a8": RIM,
    # 화면마다의 맨 위 띠 -> 시안의 머리 띠 (강철 진한 회색, 흰 제목)
    "#3d8a3e": BAR2, "#2c6a2e": RIM,                 # 관장 띠 (DP: 풀빛). 지도 빛깔은 따로라 그대로
    "#c4692c": BAR2, "#8a4416": RIM,                 # 친구수첩 띠 (DP: 귤빛)
    "#1d5e80": RIM,                                  # 게시판 띠 아래 줄
    # 화면 바탕 (DP: 크림 · 모래빛 · 연두) -> 옅은 판 빛
    "#fff8e6": "#f2f4f7", "#eee2c6": "#d3d9e0", "#f0b0a8": "#c9b8d8",   # 친구수첩 종이 · 줄 · 여백 줄
    "#f4ead8": PANEL, "#dccba8": "#b8c0ca", "#efe4cc": "#dde2e8",       # 길드 바탕 · 판 테 · 단계 막대
    "#eef4e8": PANEL, "#b8c8b0": "#b8c0ca", "#a8b0a4": "#a0a8b2",       # 도감 화면 · 무대 테 · 물음표
    "#eef0e2": "#eef1f4", "#7a8250": RIM,                               # 고르지 않은 정렬 단추 (DP: 올리브)
    "#e8edf2": STEEL,                                                   # DP v2 창 바탕 (박힌 것)
    # 도감 · 업적 (DP: 빨간 도감 몸통) -> 강철 몸통 · 진한 테, 세대 단추는 흰 회색
    "#d83c3c": STEEL, "#a42424": RIM, "#3a1414": RIM, "#fbe8e8": "#eef1f4", "#8a2020": RIM,
    # 길드 위 띠 (DP: 흙빛) -> 머리 띠 빛
    "#8c5c2e": BAR2, "#5e3c1a": RIM,
    "#b02424": CYAN_TEXT,   # 길드 고른 방 글씨 (DP: 빨강) -> 고른 것의 하늘색 (하늘색 줄 위)
    "#2a56b8": "#3d4fae",   # 길드 채팅의 남 이름 (DP: 파랑) -> 짙은 남보라 (본문 글씨와 구별되게)
    # 마이페이지 트레이너 카드 (DP: 파란 카드) -> 머리 띠 빛 카드 · 진한 테, 안쪽은 흰 판
    "#5c8ce4": BAR2, "#1f3c84": RIM, "#9ab8ea": SEG, "#f4f8ff": "#fbfcfd", "#3a68c8": BAR2,
    "#f2f6fc": "#f4f6f8",                            # 모은 것 칸 (DP: 옅은 하늘)
    # 회원가입 첫 포켓몬 가방 (DP: 가죽 가방) -> 은빛 금속 가방, 금빛 걸쇠는 주황
    "#c0843c": "#9aa5b2", "#6a4520": RIM, "#f6e8c8": PANEL, "#b08850": LINE2, "#e4cc96": "#cdd4dc",
    "#f0c040": ORANGE_TOP,
}


def shade(rgb):
    """표에 없는 DP 빛깔 -> 플라티나: 옅은 하늘 · 연두 바탕은 은빛 회색으로, 진한 파랑 띠는 강철로,
    보라는 시안의 보라로 둔다. 빨강 · 주황 · 금빛 · 아주 진한 것(글자)은 그대로."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    deg = h * 360
    if s < 0.06:
        return rgb                                   # 이미 회색
    if 75 <= deg < 165:                              # 연두 · 초록
        if s >= 0.5:
            return rgb                               # 진한 초록(포켓몬 단추 · 좋음)은 뜻이 있다 - 그대로
        s, h = s * 0.15, 0.59                        # 옅은 바탕 -> 강철빛 회색 (밝기는 그대로)
    elif 165 <= deg < 255:                           # 하늘 · 파랑
        if s >= 0.45 and v < 0.85:                   # 진한 파랑(띠 · 꼬리표) -> 강철 (흰 글씨가 읽히게)
            s, v, h = 0.2, 0.28 + 0.15 * v, 0.6
        elif s < 0.45:                               # 옅은 하늘 바탕 -> 강철빛 회색
            s, h = s * 0.35, 0.57
    elif 15 <= deg < 45 and v < 0.75 and s < 0.6:    # 흙빛 바탕 -> 짙은 강철
        s, v = s * 0.3, v * 0.85
        h = 0.6
    return colorsys.hsv_to_rgb(h, s, v)
