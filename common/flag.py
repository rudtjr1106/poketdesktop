# -*- coding: utf-8 -*-
"""길드 깃발 (2.5.0, 시즌 6) - 길드마다 하나, 24 x 24 도트. 서버 · 앱이 같이 쓴다.

2026-11-14 사용자: "길드 상점에 길드 깃발 - 아이콘인데 사람들이 자유롭게 도트로 만들 수 있는 거야, 픽셀로 그림
그릴 수 있게." 결정: 길드마다 하나(마스터 · 부마스터가 그린다) · 길드 이름 옆 + (산 사람의) 랭킹 · 친구 목록 이름 옆 ·
24 x 24 · 코인 상점 '길드 전용' 500코인, 한 번 사면 계속.

그림은 글자 SIZE*SIZE 개 (위 줄부터, 왼쪽부터). 한 글자가 한 칸:
    '.'          투명
    '0'~'9' 'a'~'v'  PALETTE 의 0~31 번 빛깔
빛깔은 고정 32색 (DawnBringer 32 - 도트 그림에 널리 쓰는 공개 팔레트). 고른 빛깔만 쓰니 그림이 서로 어울리고,
문자열이 짧고(576자) 검사하기 쉽다.
"""
SIZE = 24
EMPTY = "."
DIGITS = "0123456789abcdefghijklmnopqrstuv"          # 32 글자 - 빛깔 번호
PALETTE = (
    "#000000", "#222034", "#45283c", "#663931", "#8f563b", "#df7126", "#d9a066", "#eec39a",
    "#fbf236", "#99e550", "#6abe30", "#37946e", "#4b692f", "#524b24", "#323c39", "#3f3f74",
    "#306082", "#5b6ee1", "#639bff", "#5fcde4", "#cbdbfc", "#ffffff", "#9badb7", "#847e87",
    "#696a6a", "#595652", "#76428a", "#ac3232", "#d95763", "#d77bba", "#8f974a", "#8a6f30",
)
BLANK = EMPTY * (SIZE * SIZE)


def valid(pixels):
    """깃발 문자열이 맞는 꼴인가 (길이 · 글자)."""
    if not isinstance(pixels, str) or len(pixels) != SIZE * SIZE:
        return False
    ok = set(DIGITS) | {EMPTY}
    return all(ch in ok for ch in pixels)


def is_blank(pixels):
    return not pixels or set(pixels) <= {EMPTY}


def color_at(pixels, x, y):
    """그 칸의 빛깔 '#rrggbb' (투명이면 None)."""
    ch = pixels[y * SIZE + x]
    return None if ch == EMPTY else PALETTE[DIGITS.index(ch)]


def rows(pixels):
    """[[빛깔 또는 None, ...] x SIZE] - 그리기용."""
    return [[color_at(pixels, x, y) for x in range(SIZE)] for y in range(SIZE)]


def put(pixels, x, y, index):
    """한 칸을 칠한 새 문자열 (index None = 지우기)."""
    i = y * SIZE + x
    ch = EMPTY if index is None else DIGITS[index]
    return pixels[:i] + ch + pixels[i + 1:]


def fill(pixels, x, y, index):
    """(x, y) 와 이어진 같은 빛깔 칸을 모두 칠한 새 문자열 (채우기 통, 위아래 · 양옆으로만 잇는다)."""
    cells = list(pixels)
    want = EMPTY if index is None else DIGITS[index]
    old = cells[y * SIZE + x]
    if old == want:
        return pixels
    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if not (0 <= cx < SIZE and 0 <= cy < SIZE) or cells[cy * SIZE + cx] != old:
            continue
        cells[cy * SIZE + cx] = want
        stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
    return "".join(cells)
