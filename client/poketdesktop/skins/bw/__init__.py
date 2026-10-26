# -*- coding: utf-8 -*-
"""블랙·화이트 (5세대 · 닌텐도 DS) 테마 - DP 틀을 물려받는다 (skins/derive.py).

시안 H (design-notes/ui-revamp/concepts.html 의 '.h') 를 그대로 옮긴다:

    바탕        짙은 회색 #15181c, 오른쪽 아래에 C기어의 하늘빛 동그란 고리 두 겹, 옅은 빗금 한 줄 (판 바깥에만)
    판          #22262b 바탕 · #3d444c 가는 테(1) · 둥근 모서리 10
    글씨        밝은 #f2f4f6, 덜 중요한 것은 #99a2ac
    고름 표시   하늘빛 #35c7f3 테 + 둘레에 번지는 빛 (동그란 주머니 단추 · 목록 줄 · 카드 · 기술 카드)
    단추        알약 모양 (테 #3d444c), 주된 일은 하늘빛 알약에 짙은 글씨
    배틀        검은 그라데이션 장면 · 어두운 받침 · 어두운 이름표, 위에 타입 빛깔 띠를 두른 어두운 기술 카드

대표 화면(허브 · 가방 · 배틀)은 이 폴더의 hub.py · bag.py · tms.py · battle.py 가 시안대로 새로 그린다.
나머지 화면(길드 · 게시판 · 도감 …)은 DP 틀 그대로 두고 빛깔만 어둡게 옮긴다 - 아래 _install_hook:

    DP 는 밝은 테마라 같은 빛깔도 '바탕' 이냐 '글씨' 냐에 따라 거꾸로 옮겨야 한다 (흰 판 -> 어두운 판, 진한 글씨 ->
    밝은 글씨). derive.py 의 옮기기는 빛깔만 보므로, 이 테마는 tkinter 가 옵션을 넘기는 자리(Misc._options)에
    옵션 이름 · 캔버스 도형 종류까지 보는 고리를 하나 더 건다 (derive 의 고리 안쪽에서 돈다). 옮기는 것은
    **DP 코드에 박힌 빛깔(dp/_literals.py)만** - 타입 · 체력 · 배틀 장면(derive.KEEP_ALWAYS)과 이 테마가 직접 쓰는
    빛깔은 그대로다. 기본 테마 코드가 만든 위젯은 widgets.py 가 옮긴다 (기본 테마도 어두운 테마라 거의 그대로).

글꼴은 DP 와 같은 갈무리11.
"""
import colorsys

BASE = "dp"
FONT = "Galmuri11"

# ---------------------------------------------------------------- 시안 H 의 빛깔 (concepts.html 의 --h-*)
BG = "#15181c"          # --h-bg   창 바탕
PANEL = "#22262b"       # --h-panel 판
LINE = "#3d444c"        # --h-line  판 테
TEXT = "#f2f4f6"        # --h-white 글씨
DIMT = "#99a2ac"        # --h-dim   덜 중요한 글씨
CYAN = "#35c7f3"        # --h-cyan  고름 · 주된 단추
CARD = "#1b1f23"        # .card     포켓몬 카드 · 기술머신 줄 바탕
GO_INK = "#06222c"      # .go       하늘빛 단추의 글씨
DESC = "#cfd5db"        # 설명 글

# 시안의 반투명 빛깔을 바탕 위에 미리 섞은 것
PANEL_HI = "#2b3036"    # 올렸을 때 · 한 단계 올라온 판
LINE_HI = "#59616b"     # 진한 테 · 올렸을 때의 테
FAINT = "#6b737c"       # 흐린 글씨 (못 쓰는 것)
SEL = "#253d47"         # 고른 줄 바탕 (하늘빛 .14)
GLOW = "#274e5d"        # 고른 것 둘레의 빛 (판 위, 하늘빛 .25)
GLOW_BG = "#1d4452"     # 같은 빛 (창 바탕 위)
GLOW_FAR = "#192d36"    # 멀리 번지는 빛 (하늘빛 .12) · C기어 고리 (안쪽)
RING_FAR = "#18262d"    # C기어 고리 (바깥, 하늘빛 .08)
STRIPE = "#1e2125"      # 바탕의 옅은 빗금 (흰빛 .035)
CYAN_HI = "#5fd3f6"     # 하늘빛 단추를 올렸을 때
CYAN_LO = "#1f8fb3"     # 하늘빛 단추의 테
DEEP = "#0e1013"        # 경첩 · DS 몸통
SKY_D = "#1a7fa6"       # DP 의 파란 단추 · 띠 -> 짙은 하늘빛 (흰 글씨가 읽힌다)
SKY_DH = "#2290b9"
SKY_DL = "#0e5873"
DOT = "#ff4b4b"         # 새 소식 점
MAP_INK = "#1b2026"     # 관장 지도의 밝은 땅 위 이름표 (진한 글씨 - _fixes.py)
MAP_SUB = "#3c4450"     # 같은 이름표의 둘째 줄
PIN = "#1f2a30"         # 게시판 공지 줄 (하늘빛 아주 조금)
PIN_HI = "#243239"      # 공지 줄을 올렸을 때
SEA_D = "#1d3d52"       # 관장 지도 바다 (DP 의 옅은 하늘빛 -> 밤바다)
SEA_W = "#1b3647"       # 길드전 지도 바다 (_fixes.py 가 바탕 한 장으로 깐다)
SEA_W_EDGE = "#2d5b75"  # 길드전 지도 테

# 배틀 (시안 .stage · .pad · .hp · .mv)
STAGE_TOP, STAGE_BOT = "#20262e", BG
PLATE_BG = "#0f1215"    # 이름표 (검정 .55)
HP_TRACK = "#3a4048"
PAD_EDGE = "#353b42"

# ---------------------------------------------------------------- skins/dp/__init__.py 의 상수 -> BW
PALETTE = {
    "INK": TEXT, "SH": DEEP, "DIM": FAINT, "FAINT": "#5f666e", "CUR": CYAN, "BEZEL": DEEP,
    # 가방 위 화면 (bag.py 가 다시 그린다 - 남는 곳 대비)
    "CYAN1": BG, "CYAN2": BG,
    "TAG": PANEL_HI, "TAG_LINE": LINE, "TAG_IN": PANEL,
    "STRIP": PANEL_HI, "STRIP_LINE": LINE, "CELL": CARD, "CELL_INK": DIMT,
    "TAN_L": CARD, "TAN": CARD, "TAN_D": BG, "BROWN": LINE,
    "BTN_TAN": PANEL, "BTN_LINE": LINE, "BTN_IN": PANEL, "BTN_INK": TEXT,
    # 목록 칸
    "GREEN": BG, "GREEN_LINE": BG, "GREEN_IN": BG,
    "LIST_FRAME": LINE, "LIST_IN": PANEL, "HOVER": PANEL_HI,
    # 설명 띠 (DP: 보라) -> 한 단계 올라온 어두운 판, 제목은 하늘빛
    "PURPLE": PANEL_HI, "PURPLE_HI": LINE, "PURPLE_LO": LINE, "PURPLE_SH": DEEP, "PURPLE_EM": CYAN,
    # 파티 판
    "OLIVE1": BG, "OLIVE2": BG,
    "PLATE_LINE": LINE, "PLATE_TOP": CARD, "PLATE_BOT": CARD, "PLATE_SEL": CYAN,
    "PLATE_GOOD_TOP": "#1d3026", "PLATE_GOOD_BOT": "#1d3026",
    "PLATE_OFF_TOP": "#17191c", "PLATE_OFF_BOT": "#17191c",
    "PLATE_HOVER_TOP": "#262b31", "PLATE_HOVER_BOT": "#262b31",
    # 단추 (DP 파랑 -> 짙은 하늘빛)
    "BLUE": SKY_D, "BLUE_HI": SKY_DH, "BLUE_LINE": SKY_DL, "BLUE_TOP": "#2a9cc6",
    "GRAY_BTN": PANEL_HI, "GRAY_HI": "#353b42", "GRAY_LINE": LINE,
    "OFF_BTN": CARD, "OFF_HI": CARD, "OFF_LINE": PANEL_HI,
    "MSG_FRAME": LINE, "MSG_ST1": PANEL_HI, "MSG_ST2": PANEL_HI, "MSG_ST_LINE": LINE,
    # v2 바탕 · 판
    "WIN_BG": BG, "PANEL": PANEL, "LINE": LINE, "LINE_D": LINE_HI, "INK2": "#aeb6bf",
    "SEL": SEL, "HOV": PANEL_HI, "TAGC": "#1e82a8", "TAGC_D": SKY_DL, "SEP": PANEL_HI,
}

# 이 테마가 직접 쓰는 빛깔 (옮기지 않는다)
OWN = dict((k, v) for k, v in globals().items() if k.isupper() and isinstance(v, str) and v.startswith("#"))

# ---------------------------------------------------------------- DP 빛깔 -> BW (바탕 · 글씨를 따로)
# 하나하나 정한 것: (바탕일 때, 글씨일 때). None 이면 규칙대로.
EXPLICIT = {
    "#e83030": (CYAN, CYAN), "#e83838": (CYAN, CYAN),             # DP 커서 (빨강) -> 하늘빛
    "#fff1dc": (SEL, None), "#fff3ec": (SEL, None), "#fff2d6": (SEL, None),   # 고른 줄 · 칸
    "#dbe8f6": (PANEL_HI, None), "#eef4fb": (PANEL_HI, None),      # 올렸을 때
    "#e8edf2": (BG, None), "#eef2f6": (BG, None), "#eceef1": (BG, None),   # 창 바탕
    "#3570d0": (SKY_D, None), "#4682e2": (SKY_DH, None), "#1f4890": (SKY_DL, None),   # kit 의 파란 단추
    "#161b28": (PANEL, None),                                      # 기본 화면의 카드
    "#a8b0bc": (LINE, None),                                       # 입력칸 테
    "#a8c890": (PANEL, None), "#b8d6a0": (PANEL_HI, None),                     # 포켓치 액정 (탐험) -> 어두운 판
    "#24301c": (None, TEXT), "#41522f": (None, DIMT),
    "#3a3f48": (CARD, None), "#4a505a": (LINE, None),                          # 포켓치 몸통
    "#262c14": (None, TEXT), "#2e3418": (None, DIMT), "#7a8250": (LINE, None),   # 올리브 칸의 글 · 탭 테
    # 화면 머리 띠 (DP 는 화면마다 빛깔이 달랐다) -> 한 단계 올라온 어두운 판 (흰 제목이 그대로 읽힌다)
    "#d83c3c": (BG, None), "#a42424": (LINE, None), "#3a1414": (DEEP, None),    # 도감 (빨간 몸통)
    "#fbe8e8": (CARD, None), "#8a2020": (LINE, None),                          # 도감의 세대 · 거르기 탭
    "#3d8a3e": (PANEL_HI, None), "#2c6a2e": (LINE, None),                      # 관장
    "#c4692c": (PANEL_HI, None), "#8a4416": (LINE, None),                      # 친구수첩
    "#8c5c2e": (PANEL_HI, None), "#5e3c1a": (LINE, None),                      # 길드
    "#1d5e80": (LINE, None),                                                   # 게시판 띠 아래 줄
    "#3a68c8": (PANEL_HI, None), "#1f3c84": (LINE, None),                      # 마이페이지
    "#cfe0f4": (BG, None),                                                     # 마이페이지 · 설정 쪽 바탕 (DP 하늘빛)
    "#5c8ce4": (PANEL_HI, None),                                               # 마이페이지 트레이너 카드 (파란 카드)
    "#b02424": (None, CYAN),                                                   # 길드: 고른 방 글씨 (DP 빨강)
    "#fff4d8": (PIN, None), "#ffecc4": (PIN_HI, None),                         # 게시판 공지 줄 (DP 크림)
    "#0b0d13": (DEEP, None),                                                   # 악당 (검정) - 악당 칸 머리 · 지도의 악당 땅
    "#7fb2e5": (SEA_D, None),                                                  # 관장 지도 바다 (땅 빛깔은 그대로)
    # 로그인 - 마카오 박사의 가방 (귤빛 가죽) -> 어두운 판, 스타팅 받침 (모래빛) -> 올라온 판
    "#c0843c": (LINE, None), "#6a4520": (LINE_HI, None), "#f6e8c8": (CARD, None), "#b08850": (LINE, None),
    "#e4cc96": (PANEL_HI, None),
}

# 화면에 따라 뜻이 다른 글씨 빛깔: DP 빨강이 '고른 것' 인 화면만 하늘빛으로 (묻는 창의 빨강은 '위험' 이라 그대로)
SCREEN_FG = {
    "login": {"#c02020": CYAN, "#a02020": CYAN},     # 고른 탭 · 고른 스타팅 이름
    "learn": {"#a02020": CYAN},                      # 고른 기술 이름
    "season": {"#a02020": CYAN},                     # 고른 칭호 · 명패
}
_SCREEN_FG_ANY = frozenset(c for m in SCREEN_FG.values() for c in m)

# DP 화면이 셈해서 만든 빛깔(꼬리표의 옅은 바탕 · 진한 글씨 같은 것)도 옮기는 화면 - 장면 · 지도 · 포켓몬 빛깔을
# 셈하는 화면(배틀 · 지도 · 이로치 색 …)은 빼고, 그 밖의 DP 화면에서 부른 것만.
COMPUTED_SKIP = frozenset(("battle", "raid_battle", "gym_battle", "live_battle", "tint", "gym", "war_map",
                           "guild_war", "login", "learn", "loading"))


def _hsv(c):
    c = c.lstrip("#")
    return colorsys.rgb_to_hsv(*(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v * 255)))) for v in rgb)


def mix(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#%02x%02x%02x" % tuple(int(round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t))
                                   for i in (0, 2, 4))


def _neutral_bg(v, line=False):
    if v >= 0.9 and not line:                      # 판 · 창 바탕 (밝을수록 위로 올라온 판)
        return mix(BG, PANEL, min(1.0, (v - 0.9) / 0.1))
    if v >= 0.8:                                   # 옅은 테 (테) · 꺼진 칸 · 한 단계 올라온 판 (바탕)
        return LINE if line else PANEL_HI
    if v >= 0.55:                                  # 진한 테 · 막대 손잡이
        return LINE_HI
    if v >= 0.25:                                  # 짙은 테 · 짙은 띠 (어두운 판 위에서는 밝은 테)
        return LINE
    return DEEP


def to_bg(c, line=False):
    """DP 의 바탕 빛깔 -> BW. line 이면 테 (outline) - 옅은 회색은 판이 아니라 테 빛깔로."""
    h, s, v = _hsv(c)
    deg = h * 360
    if s < 0.12 or (s < 0.35 and v < 0.85) or (line and s < 0.45):
        return _neutral_bg(v, line)
    if v >= 0.85 and s < 0.45:                     # 옅은 빛 바탕 (크림 · 하늘 · 연두 · 분홍) -> 어두운 판에 그 빛 조금
        hue = 195 / 360.0 if 170 <= deg < 260 else h
        return mix(CARD, _hex(colorsys.hsv_to_rgb(hue, 0.75, 0.95)), 0.08 + 0.25 * min(s, 0.6))
    if 170 <= deg < 235:                           # 진한 파랑 (단추 · 꼬리표 · 띠) -> 짙은 하늘빛
        return SKY_D if v >= 0.45 else SKY_DL
    if 15 <= deg < 48 and v < 0.62:                # 흙빛 머리 띠 (길드 · 친구수첩 …) -> 올라온 판
        return PANEL_HI if v >= 0.4 else LINE
    return c                                       # 빨강 · 주황 · 금빛 · 초록 · 보라 - 뜻이 있는 빛깔


def to_fg(c):
    """DP 의 글씨 빛깔 -> BW (밝은 바탕용 진한 글씨 -> 어두운 바탕용 밝은 글씨)."""
    h, s, v = _hsv(c)
    if s < 0.25:
        if v < 0.35:
            return TEXT
        if v < 0.5:
            return "#aeb6bf"
        if v < 0.7:
            return "#8a929b"
        if v < 0.85:
            return FAINT
        return c
    if v >= 0.85:
        return c
    return _hex(colorsys.hsv_to_rgb(h, min(s, 0.75) * 0.82, 0.96))


_ROLE = [None, False]   # [지금 만드는 · 고치는 캔버스 도형 종류 ('text' 면 fill 이 글씨), 새로 만드는 중인가]
FG_KEYS = frozenset(("fg", "foreground", "insertbackground", "selectforeground", "disabledforeground",
                     "activeforeground", "highlightcolor"))
LINE_KEYS = frozenset(("outline", "activeoutline", "disabledoutline", "highlightbackground"))


def _install_hook():
    """옵션 이름 · 도형 종류를 보고 DP 빛깔을 옮기는 고리 (이 테마일 때 한 번)."""
    import tkinter as tk
    from .. import derive
    from ... import ui_common as U
    from ..dp._literals import LITERALS
    keep = set(derive.KEEP_ALWAYS)
    keep.update(c.lower() for c in U.TYPE_COLOR.values())
    keep.update(c.lower() for c in OWN.values())
    keep.update(c.lower() for c in PALETTE.values())
    keep.add("#000000")
    keep.discard("#ffffff")
    import sys
    memo = {}
    dp_pkg = __name__.rsplit(".", 1)[0] + ".dp."
    # 건너뛰는 곳: tkinter · 빛깔 고리(derive · 이 파일) · 그리기 부품
    passthru = frozenset((__name__, derive.__name__, dp_pkg + "kit", dp_pkg + "widgets", __name__ + "._art"))

    def dp_caller():
        """이 빛깔을 넘긴 곳이 (빼 둔 것 말고) DP 화면 코드인가 - tkinter 와 그리기 부품은 건너뛰고 본다."""
        f = sys._getframe(1)
        while f is not None:
            mod = f.f_globals.get("__name__", "")
            if mod in passthru or mod.startswith("tkinter"):
                f = f.f_back
                continue
            return mod.startswith(dp_pkg) and mod[len(dp_pkg):] not in COMPUTED_SKIP
        return False

    def dp_screen():
        """이 빛깔을 넘긴 DP 화면 이름 (login · learn …), DP 화면이 아니면 None."""
        f = sys._getframe(1)
        while f is not None:
            mod = f.f_globals.get("__name__", "")
            if mod in passthru or mod.startswith("tkinter"):
                f = f.f_back
                continue
            return mod[len(dp_pkg):] if mod.startswith(dp_pkg) else None
        return None

    def recolor(c, role):
        if not isinstance(c, str) or len(c) != 7 or c[0] != "#":
            return c
        low = c.lower()
        if role == "fg" and low in _SCREEN_FG_ANY:          # 화면마다 뜻이 다르다 - 기억해 두지 않는다
            alt = SCREEN_FG.get(dp_screen() or "", {}).get(low)
            if alt:
                return alt
        got = memo.get((low, role))
        if got is not None:
            return got
        out = low
        if low in EXPLICIT and EXPLICIT[low][1 if role == "fg" else 0]:
            out = EXPLICIT[low][1 if role == "fg" else 0]
        elif low in keep:
            pass
        elif low in LITERALS:
            out = to_fg(low) if role == "fg" else to_bg(low, role == "line")
        else:
            # DP 화면이 셈한 빛깔 - 부른 곳을 봐야 하므로 기억해 두지 않는다
            if low == "#ffffff" or not dp_caller():
                return c
            return to_fg(low) if role == "fg" else to_bg(low, role == "line")
        memo[(low, role)] = out
        return out

    base = tk.Misc._options

    def _options(self, cnf, kw=None):
        res = base(self, cnf, kw)
        if not res:
            return res
        out = list(res)
        kind = _ROLE[0]
        text = kind == "text"
        has_fill = False
        for i in range(0, len(out) - 1, 2):
            k = out[i]
            if not isinstance(k, str):
                continue
            key = k[1:]
            if key == "fill":
                has_fill = True
            if key in derive.COLOR_KEYS:
                if key in FG_KEYS or (text and key == "fill"):
                    role = "fg"
                elif key in LINE_KEYS or (kind == "line" and key == "fill"):
                    role = "line"
                else:
                    role = "bg"
                out[i + 1] = recolor(out[i + 1], role)
        if text and _ROLE[1] and not has_fill:          # 빛깔 없이 만든 글씨는 Tk 기본(검정) - 밝은 글씨로
            out += ["-fill", TEXT]
        return tuple(out)

    base_create = tk.Canvas._create

    def _create(self, itemType, args, kw):
        old = _ROLE[:]
        _ROLE[0], _ROLE[1] = itemType, True
        try:
            return base_create(self, itemType, args, kw)
        finally:
            _ROLE[:] = old

    base_item = tk.Canvas.itemconfigure

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        if cnf is None and not kw:
            return base_item(self, tagOrId, cnf, **kw)
        try:
            kind = self.type(tagOrId)
        except tk.TclError:
            kind = None
        old = _ROLE[:]
        _ROLE[0], _ROLE[1] = kind, False
        try:
            return base_item(self, tagOrId, cnf, **kw)
        finally:
            _ROLE[:] = old

    tk.Misc._options = _options
    tk.Canvas._create = _create
    tk.Canvas.itemconfigure = itemconfigure
    tk.Canvas.itemconfig = itemconfigure
    return recolor


RECOLOR = None


def _maybe_install():
    global RECOLOR
    from .. import active
    if active() == "bw" and RECOLOR is None:
        RECOLOR = _install_hook()


_maybe_install()
