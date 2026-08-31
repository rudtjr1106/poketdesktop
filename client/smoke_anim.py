# -*- coding: utf-8 -*-
"""바탕화면 배틀 무대와 기술 이펙트를 눈으로 확인한다.

    python client/smoke_anim.py [서버주소]

배틀을 하나 만들고 무대를 띄운 다음, 여러 종류의 기술 이펙트를 차례로
재생하면서 프레임을 찍는다. 결과: fx_<연출이름>.png
"""
import os
import random
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image, ImageDraw, ImageFont, ImageGrab      # noqa: E402

from common import pokelogic as P                            # noqa: E402
from poketdesktop import battle_fx as FX                     # noqa: E402
from poketdesktop import config                              # noqa: E402
from poketdesktop import ui_common as U                      # noqa: E402
from poketdesktop.api import Api, load_pokedex               # noqa: E402
from poketdesktop.ui_battle import BattleWindow              # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OUT = os.path.abspath(os.path.join(HERE, ".."))

# 연출 종류별로 대표 기술 하나씩
SAMPLES = [
    ("EMBER", "불꽃세례", "beam"),
    ("WATERGUN", "물대포", "beam"),
    ("THUNDERBOLT", "10만볼트", "beam"),
    ("RAZORLEAF", "잎날가르기", "beam"),
    ("SLUDGEBOMB", "오물폭탄", "ball"),
    ("AURASPHERE", "파동탄", "pulse"),
    ("HYPERVOICE", "하이퍼보이스", "sound"),
    ("STUNSPORE", "저리가루", "powder"),
    ("THUNDERPUNCH", "번개펀치", "punch"),
    ("BITE", "물기", "bite"),
    ("TACKLE", "몸통박치기", "contact"),
    ("SWORDSDANCE", "칼춤", "self"),
]
SHOTS = 6
EVERY = 130


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root, self.api, self.dex = root, api, dex
        self.balls = 10
        self.settings = config.load_settings()
        self.battle_window = None
        self.box_window = None
        self.overlay = None
        self.wild = None

    def notify(self, m):
        pass

    def refresh_tray(self):
        pass

    def request_sync(self):
        pass


def grab(win):
    win.update_idletasks()
    x, y = win.winfo_rootx(), win.winfo_rooty()
    return ImageGrab.grab((x, y, x + win.winfo_width(), y + win.winfo_height()))


def strip(frames, path, title):
    if not frames:
        return
    cols = len(frames)
    fw, fh = frames[0].size
    scale = 0.52
    fw, fh = int(fw * scale), int(fh * scale)
    pad, label = 5, 22
    sheet = Image.new("RGB", (cols * (fw + pad) + pad, fh + label + pad * 2),
                      (18, 18, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("malgun.ttf", 13)
    except Exception:
        font = None
    d.text((pad, pad - 1), title, fill=(240, 200, 90), font=font)
    for i, im in enumerate(frames):
        sheet.paste(im.resize((fw, fh), Image.LANCZOS),
                    (pad + i * (fw + pad), label + pad))
    sheet.save(path)
    return sheet


def main():
    user = "fx%05d" % random.randrange(99999)
    pw = "fxtest123456"
    api = Api(BASE)
    api.register(user, pw, "CHARMANDER")
    dexdata, _how = load_pokedex(api)
    dex = P.Pokedex(dexdata)

    w = api.wild(force=True)
    wd = w["wild"]
    if wd["state"] == "grass":
        wd = api.wild_reveal(wd["id"])["wild"]
    b = api.battle_start(wd["id"])["battle"]
    print("  %s vs 야생 %s" % (b["me"]["name"], b["foe"]["name"]))

    root = tk.Tk()
    root.withdraw()
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root, api, dex)
    st = BattleWindow(root, app, b, None)
    app.battle_window = st

    sheets = []
    state = {"idx": 0, "shot": 0, "frames": []}

    def next_move():
        if state["idx"] >= len(SAMPLES):
            return done()
        key, kr, expect = SAMPLES[state["idx"]]
        move = dex.move(key)
        got = FX.style_of(move) if move else "?"
        mark = "OK  " if got == expect else "다름"
        print("  %s %-12s %-9s 연출=%-8s (예상 %s)"
              % (mark, kr, move.get("type") if move else "?", got, expect))
        state["frames"] = []
        state["shot"] = 0
        src = st.me.center()
        dst = st.foe.center()
        st.say("%s 의 %s!" % (b["me"]["name"], kr))
        st.fx = FX.Effect(st, move, src, dst, lambda: None)
        st.fx.play()
        root.after(60, snap)

    def snap():
        state["shot"] += 1
        try:
            state["frames"].append(grab(st.win))
        except Exception as e:                       # noqa: BLE001
            print("     캡처 실패: %s" % e)
        if state["shot"] < SHOTS:
            return root.after(EVERY, snap)
        key, kr, _ = SAMPLES[state["idx"]]
        sh = strip(state["frames"],
                   os.path.join(OUT, "fx_%02d.png" % state["idx"]),
                   "%s  (%s)" % (kr, FX.style_of(dex.move(key))))
        if sh:
            sheets.append(sh)
        if st.fx:
            st.fx.stop()
        state["idx"] += 1
        root.after(320, next_move)

    def done():
        if sheets:
            wmax = max(s.width for s in sheets)
            total = sum(s.height + 4 for s in sheets)
            big = Image.new("RGB", (wmax, total), (18, 18, 24))
            yy = 0
            for s in sheets:
                big.paste(s, (0, yy))
                yy += s.height + 4
            p = os.path.join(OUT, "fx_all.png")
            big.save(p)
            print("")
            print("  모아보기: %s (%dx%d)" % (p, big.width, big.height))
        try:
            st.close()
        except Exception:
            pass
        try:
            api.delete_account(pw)
        except Exception:
            pass
        root.quit()

    root.after(3200, next_move)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
