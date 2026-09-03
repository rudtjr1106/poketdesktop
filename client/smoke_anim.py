# -*- coding: utf-8 -*-
"""바탕화면 배틀을 실제로 한 판 돌려보고 화면을 찍는다.

    python client/smoke_anim.py [서버주소]

임시 계정으로 야생을 하나 세우고, 진짜 클라이언트와 같은 경로로
바탕화면 배틀을 진행하면서 활동 영역을 여러 장 캡처한다.
결과: battle_strip.png
"""
import os
import random
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image, ImageDraw, ImageFont, ImageGrab       # noqa: E402

from common import pokelogic as P                             # noqa: E402
from poketdesktop import config, sprite_cache                 # noqa: E402
from poketdesktop import platform_os as PLAT                  # noqa: E402
from poketdesktop import ui_common as U                       # noqa: E402
from poketdesktop.api import Api, load_pokedex                # noqa: E402
from poketdesktop.desktop_battle import DesktopBattle         # noqa: E402
from poketdesktop.overlay import Overlay                      # noqa: E402
from poketdesktop.wild_ui import WildController               # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OUT = os.path.abspath(os.path.join(HERE, "..", "battle_strip.png"))
SHOTS = 14
EVERY = 700


class FakeApp(object):
    """진짜 App 이 배틀에 쓰는 부분만 흉내낸다."""

    def __init__(self, root, api, dex):
        self.root, self.api, self.dex = root, api, dex
        self.balls = 10
        self.settings = config.load_settings()
        self.overlay = None
        self.wild = None
        self.battle = None
        self.box_window = None
        self.notes = []

    def notify(self, m):
        self.notes.append(m)
        print("    [알림] %s" % m)

    def refresh_tray(self):
        pass

    def request_sync(self):
        pass

    def open_battle(self, battle, intro=None):
        if not battle or self.battle:
            return
        self.battle = DesktopBattle(self, battle, intro)


def main():
    user = "dbt%05d" % random.randrange(99999)
    pw = "dbtest123456"
    api = Api(BASE)
    api.register(user, pw, "CHARMANDER")
    dexdata, _ = load_pokedex(api)
    dex = P.Pokedex(dexdata)

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    PLAT.dpi_aware()
    U.init_fonts(root)
    U.apply_theme(root)

    app = FakeApp(root, api, dex)
    app.overlay = Overlay(root, app.settings)
    app.overlay.start()
    app.wild = WildController(app)

    # 내 포켓몬을 바탕화면에 세운다
    mons = api.desktop()
    paths = sprite_cache.ensure_many(
        api, [(m.get("num"), m.get("shiny")) for m in mons])
    app.overlay.sync(mons, paths)
    print("  내 포켓몬 %d마리 배치" % len(app.overlay.pets))

    # 야생을 세운다
    w = api.wild(force=True)
    wd = w["wild"]
    if wd["state"] == "grass":
        wd = api.wild_reveal(wd["id"])["wild"]
    mon = wd["pokemon"]
    p = sprite_cache.ensure(api, mon["num"], mon.get("shiny"))
    app.overlay.paths[(mon["num"], bool(mon.get("shiny")))] = p
    app.wild.wild_id = wd["id"]
    app.wild.show_wild(mon)
    print("  야생 %s Lv.%s 등장" % (mon["info"]["species"], mon["level"]))

    area = app.overlay.area()
    frames = []
    state = {"n": 0}

    def shoot():
        state["n"] += 1
        try:
            pad = 100
            box = (max(0, area[0] - pad), max(0, area[1] - pad),
                   area[2] + 20, area[3] + 20)
            frames.append(ImageGrab.grab(box))
        except Exception as e:                       # noqa: BLE001
            print("    캡처 실패: %s" % e)
        if state["n"] < SHOTS and (app.battle is None or not app.battle.closed):
            return root.after(EVERY, shoot)
        finish()

    def start():
        print("")
        print("  === 배틀 시작 (왼쪽 클릭과 같은 경로) ===")
        app.wild.start_battle()
        root.after(500, shoot)

    def finish():
        print("")
        print("  캡처 %d장" % len(frames))
        if frames:
            cols = 5
            rows = (len(frames) + cols - 1) // cols
            sc = 0.42
            fw = int(frames[0].width * sc)
            fh = int(frames[0].height * sc)
            pad, lab = 6, 18
            sheet = Image.new("RGB", (cols * (fw + pad) + pad,
                                      rows * (fh + lab + pad) + pad), (18, 18, 24))
            d = ImageDraw.Draw(sheet)
            from poketdesktop.effects import pil_font
            try:
                font = pil_font(12)
            except Exception:                               # noqa: BLE001
                font = None
            for i, im in enumerate(frames):
                cx = pad + (i % cols) * (fw + pad)
                cy = pad + (i // cols) * (fh + lab + pad)
                sheet.paste(im.resize((fw, fh), Image.LANCZOS), (cx, cy))
                d.text((cx + 3, cy + fh + 2), "%.1f초" % (i * EVERY / 1000.0),
                       fill=(200, 200, 215), font=font)
            sheet.save(OUT)
            print("  저장: %s (%dx%d)" % (OUT, sheet.width, sheet.height))
        try:
            if app.battle:
                app.battle.close()
            app.wild.stop()
            app.overlay.stop()
            app.overlay.clear()
        except Exception:
            pass
        try:
            api.delete_account(pw)
            print("  계정 삭제")
        except Exception:
            pass
        root.quit()

    root.after(2500, start)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
