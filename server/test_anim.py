# -*- coding: utf-8 -*-
"""동작 도트를 내주는 부분 — 이름 검사, CopyOf, PNG 크기 읽기, 이사.

**네트워크를 쓰지 않는다.** GitHub 이 느리거나 막힌 날 CI 가 빨개지면
안 되고, 여기서 보려는 것은 우리 판단이지 저쪽 파일이 아니다.
"""
import io
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


TMP = tempfile.mkdtemp(prefix="poket-anim-")
os.environ.setdefault("POKET_DB", os.path.join(TMP, "t.db"))
os.environ["POKET_SPRITE_DIR"] = os.path.join(TMP, "sprites")
os.environ["POKET_WALK_DIR"] = os.path.join(TMP, "walk")

from app import main as M                                   # noqa: E402


XML = """<AnimData>
  <Anims>
    <Anim><Name>Walk</Name><Index>0</Index>
      <FrameWidth>32</FrameWidth><FrameHeight>40</FrameHeight>
      <Durations><Duration>8</Duration><Duration>10</Duration></Durations>
    </Anim>
    <Anim><Name>Shoot</Name><Index>1</Index>
      <FrameWidth>40</FrameWidth><FrameHeight>56</FrameHeight>
      <Durations><Duration>3</Duration></Durations>
    </Anim>
    <Anim><Name>SpAttack</Name><CopyOf>Shoot</CopyOf></Anim>
    <Anim><Name>Broken</Name><CopyOf>Nope</CopyOf></Anim>
    <Anim><Name>Loop</Name><CopyOf>Loop2</CopyOf></Anim>
    <Anim><Name>Loop2</Name><CopyOf>Loop</CopyOf></Anim>
  </Anims>
</AnimData>"""


def main():
    root = ET.fromstring(XML)

    print("=== AnimData 읽기 ===")
    got = M._pick_anim(root, "Walk")
    chk("걷기: 칸 크기와 지속시간", got == (32, 40, [8, 10], "Walk"), got)
    chk("없는 이름은 None", M._pick_anim(root, "Hop") is None)

    print("\n=== CopyOf ===")
    # 파이리의 SpAttack 이 실제로 이렇다. 자기 PNG 도 칸 크기도 없다.
    got = M._pick_anim(root, "SpAttack")
    chk("가리키는 쪽의 칸 크기를 쓴다",
        got == (40, 56, [3], "Shoot"), got)
    chk("받을 파일도 가리키는 쪽 것", got and got[3] == "Shoot", got)
    chk("가리키는 데가 없으면 None", M._pick_anim(root, "Broken") is None)
    chk("서로 가리키면 None (무한히 안 돈다)",
        M._pick_anim(root, "Loop") is None)

    print("\n=== PNG 크기 ===")
    # 서버에는 Pillow 가 없다. 헤더에서 직접 읽는다.
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
           + (128).to_bytes(4, "big") + (320).to_bytes(4, "big"))
    chk("IHDR 에서 가로세로", M._png_size(png) == (128, 320), M._png_size(png))
    chk("PNG 가 아니면 (0,0)", M._png_size(b"nope") == (0, 0))
    chk("잘린 파일도 (0,0)", M._png_size(b"\x89PNG\r\n\x1a\n") == (0, 0))

    print("\n=== 이름 검사 (URL 로 들어온다) ===")
    # 막지 않으면 남의 저장소 아무 경로나 우리 서버로 받아오게 시킬 수 있다.
    for bad in ("../../etc/passwd", "Walk/../..", "AnimData", "walk", ""):
        try:
            M._check_anim(25, bad)
            ok = False
        except Exception:
            ok = True
        chk("막는다: %r" % bad, ok)
    try:
        M._check_anim(25, "Walk")
        ok = True
    except Exception:
        ok = False
    chk("Walk 는 통과", ok)
    try:
        M._check_anim(9999, "Walk")
        ok = False
    except Exception:
        ok = True
    chk("없는 도감 번호는 막는다", ok)

    print("\n=== 옛 캐시 이사 ===")
    # 걷기만 받던 시절의 파일. 그냥 두면 968종을 다시 받는다.
    d = os.path.join(M.WALK_DIR, "0025")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sheet.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    old_meta = {"ok": True, "frameW": 32, "frameH": 40, "durations": [8, 10],
                "frames": 2, "rows": 8, "src": "pmd",
                "rowmap": {"down": 0, "right": 2, "up": 4, "left": 6}}
    with open(os.path.join(d, "anim.json"), "w", encoding="utf-8") as f:
        json.dump(old_meta, f)

    M._migrate_old_walk(25)
    png_p, meta_p = M._anim_paths(25, "Walk")
    chk("Walk.png 로 옮겨졌다", os.path.exists(png_p))
    chk("옛 파일은 없어졌다", not os.path.exists(os.path.join(d, "sheet.png")))
    m = json.load(io.open(meta_p, encoding="utf-8"))
    chk("대각선이 채워졌다", m["rowmap"].get("downright") == 1, m["rowmap"])
    chk("네 방향은 그대로", m["rowmap"]["right"] == 2 and m["rowmap"]["left"] == 6)

    # 두 번 불러도 멀쩡해야 한다 (켤 때마다 부른다)
    M._migrate_old_walk(25)
    chk("두 번 불러도 그대로", os.path.exists(png_p))

    print("\n=== 없는 동작 표시 ===")
    mp = os.path.join(TMP, "miss.json")
    chk("None 을 돌려준다", M._mark_missing(mp) is None)
    chk("ok:false 로 남는다",
        json.load(io.open(mp, encoding="utf-8")) == {"ok": False})

    print("\n=== 이로치 걷는 도트 (1.4.0) ===")
    png_n, meta_n = M._anim_paths(25, "Walk")
    png_s, meta_s = M._anim_paths(25, "Walk", shiny=True)
    chk("이로치는 옆 폴더(0025s)에 둔다",
        os.path.basename(os.path.dirname(png_s)) == "0025s"
        and os.path.dirname(png_n) != os.path.dirname(png_s), (png_n, png_s))
    import urllib.error
    import urllib.request
    real = urllib.request.urlopen
    calls = []

    def fake(url, timeout=0):
        calls.append(url)
        raise fake.err
    urllib.request.urlopen = fake
    try:
        fake.err = urllib.error.URLError("끊김")
        chk("끊겼을 때는 없다고 적지 않는다 (다음에 다시)",
            M._anim_fetch(4, "Idle", shiny=True) is None
            and not os.path.exists(M._anim_paths(4, "Idle", True)[1]), calls[-1:])
        chk("이로치 주소는 폼 0000/0001 아래",
            calls and "/0004/0000/0001/AnimData.xml" in calls[-1], calls[-1:])
        fake.err = urllib.error.HTTPError(calls[-1], 503, "busy", None, None)
        chk("503 도 없다고 적지 않는다", M._anim_fetch(4, "Idle", shiny=True) is None
            and not os.path.exists(M._anim_paths(4, "Idle", True)[1]))
        fake.err = urllib.error.HTTPError(calls[-1], 404, "nope", None, None)
        M._anim_fetch(4, "Idle", shiny=True)
        chk("404 면 없다고 적는다 (클라이언트가 보통 색으로 걷는다)",
            json.load(io.open(M._anim_paths(4, "Idle", True)[1], encoding="utf-8"))
            == {"ok": False})
        chk("보통 걷기가 SpriteCollab 인 종은 두 번째 출처(followers)로 안 간다",
            not any("followers" in c for c in calls), calls)
        # 보통 걷기부터 followers 에서 온 종: 이로치도 followers 의 -b-s 로
        pn, mn = M._anim_paths(906, "Walk")
        os.makedirs(os.path.dirname(mn), exist_ok=True)
        with io.open(mn, "w", encoding="utf-8") as f:
            json.dump({"ok": True, "src": "follow", "frameW": 32, "frameH": 32,
                       "durations": [9], "frames": 1, "rows": 4}, f)

        class Resp(object):
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake2(url, timeout=0):
            calls.append(url)
            if "followsprites" in url:
                return Resp(b"\x89PNG" + b"0" * 200)
            raise urllib.error.HTTPError(url, 404, "nope", None, None)
        urllib.request.urlopen = fake2
        m = M._anim_fetch(906, "Walk", shiny=True)
        chk("followers 종의 이로치는 -b-s 로 받는다",
            m and m.get("shiny") and m.get("src") == "follow"
            and calls[-1].endswith("/906-b-s.png"), (m, calls[-1:]))
    finally:
        urllib.request.urlopen = real
    os.makedirs(os.path.dirname(meta_s), exist_ok=True)
    with io.open(meta_s, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "frameW": 32, "frameH": 40, "durations": [8],
                   "frames": 1, "rows": 8, "shiny": True}, f)
    chk("받아 둔 이로치 메타를 그대로 준다",
        M._meta_response(25, "Walk", shiny=True).get("shiny") is True)

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
