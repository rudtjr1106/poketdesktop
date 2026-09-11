# -*- coding: utf-8 -*-
"""포켓몬 그림을 화면에 쓸 수 있는 형태로 만든다.

그림은 **정식 도트**만 쓴다. 팬게임(포켓몬 Z)의 도트는 타입이 바뀐 종을
색까지 고쳐놨기 때문에(예: 피카츄가 전기/독이라 보라색) 쓰지 않는다.

원본은 애니메이션 GIF 한 장이다. 여기서 하는 일은 세 가지.

1. 프레임 분해
   GIF 를 프레임별로 뜯어서 그대로 애니메이션에 쓴다.

2. 크기 통일
   종마다 그림 크기가 제각각이라(38x55 ~ 104x102) 그대로 두면 어떤 포켓몬만
   유난히 커 보인다. 실제로 그려진 높이를 재서 목표 높이에 맞춘다.

3. 배경 투명
   윈도우 창은 '이 색을 투명으로' 방식만 되므로, 그림에 안 쓰인 색을 골라
   배경으로 칠한다. 줄일 때 가장자리가 반투명해지면 그 색이 테두리에
   번지므로 알파를 미리 곱해서 줄이고 다시 나눠 복원한다.
"""
import os

from PIL import Image, ImageSequence

RIGHT, LEFT = 0, 1

_cache = {}
_key_cache = {}


# ---------------------------------------------------------------- 투명색
def used_colors(frames, limit=4000):
    used = set()
    for im in frames:
        raw = im.convert("RGBA").tobytes()
        for i in range(0, len(raw), 4):
            if raw[i + 3]:
                used.add(raw[i:i + 3])
                if len(used) > limit:
                    return used
    return used


CANDIDATE_KEYS = [(255, 0, 255), (0, 255, 0), (255, 0, 128), (0, 254, 1),
                  (13, 255, 137), (254, 1, 254), (123, 0, 231), (1, 254, 254)]


def pick_key_color(frames):
    """그림에 한 번도 안 쓰인 색을 투명색으로 고른다."""
    used = used_colors(frames)
    for c in CANDIDATE_KEYS:
        if bytes(c) not in used:
            return c
    return (255, 0, 255)


# ---------------------------------------------------------------- 변환
def premultiply(im):
    """RGB 에 알파를 곱해둔다. 이래야 줄일 때 투명한 검정이 안 번진다."""
    from PIL import ImageChops
    r, g, b, a = im.split()
    return Image.merge("RGBA", (ImageChops.multiply(r, a),
                                ImageChops.multiply(g, a),
                                ImageChops.multiply(b, a), a))


def flatten_rgba(im, key, alpha_cut=128):
    """알파를 곱해둔 그림을 되돌리면서 투명한 곳을 투명색으로 칠한다."""
    src = im.tobytes()
    out = bytearray(len(src) // 4 * 3)
    kr, kg, kb = key
    j = 0
    for i in range(0, len(src), 4):
        a = src[i + 3]
        if a >= alpha_cut:
            out[j] = min(255, src[i] * 255 // a)
            out[j + 1] = min(255, src[i + 1] * 255 // a)
            out[j + 2] = min(255, src[i + 2] * 255 // a)
        else:
            out[j], out[j + 1], out[j + 2] = kr, kg, kb
        j += 3
    return Image.frombytes("RGB", im.size, bytes(out))


def _resize(im, size):
    """확대는 도트가 살아야 하니 NEAREST, 축소는 형태가 살아야 하니 LANCZOS."""
    if size == im.size:
        return im
    if size[0] >= im.size[0]:
        return im.resize(size, Image.NEAREST)
    return im.resize(size, Image.LANCZOS)


def read_frames(path, max_frames=64):
    """GIF/PNG 를 RGBA 프레임 목록과 프레임별 지속시간(ms)으로 읽는다."""
    im = Image.open(path)
    frames, durs = [], []
    try:
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
            durs.append(max(40, int(fr.info.get("duration", 90) or 90)))
            if len(frames) >= max_frames:
                break
    except Exception:
        pass
    if not frames:
        frames = [Image.open(path).convert("RGBA")]
        durs = [120]
    return frames, durs


def union_bbox(frames):
    l = t = 10 ** 6
    r = b = 0
    for f in frames:
        bb = f.getbbox()
        if bb:
            l, t = min(l, bb[0]), min(t, bb[1])
            r, b = max(r, bb[2]), max(b, bb[3])
    if r <= l or b <= t:
        f = frames[0]
        return 0, 0, f.width, f.height
    return l, t, r, b


class Animation(object):
    """한 포켓몬의 애니메이션. 오른쪽/왼쪽 두 벌을 들고 있다.

    투명색(key)은 그림마다 다르다. 팬텀처럼 보라색이 많은 종은 자홍색을
    투명색으로 쓰면 몸에 구멍이 뚫리기 때문에, 파일별로 안 쓰인 색을 고른다.
    """

    def __init__(self, right, left, durations, w, h, scale, key):
        self.frames = {RIGHT: right, LEFT: left}
        self.durations = durations
        self.w = w
        self.h = h
        self.scale = scale
        self.key = key

    def count(self):
        return len(self.durations)


def load_animation(path, target_height=48, min_scale=0.25, max_scale=2.5,
                   max_frames=64, key=None, max_size=None):
    """max_size=(폭, 높이) 를 주면 그 칸을 넘지 않게 더 줄인다.

    목록의 작은 칸에 넣는 도트가 그렇다. 높이만 맞추면 옆으로 긴 종
    (#564 는 22px 높이에 72px)이 칸 밖으로 나가 잘린다. **min_scale 보다
    칸이 이긴다** - 잘려서 안 보이는 것보다 작게라도 다 보이는 편이 낫다.
    줄이는 것은 아래의 알파를 곱해 줄이는 길 안에서 한 번에 한다. 다 만든
    그림을 한 번 더 줄이면 가장자리에 검은 테가 번진다.
    """
    ms = tuple(max_size) if max_size else None
    # max_frames 도 열쇠에 넣는다. 안 넣으면 첫 장만 읽어 둔 것이 모든
    # 프레임을 원하는 쪽에 그대로 건너간다.
    ck = (path, key, target_height, min_scale, max_scale, max_frames, ms)
    if ck in _cache:
        return _cache[ck]

    frames, durs = read_frames(path, max_frames)
    if key is None:
        key = pick_key_color(frames)
    l, t, r, b = union_bbox(frames)
    bw, bh = r - l, b - t
    scale = float(target_height) / bh if bh else 1.0
    scale = max(min_scale, min(max_scale, scale))
    if ms:
        if bw:
            scale = min(scale, float(ms[0]) / bw)
        if bh:
            scale = min(scale, float(ms[1]) / bh)
    fw = max(8, int(round(bw * scale)))
    fh = max(8, int(round(bh * scale)))
    if ms:
        fw = max(1, min(fw, int(ms[0])))
        fh = max(1, min(fh, int(ms[1])))

    right, left = [], []
    for f in frames:
        c = premultiply(f.crop((l, t, r, b)))
        c = _resize(c, (fw, fh))
        flat = flatten_rgba(c, key)
        right.append(flat)
        left.append(flat.transpose(Image.FLIP_LEFT_RIGHT))

    anim = Animation(right, left, durs, fw, fh, scale, key)
    _cache[ck] = anim
    return anim


def to_rgba(img, key):
    """투명색으로 칠해둔 도트를 알파 있는 그림으로 되돌린다.

    이걸 ImageTk.PhotoImage 로 만들어 Label 에 올리면 위젯 배경색 위에
    알아서 합성된다. 카드가 선택돼 배경색이 바뀌어도 도트는 그대로 쓴다.
    """
    px = img.tobytes()
    mb = bytearray(img.width * img.height)
    kr, kg, kb = key
    for i in range(0, len(px), 3):
        if px[i] != kr or px[i + 1] != kg or px[i + 2] != kb:
            mb[i // 3] = 255
    out = img.convert("RGBA")
    out.putalpha(Image.frombytes("L", img.size, bytes(mb)))
    return out


def probe_key_color(paths):
    """대표 몇 장만 훑어 투명색을 정한다. 결과는 기억해둔다."""
    ck = tuple(sorted(paths))
    if ck in _key_cache:
        return _key_cache[ck]
    sample = []
    for p in paths:
        if p and os.path.exists(p):
            fr, _d = read_frames(p, 8)
            sample.extend(fr)
    key = pick_key_color(sample) if sample else (255, 0, 255)
    _key_cache[ck] = key
    return key


def clear_cache():
    _cache.clear()


# ---------------------------------------------------------------- 걷는 도트
# 배틀 도트는 정면 고정이라 걷는 모습이 없다. 걸어다니게 하려면 4방향에
# 걷기 프레임이 있는 오버월드 도트가 필요하다.
#
# 스프라이트시트는 **가로가 프레임, 세로가 8방향**이고 방향은 아래에서
# 반시계로 돈다.
#     0 아래   1 아래오른쪽  2 오른쪽  3 위오른쪽
#     4 위(등) 5 위왼쪽      6 왼쪽    7 아래왼쪽
# 우리는 네 방향만 쓴다 (아래/오른쪽/위/왼쪽).
DOWN, UP = 2, 3          # RIGHT=0, LEFT=1 은 위에 이미 있다
DOWNRIGHT, UPRIGHT, UPLEFT, DOWNLEFT = 4, 5, 6, 7
ROW_OF = {DOWN: 0, DOWNRIGHT: 1, RIGHT: 2, UPRIGHT: 3,
          UP: 4, UPLEFT: 5, LEFT: 6, DOWNLEFT: 7}
DIRS = (DOWN, DOWNRIGHT, RIGHT, UPRIGHT, UP, UPLEFT, LEFT, DOWNLEFT)
# 서버 meta 의 rowmap 키와 우리 상수를 잇는다.
DIR_KEY = {DOWN: "down", DOWNRIGHT: "downright", RIGHT: "right",
           UPRIGHT: "upright", UP: "up", UPLEFT: "upleft",
           LEFT: "left", DOWNLEFT: "downleft"}
# 대각선이 없는 출처(followers, 4행)에서 대신 쓸 방향.
DIAG_FALLBACK = {DOWNRIGHT: RIGHT, UPRIGHT: RIGHT,
                 UPLEFT: LEFT, DOWNLEFT: LEFT}


class WalkAnimation(object):
    """방향이 있는 오버월드 애니메이션. 걷기 말고도 쓴다.

    frames[방향] 은 그 방향일 때의 프레임 목록이다. 좌우 반전이 아니라
    방향마다 진짜 다른 그림이라, 위로 가면 등이 보인다.

    ## anchor 가 왜 필요한가

    동작마다 **칸 크기가 다르다.** 피카츄는 걷기가 32x40 인데 공격은
    80x80 이다(기술 이펙트까지 한 칸에 들어 있다). 그림에 딱 맞춰
    잘라내고 창을 그 크기로 만들면, 동작을 바꿀 때마다 몸이 순간이동한다.

    그래서 **칸의 한가운데**가 잘라낸 그림 안 어디였는지를 같이 들고
    다닌다(ax, ay). 부르는 쪽은 그 점을 화면의 같은 자리에 두면 되고,
    그러면 창 크기가 변해도 포켓몬은 제자리에 선다.

    scale 도 같이 들고 다닌다. 한 종의 모든 동작은 **같은 배율**을 써야
    한다 - 동작마다 목표 높이에 맞추면 공격할 때만 작아진다.
    """

    def __init__(self, frames, durations, w, h, key, ax=None, ay=None,
                 scale=1.0, name="Walk"):
        self.frames = frames
        self.durations = durations
        self.w = w
        self.h = h
        self.key = key
        self.ax = w / 2.0 if ax is None else ax
        self.ay = h / 2.0 if ay is None else ay
        self.scale = scale
        self.name = name

    def count(self):
        return len(self.durations)


def load_walk(sheet_path, meta, target_height=48, min_scale=0.25,
              max_scale=3.0, key=None, scale=None, name=None):
    """스프라이트시트를 잘라 방향별 애니메이션으로 만든다.

    meta 는 서버가 준 {frameW, frameH, durations, rows, rowmap} 이다.
    종마다, 그리고 **동작마다** 칸 크기가 제각각이라 반드시 이 값을 보고
    잘라야 한다.

    scale 을 주면 그 배율을 쓴다. 한 종의 걷기에서 정한 배율을 나머지
    동작에 물려주기 위한 것이다 - 동작마다 목표 높이에 맞추면 공격할
    때만 몸이 작아진다.
    """
    name = name or meta.get("anim") or "Walk"
    ck = ("anim", sheet_path, name, key, target_height, min_scale, max_scale,
          scale)
    if ck in _cache:
        return _cache[ck]

    fw = int(meta["frameW"])
    fh = int(meta["frameH"])
    # 방향이 시트의 몇 번째 행인지는 출처마다 다르다. 서버가 알려준다.
    rowmap = meta.get("rowmap") or {}
    nrows = max(1, int(meta.get("rows") or 8))
    durs_ticks = list(meta["durations"]) or [8]
    # 지속시간은 1/60초 단위 틱이다. 밀리초로 바꾼다.
    durs = [max(30, int(round(t * 1000.0 / 60.0))) for t in durs_ticks]
    n = len(durs_ticks)

    sheet = Image.open(sheet_path).convert("RGBA")
    # 시트가 메타보다 짧을 수 있다. 밖을 자르면 빈 칸이 나온다.
    have_rows = max(1, min(nrows, sheet.height // fh if fh else nrows))
    have_cols = max(1, min(n, sheet.width // fw if fw else n))
    if have_cols < n:
        durs = durs[:have_cols]
        n = have_cols

    # 어느 방향이 어느 행인가. **행이 모자라면 0행 하나로 때운다** -
    # Sleep 은 방향이 아예 없어서 1행짜리다. 그때 8행인 줄 알고 자르면
    # 시트 밖을 긁어서 빈 그림이 나온다.
    rows = {}
    for d in DIRS:
        # **rowmap 에 그 방향이 없으면 ROW_OF 로 때우면 안 된다.**
        # followers 시트는 4행인데 배치가 아예 달라서(1이 왼쪽),
        # 8행 기준의 ROW_OF[DOWNRIGHT]=1 을 쓰면 아래오른쪽 자리에
        # 왼쪽 그림이 들어간다. 없으면 그 대각선의 이웃 가로 방향을 쓴다.
        # **`if alt` 로 쓰면 안 된다. RIGHT 가 0 이라 거짓이 된다.**
        # 실제로 걸렸다 - 오른쪽 대각선만 0행(아래)으로 떨어져서,
        # 오른쪽 위로 걸을 때 정면을 보고 있었다. 왼쪽은 LEFT=1 이라
        # 멀쩡해서 더 눈에 안 띄었다.
        r = rowmap.get(DIR_KEY[d])
        if r is None:
            alt = DIAG_FALLBACK.get(d)
            r = rowmap.get(DIR_KEY[alt]) if alt is not None else None
        if r is None:
            r = ROW_OF[d] if not rowmap else 0
        if r >= have_rows:
            # 행이 모자란다. Sleep 은 방향이 없어 1행뿐이다.
            alt = DIAG_FALLBACK.get(d)
            r2 = rowmap.get(DIR_KEY[alt]) if alt is not None else None
            r = r2 if (r2 is not None and r2 < have_rows) else 0
        rows[d] = r

    # 먼저 쓸 칸을 전부 꺼내서 공통 여백을 잰다.
    # 방향마다 따로 자르면 방향을 바꿀 때 몸이 튄다.
    cut = {}
    every = []
    for d in DIRS:
        row = rows[d]
        cells = []
        for i in range(n):
            box = (i * fw, row * fh, (i + 1) * fw, (row + 1) * fh)
            cells.append(sheet.crop(box))
        cut[d] = cells
        every.extend(cells)

    if key is None:
        key = pick_key_color(every)
    l, t, r, b = union_bbox(every)
    bw, bh = max(1, r - l), max(1, b - t)
    if scale is None:
        scale = float(target_height) / bh if bh else 1.0
        scale = max(min_scale, min(max_scale, scale))
    ow = max(8, int(round(bw * scale)))
    oh = max(8, int(round(bh * scale)))
    # 칸 한가운데가 잘라낸 그림 안 어디인지. 동작을 바꿔도 이 점을 같은
    # 자리에 두면 몸이 안 튄다 (WalkAnimation 의 설명을 보라).
    ax = (fw / 2.0 - l) * scale
    ay = (fh / 2.0 - t) * scale

    frames = {}
    for d in DIRS:
        out = []
        for c in cut[d]:
            im = premultiply(c.crop((l, t, r, b)))
            im = _resize(im, (ow, oh))
            out.append(flatten_rgba(im, key))
        frames[d] = out

    anim = WalkAnimation(frames, durs, ow, oh, key, ax, ay, scale, name)
    _cache[ck] = anim
    return anim


# 8방향을 각도로 나눈다. 시트에 대각선 그림이 진짜로 들어 있어서
# (행 1/3/5/7) 쓰지 않을 이유가 없다 - 비스듬히 걸을 때 몸도 비스듬해진다.
#
# 칸을 45도로 똑같이 자르지 않고 **가로 방향을 넓게** 준다. 활동 영역이
# 가로로 길어서 실제 걸음이 대부분 가로에 몰리는데, 45도로 자르면
# 조금만 기울어도 대각선 그림으로 넘어가 부산스럽다.
_DIR_BANDS = (
    (-22.5, 22.5, RIGHT),
    (22.5, 67.5, DOWNRIGHT),
    (67.5, 112.5, DOWN),
    (112.5, 157.5, DOWNLEFT),
    (157.5, 180.0, LEFT),
    (-180.0, -157.5, LEFT),
    (-157.5, -112.5, UPLEFT),
    (-112.5, -67.5, UP),
    (-67.5, -22.5, UPRIGHT),
)


def dir_from(vx, vy):
    """움직이는 방향에서 여덟 방향 중 하나를 고른다.

    화면 좌표라 y 는 아래가 양수다. 그래서 각도가 양수면 아래쪽이다.
    """
    import math
    if vx == 0 and vy == 0:
        return DOWN
    deg = math.degrees(math.atan2(vy, vx))
    for lo, hi, d in _DIR_BANDS:
        if lo <= deg < hi:
            return d
    # atan2 는 정확히 180.0 을 돌려줄 수 있다(정왼쪽). 위 칸은 끝을
    # 안 포함하므로 여기로 떨어진다. 실제로 걸렸다 - 왼쪽으로 걷는데
    # 오른쪽을 보고 있었다.
    return LEFT


def dir_four(vx, vy):
    """네 방향만 쓰는 곳(대각선 그림이 없는 종)을 위한 것."""
    if abs(vx) * 1.15 >= abs(vy):
        return RIGHT if vx >= 0 else LEFT
    return DOWN if vy >= 0 else UP
