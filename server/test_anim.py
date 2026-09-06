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

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
