# -*- coding: utf-8 -*-
"""걷는 도트의 세 번째 출처 검사 (1.9.0). 네트워크 없이 돈다.

    python server/test_walk_ow.py

미라이돈·패러독스 등 40종과 메가 19폼(메가보만다 …)은 앞의 두 출처에 걷는
도트가 없다. 세 번째 출처(pokeemerald-expansion 의 overworld.png)에서 받아
우리 시트 꼴로 바꾼다. 못 박는 것:

  1. pngmini — 팔레트 PNG 를 읽는다 (깊이 4·8, 필터 다섯 가지 전부).
  2. 한 줄 여섯 칸을 **네 줄 x 두 칸**(아래·왼쪽·오른쪽·위)으로 다시 짠다.
     오른쪽은 왼쪽을 뒤집은 것, 0번 색은 투명, 이로치는 팔레트만 갈아 끼운다.
  3. 앞의 두 출처에 없을 때만 셋째로 간다. 메가는 도감의 "ow:" 경로로.
  4. **404 일 때만** 없다고 적는다. 끊긴 것은 다음에 다시 묻는다.
  5. 출처가 늘기 전에 '없다' 고 적어 둔 걷기는 한 번 더 찾아본다.
  6. 걷기밖에 없는 출처에서 온 종은 다른 동작을 주지 않는다 (그림체가 섞인다).
  7. (1.9.1) 레전드 Z-A 의 메가 22폼은 **배틀 도트**를 쇼다운 사이트에서 받는다.
     걷는 도트는 어디에도 없어서, 이 폼들은 배틀 도트로 서서 움직인다.
"""
import io
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

TMP = tempfile.mkdtemp(prefix="poket-walk-ow-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ["POKET_WALK_DIR"] = os.path.join(TMP, "walk")
os.environ["POKET_SPRITE_DIR"] = os.path.join(TMP, "sprites")
os.environ["POKET_WARM_SPRITES"] = "0"
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import main as M                                    # noqa: E402
from app import pngmini as PM                                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


# ---------------------------------------------------------------- 검사용 팔레트 PNG
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def make_indexed(rows, palette, depth=4, filt=0):
    """색 번호 줄들을 팔레트 PNG 로. filt 는 줄마다 쓸 필터 (0~4)."""
    h, w = len(rows), len(rows[0])
    lines = []
    for r in rows:
        if depth == 8:
            lines.append(bytearray(r))
        else:
            per, out = 8 // depth, bytearray()
            for i in range(0, w, per):
                b = 0
                for k in range(per):
                    v = r[i + k] if i + k < w else 0
                    b |= v << (8 - depth * (k + 1))
                out.append(b)
            lines.append(out)
    raw, prev = bytearray(), bytearray(len(lines[0]))
    for line in lines:
        enc = bytearray(len(line))
        for i, v in enumerate(line):
            left = line[i - 1] if i else 0
            up, ul = prev[i], (prev[i - 1] if i else 0)
            pred = {0: 0, 1: left, 2: up, 3: (left + up) >> 1, 4: _paeth(left, up, ul)}[filt]
            enc[i] = (v - pred) & 255
        raw += bytes([filt]) + enc
        prev = line

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff))
    plte = b"".join(bytes(c) for c in palette)
    return (PM.SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, 3, 0, 0, 0))
            + chunk(b"PLTE", plte) + chunk(b"IDAT", zlib.compress(bytes(raw)))
            + chunk(b"IEND", b""))


def read_rgba(data):
    """pngmini.write_rgba 가 쓴 것을 도로 읽는다 (필터 0, RGBA 8비트)."""
    w = h = None
    raw = b""
    pos = 8
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert (depth, ctype) == (8, 6), (depth, ctype)
        elif kind == b"IDAT":
            raw += body
        pos += 12 + n
    flat = zlib.decompress(raw)
    out = []
    for y in range(h):
        line = flat[y * (w * 4 + 1) + 1:(y + 1) * (w * 4 + 1)]
        out.append([tuple(line[i:i + 4]) for i in range(0, w * 4, 4)])
    return w, h, out


PAL = [(115, 197, 164)] + [(i * 16, 255 - i * 16, (i * 37) % 256) for i in range(1, 16)]
SHINY = [(1, 2, 3)] + [(255 - i * 16, i * 16, (i * 91) % 256) for i in range(1, 16)]
C = 4                                   # 검사용 칸 한 변


def strip(n=6, cell=C):
    """칸 n 개짜리 한 줄. i 번째 칸은 왼쪽 위 화소만 색 i+1, 왼쪽 열은 색 9, 나머지는 바탕(0)."""
    rows = []
    for y in range(cell):
        line = []
        for i in range(n):
            for x in range(cell):
                line.append(i + 1 if (x, y) == (0, 0) else (9 if x == 0 else 0))
        rows.append(line)
    return rows


class Net(object):
    """urllib.request.urlopen 대신. 주소 조각 -> 바이트 / 오류."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, url, timeout=None):
        url = getattr(url, "full_url", url)          # Request 로 부르는 곳도 있다
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


def pal_text(pal):
    return "JASC-PAL\r\n0100\r\n%d\r\n" % len(pal) + "".join("%d %d %d\r\n" % c for c in pal)


def main():
    import urllib.request
    real = urllib.request.urlopen

    print("=== 팔레트 PNG 읽기 ===")
    rows = strip()
    for depth in (4, 8):
        for filt in range(5):
            w, h, got, pal = PM.read_indexed(make_indexed(rows, PAL, depth, filt))
            chk("깊이 %d · 필터 %d" % (depth, filt), (w, h) == (24, 4) and got == rows and pal == PAL,
                (w, h))
    try:
        PM.read_indexed(b"not a png")
        chk("PNG 가 아니면 ValueError", False)
    except ValueError:
        chk("PNG 가 아니면 ValueError", True)
    try:
        PM.read_indexed(PM.write_rgba(1, 1, [b"\x00\x00\x00\x00"]))
        chk("팔레트 그림이 아니면 ValueError", False)
    except ValueError:
        chk("팔레트 그림이 아니면 ValueError", True)

    print("\n=== 한 줄 -> 네 줄 x 두 칸 ===")
    chk("여섯 칸: 아래·위·왼쪽 두 칸씩", PM.frames_of(192, 32)
        == {"down": (0, 1), "up": (2, 3), "left": (4, 5)})
    chk("아홉 칸(옛 배치): 선 자세 셋 뒤의 걷는 칸", PM.frames_of(288, 32)
        == {"down": (3, 4), "up": (5, 6), "left": (7, 8)})
    chk("모르는 배치는 None", PM.frames_of(100, 32) is None and PM.frames_of(160, 32) is None)
    png, cell = PM.overworld_sheet(make_indexed(rows, PAL))
    w, h, px = read_rgba(png)
    chk("두 칸 x 네 줄", (w, h, cell) == (C * 2, C * 4, C), (w, h, cell))

    def mark(row, col):
        """그 칸에서 색 1~6 이 찍힌 자리와 그 색 번호."""
        for y in range(C):
            for x in range(C):
                p = px[row * C + y][col * C + x]
                if p[3] and p[:3] in PAL[1:7]:
                    return (x, y), PAL.index(p[:3])
        return None
    chk("0줄 = 아래 (칸 1, 2)", (mark(0, 0), mark(0, 1)) == (((0, 0), 1), ((0, 0), 2)), (mark(0, 0), mark(0, 1)))
    chk("1줄 = 왼쪽 (칸 5, 6)", (mark(1, 0), mark(1, 1)) == (((0, 0), 5), ((0, 0), 6)), (mark(1, 0), mark(1, 1)))
    chk("2줄 = 오른쪽: 왼쪽을 좌우로 뒤집는다", (mark(2, 0), mark(2, 1))
        == (((C - 1, 0), 5), ((C - 1, 0), 6)), (mark(2, 0), mark(2, 1)))
    chk("3줄 = 위 (칸 3, 4)", (mark(3, 0), mark(3, 1)) == (((0, 0), 3), ((0, 0), 4)), (mark(3, 0), mark(3, 1)))
    chk("서버가 알려 주는 방향 차례와 같다", PM.ROWS == tuple(k for k, _v in sorted(
        M.ROWMAP_FOLLOW.items(), key=lambda kv: kv[1])))
    chk("0번 색(바탕)은 투명", px[0][1] == (0, 0, 0, 0) and px[C * 2][0] == (0, 0, 0, 0))
    chk("그림은 불투명, 원래 색", px[1][0] == PAL[9] + (255,), px[1][0])
    png2, _c = PM.overworld_sheet(make_indexed(rows, PAL), SHINY)
    _w, _h, px2 = read_rgba(png2)
    chk("이로치: 같은 그림에 팔레트만 바꾼다", px2[1][0] == SHINY[9] + (255,)
        and px2[0][1] == (0, 0, 0, 0) and px2[0][0] == SHINY[1] + (255,), px2[1][0])
    png9, _c = PM.overworld_sheet(make_indexed(strip(9), PAL))
    _w, _h, px = read_rgba(png9)
    chk("아홉 칸짜리도 걷는 칸만 뽑는다", mark(0, 0) == ((0, 0), 4) and mark(0, 1) == ((0, 0), 5),
        (mark(0, 0), mark(0, 1)))
    try:
        PM.overworld_sheet(make_indexed(strip(5), PAL))
        chk("모르는 배치는 ValueError", False)
    except ValueError:
        chk("모르는 배치는 ValueError", True)
    chk("팔레트 파일 읽기", PM.parse_pal(pal_text(SHINY)) == SHINY)
    try:
        PM.parse_pal("<html>404</html>")
        chk("팔레트 파일이 아니면 ValueError", False)
    except ValueError:
        chk("팔레트 파일이 아니면 ValueError", True)

    print("\n=== 폴더 이름 ===")
    for en, want in (("Miraidon", "miraidon"), ("Iron Treads", "iron_treads"), ("Mr. Rime", "mr_rime"),
                     ("Sirfetch'd", "sirfetchd"), ("Wo-Chien", "wo_chien"), ("Type: Null", "type_null"),
                     ("Nidoran♀", "nidoran_f"), ("Flabébé", "flabebe"), ("Ho-Oh", "ho_oh")):
        chk("%s -> %s" % (en, want), M.ow_folder(en) == want, M.ow_folder(en))
    d = M.dex()
    mira = d.get("MIRAIDON")["num"]
    chk("도감 번호에서 폴더를 찾는다", M._ow_path(mira) == "miraidon", M._ow_path(mira))

    print("\n=== 앞의 두 출처에 없을 때만 셋째로 ===")
    sheet = make_indexed(strip(6, 8), PAL)
    try:
        net = urllib.request.urlopen = Net([("miraidon/overworld.png", sheet),
                                            ("miraidon/overworld_shiny.pal", pal_text(SHINY).encode())])
        meta = M._anim_meta(mira, "Walk")
        chk("미라이돈: 셋째 출처에서 걷는다", meta and meta.get("ok") and meta["src"] == "ow"
            and (meta["frameW"], meta["frameH"], meta["frames"], meta["rows"]) == (8, 8, 2, 4)
            and meta["rowmap"] == M.ROWMAP_FOLLOW and meta["durations"] == M.OW_TICKS, meta)
        chk("첫째 → 둘째 → 셋째 차례로 물었다", [("SpriteCollab" in u, "followers" in u, "pokeemerald" in u)
                                       for u in net.calls]
            == [(True, False, False), (False, True, False), (False, False, True)], net.calls)
        png_path, _m = M._anim_paths(mira, "Walk")
        w, h, px = read_rgba(open(png_path, "rb").read())
        chk("디스크에 우리 시트 꼴로 남는다", (w, h) == (16, 32), (w, h))
        n = len(net.calls)
        M._anim_meta(mira, "Walk")
        chk("두 번째부터는 다시 받지 않는다", len(net.calls) == n)
        sm = M._anim_meta(mira, "Walk", True)
        chk("이로치도 셋째 출처에서 (팔레트)", sm and sm.get("ok") and sm.get("shiny") is True
            and sm["src"] == "ow" and any("overworld_shiny.pal" in u for u in net.calls), sm)
        _w, _h, spx = read_rgba(open(M._anim_paths(mira, "Walk", True)[0], "rb").read())
        chk("  이로치 색으로 칠해졌다", spx[1][0] == SHINY[9] + (255,), spx[1][0])
        chk("다른 동작은 없다고 한다 (걷기밖에 없는 출처)", M._anim_meta(mira, "Idle") == {"ok": False}
            and M._meta_response(mira, "Idle") == {"ok": False})

        print("\n=== 메가 폼 ===")
        sal = [m for m in d.raw["megas"] if m["internal"] == "SALAMENCE_MEGA"][0]
        chk("도감에 경로가 적혀 있다", sal.get("walk") == "ow:salamence/mega", sal.get("walk"))
        ows = [m for m in d.raw["megas"] if str(m.get("walk") or "").startswith(M.OW_MARK)]
        chk("셋째 출처로 걷는 메가는 19폼", len(ows) == 19, len(ows))
        net = urllib.request.urlopen = Net([("salamence/mega/overworld.png", sheet)])
        meta = M._anim_meta(sal["num"], "Walk")
        chk("메가보만다가 걷는다", meta and meta.get("ok") and meta["src"] == "ow", meta)
        chk("SpriteCollab 은 묻지 않고 바로 셋째로", len(net.calls) == 1 and "salamence/mega" in net.calls[0],
            net.calls)
        chk("메가의 다른 동작은 없다", M._anim_meta(sal["num"], "Idle") in (None, {"ok": False}))
        zard = [m for m in d.raw["megas"] if m["internal"] == "CHARIZARD_MEGA_X"][0]
        chk("SpriteCollab 에 있는 메가는 그대로 (경로가 안 바뀐다)", zard.get("walk") == "0006/0001",
            zard.get("walk"))

        print("\n=== 없을 때와 끊겼을 때 ===")
        tread = d.get("IRONTREADS")["num"]
        net = urllib.request.urlopen = Net([])                       # 셋 다 404
        chk("세 출처에 다 없으면 없다고 한다", M._anim_meta(tread, "Walk") is None
            and M._meta_response(tread, "Walk") == {"ok": False})
        mark = json.load(open(M._anim_paths(tread, "Walk")[1], encoding="utf-8"))
        chk("없다는 표시에 세대를 적는다", mark == {"ok": False, "gen": M.MISS_GEN}, mark)
        n = len(net.calls)
        M._anim_meta(tread, "Walk")
        chk("지금 세대의 '없음' 은 다시 안 묻는다", len(net.calls) == n)

        pao = d.get("CHIENPAO")["num"]
        net = urllib.request.urlopen = Net([("chien_pao/overworld.png", gone(503))])
        chk("저쪽이 잠깐 안 되면(503) 모른다고 한다", M._anim_meta(pao, "Walk") is None
            and M._meta_response(pao, "Walk") == {"ok": False, "retry": True})
        chk("  표시를 안 남긴다 (다음에 다시 묻는다)", not os.path.exists(M._anim_paths(pao, "Walk")[1]))
        net = urllib.request.urlopen = Net([("chien_pao/overworld.png", urllib.error.URLError("끊김"))])
        chk("끊겨도 표시를 안 남긴다", M._anim_meta(pao, "Walk") is None
            and not os.path.exists(M._anim_paths(pao, "Walk")[1]))
        net = urllib.request.urlopen = Net([("chien_pao/overworld.png", make_indexed(strip(5), PAL))])
        chk("받았는데 모르는 꼴이면 없다고 적는다", M._anim_meta(pao, "Walk") is None
            and json.load(open(M._anim_paths(pao, "Walk")[1], encoding="utf-8"))["ok"] is False)
        bad = os.path.join(TMP, "bad.json")
        n = len(net.calls)
        chk("이상한 경로는 받지 않는다 (경로가 주소에 들어간다)",
            M._walk_fetch_ow("../../etc", os.path.join(TMP, "bad.png"), bad) is None
            and M._walk_fetch_ow("a/b/c", os.path.join(TMP, "bad.png"), bad) is None
            and M._walk_fetch_ow("Salamence/Mega", os.path.join(TMP, "bad.png"), bad) is None
            and len(net.calls) == n, net.calls[n:])

        print("\n=== 옛 '없음' 표시는 한 번 더 찾아본다 ===")
        zar = d.get("ZARUDE")["num"]
        png_path, meta_path = M._anim_paths(zar, "Walk")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)                  # 1.8.1 까지의 서버가 남긴 표시
        net = urllib.request.urlopen = Net([("zarude/overworld.png", sheet)])
        meta = M._anim_meta(zar, "Walk")
        chk("출처가 늘기 전의 '없음' 은 다시 찾아본다", meta and meta.get("ok") and meta["src"] == "ow", meta)
        _p, idle_meta = M._anim_paths(25, "Sleep")
        os.makedirs(os.path.dirname(idle_meta), exist_ok=True)
        with open(idle_meta, "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)
        net = urllib.request.urlopen = Net([])
        chk("걷기가 아닌 동작의 옛 '없음' 은 그대로 믿는다", M._anim_meta(25, "Sleep") == {"ok": False}
            and net.calls == [], net.calls)

        print("\n=== 메가 폼의 배틀 도트: 쇼다운 사이트에서 (1.9.1) ===")
        # 레전드 Z-A 의 메가 폼은 PokeAPI 저장소에 도트가 없어 아이콘·일러스트가
        # 나왔고, 바탕화면에서 메가 모습이 될 수 없었다. 22폼은 쇼다운에 있다.
        from common import sprite_fix as SF
        gren = [m for m in d.raw["megas"] if m["internal"] == "GRENINJA_MEGA"][0]["num"]
        absz = [m for m in d.raw["megas"] if m["internal"] == "ABSOL_MEGA_Z"][0]["num"]
        chk("스물두 폼", len(SF.SITE) == 22 and gren in SF.SITE and absz in SF.SITE, len(SF.SITE))
        chk("주소와 확장자", SF.site(gren) == (SF.SITE_BASE + "/ani/greninja-mega.gif", ".gif")
            and SF.site(absz) == (SF.SITE_BASE + "/gen5/absol-megaz.png", ".png"), SF.site(gren))
        chk("이로치 그림이 있는 폼은 -shiny 폴더", SF.site(absz, True)[0]
            == SF.SITE_BASE + "/gen5-shiny/absol-megaz.png", SF.site(absz, True))
        chk("이로치 그림이 없는 폼은 보통 색 그림을 쓴다", SF.site(gren, True) == SF.site(gren))
        chk("표에 없는 번호는 없다", SF.site(25) == (None, None) and SF.site(10034) == (None, None))
        chk("캐시 이름에 판이 붙는다 (예전에 받은 아이콘을 안 쓴다)",
            SF.rev(gren) == SF.SITE_REV and SF.rev(25) == "" and SF.rev(618) == "r2")
        chk("도감에 배틀 도트가 있다고 적혀 있다", all(
            (d.by_num.get(n) or {}).get("dot") is True for n in SF.SITE))
        os.makedirs(M.SPRITE_DIR, exist_ok=True)
        with open(os.path.join(M.SPRITE_DIR, "%04d.png" % gren), "wb") as f:
            f.write(b"old-icon")                         # 1.9.0 까지 받아 둔 아이콘
        chk("예전 이름의 캐시는 못 본 것으로 친다", M._sprite_cached(gren, False) == (None, None))
        net = urllib.request.urlopen = Net([("play.pokemonshowdown.com/sprites/ani/greninja-mega.gif",
                                             b"GIF89a-mega")])
        path, ext = M._sprite_fetch(gren, False)
        chk("쇼다운 사이트에서 먼저 받는다", ext == ".gif" and len(net.calls) == 1
            and open(path, "rb").read() == b"GIF89a-mega"
            and os.path.basename(path) == "%04d-%s.gif" % (gren, SF.SITE_REV),
            (path, net.calls))
        chk("두 번째부터는 캐시", M._sprite_cached(gren, False) == (path, ".gif"))
        net = urllib.request.urlopen = Net([("gen5-shiny/absol-megaz.png", b"PNG-shiny")])
        path, ext = M._sprite_fetch(absz, True)
        chk("이로치는 -shiny 폴더에서", ext == ".png" and open(path, "rb").read() == b"PNG-shiny"
            and os.path.basename(path) == "%04ds-%s.png" % (absz, SF.SITE_REV), path)
        net = urllib.request.urlopen = Net([("other/official-artwork", b"PNG-art")])
        gol = [m for m in d.raw["megas"] if m["internal"] == "GOLURK_MEGA"][0]["num"]
        path, ext = M._sprite_fetch(gol, False)
        chk("사이트에서 못 받으면 예전 차례(아이콘·일러스트)로 간다", ext == ".png"
            and "play.pokemonshowdown.com" in net.calls[0] and open(path, "rb").read() == b"PNG-art",
            net.calls)
        net = urllib.request.urlopen = Net([("other/showdown/25.gif", b"GIF-pika")])
        path, ext = M._sprite_fetch(25, False)
        chk("보통 종은 예전 그대로 (PokeAPI 에서)", ext == ".gif" and len(net.calls) == 1
            and "PokeAPI" in net.calls[0] and os.path.basename(path) == "0025.gif", net.calls)
    finally:
        urllib.request.urlopen = real

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
