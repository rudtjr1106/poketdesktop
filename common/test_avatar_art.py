# -*- coding: utf-8 -*-
"""캐릭터 도트 검사 (common/avatar_art.py). 창도 서버도 없이 돈다.

    python common/test_avatar_art.py

못 박는 것:

  1. 규격: 한 칸 32x32, 시트 96x128 (줄 = 아래·왼쪽·오른쪽·위, 칸 = 왼발·서 있음·오른발).
  2. 고를 수 있는 것은 전부 그려지고, 고르면 그림이 실제로 달라진다.
  3. 무엇을 골라도 칸 밖으로 잘려 나가지 않고, 발은 늘 같은 땅에 닿는다.
  4. 오른쪽은 왼쪽을 뒤집은 것이다. 같은 것을 고르면 같은 그림이 나온다.
  5. 보내온 것(spec)은 믿지 않는다: 모르는 열쇠·값은 기본값이 된다.
"""
import os
import random
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import avatar_art as A                               # noqa: E402

OK = FAIL = 0
GROUND = 30                  # 발바닥이 닿는 줄


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def box(cv):
    """그려진 점들의 (왼쪽, 위, 오른쪽, 아래). 아무것도 없으면 None."""
    xs = [x for row in cv for x, px in enumerate(row) if px[3]]
    ys = [y for y, row in enumerate(cv) if any(px[3] for px in row)]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def every_cell(spec):
    return [(d, f, A.cell(spec, d, f)) for d in A.DIRS for f in A.FRAMES]


def main():
    print("=== 규격 ===")
    sheet = A.walk_sheet(A.DEFAULT)
    chk("시트는 96x128", len(sheet) == 128 and all(len(r) == 96 for r in sheet), (len(sheet), len(sheet[0])))
    chk("한 칸은 32x32", all(len(cv) == 32 and all(len(r) == 32 for r in cv) for _d, _f, cv in every_cell(A.DEFAULT)))
    chk("줄은 아래·왼쪽·오른쪽·위, 칸은 왼발·서 있음·오른발", A.DIRS == ("down", "left", "right", "up")
        and A.FRAMES == ("a", "stand", "b"))
    down_stand = A.cell(A.DEFAULT, "down", "stand")
    chk("시트의 첫 줄 가운데 칸이 '아래를 보고 서 있는' 칸이다",
        [row[32:64] for row in sheet[:32]] == down_stand)
    chk("앞모습·뒷모습은 96x96", len(A.front(A.DEFAULT)) == 96 and len(A.front(A.DEFAULT)[0]) == 96
        and len(A.back(A.DEFAULT)) == 96)
    chk("점은 다 불투명하거나 다 투명하다 (반투명 없음)",
        all(px[3] in (0, 255) for row in sheet for px in row))

    print("\n=== 고를 수 있는 것 ===")
    keys = [p[0] for p in A.PARTS]
    chk("부위 일곱: 머리·모자·안경·윗옷·바지·신발·가방", keys == ["hair", "hat", "glasses", "top", "bottom", "shoes", "bag"], keys)
    n = dict((p[0], len(p[2])) for p in A.PARTS)
    chk("종류가 넉넉하다 (머리 13, 모자 6+없음, 안경 4+없음, 윗옷 9, 가방 3+없음)",
        n["hair"] == 13 and n["hat"] == 7 and n["glasses"] == 5 and n["top"] == 9 and n["bag"] == 4, n)
    chk("색: 피부 6, 머리 13, 옷 16", (len(A.SKIN), len(A.HAIR_COLORS), len(A.CLOTH)) == (6, 13, 16))
    chk("기본값은 그대로 통과한다", A.clean(A.DEFAULT) == A.DEFAULT)
    base = dict((k, c) for k, c in ((d + f, cv) for d, f, cv in every_cell(A.DEFAULT)))
    same, broken, clipped, floating = [], [], [], []
    for key, _name, options, color in A.PARTS:
        for value, _label in options:
            spec = dict(A.DEFAULT)
            spec[key] = value
            try:
                cells = every_cell(spec)
            except Exception as e:                              # noqa: BLE001
                broken.append((key, value, repr(e)))
                continue
            if value != A.DEFAULT[key] and all(base[d + f] == cv for d, f, cv in cells):
                same.append((key, value))
            for d, f, cv in cells:
                b = box(cv)
                if b[0] <= 0 or b[1] <= 0 or b[2] >= 31:
                    clipped.append((key, value, d, f, b))
                if b[3] != GROUND:
                    floating.append((key, value, d, f, b[3]))
    chk("전부 그려진다 (터지는 것 없음)", not broken, broken[:3])
    chk("고르면 그림이 달라진다", not same, same)
    chk("칸 밖으로 잘려 나가는 것이 없다 (가장자리 한 칸은 늘 비어 있다)", not clipped, clipped[:3])
    chk("발은 늘 같은 줄(%d)에 닿는다 - 걷는 칸에서 몸이 떠도 디딘 발은 땅에 있다" % GROUND, not floating, floating[:3])
    stale = []
    for key, table in A.PALETTES.items():
        owner = dict((p[3], p[0]) for p in A.PARTS).get(key)
        for name in table:
            spec = dict(A.DEFAULT)
            if owner and not spec[owner]:                        # 색을 보려면 그 부위가 있어야 한다
                spec[owner] = [o[0] for o in dict((p[0], p[2]) for p in A.PARTS)[owner] if o[0]][0]
            ref = dict(spec)
            ref[key] = [x for x in table if x != name][0]
            spec[key] = name
            if A.walk_sheet(spec) == A.walk_sheet(ref):
                stale.append((key, name))
    chk("색을 바꾸면 그림이 달라진다", not stale, stale[:4])

    print("\n=== 방향과 걷기 ===")
    busy = dict(A.DEFAULT, hair="pony", hat="ribbon", glasses="round", bag="satchel", top="hoodie")
    chk("오른쪽은 왼쪽을 뒤집은 것", all(A.cell(busy, "right", f) == A.flip(A.cell(busy, "left", f)) for f in A.FRAMES))
    chk("네 방향이 서로 다르다", len(set(repr(A.cell(busy, d, "stand")) for d in ("down", "left", "up"))) == 3)
    chk("걷는 두 칸은 서 있는 칸과 다르고, 서로도 다르다", all(
        len(set(repr(A.cell(busy, d, f)) for f in A.FRAMES)) == 3 for d in A.DIRS))
    tops = [box(A.cell(busy, "down", f))[1] for f in A.FRAMES]
    chk("걷는 칸에서는 몸이 한 칸 올라간다", tops[0] == tops[2] == tops[1] - 1, tops)
    chk("같은 것을 고르면 같은 그림", A.walk_sheet(busy) == A.walk_sheet(dict(busy)))
    chk("뒤에서는 얼굴도 안경도 안 보인다", A.cell(dict(A.DEFAULT, glasses="shades"), "up", "stand")
        == A.cell(A.DEFAULT, "up", "stand"))

    hairs = [o[0] for o in dict((p[0], p[2]) for p in A.PARTS)["hair"]]
    fronts = [repr(A.cell(dict(A.DEFAULT, hair=h), "down", "stand")) for h in hairs]
    chk("머리 13가지는 **앞에서 봐도** 서로 다르다 (포니테일은 꼬리 끝이 옆으로 나온다)",
        len(set(fronts)) == len(hairs), len(set(fronts)))
    hidden = []
    for h in hairs:
        for d in ("left", "up"):
            spec = dict(A.DEFAULT, hair=h)
            if A.cell(dict(spec, bag="backpack"), d, "stand") == A.cell(spec, d, "stand"):
                hidden.append((h, d))
    chk("배낭은 어떤 머리여도 옆·뒤에서 보인다 (긴 머리가 등을 덮어도 그 위에 멘다)", not hidden, hidden)

    print("\n=== 보내온 것은 믿지 않는다 ===")
    c = A.clean({"hair": "없는머리", "top": "hoodie", "skin": "dark", "zzz": 1, "hairColor": 3, "bag": None})
    chk("모르는 값은 기본값, 아는 값은 그대로", c["hair"] == A.DEFAULT["hair"] and c["top"] == "hoodie"
        and c["skin"] == "dark" and c["hairColor"] == A.DEFAULT["hairColor"] and c["bag"] == "", c)
    chk("모르는 열쇠는 버린다", set(c) == set(A.DEFAULT), sorted(set(c) ^ set(A.DEFAULT)))
    chk("이상한 것이 와도 기본 캐릭터", A.clean(None) == A.DEFAULT and A.clean("x") == A.DEFAULT
        and A.clean([1, 2]) == A.DEFAULT)
    rng = random.Random(7)
    picks = [A.random_spec(rng) for _ in range(60)]
    chk("무작위는 늘 그릴 수 있는 것을 낸다", all(A.clean(p) == p for p in picks))
    chk("  그리고 골고루 나온다", len(set(p["hair"] for p in picks)) >= 8 and len(set(p["top"] for p in picks)) >= 6
        and any(p["hat"] for p in picks) and any(not p["hat"] for p in picks))
    try:
        for p in picks:
            A.walk_sheet(p)
        ok = True
    except Exception as e:                                      # noqa: BLE001
        ok = repr(e)
    chk("  전부 그려진다", ok is True, ok)

    print("\n=== PNG ===")
    data = A.png(A.walk_sheet(busy))
    w, h, depth, kind = struct.unpack(">IIBB", data[16:26])
    chk("PNG 머리: 96x128, 8비트 RGBA", data[:8] == b"\x89PNG\r\n\x1a\n" and (w, h, depth, kind) == (96, 128, 8, 6),
        (w, h, depth, kind))
    pos, raw = 8, b""
    while pos < len(data):
        size, tag = struct.unpack(">I4s", data[pos:pos + 8])
        if tag == b"IDAT":
            raw += data[pos + 8:pos + 8 + size]
        pos += 12 + size
    px = zlib.decompress(raw)
    chk("풀면 줄마다 (1 + 96x4) 바이트, 128줄", len(px) == 128 * (1 + 96 * 4), len(px))
    chk("크기가 작다 (1.5KB 안팎)", len(data) < 3000, len(data))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
