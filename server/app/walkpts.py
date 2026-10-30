# -*- coding: utf-8 -*-
"""걷는 도트의 위치 점 (꾸미기, 버전 2) - SpriteCollab 의 `<동작>-Offsets.png` 를 읽어 meta 에 싣는다.

Offsets 그림은 동작 시트(`<동작>-Anim.png`)와 칸 크기 · 차례가 같고, 칸마다 점이 넷 있다 (PMDCollab/SpriteBot 의
SpriteUtils.getOffsetFromRGB 와 같은 뜻):

    검정 (0,0,0)    머리 - 실제로 찍어 보면 입 · 턱 자리다. 없는 칸도 있다 (그럴 때 SpriteBot 은 몸 가운데를 쓴다)
    초록 (0,255,0)  몸 가운데 - 늘 있다
    빨강 · 파랑     양손 - 꾸미기는 안 쓴다

meta 에 싣는 꼴 (행 = 방향, 칸 = 프레임, 칸 안 좌표):

    "head":   [[[x, y] 또는 null, ...프레임], ...행]
    "center": 같은 꼴

앱(client/poketdesktop/deco_place.py)은 이 점으로 장식 자리를 잡는다. 점이 없는 출처(followers · ow)는 앱이 그림
윗부분으로 대신한다. **서버에는 Pillow 가 없다** - pngmini 로 읽는다.
"""
from . import pngmini

HEAD = (0, 0, 0)
CENTER = (0, 255, 0)


def points(data, fw, fh, rows=None, frames=None):
    """Offsets PNG -> {"head": [...], "center": [...]}. 칸 크기가 맞지 않으면 ValueError."""
    if fw <= 0 or fh <= 0:
        raise ValueError("칸 크기가 없다")
    w, h, lines = pngmini.read_rgba(data, limit=2048)       # 실제 Offsets 는 수백 px - 큰 그림은 읽지 않는다
    nrows = h // fh
    ncols = w // fw
    if not nrows or not ncols:
        raise ValueError("칸보다 작은 그림")
    if rows:
        nrows = min(nrows, int(rows))
    if frames:
        ncols = min(ncols, int(frames))
    head = [[None] * ncols for _ in range(nrows)]
    center = [[None] * ncols for _ in range(nrows)]
    for y in range(nrows * fh):
        line = lines[y]
        alpha = line[3::4]
        for x in range(ncols * fw):
            if not alpha[x]:
                continue
            i = x * 4
            rgb = (line[i], line[i + 1], line[i + 2])
            if rgb == HEAD:
                head[y // fh][x // fw] = [x % fw, y % fh]
            elif rgb == CENTER:
                center[y // fh][x // fw] = [x % fw, y % fh]
    return {"head": head, "center": center}
