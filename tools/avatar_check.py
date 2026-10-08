# -*- coding: utf-8 -*-
"""받은 캐릭터 도트(PNG)가 규격에 맞는지 **넣기 전에** 내 PC 에서 본다.

    python tools/avatar_check.py 받은파일.png

- 규격(common/avatar_sheet.py, 안내서 docs/avatar/)에 맞는지 말해 준다. 안 맞으면 무엇이 안 맞는지.
- 옆에 '받은파일.preview.png' 를 만든다: 크게 키운 열두 칸과, 마이페이지에 보일 앞모습.
  넣기 전에 눈으로 한 번 보라는 것이다 (규격에 맞아도 넣으면 안 되는 그림이 있다).

서버에 넣는 일은 deploy/avatar_set.sh 가 한다. Pillow 는 필요 없다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import avatar_art as A                           # noqa: E402
from common import avatar_sheet as S                         # noqa: E402

BG = (22, 27, 40, 255)
LINE = (58, 68, 94, 255)


def preview(sheet, k=4):
    """열두 칸을 k 배로 (칸 사이에 금), 오른쪽에 마이페이지의 앞모습(세 배)."""
    cw = A.CELL * k
    w, h = cw * 3 + 4 + 16 + 96 + 16, cw * 4 + 5
    img = [[BG] * w for _ in range(h)]
    big = A.scale(sheet, k)
    for r in range(4):
        for c in range(3):
            ox, oy = 1 + c * (cw + 1), 1 + r * (cw + 1)
            for y in range(cw):
                for x in range(cw):
                    px = big[r * cw + y][c * cw + x]
                    if px[3]:
                        img[oy + y][ox + x] = px
    for i in range(4):                                       # 칸 사이의 금
        x = i * (cw + 1)
        for y in range(h):
            img[y][min(x, cw * 3 + 3)] = LINE
    for i in range(5):
        y = i * (cw + 1)
        for x in range(cw * 3 + 4):
            img[min(y, h - 1)][x] = LINE
    face = S.front(sheet)
    ox, oy = cw * 3 + 4 + 16, 16
    for y in range(96):
        for x in range(96):
            if face[y][x][3]:
                img[oy + y][ox + x] = face[y][x]
    return img


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print((__doc__ or "").strip())
        return 2
    path = argv[0]
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        print("파일을 읽지 못했습니다: %s" % e)
        return 2
    try:
        sheet, notes = S.read(data)
    except S.SheetError as e:
        print("규격에 맞지 않습니다: %s" % e)
        return 1
    print("규격에 맞습니다. (%d x %d, 색 %d가지)" % (S.W, S.H, len(set(px for row in sheet for px in row if px[3]))))
    for n in notes:
        print("  참고: %s" % n)
    out = os.path.splitext(path)[0] + ".preview.png"
    with open(out, "wb") as f:
        f.write(A.png(preview(sheet)))
    print("미리보기: %s  (넣기 전에 한 번 열어 보세요)" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
