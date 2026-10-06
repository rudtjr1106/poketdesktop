# -*- coding: utf-8 -*-
"""작은 PNG 읽고 쓰기 — 걷는 도트의 세 번째 출처를 우리 규격으로 바꾼다 (1.9.0).

**서버에는 Pillow 가 없다** (requirements.txt). 그림 몇 장을 바꾸자고 의존성과
메모리를 늘릴 이유가 없어서, 필요한 만큼만 표준 라이브러리(zlib, struct)로 쓴다.

세 번째 출처(pokeemerald-expansion 의 overworld.png)는 이렇게 생겼다:

    가로 한 줄에 칸 여섯 개 (칸은 정사각 - 32x32 나 64x64)
        [아래1][아래2][위1][위2][왼쪽1][왼쪽2]
    색은 팔레트 16색, **0번 색이 바탕**(투명으로 쓸 자리)
    이로치는 그림이 따로 없고 팔레트 파일(overworld_shiny.pal)만 다르다

화면(클라이언트)은 '가로 = 프레임, 세로 = 방향' 인 시트를 받는다. 그래서
여기서 **네 줄 x 두 칸**(아래·왼쪽·오른쪽·위 - followers 와 같은 차례)으로
다시 짜 준다. 오른쪽은 왼쪽을 좌우로 뒤집은 것이다. 바탕색은 투명으로,
이로치는 팔레트를 갈아 끼워서 낸다. 화면은 달라질 것이 없다.

여기서 읽는 PNG 는 **팔레트 그림(색 종류 3), 인터레이스 없음**뿐이다. 다른
꼴이면 ValueError - 부르는 쪽이 '이 종에는 없다' 로 다룬다.

(1.10.1) 이로치 시트를 만들려고 SpriteCollab 의 시트·얼굴 그림도 읽는다
(read_rgba). 그쪽은 RGBA 8비트(색 종류 6)다. 팔레트·RGB 그림도 받는다.
"""
import struct
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
# 시트의 방향 차례 (main.ROWMAP_FOLLOW 와 같다)
ROWS = ("down", "left", "right", "up")


def _chunks(data):
    if data[:8] != SIG:
        raise ValueError("PNG 가 아니다")
    pos = 8
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        yield kind, data[pos + 8:pos + 8 + n]
        pos += 12 + n


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _header(data, limit):
    """IHDR·PLTE·tRNS 와 이어 붙인 IDAT 를 읽는다."""
    w = h = depth = ctype = None
    palette, trns, raw = [], b"", []
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            w, h, depth, ctype, _comp, _filt, lace = struct.unpack(">IIBBBBB", body)
            if lace != 0:
                raise ValueError("인터레이스 그림은 못 읽는다")
        elif kind == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body) - 2, 3)]
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            raw.append(body)
        elif kind == b"IEND":
            break
    if not w or not h or not raw:
        raise ValueError("그림이 비었다")
    if w > limit or h > limit:
        raise ValueError("그림이 너무 크다")
    return w, h, depth, ctype, palette, trns, zlib.decompress(b"".join(raw))


def _unfilter(flat, h, stride, bpp):
    """줄마다 붙은 필터를 푼다. bpp 는 한 화소의 바이트 수 (1 바이트 이하면 1).

    필터 1·3·4 의 '왼쪽' 은 한 화소 앞이다. 팔레트 그림은 1바이트 앞, RGBA 는
    4바이트 앞.
    """
    if len(flat) < (stride + 1) * h:
        raise ValueError("그림이 잘렸다")
    rows, prev = [], bytearray(stride)
    pos = 0
    for _y in range(h):
        f = flat[pos]
        line = bytearray(flat[pos + 1:pos + 1 + stride])
        pos += stride + 1
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                if i >= bpp:
                    line[i] = (line[i] + _paeth(line[i - bpp], prev[i], prev[i - bpp])) & 255
                else:
                    line[i] = (line[i] + prev[i]) & 255     # 왼쪽이 0 이면 paeth 는 위
        elif f != 0:
            raise ValueError("모르는 필터 %d" % f)
        rows.append(line)
        prev = line
    return rows


def read_indexed(data, limit=1024):
    """팔레트 PNG 를 읽는다. (가로, 세로, 줄마다 색 번호 목록, [(r,g,b)...]) 를 준다."""
    w, h, depth, ctype, palette, _trns, flat = _header(data, limit)
    if ctype != 3 or depth not in (1, 2, 4, 8):
        raise ValueError("팔레트 그림이 아니다 (종류 %d, 깊이 %d)" % (ctype, depth))
    if not palette:
        raise ValueError("그림이 비었다")
    stride = (w * depth + 7) // 8
    rows = []
    for line in _unfilter(flat, h, stride, 1):
        if depth == 8:
            rows.append(list(line[:w]))
        else:
            mask, per = (1 << depth) - 1, 8 // depth
            out = []
            for b in line:
                for k in range(per):
                    out.append((b >> (8 - depth * (k + 1))) & mask)
            rows.append(out[:w])
    return w, h, rows, palette


def read_rgba(data, limit=4096):
    """PNG 를 RGBA 로 읽는다 (1.10.1). (가로, 세로, 줄마다 bytearray(가로*4)) 를 준다.

    SpriteCollab 의 동작 시트는 1024 를 넘는 것이 있다 (코라이돈 Hop 이 640x1152).
    그래서 한도를 따로 받는다. 받는 꼴: RGBA·RGB 8비트, 팔레트 (tRNS 투명 포함).
    """
    w, h, depth, ctype, palette, trns, flat = _header(data, limit)
    if ctype == 6 and depth == 8:
        return w, h, _unfilter(flat, h, w * 4, 4)
    if ctype == 2 and depth == 8:
        clear = trns[1::2] if len(trns) == 6 else None      # 투명으로 칠 한 색
        rows = []
        for line in _unfilter(flat, h, w * 3, 3):
            out = bytearray(w * 4)
            for x in range(w):
                rgb = line[x * 3:x * 3 + 3]
                out[x * 4:x * 4 + 3] = rgb
                out[x * 4 + 3] = 0 if rgb == clear else 255
            rows.append(out)
        return w, h, rows
    if ctype == 3:
        _w, _h, idx_rows, pal = read_indexed(data, limit)
        rgba = [bytes(c) + bytes((trns[i] if i < len(trns) else 255,)) for i, c in enumerate(pal)]
        clear = b"\x00\x00\x00\x00"
        return w, h, [bytearray(b"".join(rgba[c] if c < len(rgba) else clear for c in r))
                      for r in idx_rows]
    raise ValueError("못 읽는 꼴 (종류 %d, 깊이 %d)" % (ctype, depth))


def write_rgba(w, h, pixels):
    """RGBA 화소(줄마다 bytes, 길이 w*4)를 PNG 로 쓴다."""
    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff))
    raw = b"".join(b"\x00" + bytes(line) for line in pixels)
    return (SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def parse_pal(text):
    """JASC 팔레트 파일(overworld_shiny.pal)을 [(r,g,b)...] 로.

        JASC-PAL
        0100
        16
        115 197 164
        ...
    """
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n") if ln.strip()]
    if len(lines) < 4 or not lines[0].upper().startswith("JASC"):
        raise ValueError("팔레트 파일이 아니다")
    out = []
    for ln in lines[3:]:
        bits = ln.split()
        if len(bits) < 3:
            continue
        out.append(tuple(max(0, min(255, int(x))) for x in bits[:3]))
    if not out:
        raise ValueError("팔레트가 비었다")
    return out


def frames_of(w, h):
    """한 줄짜리 그림에서 방향마다 쓸 칸 번호. 모르는 꼴이면 None.

    칸은 정사각이라 칸 수 = 가로 / 세로.
      6칸: [아래1 아래2 위1 위2 왼1 왼2]
      9칸: [아래·위·왼쪽의 선 자세] 뒤에 걷는 두 칸씩 (옛 배치)
    """
    if not h or w % h:
        return None
    n = w // h
    if n == 6:
        return {"down": (0, 1), "up": (2, 3), "left": (4, 5)}
    if n == 9:
        return {"down": (3, 4), "up": (5, 6), "left": (7, 8)}
    return None


def overworld_sheet(data, palette=None):
    """한 줄짜리 overworld.png 를 우리 시트(네 줄 x 두 칸, RGBA)로 바꾼다.

    (PNG 바이트, 칸 한 변) 을 준다. palette 를 주면 그 색으로 칠한다 (이로치).
    0번 색은 투명이 된다.
    """
    w, h, rows, pal = read_indexed(data)
    cells = frames_of(w, h)
    if cells is None:
        raise ValueError("모르는 배치 (%dx%d)" % (w, h))
    if palette:
        pal = list(palette) + list(pal[len(palette):])
    rgba = [bytes((r, g, b, 255)) for r, g, b in pal]
    clear = b"\x00\x00\x00\x00"

    def cell(i, flip=False):
        """i 번째 칸을 RGBA 줄들로."""
        out = []
        for y in range(h):
            idx = rows[y][i * h:(i + 1) * h]
            if flip:
                idx = idx[::-1]
            out.append(b"".join(clear if (c == 0 or c >= len(rgba)) else rgba[c] for c in idx))
        return out

    sheet = []
    for d in ROWS:
        a, b = cells["left" if d == "right" else d]
        left, right = cell(a, d == "right"), cell(b, d == "right")
        for y in range(h):
            sheet.append(left[y] + right[y])
    return write_rgba(h * 2, h * 4, sheet), h
