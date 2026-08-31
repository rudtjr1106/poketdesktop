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
