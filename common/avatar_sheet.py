# -*- coding: utf-8 -*-
"""직접 그린 캐릭터 도트 (1.10.3) — 한 장짜리 걷기 시트의 규격과, 그 규격을 지켰는지 보는 일.

꾸미기 창(avatar_art)으로 만드는 캐릭터 말고, **자기가 직접 그린 도트**를 쓰고 싶은 사람이 있다.
그런 사람은 아래 규격대로 그린 PNG 한 장을 운영자에게 보내고, 운영자가 넣어 준다
(server/app/avatar_tool.py). 화면이 그림을 올리는 길은 없다 - 남에게 보일 그림을 아무나 올리게
두지 않는다.

## 규격 (docs/avatar/ 의 안내서와 같아야 한다)

    PNG 한 장, 96 x 128, 배경은 투명.
    32 x 32 칸이 가로 3, 세로 4 = 열두 칸.

        줄(위에서부터)   아래를 봄(앞모습) · 왼쪽 · 오른쪽 · 위를 봄(뒷모습)
        칸(왼쪽부터)     왼발을 내딛음 · 서 있음 · 오른발을 내딛음

    - 반투명은 없다. 점은 다 칠해졌거나 다 비었거나 (받을 때 반을 기준으로 가른다).
    - 색은 SHEET_COLORS 가지까지 (사진을 줄여 넣는 것이 아니라 도트다).
    - 열두 칸이 다 그려져 있어야 한다 (칸마다 SHEET_MIN_PX 점 이상).

꾸미기 캐릭터의 걷기 시트(avatar_art.walk_sheet)가 바로 이 꼴이다 - 그래서 그것이 곧 견본이다.
마이페이지의 닉네임 옆에는 **첫 줄 가운데 칸**(앞을 보고 서 있는 모습)을 세 배로 키워 놓는다.

## PNG 를 직접 읽는다

서버에는 Pillow 가 없다. 그래서 PNG 를 읽는 일도 여기서 한다 (unpng) - 8비트 RGBA·RGB,
팔레트(1~8비트), 인터레이스 없는 것. 도트 프로그램이 내놓는 PNG 는 다 여기에 든다.
"""
import base64
import struct
import zlib

from . import avatar_art as A

W, H = A.CELL * len(A.FRAMES), A.CELL * len(A.DIRS)          # 96 x 128
SHEET_COLORS = 64            # 색 가짓수 상한
SHEET_MIN_PX = 24            # 한 칸에 칠해진 점이 이보다 적으면 '빈 칸' 으로 본다
SHEET_BYTES = 40 * 1024      # 받는 파일의 크기 상한
DIR_KR = {"down": "아래(앞모습)", "left": "왼쪽", "right": "오른쪽", "up": "위(뒷모습)"}
FRAME_KR = {"a": "왼발", "stand": "서 있음", "b": "오른발"}
CLEAR = (0, 0, 0, 0)


class SheetError(ValueError):
    """규격에 안 맞는다. 글은 그린 사람에게 그대로 보여 줄 수 있는 말이다."""


# ---------------------------------------------------------------- PNG 읽기
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def unpng(data):
    """PNG bytes -> [(r, g, b, a) 줄]. 못 읽는 꼴이면 SheetError."""
    if not isinstance(data, (bytes, bytearray)) or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SheetError("PNG 파일이 아닙니다.")
    pos, chunks = 8, []
    while pos + 8 <= len(data):
        size, tag = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.append((tag, data[pos + 8:pos + 8 + size]))
        pos += 12 + size
        if tag == b"IEND":
            break
    head = next((body for tag, body in chunks if tag == b"IHDR"), None)
    if head is None or len(head) < 13:
        raise SheetError("PNG 파일이 깨져 있습니다.")
    w, h, depth, kind, _comp, _filt, lace = struct.unpack(">IIBBBBB", head[:13])
    if lace:
        raise SheetError("인터레이스로 저장한 PNG 는 읽지 못합니다. 그 옵션을 끄고 다시 저장해 주세요.")
    if w > 4096 or h > 4096:
        raise SheetError("그림이 너무 큽니다.")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(kind)
    if channels is None or (kind != 3 and depth != 8) or (kind == 3 and depth not in (1, 2, 4, 8)):
        raise SheetError("이 PNG 형식은 읽지 못합니다. 8비트 RGBA 로 저장해 주세요.")
    plte = next((body for tag, body in chunks if tag == b"PLTE"), b"")
    trns = next((body for tag, body in chunks if tag == b"tRNS"), b"")
    try:
        raw = zlib.decompress(b"".join(body for tag, body in chunks if tag == b"IDAT"))
    except zlib.error:
        raise SheetError("PNG 파일이 깨져 있습니다.")
    bpp = max(1, channels * depth // 8)                       # 한 점의 바이트 수 (필터가 이만큼 앞을 본다)
    stride = (w * channels * depth + 7) // 8
    if len(raw) < (stride + 1) * h:
        raise SheetError("PNG 파일이 깨져 있습니다.")
    out, prev = [], bytearray(stride)
    for y in range(h):
        base = y * (stride + 1)
        ft, line = raw[base], bytearray(raw[base + 1:base + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                line[i] = (line[i] + _paeth(a, b, c)) & 255
            elif ft != 0:
                raise SheetError("PNG 파일이 깨져 있습니다.")
        prev = line
        row = []
        if kind == 6:
            for x in range(w):
                row.append(tuple(line[x * 4:x * 4 + 4]))
        elif kind == 2:
            for x in range(w):
                row.append(tuple(line[x * 3:x * 3 + 3]) + (255,))
        elif kind == 4:
            for x in range(w):
                g = line[x * 2]
                row.append((g, g, g, line[x * 2 + 1]))
        elif kind == 0:
            for x in range(w):
                row.append((line[x], line[x], line[x], 255))
        else:                                                 # 팔레트
            mask = (1 << depth) - 1
            for x in range(w):
                bit = x * depth
                i = (line[bit >> 3] >> (8 - depth - (bit & 7))) & mask
                if i * 3 + 2 >= len(plte):
                    raise SheetError("PNG 파일이 깨져 있습니다.")
                row.append((plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2], trns[i] if i < len(trns) else 255))
        out.append(row)
    return out


# ---------------------------------------------------------------- 규격
def cell_of(sheet, direction, frame):
    """시트에서 한 칸(32x32)을 잘라 낸다."""
    r, c = A.DIRS.index(direction), A.FRAMES.index(frame)
    return [row[c * A.CELL:(c + 1) * A.CELL] for row in sheet[r * A.CELL:(r + 1) * A.CELL]]


def check(img):
    """읽은 그림이 규격에 맞는지 보고 다듬는다. (시트, 알릴 것 목록) 을 돌려준다. 안 맞으면 SheetError.

    다듬는 것: 반투명한 점은 반을 기준으로 칠하거나 비운다 (그리는 프로그램이 가장자리를 흐리게
    저장했을 때). 비운 점의 색은 지운다 - 같은 그림은 같은 바이트가 되게.
    """
    h = len(img)
    w = len(img[0]) if h else 0
    if (w, h) != (W, H):
        raise SheetError("그림 크기는 %d x %d 이어야 합니다 (지금 %d x %d). 한 칸 32 x 32 가 가로 3, 세로 4 입니다."
                         % (W, H, w, h))
    notes, soft, out = [], 0, []
    for row in img:
        line = []
        for r, g, b, a in row:
            if 0 < a < 255:
                soft += 1
            line.append((r, g, b, 255) if a >= 128 else CLEAR)
        out.append(line)
    if soft:
        notes.append("반투명한 점 %d개를 칠하거나 비웠습니다 (도트에는 반투명이 없습니다)." % soft)
    colors = set(px for row in out for px in row if px[3])
    if len(colors) > SHEET_COLORS:
        raise SheetError("색이 너무 많습니다 (%d가지). %d가지까지 쓸 수 있습니다. 사진이나 흐리게 줄인 그림이 "
                         "아니라 점을 찍어 그린 도트여야 합니다." % (len(colors), SHEET_COLORS))
    empty = []
    for d in A.DIRS:
        for f in A.FRAMES:
            n = sum(1 for row in cell_of(out, d, f) for px in row if px[3])
            if n < SHEET_MIN_PX:
                empty.append("%s·%s" % (DIR_KR[d], FRAME_KR[f]))
    if empty:
        raise SheetError("비어 있는 칸이 있습니다: %s. 열두 칸을 다 그려 주세요." % ", ".join(empty))
    if cell_of(out, "down", "stand") == cell_of(out, "up", "stand"):
        notes.append("앞모습과 뒷모습이 똑같습니다. 뒷모습(넷째 줄)을 따로 그렸는지 확인해 주세요.")
    if all(cell_of(out, d, "a") == cell_of(out, d, "stand") == cell_of(out, d, "b") for d in A.DIRS):
        notes.append("걷는 칸 셋이 다 똑같습니다. 걸어도 발이 안 움직입니다.")
    return out, notes


def read(data):
    """PNG bytes -> (시트, 알릴 것 목록). 규격에 안 맞으면 SheetError."""
    if len(data or b"") > SHEET_BYTES:
        raise SheetError("파일이 너무 큽니다 (%dKB). 도트 한 장은 몇 KB 면 됩니다." % (len(data) // 1024))
    return check(unpng(data))


def pack(sheet):
    """시트 -> 서버에 두고 화면에 내려보내는 글 (우리 방식으로 다시 쓴 PNG 의 base64)."""
    return base64.b64encode(A.png(sheet)).decode("ascii")


def unpack(text):
    """pack 이 만든 글 -> 시트. 깨졌거나 규격에 안 맞으면 None (화면은 꾸민 캐릭터로 넘어간다)."""
    try:
        return check(unpng(base64.b64decode(text or "")))[0]
    except Exception:                                       # noqa: BLE001
        return None


def front(sheet, k=3):
    """앞을 보고 서 있는 칸을 k 배로 (기본 96x96). 마이페이지의 닉네임 옆에 놓는다."""
    return A.scale(cell_of(sheet, "down", "stand"), k)
