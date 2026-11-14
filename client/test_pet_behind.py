# -*- coding: utf-8 -*-
"""포켓몬을 다른 창 뒤로 (2.5.0, 설정 petBehind, 게시판 #533).

    python client/test_pet_behind.py

**창을 실제로 만든다.** 가짜 도트 한 장으로 Overlay 에 포켓몬 · 알을 세운다. 못 박는 것:

  1. 기본은 꺼짐 - 예전과 똑같이 도트 · 이름표가 '항상 위' 다 (옛 설정 파일에도 꺼진 채로 채워진다).
  2. 켜면 떠 있는 도트 · 이름표 · 알이 그 자리에서 '항상 위' 가 풀린다 (다시 만들지 않는다 - 같은 창).
     새로 나오는 포켓몬도 처음부터 뒤로.
  3. 숨겼다 다시 보일 때(PLAT.show_again - 배틀 · 긴급 숨기기 · 집중하기 뒤)도 뒤로. 진화 연출처럼 누가
     '항상 위' 를 다시 걸어도 3초마다 도는 keep_on_top 이 도로 뒤로 보낸다 (올리지 않는다).
  4. 끄면 다시 '항상 위'.
  5. 풀숲 · 연출처럼 표시가 없는 창은 그대로 '항상 위' 로 다시 올라간다.
  6. 설정 창 두 테마 모두에 손잡이가 있고, 누르면 저장하고 바로 건다.
  7. 자리는 그대로다 - 테두리 없는 창의 -topmost 를 바꾸면 (0, 0) 으로 튀는 일이 있다 (raise_above 와 같은 까닭).
"""
import os
import sys
import tempfile

HOME = tempfile.mkdtemp(prefix="poket-pet-behind-")
os.environ["POKET_HOME"] = HOME

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from PIL import Image                                      # noqa: E402

from poketdesktop import config, eggs_ui, sprites          # noqa: E402
from poketdesktop import overlay as OV                     # noqa: E402
from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0
ERRORS = []
AREA = (200, 150, 900, 650)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def dot_path():
    p = os.path.join(HOME, "dot.png")
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(6, 36):
            im.putpixel((x, y), (240, 200, 40, 255))
    im.save(p)
    return p


def mon(pid, name="피카츄"):
    return {"id": pid, "num": 25, "shiny": False,
            "info": {"name": name, "species": name, "level": 12, "types": ["전기"]}}


def top(w):
    return int(w.attributes("-topmost"))


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    settings = dict(config.DEFAULTS)
    settings["areaRect"] = list(AREA)
    settings["showNames"] = True
    ov = OV.Overlay(root, settings)
    ov.area = lambda: AREA
    path = dot_path()
    ov.paths[(25, False)] = path

    print("=== 기본값 ===")
    chk("기본은 꺼져 있다", config.DEFAULTS.get("petBehind") is False)
    chk("옛 설정 파일에도 꺼진 채로 채워진다", config.load_settings().get("petBehind") is False)
    ov.sync([mon(1), mon(2, "꼬부기")], {})
    root.update()
    p = ov.pets[1]
    anim = sprites.load_animation(path, 40, 0.5, 4.0)
    egg = eggs_ui.EggPet(ov, {"id": 7, "kind": "legendary", "name": "전설의 포켓몬 알",
                              "gotSec": 10, "needSec": 1000, "leftSec": 990}, anim)
    ov.eggs[7] = egg
    egg.x, egg.y = 300.0, 500.0
    egg.place()
    root.update()
    wins = list(ov.pet_windows())
    chk("도트 · 이름표 · 알 창을 다 찾는다 (넷 이상)", len(wins) >= 4 and p.win in wins and p.name_win in wins
        and egg.win in wins, len(wins))
    chk("꺼져 있으면 모두 '항상 위' (예전과 같다)", all(top(w) == 1 for w in wins), [top(w) for w in wins])

    print("\n=== 켜기 ===")
    win_before = p.win
    pos = (p.win.winfo_x(), p.win.winfo_y())
    settings["petBehind"] = True
    ov.apply_behind()
    root.update()
    chk("떠 있는 도트 · 이름표 · 알이 바로 '항상 위' 가 풀린다", all(top(w) == 0 for w in wins), [top(w) for w in wins])
    chk("  같은 창이다 (다시 만들지 않는다)", ov.pets[1].win is win_before)
    chk("  표시가 붙는다", all(getattr(w, "_poket_behind", False) for w in wins))
    chk("  자리는 그대로", (p.win.winfo_x(), p.win.winfo_y()) == pos, ((p.win.winfo_x(), p.win.winfo_y()), pos))
    ov.sync([mon(1), mon(2, "꼬부기"), mon(3, "파이리")], {})
    root.update()
    p3 = ov.pets[3]
    chk("새로 나온 포켓몬도 처음부터 뒤로", top(p3.win) == 0 and p3.win._poket_behind, top(p3.win))
    if p3.name_win is not None:
        chk("  그 이름표도", top(p3.name_win) == 0, top(p3.name_win))

    print("\n=== 다시 보일 때 · 누가 다시 올렸을 때 ===")
    p.win.withdraw()
    root.update()
    PLAT.show_again(p.win)
    root.update()
    chk("숨겼다 다시 보여도 (PLAT.show_again) 뒤로", top(p.win) == 0 and p.win.winfo_ismapped(), top(p.win))
    PLAT.raise_above(p.win)                      # 진화 연출처럼 누가 '항상 위' 를 다시 걸었다
    root.update()
    chk("  (누가 다시 '항상 위' 를 걸었다)", top(p.win) == 1)
    grass = tk.Toplevel(root)
    grass.overrideredirect(True)
    grass.geometry("40x40+50+50")
    PLAT.raise_above(grass)                      # 풀숲처럼 표시가 없는 창
    root.update()
    ov.keep_on_top()
    root.update()
    chk("3초마다 도는 keep_on_top 이 도로 뒤로 보낸다", top(p.win) == 0, top(p.win))
    chk("표시 없는 창(풀숲 · 연출)은 그대로 '항상 위'", top(grass) == 1, top(grass))

    print("\n=== 끄기 ===")
    settings["petBehind"] = False
    ov.apply_behind()
    root.update()
    wins = list(ov.pet_windows())
    chk("끄면 다시 모두 '항상 위'", all(top(w) == 1 for w in wins), [top(w) for w in wins])
    chk("  표시도 내려간다", not any(getattr(w, "_poket_behind", False) for w in wins))
    p.win.withdraw()
    PLAT.show_again(p.win)
    root.update()
    chk("  다시 보일 때도 '항상 위'", top(p.win) == 1)

    print("\n=== 설정 창 ===")
    for skin in ("기본", "dp"):
        src = open(os.path.join(HERE, "poketdesktop", "ui_settings.py" if skin == "기본" else
                                os.path.join("skins", "dp", "settings.py")), encoding="utf-8").read()
        chk("%s 테마에 '포켓몬을 다른 창 뒤로' 손잡이 (petBehind → _toggle_behind)" % skin,
            "포켓몬을 다른 창 뒤로" in src and '"petBehind"' in src and "_toggle_behind" in src)
    from poketdesktop import ui_settings
    saved = []
    fake = type("S", (), {})()
    fake.app = type("A", (), {})()
    fake.app.settings = settings
    fake.app.overlay = ov
    fake.app.refresh_tray = lambda: None
    fake._save = lambda: saved.append(dict(settings))
    var = tk.BooleanVar(value=True)
    ui_settings.SettingsWindow._toggle_behind(fake, "petBehind", var)
    root.update()
    chk("손잡이를 켜면 저장하고 바로 뒤로", saved and saved[-1]["petBehind"] is True and top(p.win) == 0, top(p.win))
    var.set(False)
    ui_settings.SettingsWindow._toggle_behind(fake, "petBehind", var)
    root.update()
    chk("  끄면 바로 '항상 위'", settings["petBehind"] is False and top(p.win) == 1)

    chk("도는 동안 오류 없음", not ERRORS, ERRORS[:2])
    grass.destroy()
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
