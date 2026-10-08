# -*- coding: utf-8 -*-
"""직접 그린 캐릭터 도트의 규격 검사 (common/avatar_sheet.py). 창도 서버도 없이 돈다.

    python common/test_avatar_sheet.py

못 박는 것:

  1. 규격: 96 x 128, 줄 = 아래·왼쪽·오른쪽·위, 칸 = 왼발·서 있음·오른발. 꾸미기 캐릭터의 걷기 시트가
     곧 견본이다 - 그것은 언제나 규격에 맞는다.
  2. PNG 를 스스로 읽는다 (서버에는 Pillow 가 없다): 도트 프로그램이 내놓는 꼴 - RGBA, RGB, 팔레트
     (투명색 포함), 필터 다섯 가지 - 을 다 읽고, Pillow 가 읽은 것과 한 점도 다르지 않다.
  3. 안 맞는 것은 **무엇이 안 맞는지** 말해 준다: 크기, 빈 칸, 색이 너무 많음, PNG 가 아님.
  4. 반투명은 반을 기준으로 가르고 그렇게 했다고 알린다.
  5. 서버에 두는 글(pack)은 다시 읽으면 같은 그림이다. 깨진 글은 None (화면이 죽지 않는다).
"""
import base64
import io
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import avatar_art as A                               # noqa: E402
from common import avatar_sheet as S                             # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def why(fn, *a):
    try:
        fn(*a)
    except S.SheetError as e:
        return str(e)
    return None


def main():
    rng = random.Random(5)
    spec = dict(A.DEFAULT, hair="pony", hat="bucket", glasses="round", top="hoodie", bag="satchel")
    sheet = A.walk_sheet(spec)
    data = A.png(sheet)

    print("=== 규격 ===")
    chk("96 x 128", (S.W, S.H) == (96, 128))
    got, notes = S.read(data)
    chk("꾸미기 캐릭터의 걷기 시트는 규격에 맞는다 (그것이 견본이다)", got == sheet and notes == [], notes)
    bad = []
    for _ in range(40):
        try:
            S.read(A.png(A.walk_sheet(A.random_spec(rng))))
        except S.SheetError as e:
            bad.append(str(e))
    chk("  무엇을 골라도 맞는다 (무작위 40벌)", not bad, bad[:2])
    chk("칸을 잘라 낸다: 첫 줄 가운데 = 앞을 보고 서 있는 칸", S.cell_of(sheet, "down", "stand") == A.cell(spec, "down", "stand")
        and S.cell_of(sheet, "up", "b") == A.cell(spec, "up", "b") and S.cell_of(sheet, "right", "a") == A.cell(spec, "right", "a"))
    chk("마이페이지에 놓는 앞모습은 그 칸의 세 배 (96x96)", S.front(sheet) == A.front(spec) and len(S.front(sheet)) == 96)

    print("\n=== PNG 읽기 ===")
    chk("우리가 쓴 PNG 를 그대로 읽는다", S.unpng(data) == sheet)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is None:
        print("  (Pillow 가 없어 다른 프로그램이 쓴 PNG 는 건너뜁니다)")
    else:
        im = Image.new("RGBA", (S.W, S.H))
        im.putdata([px for row in sheet for px in row])
        for name, make in (
                ("RGBA", lambda b: im.save(b, "PNG")),
                ("RGBA, 줄마다 필터를 고른 것", lambda b: im.save(b, "PNG", optimize=True, compress_level=9)),
                ("RGB (투명 없음)", lambda b: im.convert("RGB").save(b, "PNG")),
                ("팔레트 + 투명색", lambda b: im.quantize(64, method=Image.Quantize.FASTOCTREE).save(b, "PNG", optimize=True)),
                ("회색", lambda b: im.convert("L").save(b, "PNG")),
                ("회색 + 알파", lambda b: im.convert("LA").save(b, "PNG"))):
            buf = io.BytesIO()
            make(buf)
            want = Image.open(io.BytesIO(buf.getvalue())).convert("RGBA").tobytes()
            try:
                mine = bytes(v for row in S.unpng(buf.getvalue()) for px in row for v in px)
            except S.SheetError as e:
                mine = str(e)
            chk("  %s: Pillow 가 읽은 것과 한 점도 다르지 않다" % name, mine == want, mine if isinstance(mine, str) else None)
        # 색이 적은 팔레트 (1·2·4비트로 저장된다)
        for colors in (2, 4, 16):
            small = Image.new("RGBA", (S.W, S.H), (0, 0, 0, 0))
            px = small.load()
            for y in range(S.H):
                for x in range(S.W):
                    if (x // 3 + y // 5) % 3:
                        v = (x * 7 + y * 3) % (colors - 1)
                        px[x, y] = (40 * v % 256, 255 - 30 * v % 256, 90, 255)
            buf = io.BytesIO()
            small.quantize(colors, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", bits={2: 1, 4: 2, 16: 4}[colors])
            want = Image.open(io.BytesIO(buf.getvalue())).convert("RGBA").tobytes()
            mine = bytes(v for row in S.unpng(buf.getvalue()) for p in row for v in p)
            chk("  팔레트 %d색 (%d비트): 같다" % (colors, {2: 1, 4: 2, 16: 4}[colors]), mine == want)
    chk("PNG 가 아니면 그렇게 말한다", why(S.read, b"GIF89a....") == "PNG 파일이 아닙니다."
        and why(S.read, b"") == "PNG 파일이 아닙니다.")
    chk("깨진 PNG", "깨져" in (why(S.read, data[:60]) or "") and "깨져" in (why(S.read, data[:8] + b"\x00" * 30) or ""),
        why(S.read, data[:60]))

    print("\n=== 안 맞는 것 ===")
    small = A.png([row[:64] for row in sheet[:64]])
    msg = why(S.read, small)
    chk("크기가 다르면 지금 크기와 바라는 크기를 말한다", msg is not None and "96 x 128" in msg and "64 x 64" in msg, msg)
    big3 = A.png(A.scale(sheet, 3))
    chk("세 배로 키워 보낸 것도 안 받는다 (원래 크기로 보내야 한다)", "288 x 384" in (why(S.read, big3) or ""), why(S.read, big3))
    hole = [list(row) for row in sheet]
    for y in range(32, 64):
        for x in range(64, 96):
            hole[y][x] = (0, 0, 0, 0)
    msg = why(S.read, A.png(hole))
    chk("빈 칸이 있으면 어느 칸인지 말한다", msg is not None and "왼쪽·오른발" in msg and "열두 칸" in msg, msg)
    noisy = [[(rng.randrange(256), rng.randrange(256), rng.randrange(256), 255) if px[3] else px for px in row]
             for row in sheet]
    msg = why(S.read, A.png(noisy))
    chk("색이 너무 많으면 (사진을 줄인 것) 안 받는다", msg is not None and "색이 너무 많습니다" in msg and "64" in msg, msg)
    chk("색 상한은 꾸미기 캐릭터보다 넉넉하다", len(set(px for row in sheet for px in row if px[3])) < S.SHEET_COLORS // 2)
    chk("너무 큰 파일", "너무 큽니다" in (why(S.read, data + b"\x00" * S.SHEET_BYTES) or ""))

    print("\n=== 다듬기 ===")
    soft = [list(row) for row in sheet]
    n = 0
    for y in range(S.H):
        for x in range(S.W):
            if soft[y][x][3] and n < 30:
                soft[y][x] = soft[y][x][:3] + (200 if n % 2 else 60,)
                n += 1
    got, notes = S.read(A.png(soft))
    chk("반투명한 점은 반을 기준으로 칠하거나 비운다", all(px[3] in (0, 255) for row in got for px in row)
        and sum(1 for row in got for px in row if px[3]) == sum(1 for row in sheet for px in row if px[3]) - 15)
    chk("  그렇게 했다고 알린다", len(notes) == 1 and "반투명한 점 30개" in notes[0], notes)
    chk("  비운 점에는 색이 남지 않는다", all(px == (0, 0, 0, 0) for row in got for px in row if not px[3]))
    same = [list(sheet[y % 32]) for y in range(S.H)]                 # 네 줄이 다 앞모습
    got, notes = S.read(A.png(same))
    chk("앞모습과 뒷모습이 같으면 받되 확인하라고 알린다", any("뒷모습" in x for x in notes), notes)
    still = [row[32:64] * 3 for row in sheet]                         # 걷는 칸 셋이 다 서 있는 칸
    got, notes = S.read(A.png(still))
    chk("걷는 칸이 다 같으면 받되 알린다", any("걷는 칸" in x for x in notes), notes)

    print("\n=== 서버에 두는 글 ===")
    text = S.pack(sheet)
    chk("글자로만 된 글이고 작다 (몇 KB)", isinstance(text, str) and len(text) < 8000 and base64.b64decode(text)[:4] == b"\x89PNG",
        len(text))
    chk("다시 읽으면 같은 그림", S.unpack(text) == sheet)
    chk("같은 그림은 같은 글", S.pack(S.unpack(text)) == text)
    chk("깨진 글·빈 글·엉뚱한 값은 None (죽지 않는다)", S.unpack("깨진 글") is None and S.unpack("") is None
        and S.unpack(None) is None and S.unpack(text[:200]) is None and S.unpack(S.pack(sheet)[::-1]) is None)
    chk("규격에 안 맞는 그림이 든 글도 None", S.unpack(base64.b64encode(small).decode()) is None)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
