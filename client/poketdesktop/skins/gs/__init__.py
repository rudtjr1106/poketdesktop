# -*- coding: utf-8 -*-
"""금·은 (2세대 · 게임보이 컬러) 테마 - DP 틀을 물려받는다 (skins/derive.py).

시안 G (design-notes/ui-revamp/concepts.html 의 '.g') 를 그대로 옮긴다:

    바탕        금빛 크림(#f4e2a4)에 옅은 점 무늬 (판 바깥에만 - 글 밑에는 무늬가 없다)
    상자        종이빛(#fffaf0) 판에 **진한 테 4 + 종이빛 2 + 금빛 안쪽 줄 2** 의 두 겹 테, 모서리는 6 깎음 (_gbc.gbox)
    커서        빨간 ▶ (고른 줄 · 고른 탭 · 지금 할 일)
    고르기 칩   진한 테 2 의 네모 칩, 고르면 진한 바탕에 종이빛 글씨 (_gbc.chip)
    작은 글     갈색(#8a6a30) - 묶음 머리 · 등급 · 지닌 도구
    배틀        종이빛 한 화면, 이름표는 ㄴ자 선으로 받친 글 (상자 아님), 'HP' 는 금빛 꼬리표,
                아래는 왼쪽 글상자 + 오른쪽 명령 상자 (두 겹 금빛 테)

대표 화면(허브 · 가방 · 배틀)은 이 폴더의 파일이 시안대로 그리고, 나머지 화면은 DP 틀 그대로 빛깔만 이것으로
옮긴다 (PALETTE · COLORS · shade). 배틀의 체력 · 타입 · 성별 · 상태 빛깔은 그대로 (뜻이 있는 빛깔).
글꼴은 시안대로 갈무리11 (갈무리9 는 같은 pt 에서 글씨가 작아 보여 바꿨다 - 글씨를 줄이지 않는다).
"""
BASE = "dp"
FONT = "Galmuri11"
RADIUS_K = 0.75          # 시안의 깎은 모서리(6) 에 가깝게 - DP 의 둥근 모서리 8 의 3/4
LINE_K = 2               # 굵은 진한 테

# ---------------------------------------------------------------- 시안 G 의 빛깔 (--g-*)
G_BG = "#f4e2a4"         # 바탕 (금빛 크림)
PAPER = "#fffaf0"        # 판 · 글상자
INK = "#2c2014"          # 글자 · 테 (진한 밤빛)
AMBER = "#d8a040"        # 금빛 안쪽 줄 · 'HP' 꼬리표
RED = "#d84830"          # 커서
GREEN = "#48b058"
BROWN = "#8a6a30"        # 작은 글 (묶음 머리 · 등급 · 지닌 도구)
CIRCLE = "#f6e6b8"       # 가방 도구 그림의 둥근 칸
DOT = "#e0c98c"          # 바탕 점 (rgba(120,80,20,.18) 을 바탕 위에 섞은 빛깔)

INK2 = "#5c4a2c"         # 덜 중요한 글
DIM = "#8f7f5c"          # 흐린 글 (못 쓰는 것)
SEL = "#fbe6a8"          # 고른 줄 (옅은 금빛)
HOV = "#fdf2d2"          # 마우스를 올린 줄
SEP = "#efe2c0"          # 줄 사이 금
LINE = "#6a5030"         # 옅은 테 (판의 보통 테 - 진한 테보다 한 단계 옅게)
BTN = "#a05a10"          # 주된 단추 (흰 글씨가 읽히는 진한 호박빛)
BTN_HI = "#b4701e"
# 화면 머리 띠 (친구 · 길드 · 게시판 · 랭킹 · 관장 · 탐험 · 마이페이지 · 도감) - DP 는 화면마다 귤빛 · 흙빛 · 파랑 ·
# 보라 · 풀빛 · 회색 · 빨강으로 달랐다. 금·은은 한 빛깔 (흰 글씨가 읽히는 밤빛 갈색, 명암비 6.8)
BAND = "#80501c"
BAND_LO = "#5a3810"

# skins/dp/__init__.py 의 상수 -> 금·은 빛깔
PALETTE = {
    "INK": INK, "SH": "#e8d8b0", "DIM": DIM, "FAINT": "#b4a47c", "CUR": RED, "BEZEL": INK,
    "CYAN1": PAPER, "CYAN2": "#fbeec4",
    "TAG": AMBER, "TAG_LINE": INK, "TAG_IN": SEL,
    "STRIP": AMBER, "STRIP_LINE": INK, "CELL": "#fff4d8", "CELL_INK": "#6a4810",
    "TAN_L": PAPER, "TAN": "#f8ecc4", "TAN_D": G_BG, "BROWN": "#5c4424",
    "BTN_TAN": PAPER, "BTN_LINE": INK, "BTN_IN": PAPER, "BTN_INK": INK,
    # 목록 칸: 금빛 바탕 + 진한 테 · 금빛 안쪽 줄의 종이 상자 (kit.framed(…, LIST_FRAME, LIST_IN))
    "GREEN": G_BG, "GREEN_LINE": G_BG, "GREEN_IN": G_BG,
    "LIST_FRAME": INK, "LIST_IN": AMBER, "HOVER": HOV,
    # 설명 띠 (DP: 보라) - 흰 글씨가 놓이는 띠라 진한 밤빛, 제목은 금빛
    "PURPLE": INK, "PURPLE_HI": INK, "PURPLE_LO": INK, "PURPLE_SH": INK, "PURPLE_EM": "#f4c860",
    # 파티 판: 종이빛 판 · 진한 테, 고르면 빨간 테
    "OLIVE1": G_BG, "OLIVE2": G_BG,
    "PLATE_LINE": INK, "PLATE_TOP": PAPER, "PLATE_BOT": PAPER, "PLATE_SEL": RED,
    "PLATE_GOOD_TOP": "#e8f3d6", "PLATE_GOOD_BOT": "#e8f3d6",
    "PLATE_OFF_TOP": "#e8e0cc", "PLATE_OFF_BOT": "#e8e0cc",
    "PLATE_HOVER_TOP": HOV, "PLATE_HOVER_BOT": HOV,
    # 단추 (DP: 파랑 = 주된 일) -> 진한 호박빛 · 진한 테
    "BLUE": BTN, "BLUE_HI": BTN_HI, "BLUE_LINE": INK, "BLUE_TOP": "#d89a48",
    "GRAY_BTN": PAPER, "GRAY_HI": "#fff4d8", "GRAY_LINE": INK,
    "RED_BTN": "#c83a24", "RED_HI": RED, "RED_LINE": "#6a1a0c",
    "OFF_BTN": "#e8e0cc", "OFF_HI": "#e8e0cc", "OFF_LINE": "#b0a488",
    "MSG_FRAME": INK, "MSG_ST1": "#e8d8b0", "MSG_ST2": "#f4e8c8", "MSG_ST_LINE": "#b0a080",
    # v2 바탕 · 판
    "WIN_BG": G_BG, "PANEL": PAPER, "LINE": LINE, "LINE_D": INK, "INK2": INK2,
    "SEL": SEL, "HOV": HOV, "TAGC": BTN, "TAGC_D": "#6a3a08", "SEP": SEP,
    # 몬스터볼 빛깔은 그대로
    "BALL_RED": "#e87474", "BALL_WHITE": "#f8f8f4", "BALL_BTN": "#c6c6c6",
}

# 이 테마 파일들이 쓰는 빛깔 - DP 빛깔 옮기기에 걸리지 않게 (derive.Recolor 의 keep)
KEEP = (G_BG, PAPER, INK, AMBER, RED, GREEN, BROWN, CIRCLE, DOT, INK2, DIM, SEL, HOV, SEP, LINE, BTN, BTN_HI, BAND, BAND_LO,
        "#4890e0", "#e8dcc0",
        # 포켓몬 박스 (box.py): 여러 마리로 고른 칸 · 칸 테 · 벽지 · 도트 칸 · 메가진화 · 전설 표시 · 놓아주기
        "#e6f1d2", "#d6bd84", "#e0c890", "#f7e9c0", "#ecd7a0", "#fbf0d2", "#efdcaa", "#7a4ad0", "#8a4ad0",
        "#c83a24", "#6a3a08", "#b4a47c")

# DP 화면 코드에 박힌 빛깔 중 따로 정해 둔 것 (나머지는 아래 shade 규칙으로)
COLORS = {
    # 납작한 단추 (kit.KINDS): 파랑 -> 진한 호박빛, 회색 -> 종이빛 몸 · 진한 테
    "#3570d0": BTN, "#4682e2": BTN_HI, "#1f4890": INK,
    "#f4f6f9": PAPER, "#8a96a8": INK,
    "#e5e8ec": "#e8e0cc", "#c2c8d0": "#b0a488", "#9aa1ab": DIM,
    # 배틀 '기권' 단추 (파랑)
    "#3a6fc8": BTN, "#4c82d8": BTN_HI,
    # 입력칸 테 (kit.entry) - 진한 테
    "#a8b0bc": INK,
    # 긴 목록 막대 (kit.Scroll): 옅은 금빛 홈 · 금빛 손잡이
    "#d8dde4": "#f0e2bc", "#b8c2d0": AMBER,
    # 올리브 칸의 줄 세우기 탭
    "#7a8250": INK, "#eef0e2": PAPER,
    # 탐험 포켓치 액정 (DP: 연두) -> 종이빛 액정
    "#a8c890": "#f8ecc8", "#b8d6a0": PAPER,
    # 배틀 아래 칸 바탕 (DP: 회색)
    "#ecece8": PAPER,
    # DP 창 바탕 · 패널 (위젯 화면: widgets.BG_MAP 의 값)
    "#e8edf2": G_BG, "#eef2f6": G_BG, "#f6f8fb": PAPER, "#dbe8f6": HOV,
    "#c8d0dc": LINE, "#c3ccd6": LINE,
    # 흰 판 -> 종이빛 (시안의 판은 순백이 아니다)
    "#ffffff": PAPER,
    # 길드 (비밀기지 모래빛) -> 금빛 크림 바탕 · 갈색 가는 테
    "#f4ead8": G_BG, "#dccba8": BROWN,
    # ---- 화면마다 달랐던 DP 고유 빛깔 -> 한 머리 띠 빛깔 (BAND)
    # 도감 · 업적의 빨간 기계 (DP 도감)
    "#d83c3c": BAND, "#a42424": BAND_LO, "#3a1414": INK,
    # 관장 탭의 풀빛 머리 띠
    "#3d8a3e": BAND, "#2c6a2e": BAND_LO,
    # 친구수첩의 귤빛 띠 · 분홍 여백 줄
    "#c4692c": BAND, "#8a4416": BAND_LO, "#f0b0a8": "#e6c27a",
    # 길드의 흙빛 띠 (비밀기지 문패)
    "#8c5c2e": BAND, "#5e3c1a": BAND_LO,
    # 게시판 띠 아래 줄 (띠 자체는 board.py)
    "#1d5e80": BAND_LO,
    # 마이페이지 · 설정의 파란 머리 띠 · 트레이너 카드
    "#3a68c8": BAND, "#1f3c84": BAND_LO, "#5c8ce4": BAND, "#9ab8ea": AMBER, "#f4f8ff": PAPER,
    # 탐험 포켓치 몸통 (DP: 짙은 회색)
    "#3a3f48": BAND, "#4a505a": "#9a6428",
    # 되돌릴 수 없는 일을 묻는 창의 분홍 머리 (DP) -> 따뜻한 붉은 크림 (위험하다는 뜻은 남긴다)
    "#fde8e8": "#f8dcc8",
}


def shade(rgb):
    """표에 없는 DP 빛깔 -> 금·은.

    파랑 · 하늘 · 옅은 풀빛 바탕은 종이빛 · 금빛 크림으로 (밝을수록 종이빛), 진한 파랑(흰 글씨가 놓이는 띠 ·
    단추)은 진한 호박빛으로, 짙은 푸른 회색(머리 띠)과 보라는 진한 밤빛으로. 빨강 · 주황 · 노랑 · 진한 초록은
    그대로 (뜻이 있는 빛깔)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    deg = h * 360
    if s < 0.03:
        if v < 0.3:
            return colorsys.hsv_to_rgb(0.09, 0.5, max(v, 0.16))      # 검정 -> 진한 밤빛
        if v >= 0.85:
            return colorsys.hsv_to_rgb(0.11, 0.07 + (1.0 - v) * 0.6, v)   # 옅은 회색 판 -> 따뜻한 크림
        return colorsys.hsv_to_rgb(0.10, 0.12, v * 0.97)            # 회색 글 · 테 -> 따뜻한 회갈색
    cool = 75 <= deg < 320
    if not cool:
        return rgb
    if v >= 0.86 and s < 0.25:                       # 옅은 바탕 (하늘 · 풀빛 · 보랏빛이 살짝 도는 흰빛)
        if v >= 0.97:
            return colorsys.hsv_to_rgb(0.11, 0.06, 1.0)              # 종이빛
        return colorsys.hsv_to_rgb(0.12, min(0.33, 0.08 + (1.0 - v) * 2.2), min(1.0, v + 0.02))
    if 75 <= deg < 165 and s >= 0.5:
        return rgb                                   # 진한 초록 (포켓몬 단추 · 좋음) 은 뜻이 있다
    if v < 0.42:                                     # 짙은 푸른 회색 · 남색 (머리 띠) -> 진한 밤빛
        return colorsys.hsv_to_rgb(0.09, 0.55, max(0.17, v * 0.8))
    if 165 <= deg < 255 and s >= 0.45:               # 진한 파랑 (띠 · 단추 · 꼬리표) -> 진한 호박빛
        return colorsys.hsv_to_rgb(0.08, 0.86, 0.32 + 0.36 * v)
    if 255 <= deg < 320 and s >= 0.3:                # 보라 -> 밤빛
        return colorsys.hsv_to_rgb(0.08, 0.6, 0.25 + 0.2 * v)
    if v >= 0.7:                                     # 중간 밝기의 푸른 회색 (테 · 판) -> 옅은 금빛 회색
        return colorsys.hsv_to_rgb(0.11, min(0.35, s * 0.9 + 0.1), v * 0.95)
    return colorsys.hsv_to_rgb(0.10, min(0.5, s + 0.2), v * 0.85)   # 흐린 글 · 테 -> 따뜻한 갈색
