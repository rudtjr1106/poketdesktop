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
                   max_frames=64, key=None):
    ck = (path, key, target_height, min_scale, max_scale)
    if ck in _cache:
        return _cache[ck]

    frames, durs = read_frames(path, max_frames)
    if key is None:
        key = pick_key_color(frames)
    l, t, r, b = union_bbox(frames)
    bw, bh = r - l, b - t
    scale = float(target_height) / bh if bh else 1.0
    scale = max(min_scale, min(max_scale, scale))
    fw = max(8, int(round(bw * scale)))
    fh = max(8, int(round(bh * scale)))

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
ROW_OF = {DOWN: 0, RIGHT: 2, UP: 4, LEFT: 6}
DIRS = (DOWN, RIGHT, UP, LEFT)


class WalkAnimation(object):
    """4방향 걷기 애니메이션.

    frames[방향] 은 그 방향으로 걸을 때의 프레임 목록이다.
    좌우 반전이 아니라 방향마다 진짜 다른 그림이라, 위로 가면 등이 보인다.
    """

    def __init__(self, frames, durations, w, h, key):
        self.frames = frames
        self.durations = durations
        self.w = w
        self.h = h
        self.key = key

    def count(self):
        return len(self.durations)


def load_walk(sheet_path, meta, target_height=48, min_scale=0.25,
              max_scale=3.0, key=None):
    """스프라이트시트를 잘라 4방향 걷기 애니메이션으로 만든다.

    meta 는 서버가 준 {frameW, frameH, durations} 다. 종마다 칸 크기가
    제각각(24x32 ~ 104x120)이라 반드시 이 값을 보고 잘라야 한다.
    """
    ck = ("walk", sheet_path, key, target_height, min_scale, max_scale)
    if ck in _cache:
        return _cache[ck]

    fw = int(meta["frameW"])
    fh = int(meta["frameH"])
    durs_ticks = list(meta["durations"]) or [8]
    # 지속시간은 1/60초 단위 틱이다. 밀리초로 바꾼다.
    durs = [max(30, int(round(t * 1000.0 / 60.0))) for t in durs_ticks]
    n = len(durs_ticks)

    sheet = Image.open(sheet_path).convert("RGBA")

    # 먼저 쓸 칸을 전부 꺼내서 공통 여백을 잰다.
    # 방향마다 따로 자르면 방향을 바꿀 때 몸이 튄다.
    cut = {}
    every = []
    for d in DIRS:
        row = ROW_OF[d]
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
    scale = float(target_height) / bh if bh else 1.0
    scale = max(min_scale, min(max_scale, scale))
    ow = max(8, int(round(bw * scale)))
    oh = max(8, int(round(bh * scale)))

    frames = {}
    for d in DIRS:
        out = []
        for c in cut[d]:
            im = premultiply(c.crop((l, t, r, b)))
            im = _resize(im, (ow, oh))
            out.append(flatten_rgba(im, key))
        frames[d] = out

    anim = WalkAnimation(frames, durs, ow, oh, key)
    _cache[ck] = anim
    return anim


def dir_from(vx, vy):
    """움직이는 방향에서 네 방향 중 하나를 고른다.

    가로와 세로 중 더 크게 움직이는 쪽을 따른다. 대각선으로 걸을 때
    방향이 딸깍딸깍 바뀌지 않도록 가로를 조금 우대한다.
    """
    if abs(vx) * 1.15 >= abs(vy):
        return RIGHT if vx >= 0 else LEFT
    return DOWN if vy >= 0 else UP
