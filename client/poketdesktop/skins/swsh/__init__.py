# -*- coding: utf-8 -*-
"""소드·실드 (8세대 · 닌텐도 스위치) 테마 - DP 틀을 물려받는다 (skins/derive.py).

시안 K (design-notes/ui-revamp/concepts.html 의 '.k') 를 그대로 옮긴다:

    바탕       남색 빗금 (#1c1f3d / #272b55, 135° 24px 띠) + 왼쪽 위 하늘색(#18b5ea) · 오른쪽 아래 분홍(#e8217f)
               모서리. 빗금은 판 바깥 바탕에만 깐다 - 글은 늘 단색 판 위에 둔다 (_sw.backdrop).
    판         흰 판(#f6f7fb) · 두꺼운 흰 테 · 그 바깥 남색 테 (r 14). 글자는 남색, 설명은 #3d4166, 흐린 글은 #8c92b8.
    단추       둥근 알약. 흰 알약 + 남색 글씨, 고른 것은 분홍 알약 + 흰 글씨 (탭 · 줄 세우기 · 주머니).
               주된 일은 분홍 · 흰 테 · 남색 바깥 테 ('지니게 하기').
    고름       목록의 고른 줄은 남색 바탕 + 흰 글씨 + 왼쪽 분홍 띠, 포켓몬 판의 고른 것은 하늘색 테 + 옅은 하늘 바탕.
    배틀       남색 빗금 장면, 남색 이름표 · 흰 테, 오른쪽 세로 기술 목록 (왼쪽 타입 빛깔 칸 + 흰 막대), 분홍 원 (다이맥스 자리).

그 밖의 화면(길드 · 게시판 · 상점 …)은 DP 배치 그대로 두고 빛깔만 이 테마로 옮긴다: 창 바탕은 남색,
판은 흰 판, 주된 단추는 분홍. DP 는 밝은 바탕 위에 진한 글자를 놓았으므로 바탕을 남색으로 바꾸면 바탕에 바로
놓인 글자가 안 보인다 - 그런 글자만 그 자리에서 밝게 바꾼다 (_contrast.install, 이 테마 안에서만).

글꼴은 Pretendard (굵은 고딕 - 시안의 font-weight 800~900).
"""
BASE = "dp"
FONT = "Pretendard"          # Pretendard-Bold.otf · Pretendard-Black.otf (맥 Tk 패밀리 이름 'Pretendard' - 재서 확인)
RADIUS_K = 1.5               # 둥글게 (시안의 칸 r 14 · 알약)
LINE_K = 1.0

# ---------------------------------------------------------------- 시안 K 의 빛깔 (.k { --k-* })
NAVY = "#1c1f3d"             # --k-navy  (바탕 · 글자 · 고른 줄)
NAVY2 = "#272b55"            # --k-navy2 (빗금 · 띠)
NAVY3 = "#363b70"            # 남색 위에서 올렸을 때
CYAN = "#18b5ea"             # --k-cyan  (소드 모서리 · 고른 포켓몬 테)
CYAN_L = "#e3f6fd"           # 고른 포켓몬 판 바탕 (.m.sel)
MAG = "#e8217f"              # --k-mag   (실드 모서리 · 고른 알약 · 주된 단추)
MAG_HI, MAG_LO = "#f2489a", "#a3104f"
PAPER = "#f6f7fb"            # --k-white (판)
PAPER2 = "#e9ebf5"           # 찾기 칸 · 고르지 않은 줄 세우기 알약 (.find · .seg span)
DIMK = "#8c92b8"             # --k-dim
DESC = "#3d4166"             # 설명 글
ON_NAVY = "#ffffff"          # 남색 위 글자
ON_NAVY_DIM = "#b8bde0"      # 남색 위 흐린 글자 (.hpk small)
LINE_P = "#d6d9ec"           # 판 안의 가는 테

# 이전 이름 (다른 파일이 쓴다)
ACCENT = MAG
SKY = "#8fdcf8"              # 남색 띠 위의 제목 (하늘빛)

# skins/dp/__init__.py 의 상수 -> 소드실드 빛깔
PALETTE = {
    "INK": NAVY, "SH": "#d9dbea", "DIM": DIMK, "FAINT": "#b4b8d4", "CUR": MAG,
    "BEZEL": NAVY,
    # 가방 위 화면 (DP 가방 왼쪽 - 이 테마는 bag.py 가 다시 그린다)
    "CYAN1": PAPER, "CYAN2": PAPER2,
    "TAG": NAVY2, "TAG_LINE": NAVY, "TAG_IN": "#4a5090",
    "STRIP": NAVY2, "STRIP_LINE": NAVY, "CELL": PAPER, "CELL_INK": DESC,
    "TAN_L": PAPER, "TAN": PAPER2, "TAN_D": PAPER2, "BROWN": DESC,
    "BTN_TAN": "#ffffff", "BTN_LINE": "#b9bdd8", "BTN_IN": "#ffffff", "BTN_INK": NAVY,
    # 목록 칸: DP 의 '초록 테 안의 흰 목록' -> 남색 테 + 흰 테 + 흰 판 (시안의 .pn)
    "GREEN": NAVY, "GREEN_LINE": NAVY, "GREEN_IN": NAVY,
    "LIST_FRAME": NAVY, "LIST_IN": "#ffffff", "HOVER": "#eceef8",
    # 설명 띠 (DP: 보라) -> 남색 띠, 제목은 하늘빛
    "PURPLE": NAVY2, "PURPLE_HI": NAVY2, "PURPLE_LO": NAVY2, "PURPLE_SH": NAVY2, "PURPLE_EM": SKY,
    # 포켓몬 판: 흰 판 · 고른 것은 하늘 테
    "OLIVE1": NAVY, "OLIVE2": NAVY,
    "PLATE_LINE": LINE_P, "PLATE_TOP": "#ffffff", "PLATE_BOT": "#ffffff", "PLATE_SEL": CYAN,
    "PLATE_GOOD_TOP": "#e7f7ee", "PLATE_GOOD_BOT": "#e7f7ee",
    "PLATE_OFF_TOP": "#e2e4ee", "PLATE_OFF_BOT": "#e2e4ee",
    "PLATE_HOVER_TOP": "#eef0fa", "PLATE_HOVER_BOT": "#eef0fa",
    # 단추 (DP: 파랑 = 주된 일) -> 분홍
    "BLUE": MAG, "BLUE_HI": MAG_HI, "BLUE_LINE": MAG_LO, "BLUE_TOP": "#f57ab3",
    "GRAY_BTN": "#ffffff", "GRAY_HI": "#ffffff", "GRAY_LINE": "#b9bdd8",
    "RED_BTN": "#d33a3a", "RED_HI": "#e25656", "RED_LINE": "#8e2020",
    "OFF_BTN": "#d9dbe8", "OFF_HI": "#d9dbe8", "OFF_LINE": "#b4b8d4",
    "MSG_FRAME": NAVY, "MSG_ST1": "#c5c8de", "MSG_ST2": "#d9dbea", "MSG_ST_LINE": "#a4a9c8",
    # v2 바탕 · 판
    "WIN_BG": NAVY, "PANEL": "#ffffff", "LINE": LINE_P, "LINE_D": NAVY, "INK2": "#4b5079",
    "SEL": CYAN_L, "HOV": "#eceef8", "TAGC": NAVY2, "TAGC_D": NAVY, "SEP": "#e4e6f2",
    # 몬스터볼 빛깔은 그대로
    "BALL_RED": "#e87474", "BALL_WHITE": "#f8f8f4", "BALL_BTN": "#c6c6c6",
}

# DP 화면 코드에 박힌 빛깔 중 따로 정해 둔 것 (나머지는 아래 shade 규칙으로)
COLORS = {
    # 창 바탕 (DP 의 옅은 푸른 회색) -> 남색. 위젯으로 짠 기본 화면의 창 바탕(dp/widgets 가 U.BG 를 옮긴 빛깔) ·
    # 작은 창 몸(dp/dialogs.BODY) · 아래 줄 바탕도 같은 자리다
    "#e8edf2": NAVY, "#eef2f6": NAVY, "#dfe4ea": NAVY2,
    "#cfe0f4": NAVY,                            # 마이페이지 · 설정의 쪽 바탕 (판은 흰 판)
    # kit 의 파란 단추 (주된 일) -> 분홍
    "#3570d0": MAG, "#4682e2": MAG_HI, "#1f4890": MAG_LO,
    # kit 의 회색 단추 -> 흰 알약 · 옅은 테
    "#f4f6f9": "#ffffff", "#8a96a8": "#b9bdd8",
    # kit.entry 의 테 (보통 · 고름) -> 옅은 테 · 분홍
    "#a8b0bc": "#c5c8de", "#e83030": MAG,
    # kit.Scroll 손잡이
    "#d8dde4": "#e2e4ee", "#b8c2d0": "#b4b8d4",
    # 배틀 '기권' (DP 파랑) -> 남색 알약 (battle.py 가 다시 칠한다 - 남는 곳 대비)
    "#3a6fc8": NAVY2, "#4c82d8": NAVY3,
    # 판 목록 안의 글 (DP: 짙은 파랑 · 짙은 올리브) -> 남색 · 설명 빛깔
    "#1c2e44": NAVY, "#34506c": "#4b5079", "#262c14": NAVY, "#2e3418": "#4b5079",
    "#7a8250": "#b9bdd8", "#eef0e2": "#ffffff",
    # 포켓치 (탐험) 몸통 -> 남색, 액정 -> 흰 판
    "#3a3f48": NAVY2, "#4a505a": NAVY3, "#23262d": NAVY,
    "#a8c890": "#ffffff", "#b8d6a0": PAPER, "#24301c": NAVY, "#41522f": "#4b5079",
    # 화면 머리 띠 (DP 는 화면마다 빛깔이 달랐다) -> 남색 띠 (흰 제목)
    "#d83c3c": NAVY2, "#a42424": NAVY,          # 도감 · 업적
    "#3d8a3e": NAVY2, "#2c6a2e": NAVY,          # 관장
    "#c4692c": NAVY2, "#8a4416": NAVY,          # 친구수첩
    "#8c5c2e": NAVY2, "#5e3c1a": NAVY,          # 길드
    "#1d5e80": NAVY,                            # 게시판 띠의 아래 줄
    "#3a68c8": NAVY2, "#1f3c84": NAVY,          # 마이페이지
    "#3a1414": NAVY,                            # 도감 테
    "#fbe8e8": PAPER2, "#8a2020": "#b9bdd8",    # 도감의 세대 · 거르기 탭
    # kit 의 빨간 단추 (DP 의 주된 일) -> 분홍 (되돌릴 수 없는 일만 _fixes 가 빨간 단추로 남긴다)
    "#d8463e": MAG, "#e65a52": MAG_HI, "#962822": MAG_LO,
    # 길드 (비밀기지 모래빛 바탕 -> 남색 바탕 위 흰 판, 고른 방 글씨 -> 분홍)
    "#f4ead8": NAVY, "#dccba8": LINE_P, "#b02424": MAG,
    # 로그인 · 가입의 '마카오 박사 가방' (귤빛 흙빛 상자) -> 남색 상자 · 흰 판
    "#c0843c": NAVY2, "#6a4520": NAVY, "#f6e8c8": PAPER2, "#b08850": "#b9bdd8", "#e4cc96": "#d9dbea",
    # DP 의 '고른 것' 빨간 글씨 (배울 기술 · 고른 탭 · 고른 칭호 · 돌아왔습니다!) -> 분홍
    "#a02020": MAG, "#c02020": MAG,
    # DP 의 귤빛 강조 (게시판 공지 띠 · 운영자 · '나' · '내 길드' · 길드 마스터) -> 분홍, 친구수첩 붉은 여백 줄 -> 옅은 테
    "#e07a28": MAG, "#f0b0a8": LINE_P,
    # 크림빛 고른 줄 · 강조 칸 -> 옅은 하늘빛 (시안의 고른 포켓몬 판)
    "#fff1dc": CYAN_L, "#fff3ec": "#fde8f2", "#fff2d6": CYAN_L,
}

# 이 테마가 직접 쓰는 빛깔 - DP 빛깔 표와 겹쳐도 옮기지 않는다
OWN = dict(NAVY=NAVY, NAVY2=NAVY2, NAVY3=NAVY3, CYAN=CYAN, CYAN_L=CYAN_L, MAG=MAG, MAG_HI=MAG_HI, MAG_LO=MAG_LO,
           PAPER=PAPER, PAPER2=PAPER2, DIMK=DIMK, DESC=DESC, ON_NAVY=ON_NAVY, ON_NAVY_DIM=ON_NAVY_DIM,
           LINE_P=LINE_P, SKY=SKY, WHITE="#ffffff")
# 뜻이 있는 빛깔 (등급 · 정보 글) - 흰 판 위 글씨로 쓰이므로 그대로 둔다
KEEP = tuple(OWN.values()) + ("#8a4ad0", "#2c8a3c", "#c06810", "#6a6a74", "#2a56b8")


def shade(rgb):
    """표에 없는 DP 빛깔 -> 소드실드.

    옅은 바탕(하늘 · 연두 · 크림 · 황토 · 회색)은 옅은 남회색(흰 판 안의 칸)으로, 진한 파랑 · 보라 · 흙빛 띠는
    남색 띠로, 진한 회색 글자는 남색 글자로. 빨강 · 분홍 · 진한 초록 · 진한 주황 · 금빛은 뜻이 있어 그대로."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    deg = h * 360
    nh = 0.65                                          # 남색 쪽 (회색에 조금 섞는다)
    if s < 0.08:                                      # 회색
        if v >= 0.80:
            return colorsys.hsv_to_rgb(nh, 0.05, max(v, 0.90))     # 옅은 회색 바탕 -> 옅은 남회색
        if v >= 0.45:
            return colorsys.hsv_to_rgb(nh, 0.20, v * 0.92)         # 흐린 글 · 테 -> 남빛 회색
        return colorsys.hsv_to_rgb(nh, 0.45, max(0.18, v * 0.85))  # 진한 글자 -> 남색
    if deg < 12 or deg >= 320:                        # 빨강 · 분홍: 위험 · 커서 - 그대로
        return rgb
    if v >= 0.86 and s < 0.35:                        # 아주 옅은 바탕 (크림 · 하늘 · 연두) -> 옅은 남회색
        return colorsys.hsv_to_rgb(nh, s * 0.25, max(v, 0.94))
    if 75 <= deg < 165:                               # 연두 · 초록
        if s >= 0.45:
            return rgb                                # 진한 초록 (좋음 · 포켓몬 단추)
        return colorsys.hsv_to_rgb(nh, s * 0.2, v)
    if 165 <= deg < 255:                              # 하늘 · 파랑
        if s >= 0.42 and v < 0.95:                    # 진한 파랑 (띠 · 꼬리표) -> 남색 띠
            return colorsys.hsv_to_rgb(0.655, 0.55, 0.22 + 0.16 * v)
        return colorsys.hsv_to_rgb(nh, s * 0.25, v)
    if 255 <= deg < 320:                              # 보라
        if v > 0.85 and s < 0.3:
            return colorsys.hsv_to_rgb(nh, s * 0.3, v)
        if s >= 0.4 and v >= 0.6:
            return rgb                                # 진한 보라 (진귀 등급 · 메가) - 뜻이 있다
        return colorsys.hsv_to_rgb(0.655, 0.55, 0.22 + 0.16 * v)
    if 12 <= deg < 60:                                # 주황 · 노랑 · 흙빛
        if s >= 0.55 and v >= 0.70:
            return rgb                                # 진한 주황 · 금빛 (강조 · 반짝이)
        if v < 0.72:
            return colorsys.hsv_to_rgb(0.655, 0.50, 0.22 + 0.16 * v)   # 흙빛 띠 · 갈색 -> 남색
        return colorsys.hsv_to_rgb(nh, s * 0.2, max(v, 0.90))          # 옅은 황토 바탕 -> 옅은 남회색
    return rgb


# 남색 바탕에 바로 놓인 진한 글자를 밝게 (이 테마에서만 - 고리는 _contrast.py)
from . import _contrast  # noqa: E402

_contrast.install()
