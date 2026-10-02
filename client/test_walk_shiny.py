# -*- coding: utf-8 -*-
"""이로치 걷는 도트를 받아 두는 규칙 (1.4.0).

    python client/test_walk_shiny.py

창을 만들지 않는다. 가짜 API 로 walk_cache 만 본다. 못 박는 것:

  1. 이로치 시트는 옆 폴더(0025s)에 받는다. 보통 시트와 섞이지 않는다.
  2. 이로치 시트가 없는 종은 **보통 색 시트로 걷는다** (배틀 도트로 굳지 않는다).
  3. 옛 서버가 ?shiny 를 모르고 보통 시트를 주면(shiny 표시 없음) 이로치
     폴더에 굳혀 두지 않는다 - 서버가 바뀐 뒤에 영영 보통 색이 된다.
  4. ensure_many 의 열쇠: 보통은 번호, 이로치는 (번호, True).
"""
import json
import os
import shutil
import sys
import tempfile

HOME = tempfile.mkdtemp(prefix="poket-walk-shiny-")
os.environ["POKET_HOME"] = HOME

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import walk_cache as WC                  # noqa: E402

OK = FAIL = 0
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class FakeApi(object):
    """num 별로 이로치가 있나 · 서버가 shiny 를 아나를 정한다."""

    def __init__(self, shiny_nums=(), old_server=False):
        self.shiny_nums = set(shiny_nums)
        self.old = old_server
        self.calls = []

    def anim_meta(self, num, name="Walk", shiny=False):
        self.calls.append(("meta", num, name, shiny))
        meta = {"ok": True, "frameW": 32, "frameH": 40, "durations": [8],
                "frames": 1, "rows": 8, "src": "pmd", "anim": name}
        if shiny and not self.old:
            if num not in self.shiny_nums:
                return {"ok": False}
            meta["shiny"] = True
        return meta

    def anim_sheet(self, num, name="Walk", shiny=False):
        self.calls.append(("sheet", num, name, shiny))
        return PNG + (b"S" if shiny else b"N")


def t_new_source():
    """1.9.0: 서버에 걷는 도트 출처가 하나 더 붙었다 (미라이돈 등 40종, 메가 19폼).

    이 PC 에 '없다' 고 적어 둔 옛 표시를 그대로 믿으면 영영 안 걷는다.
    """
    print("\n=== 옛 '없음' 표시는 다시 묻는다 (1.9.0) ===")

    class Api(object):
        def __init__(self, have=(), src="ow"):
            self.have, self.src, self.calls = set(have), src, []

        def anim_meta(self, num, name="Walk", shiny=False):
            self.calls.append((num, name))
            if num in self.have and name == "Walk":
                return {"ok": True, "frameW": 64, "frameH": 64, "durations": [12, 12],
                        "frames": 2, "rows": 4, "src": self.src, "anim": "Walk",
                        "rowmap": {"down": 0, "left": 1, "right": 2, "up": 3}}
            if name == "Idle" and num == 990:
                return {"ok": True, "frameW": 32, "frameH": 32, "durations": [8], "src": "pmd"}
            return {"ok": False}

        def anim_sheet(self, num, name="Walk", shiny=False):
            return PNG + b"W"

    # 예전 판이 '미라이돈(1008)에는 걷는 도트가 없다' 고 적어 둔 PC
    png, meta_path = WC._paths(1008, "Walk")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"ok": False}, f)
    chk("옛 표시(세대 없음)는 못 본 것으로 친다", WC.local(1008, "Walk") == (None, None),
        WC.local(1008, "Walk"))
    api = Api(have={1008})
    got, meta = WC.ensure(api, 1008, "Walk")
    chk("서버에 다시 물어 받아 온다", got and meta.get("src") == "ow" and (1008, "Walk") in api.calls,
        (got, api.calls))
    chk("이제 걷는다 (다음부터는 안 묻는다)", WC.local(1008, "Walk")[0] == got
        and (WC.ensure(api, 1008, "Walk")[0], len(api.calls))[1] == 1, api.calls)

    # 새 출처에도 없는 종(Z-A 의 새 메가 등)은 새 세대로 적어 두고 다시 안 묻는다
    api = Api()
    WC.ensure(api, 10300, "Walk")
    with open(WC._paths(10300, "Walk")[1], encoding="utf-8") as f:
        mark = json.load(f)
    chk("없으면 지금 세대로 적는다", mark == {"ok": False, "gen": WC.MISS_GEN}, mark)
    n = len(api.calls)
    WC.ensure(api, 10300, "Walk")
    chk("지금 세대의 '없음' 은 믿는다 (다시 안 묻는다)", len(api.calls) == n
        and WC.local(10300, "Walk") == (None, mark), api.calls)

    # 다른 동작의 옛 '없음' 은 그대로 믿는다 (새 출처에는 걷기밖에 없다)
    png, meta_path = WC._paths(25, "Sleep")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"ok": False}, f)
    chk("걷기가 아닌 동작의 옛 표시는 그대로", WC.local(25, "Sleep") == (None, {"ok": False}))

    print("\n=== 걷기밖에 없는 출처 (1.9.0) ===")
    api = Api(have={990})
    WC.ensure(api, 990, "Walk")
    chk("걷기가 셋째 출처에서 온 종", WC.walk_only(990) is True)
    n = len(api.calls)
    chk("다른 동작은 쓰지 않는다 (서 있을 때만 그림체가 바뀌지 않게)",
        WC.ensure(api, 990, "Idle") == (None, None) and len(api.calls) == n, api.calls[n:])
    api = Api(have={25}, src="pmd")
    WC._failed.clear()
    p25 = WC._paths(25, "Walk")
    for f in p25:
        if os.path.exists(f):
            os.remove(f)
    WC.ensure(api, 25, "Walk")
    chk("첫째 출처에서 온 종은 그대로 다른 동작을 받는다", WC.walk_only(25) is False)


def main():
    print("=== 열쇠 ===")
    chk("보통은 번호 그대로", WC.key(25) == 25 and WC.key(25, False) == 25)
    chk("이로치는 (번호, True)", WC.key(25, True) == (25, True))
    chk("번호가 없으면 그대로", WC.key(None, True) is None)
    chk("동작 시트 열쇠", WC.sheet_key(25, "Idle") == (25, "Idle")
        and WC.sheet_key(25, "Idle", True) == (25, "Idle", True))

    print("\n=== 이로치 시트가 있는 종 ===")
    api = FakeApi(shiny_nums={25})
    png, meta = WC.ensure(api, 25, "Walk", shiny=True)
    chk("이로치 폴더에 받는다", png and os.path.basename(os.path.dirname(png)) == "0025s",
        png)
    chk("이로치 시트 내용", open(png, "rb").read().endswith(b"S"))
    chk("메타에 이로치 표시", meta.get("shiny") is True, meta)
    png2, _m = WC.ensure(api, 25, "Walk")
    chk("보통 시트는 따로", png2 and os.path.basename(os.path.dirname(png2)) == "0025"
        and open(png2, "rb").read().endswith(b"N"), png2)
    n = len(api.calls)
    WC.ensure(api, 25, "Walk", shiny=True)
    chk("두 번째부터는 서버에 안 묻는다", len(api.calls) == n, api.calls[n:])

    print("\n=== 이로치 시트가 없는 종 ===")
    png, meta = WC.ensure(api, 7, "Walk", shiny=True)
    chk("보통 색 시트로 걷는다", png and open(png, "rb").read().endswith(b"N"), png)
    chk("없다고 적어 둔다 (다음부터 안 묻는다)",
        json.load(open(WC._paths(7, "Walk", True)[1], encoding="utf-8"))
        == {"ok": False, "gen": WC.MISS_GEN})

    print("\n=== 옛 서버 (shiny 를 모른다) ===")
    old = FakeApi(old_server=True)
    png, meta = WC.ensure(old, 4, "Walk", shiny=True)
    chk("보통 시트로 걷되", png and open(png, "rb").read().endswith(b"N"), png)
    chk("이로치 폴더에는 아무것도 안 남긴다",
        not os.path.exists(WC._paths(4, "Walk", True)[1]))
    WC._failed.clear()
    new = FakeApi(shiny_nums={4})
    png, meta = WC.ensure(new, 4, "Walk", shiny=True)
    chk("서버가 바뀌면 이로치로 받는다", png and open(png, "rb").read().endswith(b"S"),
        png)

    print("\n=== 가짜 API 가 shiny 를 모를 때 ===")

    class Plain(object):
        def anim_meta(self, num, name="Walk"):
            return {"ok": True, "frameW": 32, "frameH": 40, "durations": [8]}

        def anim_sheet(self, num, name="Walk"):
            return PNG + b"N"
    png, _m = WC.ensure(Plain(), 150, "Walk", shiny=True)
    chk("터지지 않고 보통 시트", png and open(png, "rb").read().endswith(b"N"))

    print("\n=== ensure_many ===")
    got = WC.ensure_many(api, [25, (25, True), (7, True), (25, True), None])
    chk("열쇠 셋 (중복·None 은 뺀다)", set(got) == {25, (25, True), (7, True)}, list(got))
    chk("이로치 열쇠에는 이로치 시트", open(got[(25, True)][0], "rb").read().endswith(b"S"))

    t_new_source()

    shutil.rmtree(HOME, ignore_errors=True)
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
