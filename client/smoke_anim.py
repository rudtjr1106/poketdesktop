# -*- coding: utf-8 -*-
"""배틀 연출이 실제로 움직이는지 프레임으로 잡아본다.

    python client/smoke_anim.py [서버주소]

배틀을 하나 만들고 기술을 쓴 뒤, 애니메이션이 도는 동안 화면을 여러 장
찍어서 한 장의 필름처럼 이어 붙인다. 결과: anim_strip.png
"""
import os
import random
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image, ImageDraw, ImageFont, ImageGrab   # noqa: E402

from poketdesktop import config                          # noqa: E402
from poketdesktop import ui_common as U                   # noqa: E402
from poketdesktop.api import Api                          # noqa: E402
from poketdesktop.ui_battle import BattleWindow           # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OUT = os.path.abspath(os.path.join(HERE, "..", "anim_strip.png"))

SHOTS = 10          # 몇 장 찍을지
EVERY = 150         # 몇 ms 간격으로
CROP = (0, 0, 640, 300)     # 무대만 잘라낸다


class FakeApp(object):
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.balls = 10
        self.settings = config.load_settings()
        self.battle_window = None
        self.box_window = None
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
    im = ImageGrab.grab((x, y, x + win.winfo_width(), y + win.winfo_height()))
    return im.crop(CROP)


def main():
    user = "anim%05d" % random.randrange(99999)
    pw = "animtest12345"
    api = Api(BASE)
    api.register(user, pw, "CHARMANDER")

    # 확실히 때릴 수 있게 야생을 하나 세운다
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
    app = FakeApp(root, api)
    bw = BattleWindow(root, app, b, None)
    app.battle_window = bw

    frames = []
    state = {"n": 0}

    def start():
        moves = bw.b["me"].get("moves") or []
        dmg = [m for m in moves if (m.get("power") or 0) > 0 and m["pp"] > 0]
        pick = (dmg or moves)[0]
        print("  기술: %s" % pick["kr"])
        bw.use(pick["key"])
        root.after(120, snap)

    def snap():
        state["n"] += 1
        try:
            frames.append(grab(bw.win))
        except Exception as e:                      # noqa: BLE001
            print("  캡처 실패: %s" % e)
        if state["n"] < SHOTS:
            return root.after(EVERY, snap)
        finish()

    def finish():
        print("  %d장 캡처" % len(frames))
        if frames:
            cols = 5
            rows = (len(frames) + cols - 1) // cols
            fw, fh = frames[0].size
            pad, label = 6, 20
            sheet = Image.new("RGB", (cols * (fw + pad) + pad,
                                      rows * (fh + label + pad) + pad),
                              (20, 20, 26))
            d = ImageDraw.Draw(sheet)
            try:
                font = ImageFont.truetype("malgun.ttf", 13)
            except Exception:
                font = None
            for i, im in enumerate(frames):
                cx = pad + (i % cols) * (fw + pad)
                cy = pad + (i // cols) * (fh + label + pad)
                sheet.paste(im, (cx, cy))
                d.text((cx + 4, cy + fh + 3), "%d프레임 (%dms)" % (i + 1, i * EVERY),
                       fill=(190, 190, 205), font=font)
            sheet.save(OUT)
            print("  저장: %s (%dx%d)" % (OUT, sheet.width, sheet.height))
        try:
            bw.close()
        except Exception:
            pass
        try:
            api.delete_account(pw)
        except Exception:
            pass
        root.quit()

    root.after(3000, start)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
