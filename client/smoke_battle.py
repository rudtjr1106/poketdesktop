# -*- coding: utf-8 -*-
"""배틀 화면 눈으로 확인하기.

    python client/smoke_battle.py [서버주소]

임시 계정으로 진짜 배틀을 하나 만들고 배틀 창을 띄운다.
몇 초 뒤 창을 그림으로 저장하고, 기술을 한 번 눌러본 뒤 정리한다.
"""
import os
import random
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import config, sprite_cache          # noqa: E402
from poketdesktop import ui_common as U                # noqa: E402
from poketdesktop.api import Api                       # noqa: E402
from poketdesktop.ui_battle import BattleWindow        # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OUT = os.path.join(HERE, "..", "battle_shot.png")


class FakeApp(object):
    """배틀 창이 기대하는 최소한의 껍데기."""

    def __init__(self, root, api):
        self.root = root
        self.api = api
        self.balls = 10
        self.settings = config.load_settings()
        self.battle_window = None
        self.box_window = None
        self.wild = None
        self.notes = []

    def notify(self, msg):
        self.notes.append(msg)
        print("  [알림] %s" % msg)

    def refresh_tray(self):
        pass

    def request_sync(self):
        pass


def shot(win, path, label):
    try:
        from PIL import ImageGrab
        win.update_idletasks()
        x, y = win.winfo_rootx(), win.winfo_rooty()
        w, h = win.winfo_width(), win.winfo_height()
        im = ImageGrab.grab((x, y, x + w, y + h))
        im.save(path)
        print("  %s 저장: %s (%dx%d)" % (label, path, im.width, im.height))
        return True
    except Exception as e:                              # noqa: BLE001
        print("  캡처 실패: %s" % e)
        return False


def main():
    user = "smoke%05d" % random.randrange(99999)
    pw = "smoketest12345"
    api = Api(BASE)
    print("=== 준비 ===")
    r = api.register(user, pw, "CHARMANDER")
    print("  계정 %s" % user)

    # 야생을 앞에 세우고 배틀 시작
    w = api.wild(force=True)
    wd = w["wild"]
    if wd["state"] == "grass":
        wd = api.wild_reveal(wd["id"])["wild"]
    print("  야생 %s Lv.%s" % (wd["pokemon"]["info"]["species"],
                             wd["pokemon"]["level"]))
    started = api.battle_start(wd["id"])
    b = started["battle"]
    print("  배틀 %d  내 %s(%d/%d) vs %s(%d/%d)"
          % (b["id"], b["me"]["name"], b["me"]["hp"], b["me"]["maxhp"],
             b["foe"]["name"], b["foe"]["hp"], b["foe"]["maxhp"]))
    print("  내 기술: %s" % ", ".join(
        "%s(%s/%s)" % (m["kr"], m["pp"], m["maxpp"]) for m in b["me"]["moves"]))

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
    print("")
    print("=== 배틀 창 ===")
    bw = BattleWindow(root, app, b, started.get("intro"))
    app.battle_window = bw

    state = {"step": 0}

    def tick():
        state["step"] += 1
        n = state["step"]
        if n == 1:
            ok = bw.me is not None and bw.foe is not None
            print("  %s 양쪽 도트 로드" % ("OK  " if ok else "FAIL"))
            print("  %s 기술 버튼 %d개"
                  % ("OK  " if bw.move_btns else "FAIL", len(bw.move_btns)))
            print("  %s 메시지: %s" % ("OK  ", bw.msg.cget("text")))
            shot(bw.win, os.path.abspath(OUT), "배틀 화면")
        elif n == 2:
            moves = bw.b["me"].get("moves") or []
            dmg = [m for m in moves if (m.get("power") or 0) > 0 and m["pp"] > 0]
            pick = (dmg or moves)[0]
            print("  기술 사용: %s" % pick["kr"])
            bw.use(pick["key"])
        elif n == 4:
            print("  %s 턴이 진행됨 (turn=%s)"
                  % ("OK  " if bw.b.get("turn", 0) >= 1 else "FAIL",
                     bw.b.get("turn")))
            print("  메시지: %s" % bw.msg.cget("text"))
            shot(bw.win, os.path.abspath(OUT.replace(".png", "2.png")), "한 턴 뒤")
        elif n >= 5:
            print("")
            print("=== 정리 ===")
            try:
                bw.close()
            except Exception:
                pass
            try:
                api.delete_account(pw)
                print("  계정 삭제")
            except Exception as e:
                print("  계정 삭제 실패: %s" % e)
            root.quit()
            return
        root.after(2600, tick)

    root.after(2600, tick)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
