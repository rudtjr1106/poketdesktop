# -*- coding: utf-8 -*-
"""에메랄드 (3세대 · 게임보이 어드밴스) 테마 - DP 틀을 물려받는다 (skins/derive.py).

시안 A (design-notes/ui-revamp/concepts.html 의 .a) 를 그대로 옮긴다:

    바탕          청록 빗금 (#68b8a0 · #74c4ac, 14px 씩 135도) - 판 바깥에만. 글은 늘 판 위에 둔다
    창(판)        미색 종이(#f8f8f0) + 두꺼운 남색 테(#283048, 4px) + 안쪽 옅은 하늘빛 줄(#9cc4e4, 3px),
                  모서리는 4px 깎는다 (gba.frame - kit.panel 도 이 모양으로 바꿔 끼운다)
    커서          빨간 ▶ (#e04030), 고른 줄은 연노랑 띠 (#fff2b8)
    머리 띠       빨간 띠에 흰 글씨 '◀ 주머니 ▶' (가방) - 허브 위 탭의 고른 칸도 이 모양
    단추          흰 바탕 · 남색 2px 테 (고른 것 = 남색 바탕 흰 글씨), 큰 단추는 빨강 · 남색 4px 테 · 그늘
    배틀          하늘색 하늘 · 연두 땅 · 초록 받침, 남색 테 흰 이름표, 아래는 기술 2x2(▶) 창 + PP · 타입 창
    글꼴          갈무리11

허브 · 가방 · 배틀은 따로 그리고 (hub.py · bag.py · tms.py · battle.py), 나머지 화면은 DP 배치 그대로
빛깔 · 테 · 바탕만 이 테마로 옮긴다 (아래 PALETTE · COLORS · shade, 그리고 widgets.py 가 거는 gba.patch_kit).
타입 빛깔 · 체력 빛깔은 그대로 (뜻이 있는 빛깔 - derive.KEEP_ALWAYS).
"""
BASE = "dp"
FONT = "Galmuri11"
RADIUS_K = 0.4           # GBA 창은 거의 네모 (모서리 4px 깎음) - 둥근 것도 아주 조금만
LINE_K = 2.0             # 테는 굵게 (진한 테 4px · 옅은 테 2px)

# 시안 A 의 빛깔 (concepts.html 35~37줄)
INK_A = "#384048"        # 글자
NAVY = "#283048"         # 창 테 (--a-ink)
NAVY_HI = "#3c4868"      # 남색 단추를 올렸을 때
NAVY_LO = "#181e30"
LIGHT = "#9cc4e4"        # 창 안쪽 옅은 줄 (--a-line)
PAPER = "#f8f8f0"        # 창 바탕 (--a-paper)
SHADE = "#d8d8d0"        # 글자 그늘 (--a-shade)
RED = "#e04030"          # 커서 · 머리 띠 · 큰 단추 (--a-red)
RED_D = "#902818"        # 빨간 띠 글자 그늘
SELY = "#fff2b8"         # 고른 줄 (--a-sel)
BG1, BG2 = "#68b8a0", "#74c4ac"   # 바탕 빗금 (--a-bg · --a-bg2)
GRP = "#6a7a8a"          # 단락 머리 (열매 · 3종)
GREEN_OK = "#3a8a4a"     # '빈손' 같은 좋은 상태
# 빗금 바탕이 없는 화면 (DP 배치 그대로인 화면)의 바탕 - 빗금 두 빛을 밝게 편 것. 그 위 글이 읽히게 옅게 둔다
WIN = "#cfe9df"

PALETTE = {
    "INK": INK_A, "SH": SHADE, "DIM": "#5c6a78", "FAINT": "#8c98a4", "CUR": RED, "WHITE": "#ffffff",
    "BEZEL": NAVY,
    # 가방 위 화면 (DP: 하늘색 · 주황 주머니 띠) - 에메랄드 가방은 bag.py 가 따로 그린다. 남는 곳은 종이 · 빨강
    "CYAN1": "#e2f2ec", "CYAN2": "#d4ece4",
    "TAG": RED, "TAG_LINE": NAVY, "TAG_IN": "#f4a090",
    "STRIP": RED, "STRIP_LINE": NAVY, "CELL": PAPER, "CELL_INK": NAVY,
    "TAN_L": "#e2f2ec", "TAN": "#cfe9df", "TAN_D": "#bfe0d4", "BROWN": NAVY,
    "BTN_TAN": PAPER, "BTN_LINE": NAVY, "BTN_IN": "#ffffff", "BTN_INK": INK_A,
    # 목록 칸 (DP: 연두 테 · 회색 테) -> 청록 빗금 빛 · 남색 테 · 옅은 하늘빛 줄
    "GREEN": BG1, "GREEN_LINE": NAVY, "GREEN_IN": LIGHT,
    "LIST_FRAME": NAVY, "LIST_IN": LIGHT, "HOVER": "#f4f0d8",
    # 설명 띠 (DP: 보라) -> 남색 띠, 제목은 연노랑
    "PURPLE": NAVY, "PURPLE_HI": NAVY_HI, "PURPLE_LO": NAVY_LO, "PURPLE_SH": NAVY_LO, "PURPLE_EM": SELY,
    # 파티 판 (DP: 올리브 바탕 · 하늘색 판 · 주황 고름) -> 종이 바탕 · 종이 판 · 빨간 고름
    "OLIVE1": PAPER, "OLIVE2": PAPER,
    "PLATE_LINE": NAVY, "PLATE_TOP": "#ffffff", "PLATE_BOT": PAPER, "PLATE_SEL": RED,
    "PLATE_GOOD_TOP": "#eaf8e0", "PLATE_GOOD_BOT": "#d8f0c8",
    "PLATE_OFF_TOP": "#e4e4dc", "PLATE_OFF_BOT": SHADE,
    "PLATE_HOVER_TOP": "#fff8d8", "PLATE_HOVER_BOT": SELY,
    # 단추 (DP: 파랑 = 주된 일) -> 남색 (시안의 '고른 줄 세우기' 단추). 큰 단추(가방 쓰기)는 빨강 - gba.py
    "BLUE": NAVY, "BLUE_HI": NAVY_HI, "BLUE_LINE": NAVY_LO, "BLUE_TOP": "#5a6a90",
    "GRAY_BTN": "#a8b0b8", "GRAY_HI": "#c8ced4", "GRAY_LINE": "#5c6670",
    "RED_BTN": RED, "RED_HI": "#ec5a48", "RED_LINE": NAVY,
    "OFF_BTN": "#d8d8d0", "OFF_HI": "#e4e4dc", "OFF_LINE": "#a0a4a8",
    "MSG_FRAME": NAVY, "MSG_ST1": LIGHT, "MSG_ST2": "#c8dcec", "MSG_ST_LINE": "#7aa4c8",
    # v2 바탕 · 판
    "WIN_BG": WIN, "PANEL": PAPER, "LINE": LIGHT, "LINE_D": NAVY, "INK2": "#4a5462",
    "SEL": SELY, "HOV": "#f4f0d8", "TAGC": NAVY, "TAGC_D": NAVY_LO, "SEP": "#e4e4da",
    # 몬스터볼 빛깔은 그대로
    "BALL_RED": "#e87474", "BALL_WHITE": "#f8f8f4", "BALL_BTN": "#c6c6c6",
}

# DP 화면 코드에 박힌 빛깔 중 따로 정해 둔 것 (나머지는 아래 shade 규칙으로)
COLORS = {
    # kit 의 파란 단추 (주된 일) -> 남색
    "#3570d0": NAVY, "#4682e2": NAVY_HI, "#1f4890": NAVY_LO,
    # 배틀 '기권' 단추 (파랑) -> 남색
    "#3a6fc8": NAVY, "#4c82d8": NAVY_HI,
    # 배틀 아래 화면 바탕 · 위 띠 (회색) -> 남색 바탕 (battle.py)
    "#ecece8": NAVY, "#d6d6d0": NAVY, "#bcbcb4": NAVY_LO,
    # 배틀 이름표 (DP: 미색 · 진회색 테) -> 종이 · 남색 테
    "#f6f6ee": PAPER, "#3c4048": NAVY,
    # 위젯으로 짠 창(묻는 창 등)의 바탕 (DP: 푸른 회색) -> 이 테마 바탕
    "#eef2f6": WIN, "#f6f8fb": PAPER, "#dbe8f6": SELY, "#dfe4ea": "#c2e2d6", "#b8c0cc": "#8cbcae",
    # 흰 판 · 흰 목록 -> 종이 (시안의 창 바탕)
    "#ffffff": PAPER,
    # 입력칸 · 목록의 회색 테 -> 남색
    "#a8b0bc": NAVY, "#8a96a8": NAVY, "#c8d0dc": LIGHT,
    # 굴림 막대 (DP: 회색 홈 · 회색 손잡이) -> 옅은 하늘 홈 · 남색 손잡이
    "#d8dde4": "#dce8f0", "#b8c2d0": "#6a7a96",

    # ---- DP 화면마다의 고유 빛깔 -> 이 테마 (머리 띠는 모두 남색 띠 + 옅은 하늘빛 밑줄, 바탕은 종이 · 옅은 청록)
    # 도감 · 업적 · 칭호 (DP: 빨간 기기) -> 남색 기기(배틀 아래 화면처럼) 안에 종이 화면 · 옅은 하늘빛 테
    "#d83c3c": NAVY, "#a42424": LIGHT, "#3a1414": LIGHT, "#eef4e8": PAPER, "#b8c8b0": LIGHT,
    "#fbe8e8": PAPER, "#8a2020": NAVY,                       # 세대 · 잡은 것 탭 (고르지 않은 칸)
    # 포켓치 액정 (DP: 연두 액정 · 회색 몸) -> 옅은 민트 칸 · 남색 테 · 남색 글
    "#a8d09e": "#d8eee4", "#3b3b40": NAVY, "#2f4a30": INK_A, "#7c9c74": LIGHT,
    # 친구수첩 (DP: 귤빛 띠 · 크림 공책 · 분홍 여백 줄) -> 남색 띠 · 종이 · 옅은 하늘빛 줄
    "#c4692c": NAVY, "#8a4416": LIGHT, "#fff8e6": PAPER, "#eee2c6": "#e4e4da", "#f0b0a8": LIGHT,
    # 길드 (DP: 흙빛 띠 · 모래빛 비밀기지) -> 남색 띠 · 옅은 청록 바탕 · 옅은 하늘빛 테
    "#8c5c2e": NAVY, "#5e3c1a": LIGHT, "#f4ead8": WIN, "#dccba8": LIGHT, "#efe4cc": "#dce8f0",
    "#b8a888": "#a0a4a8",
    # 관장 탭 머리 (DP: 풀빛 띠) -> 남색 띠
    "#3d8a3e": NAVY, "#2c6a2e": LIGHT,
    # 마이페이지 · 설정 (DP: 파란 쪽 · 파란 카드 · 하늘빛 칸) -> 옅은 청록 쪽 · 남색 카드 · 종이 · 민트 칸
    "#cfe0f4": WIN, "#3a68c8": NAVY, "#1f3c84": LIGHT, "#5c8ce4": NAVY, "#f4f8ff": PAPER, "#9ab8ea": LIGHT,
    "#f2f6fc": "#e6f2ec", "#eef1f5": "#ecece4", "#fff3ec": SELY,
    # 탐험 (DP: 회색 기기 · 연두 액정) -> 남색 기기 · 종이 칸
    "#3a3f48": NAVY, "#4a505a": NAVY_HI, "#23262d": NAVY_LO,
    "#a8c890": PAPER, "#b8d6a0": SELY, "#24301c": INK_A, "#41522f": "#5c6a78",
    # 처음 화면의 스타팅 가방 (DP: 마카오 박사의 갈색 가방) -> GBA 창 (남색 테 · 종이 안)
    "#c0843c": NAVY, "#6a4520": NAVY_LO, "#f6e8c8": PAPER, "#b08850": LIGHT, "#e4cc96": "#c2e2d6",
    # 위험한 묻는 창의 머리 (DP: 분홍 띠) -> 보통 묻는 창과 같은 옅은 민트 (빨간 이름표가 위험을 알린다)
    "#fde8e8": "#e2f2ec",
}

# 옮기지 않는 DP 빛깔 (뜻이 있는 빛깔): 기술 분류 '특수'(파랑) · 등급 '진귀'(보라)
KEEP = ("#3a6ad0", "#8a4ad0", "#7a4ad0", "#2860c0")


def shade(rgb):
    """표에 없는 DP 빛깔 -> 에메랄드: 하늘 · 파랑 바탕은 옅은 청록으로, 진한 파랑(단추 · 띠)은 남색으로,
    올리브 · 옅은 연두 바탕은 청록으로. 빨강 · 주황 · 금빛 · 회색은 그대로."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    deg = h * 360
    if s < 0.06:
        return rgb                                   # 이미 회색
    if 165 <= deg < 260:                             # 하늘 · 파랑
        if v < 0.45:                                 # 아주 진한 남빛 (글자 · 테) -> 남색
            h, s = 0.62, min(s, 0.45)
        elif s >= 0.45:                              # 진한 파랑 (단추 · 띠 · 꼬리표) -> 남색 (흰 글씨가 읽히게)
            h, s, v = 0.62, 0.44, min(v, 0.32)
        else:                                        # 옅은 하늘 바탕 -> 옅은 청록
            h = 0.44
    elif 260 <= deg < 320:                           # 보라
        if s >= 0.35 and v >= 0.5:
            return rgb                               # 진한 보라 (등급 같은 뜻 색) - 그대로
        h = 0.62 if v < 0.5 else 0.44                # 진한 것은 남색, 옅은 것은 청록
    elif 50 <= deg < 75:                             # 올리브 (DP 파티 칸의 글 · 탭) -> 청록
        h = 0.44
    elif 75 <= deg < 165:                            # 연두 · 초록
        if s >= 0.5:
            return rgb                               # 진한 초록(포켓몬 단추 · 좋음)은 뜻이 있다 - 그대로
        h = 0.44                                     # 옅은 연두 바탕 -> 청록
    return colorsys.hsv_to_rgb(h, s, v)
