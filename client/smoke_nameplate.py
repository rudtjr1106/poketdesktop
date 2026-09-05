# -*- coding: utf-8 -*-
"""바탕화면 이름표가 서버 값이 바뀔 때 따라오는지 — 진짜 Tk 로 확인.

    python client/smoke_nameplate.py

**1.0.20 에서 고친 버그.** 레벨이 올라도 바탕화면 이름표의 숫자는 그대로였다.
이름표는 만들 때 글자를 박아 넣고, sync 는 mon 만 바꿔 끼웠기 때문이다.
포켓몬 관리 창은 열 때마다 새로 그려서 거기서만 올라 보였다.

창을 실제로 띄우므로 화면이 있는 곳에서만 돈다. 도트는 서버 없이 여기서
그려서 쓴다 - 사용자의 캐시를 안 건드린다.
"""
import os
import sys
import tempfile

# 사용자의 진짜 설정·캐시를 덮어쓰면 안 된다.
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-smoke-nameplate-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from poketdesktop import config, overlay                    # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=6):
    for _ in range(n):
        root.update()


def plate(pet):
    """이름표 글자. 옛 코드처럼 name_label 이 없으면 빈 문자열 - 그래야
    터지지 않고 FAIL 줄로 남는다."""
    lbl = getattr(pet, "name_label", None)
    return lbl.cget("text") if lbl is not None else ""


def dot():
    """도트 한 장. 배틀 도트 대신 쓸 빨간 네모."""
    p = os.path.join(os.environ["POKET_HOME"], "dot.png")
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([6, 6, 25, 25], fill=(220, 60, 60, 255))
    im.save(p)
    return p


def mon(level, name="파이리", shiny=False):
    return {"id": 1, "num": 4, "shiny": shiny,
            "info": {"name": name, "species": "파이리", "level": level,
                     "types": ["불꽃"]}}


def main():
    # 맥은 Tk 를 만들기 전에 이걸 불러야 한다. 안 그러면 지난번에
    # 비정상 종료한 적이 있는 맥에서 '창을 복원할까요' 창에 걸려 멈춘다.
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    settings = dict(config.DEFAULTS)
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    paths = {(4, False): dot()}

    print("-- 레벨이 오르면 이름표가 따라온다")
    ov.sync([mon(5)], paths)
    settle(root)
    pet = ov.pets[1]
    chk("이름표가 생겼다", pet.name_win is not None
        and getattr(pet, "name_label", None) is not None)
    chk("처음에 Lv.5", "Lv.5" in plate(pet), plate(pet))
    win_before = pet.name_win

    # 서버가 레벨 6 으로 알려준다 (배틀 끝의 request_sync 가 이 길이다)
    ov.sync([mon(6)], {})
    settle(root)
    chk("같은 도트 객체를 그대로 쓴다", ov.pets[1] is pet)
    chk("이름표 숫자가 6 으로 바뀐다", "Lv.6" in plate(pet), plate(pet))
    chk("이름표 창을 새로 만들지 않았다", pet.name_win is win_before)
    chk("mon 도 새 값이다", pet.mon["info"]["level"] == 6)

    print("-- 별명을 바꿔도 따라온다")
    ov.sync([mon(6, name="불꽃이")], {})
    settle(root)
    chk("새 별명이 보인다", "불꽃이" in plate(pet), plate(pet))

    print("-- 긴 별명이면 창도 따라 늘어난다")
    w1 = pet.name_win.winfo_width()
    ov.sync([mon(6, name="아주긴별명이름표확인용")], {})
    settle(root)
    w2 = pet.name_win.winfo_width()
    chk("이름표 창 너비가 글자에 맞춰 는다", w2 > w1 + 40, (w1, w2))

    print("-- 이로치 표시")
    ov.sync([mon(6, name="불꽃이", shiny=True)], {})
    settle(root)
    chk("별이 붙는다", plate(pet).startswith("★"), plate(pet))

    print("-- 이름표를 안 켠 사람")
    ov.clear()
    settings["showNames"] = False
    ov.sync([mon(5)], paths)
    settle(root)
    pet2 = ov.pets[1]
    chk("이름표가 없다", pet2.name_win is None)
    try:
        ov.sync([mon(6)], {})
        settle(root)
        chk("이름표 없이도 sync 가 조용히 지나간다", pet2.mon["info"]["level"] == 6)
    except Exception as e:                                  # noqa: BLE001
        chk("이름표 없이도 sync 가 조용히 지나간다", False, e)

    ov.clear()
    root.destroy()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
