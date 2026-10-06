# -*- coding: utf-8 -*-
"""이로치 시트가 없는 종의 이로치 동작 도트 (1.10.1). 네트워크 없이 돈다.

    python server/test_shiny_recolor.py

코라이돈은 이로치사탕을 먹여도 바탕화면에서 빨간 몸으로 걸었다. SpriteCollab 에
보통 시트만 있고 이로치 시트(0000/0001)가 없어서다. 같은 저장소의 얼굴 그림에는
이로치가 있으니, 거기서 색 표를 뽑아 보통 시트에 입힌다. 못 박는 것:

  1. pngmini.read_rgba — RGBA(필터 다섯 가지 전부)·RGB·팔레트(tRNS) 를 읽는다.
  2. 얼굴 두 장으로 색 표를 만든다. 색만 바꾼 그림이 아니면 만들지 않는다.
  3. 표를 시트에 입힌다: 바뀐 색은 이로치 색으로(명암은 남긴다), 안 바뀐 색과
     투명한 자리는 그대로. 시트가 더 진해도 색조가 같은 얼굴 색을 짝으로 고른다.
  4. 이로치 시트가 없으면 만들어서 이로치로 준다. 이로치 쪽에 그 동작만 빠진 종
     (레시라무의 앉기)·메가 폼도. 얼굴 그림이 404 면 없다고, 끊기면 다음에 다시.
  5. 예전에 '이로치 없음' 으로 적어 둔 것은 걷기가 아닌 동작도 한 번 더 찾아본다.
"""
import json
import os
import struct
import sys
import tempfile
import urllib.error
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-recolor-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ["POKET_WALK_DIR"] = os.path.join(TMP, "walk")
os.environ["POKET_SPRITE_DIR"] = os.path.join(TMP, "sprites")
os.environ["POKET_WARM_SPRITES"] = "0"
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import main as M                                    # noqa: E402
from app import pngmini as PM                                # noqa: E402
from app import recolor as RC                                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


class Net(object):
    """urllib.request.urlopen 대신. 주소 조각 -> 바이트 / 오류. 없는 주소는 404."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, url, timeout=None):
        url = getattr(url, "full_url", url)
        self.calls.append(url)
        for part, got in self.table:
            if part in url:
                if isinstance(got, Exception):
                    raise got
                return _Resp(got)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)


class _Resp(object):
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def gone(code=404):
    return urllib.error.HTTPError("x", code, "x", None, None)


def read_rgba(data):
    """[[(r,g,b,a)...]...] 로 읽는다 (검사에서 화소를 보려고)."""
    w, h, rows = PM.read_rgba(data)
    return w, h, [[tuple(line[i:i + 4]) for i in range(0, w * 4, 4)] for line in rows]


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def make_png(rows, ctype=6, filt=0, palette=None, trns=None):
    """화소 줄들을 PNG 로. ctype 6 은 (r,g,b,a), 2 는 (r,g,b), 3 은 색 번호(깊이 8)."""
    bpp = {6: 4, 2: 3, 3: 1}[ctype]
    h, w = len(rows), len(rows[0])
    raw, prev = bytearray(), bytearray(w * bpp)
    for r in rows:
        line = bytearray(v for px in r for v in (px if isinstance(px, tuple) else (px,)))
        enc = bytearray(len(line))
        for i, v in enumerate(line):
            left = line[i - bpp] if i >= bpp else 0
            up, ul = prev[i], (prev[i - bpp] if i >= bpp else 0)
            pred = {0: 0, 1: left, 2: up, 3: (left + up) >> 1, 4: _paeth(left, up, ul)}[filt]
            enc[i] = (v - pred) & 255
        raw += bytes([filt]) + enc
        prev = line

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff))
    out = PM.SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
    if palette:
        out += chunk(b"PLTE", b"".join(bytes(c) for c in palette))
    if trns is not None:
        out += chunk(b"tRNS", bytes(trns))
    return out + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


# 코라이돈에서 뽑은 색 (얼굴 그림·걷는 시트의 실제 값)
OUTLINE = (37, 40, 51)
FACE_N = {"red": (207, 86, 65), "dark": (152, 59, 66), "blue": (73, 87, 219),
          "purple": (134, 86, 199), "line": OUTLINE}
FACE_S = {"red": (109, 109, 131), "dark": (79, 79, 98), "blue": (218, 88, 127),
          "purple": (218, 179, 79), "line": OUTLINE}
SHEET = {"red": (247, 75, 53), "dark": (196, 48, 50), "blue": (32, 62, 215),
         "purple": (152, 61, 248), "black": (0, 0, 0)}
CLEAR = (0, 0, 0, 0)


def face(colors):
    """얼굴 그림 (4x5). 바탕 없이 색 다섯 줄."""
    order = ("red", "dark", "blue", "purple", "line")
    return make_png([[colors[k] + (255,)] * 4 for k in order])


def sheet(w=4, h=2):
    """시트. 칸마다 색 다섯 가지와 투명한 자리."""
    row = [SHEET["red"] + (255,), SHEET["dark"] + (255,), SHEET["blue"] + (255,),
           SHEET["purple"] + (255,), SHEET["black"] + (255,), CLEAR]
    return make_png([row * w for _ in range(h)])


XML = """<AnimData><Anims>
  <Anim><Name>Walk</Name><FrameWidth>6</FrameWidth><FrameHeight>1</FrameHeight>
    <Durations><Duration>8</Duration><Duration>8</Duration></Durations></Anim>
  <Anim><Name>Sit</Name><FrameWidth>6</FrameWidth><FrameHeight>1</FrameHeight>
    <Durations><Duration>30</Duration></Durations></Anim>
</Anims></AnimData>"""
XML_WALK_ONLY = XML.replace("<Name>Sit</Name>", "<Name>Nope</Name>")


def lab_of(px):
    return RC.lab(px[:3])


def main():
    import urllib.request
    real = urllib.request.urlopen

    print("=== PNG 를 RGBA 로 읽기 ===")
    rows = [[(10 * x, 20 * y, 7 * x * y % 256, 255 if (x + y) % 3 else 0) for x in range(5)]
            for y in range(4)]
    for filt in range(5):
        w, h, got = PM.read_rgba(make_png(rows, 6, filt))
        chk("RGBA · 필터 %d" % filt, (w, h) == (5, 4)
            and [bytes(v for px in r for v in px) for r in rows] == [bytes(g) for g in got])
    rgb_rows = [[(1, 2, 3), (9, 9, 9)], [(9, 9, 9), (4, 5, 6)]]
    _w, _h, got = PM.read_rgba(make_png(rgb_rows, 2, 4, trns=(0, 9, 0, 9, 0, 9)))
    chk("RGB · tRNS 의 색은 투명", bytes(got[0]) == bytes((1, 2, 3, 255, 9, 9, 9, 0))
        and bytes(got[1]) == bytes((9, 9, 9, 0, 4, 5, 6, 255)), [bytes(g) for g in got])
    _w, _h, got = PM.read_rgba(make_png([[0, 1, 2]], 3, 1, palette=[(1, 1, 1), (2, 2, 2), (3, 3, 3)],
                                        trns=(0,)))
    chk("팔레트 · tRNS 로 0번 색이 투명", bytes(got[0]) == bytes((1, 1, 1, 0, 2, 2, 2, 255, 3, 3, 3, 255)),
        bytes(got[0]))
    big = make_png([[(1, 1, 1, 255)] * 2] * 1100)
    chk("1024 를 넘는 시트도 읽는다 (코라이돈 Hop 은 1152 줄)", PM.read_rgba(big)[1] == 1100)
    try:
        PM.read_indexed(make_png([[0]] * 1100, 3, palette=[(1, 1, 1)]))
        chk("팔레트 읽기의 한도는 예전 그대로 (1024)", False)
    except ValueError:
        chk("팔레트 읽기의 한도는 예전 그대로 (1024)", True)

    print("\n=== 얼굴 두 장으로 색 표 ===")
    pairs = dict(RC.table(face(FACE_N), face(FACE_S)))
    chk("바뀐 색: 빨강 -> 검정, 파랑 -> 빨강", pairs[FACE_N["red"]] == FACE_S["red"]
        and pairs[FACE_N["blue"]] == FACE_S["blue"], pairs)
    chk("안 바뀐 색(테두리)은 그대로", pairs[OUTLINE] == OUTLINE)
    for nm, a, b in (("크기가 다르다", face(FACE_N), make_png([[(1, 1, 1, 255)]])),
                     ("같은 그림이다 (이로치가 아니다)", face(FACE_N), face(FACE_N)),
                     ("모양이 다르다 (다시 그린 그림)", face(FACE_N),
                      make_png([[c + (255,) if y < 2 else CLEAR for c in [FACE_S["red"]] * 4]
                                for y in range(5)])),
                     ("한 색이 여기저기 다른 색이 된다", face(FACE_N),
                      make_png([[(x * 60, 0, 0, 255) for x in range(4)] for _y in range(5)]))):
        try:
            RC.table(a, b)
            chk("만들지 않는다: " + nm, False)
        except ValueError:
            chk("만들지 않는다: " + nm, True)

    print("\n=== 표를 시트에 입히기 ===")
    w, h, px = read_rgba(RC.apply(sheet(), RC.table(face(FACE_N), face(FACE_S))))
    red, dark, blue, purple, black, clear = px[0][:6]
    chk("크기 그대로", (w, h) == (24, 2), (w, h))
    chk("투명한 자리는 그대로", clear == CLEAR and px[1][11] == CLEAR, clear)
    chk("얼굴에서 안 바뀐 색과 짝인 색(검은 테두리)은 그대로", black == SHEET["black"] + (255,), black)
    lr, ld = lab_of(red), lab_of(dark)
    chk("빨간 몸은 검은 몸이 된다 (채도가 거의 없다)", abs(lr[1]) < 15 and abs(lr[2]) < 25 and lr[0] < 60, red)
    chk("명암은 남는다: 어두운 빨강은 더 어두운 검정", ld[0] < lr[0], (red, dark))
    chk("파란 끝은 빨간 끝이 된다", blue[0] > 150 and blue[0] > blue[2] + 40, blue)
    chk("진한 보라는 얼굴의 보라와 짝이다 (파랑이 아니라) -> 금색", purple[0] > 150 and purple[1] > 120
        and purple[2] < 110, purple)
    chk("알파는 그대로", all(p[3] in (0, 255) for line in px for p in line))

    print("\n=== 이로치 시트가 없는 종 (코라이돈) ===")
    kora = M.dex().get("KORAIDON")["num"]
    net = urllib.request.urlopen = Net([
        ("sprite/%04d/AnimData.xml" % kora, XML.encode()),
        ("sprite/%04d/Walk-Anim.png" % kora, sheet()),
        ("portrait/%04d/Normal.png" % kora, face(FACE_N)),
        ("portrait/%04d/0000/0001/Normal.png" % kora, face(FACE_S)),
    ])                                                   # 이로치 시트(0000/0001)는 404
    try:
        meta = M._anim_meta(kora, "Walk", True)
        chk("이로치로 준다 (만든 것이라고 적는다)", meta and meta.get("ok") and meta.get("shiny") is True
            and meta.get("recolor") == "portrait" and meta.get("src") == "pmd", meta)
        chk("칸 크기·지속시간은 보통 시트 그대로", (meta["frameW"], meta["frameH"], meta["durations"])
            == (6, 1, [8, 8]), meta)
        chk("이로치 시트 → 보통 시트 → 얼굴 두 장 차례로 물었다",
            [u.split("/master/")[1] for u in net.calls]
            == ["sprite/%04d/0000/0001/AnimData.xml" % kora, "sprite/%04d/AnimData.xml" % kora,
                "sprite/%04d/Walk-Anim.png" % kora, "portrait/%04d/Normal.png" % kora,
                "portrait/%04d/0000/0001/Normal.png" % kora], net.calls)
        png_path, meta_path = M._anim_paths(kora, "Walk", True)
        _w, _h, spx = read_rgba(open(png_path, "rb").read())
        chk("디스크의 이로치 시트는 검은 몸", abs(lab_of(spx[0][0])[1]) < 15, spx[0][0])
        chk("이로치 옆 폴더(1007s)에 둔다", os.path.basename(os.path.dirname(png_path)) == "%04ds" % kora)
        n = len(net.calls)
        chk("두 번째부터는 다시 안 만든다", M._meta_response(kora, "Walk", True).get("shiny") is True
            and len(net.calls) == n)
        resp = M._sheet_response(kora, "Walk", True)
        chk("시트 주소로도 이로치 시트가 나간다", resp.body == open(png_path, "rb").read())

        print("\n=== 이로치 쪽에 그 동작만 빠진 종 (레시라무의 앉기) ===")
        resh = M.dex().get("RESHIRAM")["num"]
        net = urllib.request.urlopen = Net([
            ("sprite/%04d/0000/0001/AnimData.xml" % resh, XML_WALK_ONLY.encode()),
            ("sprite/%04d/AnimData.xml" % resh, XML.encode()),
            ("sprite/%04d/Sit-Anim.png" % resh, sheet(1, 1)),
            ("portrait/%04d/Normal.png" % resh, face(FACE_N)),
            ("portrait/%04d/0000/0001/Normal.png" % resh, face(FACE_S)),
        ])
        meta = M._anim_meta(resh, "Sit", True)
        chk("앉기도 이로치로 만든다", meta and meta.get("ok") and meta.get("shiny") is True
            and meta.get("anim") == "Sit", meta)

        print("\n=== 메가 폼 (메가마기라스: 0248/0001) ===")
        tyr = [m for m in M.dex().raw["megas"] if m["internal"] == "TYRANITAR_MEGA"][0]
        chk("도감의 경로", tyr.get("walk") == "0248/0001", tyr.get("walk"))
        net = urllib.request.urlopen = Net([
            ("sprite/0248/0001/AnimData.xml", XML.encode()),
            ("sprite/0248/0001/Walk-Anim.png", sheet()),
            ("portrait/0248/0001/Normal.png", face(FACE_N)),
            ("portrait/0248/0001/0001/Normal.png", face(FACE_S)),
        ])
        meta = M._anim_meta(tyr["num"], "Walk", True)
        chk("메가의 얼굴 그림은 폼 폴더와 그 아래 0001", meta and meta.get("shiny") is True
            and any(u.endswith("portrait/0248/0001/0001/Normal.png") for u in net.calls), net.calls)

        print("\n=== 없을 때와 끊겼을 때 ===")
        mira = M.dex().get("MIRAIDON")["num"]

        def table_for(num, shiny_face):
            return [("sprite/%04d/AnimData.xml" % num, XML.encode()),
                    ("sprite/%04d/Walk-Anim.png" % num, sheet()),
                    ("portrait/%04d/Normal.png" % num, face(FACE_N)),
                    ("portrait/%04d/0000/0001/Normal.png" % num, shiny_face)]
        net = urllib.request.urlopen = Net(table_for(mira, gone(503)))
        chk("얼굴 그림이 잠깐 안 되면(503) 모른다고 한다", M._anim_meta(mira, "Walk", True) is None
            and M._meta_response(mira, "Walk", True) == {"ok": False, "retry": True})
        chk("  표시를 안 남긴다 (다음에 다시 묻는다)", not os.path.exists(M._anim_paths(mira, "Walk", True)[1]))
        net = urllib.request.urlopen = Net(table_for(mira, urllib.error.URLError("끊김")))
        chk("끊겨도 표시를 안 남긴다", M._anim_meta(mira, "Walk", True) is None
            and not os.path.exists(M._anim_paths(mira, "Walk", True)[1]))
        net = urllib.request.urlopen = Net(table_for(mira, face(FACE_N)))
        chk("이로치 얼굴이 보통 얼굴과 같으면 없다고 적는다", M._anim_meta(mira, "Walk", True) is None
            and json.load(open(M._anim_paths(mira, "Walk", True)[1], encoding="utf-8"))
            == {"ok": False, "gen": M.MISS_GEN})
        groud = M.dex().get("GROUDON")["num"]
        net = urllib.request.urlopen = Net(table_for(groud, face(FACE_S))[:3])   # 이로치 얼굴 404
        chk("이로치 얼굴이 없으면(404) 없다고 적는다 (보통 색으로 걷는다)",
            M._anim_meta(groud, "Walk", True) is None
            and json.load(open(M._anim_paths(groud, "Walk", True)[1], encoding="utf-8"))["ok"] is False)
        net = urllib.request.urlopen = Net([])
        chk("보통 시트도 없으면 만들지 않는다", M._anim_meta(9, "Idle", True) is None
            and not any("portrait" in u for u in net.calls), net.calls)
        chk("  그 자리에서 이로치도 없다고 적는다 (한 번 더 안 물어도 된다)",
            M._meta_response(9, "Idle", True) == {"ok": False}
            and json.load(open(M._anim_paths(9, "Idle", True)[1], encoding="utf-8"))["ok"] is False)
        net = urllib.request.urlopen = Net([("sprite/0010/0000/0001/", gone(404)),
                                            ("githubusercontent", urllib.error.URLError("끊김"))])
        chk("보통 시트를 지금 못 받으면 모른다고 한다", M._anim_meta(10, "Walk", True) is None
            and not os.path.exists(M._anim_paths(10, "Walk", True)[1]), net.calls)

        print("\n=== 보통 걷기가 다른 출처인 종은 얼굴 그림을 안 쓴다 ===")
        frill = M.dex().get("FRILLISH")["num"]
        pn, mn = M._anim_paths(frill, "Walk")
        os.makedirs(os.path.dirname(mn), exist_ok=True)
        with open(mn, "w", encoding="utf-8") as f:
            json.dump({"ok": True, "src": "follow", "frameW": 32, "frameH": 32,
                       "durations": [9], "frames": 1, "rows": 4}, f)
        net = urllib.request.urlopen = Net([])
        M._anim_meta(frill, "Walk", True)
        chk("그림체가 다른 시트에는 입히지 않는다", not any("portrait" in u for u in net.calls), net.calls)

        print("\n=== 예전 '이로치 없음' 표시 ===")
        drat = M.dex().get("DRATINI")["num"]
        _p, old = M._anim_paths(drat, "Sit", True)
        os.makedirs(os.path.dirname(old), exist_ok=True)
        with open(old, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "gen": 2}, f)            # 1.10.0 까지의 서버가 남긴 표시
        net = urllib.request.urlopen = Net(table_for(drat, face(FACE_S))
                                           + [("sprite/%04d/Sit-Anim.png" % drat, sheet(1, 1))])
        meta = M._anim_meta(drat, "Sit", True)
        chk("걷기가 아닌 동작도 한 번 더 찾아본다", meta and meta.get("shiny") is True, meta)
        with open(old, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "gen": M.MISS_GEN}, f)
        net = urllib.request.urlopen = Net([])
        chk("지금 세대의 '없음' 은 그대로 믿는다", M._anim_meta(drat, "Sit", True) == {"ok": False, "gen": M.MISS_GEN}
            and net.calls == [], net.calls)
        _p, plain = M._anim_paths(drat, "Hurt")
        with open(plain, "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)
        chk("보통 색 동작의 옛 '없음' 은 예전처럼 믿는다", M._anim_meta(drat, "Hurt") == {"ok": False}
            and net.calls == [], net.calls)
    finally:
        urllib.request.urlopen = real

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
