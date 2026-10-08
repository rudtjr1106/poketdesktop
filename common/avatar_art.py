# -*- coding: utf-8 -*-
"""캐릭터 도트를 그린다 (마이페이지의 캐릭터 만들기).

    sheet = walk_sheet(spec)      # 96x128: 줄 = 아래·왼쪽·오른쪽·위, 칸 = [왼발, 서 있음, 오른발]
    one = cell(spec, "down", "stand")

**그림 파일이 없다.** 부위(머리 모양·모자·안경·옷·바지·신발·가방)를 전부 여기서 점으로 찍어
겹친다. 서버와 화면이 같은 코드로 그리므로, 화면은 고른 것(spec)만 보내고 서버가 다시 그린다 -
남이 볼 그림을 화면이 올리게 두지 않는다.

전부 **우리가 그린 것**이다. 한 칸 32x32 에 머리가 큰 2등신, 방향마다 세 칸이라는 규격만 흔한
것을 따랐다. 몸집은 일부러 뭉툭하게 잡았다 (머리 18칸 폭, 몸통과 팔을 합쳐 16칸 폭).

## 그리는 법

부위마다 '조각' 이 있다. 조각은 (x, y, 글자들) 의 목록이고, 글자 하나가 점 하나다:

    .  건너뜀      1  테두리(가장 어두운 색)      2  그늘      3  바탕      4  밝은 곳

같은 조각에 색 사다리(ramp)만 바꿔 끼우면 다른 색이 된다. 사다리는 바탕색 하나에서 만든다.
머리 쪽 조각은 머리의 왼쪽 위를 (0, 0) 으로 적는다 (앞·뒤 머리는 18x14, 옆 머리는 16x14).
오른쪽을 보는 칸은 따로 그리지 않고 왼쪽을 뒤집는다.

Pillow 를 쓰지 않는다 (서버에 없다). 그림은 [(r, g, b, a), ...] 의 줄 목록이다.
"""
import struct
import zlib

CELL = 32
DIRS = ("down", "left", "right", "up")
FRAMES = ("a", "stand", "b")            # 왼발 · 서 있음 · 오른발  (걷는 순서는 stand-a-stand-b)

CLEAR = (0, 0, 0, 0)
EYE = (40, 34, 52, 255)
GLINT = (255, 255, 255, 255)

# ---------------------------------------------------------------- 색
SKIN = {
    "light": (255, 226, 200), "fair": (250, 208, 174), "tan": (230, 176, 132),
    "brown": (190, 132, 96), "deep": (140, 94, 68), "dark": (100, 68, 54),
}
HAIR_COLORS = {
    "black": (58, 54, 68), "darkbrown": (98, 66, 52), "brown": (150, 100, 64), "blonde": (240, 206, 110),
    "orange": (236, 140, 68), "red": (206, 70, 70), "pink": (244, 150, 182), "purple": (150, 110, 206),
    "blue": (86, 134, 222), "teal": (70, 174, 174), "green": (110, 190, 102), "gray": (172, 176, 190),
    "white": (238, 238, 246),
}
CLOTH = {
    "white": (242, 242, 246), "gray": (156, 160, 172), "black": (70, 70, 84), "red": (220, 78, 78),
    "orange": (242, 150, 70), "yellow": (246, 212, 94), "green": (102, 182, 102), "forest": (62, 126, 94),
    "teal": (70, 174, 182), "sky": (126, 190, 242), "blue": (78, 118, 214), "navy": (62, 74, 134),
    "purple": (150, 102, 198), "pink": (242, 150, 182), "brown": (146, 102, 70), "beige": (226, 204, 166),
}


def _mix(c, to, t):
    return tuple(int(round(c[i] + (to[i] - c[i]) * t)) for i in range(3))


def ramp(base):
    """바탕색 하나 -> (테두리, 그늘, 바탕, 밝은 곳). 어두운 쪽은 조금 푸르게 기운다."""
    edge = _mix(_mix(base, (26, 20, 50), 0.64), (0, 0, 0), 0.10)
    shade = _mix(base, (52, 42, 96), 0.28)
    light = _mix(base, (255, 255, 255), 0.42)
    return (edge + (255,), shade + (255,), tuple(base) + (255,), light + (255,))


# ---------------------------------------------------------------- 도화지
def blank():
    return [[CLEAR] * CELL for _ in range(CELL)]


def put(cv, piece, ox, oy, colors):
    """조각을 찍는다. colors = (테두리, 그늘, 바탕, 밝은 곳)."""
    for x, y, text in piece:
        yy = oy + y
        if not 0 <= yy < CELL:
            continue
        line = cv[yy]
        xx = ox + x
        for ch in text:
            if ch != "." and 0 <= xx < CELL:
                line[xx] = colors[ord(ch) - 49]
            xx += 1


def dot(cv, x, y, color):
    if 0 <= x < CELL and 0 <= y < CELL:
        cv[y][x] = color


def flip(cv):
    return [list(reversed(row)) for row in cv]


def mirror(piece, width):
    """조각을 좌우로 뒤집는다 (폭 width 안에서)."""
    return [(width - x - len(text), y, text[::-1]) for x, y, text in piece]


def rows(y0, *lines):
    """(x, 글자들) 을 위에서부터 한 줄씩 -> 조각. None 은 빈 줄."""
    out = []
    for i, ln in enumerate(lines):
        if ln is None:
            continue
        if isinstance(ln[0], int):
            ln = (ln,)
        for x, text in ln:
            out.append((x, y0 + i, text))
    return out


# ---------------------------------------------------------------- 자리
HX, HY = 7, 5            # 앞·뒤 머리(18x14)의 왼쪽 위
SX = 8                   # 옆 머리(16x14)의 왼쪽
TX, TY = 8, 18           # 윗옷(팔 포함 16칸 폭)의 왼쪽 위 - 앞·뒤
LX, LY = 11, 25          # 엉덩이·다리(10칸 폭)의 왼쪽 위 - 앞·뒤

# ---------------------------------------------------------------- 조각: 머리
HEAD_F = rows(0,
              (6, "111111"),
              (4, "1133333311"),
              (2, "11333333333311"),
              (1, "1333333333333331"),
              (0, "133333333333333331"),
              (0, "133333333333333331"),
              (0, "133333333333333331"),
              (0, "133333333333333331"),
              (0, "133333333333333331"),
              (0, "133333333333333331"),
              (0, "123333333333333321"),
              (1, "1233333333333321"),
              (2, "12223333332221"),
              (4, "1111111111"))
HEAD_S = rows(0,
              (5, "11111111"),
              (3, "113333333311"),
              (2, "13333333333331"),
              (1, "133333333333331"),
              (0, "1333333333333331"),
              (0, "1333333333333331"),
              (0, "1333333333333331"),
              (0, "1333333333333331"),
              (0, "1333333333333331"),
              (0, "1333333333333331"),
              (1, "133333333333321"),
              (1, "123333333333321"),
              (2, "1222333332221"),
              (4, "111111111"))

# 머리카락. 정수리(cap)는 모든 머리 모양이 같이 쓰고, 앞머리·옆머리·뒷머리·덧붙이는 것을 골라 얹는다.
CAP_F = rows(-2,
             (6, "111111"),
             (4, "1133443311"),
             (2, "11334444333311"),
             (1, "1334443333333331"),
             (0, "133444333333333321"),
             (0, "133443333333333321"),
             (0, "133333333333333321"),
             (0, "133333333333333321"))
CAP_S = rows(-2,
             (5, "11111111"),
             (3, "113344333311"),
             (2, "13344443333331"),
             (1, "1334443333333331"),
             (0, "133443333333333321"),
             (0, "133333333333333321"),
             (0, "133333333333333321"),
             (0, "133333333333333321"))
# 앞머리: 6·7번 줄 (눈은 8·9번 줄). 6번 줄은 폭 전체, 7번 줄은 3~14번 칸.
FRINGE_F = {
    "jagged": rows(6, (0, "133333133331333321"), (3, "131.1331.131")),
    "straight": rows(6, (0, "133333333333333321"), (3, "111111111111")),
    "parted": rows(6, ((0, "1333331"), (11, "1333321")), ((3, "131"), (12, "131"))),
    "swept": rows(6, (0, "133333333333333321"), (3, "122222221")),
    "open": rows(6, ((0, "133"), (3, "111111111111"), (15, "321"))),
}
FRINGE_S = {
    "jagged": rows(6, (0, "13333"), (0, "131"), (0, "11")),
    "straight": rows(6, (0, "13333"), (0, "1111")),
    "parted": rows(6, (0, "13333"), (0, "11")),
    "swept": rows(6, (0, "13333"), (0, "121"), (0, "1")),
    "open": rows(6, (0, "11111")),
}
# 옆머리(앞에서 볼 때 얼굴 양옆으로 내려오는 것): 7번 줄부터
SIDES_F = {
    "short": rows(7, ((0, "133"), (15, "321")), ((0, "121"), (15, "121")), ((0, "11"), (16, "11"))),
    "mid": rows(7, *([((0, "133"), (15, "321"))] * 5 + [((0, "123"), (15, "321")), ((0, "11"), (16, "11"))])),
    "long": rows(7, *([((0, "133"), (15, "321"))] * 8
                      + [((0, "123"), (15, "321")), ((0, "121"), (15, "121")), ((1, "1"), (16, "1"))])),
}
# 뒤통수(뒤에서 볼 때): 6번 줄부터
_STRAND = (0, "133323333332333321")
BACK_F = {
    "short": rows(6, (0, "133333333333333321"), (0, "133333333333333321"), _STRAND, _STRAND,
                  (0, "123323333332333221"), (1, "1223233332322221"), (2, "11222222222211"),
                  (4, "1111111111")),
    "mid": rows(6, (0, "133333333333333321"), (0, "133333333333333321"), _STRAND, _STRAND, _STRAND,
                _STRAND, _STRAND, (0, "123323333332333221"), (0, "122222222222222221"),
                (1, "1111111111111111")),
    "long": rows(6, *([(0, "133333333333333321")] * 2 + [_STRAND] * 8
                      + [(0, "123323333332333221"), (1, "1222322223222221"), (2, "11111111111111")])),
}
# 옆에서 볼 때 귀 뒤로 넘어가는 머리: 6번 줄부터 (얼굴 쪽은 FRINGE_S 가 그린다)
_SB = (8, "1233333321")          # 귀 뒤부터
_SL = (10, "12333321")           # 목 아래로 내려오는 부분: 등 뒤로만
BACK_S = {
    "short": rows(6, (5, "3333333333321"), (6, "133333333321"), _SB, _SB, _SB, (9, "123333221"),
                  (10, "12222211"), (11, "111111")),
    "mid": rows(6, (5, "3333333333321"), (6, "133333333321"), _SB, _SB, _SB, _SB, (9, "123333321"),
                (10, "12333321"), (10, "12222221"), (11, "111111")),
    "long": rows(6, *([(5, "3333333333321"), (6, "133333333321"), _SB, _SB, _SB, _SB, (9, "123333321")]
                      + [_SL] * 6 + [(10, "12222221"), (11, "111111")])),
}
# 덧붙이는 것
SPIKES_F = rows(-5, (3, "1.....11.....1"), (2, "131...1331...131"), (1, "13331.133331.13331"),
                (1, "133331333333133331"))
SPIKES_S = rows(-5, (4, "1.....1....1"), (3, "131...131..131"), (2, "13331.13331.1331"),
                (2, "1333313333313331"))
TAIL = rows(0, (1, "11"), (0, "1221"), (0, "1331"), (0, "1331"), (0, "1331"), (0, "1331"), (0, "1331"),
            (0, "1331"), (0, "1321"), (1, "121"), (1, "11"))
# 양갈래: 왼쪽 갈래(끝이 바깥으로 휜다). 오른쪽은 좌우를 뒤집어 쓴다.
TWIN_L = rows(0, (3, "11"), (2, "1221"), (1, "13331"), (0, "133331"), (0, "13331"), (0, "13331"),
              (0, "13321"), (0, "1321"), (0, "1321"), (0, "121"), (1, "1"))
PONY_B = rows(0, (2, "11"), (1, "1221"), (0, "133331"), (0, "133331"), (0, "133331"), (0, "133331"),
              (0, "133331"), (0, "123321"), (1, "1221"), (2, "11"))
BUN = rows(-5, (1, "111111"), (0, "13443331"), (0, "13333321"), (1, "111111"))
# 포니테일을 앞에서 볼 때: 머리 뒤에서 오른쪽 어깨 쪽으로 삐져나온 꼬리 끝.
# (이게 없으면 앞모습이 짧은 머리와 똑같다 - 꾸미기 창의 칸도, 마이페이지의 그림도 구분이 안 된다.)
PONY_F = rows(0, (1, "11"), (0, "1331"), (0, "13331"), (1, "1331"), (1, "1321"), (2, "121"), (3, "1"))

# 머리 모양 = (앞머리, 길이, 덧붙이는 것)
HAIR = {
    "short": ("jagged", "short", None),
    "bangs": ("straight", "short", None),
    "parted": ("parted", "short", None),
    "swept": ("swept", "short", None),
    "spiky": ("jagged", "short", "spikes"),
    "bob": ("straight", "mid", None),
    "bobpart": ("parted", "mid", None),
    "long": ("parted", "long", None),
    "longbangs": ("straight", "long", None),
    "pony": ("jagged", "short", "pony"),
    "twin": ("straight", "short", "twin"),
    "bun": ("open", "short", "bun"),
    "bald": None,
}

# ---------------------------------------------------------------- 조각: 모자
_RIB = "1" + "32" * 8 + "1"
HAT = {
    "cap": {
        "front": rows(-2, (6, "111111"), (4, "1133443311"), (2, "11334443333311"), (1, "1334443333333321"),
                      (0, "133443333333333321"), (0, "133333333333333321"), (0, "133333333333333321"),
                      (0, "111111111111111111"), (-1, "12222222222222222221"), (0, "111111111111111111")),
        "back": rows(-2, (6, "111111"), (4, "1133443311"), (2, "11334443333311"), (1, "1334443333333321"),
                     (0, "133443333333333321"), (0, "133333333333333321"), (0, "133333333333333321"),
                     (0, "133333311333333321"), ((0, "12222221"), (10, "12222221")),
                     ((1, "111111"), (11, "111111"))),
        "side": rows(-2, (5, "11111111"), (3, "113344333311"), (2, "13344433333331"),
                     (1, "1334443333333321"), (0, "133443333333333321"), (0, "133333333333333321"),
                     (0, "133333333333333321"), (-2, "11111111133333333321"),
                     ((-2, "122222221"), (7, "33333333321")), ((-1, "1111111"), (7, "11111111111"))),
        "covers": True,
    },
    "beanie": {
        "front": rows(-3, (7, "1111"), (6, "134431"), (4, "1111111111"), (2, "11334433333311"),
                      (1, "1334443333333321"), (0, "133443333333333321"), (0, "133333333333333321"),
                      (0, "111111111111111111"), (0, _RIB), (0, _RIB), (0, "111111111111111111")),
        "side": rows(-3, (6, "1111"), (5, "134431"), (3, "1111111111"), (1, "11334433333311"),
                     (0, "1334443333333321"), (0, "133443333333333321"), (0, "133333333333333321"),
                     (0, "111111111111111111"), (0, _RIB), (0, _RIB), (0, "111111111111111111")),
        "covers": True,
    },
    # 벙거지: 윗면이 평평한 통(머리를 다 덮는다 - 머리카락보다 좁으면 옆으로 머리가 삐져나와 모자가
    # 얹힌 것처럼 보인다) + 이음선 한 줄 + 거기서 꺾여 아래로 처진 챙. 돌려 봐도 같은 모양이라
    # 앞·옆·뒤가 같다.
    "bucket": {
        "front": rows(-2, (3, "111111111111"), (1, "1134443333333311"), (0, "133443333333333321"),
                      (0, "133333333333333321"), (0, "133333333333333321"), (0, "122222222222222221"),
                      (-2, "1133333333333333333311"), (-3, "134433333333333333333221"),
                      (-3, "13" + "1" * 20 + "21"), ((-3, "11"), (19, "11"))),      # 챙 끝은 한 칸 더 처진다
        "covers": True,
    },
    "beret": {
        "front": rows(-3, (9, "11"), (5, "11111111"), (2, "11133443333111"), (0, "133344433333333321"),
                      (0, "133443333333333321"), (0, "123333333333333221"), (1, "1122222222222211"),
                      (3, "111111111111")),
        "side": rows(-3, (8, "11"), (4, "11111111"), (1, "11133443333111"), (0, "1333444333333321"),
                     (0, "1334433333333321"), (0, "1233333333333221"), (1, "11222222222211"),
                     (3, "1111111111")),
        "covers": True,
    },
    "band": {
        "front": rows(3, (0, "111111111111111111"), (0, "134433333333333321"), (0, "111111111111111111")),
        "side": rows(3, (0, "111111111111111111"), (0, "134433333333333321"), (0, "111111111111111111")),
        "covers": False,
    },
    "ribbon": {
        "front": rows(-3, ((1, "11"), (6, "11")), (0, "13311331"), (0, "13412431"), ((0, "11"), (3, "11"), (6, "11"))),
        "side": rows(-3, ((8, "11"), (13, "11")), (7, "13311331"), (7, "13412431"), ((7, "11"), (10, "11"), (13, "11"))),
        "back": rows(-3, ((10, "11"), (15, "11")), (9, "13311331"), (9, "13412431"), ((9, "11"), (12, "11"), (15, "11"))),
        "covers": False,
    },
}
for _h in HAT.values():
    _h.setdefault("side", _h["front"])
    _h.setdefault("back", _h["front"])

# ---------------------------------------------------------------- 조각: 안경
# 테는 '1', 선글라스의 알은 '1' 로 메우고 반짝임만 '4'. 눈(앞 4·5와 12·13번 칸, 옆 3·4번 칸의 8·9번 줄)은
# 안경보다 먼저 그려 두므로, 테 안쪽을 비워 두면 알 너머로 보인다.
GLASSES = {
    "round": {
        "front": rows(7, ((4, "11"), (12, "11")), ((3, "1"), (6, "11111"), (14, "1")),
                      ((3, "1"), (6, "1"), (11, "1"), (14, "1")), ((4, "11"), (12, "11"))),
        "side": rows(7, (3, "11"), ((2, "1"), (5, "111111")), ((2, "1"), (5, "1")), (3, "11")),
    },
    "square": {
        "front": rows(7, ((3, "1111"), (11, "1111")), ((3, "1"), (6, "111111"), (14, "1")),
                      ((3, "1"), (6, "1"), (11, "1"), (14, "1")), ((3, "1111"), (11, "1111"))),
        "side": rows(7, (2, "1111"), ((2, "1"), (5, "111111")), ((2, "1"), (5, "1")), (2, "1111")),
    },
    "half": {
        "front": rows(7, ((3, "1111"), (11, "1111")), ((3, "1"), (6, "111111"), (14, "1"))),
        "side": rows(7, (2, "1111"), ((2, "1"), (5, "111111"))),
    },
    "shades": {
        "front": rows(7, ((3, "1111"), (11, "1111")), (3, "141111111411"), ((3, "1111"), (11, "1111"))),
        "side": rows(7, (2, "1111"), (2, "141111111"), (2, "1111")),
    },
}

# ---------------------------------------------------------------- 조각: 몸 (앞·뒤)
TOP_F = rows(0,
             (2, "111111111111"),
             (1, "13333333333321"),
             (3, "1333333321"),
             (3, "1333333321"),
             (3, "1333333321"),
             (3, "1333333321"),
             (3, "1222222221"))
ARM = rows(0, (0, "1331"), (0, "1331"), (0, "1331"), (0, "1321"), (0, "1331"), (1, "11"))
SLEEVE_LONG = rows(0, (0, "1331"), (0, "1331"), (0, "1331"), (0, "1221"))
SLEEVE_SHORT = rows(0, (0, "1331"), (0, "1221"))
HIP = rows(0, (0, "1333333321"))
LEG = rows(0, (0, "13331"), (0, "13321"))
SHOE = rows(0, (0, "144331"), (0, "133321"), (0, "111111"))
BOOT = rows(-1, (1, "13331"), (0, "144331"), (0, "133321"), (0, "111111"))
SKIRT = rows(0, (1, "1333333321"), (0, "122222222221"))

# 옆 (왼쪽을 본다)
TOP_S = rows(0,
             (2, "111111"),
             (1, "13333321"),
             (0, "1333333321"),
             (0, "1333333321"),
             (0, "1333333321"),
             (0, "1333333321"),
             (1, "12222221"))
HIP_S = rows(0, (0, "13333321"))
LEG_S = rows(0, (0, "13331"), (0, "13321"))
LEGS_S = rows(0, (0, "133331"), (0, "133321"))          # 서 있을 때: 두 다리가 겹쳐 하나로 보인다
SHOE_S = rows(0, (0, "1443331"), (0, "1333321"), (0, "1111111"))
BOOT_S = rows(-1, (2, "13331"), (0, "1443331"), (0, "1333321"), (0, "1111111"))
SKIRT_S = rows(0, (1, "13333321"), (0, "1222222221"))

# ---------------------------------------------------------------- 조각: 가방
BACKPACK_BACK = rows(0, (2, "11111111"), (1, "1344333321"), (1, "1333333321"), (1, "1322222221"),
                     (1, "1333333321"), (1, "1333113321"), (2, "11111111"))
BACKPACK_SIDE = rows(0, (0, "111"), (0, "1431"), (0, "1331"), (0, "1321"), (0, "1331"), (0, "111"))
POUCH = rows(0, (0, "1111"), (0, "1431"), (0, "1321"), (0, "1111"))

LONG_SLEEVES = ("long", "shirt", "hoodie", "jacket")

# ---------------------------------------------------------------- 고를 수 있는 것
# 화면이 이 목록으로 단추를 만들고, 서버가 이 목록으로 보내온 것을 검사한다.
# (열쇠, 이름, [(값, 이름), ...], 색을 고르는 열쇠 또는 None)
SKIN_KR = {"light": "밝은", "fair": "살구", "tan": "구릿빛", "brown": "갈색", "deep": "짙은 갈색", "dark": "어두운"}
PARTS = [
    ("hair", "머리", [("short", "짧은 머리"), ("bangs", "일자 앞머리"), ("parted", "가르마"),
                     ("swept", "넘긴 머리"), ("spiky", "뾰족 머리"), ("bob", "단발"),
                     ("bobpart", "가르마 단발"), ("long", "긴 머리"), ("longbangs", "긴 머리 앞머리"),
                     ("pony", "포니테일"), ("twin", "양갈래"), ("bun", "올림머리"), ("bald", "민머리")],
     "hairColor"),
    ("hat", "모자", [("", "없음"), ("cap", "캡"), ("beanie", "비니"), ("bucket", "벙거지"),
                    ("beret", "베레모"), ("band", "머리띠"), ("ribbon", "리본")], "hatColor"),
    ("glasses", "안경", [("", "없음"), ("round", "동그란 테"), ("square", "네모 테"), ("half", "반테"),
                        ("shades", "선글라스")], "glassesColor"),
    ("top", "윗옷", [("tee", "반팔"), ("long", "긴팔"), ("stripe", "줄무늬"), ("logo", "로고 티"),
                    ("shirt", "셔츠"), ("hoodie", "후드"), ("jacket", "겉옷"), ("overalls", "멜빵바지"),
                    ("tank", "민소매")], "topColor"),
    ("bottom", "바지", [("pants", "긴 바지"), ("shorts", "반바지"), ("skirt", "치마")], "bottomColor"),
    ("shoes", "신발", [("sneakers", "운동화"), ("boots", "부츠")], "shoeColor"),
    ("bag", "가방", [("", "없음"), ("backpack", "배낭"), ("satchel", "어깨 가방"), ("pouch", "허리 가방")],
     "bagColor"),
]
# 색을 고르는 열쇠 -> 그 색표
PALETTES = {"skin": SKIN, "hairColor": HAIR_COLORS, "hatColor": CLOTH, "glassesColor": CLOTH,
            "topColor": CLOTH, "bottomColor": CLOTH, "shoeColor": CLOTH, "bagColor": CLOTH}
DEFAULT = {"skin": "fair", "hair": "short", "hairColor": "brown", "hat": "", "hatColor": "teal",
           "glasses": "", "glassesColor": "black", "top": "tee", "topColor": "sky", "bottom": "pants",
           "bottomColor": "navy", "shoes": "sneakers", "shoeColor": "white", "bag": "", "bagColor": "orange"}


def clean(spec):
    """보내온 것을 믿지 않는다: 아는 열쇠·아는 값만 남기고 나머지는 기본값으로 채운다."""
    out = dict(DEFAULT)
    if not isinstance(spec, dict):
        return out
    for key, _name, options, _color in PARTS:
        v = spec.get(key)
        if isinstance(v, str) and v in [o[0] for o in options]:
            out[key] = v
    for key, table in PALETTES.items():
        v = spec.get(key)
        if isinstance(v, str) and v in table:
            out[key] = v
    return out


def random_spec(rng):
    """아무렇게나 고른 캐릭터 (화면의 '무작위' 단추). 모자·안경·가방은 없을 때가 더 많다."""
    out = {}
    for key, _name, options, _color in PARTS:
        values = [o[0] for o in options]
        if "" in values and rng.random() < 0.55:
            out[key] = ""
        else:
            out[key] = rng.choice([v for v in values if v] or values)
    for key, table in PALETTES.items():
        out[key] = rng.choice(sorted(table))
    return clean(out)


# ---------------------------------------------------------------- 그리기
def _colors(spec):
    return {
        "skin": ramp(SKIN.get(spec.get("skin")) or SKIN["fair"]),
        "hair": ramp(HAIR_COLORS.get(spec.get("hairColor")) or HAIR_COLORS["brown"]),
        "top": ramp(CLOTH.get(spec.get("topColor")) or CLOTH["sky"]),
        "bottom": ramp(CLOTH.get(spec.get("bottomColor")) or CLOTH["navy"]),
        "shoe": ramp(CLOTH.get(spec.get("shoeColor")) or CLOTH["white"]),
        "hat": ramp(CLOTH.get(spec.get("hatColor")) or CLOTH["teal"]),
        "bag": ramp(CLOTH.get(spec.get("bagColor")) or CLOTH["orange"]),
        "glasses": ramp(CLOTH.get(spec.get("glassesColor")) or CLOTH["black"]),
        "white": ramp(CLOTH["white"]),
    }


def _sleeve(cv, spec, c, x, y):
    top = spec.get("top") or "tee"
    put(cv, ARM, x, y, c["skin"])
    if top in LONG_SLEEVES:
        put(cv, SLEEVE_LONG, x, y, c["top"])
    elif top != "tank":
        put(cv, SLEEVE_SHORT, x, y, c["top"])


def _leg(cv, piece, x, y, n, spec, c):
    """다리 하나를 n 줄로 그린다 (살 위에 바지·반바지)."""
    bottom = spec.get("bottom") or "pants"
    for i in range(n):
        row = [(px, 0, t) for px, _y, t in piece[min(i, len(piece) - 1):][:1]]
        put(cv, row, x, y + i, c["skin"])
        if bottom == "pants" or (bottom == "shorts" and i == 0):
            put(cv, row, x, y + i, c["bottom"])


def _legs_front(cv, frame, spec, c, back, lift):
    """다리·바지·신발 (앞·뒤). lift = 몸이 올라간 칸 수 (걷는 칸에서 1).

    걷는 칸에서는 디딘 다리가 한 줄 길어져 발이 땅에 남고, 든 발은 두 칸 위에 뜬다.
    """
    step = {"a": 1, "stand": None, "b": 0}[frame]                   # 든 다리 (0 = 왼쪽, 1 = 오른쪽)
    if back and step is not None:
        step = 1 - step
    shoe = BOOT if spec.get("shoes") == "boots" else SHOE
    top = LY + 1 - lift
    for side in (0, 1):
        x = LX + side * 5
        n = 2 if step is None else (1 if side == step else 3)
        _leg(cv, LEG, x, top, n, spec, c)
        put(cv, shoe, x - 1 if side == 0 else x, top + n, c["shoe"])
    put(cv, HIP, LX, LY - lift, c["bottom"])
    if (spec.get("bottom") or "pants") == "skirt":
        put(cv, SKIRT, LX - 1, LY - lift, c["bottom"])


def _top_front(cv, frame, spec, c, back):
    """윗옷과 팔 (앞·뒤). 걷는 칸에서는 두 팔이 한 칸씩 엇갈린다."""
    top = spec.get("top") or "tee"
    t = c["top"]
    swing = {"a": (1, -1), "stand": (0, 0), "b": (-1, 1)}[frame]    # (왼팔, 오른팔)이 내려가는 칸 수
    if back:
        swing = (swing[1], swing[0])
    put(cv, TOP_F, TX, TY, t)
    _sleeve(cv, spec, c, TX, TY + 2 + swing[0])
    _sleeve(cv, spec, c, TX + 12, TY + 2 + swing[1])
    x0, y0 = TX + 4, TY + 1              # 몸통 안쪽(8칸 폭)의 왼쪽 위
    if top == "overalls":                # 멜빵바지: 가슴받이와 끈이 바지 색
        b = c["bottom"]
        for y in range(y0 + 2, y0 + 6):
            for x in range(x0 + 1, x0 + 7):
                dot(cv, x, y, b[2])
            dot(cv, x0 + 7, y, b[1])
        for x in (x0 + 1, x0 + 6):
            dot(cv, x, y0, b[2])
            dot(cv, x, y0 + 1, b[2])
        if not back:
            dot(cv, x0 + 2, y0 + 2, b[3])
            dot(cv, x0 + 5, y0 + 2, b[3])
        return
    if back:
        if top == "hoodie":              # 등으로 넘어간 모자
            for x in range(x0 + 1, x0 + 7):
                dot(cv, x, y0, t[1])
                dot(cv, x, y0 + 1, t[1])
            for x in range(x0 + 2, x0 + 6):
                dot(cv, x, y0 + 2, t[1])
        return
    if top == "jacket":                  # 앞을 연 겉옷: 가운데로 안에 입은 흰 옷이 보인다
        w = c["white"]
        for y in range(y0, y0 + 6):
            dot(cv, x0 + 3, y, w[2])
            dot(cv, x0 + 4, y, w[1])
            dot(cv, x0 + 2, y, t[0])
            dot(cv, x0 + 5, y, t[0])
        dot(cv, x0 + 1, y0, t[3])
        dot(cv, x0 + 6, y0, t[3])
    elif top == "hoodie":                # 목 둘레, 끈, 앞주머니
        for x in range(x0 + 2, x0 + 6):
            dot(cv, x, y0, t[1])
        dot(cv, x0 + 3, y0 + 1, t[3])
        dot(cv, x0 + 4, y0 + 1, t[3])
        for x in range(x0 + 1, x0 + 7):
            dot(cv, x, y0 + 4, t[1])
        dot(cv, x0 + 1, y0 + 3, t[1])
        dot(cv, x0 + 6, y0 + 3, t[1])
    elif top == "stripe":                # 가로 줄무늬
        for y in (y0 + 1, y0 + 3):
            for x in range(x0, x0 + 8):
                dot(cv, x, y, t[3] if x < x0 + 7 else t[2])
    elif top == "shirt":                 # 깃과 단추
        dot(cv, x0 + 2, y0, t[3])
        dot(cv, x0 + 5, y0, t[3])
        for y in range(y0, y0 + 6):
            dot(cv, x0 + 4, y, t[1])
        for y in (y0 + 1, y0 + 3):
            dot(cv, x0 + 3, y, t[0])
    elif top == "logo":                  # 가슴의 작은 무늬
        w = c["white"]
        for x, y in ((3, 1), (4, 1), (3, 2), (4, 2)):
            dot(cv, x0 + x, y0 + y, w[2])
        dot(cv, x0 + 4, y0 + 2, w[1])
    if top != "jacket":                  # 목선
        dot(cv, x0 + 3, y0 - 1, c["skin"][1])
        dot(cv, x0 + 4, y0 - 1, c["skin"][1])
        if top in ("tee", "long", "stripe", "logo", "tank"):
            dot(cv, x0 + 3, y0, c["skin"][2])
            dot(cv, x0 + 4, y0, c["skin"][2])


def _legs_side(cv, frame, spec, c, lift):
    """옆모습의 다리 (왼쪽을 본다). 걷는 칸에서는 두 다리가 앞뒤로 벌어진다."""
    shoe = BOOT_S if spec.get("shoes") == "boots" else SHOE_S
    top = LY + 1 - lift
    if frame == "stand":
        _leg(cv, LEGS_S, 13, top, 2, spec, c)
        put(cv, shoe, 12, top + 2, c["shoe"])
    else:
        # (다리의 x, 줄 수). 든 다리를 먼저 그려 디딘 다리 뒤로 가게 한다.
        legs = ((16, 1), (11, 3)) if frame == "a" else ((11, 1), (16, 3))
        for x, n in legs:
            _leg(cv, LEG_S, x, top, n, spec, c)
            put(cv, shoe, x - 2, top + n, c["shoe"])
    put(cv, HIP_S, 12, LY - lift, c["bottom"])
    if (spec.get("bottom") or "pants") == "skirt":
        put(cv, SKIRT_S, 11, LY - lift, c["bottom"])


def _top_side(cv, frame, spec, c):
    """옆모습의 윗옷과 팔. 팔은 다리와 반대로 흔들린다."""
    top = spec.get("top") or "tee"
    t = c["top"]
    put(cv, TOP_S, 11, TY, t)
    if top == "overalls":
        b = c["bottom"]
        for y in range(TY + 3, TY + 7):
            for x in range(12, 20):
                dot(cv, x, y, b[2] if x < 19 else b[1])
        dot(cv, 14, TY + 1, b[2])
        dot(cv, 14, TY + 2, b[2])
    elif top == "stripe":
        for y in (TY + 2, TY + 4):
            for x in range(12, 20):
                dot(cv, x, y, t[3])
    elif top == "hoodie":                # 목 뒤로 넘어간 모자
        put(cv, rows(0, (0, "111"), (0, "1321"), (0, "1221"), (1, "11")), 19, TY, t)
    ax = {"stand": 14, "a": 16, "b": 12}[frame]
    _sleeve(cv, spec, c, ax, TY + 2)


def _face_front(cv, c):
    skin = c["skin"]
    blush = _mix(skin[2][:3], (255, 120, 130), 0.34) + (255,)
    for ex in (HX + 4, HX + 12):
        dot(cv, ex, HY + 8, GLINT)
        dot(cv, ex + 1, HY + 8, EYE)
        dot(cv, ex, HY + 9, EYE)
        dot(cv, ex + 1, HY + 9, EYE)
    for bx in (HX + 2, HX + 3, HX + 14, HX + 15):
        dot(cv, bx, HY + 10, blush)
    dot(cv, HX + 8, HY + 11, skin[1])
    dot(cv, HX + 9, HY + 11, skin[1])


def _face_side(cv, c):
    skin = c["skin"]
    blush = _mix(skin[2][:3], (255, 120, 130), 0.34) + (255,)
    dot(cv, SX + 3, HY + 8, GLINT)
    dot(cv, SX + 4, HY + 8, EYE)
    dot(cv, SX + 3, HY + 9, EYE)
    dot(cv, SX + 4, HY + 9, EYE)
    dot(cv, SX + 5, HY + 10, blush)
    dot(cv, SX + 6, HY + 10, blush)
    dot(cv, SX + 2, HY + 11, skin[1])
    dot(cv, SX + 7, HY + 8, skin[1])      # 귀
    dot(cv, SX + 7, HY + 9, skin[1])


def _hair(cv, view, spec, c):
    style = HAIR.get(spec.get("hair") or "short", HAIR["short"])
    if style is None:
        return
    fringe, length, extra = style
    h = c["hair"]
    hat = HAT.get(spec.get("hat") or "")
    covered = bool(hat and hat["covers"])
    if view == "side":
        ox = SX
        put(cv, CAP_S, ox, HY, h)
        put(cv, BACK_S[length], ox, HY, h)
        put(cv, FRINGE_S[fringe], ox, HY, h)
        if extra == "spikes" and not covered:
            put(cv, SPIKES_S, ox, HY + 3, h)
        elif extra == "pony":
            put(cv, TAIL, ox + 15, HY + 3, h)
        elif extra == "twin":
            put(cv, TAIL, ox + 10, HY + 5, h)
        elif extra == "bun" and not covered:
            put(cv, BUN, ox + 8, HY + 2, h)
        return
    ox = HX
    put(cv, CAP_F, ox, HY, h)
    if view == "back":
        put(cv, BACK_F[length], ox, HY, h)
        if extra == "pony":
            put(cv, PONY_B, ox + 6, HY + 5, h)
    else:
        put(cv, FRINGE_F[fringe], ox, HY, h)
        put(cv, SIDES_F[length], ox, HY, h)
    if extra == "spikes" and not covered:
        put(cv, SPIKES_F, ox - 1, HY + 3, h)
    elif extra == "twin":
        put(cv, TWIN_L, ox - 5, HY + 3, h)
        put(cv, mirror(TWIN_L, 6), ox + 17, HY + 3, h)
    elif extra == "pony" and view == "front":
        put(cv, PONY_F, ox + 16, HY + 7, h)
    elif extra == "bun" and not covered:
        put(cv, BUN, ox + 5, HY + 2, h)


def _head(cv, view, spec, c):
    """머리·얼굴·머리카락·안경·모자. view = front / side / back."""
    if view == "side":
        put(cv, HEAD_S, SX, HY, c["skin"])
        _face_side(cv, c)
    else:
        put(cv, HEAD_F, HX, HY, c["skin"])
        if view == "front":
            _face_front(cv, c)
    _hair(cv, view, spec, c)
    g = GLASSES.get(spec.get("glasses") or "")
    if g and view != "back":
        gc = c["glasses"]
        frame_c = (gc[0], gc[1], gc[2], (214, 236, 255, 255))
        put(cv, g["side" if view == "side" else "front"], SX if view == "side" else HX, HY, frame_c)
    hat = HAT.get(spec.get("hat") or "")
    if hat:
        put(cv, hat[view], SX if view == "side" else HX, HY, c["hat"])


def _bag(cv, view, spec, c, behind):
    """가방. behind=True 는 몸보다 먼저(뒤에) 그릴 것."""
    kind = spec.get("bag") or ""
    b = c["bag"]
    if kind == "backpack":
        if view == "back" and not behind:
            put(cv, BACKPACK_BACK, 10, TY + 1, b)
        elif view == "side" and behind:
            put(cv, BACKPACK_SIDE, 20, TY + 1, b)
        elif view == "front" and not behind:            # 앞에서는 어깨끈만 보인다
            for y in range(TY + 1, TY + 6):
                dot(cv, 12, y, b[1])
                dot(cv, 19, y, b[1])
    elif kind == "satchel" and not behind:
        if view == "front":                             # 끈이 비스듬히 지나가고 허리 옆에 가방
            for i in range(6):
                dot(cv, 12 + i, TY + 1 + i, b[1])
                dot(cv, 13 + i, TY + 1 + i, b[0])
            put(cv, POUCH, 18, TY + 5, b)
        elif view == "back":
            for i in range(6):
                dot(cv, 19 - i, TY + 1 + i, b[1])
                dot(cv, 18 - i, TY + 1 + i, b[0])
            put(cv, POUCH, 10, TY + 5, b)
        else:
            for i in range(5):
                dot(cv, 13 + i, TY + 1 + i, b[1])
            put(cv, POUCH, 15, TY + 5, b)
    elif kind == "pouch" and not behind:                # 허리에 찬 가방
        if view == "side":
            for x in range(12, 20):
                dot(cv, x, TY + 6, b[1])
            put(cv, POUCH, 10, TY + 4, b)
        else:
            for x in range(12, 20):
                dot(cv, x, TY + 6, b[1])
            if view == "front":
                put(cv, POUCH, 14, TY + 4, b)


def _pack_over_hair(cv, view, spec, c):
    """배낭은 머리카락 위에 멘다. 머리를 그린 뒤에 한 번 더 얹는다.

    긴 머리는 등을 다 덮는다. 배낭을 머리보다 먼저만 그리면 옆·뒤에서 배낭이 통째로 가려져
    안 멘 것과 똑같아 보인다. 옆에서는 등 쪽으로 한 칸 빼서 얹는다 (몸통을 덮지 않게).
    """
    if (spec.get("bag") or "") != "backpack":
        return
    length = (HAIR.get(spec.get("hair") or "short") or (None, "short", None))[1]
    if length == "short":
        return                                          # 짧은 머리는 배낭까지 내려오지 않는다
    if view == "back":
        put(cv, BACKPACK_BACK, 10, TY + 1, c["bag"])
    elif view == "side":
        put(cv, BACKPACK_SIDE, 21, TY + 1, c["bag"])


def _over(cv, top, dy):
    """top 을 dy 만큼 옮겨 cv 위에 덮는다."""
    for y in range(CELL):
        yy = y + dy
        if not 0 <= yy < CELL:
            continue
        src, dst = top[y], cv[yy]
        for x in range(CELL):
            if src[x][3]:
                dst[x] = src[x]


def cell(spec, direction, frame):
    """한 칸(32x32)을 그린다.

    다리를 먼저 그리고, 윗몸(몸통·팔·가방·머리)은 따로 그려 그 위에 얹는다. 걷는 칸에서는 윗몸이
    한 칸 올라간다 - 디딘 다리는 그만큼 길어져 발이 땅에 남는다.
    """
    c = _colors(spec)
    lift = 0 if frame == "stand" else 1
    cv, up = blank(), blank()
    if direction in ("left", "right"):
        _legs_side(cv, frame, spec, c, lift)
        _bag(up, "side", spec, c, True)
        _top_side(up, frame, spec, c)
        _bag(up, "side", spec, c, False)
        _head(up, "side", spec, c)
        _pack_over_hair(up, "side", spec, c)
        _over(cv, up, -lift)
        return flip(cv) if direction == "right" else cv
    back = direction == "up"
    view = "back" if back else "front"
    _legs_front(cv, frame, spec, c, back, lift)
    _top_front(up, frame, spec, c, back)
    _bag(up, view, spec, c, False)
    _head(up, view, spec, c)
    _pack_over_hair(up, view, spec, c)
    _over(cv, up, -lift)
    return cv


def render(spec):
    return dict(((d, f), cell(spec, d, f)) for d in DIRS for f in FRAMES)


def walk_sheet(spec):
    """96x128: 줄 = 아래·왼쪽·오른쪽·위, 칸 = [왼발, 서 있음, 오른발]."""
    cells = render(spec)
    out = []
    for d in DIRS:
        for y in range(CELL):
            row = []
            for f in FRAMES:
                row.extend(cells[(d, f)][y])
            out.append(row)
    return out


def scale(img, k):
    """정수배로 키운다 (점이 번지지 않게)."""
    out = []
    for row in img:
        wide = []
        for px in row:
            wide.extend([px] * k)
        for _ in range(k):
            out.append(list(wide))
    return out


def png(img):
    """[(r, g, b, a) 줄] -> PNG bytes."""
    h, w = len(img), len(img[0])
    raw = bytearray()
    for row in img:
        raw.append(0)
        for px in row:
            raw.extend(px)

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))



def front(spec, k=3):
    """앞모습 한 장 (기본 96x96). 마이페이지의 닉네임 옆에 놓는다."""
    return scale(cell(spec, "down", "stand"), k)


def back(spec, k=3):
    """뒷모습 한 장 (기본 96x96)."""
    return scale(cell(spec, "up", "stand"), k)
