# -*- coding: utf-8 -*-
"""바탕화면 이름표가 서버 값이 바뀔 때 따라오는지 — 진짜 Tk 로 확인.

    python client/smoke_nameplate.py

**1.0.20 에서 고친 버그.** 레벨이 올라도 바탕화면 이름표의 숫자는 그대로였다.
이름표는 만들 때 글자를 박아 넣고, sync 는 mon 만 바꿔 끼웠기 때문이다.
포켓몬 관리 창은 열 때마다 새로 그려서 거기서만 올라 보였다.

**배틀 중에는 이름표를 치운다.** 체력바와 대미지 글자가 딱 이름표 줄에
그려져서 글자끼리 포개졌다. 막고 푸는 곳은 Overlay 하나다 - 막힌 동안
태어난 도트, 겹쳐 막기, 두 번 풀기, 진화가 끝나는 순간까지 여기서 본다.

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

from poketdesktop import config, evolve_fx, overlay         # noqa: E402
from poketdesktop import sprites, wild_ui                   # noqa: E402
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


def shown(w):
    """이름표 창이 떠 있는가. 창 관리자를 기다리지 않게 state() 로 본다."""
    try:
        return w is not None and w.state() == "normal"
    except tk.TclError:
        return False


def hidden(w):
    """아예 없거나, 있지만 숨어 있다. 없애 버린 창은 숨은 것으로 안 친다."""
    if w is None:
        return True
    try:
        return bool(w.winfo_exists()) and w.state() == "withdrawn"
    except tk.TclError:
        return False


def dot():
    """도트 한 장. 배틀 도트 대신 쓸 빨간 네모."""
    p = os.path.join(os.environ["POKET_HOME"], "dot.png")
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([6, 6, 25, 25], fill=(220, 60, 60, 255))
    im.save(p)
    return p


def mon(level, name="파이리", shiny=False, pid=1):
    return {"id": pid, "num": 4, "shiny": shiny,
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

    print("-- 배틀이 시작되면 이름표를 전부 치운다")
    ov.clear()
    settings["showNames"] = True
    ov.sync([mon(5, pid=1), mon(7, name="꼬부기", pid=2)], paths)
    settle(root)
    a, b = ov.pets[1], ov.pets[2]
    chk("처음에는 둘 다 이름표가 떠 있다", shown(a.name_win) and shown(b.name_win))
    plate_a = a.name_win
    ov.block_names()
    settle(root)
    chk("막으면 둘 다 숨는다", hidden(a.name_win) and hidden(b.name_win))
    chk("숨기기만 하고 없애지는 않는다", a.name_win is plate_a)
    chk("막힌 동안은 띄우면 안 된다고 답한다", not ov.names_visible())

    print("-- 막힌 동안 새로 온 도트는 이름표 없이 태어난다")
    ov.sync([mon(5, pid=1), mon(7, name="꼬부기", pid=2),
             mon(9, name="리자드", pid=3)], paths)
    settle(root)
    c = ov.pets.get(3)
    chk("sync 로 올라온 도트에 이름표가 없다", c is not None and c.name_win is None)
    foe = ov.make(mon(20, name="상대", pid=-1000))
    chk("투기장 상대편처럼 따로 만든 도트도 없다",
        foe is not None and foe.name_win is None)
    if foe is not None:
        foe.destroy()

    print("-- 겹쳐 막으면 다 풀어야 되살아난다")
    ov.block_names()
    ov.release_names()
    settle(root)
    chk("하나만 풀면 아직 숨어 있다", hidden(a.name_win) and c.name_win is None)

    print("-- 풀면 되살리고, 없던 이름표는 만든다")
    ids = [id(ov.pets[k]) for k in (1, 2, 3)]
    ov.release_names()
    settle(root)
    chk("원래 이름표가 다시 뜬다", shown(a.name_win) and shown(b.name_win))
    chk("같은 이름표 창을 다시 쓴다", a.name_win is plate_a)
    chk("막힌 동안 태어난 도트에도 이름표가 생긴다", shown(c.name_win))
    chk("도트는 다시 만들지 않았다", [id(ov.pets[k]) for k in (1, 2, 3)] == ids)

    print("-- 두 번 풀어도 0 아래로 안 내려간다")
    ov.release_names()
    chk("숫자가 0 에 머문다", ov._names_block == 0, ov._names_block)
    ov.block_names()
    settle(root)
    chk("그 뒤 한 번 막으면 숨는다", hidden(a.name_win) and hidden(c.name_win))

    print("-- 창이 숨은 도트(쓰러졌다)는 풀어도 이름표를 안 띄운다")
    b.win.withdraw()
    ov.release_names()
    settle(root)
    chk("창이 숨은 도트의 이름표는 숨은 채로", hidden(b.name_win))
    chk("나머지는 뜬다", shown(a.name_win))
    PLAT.show_again(b.win)
    ov.apply_names()
    settle(root)
    chk("창이 다시 보이면 이름표도 따라온다", shown(b.name_win))

    print("-- clear() 는 막아 둔 것도 같이 끝낸다")
    ov.block_names()
    ov.clear()
    chk("clear 뒤에는 0", ov._names_block == 0, ov._names_block)
    ov.sync([mon(5, pid=1), mon(7, name="꼬부기", pid=2)], paths)
    settle(root)
    chk("clear 뒤 새로 만든 도트에는 이름표가 붙는다",
        shown(ov.pets[1].name_win) and shown(ov.pets[2].name_win))

    print("-- 배틀 중에 크기를 바꿔 다시 만들어도 막아 둔 것은 그대로다")
    ov.block_names()
    ov.refresh_visuals()
    settle(root)
    chk("다시 만든 도트에 이름표가 안 붙는다",
        all(p.name_win is None for p in ov.pets.values()))
    ov.release_names()
    settle(root)
    chk("풀면 이름표가 생긴다", all(shown(p.name_win) for p in ov.pets.values()))

    print("-- 이름표 끄고 켜기는 도트를 다시 만들지 않는다")
    before = dict((k, id(p)) for k, p in ov.pets.items())
    settings["showNames"] = False
    ov.apply_names()
    settle(root)
    chk("끄면 이름표가 없어진다",
        all(p.name_win is None for p in ov.pets.values()))
    chk("끌 때 도트 객체가 그대로다",
        dict((k, id(p)) for k, p in ov.pets.items()) == before)
    settings["showNames"] = True
    ov.apply_names()
    settle(root)
    chk("켜면 이름표가 생긴다", all(shown(p.name_win) for p in ov.pets.values()))
    chk("켤 때도 도트 객체가 그대로다",
        dict((k, id(p)) for k, p in ov.pets.items()) == before)

    print("-- 배틀 중에 이름표를 끄면 끝날 때 반영된다")
    ov.block_names()
    settings["showNames"] = False
    ov.apply_names()
    settle(root)
    chk("배틀 중에는 건드리지 않는다",
        all(p.name_win is not None and hidden(p.name_win)
            for p in ov.pets.values()))
    ov.release_names()
    settle(root)
    chk("풀 때 끈 설정대로 없어진다",
        all(p.name_win is None for p in ov.pets.values()))
    settings["showNames"] = True
    ov.apply_names()
    settle(root)

    print("-- 야생 포켓몬에는 이름표가 없다 (야생 표식과 포개진다)")
    ctl = type("Ctl", (), {})()
    ctl.app = type("App", (), {})()
    ctl.app.overlay = ov
    ctl.app.battle = None
    anim = sprites.load_animation(paths[(4, False)], settings["targetHeight"],
                                  settings["minScale"], settings["maxScale"])
    wp = wild_ui.WildPet(ctl, mon(3, name="꼬렛", pid=900), anim)
    settle(root)
    chk("야생에는 이름표가 없다", wp.name_win is None)
    chk("야생 표식은 그대로 있다", wp.badge_win is not None)
    wp.make_nameplate()
    chk("이름표를 만들라고 해도 안 생긴다", wp.name_win is None)
    wp.destroy()

    print("-- 막힌 동안 진화가 끝나도 이름표를 안 띄운다")
    app = type("App", (), {})()
    app.root, app.overlay, app.api, app.settings = root, ov, None, settings
    p = ov.pets[1]
    ov.block_names()
    p.evolving = True
    ev = evolve_fx.Evolution(app, p, {"fromKr": "파이리", "toKr": "리자드"})
    ev.freeze()
    ev.finish()
    settle(root)
    chk("막힌 동안 끝난 진화는 이름표를 안 띄운다", hidden(p.name_win))
    chk("진화 표시는 풀린다", not getattr(p, "evolving", False))
    ov.release_names()
    settle(root)
    chk("풀면 그 도트 이름표도 돌아온다", shown(p.name_win))

    print("-- 진화 중에 막혔다 풀려도 연출이 끝나면 이름표가 생긴다")
    p.evolving = True
    ev = evolve_fx.Evolution(app, p, {"fromKr": "파이리", "toKr": "리자드"})
    ev.freeze()
    ov.block_names()
    evolve_fx.refresh_nameplate(p)      # 새 모습이 드러나며 이름표를 다시 만든다
    chk("막힌 동안에는 새로 안 만든다", p.name_win is None)
    ov.release_names()
    settle(root)
    chk("진화 중인 도트는 풀려도 건너뛴다", p.name_win is None)
    ev.finish()
    settle(root)
    chk("연출이 끝나면 이름표가 생긴다", shown(p.name_win))

    ov.clear()
    root.destroy()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
